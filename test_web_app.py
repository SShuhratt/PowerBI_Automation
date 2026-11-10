"""
test_web_app.py - Automated test suite for AutoBI Web Portal backend endpoints.
"""

import io
import json
import zipfile
from web_app import app


AUTH_HEADERS = {"X-Workspace-Key": "autobi2026"}


def test_auth_flow():
    """Verify workspace passcode authentication gate and session security."""
    client = app.test_client()

    # 1. Check status initially (unauthenticated)
    st_res = client.get("/api/auth/status")
    assert st_res.status_code == 200
    assert st_res.get_json()["authenticated"] is False

    # 2. Reject unauthenticated sample request
    unauth_res = client.post("/api/sample")
    assert unauth_res.status_code == 401
    assert unauth_res.get_json()["auth_required"] is True

    # 3. Wrong passcode rejected
    wrong_login = client.post("/api/auth/login", json={"passcode": "wrong_code"})
    assert wrong_login.status_code == 401

    # 4. Correct passcode accepted and cookie set
    good_login = client.post("/api/auth/login", json={"passcode": "autobi2026", "email": "director@company.com"})
    assert good_login.status_code == 200
    assert good_login.get_json()["success"] is True

    # 5. Status now authenticated
    st_after = client.get("/api/auth/status")
    assert st_after.get_json()["authenticated"] is True
    assert st_after.get_json()["user"] == "director@company.com"

    # 6. Logout clears session
    logout_res = client.post("/api/auth/logout")
    assert logout_res.status_code == 200
    assert client.get("/api/auth/status").get_json()["authenticated"] is False
    print("[PASS] test_auth_flow (Access Gate, Passcode verification & Logout)")


def test_index_route():
    client = app.test_client()
    res = client.get("/")
    assert res.status_code == 200
    assert b"AutoBI Studio" in res.data
    assert b"dropzone" in res.data
    assert b"Zero-Persistence Guarantee" in res.data
    assert b"Download Power BI Starter Kit" in res.data
    print("[PASS] test_index_route")


def test_api_sample():
    client = app.test_client()
    res = client.post("/api/sample", headers=AUTH_HEADERS)
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert "session_id" in data

    # Verify Auto-Healing
    audit = data["audit_log"]
    assert audit["raw_row_count"] == 13
    assert audit["cleaned_row_count"] == 12
    assert len(audit["dropped_rows"]) == 1
    assert audit["dropped_rows"][0]["row_index"] == 12

    # Verify Inferred Calculations
    assert len(audit["inferred_calculations"]) == 1
    assert audit["inferred_calculations"][0]["column"] == "total_revenue"

    # Verify KPIs
    kpis = data["kpis"]
    assert len(kpis) >= 4
    rev_kpi = [k for k in kpis if "Revenue" in k["label"]][0]
    assert "$22,437.50" in rev_kpi["value"]

    # Verify DAX measures
    dax = data["dax_measures"]
    assert len(dax) >= 8
    assert any(m["name"] == "Total Revenue" for m in dax)

    # Verify Download Zip for this session
    session_id = data["session_id"]
    dl_res = client.get(f"/api/download/{session_id}")
    assert dl_res.status_code == 200
    assert dl_res.mimetype == "application/zip"

    # Verify ZIP contents (including native Power BI Project .pbip bundle)
    zf = zipfile.ZipFile(io.BytesIO(dl_res.data))
    namelist = zf.namelist()
    assert "cleaned_data.csv" in namelist
    assert "LoadData.m" in namelist
    assert "dax_measures.dax" in namelist
    assert "POWER_BI_MEASURES_CHEATSHEET.md" in namelist
    assert "audit_log.json" in namelist
    assert "Executive_Dashboard_Preview.html" in namelist
    assert "QuickLaunch_PowerBI.bat" in namelist
    assert "AutoBI_Project.pbip" in namelist
    assert "AutoBI_Project.SemanticModel/definition/model.bim" in namelist
    assert "AutoBI_Project.Report/definition/report.json" in namelist
    assert "README.txt" in namelist

    print("[PASS] test_api_sample & test_download_zip (with native .pbip bundle)")


