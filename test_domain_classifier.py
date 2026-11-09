"""
test_domain_classifier.py - Comprehensive test suite for Domain Classification & Multi-Domain DAX Modeling
"""

import sys
import pandas as pd
from domain_classifier import DomainClassifier
from pbi_model import PowerBIModelGenerator
from web_app import app

# Ensure clean UTF-8 console output
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def test_domain_classifier_accuracy():
    # 1. Sales Data
    df_sales = pd.DataFrame({
        "order_id": [1, 2], "revenue": [100.0, 200.0], "units_sold": [2, 4], "status": ["Completed", "Cancelled"]
    })
    res_sales = DomainClassifier(df_sales).classify()
    assert res_sales["domain"] == "sales"
    assert res_sales["confidence"] >= 70.0

    # 2. Marketing Data
    df_mktg = pd.DataFrame({
        "campaign_name": ["CampA", "CampB"], "ad_spend": [500.0, 1000.0], "impressions": [10000, 25000],
        "clicks": [400, 950], "conversions": [20, 50]
    })
    res_mktg = DomainClassifier(df_mktg).classify()
    assert res_mktg["domain"] == "marketing"
    assert res_mktg["confidence"] >= 80.0

    # 3. HR Data
    df_hr = pd.DataFrame({
        "employee_id": ["E1", "E2"], "department": ["Eng", "Sales"], "salary": [120000, 95000],
        "hire_date": ["2022-01-01", "2023-01-01"], "termination_date": [None, "2024-01-01"]
    })
    res_hr = DomainClassifier(df_hr).classify()
    assert res_hr["domain"] == "hr"
    assert res_hr["confidence"] >= 80.0

    # 4. Inventory Data
    df_inv = pd.DataFrame({
        "sku": ["SKU1", "SKU2"], "warehouse": ["East", "West"], "units_on_hand": [50, 0],
        "reorder_level": [20, 10], "unit_cost": [15.0, 30.0]
    })
    res_inv = DomainClassifier(df_inv).classify()
    assert res_inv["domain"] == "inventory"
    assert res_inv["confidence"] >= 80.0

    # 5. Finance Data
    df_fin = pd.DataFrame({
        "account_name": ["Sales Rev", "Office Rent"], "revenue": [50000, 0], "expenses": [0, 8000],
        "budget": [45000, 7500]
    })
    res_fin = DomainClassifier(df_fin).classify()
    assert res_fin["domain"] == "finance"
    assert res_fin["confidence"] >= 75.0

    print("[PASS] DomainClassifier correctly identifies all 5 business domains.")


def test_multi_domain_dax_generation():
    # Marketing DAX
    df_mktg = pd.DataFrame({
        "ad_spend": [1000.0], "impressions": [50000], "clicks": [1200], "conversions": [60], "conversion_value": [4000.0]
    })
    gen_mktg = PowerBIModelGenerator(df_mktg, domain="marketing")
    dax_mktg = gen_mktg.generate_dax_measures()
    names_mktg = [m["name"] for m in dax_mktg]
    assert "Total Ad Spend" in names_mktg
    assert "Click-Through Rate (CTR)" in names_mktg
    assert "Cost Per Click (CPC)" in names_mktg
    assert "Return on Ad Spend (ROAS)" in names_mktg

    # HR DAX
    df_hr = pd.DataFrame({
        "employee_id": [1, 2], "salary": [100000, 120000], "termination_date": [None, "2024-01-01"]
    })
    gen_hr = PowerBIModelGenerator(df_hr, domain="hr")
    dax_hr = gen_hr.generate_dax_measures()
    names_hr = [m["name"] for m in dax_hr]
    assert "Total Headcount" in names_hr
    assert "Active Headcount" in names_hr
    assert "Attrition Rate" in names_hr
    assert "Total Annual Payroll" in names_hr

    # Inventory DAX
    df_inv = pd.DataFrame({
        "sku": ["S1", "S2"], "units_on_hand": [10, 0], "unit_cost": [5.0, 12.0], "reorder_level": [5, 2]
    })
    gen_inv = PowerBIModelGenerator(df_inv, domain="inventory")
    dax_inv = gen_inv.generate_dax_measures()
    names_inv = [m["name"] for m in dax_inv]
    assert "Total Inventory Value" in names_inv
    assert "Out of Stock SKUs" in names_inv
    assert "Stockout Rate" in names_inv

    print("[PASS] PowerBIModelGenerator produces domain-specific production DAX formulas.")


def test_api_multi_domain_presets():
    client = app.test_client()
    headers = {"X-Workspace-Key": "autobi2026"}

    for domain in ["sales", "marketing", "hr", "inventory"]:
        res = client.post("/api/sample", json={"domain": domain}, headers=headers)
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert data["domain"]["key"] == domain
        assert len(data["kpis"]) >= 4
        assert len(data["dax_measures"]) >= 4
        assert "chart1" in data["charts"] or "category" in data["charts"]

        # Check download for each domain
        sid = data["session_id"]
        dl = client.get(f"/api/download/{sid}")
        assert dl.status_code == 200
        assert dl.mimetype == "application/zip"

    print("[PASS] API /api/sample supports all multi-domain presets with ZIP generation.")


if __name__ == "__main__":
    test_domain_classifier_accuracy()
    test_multi_domain_dax_generation()
    test_api_multi_domain_presets()
    print("\nALL MULTI-DOMAIN TESTS PASSED! [OK]")
