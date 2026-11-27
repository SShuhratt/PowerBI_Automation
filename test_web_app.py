"""
test_web_app.py - Automated test suite for AutoBI Web Portal backend endpoints.
"""

import io
import json
import zipfile
from unittest.mock import patch
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
    assert b"heroStoryStage" in res.data
    assert b"schema3dCanvas" in res.data
    assert b"domain3dCanvas" in res.data
    assert b"landing3d.js" in res.data
    assert b"theme.js" in res.data
    assert b"themeToggleBtn" in res.data
    assert b"/studio" in res.data
    assert b"/privacy" in res.data
    assert b"/terms" in res.data
    assert b"support@autobi.uz" in res.data
    assert b"autobi-icon.svg" in res.data
    assert b"favicon.svg" in res.data
    assert b"i18n.js" in res.data
    assert b"lang-switcher" in res.data
    assert b'data-theme="dark"' in res.data

    # Light theme persistence via ?theme=light -> autobi_theme cookie -> /studio
    res_light = client.get("/?theme=light")
    assert res_light.status_code == 200
    assert b'data-theme="light"' in res_light.data

    # Studio workspace route inherits persisted theme and renders upload dropzone
    studio_res = client.get("/studio")
    assert studio_res.status_code == 200
    assert b'data-theme="light"' in studio_res.data
    assert b"dropzone" in studio_res.data
    assert b"Zero-Persistence Guarantee" in studio_res.data
    assert b"Download Power BI Starter Kit" in studio_res.data
    assert b"themeToggleBtn" in studio_res.data

    # Legacy demo query on / redirects cleanly to /studio?demo=sales
    redir_res = client.get("/?demo=sales")
    assert redir_res.status_code == 302
    assert "/studio?demo=sales" in (redir_res.headers.get("Location") or "")

    # Landing page Phase 1: zero-login live demo sandbox & pricing tiers
    assert b"publicDemoChart1" in res.data
    assert b"pricing" in res.data
    assert b"$19" in res.data and b"$59" in res.data

    # Public read-only demo API works without authentication and blocks invalid domains
    pub_sales = client.get("/api/public-demo/sales")
    assert pub_sales.status_code == 200
    pub_json = pub_sales.get_json()
    assert pub_json["success"] is True
    assert len(pub_json["kpis"]) >= 3
    assert "chart1" in pub_json["charts"]

    pub_fin = client.get("/api/public-demo/finance")
    assert pub_fin.status_code == 200
    assert pub_fin.get_json()["domain"]["key"] == "finance"

    assert client.get("/api/public-demo/invalid_domain").status_code == 400
    print("[PASS] test_index_route (3D landing, zero-login demo sandbox, pricing & /studio workspace)")


def test_brand_assets():
    client = app.test_client()
    for path, expected_mime in [
        ("/favicon.ico", "image/"),
        ("/apple-touch-icon.png", "image/png"),
        ("/static/img/autobi-icon.svg", "image/svg+xml"),
        ("/static/img/autobi-logo.svg", "image/svg+xml"),
        ("/static/img/favicon.svg", "image/svg+xml"),
        ("/static/img/favicon-32x32.png", "image/png"),
        ("/static/site.webmanifest", "application/"),
        ("/static/js/i18n.js", "javascript"),
        ("/static/js/theme.js", "javascript"),
        ("/static/js/landing3d.js", "javascript"),
    ]:
        res = client.get(path)
        assert res.status_code == 200, f"Expected 200 on {path}, got {res.status_code}"
        assert expected_mime in (res.content_type or ""), f"Unexpected mime for {path}: {res.content_type}"
    print("[PASS] test_brand_assets (SVG logo, icons, favicon, manifest, theme.js, i18n.js & landing3d.js)")


def test_legal_pages():
    cases = [
        ("/privacy", "en", b"Privacy Policy"),
        ("/privacy?lang=ru", "ru", "Политика конфиденциальности".encode("utf-8")),
        ("/privacy?lang=uz", "uz", b"Maxfiylik siyosati"),
        ("/terms", "en", b"Terms of Service"),
        ("/terms?lang=ru", "ru", "Условия использования".encode("utf-8")),
        ("/terms?lang=uz", "uz", b"Foydalanish shartlari"),
    ]
    for path, expected_lang, expected_heading in cases:
        client = app.test_client()
        res = client.get(path)
        assert res.status_code == 200, f"Expected 200 on {path}, got {res.status_code}"
        assert f'<html lang="{expected_lang}"'.encode("utf-8") in res.data
        assert expected_heading in res.data
        assert b"support@autobi.uz" in res.data

    # Verify explicit ?lang= persists via autobi_lang cookie onto subsequent navigation
    cookie_client = app.test_client()
    res_uz = cookie_client.get("/privacy?lang=uz")
    assert res_uz.status_code == 200
    assert b'<html lang="uz"' in res_uz.data
    res_terms_persisted = cookie_client.get("/terms")
    assert res_terms_persisted.status_code == 200
    assert b'<html lang="uz"' in res_terms_persisted.data
    assert b"Foydalanish shartlari" in res_terms_persisted.data
    print("[PASS] test_legal_pages (/privacy & /terms in EN/RU/UZ + cookie persistence)")


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
    # Unauthenticated download is blocked
    assert client.get(f"/api/download/{session_id}").status_code == 401
    dl_res = client.get(f"/api/download/{session_id}", headers=AUTH_HEADERS)
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
    dl_res = client.get(f"/api/download/{test_id}", headers=AUTH_HEADERS)
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

    # 2. Test Explicit Purge endpoint (unauth blocked, auth succeeds)
    assert client.post(f"/api/purge/{session_id}").status_code == 401
    purge_res = client.post(f"/api/purge/{session_id}", headers=AUTH_HEADERS)
    assert purge_res.status_code == 200
    purge_data = purge_res.get_json()
    assert purge_data["success"] is True

    # 3. Verify session is completely gone
    prev_again = client.get(f"/api/preview/{session_id}")
    assert prev_again.status_code == 404

    dl_again = client.get(f"/api/download/{session_id}", headers=AUTH_HEADERS)
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
    dl_res = client.get(f"/api/download/{session_id}", headers=AUTH_HEADERS)
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
    dl_res = client.get(f"/api/download/{session_id}", headers=AUTH_HEADERS)
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
    dl_res = client.get(f"/api/download/{session_id}", headers=AUTH_HEADERS)
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


