"""
security_vault.py - Cryptographic Storage, AES-256-GCM Encryption & Salted User Auth Vault
Protects both persisted workspace sessions and registered user records at rest:
- AES-256-GCM authenticated encryption for database records and session payloads
- HMAC-SHA256 blind indexing for zero-plaintext email lookups
- Salted scrypt password hashing for user authentication
"""

import os
import json
import time
import hmac
import base64
import hashlib
import sqlite3
from typing import Any, Dict, Optional, Tuple
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def _load_or_create_master_key() -> bytes:
    """Resolve 32-byte master key from env or persistent local keyfile."""
    env_key = os.environ.get("DB_ENCRYPTION_KEY") or os.environ.get("SECRET_KEY")
    if env_key:
        return hashlib.sha256(f"autobi-master-v1:{env_key}".encode("utf-8")).digest()

    base_dir = os.path.dirname(os.path.abspath(__file__))
    sessions_dir = os.path.join(base_dir, ".sessions")
    os.makedirs(sessions_dir, exist_ok=True)
    key_file = os.path.join(sessions_dir, ".vault.key")

    if os.path.exists(key_file):
        try:
            with open(key_file, "rb") as f:
                raw = f.read().strip()
            if len(raw) >= 32:
                return hashlib.sha256(raw).digest()
        except Exception:
            pass

    generated = os.urandom(32)
    try:
        with open(key_file, "wb") as f:
            f.write(generated)
        try:
            os.chmod(key_file, 0o600)
        except Exception:
            pass
    except Exception:
        pass
    return hashlib.sha256(generated).digest()


_MASTER_KEY = _load_or_create_master_key()
_ENC_PREFIX = "enc:v1:"


def _derive_subkey(purpose: bytes) -> bytes:
    return hmac.new(_MASTER_KEY, purpose, hashlib.sha256).digest()


_DATA_KEY = _derive_subkey(b"autobi-aes256gcm-data-v1")
_INDEX_KEY = _derive_subkey(b"autobi-email-blind-index-v1")
_AESGCM = AESGCM(_DATA_KEY)


def encrypt_json(data: Any, aad: Optional[bytes] = None) -> str:
    """Serialize JSON and encrypt with AES-256-GCM using a fresh 96-bit nonce."""
    serialized = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
    nonce = os.urandom(12)
    ciphertext = _AESGCM.encrypt(nonce, serialized, aad)
    token = base64.urlsafe_b64encode(nonce + ciphertext).decode("ascii")
    return _ENC_PREFIX + token


def decrypt_json(payload: str, aad: Optional[bytes] = None) -> Any:
    """Decrypt AES-256-GCM payload (with fallback for legacy plain JSON during rollout)."""
    if not payload or not isinstance(payload, str):
        return None
    if payload.startswith(_ENC_PREFIX):
        raw_b64 = payload[len(_ENC_PREFIX):]
        raw = base64.urlsafe_b64decode(raw_b64.encode("ascii"))
        nonce, ciphertext = raw[:12], raw[12:]
        plaintext = _AESGCM.decrypt(nonce, ciphertext, aad)
        return json.loads(plaintext.decode("utf-8"))
    # Legacy fallback (read-only migration support)
    return json.loads(payload)


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def blind_index_email(email: str) -> str:
    """Deterministic HMAC-SHA256 blind index for querying encrypted user records."""
    norm = normalize_email(email).encode("utf-8")
    return hmac.new(_INDEX_KEY, norm, hashlib.sha256).hexdigest()


def hash_password(password: str) -> str:
    """Hash password with salted scrypt (OWASP-recommended memory-hard KDF)."""
    salt = os.urandom(16)
    derived = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=16384,
        r=8,
        p=1,
        dklen=32,
    )
    return f"scrypt${salt.hex()}${derived.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Constant-time verification against stored salted scrypt hash."""
    if not password or not stored_hash or not stored_hash.startswith("scrypt$"):
        return False
    try:
        _, salt_hex, expected_hex = stored_hash.split("$", 2)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(expected_hex)
        derived = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=16384,
            r=8,
            p=1,
            dklen=len(expected),
        )
        return hmac.compare_digest(derived, expected)
    except Exception:
        return False


class EncryptedUserStore:
    """Stores user accounts with salted scrypt passwords and AES-256-GCM encrypted profiles."""

    def __init__(self, db_path: Optional[str] = None):
        if not db_path:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            db_dir = os.path.join(base_dir, ".sessions")
            os.makedirs(db_dir, exist_ok=True)
            db_path = os.path.join(db_dir, "sessions.db")
        self.db_path = db_path
        self._init_table()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
        return conn

    def _init_table(self):
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    email_hash TEXT PRIMARY KEY,
                    encrypted_profile TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                );
            """)

    def user_exists(self, email: str) -> bool:
        e_hash = blind_index_email(email)
        with self._conn() as conn:
            row = conn.execute(
                "SELECT 1 FROM users WHERE email_hash = ?;",
                (e_hash,),
            ).fetchone()
            return row is not None

    def create_user(
        self,
        email: str,
        password: str,
        full_name: str = "",
        role: str = "analyst",
    ) -> Tuple[bool, Any]:
        norm_email = normalize_email(email)
        e_hash = blind_index_email(norm_email)
        now = time.time()
        profile = {
            "email": norm_email,
            "full_name": (full_name or "").strip(),
            "role": role,
            "created_at": now,
        }
        enc_profile = encrypt_json(profile, aad=e_hash.encode("ascii"))
        pw_hash = hash_password(password)

        try:
            with self._conn() as conn:
                existing = conn.execute(
                    "SELECT 1 FROM users WHERE email_hash = ?;",
                    (e_hash,),
                ).fetchone()
                if existing:
                    return False, "user_exists"
                conn.execute(
                    """
                    INSERT INTO users (email_hash, encrypted_profile, password_hash, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?);
                    """,
                    (e_hash, enc_profile, pw_hash, now, now),
                )
            return True, profile
        except sqlite3.IntegrityError:
            return False, "user_exists"

    def authenticate_user(self, email: str, password: str) -> Tuple[str, Optional[Dict[str, Any]]]:
        """Returns ('ok', profile), ('invalid_password', None), or ('not_found', None)."""
        norm_email = normalize_email(email)
        e_hash = blind_index_email(norm_email)
        with self._conn() as conn:
            row = conn.execute(
                "SELECT encrypted_profile, password_hash FROM users WHERE email_hash = ?;",
                (e_hash,),
            ).fetchone()
            if not row:
                return "not_found", None
            enc_profile, pw_hash = row
            if not verify_password(password, pw_hash):
                return "invalid_password", None
            try:
                profile = decrypt_json(enc_profile, aad=e_hash.encode("ascii"))
            except Exception:
                profile = {"email": norm_email}
            conn.execute(
                "UPDATE users SET updated_at = ? WHERE email_hash = ?;",
                (time.time(), e_hash),
            )
            return "ok", profile

    def ensure_bootstrap_user(
        self,
        email: str,
        password: str,
        full_name: str = "Workspace Owner",
        role: str = "admin",
    ) -> None:
        """Idempotently provision an env-configured account if not yet registered."""
        if not email or not password:
            return
        norm_email = normalize_email(email)
        e_hash = blind_index_email(norm_email)
        with self._conn() as conn:
            row = conn.execute(
                "SELECT 1 FROM users WHERE email_hash = ?;",
                (e_hash,),
            ).fetchone()
            if row:
                return
        self.create_user(norm_email, password, full_name=full_name, role=role)


users_vault = EncryptedUserStore()
