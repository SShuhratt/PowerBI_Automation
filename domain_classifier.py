"""
domain_classifier.py - Intelligent Domain Classification Engine
Analyzes spreadsheet schemas and column signatures to automatically detect
the business domain (Sales, Marketing, HR, Inventory, Finance, Generic)
and guide downstream DAX modeling and visualization.
"""

from typing import Dict, List, Any
import pandas as pd


DOMAINS: Dict[str, Dict[str, Any]] = {
    "sales": {
        "label": "Sales & E-Commerce",
        "icon": "🛍️",
        "table_name": "Sales",
        "keywords": [
            "order", "revenue", "sale", "sales", "unit_price", "units_sold",
            "sales_rep", "customer", "discount", "order_id", "product",
            "quantity", "amount", "status", "aov", "subtotal"
        ],
        "primary_id_candidates": ["order_id", "invoice_id", "transaction_id"],
        "metric_hints": ["revenue", "units_sold", "unit_price", "price"]
    },
    "marketing": {
        "label": "Marketing & Paid Media",
        "icon": "📣",
        "table_name": "Marketing",
        "keywords": [
            "campaign", "ad_spend", "spend", "impression", "impressions",
            "click", "clicks", "conversion", "conversions", "ctr", "cpc",
            "cpa", "roas", "channel", "ad_group", "keyword", "cost", "cpm",
            "lead", "leads", "reach"
        ],
        "primary_id_candidates": ["campaign_id", "ad_id", "keyword_id"],
        "metric_hints": ["spend", "clicks", "impressions", "conversions", "roas"]
    },
    "hr": {
        "label": "HR & People Operations",
        "icon": "👥",
        "table_name": "Employees",
        "keywords": [
            "employee", "employee_id", "salary", "department", "hire_date",
            "termination_date", "job_title", "title", "tenure", "headcount",
            "attrition", "turnover", "compensation", "payroll", "manager",
            "performance", "rating"
        ],
        "primary_id_candidates": ["employee_id", "staff_id", "emp_id"],
        "metric_hints": ["salary", "tenure", "rating", "bonus"]
    },
    "inventory": {
        "label": "Inventory & Supply Chain",
        "icon": "📦",
        "table_name": "Inventory",
        "keywords": [
            "sku", "stock", "warehouse", "inventory", "reorder", "reorder_level",
            "supplier", "unit_cost", "lead_time", "on_hand", "units_on_hand",
            "stockout", "safety_stock", "bin_location", "batch_number"
        ],
        "primary_id_candidates": ["sku", "item_code", "product_code"],
        "metric_hints": ["units_on_hand", "unit_cost", "reorder_level", "lead_time_days"]
    },
    "finance": {
        "label": "Finance & Accounting",
        "icon": "💳",
        "table_name": "Financials",
        "keywords": [
            "account", "account_name", "debit", "credit", "budget", "actual",
            "expense", "expenses", "opex", "capex", "ebitda", "profit",
            "net_income", "asset", "liability", "gl_code", "fiscal_year"
        ],
        "primary_id_candidates": ["account_id", "gl_code", "transaction_id"],
        "metric_hints": ["budget", "actual", "debit", "credit", "revenue", "expense"]
    },
}


class DomainClassifier:
    """Classifies a dataset into an operational business domain based on column signatures."""

    def __init__(self, df: pd.DataFrame):
        self.df = df
        self.columns = [str(c).lower().strip() for c in df.columns]

    def classify(self) -> Dict[str, Any]:
        """Score each domain against normalized columns and select the strongest match."""
        scores: Dict[str, float] = {}
        matched_keywords: Dict[str, List[str]] = {}

        for domain_key, config in DOMAINS.items():
            score = 0.0
            matches = []
            keywords = config["keywords"]

            for col in self.columns:
                for kw in keywords:
                    if kw in col:
                        # Exact column name match gets higher weight
                        if col == kw:
                            score += 2.5
                        else:
                            score += 1.5
                        if kw not in matches:
                            matches.append(kw)

            # Check ID candidates
            for id_cand in config["primary_id_candidates"]:
                if any(id_cand in col for col in self.columns):
                    score += 2.0
                    break

            scores[domain_key] = score
            matched_keywords[domain_key] = matches

        # Find domain with highest score
        best_domain = max(scores, key=scores.get)
        top_score = scores[best_domain]

        # Minimum score threshold to claim domain match (otherwise generic fallback)
        if top_score < 2.0:
            return {
                "domain": "generic",
                "label": "General Business Data",
                "icon": "📊",
                "table_name": "DataTable",
                "confidence": 60.0,
                "matched_signals": [],
                "scores": scores,
                "all_domains": [
                    {"key": k, "label": v["label"], "icon": v["icon"]}
                    for k, v in DOMAINS.items()
                ]
            }

        # Calculate confidence percentage (capped at 99%)
        total_possible = 10.0
        confidence = min(99.0, max(65.0, (top_score / total_possible) * 100.0))

        domain_info = DOMAINS[best_domain]
        return {
            "domain": best_domain,
            "label": domain_info["label"],
            "icon": domain_info["icon"],
            "table_name": domain_info["table_name"],
            "confidence": round(confidence, 1),
            "matched_signals": matched_keywords[best_domain],
            "scores": scores,
            "all_domains": [
                {"key": k, "label": v["label"], "icon": v["icon"]}
                for k, v in DOMAINS.items()
            ]
        }
