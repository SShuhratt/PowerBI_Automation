"""
session_store.py - High-Performance, Multi-Worker Resilient Session Store
Guarantees session persistence across multiple Gunicorn workers and restarts.
Backends:
  1. Redis (if REDIS_URL or COOLIFY Redis is available)
  2. SQLite WAL (Zero-dependency embedded database with atomic concurrency for workers)
"""

import os
import json
import sqlite3
import time
from typing import Optional, Dict, Any


class SessionStore:
    def __init__(self, db_path: str = None, redis_url: str = None, default_ttl_seconds: int = 7200):
        self.default_ttl = default_ttl_seconds
        self.redis_client = None
        self.backend = "sqlite"

        # Check for Redis configuration
        redis_url = redis_url or os.environ.get("REDIS_URL") or os.environ.get("COOLIFY_REDIS_URL")
        if redis_url:
            try:
                import redis
                self.redis_client = redis.from_url(redis_url, decode_responses=True)
                self.redis_client.ping()
                self.backend = "redis"
                print(f"[SessionStore] Connected to Redis backend at {redis_url}")
            except Exception as e:
                print(f"[SessionStore] Redis connection failed ({e}). Falling back to SQLite WAL.")
                self.redis_client = None

        if self.backend == "sqlite":
            if not db_path:
                base_dir = os.path.dirname(os.path.abspath(__file__))
                db_dir = os.path.join(base_dir, ".sessions")
                os.makedirs(db_dir, exist_ok=True)
                db_path = os.path.join(db_dir, "sessions.db")
            self.db_path = db_path
            self._init_sqlite()
            print(f"[SessionStore] Using SQLite WAL multi-worker backend at {self.db_path}")

    def _get_sqlite_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
        return conn

    def _init_sqlite(self):
        with self._get_sqlite_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    expires_at REAL NOT NULL
                );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_expires_at ON sessions(expires_at);")

    def set(self, session_id: str, data: Dict[str, Any], ttl_seconds: Optional[int] = None) -> bool:
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl
        now = time.time()
        expires_at = now + ttl

        if self.backend == "redis" and self.redis_client:
            try:
                serialized = json.dumps(data, ensure_ascii=False, default=str)
                self.redis_client.set(f"session:{session_id}", serialized, ex=ttl)
                return True
            except Exception as e:
                print(f"[SessionStore] Redis set error: {e}")

        # Fallback to SQLite
        try:
            serialized = json.dumps(data, ensure_ascii=False, default=str)
            with self._get_sqlite_conn() as conn:
                conn.execute("""
                    INSERT INTO sessions (session_id, payload, created_at, expires_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(session_id) DO UPDATE SET
                        payload=excluded.payload,
                        created_at=excluded.created_at,
                        expires_at=excluded.expires_at;
                """, (session_id, serialized, now, expires_at))
            return True
        except Exception as e:
            print(f"[SessionStore] SQLite set error: {e}")
            return False

    def get(self, session_id: str) -> Optional[Dict[str, Any]]:
        now = time.time()
        if self.backend == "redis" and self.redis_client:
            try:
                raw = self.redis_client.get(f"session:{session_id}")
                if raw:
                    return json.loads(raw)
                return None
            except Exception as e:
                print(f"[SessionStore] Redis get error: {e}")

        try:
            with self._get_sqlite_conn() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT payload, expires_at FROM sessions WHERE session_id = ?;
                """, (session_id,))
                row = cursor.fetchone()
                if row:
                    payload_str, expires_at = row
                    if expires_at > now:
                        return json.loads(payload_str)
                    else:
                        # Expired
                        conn.execute("DELETE FROM sessions WHERE session_id = ?;", (session_id,))
                return None
        except Exception as e:
            print(f"[SessionStore] SQLite get error: {e}")
            return None

    def delete(self, session_id: str) -> bool:
        if self.backend == "redis" and self.redis_client:
            try:
                self.redis_client.delete(f"session:{session_id}")
            except Exception:
                pass
        try:
            with self._get_sqlite_conn() as conn:
                conn.execute("DELETE FROM sessions WHERE session_id = ?;", (session_id,))
            return True
        except Exception:
            return False

    def prune(self):
        """Remove expired sessions to keep disk storage minimal."""
        now = time.time()
        if self.backend == "sqlite":
            try:
                with self._get_sqlite_conn() as conn:
                    conn.execute("DELETE FROM sessions WHERE expires_at <= ?;", (now,))
            except Exception as e:
                print(f"[SessionStore] Prune error: {e}")


# Singleton instance for import across application
sessions = SessionStore()

