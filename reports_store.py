"""
reports_store.py - Encrypted Persistent Report Gallery & Period-over-Period Snapshot Store
Allows opt-in saving of AutoBI analyses into SQLite WAL with AES-256-GCM encryption
at rest, strict owner isolation via HMAC-SHA256 blind indexing, and automated MoM/period
KPI delta computation across refreshes.
"""

import os
import re
import uuid
import time
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional

from security_vault import encrypt_json, decrypt_json, blind_index_email

_NUM_EXTRACT_RE = re.compile(r"[-+]?\d[\d,]*\.?\d*")


def parse_kpi_scalar(value_str: Any) -> Optional[float]:
    """Extract numeric scalar from formatted KPI strings such as '$22,437.50' or '34.8%'."""
    if value_str is None:
        return None
    if isinstance(value_str, (int, float)):
        return float(value_str)
    match = _NUM_EXTRACT_RE.search(str(value_str).replace(" ", ""))
    if not match:
        return None
    try:
        return float(match.group(0).replace(",", ""))
    except ValueError:
        return None


def compute_kpi_deltas(current_kpis: List[Dict[str, Any]], previous_kpis: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """Return a copy of current_kpis enriched with period-over-period delta metadata."""
    if not current_kpis:
        return []
    prev_map: Dict[str, Dict[str, Any]] = {}
    for pk in previous_kpis or []:
        lbl = str(pk.get("label") or "").strip().lower()
        if lbl:
            prev_map[lbl] = pk

    enriched: List[Dict[str, Any]] = []
    for k in current_kpis:
        item = dict(k)
        lbl = str(item.get("label") or "").strip().lower()
        prev = prev_map.get(lbl)
        if prev:
            cur_val = parse_kpi_scalar(item.get("value"))
            prev_val = parse_kpi_scalar(prev.get("value"))
            if cur_val is not None and prev_val is not None:
                is_pct = "%" in str(item.get("value", ""))
                if is_pct:
                    diff = cur_val - prev_val
                    if abs(diff) < 0.05:
                        item["delta_pct"] = 0.0
                        item["delta_text"] = "0.0 pts vs prev"
                        item["delta_dir"] = "flat"
                    else:
                        sign = "+" if diff > 0 else ""
                        item["delta_pct"] = round(diff, 1)
                        item["delta_text"] = f"{sign}{diff:.1f} pts vs prev"
                        item["delta_dir"] = "up" if diff > 0 else "down"
                elif prev_val != 0:
                    pct = ((cur_val - prev_val) / abs(prev_val)) * 100.0
                    if abs(pct) < 0.05:
                        item["delta_pct"] = 0.0
                        item["delta_text"] = "0.0% vs prev"
                        item["delta_dir"] = "flat"
                    else:
                        sign = "+" if pct > 0 else ""
                        item["delta_pct"] = round(pct, 1)
                        item["delta_text"] = f"{sign}{pct:.1f}% vs prev"
                        item["delta_dir"] = "up" if pct > 0 else "down"
        enriched.append(item)
    return enriched


class ReportsStore:
    """Multi-worker SQLite WAL encrypted repository for Saved Reports & Snapshot History."""

    MAX_SNAPSHOTS_PER_REPORT = 12

    def __init__(self, db_path: Optional[str] = None):
        if not db_path:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            db_dir = os.path.join(base_dir, ".sessions")
            os.makedirs(db_dir, exist_ok=True)
            db_path = os.path.join(db_dir, "reports.db")
        self.db_path = db_path
        self._init_sqlite()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
        return conn

    def _init_sqlite(self):
        with self._get_conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS saved_reports (
                    report_id TEXT PRIMARY KEY,
                    owner_hash TEXT NOT NULL,
                    encrypted_meta TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                );
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_reports_owner ON saved_reports(owner_hash, updated_at);")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS report_snapshots (
                    snapshot_id TEXT PRIMARY KEY,
                    report_id TEXT NOT NULL,
                    owner_hash TEXT NOT NULL,
                    encrypted_payload TEXT NOT NULL,
                    period_label TEXT NOT NULL,
                    created_at REAL NOT NULL
                );
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_snaps_report ON report_snapshots(report_id, created_at);")

    def create_report(
        self,
        owner_email: str,
        title: str,
        snapshot_data: Dict[str, Any],
        domain_info: Dict[str, Any],
        source_url: Optional[str] = None,
        is_live_url: bool = False,
        db_config: Optional[Dict[str, Any]] = None,
        period_label: Optional[str] = None,
    ) -> Dict[str, Any]:
        owner_hash = blind_index_email(owner_email)
        report_id = str(uuid.uuid4())
        snapshot_id = str(uuid.uuid4())
        now = time.time()
        clean_title = (title or snapshot_data.get("filename") or "Saved AutoBI Report").strip()[:120]
        p_label = (period_label or datetime.now().strftime("%Y-%m-%d %H:%M")).strip()[:64]

        meta = {
            "report_id": report_id,
            "title": clean_title,
            "domain": domain_info or {},
            "source_url": source_url if is_live_url else None,
            "is_live_url": bool(is_live_url),
            "db_config": db_config,
            "latest_snapshot_id": snapshot_id,
            "latest_period": p_label,
            "latest_kpis": (snapshot_data.get("kpis") or [])[:6],
            "snapshot_count": 1,
        }

        enc_meta = encrypt_json(meta, aad=f"report:{report_id}:{owner_hash}".encode("utf-8"))
        enc_snap = encrypt_json(snapshot_data, aad=f"snap:{snapshot_id}:{owner_hash}".encode("utf-8"))

        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT INTO saved_reports (report_id, owner_hash, encrypted_meta, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?);
                """,
                (report_id, owner_hash, enc_meta, now, now),
            )
            conn.execute(
                """
                INSERT INTO report_snapshots (snapshot_id, report_id, owner_hash, encrypted_payload, period_label, created_at)
                VALUES (?, ?, ?, ?, ?, ?);
                """,
                (snapshot_id, report_id, owner_hash, enc_snap, p_label, now),
            )

        return {
            "report_id": report_id,
            "snapshot_id": snapshot_id,
            "title": clean_title,
            "period_label": p_label,
            "created_at": now,
            "updated_at": now,
            "snapshot_count": 1,
            "domain": meta["domain"],
            "is_live_url": meta["is_live_url"],
            "source_url": meta["source_url"],
        }

    def list_reports(self, owner_email: str) -> List[Dict[str, Any]]:
        owner_hash = blind_index_email(owner_email)
        with self._get_conn() as conn:
            rows = conn.execute(
                """
                SELECT report_id, encrypted_meta, created_at, updated_at
                FROM saved_reports
                WHERE owner_hash = ?
                ORDER BY updated_at DESC;
                """,
                (owner_hash,),
            ).fetchall()

        results: List[Dict[str, Any]] = []
        for report_id, enc_meta, created_at, updated_at in rows:
            try:
                meta = decrypt_json(enc_meta, aad=f"report:{report_id}:{owner_hash}".encode("utf-8")) or {}
            except Exception:
                continue
            results.append({
                "report_id": report_id,
                "title": meta.get("title", "Saved Report"),
                "domain": meta.get("domain", {}),
                "is_live_url": bool(meta.get("is_live_url")),
                "has_db_config": bool(meta.get("db_config")),
                "snapshot_count": int(meta.get("snapshot_count", 1)),
                "latest_period": meta.get("latest_period", ""),
                "latest_kpis": (meta.get("latest_kpis") or [])[:4],
                "created_at": created_at,
                "updated_at": updated_at,
            })
        return results

    def get_report(self, owner_email: str, report_id: str) -> Optional[Dict[str, Any]]:
        owner_hash = blind_index_email(owner_email)
        with self._get_conn() as conn:
            row = conn.execute(
                """
                SELECT encrypted_meta, created_at, updated_at
                FROM saved_reports
                WHERE report_id = ? AND owner_hash = ?;
                """,
                (report_id, owner_hash),
            ).fetchone()
            if not row:
                return None

            snaps_rows = conn.execute(
                """
                SELECT snapshot_id, encrypted_payload, period_label, created_at
                FROM report_snapshots
                WHERE report_id = ? AND owner_hash = ?
                ORDER BY created_at DESC;
                """,
                (report_id, owner_hash),
            ).fetchall()

        try:
            meta = decrypt_json(row[0], aad=f"report:{report_id}:{owner_hash}".encode("utf-8")) or {}
        except Exception:
            return None

        history = []
        latest_payload = None
        for idx, (snap_id, enc_payload, p_label, s_created) in enumerate(snaps_rows):
            try:
                payload = decrypt_json(enc_payload, aad=f"snap:{snap_id}:{owner_hash}".encode("utf-8"))
            except Exception:
                continue
            if idx == 0:
                latest_payload = payload
            history.append({
                "snapshot_id": snap_id,
                "period_label": p_label,
                "created_at": s_created,
                "kpis": (payload or {}).get("kpis", []),
            })

        if latest_payload is None:
            return None

        if len(history) >= 2:
            latest_payload["kpis"] = compute_kpi_deltas(latest_payload.get("kpis") or [], history[1].get("kpis"))

        return {
            "report_id": report_id,
            "meta": meta,
            "created_at": row[1],
            "updated_at": row[2],
            "latest_payload": latest_payload,
            "history": [
                {"snapshot_id": h["snapshot_id"], "period_label": h["period_label"], "created_at": h["created_at"]}
                for h in history
            ],
        }

    def add_snapshot(
        self,
        owner_email: str,
        report_id: str,
        new_payload: Dict[str, Any],
        period_label: Optional[str] = None,
        domain_info: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        owner_hash = blind_index_email(owner_email)
        existing = self.get_report(owner_email, report_id)
        if not existing:
            return None

        prev_kpis = (existing.get("latest_payload") or {}).get("kpis") or []
        enriched_kpis = compute_kpi_deltas(new_payload.get("kpis") or [], prev_kpis)
        new_payload = dict(new_payload)
        new_payload["kpis"] = enriched_kpis

        snapshot_id = str(uuid.uuid4())
        now = time.time()
        p_label = (period_label or datetime.now().strftime("%Y-%m-%d %H:%M")).strip()[:64]
        enc_snap = encrypt_json(new_payload, aad=f"snap:{snapshot_id}:{owner_hash}".encode("utf-8"))

        meta = dict(existing.get("meta") or {})
        if domain_info:
            meta["domain"] = domain_info
        meta["latest_snapshot_id"] = snapshot_id
        meta["latest_period"] = p_label
        meta["latest_kpis"] = enriched_kpis[:6]

        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT INTO report_snapshots (snapshot_id, report_id, owner_hash, encrypted_payload, period_label, created_at)
                VALUES (?, ?, ?, ?, ?, ?);
                """,
                (snapshot_id, report_id, owner_hash, enc_snap, p_label, now),
            )
            # Prune old snapshots beyond MAX_SNAPSHOTS_PER_REPORT
            rows = conn.execute(
                """
                SELECT snapshot_id FROM report_snapshots
                WHERE report_id = ? AND owner_hash = ?
                ORDER BY created_at DESC;
                """,
                (report_id, owner_hash),
            ).fetchall()
            if len(rows) > self.MAX_SNAPSHOTS_PER_REPORT:
                for (old_id,) in rows[self.MAX_SNAPSHOTS_PER_REPORT:]:
                    conn.execute("DELETE FROM report_snapshots WHERE snapshot_id = ?;", (old_id,))
            meta["snapshot_count"] = min(len(rows), self.MAX_SNAPSHOTS_PER_REPORT)
            enc_meta = encrypt_json(meta, aad=f"report:{report_id}:{owner_hash}".encode("utf-8"))
            conn.execute(
                """
                UPDATE saved_reports
                SET encrypted_meta = ?, updated_at = ?
                WHERE report_id = ? AND owner_hash = ?;
                """,
                (enc_meta, now, report_id, owner_hash),
            )

        return {
            "report_id": report_id,
            "snapshot_id": snapshot_id,
            "period_label": p_label,
            "kpis": enriched_kpis,
            "snapshot_count": meta["snapshot_count"],
            "updated_at": now,
        }

    def delete_report(self, owner_email: str, report_id: str) -> bool:
        owner_hash = blind_index_email(owner_email)
        with self._get_conn() as conn:
            cur_meta = conn.execute(
                "SELECT 1 FROM saved_reports WHERE report_id = ? AND owner_hash = ?;",
                (report_id, owner_hash),
            ).fetchone()
            if not cur_meta:
                return False
            conn.execute("DELETE FROM report_snapshots WHERE report_id = ? AND owner_hash = ?;", (report_id, owner_hash))
            conn.execute("DELETE FROM saved_reports WHERE report_id = ? AND owner_hash = ?;", (report_id, owner_hash))
        return True


reports_store = ReportsStore()