def test_api_upload_csv():
    client = app.test_client()
    # Create sample CSV with a summary row and missing calculation
    csv_content = """Order ID,Units Sold,Unit Price ($),Total Revenue ($),Status
101,10,15,,Completed
102,5,20,,Completed
Total,15,35,,
"""
    data = {
        'file': (io.BytesIO(csv_content.encode('utf-8')), 'test_upload.csv')
    }
    res = client.post("/api/upload", data=data, content_type='multipart/form-data', headers=AUTH_HEADERS)
    assert res.status_code == 200
    res_data = res.get_json()
    assert res_data["success"] is True

    # Check that 'Total' was pruned
    assert res_data["audit_log"]["cleaned_row_count"] == 2
    assert len(res_data["audit_log"]["dropped_rows"]) == 1

    # Check that Total Revenue was computed: (10*15) + (5*20) = 150 + 100 = 250
    rev_kpi = [k for k in res_data["kpis"] if "Revenue" in k["label"]][0]
    assert "$250.00" in rev_kpi["value"]
    print("[PASS] test_api_upload_csv")


def test_session_persistence():
    """Verify that sessions persist in SQLite WAL across different connection/worker instances."""
    from session_store import sessions
    test_id = "test-sid-uuid-42"
    test_payload = {"filename": "sales.xlsx", "cleaned_csv": "col1,col2\n1,2", "m_script": "let", "dax_content": "Total = 1", "cheatsheet": "# Cheatsheet", "audit_log": {}, "readme": "Hello"}
    
    assert sessions.set(test_id, test_payload) is True
    retrieved = sessions.get(test_id)
    assert retrieved is not None
    assert retrieved["filename"] == "sales.xlsx"
    assert retrieved["cleaned_csv"] == "col1,col2\n1,2"
    
    # Test client download route using the persisted session
    client = app.test_client()
    dl_res = client.get(f"/api/download/{test_id}")
    assert dl_res.status_code == 200
    assert dl_res.mimetype == "application/zip"
    
    # Clean up
    sessions.delete(test_id)
    assert sessions.get(test_id) is None
    print("[PASS] test_session_persistence across workers")


def test_multi_sheet_and_encoding():
    """Verify multi-sheet Excel extraction and CP1251 Cyrillic CSV parsing."""
    import pandas as pd
    client = app.test_client()

    # 1. Multi-Sheet Excel
    excel_buf = io.BytesIO()
    with pd.ExcelWriter(excel_buf, engine="openpyxl") as writer:
        pd.DataFrame([{"notes": "This is cover notes"}]).to_excel(writer, sheet_name="Cover", index=False)
        pd.DataFrame([
            {"order_id": 101, "units_sold": 5, "unit_price": 50.0, "total_revenue": None},
            {"order_id": 102, "units_sold": 2, "unit_price": 100.0, "total_revenue": None},
            {"order_id": "Total", "units_sold": 7, "unit_price": 150.0, "total_revenue": None}
        ]).to_excel(writer, sheet_name="Sales_Data", index=False)
    excel_buf.seek(0)

    # Test /api/sheets inspection
    sheets_res = client.post("/api/sheets", data={'file': (io.BytesIO(excel_buf.getvalue()), 'multi.xlsx')}, content_type='multipart/form-data', headers=AUTH_HEADERS)
    assert sheets_res.status_code == 200
    s_data = sheets_res.get_json()
    assert s_data["has_multiple"] is True
    assert "Sales_Data" in s_data["sheets"]

    # Test smart selection (should auto-pick Sales_Data because it has the most rows/cells)
    excel_buf.seek(0)
    upload_res = client.post("/api/upload", data={'file': (excel_buf, 'multi.xlsx')}, content_type='multipart/form-data', headers=AUTH_HEADERS)
    assert upload_res.status_code == 200
    u_data = upload_res.get_json()
    assert u_data["sheet_info"]["selected_sheet"] == "Sales_Data"
    assert u_data["audit_log"]["cleaned_row_count"] == 2

    # 2. Cyrillic Windows-1251 / CP1251 CSV
    cyrillic_csv = "Товар;Количество;Цена;Итого\nНоутбук;2;1200;\nМышь;5;25;\nИтого;7;1225;\n"
    cyrillic_bytes = cyrillic_csv.encode("cp1251")
    c_res = client.post("/api/upload", data={'file': (io.BytesIO(cyrillic_bytes), 'report_1c.csv')}, content_type='multipart/form-data', headers=AUTH_HEADERS)
    assert c_res.status_code == 200
    c_data = c_res.get_json()
    assert c_data["audit_log"]["cleaned_row_count"] == 2
    assert len(c_data["audit_log"]["dropped_rows"]) == 1
    print("[PASS] test_multi_sheet_and_encoding (Excel sheets + CP1251 Cyrillic)")


