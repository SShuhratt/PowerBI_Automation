"""
test_edge_cases.py - Exhaustive Edge Case Test Suite for AutoBI Multi-Domain Engine
Tests real-world messy spreadsheets:
1. temp_stats.xlsx (The exact user crash scenario: mixed integer year headers, Uzbek punctuation, non-English schema)
2. Heterogeneous Column Types (ints, floats, strings, None, blanks)
3. Unicode Punctuation & Quotes in headers (Ko'rsatkich, O'sish, Xalqaro me'yor, brackets, currency)
4. Header Offset / Banner Rows (Title block on Row 0, blank Row 1, actual headers on Row 2)
5. Summary / Trailer Rows (Total, Grand Total, Subtotal, Average)
6. Placeholder Representations ('—', '–', 'N/A', '#DIV/0!', '#VALUE!')
7. European / CIS Number Formats (comma decimals, space thousands, percentages)
8. Extreme Dimensions (0-row empty dataset, 1-row dataset, All-NaN columns, duplicate headers)
9. Domain Classifier & DAX generation across Sales, Marketing, HR, Inventory, Finance, Generic
10. Full Flask API Endpoints (/api/upload, /api/sample, /api/download/<session_id>)
"""

import io
import os
import zipfile
import json
import traceback
import pandas as pd
import numpy as np

from cleaner import SelfHealingCleaner
from pbi_model import PowerBIModelGenerator
from domain_classifier import DomainClassifier
from web_app import app, build_analysis_payload, sanitize_for_json


def test_user_temp_stats_file():
    """Verify that temp_stats.xlsx is cleaned and processed without '<' int/str error."""
    file_path = r"C:\Users\user\Desktop\temp_stats.xlsx"
    if not os.path.exists(file_path):
        print("[-] Skipping test_user_temp_stats_file (file not found on Desktop)")
        return

    # 1. Cleaner directly
    cleaner = SelfHealingCleaner(file_path)
    df_clean = cleaner.clean()
    assert len(df_clean) > 0, "DataFrame should not be empty"
    assert "year_2020" in df_clean.columns, "2020 should become year_2020"
    assert "year_2022" in df_clean.columns, "2022 should become year_2022"
    assert "year_2024" in df_clean.columns, "2024 should become year_2024"
    assert "korsatkich" in df_clean.columns, "Ko'rsatkich should become korsatkich"
    assert "osish" in df_clean.columns, "O'sish should become osish"

    # Verify all renamed_columns keys are strings
    for k in cleaner.audit_log["renamed_columns"].keys():
        assert isinstance(k, str), f"Renamed column key {k!r} is not a string"

    # 2. Semantic modeling
    gen = PowerBIModelGenerator(df_clean)
    measures = gen.generate_dax_measures()
    assert len(measures) >= 1, "Should generate at least 1 DAX measure"
    m_script = gen.generate_power_query_m()
    assert "Table.PromoteHeaders" in m_script

    # 3. Payload and JSON sanitization
    payload = build_analysis_payload(cleaner, df_clean, "temp_stats.xlsx")
    assert payload["success"] is True
    assert payload["domain"]["key"] == "generic"
    assert len(payload["kpis"]) >= 4, f"Generic KPIs missing: {payload['kpis']}"
    assert "chart1" in payload["charts"], "Generic chart1 should exist"

    # Ensure json dumps with sort_keys=True DOES NOT CRASH
    serialized = json.dumps(payload, sort_keys=True)
    assert len(serialized) > 100

    # 4. End-to-end API upload
    client = app.test_client()
    with open(file_path, "rb") as f:
        file_bytes = f.read()

    res = client.post(
        "/api/upload",
        data={"file": (io.BytesIO(file_bytes), "temp_stats.xlsx")},
        content_type="multipart/form-data"
    )
    assert res.status_code == 200, f"Upload failed with status {res.status_code}: {res.data}"
    json_data = res.get_json()
    assert json_data["success"] is True
    assert json_data["domain"]["key"] == "generic"
    assert len(json_data["table_records"]) == len(df_clean)
    print("[PASS] test_user_temp_stats_file (User crash case resolved successfully)")


