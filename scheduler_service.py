"""
scheduler_service.py - Encrypted Multi-Worker Safe Scheduler for Automated Telegram Digests
Schedules daily or weekly-Monday automated refreshes + executive Telegram dispatch
for saved AutoBI reports, guarded by an atomic SQLite lease lock across Gunicorn workers.
"""

import os
import time
import uuid
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional

from security_vault import encrypt_json, decrypt_json, blind_index_email

_SCHEDULER_THREAD_LOCK = threading.Lock()
_SCHEDULER_STARTED = False


def compute_next_run(cadence: str, from_ts: Optional[float] = None, hour_utc: int = 4) -> float:
    """Compute next UTC Unix timestamp for 'daily' or 'weekly_mon' cadence."""
    base_ts = float(from_ts) if from_ts is not None else time.time()
    dt = datetime.fromtimestamp(base_ts, tz=timezone.utc)
    hour_clamped = max(0, min(23, int(hour_utc)))
    candidate = dt.replace(hour=hour_clamped, minute=0, second=0, microsecond=0)

    if cadence == "weekly_mon":
        # weekday(): Monday == 0
        days_ahead = (0 - candidate.weekday()) % 7
        candidate = candidate + timedelta(days=days_ahead)
        if candidate.timestamp() <= base_ts:
            candidate = candidate + timedelta(days=7)
        return candidate.timestamp()

    # Default: daily
    if candidate.timestamp() <= base_ts:
        candidate = candidate + timedelta(days=1)
    return candidate.timestamp()