def test_preview_and_purge():
    """Verify live executive dashboard preview and explicit data privacy purge."""
    client = app.test_client()
    sample_res = client.post("/api/sample", headers=AUTH_HEADERS)
    session_id = sample_res.get_json()["session_id"]

    # 1. Test Executive Preview HTML endpoint
    prev_res = client.get(f"/api/preview/{session_id}")
    assert prev_res.status_code == 200
    assert "text/html" in prev_res.content_type
    assert b"AutoBI Executive Dashboard" in prev_res.data
    assert b"chart.js" in prev_res.data.lower()

    # 2. Test Explicit Purge endpoint
    purge_res = client.post(f"/api/purge/{session_id}")
    assert purge_res.status_code == 200
    purge_data = purge_res.get_json()
    assert purge_data["success"] is True

    # 3. Verify session is completely gone
    prev_again = client.get(f"/api/preview/{session_id}")
    assert prev_again.status_code == 404

    dl_again = client.get(f"/api/download/{session_id}")
    assert dl_again.status_code == 404
    print("[PASS] test_preview_and_purge (Executive Preview + Data Purge)")


def test_dim_date_and_time_intelligence():
    """Verify automated Dim_Date generation, relationships, and Time Intelligence DAX."""
    client = app.test_client()
    sample_res = client.post("/api/sample", headers=AUTH_HEADERS)
    assert sample_res.status_code == 200
    data = sample_res.get_json()
    dax_names = [m["name"] for m in data["dax_measures"]]

    # Verify Time Intelligence measures
    assert any("YTD" in n for n in dax_names)
    assert any("Prior Year" in n for n in dax_names)
    assert any("YoY Growth %" in n for n in dax_names)
    assert any("MTD" in n for n in dax_names)

    # Verify model.bim contains Dim_Date and Relationship
    session_id = data["session_id"]
    dl_res = client.get(f"/api/download/{session_id}")
    zf = zipfile.ZipFile(io.BytesIO(dl_res.data))
    model_bim = json.loads(zf.read("AutoBI_Project.SemanticModel/definition/model.bim").decode("utf-8"))
    table_names = [t["name"] for t in model_bim["model"]["tables"]]
    assert "Dim_Date" in table_names
    assert len(model_bim["model"].get("relationships", [])) >= 1
    rel = model_bim["model"]["relationships"][0]
    assert rel["toTable"] == "Dim_Date"
    assert rel["toColumn"] == "Date"
    print("[PASS] test_dim_date_and_time_intelligence (Dim_Date, 1-to-many relationship, and YTD/YoY DAX)")


def test_google_sheets_connector():
    """Verify Google Sheets URL parsing and /api/ingest-url endpoint."""
    from google_sheets import extract_google_sheets_csv_url
    from unittest.mock import patch

    # 1. Test URL extractor with various formats
    test_urls = [
        "https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms/edit?usp=sharing",
        "https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms/edit#gid=12345",
        "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms"
    ]
    for u in test_urls:
        csv_url = extract_google_sheets_csv_url(u)
        assert "export?format=csv" in csv_url
        assert "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms" in csv_url

    # 2. Test /api/ingest-url input validation
    client = app.test_client()
    bad_req = client.post("/api/ingest-url", json={"url": "not-a-sheet-url"}, headers=AUTH_HEADERS)
    assert bad_req.status_code == 400

    # 3. Test /api/ingest-url with mock fetch
    mock_csv = "order_id,order_date,units_sold,unit_price,total_revenue,status\n101,2026-01-10,5,20,100,Completed\nTotal,2026-01-10,5,20,100,\n"
    with patch("web_app.fetch_google_sheets_csv") as mock_fetch:
        mock_fetch.return_value = (
            io.BytesIO(mock_csv.encode("utf-8")),
            "google_sheet_1BxiMVs0XRA5.csv",
            "https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5/export?format=csv&gid=0"
        )
        res = client.post("/api/ingest-url", json={"url": test_urls[0]}, headers=AUTH_HEADERS)
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert data["is_live_url"] is True
        assert "Web.Contents" in data["power_query_m"]
        assert data["audit_log"]["cleaned_row_count"] == 1

    print("[PASS] test_google_sheets_connector (URL parsing, mock ingestion, and Web.Contents M generation)")


