"""
test_web_app.py - Automated test suite for AutoBI Web Portal backend endpoints.
"""

import io
import json
import zipfile
from web_app import app


def test_index_route():
    client = app.test_client()
    res = client.get("/")
    assert res.status_code == 200
    assert b"AutoBI Studio" in res.data
    assert b"dropzone" in res.data
    assert b"Download Power BI Starter Kit" in res.data
    print("[PASS] test_index_route")


def test_api_sample():
    client = app.test_client()
    res = client.post("/api/sample")
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

    # Verify ZIP contents
    zf = zipfile.ZipFile(io.BytesIO(dl_res.data))
    namelist = zf.namelist()
    assert "cleaned_data.csv" in namelist
    assert "LoadData.m" in namelist
    assert "dax_measures.dax" in namelist
    assert "POWER_BI_MEASURES_CHEATSHEET.md" in namelist
    assert "audit_log.json" in namelist
    assert "Executive_Dashboard_Preview.html" in namelist
    assert "QuickLaunch_PowerBI.bat" in namelist
    assert "README.txt" in namelist

    print("[PASS] test_api_sample & test_download_zip")


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
    res = client.post("/api/upload", data=data, content_type='multipart/form-data')
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
    sheets_res = client.post("/api/sheets", data={'file': (io.BytesIO(excel_buf.getvalue()), 'multi.xlsx')}, content_type='multipart/form-data')
    assert sheets_res.status_code == 200
    s_data = sheets_res.get_json()
    assert s_data["has_multiple"] is True
    assert "Sales_Data" in s_data["sheets"]

    # Test smart selection (should auto-pick Sales_Data because it has the most rows/cells)
    excel_buf.seek(0)
    upload_res = client.post("/api/upload", data={'file': (excel_buf, 'multi.xlsx')}, content_type='multipart/form-data')
    assert upload_res.status_code == 200
    u_data = upload_res.get_json()
    assert u_data["sheet_info"]["selected_sheet"] == "Sales_Data"
    assert u_data["audit_log"]["cleaned_row_count"] == 2

    # 2. Cyrillic Windows-1251 / CP1251 CSV
    cyrillic_csv = "Товар;Количество;Цена;Итого\nНоутбук;2;1200;\nМышь;5;25;\nИтого;7;1225;\n"
    cyrillic_bytes = cyrillic_csv.encode("cp1251")
    c_res = client.post("/api/upload", data={'file': (io.BytesIO(cyrillic_bytes), 'report_1c.csv')}, content_type='multipart/form-data')
    assert c_res.status_code == 200
    c_data = c_res.get_json()
    assert c_data["audit_log"]["cleaned_row_count"] == 2
    assert len(c_data["audit_log"]["dropped_rows"]) == 1
    print("[PASS] test_multi_sheet_and_encoding (Excel sheets + CP1251 Cyrillic)")


def test_preview_and_purge():
    """Verify live executive dashboard preview and explicit data privacy purge."""
    client = app.test_client()
    sample_res = client.post("/api/sample")
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


if __name__ == "__main__":
    test_index_route()
    test_api_sample()
    test_api_upload_csv()
    test_session_persistence()
    test_multi_sheet_and_encoding()
    test_preview_and_purge()
    print("\nALL WEB PORTAL TESTS PASSED SUCCESSFULLY! [OK]")
