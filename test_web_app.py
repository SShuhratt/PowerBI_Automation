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


if __name__ == "__main__":
    test_index_route()
    test_api_sample()
    test_api_upload_csv()
    print("\nALL WEB PORTAL TESTS PASSED SUCCESSFULLY! [OK]")
