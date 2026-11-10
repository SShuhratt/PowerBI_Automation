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
from datetime import datetime, timedelta
from typing import Optional
import functools
import pandas as pd
from flask import Flask, request, jsonify, render_template, send_file

from cleaner import SelfHealingCleaner
from pbi_model import PowerBIModelGenerator
from domain_classifier import DomainClassifier, DOMAINS
from session_store import sessions
from dashboard_preview import generate_html_dashboard
from pbip_generator import generate_pbip_artifacts
from google_sheets import fetch_google_sheets_csv, extract_google_sheets_csv_url

import numpy as np
import math

app = Flask(__name__, static_folder="static", template_folder="templates")
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024  # 32MB max upload
app.json.sort_keys = False

# Authentication configuration
WORKSPACE_PASSCODE = os.environ.get("WORKSPACE_PASSCODE", "autobi2026")
AUTH_ENABLED = os.environ.get("AUTH_ENABLED", "true").lower() in ("true", "1", "yes")


def get_current_user():
    if not AUTH_ENABLED:
        return "pilot@autobi.local"
    # 1. Check HTTP-only cookie
    user_cookie = request.cookies.get("autobi_user")
    if user_cookie:
        return user_cookie
    # 2. Check X-Workspace-Key header (for automated scripts / API tests)
    key_header = request.headers.get("X-Workspace-Key")
    if key_header == WORKSPACE_PASSCODE:
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
    model_gen = PowerBIModelGenerator(df, csv_path=csv_path_for_model, domain=domain_override)
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

    # 4. Cleaned CSV in-memory
    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False)
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

    # 6. Compute Domain-Specific KPIs
    cols = list(df.columns)
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

        # Charts: Spend by Channel & Conversions by Campaign
        if "channel" in cols and "ad_spend" in cols:
            charts["chart1"] = {
                "title": "Ad Spend by Channel",
                "type": "doughnut",
                "data": {str(k): round(float(v), 2) for k, v in df.groupby("channel")["ad_spend"].sum().items()}
            }
        if "campaign_name" in cols and "conversions" in cols:
            charts["chart2"] = {
                "title": "Conversions by Campaign",
                "type": "bar",
                "data": {str(k): int(v) for k, v in df.groupby("campaign_name")["conversions"].sum().items()}
            }

    elif domain_key == "hr":
        headcount = len(df)
        term_col = "termination_date" if "termination_date" in cols else None
        active = len(df[df[term_col].isna()]) if term_col else headcount
        departed = headcount - active
        attrition = (departed / headcount * 100) if headcount > 0 else 0.0
        avg_sal = float(df["salary"].mean()) if "salary" in cols else 0.0
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
                "data": {str(k): int(v) for k, v in df["department"].value_counts().items()}
            }
        if "department" in cols and "salary" in cols:
            charts["chart2"] = {
                "title": "Payroll Spend by Department",
                "type": "doughnut",
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
            df["_temp_val"] = df[stock_col] * df[cost_col]
            charts["chart1"] = {
                "title": "Inventory Value by Category",
                "type": "bar",
                "data": {str(k): round(float(v), 2) for k, v in df.groupby("category")["_temp_val"].sum().items()}
            }
        if "warehouse" in cols and stock_col:
            charts["chart2"] = {
                "title": "Unit Distribution by Warehouse",
                "type": "doughnut",
                "data": {str(k): int(v) for k, v in df.groupby("warehouse")[stock_col].sum().items()}
            }

    elif domain_key == "finance":
        rev_col = None
        for c in cols:
            if any(k in c for k in ["revenue", "income", "sales", "actual"]):
                rev_col = c
                break
        exp_col = None
        for c in cols:
            if any(k in c for k in ["expense", "opex", "cost", "spending"]):
                exp_col = c
                break
        profit_col = None
        for c in cols:
            if any(k in c for k in ["profit", "net_income", "margin"]):
                profit_col = c
                break
        budget_col = None
        for c in cols:
            if "budget" in c:
                budget_col = c
                break
        account_col = None
        for c in cols:
            if any(k in c for k in ["account", "gl_code", "category", "entity"]):
                account_col = c
                break

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
                "title": f"Expenses by {account_col.replace('_', ' ').title()}",
                "type": "bar",
                "data": {str(k): round(float(v), 2) for k, v in df.groupby(account_col)[exp_col].sum().head(10).items()}
            }
        elif account_col and rev_col and pd.api.types.is_numeric_dtype(df[rev_col]):
            charts["chart1"] = {
                "title": f"Revenue by {account_col.replace('_', ' ').title()}",
                "type": "bar",
                "data": {str(k): round(float(v), 2) for k, v in df.groupby(account_col)[rev_col].sum().head(10).items()}
            }
        if account_col:
            charts["chart2"] = {
                "title": f"Distribution by {account_col.replace('_', ' ').title()}",
                "type": "doughnut",
                "data": {str(k): int(v) for k, v in df[account_col].value_counts().head(8).items()}
            }

    elif domain_key == "generic":
        total_records = len(df)
        total_cols = len(cols)
        total_cells = max(total_records * total_cols, 1)
        filled_cells = int(df.notna().sum().sum())
        completeness = (filled_cells / total_cells) * 100.0

        num_cols = [c for c in cols if pd.api.types.is_numeric_dtype(df[c])]
        cat_cols = [c for c in cols if not pd.api.types.is_numeric_dtype(df[c])]

        first_cat = cat_cols[0] if cat_cols else (cols[0] if cols else "item")
        unique_entities = int(df[first_cat].nunique()) if first_cat in cols else total_records

        kpis = [
            {"label": "Total Records", "value": f"{total_records:,}", "sub": "Recorded rows / observations", "theme": "emerald"},
            {"label": "Data Fields / Dimensions", "value": f"{total_cols:,}", "sub": "Tracked attributes", "theme": "cyan"},
            {"label": "Data Completeness", "value": f"{completeness:.1f}%", "sub": f"{filled_cells:,} non-empty data points", "theme": "emerald" if completeness >= 80 else "amber"},
            {"label": "Primary Entities", "value": f"{unique_entities:,}", "sub": f"Unique {first_cat.replace('_', ' ').title()}", "theme": ""},
            {"label": "Numeric Metrics", "value": f"{len(num_cols):,}", "sub": "Calculable numeric fields", "theme": "cyan"},
            {"label": "Text / Categorical Fields", "value": f"{len(cat_cols):,}", "sub": "Descriptive dimensions", "theme": ""}
        ]

        col_fill_rates = {str(c): round(float(df[c].notna().mean() * 100), 1) for c in cols[:10]}
        charts["chart1"] = {
            "title": "Field Fill Rate (% Valid Data)",
            "type": "bar",
            "data": col_fill_rates
        }

        if cat_cols and num_cols:
            n_col = num_cols[0]
            charts["chart2"] = {
                "title": f"{n_col.replace('_', ' ').title()} by {first_cat.replace('_', ' ').title()}",
                "type": "bar",
                "data": {str(k): round(float(v), 2) for k, v in df.groupby(first_cat)[n_col].sum().head(8).items()}
            }
        elif cat_cols:
            charts["chart2"] = {
                "title": f"Observations by {first_cat.replace('_', ' ').title()}",
                "type": "doughnut",
                "data": {str(k): int(v) for k, v in df[first_cat].value_counts().head(8).items()}
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
                "data": {str(k): round(float(v), 2) for k, v in df.groupby("category")["total_revenue"].sum().items()}
            }
        if "region" in cols and "total_revenue" in cols and pd.api.types.is_numeric_dtype(df["total_revenue"]):
            charts["chart2"] = {
                "title": "Revenue Distribution by Region",
                "type": "doughnut",
                "data": {str(k): round(float(v), 2) for k, v in df.groupby("region")["total_revenue"].sum().items()}
            }

    # 7. Sample Table Records (up to 50 rows)
    preview_df = df.head(50).copy()
    for c in preview_df.columns:
        if pd.api.types.is_datetime64_any_dtype(preview_df[c]):
            preview_df[c] = preview_df[c].dt.strftime("%Y-%m-%d")

    records = preview_df.fillna("").to_dict(orient="records")

    # 8. Generate standalone Executive HTML dashboard
    dashboard_html = generate_html_dashboard(df, kpis, charts, domain_info, filename)

    # 9. Generate Native Power BI Project (.pbip) artifacts
    pbip_files = generate_pbip_artifacts(df, model_gen.table_name, measures, m_script)

    # Persist session with artifacts, dashboard preview and PBIP bundle
    sessions.set(session_id, {
        "created_at": datetime.now().isoformat(),
        "cleaned_csv": cleaned_csv_str,
        "dax_content": dax_file_content,
        "m_script": m_script,
        "cheatsheet": cheatsheet_content,
        "audit_log": cleaner.audit_log,
        "readme": readme_content,
        "filename": filename,
        "dashboard_html": dashboard_html,
        "pbip_files": pbip_files,
        "is_live_url": is_live_url,
        "source_url": source_csv_path if is_live_url else None,
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
            ]
        },
        "kpis": kpis,
        "charts": charts,
        "audit_log": cleaner.audit_log,
        "dax_measures": measures,
        "power_query_m": m_script,
        "sheet_info": {
            "selected_sheet": getattr(cleaner, "sheet_name", None),
            "available_sheets": getattr(cleaner, "available_sheets", []),
        },
        "table_columns": list(df.columns),
        "table_records": records,
    }
    return sanitize_for_json(payload)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/auth/status")