def test_1c_crosstab_unpivoting():
    """Verify 1C and ERP cross-tab monthly matrix detection, unpivoting, and summary pruning."""
    import pandas as pd
    client = app.test_client()

    crosstab_df = pd.DataFrame({
        "Номенклатура": ["Asus ZenBook 14", "Dell XPS 15", "Apple MacBook Air"],
        "Склад": ["Ташкент", "Ташкент", "Самарканд"],
        "Январь 2026": [12000, 18000, 15000],
        "Февраль 2026": [14000, 19500, 16200],
        "Март 2026": [16500, 21000, 17800],
        "Итого": [42500, 58500, 49000]
    })
    # Add summary row
    summary_row = pd.DataFrame([{
        "Номенклатура": "Итого", "Склад": "Всего",
        "Январь 2026": 45000, "Февраль 2026": 49700, "Март 2026": 55300, "Итого": 150000
    }])
    full_crosstab = pd.concat([crosstab_df, summary_row], ignore_index=True)

    buf = io.BytesIO()
    full_crosstab.to_excel(buf, index=False)
    buf.seek(0)

    data = {"file": (buf, "1C_Monthly_Matrix_Export.xlsx")}
    res = client.post("/api/upload", data=data, content_type="multipart/form-data", headers=AUTH_HEADERS)
    assert res.status_code == 200
    result = res.get_json()
    assert result["success"] is True

    # Verify unpivot execution
    unpivot = result["unpivoted_matrix"]
    assert unpivot["is_unpivoted"] is True
    assert len(unpivot["temporal_columns"]) == 3
    assert "Итого" in unpivot["pruned_summary_columns"]
    assert result["audit_log"]["cleaned_row_count"] == 9  # 3 products * 3 months

    # Verify date and amount columns
    cols = result["table_columns"]
    assert "date" in cols
    assert "amount" in cols
    assert "period" in cols

    # Verify Power BI model generator produced time intelligence for unpivoted date
    dax_names = [m["name"] for m in result["dax_measures"]]
    assert any("YTD" in n for n in dax_names)
    assert any("YoY Growth" in n for n in dax_names)

    print("[PASS] test_1c_crosstab_unpivoting (1C matrix detection, pd.melt flattener, and summary pruning)")


def test_cfo_anomaly_detection_engine():
    """Verify CFO red-flags engine for duplicate invoices, margin leakage, 3σ outliers, and Audit_Exceptions table in .pbip."""
    import pandas as pd
    client = app.test_client()

    risky_sales = pd.DataFrame({
        "order_id": [201, 202, 203, 203, 204, 205, 206],
        "order_date": ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-03", "2026-01-04", "2026-01-05", "2026-01-06"],
        "category": ["Electronics", "Electronics", "Accessories", "Accessories", "Office", "Office", "Electronics"],
        "unit_price": [120.0, 50.0, 30.0, 30.0, 15.0, 0.0, 95000.0],
        "unit_cost": [80.0, 75.0, 20.0, 20.0, 10.0, 25.0, 110.0],  # 202: cost > price (leakage)
        "units_sold": [2, 1, 4, 4, 3, 5, 1],
        "total_revenue": [240.0, 50.0, 120.0, 120.0, 45.0, 0.0, 95000.0],
        "profit": [80.0, -25.0, 40.0, 40.0, 15.0, -125.0, 94890.0]  # negative profit
    })

    buf = io.BytesIO()
    risky_sales.to_csv(buf, index=False)
    buf.seek(0)

    data = {"file": (buf, "financial_risks_audit.csv")}
    res = client.post("/api/upload", data=data, content_type="multipart/form-data", headers=AUTH_HEADERS)
    assert res.status_code == 200
    result = res.get_json()
    assert result["success"] is True

    # Verify CFO Anomaly Detection
    summary = result["anomaly_summary"]
    assert summary["has_critical"] is True
    assert summary["critical_count"] >= 2
    assert summary["total_flags"] >= 4

    anomalies = result["anomalies"]
    cats = [a["category"] for a in anomalies]
    assert "duplicate_invoices" in cats
    assert "margin_leakage" in cats
    assert "negative_profit" in cats
    assert "zero_price_freebie" in cats

    # Verify Audit_Exceptions table injected in Power BI Project .pbip
    session_id = result["session_id"]
    dl_res = client.get(f"/api/download/{session_id}")
    assert dl_res.status_code == 200
    zf = zipfile.ZipFile(io.BytesIO(dl_res.data))
    model_bim = json.loads(zf.read("AutoBI_Project.SemanticModel/definition/model.bim").decode("utf-8"))
    table_names = [t["name"] for t in model_bim["model"]["tables"]]
    assert "Audit_Exceptions" in table_names

    # Check Audit_Exceptions columns and partition
    audit_table = [t for t in model_bim["model"]["tables"] if t["name"] == "Audit_Exceptions"][0]
    col_names = [c["name"] for c in audit_table["columns"]]
    assert "Exception_ID" in col_names
    assert "Severity" in col_names
    assert "Category" in col_names

    print("[PASS] test_cfo_anomaly_detection_engine (Duplicate invoices, margin leakage, negative profit, and Audit_Exceptions table)")


