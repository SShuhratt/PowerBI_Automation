"""
regional_presets.py - Uzbekistan & CIS Business Export Normalization Presets
Detects and enriches spreadsheet/CSV exports from amoCRM, Bitrix24, Uzum Market
Seller cabinets, and Payme / Click merchant statements with zero LLC API lock-in.
"""

from typing import Any, Dict, List
import pandas as pd


def _find_first(cols: List[str], keywords: List[str]) -> str:
    for kw in keywords:
        for c in cols:
            if c == kw:
                return c
    for kw in keywords:
        for c in cols:
            if kw in c:
                return c
    return ""


def enrich_regional_preset(
    df: pd.DataFrame,
    display_labels: Dict[str, str],
    audit_log: Dict[str, Any],
) -> pd.DataFrame:
    """Detect CRM (amoCRM/Bitrix24) or regional (Uzum/Payme/Click) exports and map canonical BI columns."""
    cols = [str(c) for c in df.columns]
    cols_lower = [c.lower() for c in cols]

    # 1. amoCRM / Bitrix24 CRM Deal Export Preset
    crm_stage_col = _find_first(cols_lower, ["этап_сделки", "etap_sdelki", "стадия", "stadiya", "stage", "deal_stage", "voronka", "воронка"])
    crm_owner_col = _find_first(cols_lower, ["ответственный", "otvetstvennyy", "responsible", "менеджер", "sales_rep", "manager", "masul"])
    crm_amt_col = _find_first(cols_lower, ["бюджет", "byudjet", "budget", "сумма_сделки", "deal_amount", "summa_sdelki"])

    if crm_stage_col and (crm_owner_col or crm_amt_col):
        df = df.copy()
        if "sales_rep" not in cols_lower and crm_owner_col:
            df["sales_rep"] = df[crm_owner_col].astype(str)
            display_labels.setdefault("sales_rep", display_labels.get(crm_owner_col, "Manager"))
        if "category" not in cols_lower:
            df["category"] = df[crm_stage_col].astype(str)
            display_labels.setdefault("category", display_labels.get(crm_stage_col, "Deal Stage"))
        if "total_revenue" not in cols_lower and crm_amt_col and pd.api.types.is_numeric_dtype(df[crm_amt_col]):
            df["total_revenue"] = df[crm_amt_col]
            display_labels.setdefault("total_revenue", display_labels.get(crm_amt_col, "Deal Value"))
        if "status" not in cols_lower:
            def _map_crm_status(val: Any) -> str:
                s = str(val or "").strip().lower()
                if any(w in s for w in ["успешно", "реализовано", "won", "closed won", "completed", "muvaffaqiyat", "paid"]):
                    return "Completed"
                if any(w in s for w in ["отказ", "закрыто и не", "lost", "cancelled", "rejected", "bekor"]):
                    return "Cancelled"
                return "Pending"
            df["status"] = df[crm_stage_col].map(_map_crm_status)
            display_labels.setdefault("status", "Deal Status")

        audit_log["regional_preset"] = {
            "key": "amocrm_bitrix",
            "label": "amoCRM / Bitrix24 Deal Funnel",
            "mapped_columns": [c for c in ["sales_rep", "category", "total_revenue", "status"] if c in df.columns],
        }
        return df

    # 2. Uzum Market Seller Report Preset
    uzum_comm = _find_first(cols_lower, ["комиссия", "komissiya", "commission", "uzum_fee", "marketplace_fee"])
    uzum_log = _find_first(cols_lower, ["логистика", "logistika", "logistics", "delivery_fee", "dostavka"])
    uzum_sku = _find_first(cols_lower, ["артикул", "artikul", "sku", "product_id", "tovar", "товар", "mahsulot"])
    uzum_rev = _find_first(cols_lower, ["выручка", "tushum", "revenue", "total_revenue", "цена", "price", "summa_prodazh"])

    if uzum_sku and (uzum_comm or uzum_log):
        df = df.copy()
        if "sku" not in cols_lower:
            df["sku"] = df[uzum_sku].astype(str)
            display_labels.setdefault("sku", display_labels.get(uzum_sku, "SKU"))
        if "total_revenue" not in cols_lower and uzum_rev and pd.api.types.is_numeric_dtype(df[uzum_rev]):
            df["total_revenue"] = df[uzum_rev]
            display_labels.setdefault("total_revenue", display_labels.get(uzum_rev, "Gross Sales"))
        if "net_payout" not in cols_lower and uzum_rev and pd.api.types.is_numeric_dtype(df[uzum_rev]):
            comm_series = df[uzum_comm].fillna(0.0) if uzum_comm and pd.api.types.is_numeric_dtype(df[uzum_comm]) else 0.0
            log_series = df[uzum_log].fillna(0.0) if uzum_log and pd.api.types.is_numeric_dtype(df[uzum_log]) else 0.0
            df["net_payout"] = (df[uzum_rev].fillna(0.0) - comm_series - log_series).round(2)
            display_labels.setdefault("net_payout", "Net Seller Payout")
        if "category" not in cols_lower:
            df["category"] = df[uzum_sku].astype(str)
            display_labels.setdefault("category", display_labels.get(uzum_sku, "Product / SKU"))

        audit_log["regional_preset"] = {
            "key": "uzum_market",
            "label": "Uzum Market Seller Export",
            "mapped_columns": [c for c in ["sku", "total_revenue", "net_payout", "category"] if c in df.columns],
        }
        return df

    # 3. Payme / Click Merchant Statement Preset
    tx_col = _find_first(cols_lower, ["transaction_id", "tranzaksiya", "id_транзакции", "id_платежа", "payme_id", "click_id"])
    fee_col = _find_first(cols_lower, ["комиссия", "komissiya", "fee", "merchant_fee", "эквайринг"])
    amt_col = _find_first(cols_lower, ["сумма", "summa", "amount", "total_amount"])
    pay_sys = _find_first(cols_lower, ["метод_оплаты", "payment_method", "система", "provider", "gateway"])

    if tx_col and amt_col and (fee_col or pay_sys):
        df = df.copy()
        if "revenue" not in cols_lower and pd.api.types.is_numeric_dtype(df[amt_col]):
            df["revenue"] = df[amt_col]
            display_labels.setdefault("revenue", display_labels.get(amt_col, "Payment Amount"))
        if fee_col and pd.api.types.is_numeric_dtype(df[fee_col]):
            if "expenses" not in cols_lower:
                df["expenses"] = df[fee_col]
                display_labels.setdefault("expenses", display_labels.get(fee_col, "Gateway Fee"))
            if "net_amount" not in cols_lower and pd.api.types.is_numeric_dtype(df[amt_col]):
                df["net_amount"] = (df[amt_col].fillna(0.0) - df[fee_col].fillna(0.0)).round(2)
                display_labels.setdefault("net_amount", "Net Settlement")
        if "category" not in cols_lower and pay_sys:
            df["category"] = df[pay_sys].astype(str)
            display_labels.setdefault("category", display_labels.get(pay_sys, "Payment Gateway"))

        audit_log["regional_preset"] = {
            "key": "payme_click",
            "label": "Payme / Click Merchant Statement",
            "mapped_columns": [c for c in ["revenue", "expenses", "net_amount", "category"] if c in df.columns],
        }
        return df

    return df
