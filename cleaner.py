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


MONTH_NAMES_MAP = {
    # EN
    'january': 1, 'february': 2, 'march': 3, 'april': 4, 'may': 5, 'june': 6,
    'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11, 'december': 12,
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'jun': 6, 'jul': 7, 'aug': 8, 'sep': 9, 'sept': 9, 'oct': 10, 'nov': 11, 'dec': 12,
    # RU
    'январь': 1, 'февраль': 2, 'март': 3, 'апрель': 4, 'май': 5, 'мая': 5, 'июнь': 6,
    'июль': 7, 'август': 8, 'сентябрь': 9, 'октябрь': 10, 'ноябрь': 11, 'декабрь': 12,
    'янв': 1, 'фев': 2, 'мар': 3, 'апр': 4, 'июн': 6, 'июл': 7, 'авг': 8, 'сен': 9, 'окт': 10, 'ноя': 11, 'дек': 12,
    # UZ
    'yanvar': 1, 'fevral': 2, 'mart': 3, 'aprel': 4, 'iyun': 6, 'iyul': 7, 'avgust': 8,
    'sentabr': 9, 'sentyabr': 9, 'oktabr': 10, 'noyabr': 11, 'dekabr': 12,
    'yan': 1, 'fev': 2, 'mar': 3, 'apr': 4, 'iyun': 6, 'iyul': 7, 'avg': 8, 'sen': 9, 'okt': 10, 'noy': 11, 'dek': 12
}

SUMMARY_KEYWORDS = [
    'total', 'итого', 'jami', 'subtotal', 'grand total', 'всего',
    'sum', 'сумма', 'barchasi', 'umumiy', 'overall', 'total_summary'
]