class SchedulerService:
    """SQLite WAL encrypted schedule manager with atomic lease locking."""

    def __init__(self, db_path: Optional[str] = None):
        if not db_path:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            db_dir = os.path.join(base_dir, ".sessions")
            os.makedirs(db_dir, exist_ok=True)
            db_path = os.path.join(db_dir, "schedules.db")
        self.db_path = db_path
        self._init_sqlite()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10.0, isolation_level=None)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
        return conn

    def _init_sqlite(self):
        conn = self._get_conn()
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS report_schedules (
                    schedule_id TEXT PRIMARY KEY,
                    report_id TEXT UNIQUE NOT NULL,
                    owner_hash TEXT NOT NULL,
                    encrypted_config TEXT NOT NULL,
                    cadence TEXT NOT NULL,
                    next_run_at REAL NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    last_run_at REAL,
                    last_status TEXT,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                );
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sched_due ON report_schedules(enabled, next_run_at);")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS scheduler_locks (
                    lock_name TEXT PRIMARY KEY,
                    owner_id TEXT NOT NULL,
                    expires_at REAL NOT NULL
                );
                """
            )
        finally:
            conn.close()

    def upsert_schedule(
        self,
        owner_email: str,
        report_id: str,
        cadence: str = "weekly_mon",
        targets: Optional[List[str]] = None,
        alert_only_on_anomalies: bool = False,
        hour_utc: int = 4,
        enabled: bool = True,
        next_run_at: Optional[float] = None,
    ) -> Dict[str, Any]:
        cad = cadence if cadence in ("daily", "weekly_mon") else "weekly_mon"
        clean_targets = [str(t).strip() for t in (targets or []) if str(t).strip()]
        if enabled and not clean_targets:
            raise ValueError("At least one Telegram target is required to enable scheduled digests.")

        owner_hash = blind_index_email(owner_email)
        now = time.time()
        next_ts = float(next_run_at) if next_run_at is not None else compute_next_run(cad, now, hour_utc=hour_utc)
        schedule_id = str(uuid.uuid4())
        cfg_payload = {
            "owner_email": owner_email,
            "targets": clean_targets,
            "alert_only_on_anomalies": bool(alert_only_on_anomalies),
            "hour_utc": max(0, min(23, int(hour_utc))),
            "cadence": cad,
        }
        enc_cfg = encrypt_json(cfg_payload, aad=f"sched:{report_id}:{owner_hash}".encode("utf-8"))

        conn = self._get_conn()
        try:
            conn.execute("BEGIN IMMEDIATE;")
            existing = conn.execute(
                "SELECT schedule_id FROM report_schedules WHERE report_id = ?;",
                (report_id,),
            ).fetchone()
            if existing:
                schedule_id = existing[0]
                conn.execute(
                    """
                    UPDATE report_schedules
                    SET owner_hash = ?, encrypted_config = ?, cadence = ?, next_run_at = ?,
                        enabled = ?, updated_at = ?
                    WHERE report_id = ?;
                    """,
                    (owner_hash, enc_cfg, cad, next_ts, 1 if enabled else 0, now, report_id),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO report_schedules (
                        schedule_id, report_id, owner_hash, encrypted_config, cadence,
                        next_run_at, enabled, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (schedule_id, report_id, owner_hash, enc_cfg, cad, next_ts, 1 if enabled else 0, now, now),
                )
            conn.execute("COMMIT;")
        except Exception:
            try:
                conn.execute("ROLLBACK;")
            except Exception:
                pass
            raise
        finally:
            conn.close()

        return {
            "schedule_id": schedule_id,
            "report_id": report_id,
            "cadence": cad,
            "hour_utc": cfg_payload["hour_utc"],
            "targets": clean_targets,
            "alert_only_on_anomalies": bool(alert_only_on_anomalies),
            "enabled": bool(enabled),
            "next_run_at": next_ts,
        }

    def get_schedule(self, owner_email: str, report_id: str) -> Optional[Dict[str, Any]]:
        owner_hash = blind_index_email(owner_email)
        conn = self._get_conn()
        try:
            row = conn.execute(
                """
                SELECT schedule_id, encrypted_config, cadence, next_run_at, enabled, last_run_at, last_status
                FROM report_schedules
                WHERE report_id = ? AND owner_hash = ?;
                """,
                (report_id, owner_hash),
            ).fetchone()
        finally:
            conn.close()

        if not row:
            return None
        try:
            cfg = decrypt_json(row[1], aad=f"sched:{report_id}:{owner_hash}".encode("utf-8")) or {}
        except Exception:
            return None

        return {
            "schedule_id": row[0],
            "report_id": report_id,
            "cadence": row[2],
            "hour_utc": cfg.get("hour_utc", 4),
            "targets": cfg.get("targets", []),
            "alert_only_on_anomalies": bool(cfg.get("alert_only_on_anomalies")),
            "enabled": bool(row[4]),
            "next_run_at": row[3],
            "last_run_at": row[5],
            "last_status": row[6],
        }

    def delete_schedule(self, owner_email: str, report_id: str) -> bool:
        owner_hash = blind_index_email(owner_email)
        conn = self._get_conn()
        try:
            conn.execute("BEGIN IMMEDIATE;")
            cur = conn.execute(
                "DELETE FROM report_schedules WHERE report_id = ? AND owner_hash = ?;",
                (report_id, owner_hash),
            )
            conn.execute("COMMIT;")
            return cur.rowcount > 0
        except Exception:
            try:
                conn.execute("ROLLBACK;")
            except Exception:
                pass
            return False
        finally:
            conn.close()

    def acquire_lease(self, lock_name: str, owner_id: str, ttl_seconds: float = 55.0, now: Optional[float] = None) -> bool:
        ts = float(now) if now is not None else time.time()
        expires = ts + ttl_seconds
        conn = self._get_conn()
        try:
            conn.execute("BEGIN IMMEDIATE;")
            row = conn.execute(
                "SELECT owner_id, expires_at FROM scheduler_locks WHERE lock_name = ?;",
                (lock_name,),
            ).fetchone()
            if row and float(row[1]) > ts and row[0] != owner_id:
                conn.execute("COMMIT;")
                return False
            conn.execute(
                """
                INSERT INTO scheduler_locks (lock_name, owner_id, expires_at)
                VALUES (?, ?, ?)
                ON CONFLICT(lock_name) DO UPDATE SET owner_id = excluded.owner_id, expires_at = excluded.expires_at;
                """,
                (lock_name, owner_id, expires),
            )
            conn.execute("COMMIT;")
            return True
        except Exception:
            try:
                conn.execute("ROLLBACK;")
            except Exception:
                pass
            return False
        finally:
            conn.close()

    def release_lease(self, lock_name: str, owner_id: str):
        conn = self._get_conn()
        try:
            conn.execute("BEGIN IMMEDIATE;")
            conn.execute("DELETE FROM scheduler_locks WHERE lock_name = ? AND owner_id = ?;", (lock_name, owner_id))
            conn.execute("COMMIT;")
        except Exception:
            try:
                conn.execute("ROLLBACK;")
            except Exception:
                pass
        finally:
            conn.close()

    def run_single(
        self,
        owner_email: str,
        report_id: str,
        runner_fn: Callable[[str, str], Dict[str, Any]],
        dispatch_fn: Callable[..., Dict[str, Any]],
        override_targets: Optional[List[str]] = None,
        now: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Execute a single report refresh + optional anomaly-gated Telegram dispatch."""
        ts = float(now) if now is not None else time.time()
        sched = self.get_schedule(owner_email, report_id)
        targets = override_targets if override_targets else (sched.get("targets", []) if sched else [])
        alert_only = bool(sched.get("alert_only_on_anomalies")) if sched else False

        run_out = runner_fn(owner_email, report_id)
        sess_data = run_out["session_data"]
        anom_summary = run_out.get("anomaly_summary") or {}
        flag_total = int(anom_summary.get("total_flags", 0))
        crit_total = int(anom_summary.get("critical_count", 0))

        if alert_only and flag_total == 0 and crit_total == 0:
            status = "skipped_no_anomalies"
            dispatch_result = {"dispatched": False, "reason": "No CFO anomalies detected."}
        else:
            if not targets:
                raise ValueError("No Telegram recipients configured for this scheduled digest.")
            dispatch_result = dispatch_fn(sess_data, targets=targets)
            status = "dispatched"

        if sched:
            next_ts = compute_next_run(sched["cadence"], from_ts=ts, hour_utc=sched.get("hour_utc", 4))
            owner_hash = blind_index_email(owner_email)
            conn = self._get_conn()
            try:
                conn.execute("BEGIN IMMEDIATE;")
                conn.execute(
                    """
                    UPDATE report_schedules
                    SET last_run_at = ?, last_status = ?, next_run_at = ?, updated_at = ?
                    WHERE report_id = ? AND owner_hash = ?;
                    """,
                    (ts, status, next_ts, ts, report_id, owner_hash),
                )
                conn.execute("COMMIT;")
            finally:
                conn.close()

        return {"report_id": report_id, "status": status, "dispatch": dispatch_result}

    def run_due_schedules(
        self,
        runner_fn: Callable[[str, str], Dict[str, Any]],
        dispatch_fn: Callable[..., Dict[str, Any]],
        now: Optional[float] = None,
        lock_name: str = "due_schedules_tick",
    ) -> Dict[str, Any]:
        """Claim multi-worker lease and run every enabled due schedule once."""
        ts = float(now) if now is not None else time.time()
        owner_id = str(uuid.uuid4())
        if not self.acquire_lease(lock_name, owner_id, ttl_seconds=55.0, now=ts):
            return {"acquired": False, "executed": 0, "skipped": 0, "errors": []}

        executed = 0
        skipped = 0
        errors: List[Dict[str, str]] = []
        try:
            conn = self._get_conn()
            try:
                due_rows = conn.execute(
                    """
                    SELECT report_id, owner_hash, encrypted_config, cadence
                    FROM report_schedules
                    WHERE enabled = 1 AND next_run_at <= ?
                    ORDER BY next_run_at ASC;
                    """,
                    (ts,),
                ).fetchall()
            finally:
                conn.close()

            for report_id, owner_hash, enc_cfg, cadence in due_rows:
                try:
                    cfg = decrypt_json(enc_cfg, aad=f"sched:{report_id}:{owner_hash}".encode("utf-8")) or {}
                    owner_email = cfg.get("owner_email")
                    if not owner_email:
                        raise ValueError("Corrupted schedule owner metadata.")
                    res = self.run_single(owner_email, report_id, runner_fn, dispatch_fn, now=ts)
                    if res["status"] == "dispatched":
                        executed += 1
                    else:
                        skipped += 1
                except Exception as exc:
                    errors.append({"report_id": report_id, "error": str(exc)})
                    # Push next_run_at by 1 hour so broken links don't spin tightly every tick
                    conn_err = self._get_conn()
                    try:
                        conn_err.execute("BEGIN IMMEDIATE;")
                        conn_err.execute(
                            "UPDATE report_schedules SET last_run_at = ?, last_status = ?, next_run_at = ? WHERE report_id = ?;",
                            (ts, f"error: {str(exc)[:180]}", ts + 3600, report_id),
                        )
                        conn_err.execute("COMMIT;")
                    finally:
                        conn_err.close()
        finally:
            self.release_lease(lock_name, owner_id)

        return {"acquired": True, "executed": executed, "skipped": skipped, "errors": errors}


scheduler_service = SchedulerService()


def start_background_scheduler(
    runner_fn: Callable[[str, str], Dict[str, Any]],
    dispatch_fn: Callable[..., Dict[str, Any]],
    interval_seconds: int = 60,
):
    """Launch a single daemon polling thread per process to process due schedules safely."""
    global _SCHEDULER_STARTED
    if os.environ.get("AUTOBI_DISABLE_SCHEDULER", "").lower() in ("1", "true", "yes"):
        return
    with _SCHEDULER_THREAD_LOCK:
        if _SCHEDULER_STARTED:
            return
        _SCHEDULER_STARTED = True

        def _loop():
            while True:
                time.sleep(max(10, interval_seconds))
                try:
                    scheduler_service.run_due_schedules(runner_fn, dispatch_fn)
                except Exception as exc:
                    print(f"[Scheduler] Background tick error: {exc}")

        t = threading.Thread(target=_loop, name="autobi-digest-scheduler", daemon=True)
        t.start()
