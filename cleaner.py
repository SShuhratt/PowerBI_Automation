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

    def _clean_column_name(self, col) -> str:
        """Standardize column names for clean DAX / Power Query use."""
        clean = str(col).strip() if pd.notna(col) else ""
        # Handle 'Unnamed: ...', nan, None
        if not clean or clean.lower().startswith("unnamed:") or clean.lower() in ("nan", "none", "null"):
            return "col"
        # Remove currency symbols and parenthesized units like ($), (€), (so'm), [USD], (ROI)
        clean = re.sub(r'[\(\[\{][\$\€\£\¥\s\w\.\'\"]*[\)\]\}]', '', clean).strip()
        # Remove remaining brackets and punctuation
        clean = re.sub(r'[(){}\[\]]', '', clean).strip()
        # Remove quotation marks, apostrophes, backticks
        clean = re.sub(r"['\"`]", "", clean).strip()
        # Replace spaces, hyphens, slashes, plus, percent, ampersand, hash with single underscore
        clean = re.sub(r'[\s\-_/\\.:,;+&%#]+', '_', clean).strip('_')
        # If clean is empty or digits, format cleanly
        if not clean:
            clean = "col"
        elif clean.isdigit() and len(clean) == 4 and (clean.startswith("19") or clean.startswith("20")):
            clean = f"year_{clean}"
        elif clean[0].isdigit():
            clean = f"col_{clean}"
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

        # Detect leading title banner / header offset (e.g. Row 0 is empty or title banner, headers on Row 1 or 2)
        if len(df) > 1 and len(df.columns) > 1:
            unnamed_count = sum(1 for c in df.columns if str(c).lower().startswith("unnamed:") or pd.isna(c) or str(c).strip() == "")
            unnamed_ratio = unnamed_count / max(len(df.columns), 1)
            if unnamed_ratio >= 0.6:
                for cand_idx in range(min(5, len(df))):
                    cand_row = df.iloc[cand_idx]
                    cand_non_null = cand_row.notna().sum()
                    if cand_non_null >= 2 and (cand_non_null / len(df.columns)) >= 0.5:
                        self.audit_log["header_promoted_from_row"] = cand_idx + 1
                        df.columns = [str(val).strip() if pd.notna(val) else f"col_{i}" for i, val in enumerate(cand_row)]
                        df = df.iloc[cand_idx + 1:].reset_index(drop=True)
                        break

        # Standardize common null/dash placeholders (e.g. '—', '–', 'N/A', Excel errors)
        df.replace({
            r'^\s*[—–\-]+\s*$': np.nan,
            r'^\s*(N/A|n/a|#N/A|#VALUE!|#REF!|#DIV/0!|#NAME\?|#NUM!|#NULL!|None|NULL|null)\s*$': np.nan
        }, regex=True, inplace=True)

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
                    "content_preview": {str(k): str(v) for k, v in row.to_dict().items() if pd.notna(v)}
                })
            else:
                non_summary_indices.append(idx)

        df = df.loc[non_summary_indices].copy().reset_index(drop=True)

        # 3. Standardize Column Names (De-duplicate and guarantee string keys)
        original_cols = list(df.columns)
        new_cols = []
        seen = {}
        for i, col in enumerate(original_cols):
            base_clean = self._clean_column_name(col)
            if base_clean in seen:
                seen[base_clean] += 1
                col_name = f"{base_clean}_{seen[base_clean]}"
            else:
                seen[base_clean] = 1
                col_name = base_clean
            new_cols.append(col_name)

        col_map = {str(orig): str(new) for orig, new in zip(original_cols, new_cols)}
        self.audit_log["renamed_columns"] = col_map
        df.columns = new_cols

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
            str_col = str(col)
            # Check for date candidates
            if "date" in str_col or "time" in str_col:
                df[col] = pd.to_datetime(df[col], errors='coerce')
                self.audit_log["datatype_conversions"][str_col] = "datetime64"
            elif any(k in str_col for k in ["price", "revenue", "cost", "margin", "amount", "spend", "salary", "budget", "profit", "opex", "capex"]):
                if df[col].dtype == object:
                    clean_series = df[col].astype(str).str.replace(r'[^\d,.\-]', '', regex=True).str.replace(',', '.')
                    df[col] = pd.to_numeric(clean_series, errors='coerce')
                else:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
                self.audit_log["datatype_conversions"][str_col] = "float64"
            elif any(k in str_col for k in ["units", "quantity", "count", "clicks", "impressions", "conversions"]):
                try:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
                    self.audit_log["datatype_conversions"][str_col] = "numeric"
                except Exception:
                    df[col] = df[col].apply(lambda v: str(v).strip() if pd.notna(v) else np.nan)
                    self.audit_log["datatype_conversions"][str_col] = "string"
            else:
                if df[col].dtype == object:
                    non_nulls = df[col].dropna()
                    if len(non_nulls) > 0:
                        # Try parsing as numeric if majority look numeric (handling space thousands and comma decimals)
                        clean_cand = non_nulls.astype(str).str.strip().str.replace(',', '.', regex=False).str.replace(' ', '', regex=False)
                        converted = pd.to_numeric(clean_cand, errors='coerce')
                        if converted.notna().mean() >= 0.75:
                            df[col] = pd.to_numeric(df[col].astype(str).str.strip().str.replace(',', '.', regex=False).str.replace(' ', '', regex=False), errors='coerce')
                            self.audit_log["datatype_conversions"][str_col] = "numeric"
                            continue
                    df[col] = df[col].apply(lambda v: str(v).strip() if pd.notna(v) else np.nan)
                    self.audit_log["datatype_conversions"][str_col] = "string"

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