def test_heterogeneous_column_types():
    """Excel files often have integer years, floats, or blank cells as column headers."""
    raw_data = {
        2020: [100, 200, 300],
        2021: [150, 250, 350],
        4.5: ["A", "B", "C"],
        "Revenue ($)": [1000.0, 2000.0, 3000.0],
        None: ["x", "y", "z"],
        "": [1, 2, 3]
    }
    df_raw = pd.DataFrame(raw_data)
    cleaner = SelfHealingCleaner(df_raw, filename="mixed_headers.xlsx")
    df_clean = cleaner.clean()

    # Column names must all be valid strings
    for col in df_clean.columns:
        assert isinstance(col, str)
        assert len(col) > 0

    assert "year_2020" in df_clean.columns
    assert "year_2021" in df_clean.columns
    assert "revenue" in df_clean.columns

    payload = build_analysis_payload(cleaner, df_clean, "mixed_headers.xlsx")
    # Must serialize cleanly even with sort_keys=True
    dumped = json.dumps(payload, sort_keys=True)
    assert len(dumped) > 0
    print("[PASS] test_heterogeneous_column_types")


def test_unicode_punctuation_in_headers():
    """Headers with quotes, apostrophes, accents, brackets, currency symbols."""
    raw_data = {
        "Ko'rsatkich": ["A", "B"],
        "O'sish (%)": [0.1, 0.2],
        "Xalqaro me'yor": ["IMF", "WB"],
        "Net Profit / (Loss) [USD]": [500, -200],
        "Date & Time": ["2026-01-01", "2026-01-02"],
        "Tax (incl. VAT)": [10, 20]
    }
    df_raw = pd.DataFrame(raw_data)
    cleaner = SelfHealingCleaner(df_raw, filename="unicode_test.xlsx")
    df_clean = cleaner.clean()

    expected_cols = ["korsatkich", "osish", "xalqaro_meyor", "net_profit", "date_time", "tax"]
    assert df_clean.columns.tolist() == expected_cols, f"Got: {df_clean.columns.tolist()}"
    print("[PASS] test_unicode_punctuation_in_headers")


def test_header_offset_banner_row():
    """Spreadsheet with Row 0 title banner, Row 1 blank, Row 2 actual headers."""
    data = [
        ["Annual Sales Report 2026", None, None, None],
        [None, None, None, None],
        ["order_id", "region", "units_sold", "unit_price"],
        [101, "North", 10, 15.0],
        [102, "South", 20, 25.0],
    ]
    df_raw = pd.DataFrame(data, columns=["Unnamed: 0", "Unnamed: 1", "Unnamed: 2", "Unnamed: 3"])
    cleaner = SelfHealingCleaner(df_raw, filename="banner_report.xlsx")
    df_clean = cleaner.clean()

    assert "order_id" in df_clean.columns
    assert "region" in df_clean.columns
    assert "units_sold" in df_clean.columns
    assert len(df_clean) == 2
    assert cleaner.audit_log.get("header_promoted_from_row") == 3
    print("[PASS] test_header_offset_banner_row")


def test_summary_trailer_rows_dropped():
    """Spreadsheet containing Total, Grand Total, Subtotal, Average rows."""
    data = [
        {"item": "Widget A", "revenue": 100.0, "qty": 10},
        {"item": "Widget B", "revenue": 200.0, "qty": 20},
        {"item": "Subtotal", "revenue": 300.0, "qty": 30},
        {"item": "Widget C", "revenue": 150.0, "qty": 15},
        {"item": "Grand Total", "revenue": 450.0, "qty": 45},
    ]
    df_raw = pd.DataFrame(data)
    cleaner = SelfHealingCleaner(df_raw, filename="with_totals.xlsx")
    df_clean = cleaner.clean()

    # Both Subtotal and Grand Total should be purged
    assert len(df_clean) == 3
    assert all("total" not in str(val).lower() for val in df_clean["item"])
    assert len(cleaner.audit_log["dropped_rows"]) == 2
    print("[PASS] test_summary_trailer_rows_dropped")