class SelfHealingCleaner:
    def __init__(self, file_input, filename: str = None, sheet_name: str = None):
        self.file_input = file_input
        self.filename = filename or (file_input if isinstance(file_input, str) else "uploaded_file.xlsx")
        self.sheet_name = sheet_name
        self.available_sheets = []
        self.audit_log = {
            "source_file": self.filename,
            "timestamp": datetime.now().isoformat(),
            "raw_row_count": 0,
            "cleaned_row_count": 0,
            "selected_sheet": self.sheet_name,
            "available_sheets": [],
            "dropped_rows": [],
            "inferred_calculations": [],
            "renamed_columns": {},
            "datatype_conversions": {},
            "unpivoted_matrix": {"is_unpivoted": False},
            "anomalies": [],
            "anomaly_summary": {
                "total_flags": 0,
                "critical_count": 0,
                "warning_count": 0,
                "info_count": 0,
                "has_critical": False
            }
        }

    @staticmethod
    def inspect_sheets(file_input, filename: str = None) -> list:
        """Inspect sheet names in an Excel file without full table loading."""
        lower = (filename or (file_input if isinstance(file_input, str) else "")).lower()
        if lower.endswith(".csv"):
            return []
        try:
            import openpyxl
            if isinstance(file_input, (str, os.PathLike)):
                wb = openpyxl.load_workbook(file_input, read_only=True)
                return wb.sheetnames
            else:
                # Buffer
                pos = file_input.tell() if hasattr(file_input, "tell") else 0
                wb = openpyxl.load_workbook(file_input, read_only=True)
                sheets = wb.sheetnames
                if hasattr(file_input, "seek"):
                    file_input.seek(pos)
                return sheets
        except Exception:
            return []

    def _load_csv_with_fallback(self, file_source) -> pd.DataFrame:
        """Robust CSV loader supporting UTF-8-BOM, CP1251 (1C accounting), semicolon delimiters."""
        encodings = ["utf-8-sig", "utf-8", "cp1251", "windows-1251", "latin1"]
        for enc in encodings:
            try:
                if hasattr(file_source, "seek"):
                    file_source.seek(0)
                # Try with automatic separator detection (comma vs semicolon)
                return pd.read_csv(file_source, encoding=enc, sep=None, engine="python")
            except Exception:
                continue
        # Final fallback
        if hasattr(file_source, "seek"):
            file_source.seek(0)
        return pd.read_csv(file_source, encoding="utf-8", errors="replace")

    def _load_excel_smart(self, file_source, sheet_name=None) -> tuple:
        """Load Excel workbook with sheet detection."""
        if hasattr(file_source, "seek"):
            file_source.seek(0)
        excel_file = pd.ExcelFile(file_source)
        sheets = excel_file.sheet_names
        chosen_sheet = sheet_name

        if not chosen_sheet:
            # If multiple sheets, pick the sheet with most non-empty rows
            if len(sheets) == 1:
                chosen_sheet = sheets[0]
            else:
                best_sheet = sheets[0]
                max_cells = -1
                for s in sheets:
                    try:
                        sample_df = excel_file.parse(s, nrows=20)
                        cell_count = sample_df.notna().sum().sum()
                        if cell_count > max_cells:
                            max_cells = cell_count
                            best_sheet = s
                    except Exception:
                        continue
                chosen_sheet = best_sheet

        df = excel_file.parse(chosen_sheet)
        return df, chosen_sheet, sheets

    def _is_summary_col(self, col_name: str) -> bool:
        s = str(col_name).strip().lower()
        if s in SUMMARY_KEYWORDS:
            return True
        return any(s == f"total_{k}" or s == f"{k}_total" for k in ["revenue", "amount", "sales", "sum", "cost"])

    def _parse_temporal_header(self, header_str: str, default_year: int = 2026):
        """Parse temporal columns (EN, RU, UZ months, quarters, and years)."""
        s = str(header_str).strip().lower()
        if self._is_summary_col(s):
            return None

        s_clean = re.sub(r'[\s\-_/]+', ' ', s)
        yr_match = re.search(r'(?:19|20)\d{2}', s_clean)
        year = int(yr_match.group(0)) if yr_match else default_year

        # Quarter matching (e.g. Q1, Q1 2026, 1-kvartal, 1-кв)
        q_match = re.search(r'\bq([1-4])\b|([1-4])-?kvartal|([1-4])-?кв(?:артал)?', s_clean)
        if q_match:
            q_num = int(q_match.group(1) or q_match.group(2) or q_match.group(3))
            month = (q_num - 1) * 3 + 1
            return datetime(year, month, 1), "quarter"

        # Month matching across English, Russian, Uzbek
        for name, m_num in sorted(MONTH_NAMES_MAP.items(), key=lambda x: -len(x[0])):
            pattern = r'\b' + re.escape(name) + r'\b'
            if re.search(pattern, s_clean) or s_clean.startswith(name):
                return datetime(year, m_num, 1), "month"

        # Standalone year column (e.g. "2024", "2025", "year_2026", "2026 г.")
        if yr_match:
            bare = re.sub(r'[\s\-_yearгyil\.]+', '', s_clean)
            if bare == str(year):
                return datetime(year, 1, 1), "year"

        return None

    def _detect_and_unpivot_crosstab(self, df: pd.DataFrame) -> pd.DataFrame:
        """Detect and unpivot wide cross-tab matrices (1C/SAP exports, annual monthly budgets)."""
        if len(df.columns) < 3 or len(df) == 0:
            return df

        cols = list(df.columns)
        temporal_cols = []
        parsed_dates = {}
        parsed_types = {}

        for c in cols:
            res = self._parse_temporal_header(str(c))
            if res is not None:
                dt, t_type = res
                temporal_cols.append(c)
                parsed_dates[c] = dt
                parsed_types[c] = t_type

        non_temp_cols = [c for c in cols if c not in temporal_cols and not self._is_summary_col(c)]
        month_or_quarter_cols = [c for c in temporal_cols if parsed_types.get(c) in ("month", "quarter")]
        year_cols = [c for c in temporal_cols if parsed_types.get(c) == "year"]
        has_metric_or_growth_cols = any(any(k in str(c).lower() for k in ["growth", "osish", "o'sish", "изменение", "delta", "diff", "%"]) for c in cols)

        is_matrix = (len(month_or_quarter_cols) >= 3 and len(non_temp_cols) >= 1) or (
            len(year_cols) >= 4 and not has_metric_or_growth_cols and len(non_temp_cols) >= 1
        )

        if not is_matrix:
            self.audit_log["unpivoted_matrix"] = {"is_unpivoted": False}
            return df

        # Prune summary columns
        pruned_summary_cols = [c for c in cols if self._is_summary_col(c)]
        df_work = df.drop(columns=pruned_summary_cols, errors="ignore")

        # Melt wide columns to standard tabular structure
        id_vars = [c for c in df_work.columns if c not in temporal_cols]
        raw_rows = len(df_work)

        df_melted = pd.melt(
            df_work,
            id_vars=id_vars,
            value_vars=temporal_cols,
            var_name="period",
            value_name="amount"
        )

        # Standardize date column from parsed period dates
        df_melted["date"] = df_melted["period"].map(parsed_dates)
        if df_melted["date"].isna().any():
            df_melted["date"] = pd.to_datetime(df_melted["date"]).fillna(datetime(2026, 1, 1))

        # Standardize numeric amount
        if df_melted["amount"].dtype == object:
            clean_s = df_melted["amount"].astype(str).str.replace(r'[^\d,.\-]', '', regex=True).str.replace(',', '.')
            df_melted["amount"] = pd.to_numeric(clean_s, errors="coerce")
        else:
            df_melted["amount"] = pd.to_numeric(df_melted["amount"], errors="coerce")

        # Drop entirely empty/nan amount rows resulting from sparse cross-tab cells
        df_melted = df_melted.dropna(subset=["amount"]).reset_index(drop=True)

        self.audit_log["unpivoted_matrix"] = {
            "is_unpivoted": True,
            "id_columns": [str(c) for c in id_vars],
            "temporal_columns": [str(c) for c in temporal_cols],
            "pruned_summary_columns": [str(c) for c in pruned_summary_cols],
            "period_col": "period",
            "date_col": "date",
            "value_col": "amount",
            "original_rows": raw_rows,
            "unpivoted_rows": len(df_melted),
            "expansion_summary": f"Unpivoted {len(temporal_cols)} cross-tab columns into {len(df_melted):,} granular rows."
        }

        return df_melted

    @staticmethod
    def _serialize_sample_records(df_slice: pd.DataFrame, max_rows: int = 5) -> list:
        records = []
        for _, row in df_slice.head(max_rows).iterrows():
            clean_row = {}
            for k, v in row.items():
                if pd.isna(v):
                    clean_row[str(k)] = None
                elif isinstance(v, (datetime, pd.Timestamp)):
                    clean_row[str(k)] = v.strftime("%Y-%m-%d")
                elif isinstance(v, (np.integer, int)):
                    clean_row[str(k)] = int(v)
                elif isinstance(v, (np.floating, float)):
                    clean_row[str(k)] = round(float(v), 2)
                else:
                    clean_row[str(k)] = str(v)
            records.append(clean_row)
        return records

    def _detect_business_anomalies(self, df: pd.DataFrame) -> dict:
        """CFO Red-Flags & Business Anomaly Detection Engine."""
        anomalies = []
        cols = list(df.columns)

        # 1. Exact Duplicate Rows
        exact_dups = df[df.duplicated(keep=False)]
        if len(exact_dups) > 0:
            sample_preview = self._serialize_sample_records(exact_dups)
            anomalies.append({
                "category": "duplicate_records",
                "severity": "warning",
                "title": f"Duplicate Transaction Records ({len(exact_dups)} rows)",
                "description": f"Detected {len(exact_dups)} duplicate rows with identical values across all columns. Duplicates artificially inflate revenue and skew KPIs.",
                "affected_count": int(len(exact_dups)),
                "sample_rows": sample_preview
            })

        # 2. Duplicate Invoices / Transaction IDs
        id_candidates = [c for c in cols if any(k in c.lower() for k in ["order_id", "invoice_id", "invoice_no", "invoice", "trans_id", "transaction_id", "check_no", "receipt_id"])]
        if id_candidates:
            id_col = id_candidates[0]
            dup_id_df = df[df.duplicated(subset=[id_col], keep=False)]
            if len(dup_id_df) > 0:
                sample_preview = self._serialize_sample_records(dup_id_df)
                anomalies.append({
                    "category": "duplicate_invoices",
                    "severity": "critical",
                    "title": f"Duplicate Invoices / Transaction IDs ({len(dup_id_df)} records)",
                    "description": f"Identified {len(dup_id_df)} records sharing duplicated '{id_col}' values. Reused invoice IDs cause financial double-counting and indicate potential billing errors.",
                    "affected_count": int(len(dup_id_df)),
                    "sample_rows": sample_preview
                })

        # 3. Margin Leakage (Unit Price < Unit Cost)
        price_cands = [c for c in cols if any(k in c.lower() for k in ["unit_price", "price", "sale_price", "rate"])]
        cost_cands = [c for c in cols if any(k in c.lower() for k in ["unit_cost", "cost", "cogs", "buy_price"])]
        if price_cands and cost_cands:
            p_col = price_cands[0]
            c_col = cost_cands[0]
            if pd.api.types.is_numeric_dtype(df[p_col]) and pd.api.types.is_numeric_dtype(df[c_col]):
                leakage_mask = (df[p_col].notna()) & (df[c_col].notna()) & (df[p_col] < df[c_col])
                leakage_df = df[leakage_mask]
                if len(leakage_df) > 0:
                    sample_preview = self._serialize_sample_records(leakage_df)
                    anomalies.append({
                        "category": "margin_leakage",
                        "severity": "critical",
                        "title": f"Margin Leakage Detected ({len(leakage_df)} transactions)",
                        "description": f"Found {len(leakage_df)} transactions where {p_col} is less than {c_col}. Selling below unit cost generates immediate operating cash deficits.",
                        "affected_count": int(len(leakage_df)),
                        "sample_rows": sample_preview
                    })

        # 4. Negative Profit / Deficit Rows
        profit_cands = [c for c in cols if any(k in c.lower() for k in ["net_income", "profit", "net_profit", "operating_profit"]) and "margin" not in c.lower()]
        if profit_cands:
            prof_col = profit_cands[0]
            if pd.api.types.is_numeric_dtype(df[prof_col]):
                neg_mask = (df[prof_col].notna()) & (df[prof_col] < 0)
                neg_df = df[neg_mask]
                if len(neg_df) > 0:
                    sample_preview = self._serialize_sample_records(neg_df)
                    anomalies.append({
                        "category": "negative_profit",
                        "severity": "critical",
                        "title": f"Negative Net Profit Records ({len(neg_df)} rows)",
                        "description": f"Identified {len(neg_df)} entries with negative '{prof_col}', representing unprofitable business lines or severe accounting variances.",
                        "affected_count": int(len(neg_df)),
                        "sample_rows": sample_preview
                    })

        # 5. Statistical Outliers (>3 sigma / Probable Typos)
        target_metric_cols = [c for c in cols if any(k in c.lower() for k in ["amount", "revenue", "total_revenue", "sales_amount", "spend", "ad_spend", "salary", "stock_value", "total_cost"])]
        for col in target_metric_cols:
            if pd.api.types.is_numeric_dtype(df[col]):
                s = df[col].dropna()
                if len(s) >= 5:
                    mean = s.mean()
                    std = s.std()
                    if std > 0:
                        z_scores = (s - mean).abs() / std
                        outliers = df.loc[s[z_scores > 3].index]
                        if len(outliers) > 0:
                            sample_preview = self._serialize_sample_records(outliers)
                            anomalies.append({
                                "category": "statistical_outlier",
                                "severity": "warning",
                                "title": f"Statistical Outliers in '{col}' (>3σ, {len(outliers)} rows)",
                                "description": f"Detected {len(outliers)} entries exceeding 3 standard deviations (mean: {mean:,.1f}, max: {s.max():,.1f}). These frequently represent typo mistakes (e.g., extra zeros appended).",
                                "affected_count": int(len(outliers)),
                                "sample_rows": sample_preview
                            })
                            break  # report one primary metric outlier to keep alerts focused

        # 6. Zero-Price / Freebie Transactions
        qty_cands = [c for c in cols if any(k in c.lower() for k in ["quantity", "units_sold", "units", "qty"])]
        prc_cands = [c for c in cols if any(k in c.lower() for k in ["unit_price", "price", "amount", "total_revenue", "revenue"])]
        if qty_cands and prc_cands:
            q_col = qty_cands[0]
            p_col = prc_cands[0]
            if pd.api.types.is_numeric_dtype(df[q_col]) and pd.api.types.is_numeric_dtype(df[p_col]):
                zero_mask = (df[p_col] == 0) & (df[q_col] > 0)
                zero_df = df[zero_mask]
                if len(zero_df) > 0:
                    sample_preview = self._serialize_sample_records(zero_df)
                    anomalies.append({
                        "category": "zero_price_freebie",
                        "severity": "info",
                        "title": f"Zero-Price Deliveries ({len(zero_df)} transactions)",
                        "description": f"Found {len(zero_df)} transactions with $0 {p_col} despite positive {q_col}. May indicate complimentary samples or unbilled sales.",
                        "affected_count": int(len(zero_df)),
                        "sample_rows": sample_preview
                    })

        critical_c = sum(1 for a in anomalies if a["severity"] == "critical")
        warning_c = sum(1 for a in anomalies if a["severity"] == "warning")
        info_c = sum(1 for a in anomalies if a["severity"] == "info")

        summary = {
            "total_flags": len(anomalies),
            "critical_count": critical_c,
            "warning_count": warning_c,
            "info_count": info_c,
            "has_critical": critical_c > 0
        }

        self.audit_log["anomalies"] = anomalies
        self.audit_log["anomaly_summary"] = summary
        return summary

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
                df = self._load_csv_with_fallback(self.file_input)
            else:
                df, chosen_sheet, all_sheets = self._load_excel_smart(self.file_input, self.sheet_name)
                self.available_sheets = all_sheets
                self.sheet_name = chosen_sheet
                self.audit_log["selected_sheet"] = chosen_sheet
                self.audit_log["available_sheets"] = all_sheets
        else:
            lower_name = self.filename.lower()
            if lower_name.endswith(".csv"):
                df = self._load_csv_with_fallback(self.file_input)
            else:
                df, chosen_sheet, all_sheets = self._load_excel_smart(self.file_input, self.sheet_name)
                self.available_sheets = all_sheets
                self.sheet_name = chosen_sheet
                self.audit_log["selected_sheet"] = chosen_sheet
                self.audit_log["available_sheets"] = all_sheets

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
            summary_terms = [
                "total", "subtotal", "average", "summary", "grand total", "sum",
                "итого", "всего", "среднее", "общий итог", "сумма",
                "jami", "barchasi", "umumiy"
            ]
            has_summary_keyword = any(k in row_str for k in summary_terms)
            is_summary = has_summary_keyword and (nan_ratio >= 0.25 or any(k == first_val for k in summary_terms))
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

        # 2.5 Detect and unpivot wide cross-tab matrices (1C / ERP / Monthly budget matrices)
        df = self._detect_and_unpivot_crosstab(df)

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

        # 6. CFO Red-Flags & Business Anomaly Detection
        self._detect_business_anomalies(df)

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
