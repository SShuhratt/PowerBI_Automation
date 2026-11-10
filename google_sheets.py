"""
google_sheets.py - Google Sheets URL Parser and Live Ingestion Connector
Extracts direct CSV export endpoints from public Google Sheets sharing links
and fetches data for automated self-healing and Power BI semantic modeling.
"""

import re
import urllib.request
import urllib.error
import io
from typing import Tuple


def extract_google_sheets_csv_url(url_or_id: str) -> str:
    """
    Extracts the direct CSV export URL from any public Google Sheets link or ID.
    Supports formats:
    - https://docs.google.com/spreadsheets/d/{ID}/edit#gid={GID}
    - https://docs.google.com/spreadsheets/d/{ID}/edit?usp=sharing
    - https://docs.google.com/spreadsheets/d/{ID}/export?format=csv
    - Raw spreadsheet ID
    """
    url = url_or_id.strip()
    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", url)
    if match:
        sheet_id = match.group(1)
    elif re.match(r"^[a-zA-Z0-9-_]{20,}$", url):
        sheet_id = url
    else:
        raise ValueError("Invalid Google Sheets link. Please provide a valid docs.google.com/spreadsheets URL.")

    # Extract gid (tab identifier) if present
    gid_match = re.search(r"[#&?]gid=([0-9]+)", url)
    gid = gid_match.group(1) if gid_match else "0"

    return f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"


def fetch_google_sheets_csv(url_or_id: str, timeout: int = 15) -> Tuple[io.BytesIO, str, str]:
    """
    Fetches the CSV bytes from a Google Sheets URL.
    Returns: (BytesIO buffer, filename, csv_export_url)
    """
    csv_url = extract_google_sheets_csv_url(url_or_id)
    req = urllib.request.Request(
        csv_url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AutoBI/1.0"
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            max_bytes = 32 * 1024 * 1024  # 32MB max limit
            data = response.read(max_bytes + 1)
            if len(data) > max_bytes:
                raise ValueError("Google Sheet exceeds the 32MB maximum download limit.")
            # If Google redirects to an HTML login page, it's not public
            if b"<html" in data[:400].lower() and (b"google" in data[:400].lower() or b"sign in" in data[:400].lower()):
                raise PermissionError("The Google Sheet is private. Please set link sharing to 'Anyone with the link can view'.")

            sheet_id = csv_url.split("/")[5][:12]
            filename = f"google_sheet_{sheet_id}.csv"
            return io.BytesIO(data), filename, csv_url
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            raise PermissionError("Google Sheet access denied. Ensure the link sharing is set to 'Anyone with the link can view'.")
        raise RuntimeError(f"HTTP error {e.code} fetching Google Sheet: {e.reason}")
    except urllib.error.URLError as e:
        raise ConnectionError(f"Could not connect to Google Sheets: {e.reason}")

