"""
cleaner.py - Intelligent Self-Healing Spreadsheet Cleaner
Ingests messy business spreadsheets (Excel/Google Sheets), detects anomalies,
removes summary rows, infers missing calculated columns, and exports clean data.
"""

import os
import re
import pandas as pd
import numpy as np
from datetime import datetime


class SelfHealingCleaner:
    def __init__(self, file_input, filename: str = None):
        self.file_input = file_input
        self.filename = filename or (file_input if isinstance(file_input, str) else "uploaded_file.xlsx")
        self.audit_log = {
            "source_file": self.filename,
            "timestamp": datetime.now().isoformat(),
            "raw_row_count": 0,
            "cleaned_row_count": 0,
            "dropped_rows": [],
            "inferred_calculations": [],
            "renamed_columns": {},
            "datatype_conversions": {},
        }

    def _clean_column_name(self, col: str) -> str:
        """Standardize column names for clean DAX / Power Query use."""
        clean = str(col).strip()
        # Remove currency symbols and parentheses like ($), (€)
        clean = re.sub(r'[\(\[\{][\$\€\£\¥\s\w]*[\)\]\}]', '', clean).strip()
        # Replace spaces, hyphens, slashes with single space
        clean = re.sub(r'[\s\-_/]+', '_', clean).strip('_')
        return clean.lower()

    def clean(self) -> pd.DataFrame:
        # 1. Load data from DataFrame, file path or buffer (Excel or CSV)
        if isinstance(self.file_input, pd.DataFrame):
            df = self.file_input.copy()
        elif isinstance(self.file_input, str):
            if not os.path.exists(self.file_input):
                raise FileNotFoundError(f"Input file not found: {self.file_input}")
            lower_name = self.file_input.lower()
            if lower_name.endswith(".csv"):
                df = pd.read_csv(self.file_input)
            else:
                df = pd.read_excel(self.file_input)
        else:
            lower_name = self.filename.lower()
            if lower_name.endswith(".csv"):
                df = pd.read_csv(self.file_input)
            else:
                df = pd.read_excel(self.file_input)

        self.audit_log["raw_row_count"] = len(df)

        # 2. Detect and eliminate human-added summary/trailer rows (e.g. 'Total', 'Subtotal')
        non_summary_indices = []
        for idx, row in df.iterrows():
            row_str = " ".join([str(val).lower() for val in row.values if pd.notna(val)])
            nan_ratio = row.isna().mean()
            first_val = str(row.iloc[0]).lower().strip() if len(row) > 0 and pd.notna(row.iloc[0]) else ""
            has_summary_keyword = any(k in row_str for k in ["total", "subtotal", "average", "summary", "grand total"])
            is_summary = has_summary_keyword and (nan_ratio >= 0.25 or any(k == first_val for k in ["total", "subtotal", "sum", "average", "grand total"]))
            all_nan = row.isna().all()

            if is_summary or all_nan:
                reason = "Identified as summary row (Total/Subtotal)" if is_summary else "Completely empty row"
                self.audit_log["dropped_rows"].append({
                    "row_index": int(idx),
                    "reason": reason,
                    "content_preview": {k: str(v) for k, v in row.to_dict().items() if pd.notna(v)}
                })
            else:
                non_summary_indices.append(idx)

        df = df.loc[non_summary_indices].copy().reset_index(drop=True)

        # 3. Standardize Column Names
        original_cols = list(df.columns)
        new_cols = [self._clean_column_name(col) for col in original_cols]
        col_map = dict(zip(original_cols, new_cols))
        self.audit_log["renamed_columns"] = col_map
        df.rename(columns=col_map, inplace=True)

        # 4. Detect and Auto-Compute Missing Business Columns across Domains
        for col in df.columns:
            if df[col].isna().all():
                # --- Sales: Revenue = Units * Price ---
                if any(k in col for k in ["revenue", "total_rev", "sales_amount"]):
                    qty_cands = [c for c in df.columns if any(k in c for k in ["unit", "qty", "quantity", "sold", "count"])]
                    price_cands = [c for c in df.columns if any(k in c for k in ["price", "cost", "rate"])]
                    if qty_cands and price_cands:
                        df[col] = pd.to_numeric(df[qty_cands[0]], errors='coerce') * pd.to_numeric(df[price_cands[0]], errors='coerce')
                        self.audit_log["inferred_calculations"].append({
                            "column": col,
                            "formula": f"{qty_cands[0]} * {price_cands[0]}",
                            "status": f"Filled {len(df)} rows where Sales Revenue was blank."
                        })

                # --- Marketing: CPC = Spend / Clicks ---
                elif "cpc" in col or "cost_per_click" in col:
                    spend_cands = [c for c in df.columns if any(k in c for k in ["spend", "cost", "budget"])]
                    click_cands = [c for c in df.columns if "click" in c]
                    if spend_cands and click_cands:
                        df[col] = pd.to_numeric(df[spend_cands[0]], errors='coerce') / pd.to_numeric(df[click_cands[0]], errors='coerce').replace(0, np.nan)
                        self.audit_log["inferred_calculations"].append({
                            "column": col,
                            "formula": f"{spend_cands[0]} / {click_cands[0]}",
                            "status": f"Filled {len(df)} rows where CPC was blank."
                        })

                # --- Marketing: CTR = Clicks / Impressions ---
                elif "ctr" in col or "click_through_rate" in col:
                    click_cands = [c for c in df.columns if "click" in c]
                    imp_cands = [c for c in df.columns if "impression" in c]
                    if click_cands and imp_cands:
                        df[col] = (pd.to_numeric(df[click_cands[0]], errors='coerce') / pd.to_numeric(df[imp_cands[0]], errors='coerce').replace(0, np.nan)) * 100
                        self.audit_log["inferred_calculations"].append({
                            "column": col,
                            "formula": f"({click_cands[0]} / {imp_cands[0]}) * 100",
                            "status": f"Filled {len(df)} rows where CTR (%) was blank."
                        })

                # --- Inventory: Stock Value = Units * Unit Cost ---
                elif any(k in col for k in ["stock_value", "inventory_value", "total_cost"]):
                    stock_cands = [c for c in df.columns if any(k in c for k in ["stock", "on_hand", "quantity", "units"])]
                    cost_cands = [c for c in df.columns if any(k in c for k in ["unit_cost", "cost", "price"])]
                    if stock_cands and cost_cands:
                        df[col] = pd.to_numeric(df[stock_cands[0]], errors='coerce') * pd.to_numeric(df[cost_cands[0]], errors='coerce')
                        self.audit_log["inferred_calculations"].append({
                            "column": col,
                            "formula": f"{stock_cands[0]} * {cost_cands[0]}",
                            "status": f"Filled {len(df)} rows where Inventory Value was blank."
                        })

                # --- Finance: Net Income / Profit = Revenue - Expenses ---
                elif any(k in col for k in ["net_income", "profit", "net_profit", "operating_profit"]):
                    rev_cands = [c for c in df.columns if any(k in c for k in ["revenue", "income", "sales"])]
                    exp_cands = [c for c in df.columns if any(k in c for k in ["expense", "cost", "opex"])]
                    if rev_cands and exp_cands:
                        df[col] = pd.to_numeric(df[rev_cands[0]], errors='coerce') - pd.to_numeric(df[exp_cands[0]], errors='coerce')
                        self.audit_log["inferred_calculations"].append({
                            "column": col,
                            "formula": f"{rev_cands[0]} - {exp_cands[0]}",
                            "status": f"Filled {len(df)} rows where Net Income was blank."
                        })

        # 5. Type Inference and Sanitization
        for col in df.columns:
            # Check for date candidates
            if "date" in col or "time" in col:
                df[col] = pd.to_datetime(df[col], errors='coerce')
                self.audit_log["datatype_conversions"][col] = "datetime64"
            elif any(k in col for k in ["price", "revenue", "cost", "margin", "amount"]):
                df[col] = pd.to_numeric(df[col], errors='coerce')
                self.audit_log["datatype_conversions"][col] = "float64"
            elif any(k in col for k in ["units", "quantity", "count", "id"]):
                try:
                    df[col] = pd.to_numeric(df[col])
                    self.audit_log["datatype_conversions"][col] = "numeric"
                except Exception:
                    df[col] = df[col].astype(str).str.strip()
                    self.audit_log["datatype_conversions"][col] = "string"
            else:
                if df[col].dtype == object:
                    df[col] = df[col].astype(str).str.strip()
                    self.audit_log["datatype_conversions"][col] = "string"

        self.audit_log["cleaned_row_count"] = len(df)
        return df

    def save_clean_data(self, output_dir: str) -> dict:
        os.makedirs(output_dir, exist_ok=True)
        df_clean = self.clean()

        csv_path = os.path.join(output_dir, "cleaned_sales.csv")
        df_clean.to_csv(csv_path, index=False)

        audit_path = os.path.join(output_dir, "audit_log.json")
        import json
        with open(audit_path, "w", encoding="utf-8") as f:
            json.dump(self.audit_log, f, indent=2, default=str)

        return {
            "csv_path": csv_path,
            "audit_path": audit_path,
            "df": df_clean,
            "audit_log": self.audit_log
        }