def test_telegram_executive_dispatcher():
    """Verify Telegram config and dispatch endpoints, message builder, and document attachment."""
    client = app.test_client()

    # 1. Unauthenticated request rejected
    unauth_res = client.get("/api/telegram/config")
    assert unauth_res.status_code == 401

    # 2. Authenticated config check
    config_res = client.get("/api/telegram/config", headers=AUTH_HEADERS)
    assert config_res.status_code == 200
    cfg = config_res.get_json()
    assert "configured" in cfg
    assert "has_token" in cfg
    assert "chat_id_configured" in cfg

    # 3. Validation: missing session_id
    bad_req = client.post("/api/telegram/dispatch", json={}, headers=AUTH_HEADERS)
    assert bad_req.status_code == 400
    assert "Missing session_id" in bad_req.get_json()["error"]

    # 4. Validation: invalid session_id
    not_found = client.post("/api/telegram/dispatch", json={"session_id": "nonexistent_session_123"}, headers=AUTH_HEADERS)
    assert not_found.status_code == 404

    # 5. Validation: missing bot token and chat id when environment is empty
    sample_res = client.post("/api/sample", headers=AUTH_HEADERS)
    assert sample_res.status_code == 200
    session_id = sample_res.get_json()["session_id"]

    with patch("telegram_client.get_default_telegram_config", return_value=(None, None)):
        no_creds = client.post(
            "/api/telegram/dispatch",
            json={"session_id": session_id},
            headers=AUTH_HEADERS
        )
        assert no_creds.status_code == 400
        assert "Telegram Bot Token is required" in no_creds.get_json()["error"]

    # 6. Successful dispatch with mocked Telegram API
    mock_msg_resp = {"ok": True, "result": {"message_id": 9901}}
    mock_doc_resp = {"ok": True, "result": {"message_id": 9902}}

    with patch("telegram_client.send_telegram_message", return_value=mock_msg_resp) as mock_msg, \
         patch("telegram_client.send_telegram_document", return_value=mock_doc_resp) as mock_doc:

        dispatch_res = client.post(
            "/api/telegram/dispatch",
            json={
                "session_id": session_id,
                "chat_id": "@board_directors",
                "bot_token": "123456789:ABCDEF_TEST_TOKEN"
            },
            headers=AUTH_HEADERS
        )
        assert dispatch_res.status_code == 200
        disp_data = dispatch_res.get_json()
        assert disp_data["success"] is True
        assert disp_data["message_id"] == 9901
        assert disp_data["document_id"] == 9902

        # Verify mock calls
        assert mock_msg.called
        msg_text = mock_msg.call_args[0][0]
        assert "AutoBI Executive Digest" in msg_text
        assert "Executive Key Performance Indicators" in msg_text
        assert mock_msg.call_args[0][1] == "@board_directors"
        assert mock_msg.call_args[0][2] == "123456789:ABCDEF_TEST_TOKEN"

        assert mock_doc.called
        doc_bytes = mock_doc.call_args[0][0]
        assert b"<!DOCTYPE html>" in doc_bytes or len(doc_bytes) > 100
        assert mock_doc.call_args[1]["filename"].startswith("Executive_Dashboard_")
        assert mock_doc.call_args[1]["filename"].endswith(".html")
        assert mock_doc.call_args[1]["chat_id"] == "@board_directors"

    # 7. Deep linking auto-detect polling test
    import uuid
    from telegram_client import upsert_subscriber
    unique_code = f"code_{uuid.uuid4().hex[:8]}"
    poll_unfound = client.get(f"/api/telegram/poll-connection?code={unique_code}", headers=AUTH_HEADERS)
    assert poll_unfound.status_code == 200
    assert poll_unfound.get_json()["connected"] is False

    # Simulate user tapping Start on Telegram bot with parameter unique_code
    upsert_subscriber({
        "chat_id": 77665544,
        "username": "executive_director",
        "first_name": "Executive",
        "last_start_param": unique_code
    })
    poll_found = client.get(f"/api/telegram/poll-connection?code={unique_code}", headers=AUTH_HEADERS)
    assert poll_found.status_code == 200
    assert poll_found.get_json()["connected"] is True
    assert poll_found.get_json()["chat_id"] == 77665544
    assert poll_found.get_json()["username"] == "executive_director"

    # 8. Multi-recipient dispatch with link & username resolution
    with patch("telegram_client.send_telegram_message", return_value=mock_msg_resp) as multi_msg, \
         patch("telegram_client.send_telegram_document", return_value=mock_doc_resp) as multi_doc:

        multi_res = client.post(
            "/api/telegram/dispatch",
            json={
                "session_id": session_id,
                "targets": [
                    "https://t.me/company_board_channel",
                    "@executive_director",
                    "11223344"
                ],
                "bot_token": "123456789:ABCDEF_TEST_TOKEN"
            },
            headers=AUTH_HEADERS
        )
        assert multi_res.status_code == 200
        multi_data = multi_res.get_json()
        assert multi_data["success"] is True
        assert multi_data["dispatched_count"] == 3
        assert len(multi_data["dispatched"]) == 3

        # Verify normalized destinations
        dests = [d["destination"] for d in multi_data["dispatched"]]
        assert "@company_board_channel" in dests
        assert "77665544" in dests  # Resolved from @executive_director!
        assert "11223344" in dests

    print("[PASS] test_telegram_executive_dispatcher (Config, 1-click deep link polling, multi-recipient dispatch, and URL resolution)")