def auth_status():
    user = get_current_user()
    return jsonify({
        "auth_enabled": AUTH_ENABLED,
        "authenticated": user is not None,
        "user": user
    })


@app.route("/api/auth/login", methods=["POST"])
def auth_login():
    data = request.get_json(silent=True) or {}
    passcode = data.get("passcode", "").strip()
    email = data.get("email", "").strip() or "analyst@enterprise.local"

    if not passcode or passcode != WORKSPACE_PASSCODE:
        return jsonify({"success": False, "error": "Invalid workspace access passcode."}), 401

    res = jsonify({
        "success": True,
        "message": "Workspace successfully authenticated.",
        "user": email
    })
    res.set_cookie("autobi_user", email, max_age=30 * 86400, httponly=True, samesite="Lax")
    return res


@app.route("/api/auth/logout", methods=["POST"])
def auth_logout():
    res = jsonify({"success": True, "message": "Logged out of workspace."})
    res.set_cookie("autobi_user", "", max_age=0, httponly=True, samesite="Lax")
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


@app.route("/api/sheets", methods=["POST"])
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
        result = build_analysis_payload(cleaner, df_clean, f"demo_{domain}_dataset.xlsx", domain_override=domain)
        return jsonify(result)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/preview/<session_id>")
def preview_dashboard(session_id: str):
    """Serve standalone interactive HTML executive dashboard."""
    session = sessions.get(session_id)
    if not session or not session.get("dashboard_html"):
        return jsonify({"error": "Session expired or preview unavailable. Please re-run analysis."}), 404
    return session["dashboard_html"], 200, {"Content-Type": "text/html; charset=utf-8"}


@app.route("/api/purge/<session_id>", methods=["POST", "DELETE"])
def purge_session(session_id: str):
    """Explicit data privacy purge: permanently wipes session from server RAM and disk."""
    success = sessions.delete(session_id)
    return jsonify({
        "success": success,
        "message": "Session and all associated data permanently purged from server memory and disk storage."
    })


@app.route("/api/download/<session_id>")
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


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="AutoBI Multi-Domain Web Portal")
    parser.add_argument("--port", type=int, default=5000, help="Port to listen on")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host binding")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    args = parser.parse_args()

    print("=" * 80)
    print(f"[*] STARTING AUTOBI MULTI-DOMAIN WEB PORTAL AT http://{args.host}:{args.port}")
    print("=" * 80)
    app.run(host=args.host, port=args.port, debug=args.debug)
