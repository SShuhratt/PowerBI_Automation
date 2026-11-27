"""
sql_connector.py - Read-Only PostgreSQL & MySQL Ingestion Connector
Provides SSRF-hardened URI validation, strict SELECT-only SQL static inspection,
credential masking, statement timeouts, and read-only transaction execution.
"""

import re
import ipaddress
import socket
from urllib.parse import urlparse
from typing import Any, Callable, Dict, Optional, Tuple
import pandas as pd

MAX_SQL_ROWS = 50000
SQL_TIMEOUT_SECONDS = 10

_BLOCKED_SQL_KEYWORDS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE|REPLACE|GRANT|REVOKE|MERGE|UPSERT|CALL|EXEC|EXECUTE|COPY|OUTFILE|DUMPFILE|LOAD_FILE|INTO\s+OUTFILE|ATTACH|DETACH|PRAGMA|VACUUM|SET)\b",
    re.IGNORECASE,
)

_BLOCKED_HOSTNAMES = {
    "localhost",
    "localhost.localdomain",
    "metadata.google.internal",
    "metadata",
    "169.254.169.254",
    "100.100.100.200",
    "0.0.0.0",
    "::1",
    "127.0.0.1",
}


def strip_sql_comments_and_strings(sql: str) -> str:
    """Remove SQL comments and single/double-quoted string contents for safe keyword scanning."""
    no_block = re.sub(r"/\*[\s\S]*?\*/", " ", sql or "")
    no_line = re.sub(r"--[^\r\n]*", " ", no_block)
    no_strings = re.sub(r"'(?:''|[^'])*'", "''", no_line)
    return no_strings.strip()


def validate_select_only_sql(sql: str) -> str:
    """Validate that SQL contains a single strictly read-only SELECT/CTE query."""
    raw = (sql or "").strip()
    if not raw:
        raise ValueError("Please enter a SELECT SQL query.")

    stripped = strip_sql_comments_and_strings(raw)
    if not stripped:
        raise ValueError("SQL query is empty after removing comments.")

    # Allow a single trailing semicolon, reject multi-statement chains
    without_trailing_semi = stripped[:-1].strip() if stripped.endswith(";") else stripped
    if ";" in without_trailing_semi:
        raise ValueError("Multiple SQL statements are not permitted. Provide one SELECT query.")

    first_token = without_trailing_semi.split(None, 1)[0].upper()
    if first_token not in ("SELECT", "WITH"):
        raise ValueError("Only read-only SELECT (or WITH ... SELECT) queries are permitted.")

    match = _BLOCKED_SQL_KEYWORDS.search(without_trailing_semi)
    if match:
        raise ValueError(f"Blocked SQL keyword '{match.group(1).upper()}'. Only read-only SELECT queries are allowed.")

    return raw[:-1].strip() if raw.endswith(";") else raw


def _is_blocked_ip(host: str) -> bool:
    clean = host.strip("[]").lower()
    if clean in _BLOCKED_HOSTNAMES:
        return True
    try:
        ip = ipaddress.ip_address(clean)
        return ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_unspecified
    except ValueError:
        pass
    try:
        resolved = socket.getaddrinfo(clean, None)
        for item in resolved:
            addr = item[4][0]
            ip = ipaddress.ip_address(addr)
            if ip.is_loopback or ip.is_link_local or ip.is_unspecified:
                return True
    except Exception:
        # Leave unresolvable hosts to fail normally during connection (except literal metadata names above)
        pass
    return False