def test_cybersecurity_and_hardening():
    """Verify security controls: view-only shared link isolation, cookie HMAC signing, rate-limiting, CSV injection defense, SSRF validation, and security headers."""
    import pandas as pd
    from web_app import sign_auth_token, verify_auth_token, sanitize_df_for_csv_export, FAILED_LOGINS
    from telegram_client import send_telegram_message

    client = app.test_client()

    # 1. View-Only Shared Link vs Operational Action Restrictions
    sample_res = client.post("/api/sample", headers=AUTH_HEADERS)
    assert sample_res.status_code == 200
    session_id = sample_res.get_json()["session_id"]

    # Shared link preview is accessible without authentication (view-only)
    preview_res = client.get(f"/api/preview/{session_id}")
    assert preview_res.status_code == 200
    assert "text/html" in preview_res.content_type

    # All operational actions MUST fail without authentication (401 Unauthorized)
    assert client.get(f"/api/download/{session_id}").status_code == 401
    assert client.post(f"/api/purge/{session_id}").status_code == 401
    assert client.post("/api/sheets").status_code == 401
    assert client.post("/api/upload").status_code == 401
    assert client.post("/api/telegram/dispatch", json={"session_id": session_id}).status_code == 401

    # 2. Cryptographic Cookie Tampering Defense
    # Unsigned/tampered cookie must be rejected
    client.set_cookie("autobi_user", "ceo@enterprise.com")
    status_tampered = client.get("/api/auth/status")
    assert status_tampered.get_json()["authenticated"] is False

    # Signed cookie must succeed
    signed_token = sign_auth_token("cfo@enterprise.com")
    client.set_cookie("autobi_user", signed_token)
    status_signed = client.get("/api/auth/status")
    assert status_signed.get_json()["authenticated"] is True
    assert status_signed.get_json()["user"] == "cfo@enterprise.com"

    # Clear cookie for subsequent checks
    client.set_cookie("autobi_user", "")

    # 3. Login Brute-Force Rate Limiter (5 attempts per IP)
    test_ip = "198.51.100.42"
    FAILED_LOGINS[test_ip] = []
    for _ in range(5):
        client.post("/api/auth/login", json={"passcode": "wrong_guess"}, environ_overrides={"REMOTE_ADDR": test_ip})

    rate_limited_res = client.post("/api/auth/login", json={"passcode": "autobi2026"}, environ_overrides={"REMOTE_ADDR": test_ip})
    assert rate_limited_res.status_code == 429
    assert "Too many failed login attempts" in rate_limited_res.get_json()["error"]
    del FAILED_LOGINS[test_ip]

    # 3b. Cloudflare CF-Connecting-IP isolation & HTTPS Secure cookie flag
    proxy_ip = "10.0.1.5"
    FAILED_LOGINS.pop("203.0.113.10", None)
    FAILED_LOGINS.pop("203.0.113.11", None)
    for _ in range(5):
        client.post(
            "/api/auth/login",
            json={"passcode": "wrong_guess"},
            headers={"CF-Connecting-IP": "203.0.113.10"},
            environ_overrides={"REMOTE_ADDR": proxy_ip},
        )
    assert client.post(
        "/api/auth/login",
        json={"passcode": "autobi2026"},
        headers={"CF-Connecting-IP": "203.0.113.10"},
        environ_overrides={"REMOTE_ADDR": proxy_ip},
    ).status_code == 429

    # Different client behind the same reverse proxy must NOT be locked out
    https_login = client.post(
        "/api/auth/login",
        json={"passcode": "autobi2026"},
        headers={"CF-Connecting-IP": "203.0.113.11", "X-Forwarded-Proto": "https"},
        environ_overrides={"REMOTE_ADDR": proxy_ip},
    )
    assert https_login.status_code == 200
    set_cookie_hdr = https_login.headers.get("Set-Cookie", "")
    assert "Secure" in set_cookie_hdr
    assert "HttpOnly" in set_cookie_hdr
    FAILED_LOGINS.pop("203.0.113.10", None)
    client.set_cookie("autobi_user", "")

    # 4. CSV Formula / DDE Injection Sanitization
    malicious_df = pd.DataFrame({
        "item": ["=CMD|' /C calc'!A0", "+100", "-50.25", "@SUM(1,2)", "Normal Product", "\t=MALICIOUS()"],
        "price": [10.0, 20.0, 30.0, 40.0, 50.0, 60.0]
    })
    safe_df = sanitize_df_for_csv_export(malicious_df)
    items = list(safe_df["item"])
    assert items[0] == "'=CMD|' /C calc'!A0"
    assert items[1] == "+100"       # Pure number string is untouched
    assert items[2] == "-50.25"     # Pure negative number is untouched
    assert items[3] == "'@SUM(1,2)"
    assert items[4] == "Normal Product"
    assert items[5] == "'\t=MALICIOUS()"

    # 5. Security Headers
    headers_res = client.get("/")
    assert headers_res.headers.get("X-Content-Type-Options") == "nosniff"
    assert headers_res.headers.get("X-Frame-Options") == "SAMEORIGIN"
    assert headers_res.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert "Content-Security-Policy" in headers_res.headers

    # 6. Telegram Bot Token SSRF Validation
    try:
        send_telegram_message("Test", chat_id="123456", bot_token="http://attacker.com/leak")
        assert False, "Should have raised ValueError on malicious bot_token SSRF attempt"
    except ValueError as e:
        assert "Invalid Telegram Bot Token format" in str(e)

    # 7. Telegram Connection Code Enforcement
    no_code_poll = client.get("/api/telegram/poll-connection", headers=AUTH_HEADERS)
    assert no_code_poll.status_code == 400
    assert "Connection code required" in no_code_poll.get_json()["error"]

    print("[PASS] test_cybersecurity_and_hardening (View-only shared link, HMAC cookie signing, login rate limiter, DDE sanitization, SSRF guard, security headers)")


