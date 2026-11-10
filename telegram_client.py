"""
telegram_client.py - 1-Click Executive Telegram Digest & Report Dispatcher
Dispatches high-priority executive KPI digests and interactive HTML dashboard
attachments directly to Telegram channels, groups, or director chats via Telegram Bot API.
"""

import os
import re
import json
import urllib.request
import urllib.error
from typing import Dict, Any, Optional, Tuple


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
    chat_id: Optional[str] = None,
    bot_token: Optional[str] = None
) -> Dict[str, Any]:
    """
    High-level orchestrator: sends both executive summary message and attached HTML dashboard.
    """
    default_token, default_chat_id = get_default_telegram_config()
    final_token = bot_token or default_token
    final_chat_id = chat_id or default_chat_id

    if not final_token:
        raise ValueError("Telegram Bot Token is required. Set TELEGRAM_BOT_TOKEN or provide in request.")
    if not final_chat_id:
        raise ValueError("Telegram Chat ID is required. Set TELEGRAM_CHAT_ID or provide in request.")

    # 1. Format and send summary message
    message_text = build_executive_digest_message(session_data)
    msg_res = send_telegram_message(message_text, final_chat_id, final_token)

    # 2. Send attached interactive HTML dashboard
    doc_res = None
    dashboard_html = session_data.get("dashboard_html")
    if dashboard_html:
        filename = session_data.get("filename", "dataset")
        base_name = os.path.splitext(filename)[0]
        doc_filename = f"Executive_Dashboard_{base_name}.html"
        caption = f"📊 AutoBI Executive Dashboard — {base_name}"
        doc_res = send_telegram_document(
            dashboard_html.encode("utf-8"),
            filename=doc_filename,
            caption=caption,
            chat_id=final_chat_id,
            bot_token=final_token
        )

    return {
        "success": True,
        "message": "Executive digest and dashboard dispatched to Telegram successfully!",
        "chat_id": final_chat_id,
        "message_id": msg_res.get("result", {}).get("message_id"),
        "document_id": doc_res.get("result", {}).get("message_id") if doc_res else None
    }
