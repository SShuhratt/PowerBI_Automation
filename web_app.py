"""
web_app.py - Web Portal Backend for Multi-Domain Self-Healing Spreadsheet to Power BI Engine
Provides REST API endpoints for uploading messy business spreadsheets across domains
(Sales, Marketing, HR, Inventory, Finance), running automated healing & semantic modeling,
and serving downloadable Power BI starter packs.
"""

import os
import io
import uuid
import json
import zipfile
import time
import hmac
import hashlib
from datetime import datetime, timedelta
from typing import Optional
import functools
import pandas as pd
from flask import Flask, request, jsonify, render_template, send_file, send_from_directory, make_response, redirect, url_for
from werkzeug.middleware.proxy_fix import ProxyFix

import re
from cleaner import SelfHealingCleaner
from pbi_model import PowerBIModelGenerator
from domain_classifier import DomainClassifier, DOMAINS, GENERIC_DOMAIN_INFO
from session_store import sessions
from security_vault import users_vault, normalize_email
from reports_store import reports_store, compute_kpi_deltas
from scheduler_service import scheduler_service, start_background_scheduler
from dashboard_preview import generate_html_dashboard
from pbip_generator import generate_pbip_artifacts
from google_sheets import fetch_google_sheets_csv, extract_google_sheets_csv_url
from sql_connector import fetch_readonly_sql_df
from i18n_translations import (
    LEGAL_DOCUMENTS,
    LEGAL_UI,
    SUPPORTED_LANGS,
    SUPPORTED_THEMES,
    normalize_lang,
    normalize_theme,
    resolve_lang,
    resolve_theme,
)

import numpy as np
import math

app = Flask(__name__, static_folder="static", template_folder="templates")
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024  # 32MB max upload
app.json.sort_keys = False

# Authentication configuration
WORKSPACE_PASSCODE = os.environ.get("WORKSPACE_PASSCODE", "autobi2026")
AUTH_ENABLED = os.environ.get("AUTH_ENABLED", "true").lower() in ("true", "1", "yes")

# Cryptographic token signing key
SECRET_KEY = os.environ.get("SECRET_KEY")
if not SECRET_KEY:
    SECRET_KEY = hashlib.sha256(f"autobi_secure_salt_{WORKSPACE_PASSCODE}".encode()).hexdigest()

# Optional bootstrap user account (configured strictly via environment variables)
_BOOTSTRAP_EMAIL = os.environ.get("BOOTSTRAP_USER_EMAIL", "").strip()
_BOOTSTRAP_PASSWORD = os.environ.get("BOOTSTRAP_USER_PASSWORD", "").strip()
if _BOOTSTRAP_EMAIL and _BOOTSTRAP_PASSWORD:
    users_vault.ensure_bootstrap_user(_BOOTSTRAP_EMAIL, _BOOTSTRAP_PASSWORD, full_name="Workspace Owner", role="admin")

# In-memory IP rate limiter for login attempts (max 5 failed attempts per 15 min)
FAILED_LOGINS = {}

def check_login_rate_limit(ip: str) -> bool:
    """Returns True if the IP is allowed to attempt login, False if rate-limited."""
    now = time.time()
    attempts = [t for t in FAILED_LOGINS.get(ip, []) if now - t < 900]
    FAILED_LOGINS[ip] = attempts
    return len(attempts) < 5

def record_failed_login(ip: str):
    now = time.time()
    attempts = [t for t in FAILED_LOGINS.get(ip, []) if now - t < 900]
    attempts.append(now)
    FAILED_LOGINS[ip] = attempts

def reset_failed_logins(ip: str):
    if ip in FAILED_LOGINS:
        del FAILED_LOGINS[ip]


def get_client_ip() -> str:
    """Extract real client IP when running behind Cloudflare and Coolify Traefik."""
    cf_ip = request.headers.get("CF-Connecting-IP")
    if cf_ip:
        return cf_ip.strip()
    xff = request.headers.get("X-Forwarded-For")
    if xff:
        return xff.split(",")[0].strip()
    return request.remote_addr or "127.0.0.1"


def _is_https_request() -> bool:
    """Return True if the request arrived over HTTPS (directly or via Cloudflare/Traefik)."""
    return request.is_secure or request.headers.get("X-Forwarded-Proto", "").lower() == "https"

def sign_auth_token(email: str, ttl_days: int = 30) -> str:
    """Generates a cryptographically signed HMAC-SHA256 token: email|expires_at|signature."""
    exp = int(time.time()) + (ttl_days * 86400)
    payload = f"{email}|{exp}"
    sig = hmac.new(SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}|{sig}"