def test_encrypted_user_vault_and_registration():
    """Verify zero credential prefill, user registration, salted scrypt passwords, and AES-256-GCM DB encryption."""
    import sqlite3
    import uuid
    from security_vault import users_vault, blind_index_email
    from session_store import sessions

    client = app.test_client()

    # 1. Auth modal in /studio must NEVER prefill analyst@enterprise.local and must use novalidate
    studio_html = client.get("/studio").data.decode("utf-8")
    assert "analyst@enterprise.local" not in studio_html
    assert 'id="authForm"' in studio_html
    assert "novalidate" in studio_html
    assert 'id="authTabRegister"' in studio_html

    # 2. Register a unique user via /api/auth/register
    test_email = f"vault_{uuid.uuid4().hex[:8]}@autobi.uz"
    test_pw = "StrongPass#2026!"
    reg_res = client.post("/api/auth/register", json={
        "full_name": "Test Analyst",
        "email": test_email,
        "password": test_pw,
    })
    assert reg_res.status_code == 200
    assert reg_res.get_json()["success"] is True
    assert reg_res.get_json()["user"] == test_email

    # Duplicate email registration must fail with 409
    dup_res = client.post("/api/auth/register", json={"email": test_email, "password": test_pw})
    assert dup_res.status_code == 409
    assert dup_res.get_json()["error_code"] == "auth_email_exists"

    # Registered user must NOT accept legacy shared passcode instead of their real password
    client.post("/api/auth/logout")
    bypass_res = client.post("/api/auth/login", json={"email": test_email, "password": "autobi2026"})
    assert bypass_res.status_code == 401

    # Registered user signs in cleanly with their own password
    login_res = client.post("/api/auth/login", json={"email": test_email, "password": test_pw})
    assert login_res.status_code == 200
    assert login_res.get_json()["user"] == test_email

    # 3. Verify raw DB rows have zero plaintext email, name, password, or spreadsheet payloads
    e_hash = blind_index_email(test_email)
    with sqlite3.connect(users_vault.db_path) as conn:
        u_row = conn.execute(
            "SELECT email_hash, encrypted_profile, password_hash FROM users WHERE email_hash = ?;",
            (e_hash,),
        ).fetchone()
    assert u_row is not None
    assert u_row[0] == e_hash
    assert u_row[1].startswith("enc:v1:")
    assert test_email not in u_row[1]
    assert "Test Analyst" not in u_row[1]
    assert u_row[2].startswith("scrypt$")
    assert test_pw not in u_row[2]

    # Trigger an encrypted session write via /api/sample
    sample_res = client.post("/api/sample", json={"domain": "generic"})
    assert sample_res.status_code == 200
    sid = sample_res.get_json()["session_id"]
    with sqlite3.connect(sessions.db_path) as conn:
        s_row = conn.execute("SELECT payload FROM sessions WHERE session_id = ?;", (sid,)).fetchone()
    assert s_row is not None
    assert s_row[0].startswith("enc:v1:")
    assert "Tashkent Central" not in s_row[0]
    assert "Aziz Karimov" not in s_row[0]
    client.post(f"/api/purge/{sid}")
    print("[PASS] test_encrypted_user_vault_and_registration (Zero prefill, registration, scrypt & AES-256-GCM DB at rest)")


