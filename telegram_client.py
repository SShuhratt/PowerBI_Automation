"""
telegram_client.py - 1-Click Executive Telegram Digest & Report Dispatcher
Dispatches high-priority executive KPI digests and interactive HTML dashboard
attachments directly to Telegram channels, groups, or director chats via Telegram Bot API.
"""

import os
import re
import json
import sqlite3
import time
import urllib.request
import urllib.error
from typing import Dict, Any, Optional, Tuple, List, Union


def _get_db_path(db_path: Optional[str] = None) -> str:
    if db_path:
        return db_path
    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_dir = os.path.join(base_dir, ".sessions")
    os.makedirs(db_dir, exist_ok=True)
    return os.path.join(db_dir, "sessions.db")


def init_telegram_db(db_path: Optional[str] = None):
    p = _get_db_path(db_path)
    conn = sqlite3.connect(p, timeout=10.0)
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
        with conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS telegram_subscribers (
                    chat_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    chat_type TEXT,
                    last_start_param TEXT,
                    updated_at REAL NOT NULL
                );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tg_username ON telegram_subscribers(username);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tg_param ON telegram_subscribers(last_start_param);")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS telegram_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
            """)
    finally:
        conn.close()


def upsert_subscriber(sub: Dict[str, Any], db_path: Optional[str] = None):
    init_telegram_db(db_path)
    p = _get_db_path(db_path)
    conn = sqlite3.connect(p, timeout=10.0)
    try:
        uname = (sub.get("username") or "").lstrip("@").lower() or None
        with conn:
            conn.execute("""
                INSERT INTO telegram_subscribers (chat_id, username, first_name, chat_type, last_start_param, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(chat_id) DO UPDATE SET
                    username=excluded.username,
                    first_name=excluded.first_name,
                    chat_type=excluded.chat_type,
                    last_start_param=COALESCE(excluded.last_start_param, telegram_subscribers.last_start_param),
                    updated_at=excluded.updated_at;
            """, (
                sub["chat_id"],
                uname,
                sub.get("first_name", ""),
                sub.get("chat_type", "private"),
                sub.get("last_start_param"),
                time.time()
            ))
    finally:
        conn.close()


def get_subscriber_by_param(param: str, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    if not param:
        return None
    init_telegram_db(db_path)
    p = _get_db_path(db_path)
    conn = sqlite3.connect(p, timeout=10.0)
    try:
        conn.row_factory = sqlite3.Row
        cur = conn.execute(
            "SELECT * FROM telegram_subscribers WHERE last_start_param = ? ORDER BY updated_at DESC LIMIT 1",
            (param.strip(),)
        )
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_subscriber_by_username(username: str, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    if not username:
        return None
    uname = username.lstrip("@").lower().strip()
    init_telegram_db(db_path)
    p = _get_db_path(db_path)
    conn = sqlite3.connect(p, timeout=10.0)
    try:
        conn.row_factory = sqlite3.Row
        cur = conn.execute(
            "SELECT * FROM telegram_subscribers WHERE username = ? LIMIT 1",
            (uname,)
        )
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_recent_subscribers(limit: int = 5, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    init_telegram_db(db_path)
    p = _get_db_path(db_path)
    conn = sqlite3.connect(p, timeout=10.0)
    try:
        conn.row_factory = sqlite3.Row
        cur = conn.execute(
            "SELECT chat_id, username, first_name, chat_type, updated_at FROM telegram_subscribers ORDER BY updated_at DESC LIMIT ?",
            (limit,)
        )
        res = []
        for r in cur.fetchall():
            d = dict(r)
            uname = d.get("username")
            fn = d.get("first_name")
            label = f"{fn} (@{uname})" if (fn and uname) else (f"@{uname}" if uname else (fn or f"Chat {d['chat_id']}"))
            d["label"] = label
            res.append(d)
        return res
    finally:
        conn.close()


def get_last_update_offset(db_path: Optional[str] = None) -> int:
    init_telegram_db(db_path)
    p = _get_db_path(db_path)
    conn = sqlite3.connect(p, timeout=10.0)
    try:
        cur = conn.execute("SELECT value FROM telegram_meta WHERE key = 'last_update_offset'")
        row = cur.fetchone()
        return int(row[0]) if row else 0
    finally:
        conn.close()


def set_last_update_offset(offset: int, db_path: Optional[str] = None):
    init_telegram_db(db_path)
    p = _get_db_path(db_path)
    conn = sqlite3.connect(p, timeout=10.0)
    try:
        with conn:
            conn.execute("INSERT OR REPLACE INTO telegram_meta (key, value) VALUES ('last_update_offset', ?)", (str(offset),))
    finally:
        conn.close()


def poll_and_sync_updates(bot_token: Optional[str] = None, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    default_token, _ = get_default_telegram_config()
    token = bot_token or default_token
    if not token:
        return []

    last_offset = get_last_update_offset(db_path)
    url = f"https://api.telegram.org/bot{token}/getUpdates?offset={last_offset}&limit=50&timeout=2"
    req = urllib.request.Request(url, headers={"User-Agent": "AutoBI-Enterprise-Agent"})

    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return []

    updates = data.get("result", [])
    if not updates:
        return []

    new_subs = []
    max_id = last_offset
    for u in updates:
        up_id = u.get("update_id", 0)
        if up_id >= max_id:
            max_id = up_id + 1

        msg = u.get("message") or u.get("channel_post") or (u.get("my_chat_member") or {}).get("chat")
        if not msg:
            continue

        chat = msg.get("chat") if isinstance(msg, dict) and "chat" in msg else msg
        if not isinstance(chat, dict):
            continue

        cid = chat.get("id")
        if not cid:
            continue

        uname = chat.get("username", "")
        fname = chat.get("first_name") or chat.get("title") or ""
        ctype = chat.get("type", "private")
        text = msg.get("text", "") if isinstance(msg, dict) else ""

        param = None
        if text.startswith("/start"):
            parts = text.split(maxsplit=1)
            if len(parts) > 1:
                param = parts[1].strip()

        sub = {
            "chat_id": cid,
            "username": uname,
            "first_name": fname,
            "chat_type": ctype,
            "last_start_param": param
        }
        upsert_subscriber(sub, db_path=db_path)
        new_subs.append(sub)

        # Welcome greeting confirming connection
        if text.startswith("/start"):
            try:
                greeting = (
                    "👋 <b>AutoBI Studio ga xush kelibsiz!</b>\n\n"
                    "Telegram hisobingiz AutoBI Studio ga muvaffaqiyatli ulandi.\n"
                    "Veb-portaldan yuborilgan boshqaruv xulosalari va interaktiv HTML dashboardlar "
                    "ushbu chatga yetkaziladi."
                )
                send_telegram_message(greeting, str(cid), token)
            except Exception:
                pass

    if max_id > last_offset:
        set_last_update_offset(max_id, db_path)

    return new_subs


def parse_raw_target(raw: str) -> str:
    """
    Cleans up any Telegram link, username, or ID into a clean target format.
    """
    s = raw.strip().rstrip(";,")
    if not s:
        return ""
    if re.match(r'^-?\d+$', s):
        return s
    url_match = re.search(r'(?:https?:\/\/)?(?:www\.)?(?:t\.me|telegram\.me)\/([a-zA-Z0-9_+]+)', s)
    if url_match:
        slug = url_match.group(1)
        if slug not in ('joinchat', 'c', 'share', 'addstickers'):
            return f"@{slug}"
        return s
    if s.startswith("@"):
        return s
    if re.match(r'^[a-zA-Z0-9_]{4,}$', s):
        return f"@{s}"
    return s


def resolve_target_to_chat(target: str, db_path: Optional[str] = None) -> Tuple[str, str, Optional[str]]:
    """
    Resolves target (numeric ID, @channel, @username, or link) to:
    (destination, display_label, error)
    """
    clean = parse_raw_target(target)
    if not clean:
        return "", "", "Empty recipient target"

    if re.match(r'^-?\d+$', clean):
        return clean, f"Chat ID: {clean}", None

    # Check known subscribers in database
    uname = clean.lstrip("@").lower()
    sub = get_subscriber_by_username(uname, db_path=db_path)
    if sub:
        fn = sub.get("first_name") or uname
        return str(sub["chat_id"]), f"{fn} (@{uname})", None

    # If it's a channel or group with @
    if clean.startswith("@"):
        return clean, clean, None

    return clean, clean, None


def get_default_telegram_config() -> Tuple[Optional[str], Optional[str]]:
    """Retrieves default bot token and chat ID from environment variables or local env files."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        for fname in (".coolify.env", ".env"):
            p = os.path.join(os.path.dirname(__file__), fname)
            if os.path.exists(p):
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        for line in f:
                            line = line.strip()
                            if line and not line.startswith("#") and "=" in line:
                                k, v = line.split("=", 1)
                                k, v = k.strip(), v.strip().rstrip(";")
                                if k == "TELEGRAM_BOT_TOKEN" and not token:
                                    token = v
                                elif k == "TELEGRAM_CHAT_ID" and not chat_id:
                                    chat_id = v
                except Exception:
                    pass
    return token, chat_id


def get_bot_username() -> str:
    """Retrieves configured Telegram bot username."""
    username = os.environ.get("TELEGRAM_BOT_USERNAME")
    if not username:
        for fname in (".coolify.env", ".env"):
            p = os.path.join(os.path.dirname(__file__), fname)
            if os.path.exists(p):
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        for line in f:
                            line = line.strip()
                            if line and not line.startswith("#") and "=" in line:
                                k, v = line.split("=", 1)
                                if k.strip() == "TELEGRAM_BOT_USERNAME":
                                    username = v.strip().rstrip(";")
                except Exception:
                    pass
    return username or "@auto_bibot"


def escape_html(text: Any) -> str:
    """Escapes HTML special characters for safe Telegram HTML parse mode."""
    s = str(text or "")
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_executive_digest_message(session_data: Dict[str, Any]) -> str:
    """Builds a beautifully structured HTML message for mobile executive Telegram viewing."""
    filename = session_data.get("filename", "Spreadsheet.xlsx")
    audit = session_data.get("audit_log") or {}
    anomalies = audit.get("anomalies") or []
    anomaly_summary = audit.get("anomaly_summary") or {}
    fx = audit.get("fx_normalization") or {}
    pareto = audit.get("pareto_segmentation") or {}

    row_count = audit.get("cleaned_row_count")
    if isinstance(row_count, (int, float)):
        row_str = f"{int(row_count):,} rows"
    else:
        row_str = f"{row_count or 'N/A'} rows"

    lines = [
        "🚀 <b>AutoBI Executive Digest</b>",
        f"📁 <b>Source:</b> <code>{escape_html(filename)}</code>",
        f"📊 <b>Clean Records:</b> {row_str}",
        ""
    ]

    # 1. Top KPIs
    kpis = session_data.get("kpis", [])
    if kpis:
        lines.append("📈 <b>Executive Key Performance Indicators:</b>")
        for k in kpis[:5]:
            lbl = escape_html(k.get("label", ""))
            val = escape_html(k.get("value", ""))
            sub = escape_html(k.get("sub", ""))
            sub_text = f" <i>({sub})</i>" if sub else ""
            lines.append(f"• <b>{lbl}:</b> {val}{sub_text}")
        lines.append("")

    # 2. CFO Red-Flags & Audit Status
    lines.append("🚨 <b>CFO Risk & Audit Status:</b>")
    if anomalies:
        crit_c = anomaly_summary.get("critical_count", 0)
        warn_c = anomaly_summary.get("warning_count", 0)
        lines.append(f"• <b>Status:</b> ⚠️ Attention Required ({len(anomalies)} anomalies flagged)")
        if crit_c > 0:
            lines.append(f"• <b>Critical Risks:</b> {crit_c}")
        if warn_c > 0:
            lines.append(f"• <b>Warnings / Outliers:</b> {warn_c}")
        # List up to 2 specific flags
        for a in anomalies[:2]:
            lines.append(f"  - <i>{escape_html(a.get('title', ''))}</i>")
    else:
        lines.append("• <b>Status:</b> ✓ 100% Data Integrity Verified (0 anomalies)")
    lines.append("")

    # 3. Multi-Currency Normalization (if active)
    if fx.get("is_multi_currency"):
        ccys = ", ".join(fx.get("detected_currencies", []))
        lines.append(f"💱 <b>CBU.uz FX Normalization:</b> Converted ({escape_html(ccys)}) to standardized UZS and USD.")
        lines.append("")

    # 4. Pareto (80/20) Segmentation (if active)
    if pareto.get("is_segmented"):
        cnt_a = pareto.get("class_a_count", 0)
        share_a = pareto.get("class_a_revenue_share", 0)
        dim = pareto.get("dimension_col", "items")
        lines.append(f"🎯 <b>Pareto 80/20 Insight:</b> {cnt_a} Class A {escape_html(dim)} generate <b>{share_a}%</b> of total volume.")
        lines.append("")

    lines.append("📎 <i>Attached: Interactive Executive Dashboard (open in any browser).</i>")
    return "\n".join(lines)


def send_telegram_message(
    text: str,
    chat_id: str,
    bot_token: str,
    timeout: int = 10
) -> Dict[str, Any]:
    """Sends an HTML formatted message via Telegram Bot API."""
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "User-Agent": "AutoBI-Enterprise-Agent"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="ignore")
        try:
            err_json = json.loads(err_body)
            desc = err_json.get("description", e.reason)
            raise ValueError(f"Telegram API error ({e.code}): {desc}")
        except ValueError:
            raise
        except Exception:
            raise ValueError(f"Telegram API error ({e.code}): {err_body or e.reason}")


