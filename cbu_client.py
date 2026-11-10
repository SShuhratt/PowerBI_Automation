"""
cbu_client.py - Central Bank of Uzbekistan (CBU.uz) Live FX Client
Fetches real-time and historical currency rates with local caching and offline fallback.
Official endpoint: https://cbu.uz/uz/arkhiv-kursov-valyut/json/
"""

import os
import json
import time
import urllib.request
import urllib.error
from typing import Dict, Any, Tuple

CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".sessions", "cbu_rates.json")
CACHE_TTL_SECONDS = 43200  # 12 hours

# Fallback baseline rates if offline or API unreachable
FALLBACK_RATES = {
    "USD": 12000.0,
    "EUR": 13420.0,
    "RUB": 145.8,
    "GBP": 16080.0,
    "JPY": 76.0,
    "CNY": 1660.0,
    "KZT": 24.5,
    "UZS": 1.0,
    "SOM": 1.0,
    "СУМ": 1.0,
    "SO'M": 1.0
}


def normalize_currency_code(raw_str: str) -> str:
    """Standardizes various currency representations to 3-letter ISO code."""
    if not raw_str:
        return "UZS"
    s = str(raw_str).strip().upper()
    if "$" in s or "USD" in s or "ДОЛЛАР" in s:
        return "USD"
    if "€" in s or "EUR" in s or "ЕВРО" in s:
        return "EUR"
    if "₽" in s or "RUB" in s or "РУБ" in s:
        return "RUB"
    if "£" in s or "GBP" in s:
        return "GBP"
    if "¥" in s or "JPY" in s or "CNY" in s:
        return "CNY" if "CNY" in s else "JPY"
    if any(k in s for k in ["UZS", "SO'M", "SOM", "СУМ", "СЎМ"]):
        return "UZS"
    return s[:3] if len(s) >= 3 else "UZS"


def get_cbu_rates() -> Tuple[Dict[str, float], Dict[str, Any]]:
    """
    Retrieves current FX rates against UZS.
    Returns:
        rates: dict mapping currency code to rate in UZS (e.g. {'USD': 11994.1, 'UZS': 1.0})
        metadata: dict with source ('live', 'cached', 'fallback') and fetch details.
    """
    now = time.time()

    # 1. Check local cache
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                cached = json.load(f)
            cached_time = cached.get("timestamp", 0)
            if (now - cached_time) < CACHE_TTL_SECONDS and "rates" in cached:
                return cached["rates"], {
                    "source": "cached",
                    "cache_age_hours": round((now - cached_time) / 3600, 1),
                    "cbu_date": cached.get("cbu_date", "Today")
                }
        except Exception:
            pass

    # 2. Fetch from official CBU open JSON API
    url = "https://cbu.uz/uz/arkhiv-kursov-valyut/json/"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (AutoBI-Enterprise-Analytics)"}
    )
    try:
        with urllib.request.urlopen(req, timeout=4) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        rates = {"UZS": 1.0, "SOM": 1.0, "СУМ": 1.0, "SO'M": 1.0}
        cbu_date = "Today"
        for item in data:
            ccy = item.get("Ccy", "").upper()
            rate_val = float(str(item.get("Rate", "0")).replace(",", "."))
            if ccy and rate_val > 0:
                rates[ccy] = rate_val
            if not cbu_date or cbu_date == "Today":
                cbu_date = item.get("Date", "Today")

        # Save to local cache
        try:
            os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump({
                    "timestamp": now,
                    "cbu_date": cbu_date,
                    "rates": rates
                }, f, indent=2)
        except Exception:
            pass

        return rates, {
            "source": "live",
            "cbu_date": cbu_date,
            "provider": "Central Bank of Uzbekistan (CBU.uz)"
        }

    except Exception as e:
        # 3. Fallback to cached (even if expired) or hardcoded baseline
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    cached = json.load(f)
                return cached.get("rates", FALLBACK_RATES), {
                    "source": "cached_fallback",
                    "warning": f"Live CBU request failed ({e}). Used cached rates.",
                    "cbu_date": cached.get("cbu_date", "Historical")
                }
            except Exception:
                pass

        return FALLBACK_RATES.copy(), {
            "source": "fallback",
            "warning": f"Live CBU request failed ({e}). Used standard baseline table.",
            "cbu_date": "Baseline Standard"
        }