def test_custom_generic_schema_and_sticky_header():
    """Verify universal/custom dataset support (any columns -> BI) and sticky persistent navbar."""
    client = app.test_client()

    # 1. Custom CSV completely unrelated to the 5 domains (e.g., Clinic Visits / SLA)
    custom_csv = (
        "clinic_id,visit_date,doctor_specialty,patient_wait_minutes,visit_fee_points\n"
        "CL-101,2026-02-01,Cardiology,14.5,120\n"
        "CL-102,2026-02-02,Neurology,22.0,150\n"
        "CL-103,2026-02-03,Cardiology,11.0,130\n"
    )
    res = client.post(
        "/api/upload",
        data={"file": (io.BytesIO(custom_csv.encode("utf-8")), "clinic_custom.csv")},
        content_type="multipart/form-data",
        headers=AUTH_HEADERS,
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert data["domain"]["key"] == "generic"
    assert len(data["kpis"]) >= 5
    dax_names = [m["name"] for m in data["dax_measures"]]
    assert "Total Records" in dax_names
    assert any("Wait Minutes" in n or "Visit Fee" in n for n in dax_names)

    # 2. Download custom dataset ZIP
    sid = data["session_id"]
    dl = client.get(f"/api/download/{sid}", headers=AUTH_HEADERS)
    assert dl.status_code == 200
    assert dl.mimetype == "application/zip"
    client.post(f"/api/purge/{sid}", headers=AUTH_HEADERS)

    # 3. Sticky header CSS verification
    css_res = client.get("/static/css/style.css")
    assert css_res.status_code == 200
    css_text = css_res.data.decode("utf-8")
    assert "position: sticky;" in css_text
    assert "--bg-header-sticky" in css_text

    # 4. Human-readable headers & meaningful custom charts (no col_/snake_case boilerplate)
    solow_csv = (
        "Davr,Kapital (K),Mahsulot (Y),Investitsiya (I),90% ga erishish holati\n"
        "1,100.0,320.5,48.1,Erishilmadi\n"
        "2,115.2,342.8,51.4,Erishilmadi\n"
        "3,131.0,367.2,55.0,Erishilmadi\n"
        "4,149.5,392.0,58.8,ERISHILDI (>=90%)\n"
        "5,168.1,418.4,62.7,ERISHILDI (>=90%)\n"
        "6,188.0,445.9,66.9,ERISHILDI (>=90%)\n"
    )
    solow_res = client.post(
        "/api/upload",
        data={"file": (io.BytesIO(solow_csv.encode("utf-8")), "solow_custom.csv")},
        content_type="multipart/form-data",
        headers=AUTH_HEADERS,
    )
    assert solow_res.status_code == 200
    solow = solow_res.get_json()
    assert solow["domain"]["key"] == "generic"
    assert solow["display_labels"]["col_90_ga_erishish_holati"] == "90% ga erishish holati"
    assert solow["display_labels"]["kapital"] == "Kapital (K)"

    c1 = solow["charts"].get("chart1", {})
    c2 = solow["charts"].get("chart2", {})
    assert c1 and c2
    assert "Field Fill Rate" not in c1.get("title", "")
    assert "col_90" not in c1.get("title", "").lower() and "col_90" not in c2.get("title", "").lower()
    assert not c2.get("title", "").startswith("Davr by")
    assert c1.get("type") == "line"
    assert c2.get("type") == "doughnut"
    assert c1.get("series_label") and c2.get("series_label")
    assert all("col_" not in k["label"].lower() for k in solow["kpis"])
    client.post(f"/api/purge/{solow['session_id']}", headers=AUTH_HEADERS)
    print("[PASS] test_custom_generic_schema_and_sticky_header (Custom dataset BI pipeline, clean labels & persistent sticky header)")


def test_interactive_chart_builder_and_slicers():
    """Verify server-side slicers and customizable chart aggregations via /api/session/<id>/query."""
    client = app.test_client()
    sample_res = client.post("/api/sample", json={"domain": "sales"}, headers=AUTH_HEADERS)
    assert sample_res.status_code == 200
    s_data = sample_res.get_json()
    sid = s_data["session_id"]

    # Interactive schema exposed cleanly
    schema = s_data.get("interactive_schema") or {}
    assert len(schema.get("numeric_cols", [])) >= 1
    assert len(schema.get("dimension_cols", [])) >= 1

    # Unauthenticated query blocked
    assert client.post(f"/api/session/{sid}/query", json={}).status_code == 401

    # Filter by category + override chart1 & chart2
    first_cat = schema["slicers"][0]["values"][0] if schema.get("slicers") else None
    slicer_col = schema["slicers"][0]["key"] if schema.get("slicers") else None
    filters = {slicer_col: first_cat} if slicer_col else {}

    q_res = client.post(
        f"/api/session/{sid}/query",
        json={
            "filters": filters,
            "chart_overrides": {
                "chart1": {"type": "line", "dim": "region", "metric": "total_revenue", "agg": "avg"},
                "chart2": {"type": "bar", "dim": "status", "metric": "__count__", "agg": "count"},
            },
            "save": True,
        },
        headers=AUTH_HEADERS,
    )
    assert q_res.status_code == 200
    q_json = q_res.get_json()
    assert q_json["success"] is True
    assert q_json["charts"]["chart1"]["type"] == "line"
    assert "Average Total Revenue" in q_json["charts"]["chart1"]["title"]
    assert q_json["charts"]["chart2"]["type"] == "bar"
    assert q_json["row_count"] <= q_json["total_row_count"]

    # Invalid column safely rejected with 400
    bad_res = client.post(
        f"/api/session/{sid}/query",
        json={"chart_overrides": {"chart1": {"type": "bar", "dim": "no_such_col", "metric": "total_revenue", "agg": "sum"}}},
        headers=AUTH_HEADERS,
    )
    assert bad_res.status_code == 400

    # Customized charts persist into HTML executive preview
    prev_res = client.get(f"/api/preview/{sid}")
    assert prev_res.status_code == 200
    assert b"Average Total Revenue" in prev_res.data
    client.post(f"/api/purge/{sid}", headers=AUTH_HEADERS)
    print("[PASS] test_interactive_chart_builder_and_slicers (Full-dataset filters & Chart Builder overrides)")


def test_saved_reports_and_mom_refresh():
    """Verify AES-256-GCM encrypted Saved Reports gallery, strict owner isolation, and MoM deltas on refresh."""
    import sqlite3
    import uuid
    from reports_store import reports_store

    client_a = app.test_client()
    client_b = app.test_client()

    # Register two separate isolated users
    email_a = f"owner_a_{uuid.uuid4().hex[:6]}@enterprise.local"
    email_b = f"owner_b_{uuid.uuid4().hex[:6]}@enterprise.local"
    assert client_a.post("/api/auth/register", json={"full_name": "Owner A", "email": email_a, "password": "Password123!"}).status_code == 200
    assert client_b.post("/api/auth/register", json={"full_name": "Owner B", "email": email_b, "password": "Password123!"}).status_code == 200

    # User A uploads Period 1 sales CSV
    csv_jan = (
        "order_id,order_date,region,category,units_sold,unit_price,total_revenue,status\n"
        "101,2026-01-05,Tashkent,Electronics,10,100.0,,Completed\n"
        "102,2026-01-12,Samarkand,Furniture,5,200.0,,Completed\n"
    )
    up_res = client_a.post("/api/upload", data={"file": (io.BytesIO(csv_jan.encode()), "jan_sales.csv")}, content_type="multipart/form-data")
    assert up_res.status_code == 200
    sid = up_res.get_json()["session_id"]

    # Save report
    save_res = client_a.post("/api/reports", json={"session_id": sid, "title": "Monthly Secret Retail", "period_label": "2026-01"})
    assert save_res.status_code == 201
    rid = save_res.get_json()["report"]["report_id"]

    # Verify AES-256-GCM encryption at rest in reports.db (no plaintext title or data)
    with sqlite3.connect(reports_store.db_path) as conn:
        row = conn.execute("SELECT encrypted_meta FROM saved_reports WHERE report_id = ?;", (rid,)).fetchone()
    assert row is not None
    assert row[0].startswith("enc:v1:")
    assert "Monthly Secret Retail" not in row[0]

    # Cross-user isolation: User B cannot list, open, refresh, or delete User A's report
    assert not any(r["report_id"] == rid for r in client_b.get("/api/reports").get_json()["reports"])
    assert client_b.get(f"/api/reports/{rid}").status_code == 404
    assert client_b.delete(f"/api/reports/{rid}").status_code == 404

    # User A refreshes with Period 2 CSV (+50% higher revenue) -> MoM delta computed
    csv_feb = (
        "order_id,order_date,region,category,units_sold,unit_price,total_revenue,status\n"
        "201,2026-02-05,Tashkent,Electronics,15,100.0,,Completed\n"
        "202,2026-02-12,Samarkand,Furniture,7.5,200.0,,Completed\n"
    )
    ref_res = client_a.post(
        f"/api/reports/{rid}/refresh",
        data={"file": (io.BytesIO(csv_feb.encode()), "feb_sales.csv"), "period_label": "2026-02"},
        content_type="multipart/form-data",
    )
    assert ref_res.status_code == 200
    ref_json = ref_res.get_json()
    rev_kpi = [k for k in ref_json["kpis"] if "Revenue" in k["label"]][0]
    assert rev_kpi["delta_dir"] == "up"
    assert "+50.0%" in rev_kpi["delta_text"]

    # Reopen saved report -> hydrates download-ready session
    open_res = client_a.get(f"/api/reports/{rid}")
    assert open_res.status_code == 200
    open_json = open_res.get_json()
    assert len(open_json["snapshot_history"]) == 2
    assert client_a.get(f"/api/download/{open_json['session_id']}").status_code == 200

    # Delete report permanently
    assert client_a.delete(f"/api/reports/{rid}").status_code == 200
    assert client_a.get(f"/api/reports/{rid}").status_code == 404
    print("[PASS] test_saved_reports_and_mom_refresh (Encrypted gallery, owner isolation & MoM deltas)")


def test_scheduled_telegram_digests():
    """Verify encrypted digest scheduling, multi-worker lease lock, anomaly-only gating & test-run."""
    import sqlite3
    import time
    from unittest.mock import patch
    from scheduler_service import scheduler_service

    client = app.test_client()
    # Upload dataset with a negative profit anomaly so anomaly check triggers cleanly
    csv_anom = (
        "account_id,account_name,category,revenue,expenses,profit\n"
        "GL-1,Retail Store,Sales,1000,1500,-500\n"
        "GL-2,Online Store,Sales,5000,2000,3000\n"
    )
    up = client.post(
        "/api/upload",
        data={"file": (io.BytesIO(csv_anom.encode()), "sched_fin.csv")},
        content_type="multipart/form-data",
        headers=AUTH_HEADERS,
    )
    assert up.status_code == 200
    sid = up.get_json()["session_id"]

    rep_res = client.post("/api/reports", json={"session_id": sid, "title": "Weekly CFO Finance"}, headers=AUTH_HEADERS)
    assert rep_res.status_code == 201
    rid = rep_res.get_json()["report"]["report_id"]

    # Create encrypted schedule
    sc_res = client.post(
        f"/api/reports/{rid}/schedule",
        json={"cadence": "daily", "hour_utc": 4, "targets": ["@cfo_alerts"], "alert_only_on_anomalies": True, "enabled": True},
        headers=AUTH_HEADERS,
    )
    assert sc_res.status_code == 200
    assert sc_res.get_json()["schedule"]["cadence"] == "daily"

    # Raw schedule config is encrypted at rest
    with sqlite3.connect(scheduler_service.db_path) as conn:
        srow = conn.execute("SELECT encrypted_config FROM report_schedules WHERE report_id = ?;", (rid,)).fetchone()
    assert srow and srow[0].startswith("enc:v1:")
    assert "@cfo_alerts" not in srow[0]

    # Lease lock stops concurrent multi-worker double execution
    assert scheduler_service.acquire_lease("test_tick_lock", "worker-1", ttl_seconds=30) is True
    assert scheduler_service.acquire_lease("test_tick_lock", "worker-2", ttl_seconds=30) is False
    scheduler_service.release_lease("test_tick_lock", "worker-1")

    # Run due schedule via mocked Telegram dispatcher
    with patch("telegram_client.dispatch_executive_report", return_value={"success": True, "dispatched_count": 1}) as mock_disp:
        # Force schedule due immediately and execute tick
        scheduler_service.upsert_schedule(
            owner_email="api-client@autobi.local",
            report_id=rid,
            cadence="daily",
            targets=["@cfo_alerts"],
            alert_only_on_anomalies=True,
            next_run_at=time.time() - 5,
        )
        from web_app import _execute_scheduled_refresh_job, _dispatch_telegram_job
        tick = scheduler_service.run_due_schedules(_execute_scheduled_refresh_job, _dispatch_telegram_job)
        assert tick["acquired"] is True
        assert tick["executed"] >= 1
        assert mock_disp.called

        # Next tick should NOT fire again because next_run_at moved to tomorrow
        mock_disp.reset_mock()
        tick2 = scheduler_service.run_due_schedules(_execute_scheduled_refresh_job, _dispatch_telegram_job)
        assert tick2["executed"] == 0
        assert not mock_disp.called

    # Clean up
    assert client.delete(f"/api/reports/{rid}", headers=AUTH_HEADERS).status_code == 200
    print("[PASS] test_scheduled_telegram_digests (Encrypted schedules, lease lock, anomaly gating & Telegram dispatch)")


def test_regional_presets_and_sql_connector():
    """Verify amoCRM/Bitrix24, Uzum Market, Payme/Click export enrichment and Read-Only SQL connector security."""
    import sqlite3
    from unittest.mock import patch
    from sql_connector import validate_select_only_sql, validate_db_uri_safe, mask_db_uri

    client = app.test_client()

    # 1. amoCRM / Bitrix24 Russian deal export
    crm_csv = (
        "ID сделки,Этап сделки,Ответственный,Бюджет,Дата создания\n"
        "D-1,Успешно реализовано,Sardorbek,4500,2026-11-01\n"
        "D-2,Переговоры,Madina,2800,2026-11-03\n"
        "D-3,Отказ клиента,Timur,1200,2026-11-05\n"
    )
    crm_res = client.post(
        "/api/upload",
        data={"file": (io.BytesIO(crm_csv.encode("utf-8")), "amocrm_deals.csv")},
        content_type="multipart/form-data",
        headers=AUTH_HEADERS,
    )
    assert crm_res.status_code == 200
    crm_json = crm_res.get_json()
    assert (crm_json.get("regional_preset") or {}).get("key") == "amocrm_bitrix"
    assert crm_json["domain"]["key"] == "sales"
    assert any(k["label"] == "Cancellation Rate" for k in crm_json["kpis"])

    # 2. Uzum Market Seller export -> net_payout computed cleanly
    uzum_csv = (
        "Артикул,Товар,Комиссия,Логистика,Выручка\n"
        "SKU-10,Headphones,150,50,1000\n"
        "SKU-11,Keyboard,90,30,600\n"
    )
    uzum_res = client.post(
        "/api/upload",
        data={"file": (io.BytesIO(uzum_csv.encode("utf-8")), "uzum_seller.csv")},
        content_type="multipart/form-data",
        headers=AUTH_HEADERS,
    )
    assert uzum_res.status_code == 200
    uzum_json = uzum_res.get_json()
    assert (uzum_json.get("regional_preset") or {}).get("key") == "uzum_market"
    assert uzum_json["table_records"][0]["net_payout"] == 800.0

    # 3. Payme / Click Merchant statement -> net_amount + duplicate tx flag
    payme_csv = (
        "transaction_id,payment_method,сумма,комиссия\n"
        "TX-5001,Payme,500000,10000\n"
        "TX-5001,Payme,500000,10000\n"
        "TX-5002,Click,250000,5000\n"
    )
    payme_res = client.post(
        "/api/upload",
        data={"file": (io.BytesIO(payme_csv.encode("utf-8")), "payme_statement.csv")},
        content_type="multipart/form-data",
        headers=AUTH_HEADERS,
    )
    assert payme_res.status_code == 200
    payme_json = payme_res.get_json()
    assert (payme_json.get("regional_preset") or {}).get("key") == "payme_click"
    assert payme_json["table_records"][0]["net_amount"] == 490000.0
    assert any(a["category"] == "duplicate_invoices" for a in payme_json["anomalies"])

    # 4. SQL Connector static & SSRF security checks
    for bad_sql in ["DROP TABLE users", "DELETE FROM orders WHERE 1=1", "SELECT 1; DROP TABLE x", "UPDATE sales SET a=1"]:
        try:
            validate_select_only_sql(bad_sql)
            raise AssertionError(f"Expected blocked SQL for {bad_sql}")
        except ValueError:
            pass

    for bad_uri in [
        "sqlite:///D:/secret.db",
        "postgresql://user:pass@169.254.169.254:5432/meta",
        "postgresql://user:pass@127.0.0.1:5432/localdb",
        "mysql://user:pass@localhost:3306/localdb",
    ]:
        try:
            validate_db_uri_safe(bad_uri)
            raise AssertionError(f"Expected blocked URI for {bad_uri}")
        except ValueError:
            pass

    assert mask_db_uri("postgresql://analyst:supersecret99@db.example.com:5432/prod_sales") == "postgresql://db.example.com:5432/prod_sales"

    # Unauthenticated request blocked (401); blocked SQL over HTTP rejected (400)
    assert client.post("/api/ingest-sql", json={"uri": "postgresql://u:p@db.example.com:5432/db", "query": "SELECT 1"}).status_code == 401
    assert client.post("/api/ingest-sql", json={"uri": "postgresql://u:p@db.example.com:5432/db", "query": "DROP TABLE x"}, headers=AUTH_HEADERS).status_code == 400
    assert client.post("/api/ingest-sql", json={"uri": "postgresql://u:p@169.254.169.254:5432/db", "query": "SELECT 1"}, headers=AUTH_HEADERS).status_code == 400

    # Mocked PostgreSQL ingestion succeeds and never leaks password
    import pandas as pd
    mock_df = pd.DataFrame([
        {"order_id": 1, "order_date": "2026-11-01", "category": "Tech", "units_sold": 3, "unit_price": 200.0, "status": "Completed"},
        {"order_id": 2, "order_date": "2026-11-02", "category": "Tech", "units_sold": 2, "unit_price": 150.0, "status": "Completed"},
    ])
    with patch("web_app.fetch_readonly_sql_df", return_value=(mock_df, "postgresql://db.example.com:5432/prod_sales")):
        sql_res = client.post(
            "/api/ingest-sql",
            json={"uri": "postgresql://analyst:supersecret99@db.example.com:5432/prod_sales", "query": "SELECT * FROM orders LIMIT 10"},
            headers=AUTH_HEADERS,
        )
        assert sql_res.status_code == 200
        sql_text = sql_res.data.decode("utf-8")
        assert "supersecret99" not in sql_text
        assert sql_res.get_json()["filename"] == "postgresql://db.example.com:5432/prod_sales"

    # CRM & Uzum demo endpoints run cleanly
    assert client.post("/api/sample", json={"domain": "crm"}, headers=AUTH_HEADERS).status_code == 200
    assert client.post("/api/sample", json={"domain": "uzum"}, headers=AUTH_HEADERS).status_code == 200
    print("[PASS] test_regional_presets_and_sql_connector (amoCRM/Bitrix24, Uzum, Payme/Click & Read-Only SQL security)")


def test_telegram_webapp_and_interactive_bot():
    """Verify Telegram Mini App (/tg-app, initData HMAC auth) and interactive webhook commands & chat uploads."""
    import hashlib
    import hmac as std_hmac
    import json as std_json
    import time
    import urllib.parse
    from unittest.mock import patch

    client = app.test_client()
    test_bot_token = "123456789:ABCDEF1234567890abcdef1234567890abc"

    # 1. /tg-app Mini App shell renders telegram-web-app.js and Telegram frame-ancestors CSP
    tg_res = client.get("/tg-app")
    assert tg_res.status_code == 200
    assert b"telegram-web-app.js" in tg_res.data
    assert b"tg-webapp-mode" in tg_res.data
    csp_hdr = tg_res.headers.get("Content-Security-Policy", "")
    assert "https://telegram.org" in csp_hdr
    assert "https://web.telegram.org" in csp_hdr

    # 2. Cryptographically signed Telegram.WebApp.initData authentication
    user_json = std_json.dumps({"id": 99887766, "first_name": "Shuhrat", "username": "shuhrat_tg", "language_code": "uz"})
    auth_date = str(int(time.time()))
    params = {"auth_date": auth_date, "query_id": "AAEAAAE", "user": user_json}
    data_check = "\n".join(f"{k}={params[k]}" for k in sorted(params.keys()))
    secret_key = std_hmac.new(b"WebAppData", test_bot_token.encode("utf-8"), hashlib.sha256).digest()
    sig_hash = std_hmac.new(secret_key, data_check.encode("utf-8"), hashlib.sha256).hexdigest()
    init_data = urllib.parse.urlencode({**params, "hash": sig_hash})

    # Tampered initData is rejected with 401
    assert client.post("/api/auth/telegram-webapp", json={"init_data": init_data + "tamper", "bot_token": test_bot_token}).status_code == 401

    # Valid signed initData authenticates into encrypted tg_99887766@telegram.autobi.uz workspace
    auth_res = client.post("/api/auth/telegram-webapp", json={"init_data": init_data, "bot_token": test_bot_token})
    assert auth_res.status_code == 200
    auth_json = auth_res.get_json()
    assert auth_json["success"] is True
    assert auth_json["user"] == "tg_99887766@telegram.autobi.uz"
    signed_token = auth_json["token"]

    # 3. Signed bearer token unlocks /api/session/<sid> without needing cookie
    sample_res = client.post("/api/sample", json={"domain": "sales"}, headers={"X-AutoBI-Token": signed_token})
    assert sample_res.status_code == 200
    sid = sample_res.get_json()["session_id"]
    sess_res = client.get(f"/api/session/{sid}", headers={"X-AutoBI-Token": signed_token})
    assert sess_res.status_code == 200
    assert sess_res.get_json()["session_id"] == sid

    # 4. Interactive webhook rejects forged secret headers
    forged_wh = client.post(
        "/api/telegram/webhook",
        json={"message": {"chat": {"id": 99887766, "type": "private"}, "text": "/start"}},
        headers={"X-Telegram-Bot-Api-Secret-Token": "wrong_secret"},
    )
    assert forged_wh.status_code == 403

    # 5. Webhook /start + /demo + direct chat CSV upload trigger Mini App inline buttons
    from web_app import _tg_webhook_secret
    wh_headers = {"X-Telegram-Bot-Api-Secret-Token": _tg_webhook_secret()}
    csv_bytes = b"order_id,order_date,category,units_sold,unit_price,status\n1,2026-11-01,Tech,4,250,Completed\n2,2026-11-02,Tech,2,150,Completed\n"

    with patch("telegram_client.get_default_telegram_config", return_value=(test_bot_token, "99887766")), \
         patch("telegram_client.send_telegram_message", return_value={"ok": True, "result": {"message_id": 11}}) as mock_msg, \
         patch("telegram_client.send_telegram_document", return_value={"ok": True, "result": {"message_id": 12}}) as mock_doc, \
         patch("telegram_client.download_telegram_file", return_value=(io.BytesIO(csv_bytes), "tg_chat_sales.csv")):

        start_wh = client.post(
            "/api/telegram/webhook",
            json={"message": {"chat": {"id": 99887766, "type": "private", "username": "shuhrat_tg"}, "text": "/start"}},
            headers=wh_headers,
        )
        assert start_wh.status_code == 200
        assert start_wh.get_json()["handled"] == "start"
        markup_sent = mock_msg.call_args.kwargs.get("reply_markup") or {}
        assert "web_app" in str(markup_sent)

        doc_wh = client.post(
            "/api/telegram/webhook",
            json={"message": {
                "chat": {"id": 99887766, "type": "private", "username": "shuhrat_tg"},
                "document": {"file_id": "BQACAgIAAx0C_TEST", "file_name": "tg_chat_sales.csv"}
            }},
            headers=wh_headers,
        )
        assert doc_wh.status_code == 200
        doc_json = doc_wh.get_json()
        assert doc_json["handled"] == "document"
        doc_sid = doc_json["session_id"]
        assert mock_doc.called
        last_markup = mock_msg.call_args.kwargs.get("reply_markup") or {}
        assert f"?session={doc_sid}" in str(last_markup)

    print("[PASS] test_telegram_webapp_and_interactive_bot (Telegram Mini App initData HMAC, /tg-app & interactive webhook)")


if __name__ == "__main__":
    test_auth_flow()
    test_index_route()
    test_brand_assets()
    test_legal_pages()
    test_encrypted_user_vault_and_registration()
    test_custom_generic_schema_and_sticky_header()
    test_interactive_chart_builder_and_slicers()
    test_saved_reports_and_mom_refresh()
    test_scheduled_telegram_digests()
    test_regional_presets_and_sql_connector()
    test_telegram_webapp_and_interactive_bot()
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
    test_telegram_executive_dispatcher()
    test_cybersecurity_and_hardening()
    print("\nALL WEB PORTAL TESTS PASSED SUCCESSFULLY! [OK]")