def test_placeholder_normalization():
    """Dashes, N/A, and Excel formula errors should convert to real np.nan."""
    data = {
        "item": ["A", "B", "C", "D", "E", "F"],
        "metric": [" — ", "–", "N/A", "#DIV/0!", "#VALUE!", "100"]
    }
    df_raw = pd.DataFrame(data)
    cleaner = SelfHealingCleaner(df_raw, filename="placeholders.xlsx")
    df_clean = cleaner.clean()

    assert df_clean["metric"].iloc[:5].isna().all()
    assert df_clean["metric"].iloc[5] == 100 or str(df_clean["metric"].iloc[5]).startswith("100")
    print("[PASS] test_placeholder_normalization")


def test_european_cis_numbers():
    """Comma as decimal, space as thousands separator."""
    data = {
        "sales_rep": ["Alice", "Bob", "Charlie"],
        "amount": ["1 250,50", "3 400,00", "500,75"],
        "salary": ["3 500", "4 200", "5 000"]
    }
    df_raw = pd.DataFrame(data)
    cleaner = SelfHealingCleaner(df_raw, filename="european_fmt.xlsx")
    df_clean = cleaner.clean()

    assert pd.api.types.is_numeric_dtype(df_clean["amount"])
    assert df_clean["amount"].iloc[0] == 1250.50
    assert pd.api.types.is_numeric_dtype(df_clean["salary"])
    assert df_clean["salary"].iloc[0] == 3500
    print("[PASS] test_european_cis_numbers")


def test_zero_row_empty_dataframe():
    """Empty dataframe with headers only must not crash with ZeroDivisionError."""
    df_empty = pd.DataFrame(columns=["order_id", "order_date", "total_revenue", "units_sold"])
    cleaner = SelfHealingCleaner(df_empty, filename="empty.xlsx")
    df_clean = cleaner.clean()

    payload = build_analysis_payload(cleaner, df_clean, "empty.xlsx")
    assert payload["success"] is True
    assert len(payload["table_records"]) == 0
    # Check serialization
    json.dumps(payload, sort_keys=True)
    print("[PASS] test_zero_row_empty_dataframe")


def test_single_row_dataframe():
    """Dataset with just 1 row of data."""
    df_single = pd.DataFrame([{"campaign_name": "Lone Campaign", "ad_spend": 50.0, "clicks": 20, "impressions": 500}])
    cleaner = SelfHealingCleaner(df_single, filename="single.xlsx")
    df_clean = cleaner.clean()

    payload = build_analysis_payload(cleaner, df_clean, "single.xlsx")
    assert payload["success"] is True
    assert len(payload["table_records"]) == 1
    print("[PASS] test_single_row_dataframe")


def test_all_nan_column_and_inferred_calc():
    """Missing total_revenue column should be inferred from units_sold * unit_price."""
    data = {
        "order_id": [1, 2, 3],
        "units_sold": [10, 20, 30],
        "unit_price": [5.0, 10.0, 15.0],
        "total_revenue": [np.nan, np.nan, np.nan]
    }
    df_raw = pd.DataFrame(data)
    cleaner = SelfHealingCleaner(df_raw, filename="calc_inference.xlsx")
    df_clean = cleaner.clean()

    assert df_clean["total_revenue"].tolist() == [50.0, 200.0, 450.0]
    assert len(cleaner.audit_log["inferred_calculations"]) == 1
    print("[PASS] test_all_nan_column_and_inferred_calc")


def test_duplicate_column_headers():
    """Duplicate column headers must be cleanly disambiguated."""
    df_dups = pd.DataFrame([[1, 2, 3, 4]], columns=["sales", "sales", "Sales", "SALES"])
    cleaner = SelfHealingCleaner(df_dups, filename="duplicates.xlsx")
    df_clean = cleaner.clean()

    assert df_clean.columns.tolist() == ["sales", "sales_2", "sales_3", "sales_4"]
    print("[PASS] test_duplicate_column_headers")