def validate_db_uri_safe(uri: str, allow_sqlite_for_test: bool = False) -> Tuple[str, Dict[str, Any]]:
    """Validate scheme, database path, and block loopback/metadata SSRF hosts."""
    raw = (uri or "").strip()
    if not raw:
        raise ValueError("Database connection URI is required.")

    parsed = urlparse(raw)
    scheme = (parsed.scheme or "").lower().split("+")[0]

    if scheme == "sqlite" and allow_sqlite_for_test:
        return scheme, {"host": "sqlite", "port": None, "database": parsed.path or ":memory:"}

    if scheme not in ("postgresql", "postgres", "mysql"):
        raise ValueError("Unsupported database scheme. Use postgresql:// or mysql:// connection URI.")

    host = (parsed.hostname or "").strip()
    if not host:
        raise ValueError("Database URI must include a hostname.")
    if _is_blocked_ip(host):
        raise ValueError(f"Blocked connection host '{host}' for security (loopback and cloud metadata IPs are restricted).")

    dbname = (parsed.path or "").lstrip("/").strip()
    if not dbname:
        raise ValueError("Database URI must include a target database name (e.g., /analytics).")

    default_port = 5432 if scheme in ("postgresql", "postgres") else 3306
    return ("postgresql" if scheme == "postgres" else scheme), {
        "host": host,
        "port": parsed.port or default_port,
        "database": dbname,
        "user": parsed.username or "",
        "password": parsed.password or "",
    }


def mask_db_uri(uri: str) -> str:
    """Return credential-free database descriptor for safe logging and UI badges."""
    try:
        parsed = urlparse((uri or "").strip())
        scheme = (parsed.scheme or "sql").split("+")[0]
        host = parsed.hostname or "db"
        port = f":{parsed.port}" if parsed.port else ""
        dbname = (parsed.path or "").lstrip("/") or "db"
        return f"{scheme}://{host}{port}/{dbname}"
    except Exception:
        return "sql://database"


def fetch_readonly_sql_df(
    uri: str,
    sql: str,
    max_rows: int = MAX_SQL_ROWS,
    timeout_sec: int = SQL_TIMEOUT_SECONDS,
    connection_factory: Optional[Callable[[str, Dict[str, Any]], Any]] = None,
    allow_sqlite_for_test: bool = False,
) -> Tuple[pd.DataFrame, str]:
    """Execute a validated read-only SELECT query and return (DataFrame, masked_source_label)."""
    scheme, info = validate_db_uri_safe(uri, allow_sqlite_for_test=allow_sqlite_for_test)
    clean_sql = validate_select_only_sql(sql)
    capped_rows = max(1, min(int(max_rows), MAX_SQL_ROWS))
    masked_label = mask_db_uri(uri)

    conn = None
    try:
        if connection_factory is not None:
            conn = connection_factory(scheme, info)
        elif scheme == "sqlite" and allow_sqlite_for_test:
            import sqlite3
            conn = sqlite3.connect(info["database"], timeout=timeout_sec)
        elif scheme == "postgresql":
            try:
                import psycopg2
            except ImportError as ie:
                raise RuntimeError("PostgreSQL driver (psycopg2-binary) is not installed on this runtime.") from ie
            conn = psycopg2.connect(
                host=info["host"],
                port=info["port"],
                dbname=info["database"],
                user=info["user"],
                password=info["password"],
                connect_timeout=min(timeout_sec, 10),
                options=f"-c statement_timeout={int(timeout_sec * 1000)} -c default_transaction_read_only=on",
            )
            try:
                conn.set_session(readonly=True, autocommit=True)
            except Exception:
                pass
        elif scheme == "mysql":
            try:
                import pymysql
            except ImportError as ie:
                raise RuntimeError("MySQL driver (PyMySQL) is not installed on this runtime.") from ie
            conn = pymysql.connect(
                host=info["host"],
                port=info["port"],
                database=info["database"],
                user=info["user"],
                password=info["password"],
                connect_timeout=min(timeout_sec, 10),
                read_timeout=timeout_sec,
            )

        cur = conn.cursor()
        if scheme == "mysql" and connection_factory is None:
            try:
                cur.execute("SET SESSION TRANSACTION READ ONLY;")
            except Exception:
                pass

        cur.execute(clean_sql)
        rows = cur.fetchmany(capped_rows)
        cols = [desc[0] for desc in (cur.description or [])]
        cur.close()
        df = pd.DataFrame(rows, columns=cols)
        return df, masked_label
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