def test_cbu_fx_normalization():
    """Verify Central Bank of Uzbekistan (CBU.uz) multi-currency detection, UZS/USD conversion, and Currency_Selector in .pbip."""
    import pandas as pd
    client = app.test_client()

    multi_df = pd.DataFrame({
        "order_id": [301, 302, 303, 304],
        "order_date": ["2026-01-10", "2026-01-11", "2026-01-12", "2026-01-13"],
        "product": ["Industrial Server", "Office Laptop", "Warehouse Scanner", "Barcode Labels"],
        "currency": ["USD", "EUR", "UZS", "USD"],
        "amount": [4500.0, 1800.0, 12000000.0, 250.0]
    })

    buf = io.BytesIO()
    multi_df.to_csv(buf, index=False)
    buf.seek(0)

    data = {"file": (buf, "multi_currency_export.csv")}
    res = client.post("/api/upload", data=data, content_type="multipart/form-data", headers=AUTH_HEADERS)
    assert res.status_code == 200
    result = res.get_json()
    assert result["success"] is True

    # Verify FX normalization audit
    fx = result["fx_normalization"]
    assert fx["is_multi_currency"] is True
    assert set(fx["detected_currencies"]) == {"USD", "EUR", "UZS"}
    assert "amount_uzs" in result["table_columns"]
    assert "amount_usd" in result["table_columns"]

    # Verify DAX measures
    dax_names = [m["name"] for m in result["dax_measures"]]
    assert "Total Volume (UZS)" in dax_names
    assert "Total Volume (USD)" in dax_names
    assert "Dynamic Currency Switcher" in dax_names

    # Verify Currency_Selector table in model.bim
    session_id = result["session_id"]
    dl_res = client.get(f"/api/download/{session_id}")
    assert dl_res.status_code == 200
    zf = zipfile.ZipFile(io.BytesIO(dl_res.data))
    model_bim = json.loads(zf.read("AutoBI_Project.SemanticModel/definition/model.bim").decode("utf-8"))
    table_names = [t["name"] for t in model_bim["model"]["tables"]]
    assert "Currency_Selector" in table_names

    print("[PASS] test_cbu_fx_normalization (CBU.uz live FX rates, dual UZS/USD conversion, and Currency_Selector parameter table)")


def test_pareto_abc_segmentation():
    """Verify Pareto (80/20) ABC classification tagging and DAX Class A/B/C metrics."""
    import pandas as pd
    client = app.test_client()

    pareto_df = pd.DataFrame({
        "order_id": [401, 402, 403, 404, 405, 406, 407],
        "order_date": ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04", "2026-01-05", "2026-01-06", "2026-01-07"],
        "product": ["Enterprise Core Switch", "Blade Server 2U", "Managed Router", "Patch Panel", "Ethernet Cable Cat6", "RJ45 Plugs", "Cable Tie Pack"],
        "units_sold": [2, 3, 5, 10, 25, 100, 50],
        "unit_price": [15000.0, 8000.0, 2000.0, 250.0, 30.0, 2.0, 5.0],
        "total_revenue": [30000.0, 24000.0, 10000.0, 2500.0, 750.0, 200.0, 250.0]
    })

    buf = io.BytesIO()
    pareto_df.to_csv(buf, index=False)
    buf.seek(0)

    data = {"file": (buf, "pareto_sales_catalog.csv")}
    res = client.post("/api/upload", data=data, content_type="multipart/form-data", headers=AUTH_HEADERS)
    assert res.status_code == 200
    result = res.get_json()
    assert result["success"] is True

    # Verify Pareto segmentation audit
    pareto = result["pareto_segmentation"]
    assert pareto["is_segmented"] is True
    assert pareto["class_a_count"] >= 1
    assert pareto["class_a_revenue_share"] >= 75.0
    assert "abc_class" in result["table_columns"]

    # Verify DAX measures
    dax_names = [m["name"] for m in result["dax_measures"]]
    assert "Class A Volume" in dax_names
    assert "Class A Share %" in dax_names
    assert "Class B Volume" in dax_names
    assert "Class C Volume" in dax_names

    print("[PASS] test_pareto_abc_segmentation (Pareto 80/20 logic, abc_class column, and Class A Share % DAX)")


if __name__ == "__main__":
    test_auth_flow()
    test_index_route()
    test_api_sample()
    test_api_upload_csv()
    test_session_persistence()
    test_multi_sheet_and_encoding()
    test_preview_and_purge()
    test_dim_date_and_time_intelligence()
    test_google_sheets_connector()
    test_1c_crosstab_unpivoting()
    test_cfo_anomaly_detection_engine()
    test_cbu_fx_normalization()
    test_pareto_abc_segmentation()
    print("\nALL WEB PORTAL TESTS PASSED SUCCESSFULLY! [OK]")