def test_all_domain_models_and_payloads():
    """Ensure every operational domain generates rich KPIs, charts, and valid DAX."""
    domains = {
        "sales": [{"order_id": 1, "units_sold": 5, "total_revenue": 100.0, "status": "Completed"}],
        "marketing": [{"campaign_id": "C1", "campaign_name": "Promo", "channel": "Google", "ad_spend": 200.0, "clicks": 50, "impressions": 1000, "conversions": 10}],
        "hr": [{"employee_id": "E1", "department": "Sales", "salary": 80000, "hire_date": "2023-01-01"}],
        "inventory": [{"sku": "SKU1", "product_name": "Gadget", "units_on_hand": 100, "unit_cost": 25.0, "reorder_level": 30}],
        "finance": [{"account": "Ops", "revenue": 5000.0, "expense": 3000.0, "profit": 2000.0, "budget": 4500.0}],
        "generic": [{"metric_name": "GDP Growth", "q1": "2.4%", "q2": "3.1%"}]
    }

    for domain_key, data in domains.items():
        df = pd.DataFrame(data)
        cleaner = SelfHealingCleaner(df, filename=f"test_{domain_key}.xlsx")
        df_clean = cleaner.clean()

        payload = build_analysis_payload(cleaner, df_clean, f"test_{domain_key}.xlsx", domain_override=domain_key if domain_key != "generic" else None)
        assert payload["success"] is True
        assert len(payload["kpis"]) >= 3
        assert len(payload["dax_measures"]) >= 1
        # Must serialize without error
        json_str = json.dumps(payload, sort_keys=True)
        assert len(json_str) > 50

    print("[PASS] test_all_domain_models_and_payloads (sales, marketing, hr, inventory, finance, generic)")


def test_api_sample_all_domains():
    """Test /api/sample endpoint for all preset domains."""
    client = app.test_client()
    for dom in ["sales", "marketing", "hr", "inventory"]:
        res = client.post("/api/sample", json={"domain": dom})
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert data["domain"]["key"] == dom
        assert len(data["kpis"]) >= 4
        assert len(data["dax_measures"]) >= 2

        # Verify download pack
        session_id = data["session_id"]
        dl_res = client.get(f"/api/download/{session_id}")
        assert dl_res.status_code == 200
        assert dl_res.mimetype == "application/zip"

        # Inspect zip contents
        zip_buf = io.BytesIO(dl_res.data)
        with zipfile.ZipFile(zip_buf, "r") as zf:
            files = zf.namelist()
            assert "cleaned_data.csv" in files
            assert "LoadData.m" in files
            assert "dax_measures.dax" in files
            assert "POWER_BI_MEASURES_CHEATSHEET.md" in files
            assert "audit_log.json" in files
            assert "README.txt" in files

    print("[PASS] test_api_sample_all_domains")


def test_api_upload_csv_bytes():
    """Test uploading a messy CSV directly via /api/upload."""
    client = app.test_client()
    csv_content = b"Item,2020,2022,Growth\nProduct A,100,150,50%\nProduct B,200,280,40%\nTotal,300,430,43%\n"
    res = client.post(
        "/api/upload",
        data={"file": (io.BytesIO(csv_content), "messy_sales.csv")},
        content_type="multipart/form-data"
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    # 'Total' row must have been dropped
    assert len(data["table_records"]) == 2
    # Renamed columns must have string keys
    for k in data["audit_log"]["renamed_columns"].keys():
        assert isinstance(k, str)

    print("[PASS] test_api_upload_csv_bytes")


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    print("=" * 80)
    print("RUNNING EXHAUSTIVE SPREADSHEET EDGE CASE TEST SUITE")
    print("=" * 80)

    tests = [
        test_user_temp_stats_file,
        test_heterogeneous_column_types,
        test_unicode_punctuation_in_headers,
        test_header_offset_banner_row,
        test_summary_trailer_rows_dropped,
        test_placeholder_normalization,
        test_european_cis_numbers,
        test_zero_row_empty_dataframe,
        test_single_row_dataframe,
        test_all_nan_column_and_inferred_calc,
        test_duplicate_column_headers,
        test_all_domain_models_and_payloads,
        test_api_sample_all_domains,
        test_api_upload_csv_bytes,
    ]

    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"[FAIL] {t.__name__}: {e}")
            traceback.print_exc()

    print("=" * 80)
    print(f"RESULTS: {passed} PASSED, {failed} FAILED across {len(tests)} edge cases")
    print("=" * 80)
    if failed > 0:
        sys.exit(1)