def verify_auth_token(token: str) -> Optional[str]:
    """Validates the HMAC-SHA256 signature and expiration; returns email if valid."""
    if not token or not isinstance(token, str):
        return None
    parts = token.split("|")
    if len(parts) != 3:
        return None
    email, exp_str, sig = parts
    try:
        exp = int(exp_str)
        if time.time() > exp:
            return None
    except ValueError:
        return None

    payload = f"{email}|{exp_str}"
    expected_sig = hmac.new(SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()
    if hmac.compare_digest(sig, expected_sig):
        return email
    return None

def get_current_user():
    if not AUTH_ENABLED:
        return "pilot@autobi.local"
    # 1. Check cryptographically signed HTTP-only cookie
    user_cookie = request.cookies.get("autobi_user")
    if user_cookie:
        verified_email = verify_auth_token(user_cookie)
        if verified_email:
            return verified_email

    # 2. Check X-Workspace-Key header with constant-time comparison (for tests/APIs)
    key_header = request.headers.get("X-Workspace-Key")
    if key_header and hmac.compare_digest(key_header, WORKSPACE_PASSCODE):
        return "api-client@autobi.local"
    return None


def require_auth(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if not AUTH_ENABLED:
            return f(*args, **kwargs)
        user = get_current_user()
        if not user:
            return jsonify({
                "success": False,
                "error": "Workspace authentication required. Please unlock with workspace passcode.",
                "auth_required": True
            }), 401
        return f(*args, **kwargs)
    return decorated


def sanitize_df_for_csv_export(df: pd.DataFrame) -> pd.DataFrame:
    """
    Prevents CSV Formula / DDE Injection.
    Any text cell starting with '=', '+', '-', '@', '\t', '\r' is escaped with a single quote.
    """
    df_safe = df.copy()
    for col in df_safe.columns:
        if df_safe[col].dtype == object or isinstance(df_safe[col].dtype, pd.StringDtype):
            def escape_formula(val):
                if isinstance(val, str) and val and val[0] in ('=', '+', '-', '@', '\t', '\r'):
                    try:
                        float(val)
                        return val
                    except ValueError:
                        return f"'{val}"
                return val
            df_safe[col] = df_safe[col].map(escape_formula)
    return df_safe


def sanitize_for_json(obj):
    """Recursively ensure all dictionary keys are strings and numeric values are JSON compliant."""
    if isinstance(obj, dict):
        return {str(k): sanitize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple, set)):
        return [sanitize_for_json(v) for v in obj]
    elif isinstance(obj, (bool, np.bool_)):
        return bool(obj)
    elif isinstance(obj, (float, np.floating)):
        if math.isnan(obj) or math.isinf(obj):
            return 0.0
        return float(obj)
    elif isinstance(obj, (int, np.integer)):
        return int(obj)
    elif isinstance(obj, (datetime, pd.Timestamp)):
        return obj.isoformat()
    elif isinstance(obj, uuid.UUID):
        return str(obj)
    elif isinstance(obj, bytes):
        return obj.decode('utf-8', errors='ignore')
    elif obj is None:
        return None
    try:
        if pd.isna(obj):
            return None
    except Exception:
        pass
    return obj


# Multi-worker persistent session storage via session_store (Redis / SQLite WAL)
SAMPLE_FILE_PATH = r"D:\Documents\power_bi_test_sample.xlsx"


def prune_old_sessions():
    """Trigger periodic cleanup of expired sessions."""
    sessions.prune()


def generate_synthetic_demo_df(domain: str) -> pd.DataFrame:
    """Generate realistic demonstration datasets with slight real-world imperfections for instant testing."""
    if domain == "marketing":
        data = [
            {"campaign_id": "CMP-101", "campaign_name": "Summer Blast Q1", "channel": "Google Search", "impressions": 145000, "clicks": 5800, "ad_spend": 3200.0, "conversions": 310, "conversion_value": 15500.0},
            {"campaign_id": "CMP-102", "campaign_name": "Brand Awareness", "channel": "Facebook Ads", "impressions": 280000, "clicks": 7200, "ad_spend": 2400.0, "conversions": 190, "conversion_value": 8550.0},
            {"campaign_id": "CMP-103", "campaign_name": "Retargeting Pro", "channel": "Google Display", "impressions": 95000, "clicks": 4100, "ad_spend": 1850.0, "conversions": 260, "conversion_value": 14300.0},
            {"campaign_id": "CMP-104", "campaign_name": "LinkedIn B2B Ops", "channel": "LinkedIn", "impressions": 48000, "clicks": 1650, "ad_spend": 3100.0, "conversions": 145, "conversion_value": 18850.0},
            {"campaign_id": "CMP-105", "campaign_name": "Influencer Drop", "channel": "Instagram", "impressions": 320000, "clicks": 9800, "ad_spend": 4500.0, "conversions": 420, "conversion_value": 23100.0},
            {"campaign_id": "CMP-106", "campaign_name": "Email Newsletter", "channel": "Direct Mail", "impressions": 35000, "clicks": 2800, "ad_spend": 450.0, "conversions": 180, "conversion_value": 9900.0},
            {"campaign_id": "Total Summary", "campaign_name": "Total", "channel": "All", "impressions": 923000, "clicks": 31350, "ad_spend": 15500.0, "conversions": 1505, "conversion_value": 90200.0},
        ]
        return pd.DataFrame(data)

    elif domain == "hr":
        data = [
            {"employee_id": "EMP-001", "name": "Alice Chen", "department": "Engineering", "job_title": "Staff Engineer", "hire_date": "2021-03-15", "termination_date": None, "salary": 145000, "performance_score": 4.8},
            {"employee_id": "EMP-002", "name": "Bob Miller", "department": "Sales", "job_title": "Account Exec", "hire_date": "2022-06-01", "termination_date": None, "salary": 95000, "performance_score": 4.2},
            {"employee_id": "EMP-003", "name": "Carol Danvers", "department": "Marketing", "job_title": "Demand Gen Lead", "hire_date": "2020-01-10", "termination_date": "2025-11-30", "salary": 110000, "performance_score": 3.9},
            {"employee_id": "EMP-004", "name": "David Ross", "department": "Engineering", "job_title": "Frontend Dev", "hire_date": "2023-08-14", "termination_date": None, "salary": 115000, "performance_score": 4.5},
            {"employee_id": "EMP-005", "name": "Elena Rostova", "department": "Product", "job_title": "Product Manager", "hire_date": "2021-11-05", "termination_date": None, "salary": 135000, "performance_score": 4.7},
            {"employee_id": "EMP-006", "name": "Frank Castle", "department": "Operations", "job_title": "Logistics Analyst", "hire_date": "2022-02-18", "termination_date": "2026-01-15", "salary": 78000, "performance_score": 3.5},
            {"employee_id": "EMP-007", "name": "Grace Hopper", "department": "Engineering", "job_title": "Principal Architect", "hire_date": "2019-05-20", "termination_date": None, "salary": 185000, "performance_score": 4.9},
            {"employee_id": "Total Employees", "name": "Average / Sum", "department": "Company", "hire_date": None, "termination_date": None, "salary": 863000, "performance_score": 4.35},
        ]
        return pd.DataFrame(data)

    elif domain == "inventory":
        data = [
            {"sku": "SKU-EL-001", "product_name": "Noise Cancelling Headphones", "category": "Electronics", "warehouse": "West Coast Hub", "units_on_hand": 140, "reorder_level": 50, "unit_cost": 85.0, "lead_time_days": 12},
            {"sku": "SKU-EL-002", "product_name": "Mechanical Keyboard Pro", "category": "Electronics", "warehouse": "East Coast Hub", "units_on_hand": 25, "reorder_level": 40, "unit_cost": 65.0, "lead_time_days": 14},
            {"sku": "SKU-OF-003", "product_name": "Ergonomic Mesh Chair", "category": "Furniture", "warehouse": "Central Depot", "units_on_hand": 0, "reorder_level": 15, "unit_cost": 210.0, "lead_time_days": 21},
            {"sku": "SKU-OF-004", "product_name": "Standing Desk 60-inch", "category": "Furniture", "warehouse": "West Coast Hub", "units_on_hand": 8, "reorder_level": 12, "unit_cost": 340.0, "lead_time_days": 18},
            {"sku": "SKU-AC-005", "product_name": "USB-C Multiport Adapter", "category": "Accessories", "warehouse": "Central Depot", "units_on_hand": 450, "reorder_level": 100, "unit_cost": 14.5, "lead_time_days": 7},
            {"sku": "SKU-AC-006", "product_name": "Wireless Vertical Mouse", "category": "Accessories", "warehouse": "East Coast Hub", "units_on_hand": 18, "reorder_level": 30, "unit_cost": 28.0, "lead_time_days": 10},
            {"sku": "Total SKU Summary", "product_name": "Total Stock", "category": "All", "warehouse": "Network", "units_on_hand": 641, "reorder_level": 247, "unit_cost": 742.5, "lead_time_days": 13.6},
        ]
        return pd.DataFrame(data)

    elif domain == "finance":
        data = [
            {"account_id": "GL-401", "account_name": "Enterprise SaaS", "category": "Revenue", "currency": "USD", "revenue": 48500.0, "expenses": 12400.0, "budget": 45000.0, "profit": None},
            {"account_id": "GL-402", "account_name": "Tashkent Retail", "category": "Revenue", "currency": "UZS", "revenue": 320000000.0, "expenses": 195000000.0, "budget": 300000000.0, "profit": None},
            {"account_id": "GL-501", "account_name": "Cloud Infrastructure", "category": "OPEX", "currency": "USD", "revenue": 14200.0, "expenses": 8900.0, "budget": 15000.0, "profit": None},
            {"account_id": "GL-502", "account_name": "Regional Logistics", "category": "OPEX", "currency": "UZS", "revenue": 145000000.0, "expenses": 162000000.0, "budget": 150000000.0, "profit": None},
            {"account_id": "GL-403", "account_name": "Advisory Retainers", "category": "Revenue", "currency": "USD", "revenue": 29400.0, "expenses": 7200.0, "budget": 28000.0, "profit": None},
            {"account_id": "Total Summary", "account_name": "Total", "category": "All", "currency": "USD", "revenue": 92100.0, "expenses": 28500.0, "budget": 88000.0, "profit": None},
        ]
        return pd.DataFrame(data)

    elif domain == "crm":
        data = [
            {"ID сделки": "AMO-901", "Этап сделки": "Успешно реализовано", "Ответственный": "Sardorbek R.", "Бюджет": 4200.0, "Дата создания": "2026-10-02"},
            {"ID сделки": "AMO-902", "Этап сделки": "Переговоры", "Ответственный": "Madina K.", "Бюджет": 2900.0, "Дата создания": "2026-10-08"},
            {"ID сделки": "AMO-903", "Этап сделки": "Успешно реализовано", "Ответственный": "Sardorbek R.", "Бюджет": 6100.0, "Дата создания": "2026-10-14"},
            {"ID сделки": "AMO-904", "Этап сделки": "Отказ клиента", "Ответственный": "Timur A.", "Бюджет": 1800.0, "Дата создания": "2026-10-19"},
            {"ID сделки": "AMO-905", "Этап сделки": "Успешно реализовано", "Ответственный": "Madina K.", "Бюджет": 5400.0, "Дата создания": "2026-10-25"},
            {"ID сделки": "Итого", "Этап сделки": "Total", "Ответственный": None, "Бюджет": 20400.0, "Дата создания": None},
        ]
        return pd.DataFrame(data)

    elif domain == "uzum":
        data = [
            {"Артикул": "UZM-TWS-01", "Товар": "Беспроводные наушники Pro", "units_sold": 85, "Выручка": 10200.0, "Комиссия": 1530.0, "Логистика": 425.0},
            {"Артикул": "UZM-KBD-02", "Товар": "Механическая клавиатура", "units_sold": 34, "Выручка": 4080.0, "Комиссия": 612.0, "Логистика": 204.0},
            {"Артикул": "UZM-CHG-03", "Товар": "Быстрая зарядка 65W", "units_sold": 120, "Выручка": 3600.0, "Комиссия": 540.0, "Логистика": 360.0},
            {"Артикул": "UZM-HUB-04", "Товар": "USB-C Док-станция", "units_sold": 48, "Выручка": 3840.0, "Комиссия": 576.0, "Логистика": 192.0},
            {"Артикул": "Итого", "Товар": "All SKUs", "units_sold": 287, "Выручка": 21720.0, "Комиссия": 3258.0, "Логистика": 1181.0},
        ]
        return pd.DataFrame(data)

    elif domain == "generic":
        data = [
            {"ticket_id": "OPS-401", "service_date": "2026-01-10", "hub_region": "Tashkent Central", "team_lead": "Aziz Karimov", "sla_hours": 3.4, "cases_resolved": 42, "csat_score": 4.8},
            {"ticket_id": "OPS-402", "service_date": "2026-01-12", "hub_region": "Samarkand Hub", "team_lead": "Dilnoza Aliyeva", "sla_hours": 4.1, "cases_resolved": 35, "csat_score": 4.6},
            {"ticket_id": "OPS-403", "service_date": "2026-01-14", "hub_region": "Bukhara West", "team_lead": "Timur Rustamov", "sla_hours": 5.2, "cases_resolved": 28, "csat_score": 4.4},
            {"ticket_id": "OPS-404", "service_date": "2026-01-16", "hub_region": "Tashkent Central", "team_lead": "Aziz Karimov", "sla_hours": 2.9, "cases_resolved": 49, "csat_score": 4.9},
            {"ticket_id": "OPS-405", "service_date": "2026-01-19", "hub_region": "Fergana Valley", "team_lead": "Madina Umarova", "sla_hours": 3.8, "cases_resolved": 37, "csat_score": 4.7},
            {"ticket_id": "Total Summary", "service_date": None, "hub_region": "All Hubs", "team_lead": None, "sla_hours": 3.88, "cases_resolved": 191, "csat_score": 4.68},
        ]
        return pd.DataFrame(data)

    else:
        # Default fallback to Sales demo
        if os.path.exists(SAMPLE_FILE_PATH):
            return pd.read_excel(SAMPLE_FILE_PATH)
        data = [
            {"order_id": 1001, "order_date": "2026-01-15", "region": "North", "sales_rep": "John Smith", "category": "Electronics", "units_sold": 12, "unit_price": 150.0, "total_revenue": None, "status": "Completed"},
            {"order_id": 1002, "order_date": "2026-01-18", "region": "East", "sales_rep": "Sarah Jenkins", "category": "Office Supplies", "units_sold": 45, "unit_price": 12.5, "total_revenue": None, "status": "Completed"},
            {"order_id": "Total", "order_date": None, "region": None, "sales_rep": None, "category": None, "units_sold": 57, "unit_price": 162.5, "total_revenue": None, "status": None},
        ]
        return pd.DataFrame(data)


def _humanize_col(col: str, display_labels: Optional[dict] = None) -> str:
    """Return original readable column header or strip col_/underscore boilerplate."""
    col_str = str(col or "").strip()
    if display_labels and col_str in display_labels and str(display_labels[col_str]).strip():
        return str(display_labels[col_str]).strip()
    cleaned = re.sub(r'^col_+', '', col_str)
    cleaned = re.sub(r'_+', ' ', cleaned).strip()
    if not cleaned:
        return "Value"
    acronyms = {"uzs", "usd", "fx", "kpi", "sku", "abc", "gdp", "roi", "gl", "id", "ctr", "cpc", "roas"}
    words = []
    for idx, tok in enumerate(cleaned.split()):
        low = tok.lower()
        if low in acronyms:
            words.append(low.upper())
        elif idx == 0:
            words.append(tok[:1].upper() + tok[1:])
        else:
            words.append(tok)
    return " ".join(words)


def _format_metric_value(val: float) -> str:
    """Format numeric KPI values cleanly without trailing noise."""
    if pd.isna(val):
        return "0"
    if abs(val) >= 1000:
        return f"{val:,.1f}" if abs(val % 1) >= 0.05 else f"{val:,.0f}"
    if abs(val) >= 10:
        return f"{val:,.2f}" if abs(val % 1) >= 0.005 else f"{val:,.0f}"
    return f"{val:,.3f}".rstrip("0").rstrip(".") if "." in f"{val:,.3f}" else f"{val:,.0f}"


def _pick_generic_columns(df: pd.DataFrame, num_cols: list[str], cat_cols: list[str]) -> tuple[Optional[str], list[str], Optional[str]]:
    """Separate axis/sequence columns from real numeric metrics and choose best breakdown dimension."""
    seq_pattern = re.compile(
        r'^(id|no|num|idx|index|row|seq|step|davr|period|yil|year|quarter|month|day|t)$|_id$|^id_',
        re.IGNORECASE,
    )
    axis_col: Optional[str] = None
    metric_cols: list[str] = []

    dt_cols = [c for c in df.columns if pd.api.types.is_datetime64_any_dtype(df[c])]
    if dt_cols:
        axis_col = dt_cols[0]

    for c in num_cols:
        s = df[c].dropna()
        is_seq = bool(seq_pattern.search(str(c)))
        if not is_seq and len(s) >= 4:
            try:
                is_int_like = bool((s % 1 == 0).all())
                diffs = s.diff().dropna()
                if is_int_like and len(diffs) > 0 and (diffs > 0).all() and diffs.nunique() == 1 and diffs.iloc[0] in (1, 5, 10):
                    is_seq = True
            except Exception:
                pass
        if is_seq:
            if axis_col is None:
                axis_col = c
        else:
            metric_cols.append(c)

    if not metric_cols and num_cols:
        metric_cols = [c for c in num_cols if c != axis_col] or list(num_cols)

    # Prefer metrics that are actual quantities/values before small ratios/growth rates
    ratio_hint = re.compile(r'%|rate|ratio|growth|pct|share|sur|nisbat', re.IGNORECASE)
    metric_cols.sort(key=lambda c: (1 if ratio_hint.search(str(c)) else 0))

    # Pick most informative categorical dimension (low-to-medium cardinality: 2..12 distinct values)
    usable_cats = [c for c in cat_cols if c not in dt_cols]
    dim_col: Optional[str] = None
    if usable_cats:
        bounded = [(int(df[c].nunique(dropna=True)), c) for c in usable_cats if 2 <= df[c].nunique(dropna=True) <= 12]
        if bounded:
            bounded.sort(key=lambda x: x[0])
            dim_col = bounded[0][1]
        else:
            varied = [c for c in usable_cats if df[c].nunique(dropna=True) >= 2]
            dim_col = varied[0] if varied else usable_cats[0]

    return axis_col, metric_cols, dim_col


def _compute_domain_analytics(
    df: pd.DataFrame,
    domain_key: str,
    display_labels: Optional[dict] = None,
) -> tuple[list, dict]:
    """Compute domain-specific KPI cards and chart configurations from a cleaned DataFrame."""
    display_labels = display_labels or {}
    cols = [c for c in df.columns if not str(c).startswith("_temp_")]
    kpis = []
    charts = {}

    if domain_key == "marketing":
        spend = float(df["ad_spend"].sum()) if "ad_spend" in cols else 0.0
        clicks = int(df["clicks"].sum()) if "clicks" in cols else 0
        imps = int(df["impressions"].sum()) if "impressions" in cols else 0
        convs = int(df["conversions"].sum()) if "conversions" in cols else 0
        conv_val = float(df["conversion_value"].sum()) if "conversion_value" in cols else 0.0

        ctr = (clicks / imps * 100) if imps > 0 else 0.0
        cpc = (spend / clicks) if clicks > 0 else 0.0
        roas = (conv_val / spend) if spend > 0 else 0.0

        kpis = [
            {"label": "Total Ad Spend", "value": f"${spend:,.2f}", "sub": "Campaign budget deployed", "theme": ""},
            {"label": "Total Clicks Delivered", "value": f"{clicks:,}", "sub": f"From {imps:,} impressions", "theme": "cyan"},
            {"label": "Click-Through Rate (CTR)", "value": f"{ctr:.2f}%", "sub": "Audience engagement rate", "theme": "emerald"},
            {"label": "Cost Per Click (CPC)", "value": f"${cpc:.2f}", "sub": "Average traffic acquisition cost", "theme": "amber"},
            {"label": "Total Conversions", "value": f"{convs:,}", "sub": "Purchases / qualified leads", "theme": "cyan"},
            {"label": "Return on Ad Spend (ROAS)", "value": f"{roas:.2f}x", "sub": f"Value: ${conv_val:,.2f}", "theme": "emerald"}
        ]

        if "channel" in cols and "ad_spend" in cols:
            charts["chart1"] = {
                "title": "Ad Spend by Channel",
                "type": "doughnut",
                "series_label": "Ad Spend",
                "data": {str(k): round(float(v), 2) for k, v in df.groupby("channel")["ad_spend"].sum().items()}
            }
        if "campaign_name" in cols and "conversions" in cols:
            charts["chart2"] = {
                "title": "Conversions by Campaign",
                "type": "bar",
                "series_label": "Conversions",
                "data": {str(k): int(v) for k, v in df.groupby("campaign_name")["conversions"].sum().items()}
            }

    elif domain_key == "hr":
        headcount = len(df)
        term_col = "termination_date" if "termination_date" in cols else None
        active = len(df[df[term_col].isna()]) if term_col else headcount
        departed = headcount - active
        attrition = (departed / headcount * 100) if headcount > 0 else 0.0
        avg_sal = float(df["salary"].mean()) if "salary" in cols and headcount > 0 else 0.0
        payroll = float(df["salary"].sum()) if "salary" in cols else 0.0

        kpis = [
            {"label": "Total Workforce", "value": f"{headcount:,}", "sub": "All recorded personnel", "theme": ""},
            {"label": "Active Headcount", "value": f"{active:,}", "sub": "Currently on payroll", "theme": "emerald"},
            {"label": "Departed Staff", "value": f"{departed:,}", "sub": "Exits & terminations", "theme": "rose"},
            {"label": "Workforce Attrition", "value": f"{attrition:.1f}%", "sub": "Overall turnover rate", "theme": "amber"},
            {"label": "Average Annual Salary", "value": f"${avg_sal:,.0f}", "sub": "Mean company compensation", "theme": "cyan"},
            {"label": "Cumulative Payroll", "value": f"${payroll:,.0f}", "sub": "Total annualized payroll", "theme": ""}
        ]

        if "department" in cols:
            charts["chart1"] = {
                "title": "Headcount by Department",
                "type": "bar",
                "series_label": "Employees",
                "data": {str(k): int(v) for k, v in df["department"].value_counts().items()}
            }
        if "department" in cols and "salary" in cols:
            charts["chart2"] = {
                "title": "Payroll Spend by Department",
                "type": "doughnut",
                "series_label": "Payroll",
                "data": {str(k): round(float(v), 2) for k, v in df.groupby("department")["salary"].sum().items()}
            }

    elif domain_key == "inventory":
        sku_col = "sku" if "sku" in cols else None
        stock_col = "units_on_hand" if "units_on_hand" in cols else None
        cost_col = "unit_cost" if "unit_cost" in cols else None
        reorder_col = "reorder_level" if "reorder_level" in cols else None

        skus = int(df[sku_col].nunique()) if sku_col else len(df)
        units = int(df[stock_col].sum()) if stock_col else 0
        val = float((df[stock_col] * df[cost_col]).sum()) if stock_col and cost_col else 0.0
        oos = len(df[df[stock_col] <= 0]) if stock_col else 0
        reorders = len(df[df[stock_col] <= df[reorder_col]]) if stock_col and reorder_col else 0
        stockout_rate = (oos / skus * 100) if skus > 0 else 0.0

        kpis = [
            {"label": "Total Inventory Value", "value": f"${val:,.2f}", "sub": "Warehouse valuation", "theme": "emerald"},
            {"label": "Units in Stock", "value": f"{units:,}", "sub": "Total physical items", "theme": "cyan"},
            {"label": "Catalog SKU Count", "value": f"{skus:,}", "sub": "Distinct items tracked", "theme": ""},
            {"label": "Stockout Rate", "value": f"{stockout_rate:.1f}%", "sub": f"{oos} out-of-stock SKUs", "theme": "rose"},
            {"label": "Reorder Threshold Alerts", "value": f"{reorders:,}", "sub": "Under safety stock limit", "theme": "amber"},
            {"label": "Active Warehouses", "value": f"{df['warehouse'].nunique() if 'warehouse' in cols else 1}", "sub": "Fulfillment facilities", "theme": ""}
        ]

        if "category" in cols and stock_col and cost_col:
            cat_vals = df.assign(_tmp_val=df[stock_col] * df[cost_col]).groupby("category")["_tmp_val"].sum()
            charts["chart1"] = {
                "title": "Inventory Value by Category",
                "type": "bar",
                "series_label": "Inventory Value",
                "data": {str(k): round(float(v), 2) for k, v in cat_vals.items()}
            }
        if "warehouse" in cols and stock_col:
            charts["chart2"] = {
                "title": "Unit Distribution by Warehouse",
                "type": "doughnut",
                "series_label": "Units",
                "data": {str(k): int(v) for k, v in df.groupby("warehouse")[stock_col].sum().items()}
            }

    elif domain_key == "finance":
        rev_col = next((c for c in cols if any(k in c for k in ["revenue", "income", "sales", "actual"])), None)
        exp_col = next((c for c in cols if any(k in c for k in ["expense", "opex", "cost", "spending"])), None)
        profit_col = next((c for c in cols if any(k in c for k in ["profit", "net_income", "margin"])), None)
        budget_col = next((c for c in cols if "budget" in c), None)
        account_col = next((c for c in cols if any(k in c for k in ["account", "gl_code", "category", "entity"])), None)

        tot_rev = float(df[rev_col].sum()) if rev_col and pd.api.types.is_numeric_dtype(df[rev_col]) else 0.0
        tot_exp = float(df[exp_col].sum()) if exp_col and pd.api.types.is_numeric_dtype(df[exp_col]) else 0.0
        net_prof = float(df[profit_col].sum()) if profit_col and pd.api.types.is_numeric_dtype(df[profit_col]) else (tot_rev - tot_exp if rev_col and exp_col else 0.0)
        margin = (net_prof / tot_rev * 100) if tot_rev > 0 else 0.0
        tot_budget = float(df[budget_col].sum()) if budget_col and pd.api.types.is_numeric_dtype(df[budget_col]) else 0.0
        variance = (tot_rev - tot_budget) if rev_col and budget_col else 0.0
        accts = int(df[account_col].nunique()) if account_col else len(df)

        kpis = [
            {"label": "Total Revenue / Inflow", "value": f"${tot_rev:,.2f}" if tot_rev > 0 else f"{tot_rev:,.0f}", "sub": "Operating inflow", "theme": "emerald"},
            {"label": "Operating Expenses", "value": f"${tot_exp:,.2f}" if tot_exp > 0 else f"{tot_exp:,.0f}", "sub": "Recorded expenditure", "theme": "rose"},
            {"label": "Net Operating Profit", "value": f"${net_prof:,.2f}" if net_prof != 0 else f"{net_prof:,.0f}", "sub": "Earnings before taxes", "theme": "emerald" if net_prof >= 0 else "rose"},
            {"label": "Operating Margin", "value": f"{margin:.1f}%", "sub": "Profit conversion rate", "theme": "cyan"},
            {"label": "Budget Target", "value": f"${tot_budget:,.2f}" if tot_budget > 0 else f"{tot_budget:,.0f}", "sub": f"Variance: ${variance:,.0f}", "theme": "amber"},
            {"label": "Active GL Accounts", "value": f"{accts:,}", "sub": "Monitored accounts / entities", "theme": ""}
        ]

        if account_col and exp_col and pd.api.types.is_numeric_dtype(df[exp_col]):
            charts["chart1"] = {
                "title": f"Expenses by {_humanize_col(account_col, display_labels)}",
                "type": "bar",
                "series_label": _humanize_col(exp_col, display_labels),
                "data": {str(k): round(float(v), 2) for k, v in df.groupby(account_col)[exp_col].sum().head(10).items()}
            }
        elif account_col and rev_col and pd.api.types.is_numeric_dtype(df[rev_col]):
            charts["chart1"] = {
                "title": f"Revenue by {_humanize_col(account_col, display_labels)}",
                "type": "bar",
                "series_label": _humanize_col(rev_col, display_labels),
                "data": {str(k): round(float(v), 2) for k, v in df.groupby(account_col)[rev_col].sum().head(10).items()}
            }
        if account_col:
            charts["chart2"] = {
                "title": f"Distribution by {_humanize_col(account_col, display_labels)}",
                "type": "doughnut",
                "series_label": "Records",
                "data": {str(k): int(v) for k, v in df[account_col].value_counts().head(8).items()}
            }

    elif domain_key == "generic":
        total_records = len(df)
        total_cols = len(cols)
        total_cells = max(total_records * total_cols, 1)
        filled_cells = int(df[cols].notna().sum().sum()) if cols else 0
        completeness = (filled_cells / total_cells) * 100.0

        num_cols = [c for c in cols if pd.api.types.is_numeric_dtype(df[c])]
        cat_cols = [c for c in cols if not pd.api.types.is_numeric_dtype(df[c])]
        axis_col, metric_cols, dim_col = _pick_generic_columns(df, num_cols, cat_cols)

        m1 = metric_cols[0] if metric_cols else None
        m2 = metric_cols[1] if len(metric_cols) > 1 else None
        m1_label = _humanize_col(m1, display_labels) if m1 else ""
        m2_label = _humanize_col(m2, display_labels) if m2 else ""
        axis_label = _humanize_col(axis_col, display_labels) if axis_col else ""
        dim_label = _humanize_col(dim_col, display_labels) if dim_col else ""

        kpis = [
            {"label": "Total Records", "value": f"{total_records:,}", "sub": f"{total_cols} attributes tracked", "theme": "emerald"},
        ]

        if m1:
            m1_series = df[m1].dropna()
            m1_sum = float(m1_series.sum()) if len(m1_series) else 0.0
            m1_avg = float(m1_series.mean()) if len(m1_series) else 0.0
            kpis.append({"label": f"Total {m1_label}", "value": _format_metric_value(m1_sum), "sub": f"Average: {_format_metric_value(m1_avg)}", "theme": "cyan"})
        else:
            kpis.append({"label": "Tracked Fields", "value": f"{total_cols:,}", "sub": f"{len(cat_cols)} text / category attributes", "theme": "cyan"})

        if m2:
            m2_series = df[m2].dropna()
            m2_avg = float(m2_series.mean()) if len(m2_series) else 0.0
            m2_max = float(m2_series.max()) if len(m2_series) else 0.0
            kpis.append({"label": f"Average {m2_label}", "value": _format_metric_value(m2_avg), "sub": f"Peak: {_format_metric_value(m2_max)}", "theme": ""})
        else:
            kpis.append({"label": "Numeric Metrics", "value": f"{len(metric_cols):,}", "sub": "Quantitative measurements", "theme": ""})

        if dim_col:
            vc = df[dim_col].dropna().astype(str).value_counts()
            unique_dim = int(vc.shape[0])
            top_name = str(vc.index[0]) if len(vc) > 0 else "—"
            top_pct = (int(vc.iloc[0]) / max(total_records, 1)) * 100.0 if len(vc) > 0 else 0.0
            kpis.append({"label": dim_label, "value": f"{unique_dim:,}", "sub": f"Top: {top_name} ({top_pct:.0f}%)", "theme": "amber"})
        elif axis_col:
            ax_series = df[axis_col].dropna()
            span_sub = f"{ax_series.min()} – {ax_series.max()}" if len(ax_series) else "Sequence"
            kpis.append({"label": axis_label, "value": f"{int(ax_series.nunique()):,}", "sub": span_sub, "theme": "amber"})

        kpis.append({
            "label": "Data Completeness",
            "value": f"{completeness:.1f}%",
            "sub": f"{filled_cells:,} populated values",
            "theme": "emerald" if completeness >= 80 else "amber"
        })

        if m1 and axis_col and len(df) >= 2:
            trend_df = df[[axis_col, m1]].dropna().copy()
            if len(trend_df) > 36:
                step = max(len(trend_df) // 36, 1)
                trend_df = trend_df.iloc[::step].head(36)
            if pd.api.types.is_datetime64_any_dtype(trend_df[axis_col]):
                ax_keys = trend_df[axis_col].dt.strftime("%Y-%m-%d").tolist()
            else:
                ax_keys = [
                    str(int(v)) if isinstance(v, (int, float)) and float(v).is_integer() else str(v)
                    for v in trend_df[axis_col].tolist()
                ]
            charts["chart1"] = {
                "title": f"{m1_label} ({axis_label})",
                "type": "line",
                "series_label": m1_label,
                "data": {k: round(float(v), 2) for k, v in zip(ax_keys, trend_df[m1].tolist())}
            }
        elif m1 and dim_col and df[dim_col].nunique(dropna=True) >= 2:
            grouped = df.groupby(dim_col)[m1].sum().head(10)
            charts["chart1"] = {
                "title": f"{m1_label} by {dim_label}",
                "type": "bar",
                "series_label": m1_label,
                "data": {str(k): round(float(v), 2) for k, v in grouped.items()}
            }
        elif len(metric_cols) >= 2:
            charts["chart1"] = {
                "title": "Average Value by Metric",
                "type": "bar",
                "series_label": "Average",
                "data": {_humanize_col(c, display_labels): round(float(df[c].mean()), 2) for c in metric_cols[:8] if df[c].notna().any()}
            }
        elif dim_col and df[dim_col].nunique(dropna=True) >= 2:
            vc = df[dim_col].dropna().astype(str).value_counts().head(8)
            charts["chart1"] = {
                "title": f"Distribution: {dim_label}",
                "type": "bar",
                "series_label": "Records",
                "data": {str(k): int(v) for k, v in vc.items()}
            }
        else:
            col_fill_rates = {_humanize_col(c, display_labels): round(float(df[c].notna().mean() * 100), 1) for c in cols[:10]}
            charts["chart1"] = {
                "title": "Data Completeness by Field (%)",
                "type": "bar",
                "series_label": "Completeness %",
                "data": col_fill_rates
            }

        if dim_col and df[dim_col].nunique(dropna=True) >= 2:
            vc = df[dim_col].dropna().astype(str).value_counts().head(8)
            charts["chart2"] = {
                "title": f"Breakdown: {dim_label}",
                "type": "doughnut",
                "series_label": "Records",
                "data": {str(k): int(v) for k, v in vc.items()}
            }
        elif m2 and axis_col and len(df) >= 2:
            trend_df2 = df[[axis_col, m2]].dropna().copy()
            if len(trend_df2) > 36:
                step2 = max(len(trend_df2) // 36, 1)
                trend_df2 = trend_df2.iloc[::step2].head(36)
            if pd.api.types.is_datetime64_any_dtype(trend_df2[axis_col]):
                ax_keys2 = trend_df2[axis_col].dt.strftime("%Y-%m-%d").tolist()
            else:
                ax_keys2 = [
                    str(int(v)) if isinstance(v, (int, float)) and float(v).is_integer() else str(v)
                    for v in trend_df2[axis_col].tolist()
                ]
            charts["chart2"] = {
                "title": f"{m2_label} ({axis_label})",
                "type": "line",
                "series_label": m2_label,
                "data": {k: round(float(v), 2) for k, v in zip(ax_keys2, trend_df2[m2].tolist())}
            }
        elif len(metric_cols) >= 2:
            charts["chart2"] = {
                "title": "Total Volume by Metric",
                "type": "bar",
                "series_label": "Total",
                "data": {_humanize_col(c, display_labels): round(float(df[c].sum()), 2) for c in metric_cols[:8] if df[c].notna().any()}
            }

    else:
        # Default to Sales Domain
        total_rev = float(df["total_revenue"].sum()) if "total_revenue" in cols and pd.api.types.is_numeric_dtype(df["total_revenue"]) else 0.0
        total_units = int(df["units_sold"].sum()) if "units_sold" in cols and pd.api.types.is_numeric_dtype(df["units_sold"]) else 0
        total_orders = int(df["order_id"].nunique()) if "order_id" in cols else len(df)
        aov = (total_rev / total_orders) if total_orders > 0 else 0.0
        completed_rev = float(df[df["status"] == "Completed"]["total_revenue"].sum()) if "status" in cols and "total_revenue" in cols and pd.api.types.is_numeric_dtype(df["total_revenue"]) else 0.0
        cancel_rate = (len(df[df["status"] == "Cancelled"]) / len(df) * 100) if "status" in cols and len(df) > 0 else 0.0

        kpis = [
            {"label": "Total Gross Revenue", "value": f"${total_rev:,.2f}", "sub": "Across catalog sales", "theme": "emerald"},
            {"label": "Volume Sold", "value": f"{total_units:,}", "sub": "Total items purchased", "theme": "cyan"},
            {"label": "Total Orders", "value": f"{total_orders:,}", "sub": "Distinct transactions", "theme": ""},
            {"label": "Average Order Value", "value": f"${aov:,.2f}", "sub": "Average basket size", "theme": "amber"},
            {"label": "Completed Revenue", "value": f"${completed_rev:,.2f}", "sub": "Fulfilled cashflow", "theme": "emerald"},
            {"label": "Cancellation Rate", "value": f"{cancel_rate:.1f}%", "sub": "Operational risk", "theme": "rose"}
        ]

        if "category" in cols and "total_revenue" in cols and pd.api.types.is_numeric_dtype(df["total_revenue"]):
            charts["chart1"] = {
                "title": "Revenue by Product Category",
                "type": "bar",
                "series_label": "Revenue",
                "data": {str(k): round(float(v), 2) for k, v in df.groupby("category")["total_revenue"].sum().items()}
            }
        if "region" in cols and "total_revenue" in cols and pd.api.types.is_numeric_dtype(df["total_revenue"]):
            charts["chart2"] = {
                "title": "Revenue Distribution by Region",
                "type": "doughnut",
                "series_label": "Revenue",
                "data": {str(k): round(float(v), 2) for k, v in df.groupby("region")["total_revenue"].sum().items()}
            }

    return kpis, charts


def _extract_interactive_schema(df: pd.DataFrame, display_labels: Optional[dict] = None) -> dict:
    """Inspect cleaned DataFrame and expose column metadata + low-cardinality slicers for interactive BI."""
    display_labels = display_labels or {}
    cols = [c for c in df.columns if not str(c).startswith("_temp_")]
    numeric_cols = [
        {"key": str(c), "label": _humanize_col(c, display_labels)}
        for c in cols
        if pd.api.types.is_numeric_dtype(df[c])
    ]
    dt_cols = [c for c in cols if pd.api.types.is_datetime64_any_dtype(df[c])]
    cat_cols = [c for c in cols if c not in dt_cols and not pd.api.types.is_numeric_dtype(df[c])]

    # Ordered dimension list: dates first, then categoricals, then remaining numeric axis candidates
    ordered_dims = dt_cols + cat_cols + [c for c in cols if c not in dt_cols and c not in cat_cols]
    dimension_cols = [{"key": str(c), "label": _humanize_col(c, display_labels)} for c in ordered_dims]

    slicers = []
    for c in cat_cols:
        vals = df[c].dropna().astype(str).str.strip()
        vals = vals[vals != ""]
        uniq_cnt = int(vals.nunique())
        if 2 <= uniq_cnt <= 25:
            slicers.append({
                "key": str(c),
                "label": _humanize_col(c, display_labels),
                "values": sorted(vals.unique().tolist())[:25],
                "cardinality": uniq_cnt,
            })
    slicers.sort(key=lambda s: s["cardinality"])
    slicers = [{k: v for k, v in s.items() if k != "cardinality"} for s in slicers[:2]]

    date_meta = None
    if dt_cols:
        d_series = df[dt_cols[0]].dropna()
        if len(d_series) > 0:
            date_meta = {
                "key": str(dt_cols[0]),
                "label": _humanize_col(dt_cols[0], display_labels),
                "min": d_series.min().strftime("%Y-%m-%d"),
                "max": d_series.max().strftime("%Y-%m-%d"),
            }

    return {
        "numeric_cols": numeric_cols,
        "dimension_cols": dimension_cols,
        "slicers": slicers,
        "date_col": date_meta,
    }


def _build_custom_chart(df: pd.DataFrame, spec: dict, display_labels: Optional[dict] = None) -> dict:
    """Compute deterministic custom chart aggregation validated against available DataFrame columns."""
    display_labels = display_labels or {}
    cols = [c for c in df.columns if not str(c).startswith("_temp_")]
    dim = str((spec or {}).get("dim") or "").strip()
    metric = str((spec or {}).get("metric") or "__count__").strip()
    agg = str((spec or {}).get("agg") or "sum").strip().lower()
    chart_type = str((spec or {}).get("type") or "bar").strip().lower()

    if chart_type not in ("bar", "line", "doughnut"):
        raise ValueError(f"Unsupported chart type '{chart_type}'.")
    if agg not in ("sum", "avg", "count", "max"):
        raise ValueError(f"Unsupported aggregation '{agg}'.")
    if not dim or dim not in cols:
        raise ValueError(f"Invalid dimension column '{dim}'.")
    if metric != "__count__" and (metric not in cols or not pd.api.types.is_numeric_dtype(df[metric])):
        raise ValueError(f"Invalid numeric metric column '{metric}'.")

    dim_label = _humanize_col(dim, display_labels)
    if metric == "__count__" or agg == "count":
        series = df[dim].dropna().astype(str).value_counts()
        if chart_type == "line":
            series = series.head(36)
        else:
            series = series.head(12)
        return {
            "title": f"Record Count by {dim_label}",
            "type": chart_type,
            "series_label": "Records",
            "data": {str(k): int(v) for k, v in series.items()},
        }

    metric_label = _humanize_col(metric, display_labels)
    work = df[[dim, metric]].dropna().copy()
    is_dt = pd.api.types.is_datetime64_any_dtype(work[dim])
    if is_dt:
        work[dim] = work[dim].dt.strftime("%Y-%m-%d")
    else:
        work[dim] = work[dim].apply(lambda v: str(int(v)) if isinstance(v, (int, float)) and float(v).is_integer() else str(v))

    grouped = work.groupby(dim, sort=is_dt)[metric]
    if agg == "avg":
        res = grouped.mean()
        agg_word = "Average"
    elif agg == "max":
        res = grouped.max()
        agg_word = "Max"
    else:
        res = grouped.sum()
        agg_word = "Total"

    if chart_type == "line":
        if len(res) > 36:
            step = max(len(res) // 36, 1)
            res = res.iloc[::step].head(36)
    else:
        res = res.sort_values(ascending=False).head(12)

    return {
        "title": f"{agg_word} {metric_label} by {dim_label}",
        "type": chart_type,
        "series_label": metric_label,
        "data": {str(k): round(float(v), 2) for k, v in res.items()},
    }


def build_analysis_payload(
    cleaner: SelfHealingCleaner,
    df: pd.DataFrame,
    filename: str,
    domain_override: Optional[str] = None,
    source_csv_path: Optional[str] = None,
    is_live_url: bool = False
) -> dict:
    """Run semantic modeling, compute domain-specific KPIs/charts, and prepare session artifacts."""
    prune_old_sessions()
    session_id = str(uuid.uuid4())

    csv_path_for_model = source_csv_path if (source_csv_path and (source_csv_path.startswith("http://") or source_csv_path.startswith("https://"))) else "cleaned_data.csv"

    # 1. Domain Classification & Model Generation
    model_gen = PowerBIModelGenerator(
        df,
        csv_path=csv_path_for_model,
        domain=domain_override,
        audit_log=cleaner.audit_log
    )
    domain_key = model_gen.domain
    domain_info = model_gen.domain_info
    measures = model_gen.generate_dax_measures()
    m_script = model_gen.generate_power_query_m()

    # 2. Markdown Cheatsheet Content
    cheatsheet_lines = [
        f"# Auto-Generated Power BI Measures for `{model_gen.table_name}`",
        f"Domain: {domain_info.get('label', domain_key)} | Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "| Measure Name | Format | DAX Expression | Description |",
        "| :--- | :--- | :--- | :--- |",
    ]
    for m in measures:
        dax_escaped = m["dax"].replace("|", "\\|")
        cheatsheet_lines.append(f"| **{m['name']}** | `{m['format']}` | `{dax_escaped}` | {m['description']} |")
    cheatsheet_content = "\n".join(cheatsheet_lines)

    # 3. DAX File Content
    dax_lines = []
    for m in measures:
        dax_lines.append(f"// Measure: {m['name']} ({m['format']})")
        dax_lines.append(f"// {m['description']}")
        dax_lines.append(f"{m['dax']}\n")
    dax_file_content = "\n".join(dax_lines)

    # 4. Cleaned CSV in-memory (with DDE formula injection sanitization)
    csv_buffer = io.StringIO()
    sanitize_df_for_csv_export(df).to_csv(csv_buffer, index=False)
    cleaned_csv_str = csv_buffer.getvalue()

    # 5. Readme
    readme_content = f"""================================================================================
Power BI Starter Kit - Auto-Generated by AutoBI Studio
Domain: {domain_info.get('label', domain_key)}
Source File: {filename}
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
================================================================================

HOW TO USE IN POWER BI DESKTOP IN 60 SECONDS:

1. IMPORT THE CLEAN DATA:
   - Open Power BI Desktop.
   - Click "Get Data" -> "Text/CSV" -> Select 'cleaned_data.csv' from this folder.
   - Click "Load".

   (Alternative with Power Query M Script):
   - Click "Transform Data" -> "Home" -> "Advanced Editor".
   - Paste the code from 'LoadData.m' into the editor.

2. ADD PRODUCTION DAX MEASURES:
   - In Power BI Desktop, select the '{model_gen.table_name}' table.
   - Click "New Measure" on the Modeling ribbon.
   - Open 'dax_measures.dax' or 'POWER_BI_MEASURES_CHEATSHEET.md'.
   - Copy and paste your domain-specific DAX formulas.

3. AUDIT & TRACEABILITY:
   - Open 'audit_log.json' to review data healing actions.
"""

    # 6. Compute Domain-Specific KPIs & Interactive Schema
    display_labels = cleaner.audit_log.get("display_labels") or {}
    kpis, charts = _compute_domain_analytics(df, domain_key, display_labels)
    interactive_schema = _extract_interactive_schema(df, display_labels)

    # 7. Sample Table Records (up to 50 rows)
    preview_df = df.head(50).copy()
    for c in preview_df.columns:
        if pd.api.types.is_datetime64_any_dtype(preview_df[c]):
            preview_df[c] = preview_df[c].dt.strftime("%Y-%m-%d")

    records = preview_df.fillna("").to_dict(orient="records")

    # 8. Generate standalone Executive HTML dashboard
    anomalies_list = cleaner.audit_log.get("anomalies", [])
    anomaly_summary_dict = cleaner.audit_log.get("anomaly_summary", {"total_flags": 0, "critical_count": 0, "warning_count": 0, "info_count": 0, "has_critical": False})
    fx_dict = cleaner.audit_log.get("fx_normalization", {"is_multi_currency": False})
    pareto_dict = cleaner.audit_log.get("pareto_segmentation", {"is_segmented": False})

    dashboard_html = generate_html_dashboard(
        df,
        kpis,
        charts,
        domain_info,
        filename,
        anomalies=anomalies_list,
        anomaly_summary=anomaly_summary_dict,
        fx_info=fx_dict,
        pareto_info=pareto_dict,
        display_labels=display_labels
    )

    # 9. Generate Native Power BI Project (.pbip) artifacts
    pbip_files = generate_pbip_artifacts(
        df,
        model_gen.table_name,
        measures,
        m_script,
        anomalies=anomalies_list,
        fx_info=fx_dict
    )

    # Persist session with artifacts, dashboard preview and PBIP bundle
    sessions.set(session_id, {
        "created_at": datetime.now().isoformat(),
        "cleaned_csv": cleaned_csv_str,
        "dax_content": dax_file_content,
        "m_script": m_script,
        "cheatsheet": cheatsheet_content,
        "audit_log": sanitize_for_json(cleaner.audit_log),
        "readme": readme_content,
        "filename": filename,
        "dashboard_html": dashboard_html,
        "pbip_files": pbip_files,
        "is_live_url": is_live_url,
        "source_url": source_csv_path if is_live_url else None,
        "kpis": kpis,
        "charts": charts,
        "domain_key": domain_key,
        "domain_info": domain_info,
        "display_labels": display_labels,
        "interactive_schema": interactive_schema,
        "dax_measures": measures,
        "power_query_m": m_script,
        "table_columns": list(df.columns),
        "table_records": records,
    })

    payload = {
        "success": True,
        "session_id": session_id,
        "filename": filename,
        "is_live_url": is_live_url,
        "source_url": source_csv_path if is_live_url else None,
        "domain": {
            "key": domain_key,
            "label": domain_info.get("label", domain_key),
            "icon": domain_info.get("icon", "📊"),
            "table_name": model_gen.table_name,
            "confidence": domain_info.get("confidence", 90.0),
            "matched_signals": domain_info.get("matched_signals", []),
            "all_domains": [
                {"key": k, "label": v["label"], "icon": v["icon"]}
                for k, v in DOMAINS.items()
            ] + [{"key": "generic", "label": GENERIC_DOMAIN_INFO["label"], "icon": GENERIC_DOMAIN_INFO["icon"]}]
        },
        "kpis": kpis,
        "charts": charts,
        "interactive_schema": interactive_schema,
        "audit_log": cleaner.audit_log,
        "anomalies": anomalies_list,
        "anomaly_summary": anomaly_summary_dict,
        "unpivoted_matrix": cleaner.audit_log.get("unpivoted_matrix", {"is_unpivoted": False}),
        "fx_normalization": fx_dict,
        "pareto_segmentation": pareto_dict,
        "regional_preset": cleaner.audit_log.get("regional_preset"),
        "dax_measures": measures,
        "power_query_m": m_script,
        "sheet_info": {
            "selected_sheet": getattr(cleaner, "sheet_name", None),
            "available_sheets": getattr(cleaner, "available_sheets", []),
        },
        "table_columns": list(df.columns),
        "display_labels": display_labels,
        "table_records": records,
    }
    return sanitize_for_json(payload)


def _apply_ui_pref_cookies(res):
    """Persist explicit ?lang= and ?theme= query parameters in cookies."""
    explicit_lang = normalize_lang(request.args.get("lang", ""))
    if explicit_lang in SUPPORTED_LANGS:
        res.set_cookie(
            "autobi_lang",
            explicit_lang,
            max_age=365 * 86400,
            samesite="Lax",
            secure=_is_https_request(),
        )
    explicit_theme = normalize_theme(request.args.get("theme", ""))
    if explicit_theme in SUPPORTED_THEMES:
        res.set_cookie(
            "autobi_theme",
            explicit_theme,
            max_age=365 * 86400,
            samesite="Lax",
            secure=_is_https_request(),
        )
    return res


def _render_legal_page(doc_key: str):
    """Render a localized legal document (/privacy or /terms) and persist preferences."""
    lang = resolve_lang(request)
    theme = resolve_theme(request)
    doc = LEGAL_DOCUMENTS[doc_key].get(lang, LEGAL_DOCUMENTS[doc_key]["en"])
    ui = LEGAL_UI.get(lang, LEGAL_UI["en"])
    html_out = render_template(
        "legal.html",
        lang=lang,
        theme=theme,
        supported_langs=SUPPORTED_LANGS,
        legal_ui=ui,
        **doc,
    )
    return _apply_ui_pref_cookies(make_response(html_out))


@app.route("/")
def index():
    """Render the animated 3D Data Analytics & Engineering landing page."""
    if request.args.get("demo"):
        return redirect(url_for("studio", **request.args.to_dict()))
    lang = resolve_lang(request)
    theme = resolve_theme(request)
    res = make_response(render_template("landing.html", lang=lang, theme=theme))
    return _apply_ui_pref_cookies(res)


@app.route("/studio")
def studio():
    """Render the interactive AutoBI Studio workspace."""
    lang = resolve_lang(request)
    theme = resolve_theme(request)
    res = make_response(render_template("index.html", lang=lang, theme=theme))
    return _apply_ui_pref_cookies(res)


@app.route("/privacy")
def privacy_policy():
    """Render the localized AutoBI Studio Privacy Policy page."""
    return _render_legal_page("privacy")


@app.route("/terms")
def terms_of_service():
    """Render the localized AutoBI Studio Terms of Service page."""
    return _render_legal_page("terms")


@app.route("/favicon.ico")
def favicon():
    """Serve the multi-resolution ICO favicon at the root path."""
    return send_from_directory(
        os.path.join(app.root_path, "static", "img"),
        "favicon.ico",
        mimetype="image/vnd.microsoft.icon",
    )


@app.route("/apple-touch-icon.png")
def apple_touch_icon():
    """Serve the iOS/Safari touch icon at the root path."""
    return send_from_directory(
        os.path.join(app.root_path, "static", "img"),
        "apple-touch-icon.png",
        mimetype="image/png",
    )


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _attach_auth_cookie(res, email: str):
    signed_token = sign_auth_token(email)
    res.set_cookie(
        "autobi_user",
        signed_token,
        max_age=30 * 86400,
        httponly=True,
        samesite="Lax",
        secure=_is_https_request(),
    )
    return res


@app.route("/api/auth/status")
def auth_status():
    user = get_current_user()
    return jsonify({
        "auth_enabled": AUTH_ENABLED,
        "authenticated": user is not None,
        "user": user
    })


@app.route("/api/auth/register", methods=["POST"])
def auth_register():
    client_ip = get_client_ip()
    if not check_login_rate_limit(client_ip):
        return jsonify({
            "success": False,
            "error_code": "err_rate_limit",
            "error": "Too many failed attempts. Please wait 15 minutes before trying again."
        }), 429

    data = request.get_json(silent=True) or {}
    email = normalize_email(data.get("email") or "")
    password = (data.get("password") or data.get("passcode") or "").strip()
    full_name = (data.get("full_name") or "").strip()

    if not email:
        return jsonify({"success": False, "error_code": "err_email_required", "error": "Please enter your work email."}), 400
    if not _EMAIL_RE.match(email):
        return jsonify({"success": False, "error_code": "err_email_invalid", "error": "Please enter a valid email address."}), 400
    if len(password) < 8:
        return jsonify({"success": False, "error_code": "err_password_min", "error": "Password must be at least 8 characters."}), 400

    created, result = users_vault.create_user(email, password, full_name=full_name)
    if not created:
        return jsonify({
            "success": False,
            "error_code": "auth_email_exists",
            "error": "An account with this email already exists. Please sign in instead."
        }), 409

    reset_failed_logins(client_ip)
    res = jsonify({
        "success": True,
        "message": "Account created and workspace authenticated.",
        "user": email,
        "full_name": result.get("full_name", "")
    })
    return _attach_auth_cookie(res, email)


@app.route("/api/auth/login", methods=["POST"])
def auth_login():
    client_ip = get_client_ip()
    if not check_login_rate_limit(client_ip):
        return jsonify({
            "success": False,
            "error_code": "err_rate_limit",
            "error": "Too many failed login attempts. Please wait 15 minutes before trying again."
        }), 429

    data = request.get_json(silent=True) or {}
    has_email_field = "email" in data
    raw_email = (data.get("email") or "").strip()
    email = normalize_email(raw_email)
    secret = (data.get("password") or data.get("passcode") or "").strip()

    if has_email_field or "password" in data:
        if not email:
            return jsonify({"success": False, "error_code": "err_email_required", "error": "Please enter your work email."}), 400
        if not _EMAIL_RE.match(email):
            return jsonify({"success": False, "error_code": "err_email_invalid", "error": "Please enter a valid email address."}), 400

    if not secret:
        record_failed_login(client_ip)
        return jsonify({"success": False, "error_code": "err_password_required", "error": "Please enter your password."}), 400

    if email:
        auth_state, profile = users_vault.authenticate_user(email, secret)
        if auth_state == "ok":
            reset_failed_logins(client_ip)
            res = jsonify({
                "success": True,
                "message": "Workspace successfully authenticated.",
                "user": email,
                "full_name": (profile or {}).get("full_name", "")
            })
            return _attach_auth_cookie(res, email)
        if auth_state == "invalid_password":
            record_failed_login(client_ip)
            return jsonify({
                "success": False,
                "error_code": "err_invalid_credentials",
                "error": "Invalid email or password."
            }), 401
        # Unregistered email: allow legacy workspace passcode ONLY if it explicitly matches WORKSPACE_PASSCODE
        if hmac.compare_digest(secret, WORKSPACE_PASSCODE):
            reset_failed_logins(client_ip)
            res = jsonify({
                "success": True,
                "message": "Workspace successfully authenticated.",
                "user": email
            })
            return _attach_auth_cookie(res, email)
        record_failed_login(client_ip)
        return jsonify({
            "success": False,
            "error_code": "err_account_or_password",
            "error": "Account not found or invalid password. New users can switch to Create Account."
        }), 401

    # API passcode-only compatibility (no email supplied)
    if not hmac.compare_digest(secret, WORKSPACE_PASSCODE):
        record_failed_login(client_ip)
        return jsonify({"success": False, "error_code": "err_invalid_credentials", "error": "Invalid workspace access passcode."}), 401

    reset_failed_logins(client_ip)
    res = jsonify({
        "success": True,
        "message": "Workspace successfully authenticated.",
        "user": "workspace-api@autobi.local"
    })
    return _attach_auth_cookie(res, "workspace-api@autobi.local")


@app.route("/api/auth/logout", methods=["POST"])
def auth_logout():
    res = jsonify({"success": True, "message": "Logged out of workspace."})
    res.set_cookie(
        "autobi_user",
        "",
        max_age=0,
        httponly=True,
        samesite="Lax",
        secure=_is_https_request(),
    )
    return res


@app.route("/api/upload", methods=["POST"])
@require_auth
def upload_file():
    if "file" not in request.files:
        return jsonify({"success": False, "error": "No file uploaded"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"success": False, "error": "Empty filename"}), 400

    domain_override = request.form.get("domain") or None
    sheet_override = request.form.get("sheet") or None

    filename = file.filename
    lower_ext = os.path.splitext(filename)[1].lower()
    if lower_ext not in [".xlsx", ".xls", ".csv"]:
        return jsonify({"success": False, "error": f"Unsupported format '{lower_ext}'. Please upload an Excel or CSV file."}), 400

    try:
        file_bytes = file.read()
        file_buffer = io.BytesIO(file_bytes)

        cleaner = SelfHealingCleaner(file_buffer, filename=filename, sheet_name=sheet_override)
        df_clean = cleaner.clean()
        result = build_analysis_payload(cleaner, df_clean, filename, domain_override=domain_override)
        return jsonify(result)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/ingest-url", methods=["POST"])
@require_auth
def ingest_google_sheet_url():
    """Ingest a live Google Sheets URL, clean it, and build the Power BI model with live refresh."""
    data = request.get_json(silent=True) or {}
    url = data.get("url", "").strip()
    domain_override = data.get("domain")

    if not url:
        return jsonify({"success": False, "error": "Please provide a valid Google Sheets URL."}), 400

    try:
        file_buffer, filename, csv_export_url = fetch_google_sheets_csv(url)
        cleaner = SelfHealingCleaner(file_buffer, filename=filename)
        df_clean = cleaner.clean()

        result = build_analysis_payload(
            cleaner,
            df_clean,
            filename,
            domain_override=domain_override,
            source_csv_path=csv_export_url,
            is_live_url=True
        )
        return jsonify(result)
    except PermissionError as e:
        return jsonify({"success": False, "error": str(e)}), 403
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        return jsonify({"success": False, "error": f"Failed to ingest Google Sheet: {str(e)}"}), 500


@app.route("/api/ingest-sql", methods=["POST"])
@require_auth
def ingest_readonly_sql():
    """Execute a validated read-only SELECT query on PostgreSQL/MySQL and build the BI workspace."""
    data = request.get_json(silent=True) or {}
    uri = (data.get("uri") or "").strip()
    query = (data.get("query") or "").strip()
    domain_override = data.get("domain")

    if not uri or not query:
        return jsonify({"success": False, "error": "Please provide both a database connection URI and a SELECT query."}), 400

    try:
        df_raw, masked_source = fetch_readonly_sql_df(uri, query)
        if df_raw.empty:
            return jsonify({"success": False, "error": "SQL query returned 0 rows."}), 400
        cleaner = SelfHealingCleaner(df_raw, filename="sql_query_extract.xlsx")
        df_clean = cleaner.clean()
        result = build_analysis_payload(cleaner, df_clean, masked_source, domain_override=domain_override)
        return jsonify(result)
    except ValueError as ve:
        return jsonify({"success": False, "error": str(ve)}), 400
    except RuntimeError as re_err:
        return jsonify({"success": False, "error": str(re_err)}), 500
    except Exception as e:
        return jsonify({"success": False, "error": f"SQL ingestion failed: {str(e)}"}), 502


@app.route("/api/sheets", methods=["POST"])
@require_auth
def inspect_file_sheets():
    """Returns sheet names in an Excel file so users can choose which tab to analyze."""
    if "file" not in request.files:
        return jsonify({"success": False, "error": "No file uploaded"}), 400
    file = request.files["file"]
    if not file.filename:
        return jsonify({"success": False, "error": "Empty filename"}), 400

    filename = file.filename
    try:
        file_bytes = file.read()
        sheets = SelfHealingCleaner.inspect_sheets(io.BytesIO(file_bytes), filename=filename)
        return jsonify({
            "success": True,
            "filename": filename,
            "sheets": sheets,
            "has_multiple": len(sheets) > 1
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/sample", methods=["POST"])
@require_auth
def run_sample():
    # Support specifying domain preset in JSON or query param
    req_json = request.get_json(silent=True) or {}
    domain = req_json.get("domain") or request.args.get("domain") or "sales"

    try:
        df_raw = generate_synthetic_demo_df(domain)
        # Pass through cleaner to run self-healing and trailer row elimination
        cleaner = SelfHealingCleaner(df_raw, filename=f"demo_{domain}_dataset.xlsx")
        df_clean = cleaner.clean()
        effective_override = None if domain in ("crm", "uzum") else domain
        result = build_analysis_payload(cleaner, df_clean, f"demo_{domain}_dataset.xlsx", domain_override=effective_override)
        return jsonify(result)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


_PUBLIC_DEMO_CACHE: dict[str, dict] = {}
_PUBLIC_DEMO_DOMAINS = {"sales", "marketing", "hr", "inventory", "finance", "generic"}


@app.route("/api/public-demo/<domain>", methods=["GET"])
def public_demo_preview(domain: str):
    """Read-only zero-login sample preview endpoint for landing page interactive showcase."""
    dom = (domain or "").strip().lower()
    if dom not in _PUBLIC_DEMO_DOMAINS:
        return jsonify({"success": False, "error": "Unsupported demo domain."}), 400

    cached = _PUBLIC_DEMO_CACHE.get(dom)
    if cached and (time.time() - cached.get("_ts", 0)) < 1800:
        return jsonify({k: v for k, v in cached.items() if k != "_ts"})

    try:
        df_raw = generate_synthetic_demo_df(dom)
        cleaner = SelfHealingCleaner(df_raw, filename=f"demo_{dom}_dataset.xlsx")
        df_clean = cleaner.clean()
        payload = build_analysis_payload(cleaner, df_clean, f"demo_{dom}_dataset.xlsx", domain_override=dom)
        # Purge ephemeral synthetic session immediately so public demos leave zero session footprint
        if payload.get("session_id"):
            sessions.delete(payload["session_id"])

        audit = payload.get("audit_log") or {}
        anom = payload.get("anomaly_summary") or {}
        fx = payload.get("fx_normalization") or {}
        unpiv = payload.get("unpivoted_matrix") or {}

        light_payload = sanitize_for_json({
            "success": True,
            "domain": payload.get("domain"),
            "kpis": (payload.get("kpis") or [])[:4],
            "charts": payload.get("charts") or {},
            "dax_measures": (payload.get("dax_measures") or [])[:3],
            "display_labels": payload.get("display_labels") or {},
            "table_columns": (payload.get("table_columns") or [])[:6],
            "table_records": (payload.get("table_records") or [])[:5],
            "audit_summary": {
                "raw_rows": audit.get("raw_row_count", len(df_clean)),
                "cleaned_rows": audit.get("cleaned_row_count", len(df_clean)),
                "dropped_rows": len(audit.get("dropped_rows") or []),
                "flags_count": anom.get("total_flags", 0),
                "critical_count": anom.get("critical_count", 0),
                "fx_active": bool(fx.get("is_multi_currency")),
                "unpivoted": bool(unpiv.get("is_unpivoted")),
            },
        })
        light_payload["_ts"] = time.time()
        _PUBLIC_DEMO_CACHE[dom] = light_payload
        return jsonify({k: v for k, v in light_payload.items() if k != "_ts"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/session/<session_id>/query", methods=["POST"])
@require_auth
def query_session_analytics(session_id: str):
    """Apply top-bar slicers, date ranges, and custom Chart Builder overrides on full session data."""
    sess = sessions.get(session_id)
    if not sess:
        return jsonify({"success": False, "error": "Session expired or not found."}), 404

    data = request.get_json(silent=True) or {}
    filters = data.get("filters") or {}
    date_from = (data.get("date_from") or "").strip()
    date_to = (data.get("date_to") or "").strip()
    chart_overrides = data.get("chart_overrides") or {}
    save_overrides = bool(data.get("save", True))

    try:
        full_df = pd.read_csv(io.StringIO(sess["cleaned_csv"]))
    except Exception as e:
        return jsonify({"success": False, "error": f"Unable to reload session dataset: {e}"}), 500

    schema = sess.get("interactive_schema") or {}
    date_info = schema.get("date_col")
    date_key = date_info.get("key") if isinstance(date_info, dict) else None
    if date_key and date_key in full_df.columns:
        full_df[date_key] = pd.to_datetime(full_df[date_key], errors="coerce")

    filtered_df = full_df.copy()

    if isinstance(filters, dict):
        for col_key, val in filters.items():
            if val is None or val == "" or val == "__all__":
                continue
            if col_key not in filtered_df.columns:
                return jsonify({"success": False, "error": f"Unknown filter column '{col_key}'."}), 400
            filtered_df = filtered_df[filtered_df[col_key].astype(str) == str(val)]

    if date_key and date_key in filtered_df.columns and (date_from or date_to):
        if date_from:
            dt_from = pd.to_datetime(date_from, errors="coerce")
            if pd.notna(dt_from):
                filtered_df = filtered_df[filtered_df[date_key] >= dt_from]
        if date_to:
            dt_to = pd.to_datetime(date_to, errors="coerce")
            if pd.notna(dt_to):
                filtered_df = filtered_df[filtered_df[date_key] <= dt_to]

    domain_key = sess.get("domain_key", "generic")
    display_labels = sess.get("display_labels") or (sess.get("audit_log") or {}).get("display_labels") or {}
    kpis, charts = _compute_domain_analytics(filtered_df, domain_key, display_labels)

    if isinstance(chart_overrides, dict):
        for slot in ("chart1", "chart2"):
            override_spec = chart_overrides.get(slot)
            if isinstance(override_spec, dict) and override_spec.get("dim"):
                try:
                    charts[slot] = _build_custom_chart(filtered_df, override_spec, display_labels)
                except ValueError as ve:
                    return jsonify({"success": False, "error": str(ve)}), 400

    preview_df = filtered_df.head(50).copy()
    for c in preview_df.columns:
        if pd.api.types.is_datetime64_any_dtype(preview_df[c]):
            preview_df[c] = preview_df[c].dt.strftime("%Y-%m-%d")
    records = preview_df.fillna("").to_dict(orient="records")

    if save_overrides and isinstance(chart_overrides, dict):
        sess["chart_overrides"] = chart_overrides
        sess["charts"] = charts
        sess["kpis"] = kpis
        try:
            audit_log = sess.get("audit_log") or {}
            sess["dashboard_html"] = generate_html_dashboard(
                filtered_df if len(filtered_df) > 0 else full_df,
                kpis,
                charts,
                sess.get("domain_info") or {"label": domain_key, "icon": "📊"},
                sess.get("filename", "dataset.csv"),
                anomalies=audit_log.get("anomalies", []),
                anomaly_summary=audit_log.get("anomaly_summary", {}),
                fx_info=audit_log.get("fx_normalization", {}),
                pareto_info=audit_log.get("pareto_segmentation", {}),
                display_labels=display_labels,
            )
        except Exception:
            pass
        sessions.set(session_id, sess)

    return jsonify(sanitize_for_json({
        "success": True,
        "kpis": kpis,
        "charts": charts,
        "row_count": int(len(filtered_df)),
        "total_row_count": int(len(full_df)),
        "table_records": records,
        "chart_overrides": chart_overrides,
    }))


def _build_session_snapshot_dict(sess: dict) -> dict:
    """Extract full session artifact & UI state into a storable report snapshot dict."""
    audit_log = sess.get("audit_log") or {}
    return sanitize_for_json({
        "cleaned_csv": sess.get("cleaned_csv", ""),
        "dax_content": sess.get("dax_content", ""),
        "m_script": sess.get("m_script", ""),
        "power_query_m": sess.get("power_query_m") or sess.get("m_script", ""),
        "cheatsheet": sess.get("cheatsheet", ""),
        "audit_log": audit_log,
        "readme": sess.get("readme", ""),
        "filename": sess.get("filename", "report.xlsx"),
        "dashboard_html": sess.get("dashboard_html", ""),
        "pbip_files": sess.get("pbip_files", {}),
        "is_live_url": bool(sess.get("is_live_url")),
        "source_url": sess.get("source_url"),
        "kpis": sess.get("kpis", []),
        "charts": sess.get("charts", {}),
        "chart_overrides": sess.get("chart_overrides", {}),
        "domain_key": sess.get("domain_key", "generic"),
        "domain_info": sess.get("domain_info", {}),
        "display_labels": sess.get("display_labels") or audit_log.get("display_labels") or {},
        "interactive_schema": sess.get("interactive_schema") or {},
        "dax_measures": sess.get("dax_measures", []),
        "table_columns": sess.get("table_columns", []),
        "table_records": sess.get("table_records", []),
    })


def _snapshot_to_studio_response(snap: dict, report_meta: Optional[dict] = None, history: Optional[list] = None) -> dict:
    """Hydrate an interactive session from a saved snapshot and return a Studio-compatible JSON payload."""
    new_session_id = str(uuid.uuid4())
    sess_obj = dict(snap)
    sess_obj["created_at"] = datetime.now().isoformat()
    sessions.set(new_session_id, sess_obj)

    domain_key = snap.get("domain_key", "generic")
    domain_info = snap.get("domain_info") or {}
    audit_log = snap.get("audit_log") or {}

    return sanitize_for_json({
        "success": True,
        "session_id": new_session_id,
        "filename": snap.get("filename", "saved_report.xlsx"),
        "is_live_url": bool(snap.get("is_live_url")),
        "source_url": snap.get("source_url"),
        "domain": {
            "key": domain_key,
            "label": domain_info.get("label", domain_key),
            "icon": domain_info.get("icon", "📊"),
            "table_name": domain_info.get("table_name", "DataTable"),
            "confidence": domain_info.get("confidence", 90.0),
            "matched_signals": domain_info.get("matched_signals", []),
            "all_domains": [
                {"key": k, "label": v["label"], "icon": v["icon"]}
                for k, v in DOMAINS.items()
            ] + [{"key": "generic", "label": GENERIC_DOMAIN_INFO["label"], "icon": GENERIC_DOMAIN_INFO["icon"]}],
        },
        "kpis": snap.get("kpis", []),
        "charts": snap.get("charts", {}),
        "chart_overrides": snap.get("chart_overrides", {}),
        "interactive_schema": snap.get("interactive_schema", {}),
        "audit_log": audit_log,
        "anomalies": audit_log.get("anomalies", []),
        "anomaly_summary": audit_log.get("anomaly_summary", {"total_flags": 0, "critical_count": 0, "warning_count": 0, "info_count": 0, "has_critical": False}),
        "unpivoted_matrix": audit_log.get("unpivoted_matrix", {"is_unpivoted": False}),
        "fx_normalization": audit_log.get("fx_normalization", {"is_multi_currency": False}),
        "pareto_segmentation": audit_log.get("pareto_segmentation", {"is_segmented": False}),
        "dax_measures": snap.get("dax_measures", []),
        "power_query_m": snap.get("power_query_m") or snap.get("m_script", ""),
        "table_columns": snap.get("table_columns", []),
        "display_labels": snap.get("display_labels") or audit_log.get("display_labels") or {},
        "table_records": snap.get("table_records", []),
        "report_meta": report_meta,
        "snapshot_history": history or [],
    })


@app.route("/api/reports", methods=["GET"])
@require_auth
def list_saved_reports():
    """List encrypted saved reports belonging to the current authenticated user."""
    user = get_current_user()
    items = reports_store.list_reports(user)
    return jsonify(sanitize_for_json({"success": True, "reports": items}))


@app.route("/api/reports", methods=["POST"])
@require_auth
def save_current_report():
    """Opt-in: Save an active analysis session into the encrypted My Reports gallery."""
    user = get_current_user()
    data = request.get_json(silent=True) or {}
    session_id = (data.get("session_id") or "").strip()
    if not session_id:
        return jsonify({"success": False, "error": "Missing session_id."}), 400
    sess = sessions.get(session_id)
    if not sess:
        return jsonify({"success": False, "error": "Session expired or not found."}), 404

    snap = _build_session_snapshot_dict(sess)
    title = (data.get("title") or sess.get("filename") or "Saved Report").strip()
    period_label = (data.get("period_label") or "").strip() or None
    domain_key = snap.get("domain_key", "generic")
    domain_info = dict(snap.get("domain_info") or {})
    domain_info.setdefault("key", domain_key)

    created = reports_store.create_report(
        owner_email=user,
        title=title,
        snapshot_data=snap,
        domain_info=domain_info,
        source_url=sess.get("source_url"),
        is_live_url=bool(sess.get("is_live_url")),
        db_config=sess.get("db_config"),
        period_label=period_label,
    )
    return jsonify(sanitize_for_json({"success": True, "report": created})), 201


@app.route("/api/reports/<report_id>", methods=["GET"])
@require_auth
def open_saved_report(report_id: str):
    """Load an encrypted saved report into an active Studio session."""
    user = get_current_user()
    rep = reports_store.get_report(user, report_id)
    if not rep:
        return jsonify({"success": False, "error": "Report not found or access denied."}), 404

    resp = _snapshot_to_studio_response(
        rep["latest_payload"],
        report_meta=rep["meta"],
        history=rep["history"],
    )
    return jsonify(resp)


@app.route("/api/reports/<report_id>/refresh", methods=["POST"])
@require_auth
def refresh_saved_report(report_id: str):
    """Upload a new file (or re-pull linked source) to append a new snapshot and compute MoM deltas."""
    user = get_current_user()
    existing = reports_store.get_report(user, report_id)
    if not existing:
        return jsonify({"success": False, "error": "Report not found or access denied."}), 404

    meta = existing.get("meta") or {}
    prev_snap = existing.get("latest_payload") or {}
    domain_override = (meta.get("domain") or {}).get("key") or prev_snap.get("domain_key")
    period_label = None
    source_url = meta.get("source_url")
    is_live_url = bool(meta.get("is_live_url"))

    try:
        if "file" in request.files and request.files["file"].filename:
            f = request.files["file"]
            period_label = (request.form.get("period_label") or "").strip() or None
            filename = f.filename
            cleaner = SelfHealingCleaner(io.BytesIO(f.read()), filename=filename)
            df_clean = cleaner.clean()
            payload = build_analysis_payload(cleaner, df_clean, filename, domain_override=domain_override)
            is_live_url = False
            source_url = None
        else:
            req_json = request.get_json(silent=True) or {}
            period_label = (req_json.get("period_label") or "").strip() or None
            target_url = (req_json.get("url") or source_url or "").strip()
            if not target_url:
                return jsonify({"success": False, "error": "Please upload a file or provide a live Google Sheets URL."}), 400
            file_buffer, filename, csv_export_url = fetch_google_sheets_csv(target_url)
            cleaner = SelfHealingCleaner(file_buffer, filename=filename)
            df_clean = cleaner.clean()
            payload = build_analysis_payload(
                cleaner,
                df_clean,
                filename,
                domain_override=domain_override,
                source_csv_path=csv_export_url,
                is_live_url=True,
            )
            is_live_url = True
            source_url = csv_export_url

        new_sess_id = payload["session_id"]
        new_sess = sessions.get(new_sess_id) or {}
        # Carry forward custom chart overrides onto fresh snapshot if compatible
        saved_overrides = prev_snap.get("chart_overrides") or {}
        if saved_overrides:
            try:
                tmp_df = pd.read_csv(io.StringIO(new_sess["cleaned_csv"]))
                disp = new_sess.get("display_labels") or {}
                for slot in ("chart1", "chart2"):
                    if slot in saved_overrides and isinstance(saved_overrides[slot], dict):
                        new_sess["charts"][slot] = _build_custom_chart(tmp_df, saved_overrides[slot], disp)
                new_sess["chart_overrides"] = saved_overrides
                payload["charts"] = new_sess["charts"]
                payload["chart_overrides"] = saved_overrides
            except Exception:
                pass

        snap_bundle = _build_session_snapshot_dict(new_sess)
        updated_info = reports_store.add_snapshot(
            owner_email=user,
            report_id=report_id,
            new_payload=snap_bundle,
            period_label=period_label,
            domain_info=payload.get("domain"),
        )
        # Update hydrated session KPIs with computed MoM deltas and delete extra temp session
        payload["kpis"] = updated_info["kpis"]
        new_sess["kpis"] = updated_info["kpis"]
        sessions.set(new_sess_id, new_sess)

        rep_after = reports_store.get_report(user, report_id)
        payload["report_meta"] = rep_after["meta"] if rep_after else meta
        payload["snapshot_history"] = rep_after["history"] if rep_after else []
        return jsonify(sanitize_for_json(payload))
    except PermissionError as e:
        return jsonify({"success": False, "error": str(e)}), 403
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        return jsonify({"success": False, "error": f"Failed to refresh report: {str(e)}"}), 500


@app.route("/api/reports/<report_id>", methods=["DELETE"])
@require_auth
def delete_saved_report(report_id: str):
    """Permanently delete a saved report and all its encrypted snapshots."""
    user = get_current_user()
    ok = reports_store.delete_report(user, report_id)
    if not ok:
        return jsonify({"success": False, "error": "Report not found or access denied."}), 404
    scheduler_service.delete_schedule(user, report_id)
    return jsonify({"success": True, "message": "Saved report permanently deleted."})


def _execute_scheduled_refresh_job(owner_email: str, report_id: str) -> dict:
    """Refresh a saved report from its linked source (if live URL) and return session_data + anomaly_summary."""
    rep = reports_store.get_report(owner_email, report_id)
    if not rep:
        raise ValueError("Scheduled report not found.")
    meta = rep.get("meta") or {}
    snap = rep.get("latest_payload") or {}
    source_url = meta.get("source_url")

    if source_url:
        file_buffer, filename, csv_export_url = fetch_google_sheets_csv(source_url)
        cleaner = SelfHealingCleaner(file_buffer, filename=filename)
        df_clean = cleaner.clean()
        domain_override = (meta.get("domain") or {}).get("key") or snap.get("domain_key")
        payload = build_analysis_payload(
            cleaner,
            df_clean,
            filename,
            domain_override=domain_override,
            source_csv_path=csv_export_url,
            is_live_url=True,
        )
        new_sess = sessions.get(payload["session_id"]) or {}
        snap_bundle = _build_session_snapshot_dict(new_sess)
        updated_info = reports_store.add_snapshot(
            owner_email=owner_email,
            report_id=report_id,
            new_payload=snap_bundle,
            domain_info=payload.get("domain"),
        )
        new_sess["kpis"] = updated_info["kpis"]
        sessions.delete(payload["session_id"])
        return {
            "session_data": new_sess,
            "anomaly_summary": (new_sess.get("audit_log") or {}).get("anomaly_summary", {}),
            "snapshot_info": updated_info,
        }

    # File-based report test-run: reuse latest encrypted snapshot safely
    audit_log = snap.get("audit_log") or {}
    return {
        "session_data": snap,
        "anomaly_summary": audit_log.get("anomaly_summary", {}),
        "snapshot_info": {"report_id": report_id},
    }


def _dispatch_telegram_job(session_data: dict, targets=None) -> dict:
    from telegram_client import dispatch_executive_report
    return dispatch_executive_report(session_data, targets=targets)


@app.route("/api/reports/<report_id>/schedule", methods=["GET"])
@require_auth
def get_report_schedule(report_id: str):
    user = get_current_user()
    if not reports_store.get_report(user, report_id):
        return jsonify({"success": False, "error": "Report not found or access denied."}), 404
    sched = scheduler_service.get_schedule(user, report_id)
    return jsonify(sanitize_for_json({"success": True, "schedule": sched}))


@app.route("/api/reports/<report_id>/schedule", methods=["POST"])
@require_auth
def upsert_report_schedule(report_id: str):
    user = get_current_user()
    if not reports_store.get_report(user, report_id):
        return jsonify({"success": False, "error": "Report not found or access denied."}), 404
    data = request.get_json(silent=True) or {}
    cadence = (data.get("cadence") or "weekly_mon").strip()
    targets = data.get("targets") or []
    if isinstance(targets, str):
        targets = [t.strip() for t in re.split(r"[,;\n\r]+", targets) if t.strip()]
    alert_only = bool(data.get("alert_only_on_anomalies", False))
    hour_utc = int(data.get("hour_utc", 4))
    enabled = bool(data.get("enabled", True))

    try:
        sched = scheduler_service.upsert_schedule(
            owner_email=user,
            report_id=report_id,
            cadence=cadence,
            targets=targets,
            alert_only_on_anomalies=alert_only,
            hour_utc=hour_utc,
            enabled=enabled,
        )
        return jsonify(sanitize_for_json({"success": True, "schedule": sched}))
    except ValueError as ve:
        return jsonify({"success": False, "error": str(ve)}), 400


@app.route("/api/reports/<report_id>/schedule", methods=["DELETE"])
@require_auth
def delete_report_schedule(report_id: str):
    user = get_current_user()
    if not reports_store.get_report(user, report_id):
        return jsonify({"success": False, "error": "Report not found or access denied."}), 404
    removed = scheduler_service.delete_schedule(user, report_id)
    return jsonify({"success": True, "removed": removed})


@app.route("/api/reports/<report_id>/schedule/test-run", methods=["POST"])
@require_auth
def test_run_report_schedule(report_id: str):
    user = get_current_user()
    if not reports_store.get_report(user, report_id):
        return jsonify({"success": False, "error": "Report not found or access denied."}), 404
    data = request.get_json(silent=True) or {}
    targets = data.get("targets")
    if isinstance(targets, str):
        targets = [t.strip() for t in re.split(r"[,;\n\r]+", targets) if t.strip()]
    try:
        res = scheduler_service.run_single(
            owner_email=user,
            report_id=report_id,
            runner_fn=_execute_scheduled_refresh_job,
            dispatch_fn=_dispatch_telegram_job,
            override_targets=targets,
        )
        return jsonify(sanitize_for_json({"success": True, "result": res}))
    except ValueError as ve:
        return jsonify({"success": False, "error": str(ve)}), 400
    except Exception as e:
        return jsonify({"success": False, "error": f"Scheduled test run failed: {str(e)}"}), 502


@app.route("/api/preview/<session_id>")
def preview_dashboard(session_id: str):
    """Serve standalone interactive HTML executive dashboard (view-only shared link)."""
    session = sessions.get(session_id)
    if not session or not session.get("dashboard_html"):
        return jsonify({"error": "Session expired or preview unavailable. Please re-run analysis."}), 404
    return session["dashboard_html"], 200, {"Content-Type": "text/html; charset=utf-8"}


@app.route("/api/telegram/config", methods=["GET"])
@require_auth
def telegram_config():
    """Returns whether Telegram Bot credentials are configured."""
    from telegram_client import get_default_telegram_config, get_bot_username, poll_and_sync_updates
    token, chat_id = get_default_telegram_config()
    username = get_bot_username() if token else None

    # Sync any recent updates
    if token:
        try:
            poll_and_sync_updates()
        except Exception:
            pass

    return jsonify({
        "configured": bool(token and chat_id),
        "has_token": bool(token),
        "bot_username": username,
        "chat_id_configured": bool(chat_id),
        "default_chat_id": (chat_id[:4] + "..." + chat_id[-4:]) if chat_id and len(chat_id) > 8 else chat_id,
        "recent_subscribers": []
    })


@app.route("/api/telegram/poll-connection", methods=["GET"])
@require_auth
def telegram_poll_connection():
    """Poll Telegram Bot API for incoming /start messages with a matching connection code."""
    from telegram_client import poll_and_sync_updates, get_subscriber_by_param
    code = request.args.get("code", "").strip()
    if not code:
        return jsonify({"connected": False, "error": "Connection code required."}), 400

    try:
        poll_and_sync_updates()
    except Exception:
        pass

    sub = get_subscriber_by_param(code)
    if sub:
        uname = sub.get("username")
        fn = sub.get("first_name")
        label = f"{fn} (@{uname})" if (fn and uname) else (f"@{uname}" if uname else (fn or f"Chat {sub['chat_id']}"))
        return jsonify({
            "connected": True,
            "chat_id": sub["chat_id"],
            "username": uname,
            "first_name": fn,
            "label": label
        })

    return jsonify({"connected": False})


@app.route("/api/telegram/dispatch", methods=["POST"])
@require_auth
def telegram_dispatch():
    """Dispatch executive digest and interactive HTML report directly to Telegram (single or multiple targets)."""
    data = request.get_json(silent=True) or {}
    session_id = data.get("session_id")
    if not session_id:
        return jsonify({"error": "Missing session_id."}), 400

    session_data = sessions.get(session_id)
    if not session_data:
        return jsonify({"error": "Session expired or invalid. Please re-run analysis."}), 404

    chat_id = data.get("chat_id")
    targets = data.get("targets")
    bot_token = data.get("bot_token")

    try:
        from telegram_client import dispatch_executive_report
        result = dispatch_executive_report(session_data, chat_id=chat_id, targets=targets, bot_token=bot_token)
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Telegram dispatch failed: {str(e)}"}), 502


@app.route("/api/purge/<session_id>", methods=["POST", "DELETE"])
@require_auth
def purge_session(session_id: str):
    """Explicit data privacy purge: permanently wipes session from server RAM and disk."""
    success = sessions.delete(session_id)
    return jsonify({
        "success": success,
        "message": "Session and all associated data permanently purged from server memory and disk storage."
    })


@app.route("/api/download/<session_id>")
@require_auth
def download_pack(session_id: str):
    session = sessions.get(session_id)
    if not session:
        return jsonify({"error": "Session expired or invalid. Please re-run the analysis."}), 404

    quicklaunch_bat = """@echo off
echo ===============================================================================
echo AutoBI - Quick Launch Power BI Starter Kit
echo ===============================================================================
echo.
echo 1. Opening Offline Executive Dashboard Preview in browser...
start "" "Executive_Dashboard_Preview.html"
echo 2. Opening Measures Cheatsheet...
start "" "POWER_BI_MEASURES_CHEATSHEET.md"
echo.
echo 3. Launching Power BI Project directly...
start "" "AutoBI_Project.pbip" 2>nul || start "" "C:\\Program Files\\Microsoft Power BI Desktop\\bin\\PBIDesktop.exe" "AutoBI_Project.pbip" 2>nul || echo [Notice] Power BI Desktop was not found at standard path. Please double-click 'AutoBI_Project.pbip' directly.
echo.
echo Done! All measures, tables, and column types are pre-loaded in AutoBI_Project.pbip.
pause
"""

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("cleaned_data.csv", session["cleaned_csv"])
        zf.writestr("LoadData.m", session["m_script"])
        zf.writestr("dax_measures.dax", session["dax_content"])
        zf.writestr("POWER_BI_MEASURES_CHEATSHEET.md", session["cheatsheet"])
        zf.writestr("audit_log.json", json.dumps(session["audit_log"], indent=2, default=str))
        zf.writestr("Executive_Dashboard_Preview.html", session.get("dashboard_html", ""))
        zf.writestr("QuickLaunch_PowerBI.bat", quicklaunch_bat)
        zf.writestr("README.txt", session["readme"])

        # Include native Power BI Project (.pbip) bundle
        pbip_files = session.get("pbip_files", {})
        for rel_path, file_content in pbip_files.items():
            zf.writestr(rel_path, file_content)

    zip_buffer.seek(0)
    download_filename = f"powerbi_{session.get('filename', 'pack').split('.')[0]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
    return send_file(
        zip_buffer,
        mimetype="application/zip",
        as_attachment=True,
        download_name=download_filename
    )


@app.after_request
def add_security_headers(response):
    """Add defensive security headers to all HTTP responses."""
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
        "font-src 'self' https://fonts.gstatic.com https://cdnjs.cloudflare.com; "
        "img-src 'self' data: https:; "
        "connect-src 'self';"
    )
    return response


if os.environ.get("SERVER_SOFTWARE", "").startswith("gunicorn"):
    start_background_scheduler(_execute_scheduled_refresh_job, _dispatch_telegram_job, interval_seconds=60)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="AutoBI Multi-Domain Web Portal")
    parser.add_argument("--port", type=int, default=5000, help="Port to listen on")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host binding")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    args = parser.parse_args()

    start_background_scheduler(_execute_scheduled_refresh_job, _dispatch_telegram_job, interval_seconds=60)
    print("=" * 80)
    print(f"[*] STARTING AUTOBI MULTI-DOMAIN WEB PORTAL AT http://{args.host}:{args.port}")
    print("=" * 80)
    app.run(host=args.host, port=args.port, debug=args.debug)