def send_telegram_document(
    document_bytes: bytes,
    filename: str,
    caption: str,
    chat_id: str,
    bot_token: str,
    timeout: int = 20
) -> Dict[str, Any]:
    """Uploads a standalone document (interactive HTML report) via multipart form-data."""
    url = f"https://api.telegram.org/bot{bot_token}/sendDocument"
    boundary = "----WebKitFormBoundaryAutoBITelegram7MA4YW"

    # Build multipart form data
    body = bytearray()

    # chat_id field
    body.extend(f"--{boundary}\r\n".encode("utf-8"))
    body.extend(f'Content-Disposition: form-data; name="chat_id"\r\n\r\n{chat_id}\r\n'.encode("utf-8"))

    # caption field
    body.extend(f"--{boundary}\r\n".encode("utf-8"))
    body.extend(f'Content-Disposition: form-data; name="caption"\r\n\r\n{caption}\r\n'.encode("utf-8"))

    # document file field
    clean_filename = re.sub(r'[^\w\.\-]', '_', filename)
    body.extend(f"--{boundary}\r\n".encode("utf-8"))
    body.extend(
        f'Content-Disposition: form-data; name="document"; filename="{clean_filename}"\r\n'
        f'Content-Type: text/html; charset=utf-8\r\n\r\n'.encode("utf-8")
    )
    body.extend(document_bytes)
    body.extend(f"\r\n--{boundary}--\r\n".encode("utf-8"))

    req = urllib.request.Request(
        url,
        data=bytes(body),
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "User-Agent": "AutoBI-Enterprise-Agent"
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="ignore")
        try:
            err_json = json.loads(err_body)
            desc = err_json.get("description", e.reason)
            raise ValueError(f"Telegram API error ({e.code}): {desc}")
        except ValueError:
            raise
        except Exception:
            raise ValueError(f"Telegram API error ({e.code}): {err_body or e.reason}")


def dispatch_executive_report(
    session_data: Dict[str, Any],
    chat_id: Optional[Union[str, List[str]]] = None,
    bot_token: Optional[str] = None,
    targets: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    High-level orchestrator: sends both executive summary message and attached HTML dashboard
    to one or multiple targets (personal chats, group/channel links, or usernames).
    """
    default_token, default_chat_id = get_default_telegram_config()
    final_token = bot_token or default_token

    if not final_token:
        raise ValueError("Telegram Bot Token is required. Set TELEGRAM_BOT_TOKEN or provide in request.")

    # 1. Gather all targets
    raw_list: List[str] = []
    if targets:
        raw_list.extend(targets)
    if chat_id:
        if isinstance(chat_id, list):
            raw_list.extend(chat_id)
        elif isinstance(chat_id, str):
            parts = re.split(r'[,;\n\r]+', chat_id)
            raw_list.extend([p.strip() for p in parts if p.strip()])

    if not raw_list and default_chat_id:
        raw_list.append(default_chat_id)

    if not raw_list:
        raise ValueError("Telegram Chat ID or target link is required. Please provide a chat ID, username, or channel link.")

    message_text = build_executive_digest_message(session_data)
    dashboard_html = session_data.get("dashboard_html")
    filename = session_data.get("filename", "dataset")
    base_name = os.path.splitext(filename)[0]
    doc_filename = f"Executive_Dashboard_{base_name}.html"
    caption = f"📊 AutoBI Executive Dashboard — {base_name}"

    dispatched = []
    errors = []

    for raw in raw_list:
        dest, label, err = resolve_target_to_chat(raw)
        if err:
            errors.append({"target": raw, "error": err})
            continue

        try:
            # 1. Send text digest
            msg_res = send_telegram_message(message_text, dest, final_token)
            msg_id = msg_res.get("result", {}).get("message_id")

            # 2. Send attached document
            doc_id = None
            if dashboard_html:
                doc_res = send_telegram_document(
                    dashboard_html.encode("utf-8"),
                    filename=doc_filename,
                    caption=caption,
                    chat_id=dest,
                    bot_token=final_token
                )
                doc_id = doc_res.get("result", {}).get("message_id")

            dispatched.append({
                "target": raw,
                "destination": dest,
                "label": label,
                "success": True,
                "message_id": msg_id,
                "document_id": doc_id
            })
        except Exception as e:
            err_str = str(e)
            if "chat not found" in err_str.lower() and raw.startswith("@"):
                err_str = f"Private user {raw} has not clicked /start on @auto_bibot yet, or channel not found."
            errors.append({
                "target": raw,
                "destination": dest,
                "label": label,
                "error": err_str
            })

    if not dispatched and errors:
        raise ValueError(f"Failed to dispatch: {'; '.join([e['error'] for e in errors])}")

    first_disp = dispatched[0] if dispatched else {}
    msg_summary = f"Dispatched report to {len(dispatched)} recipient(s) successfully!" if len(dispatched) > 1 else "Executive digest and dashboard dispatched to Telegram successfully!"

    return {
        "success": True,
        "message": msg_summary,
        "chat_id": first_disp.get("destination"),
        "message_id": first_disp.get("message_id"),
        "document_id": first_disp.get("document_id"),
        "dispatched_count": len(dispatched),
        "dispatched": dispatched,
        "errors": errors
    }
