"""
pbi_model.py - Intelligent Multi-Domain Power BI Semantic Model & DAX Generator
Inspects cleaned schemas, identifies or accepts the business domain, and generates
domain-tailored DAX measures, Power Query (M) code, and documentation cheatsheets.
"""

import os
from typing import List, Dict, Any
import pandas as pd

from domain_classifier import DomainClassifier, DOMAINS


class PowerBIModelGenerator:
    """Generates production-grade Power BI semantic models and domain-tailored DAX measures."""

    def __init__(
        self,
        df: pd.DataFrame,
        csv_path: str = "cleaned_data.csv",
        table_name: str = None,
        domain: str = None
    ):
        self.df = df
        self.csv_path = csv_path.replace("\\", "\\\\") if csv_path else "cleaned_data.csv"

        # Domain classification
        if domain and domain in DOMAINS:
            self.domain = domain
            self.domain_info = DOMAINS[domain]
        else:
            classifier = DomainClassifier(df)
            detected = classifier.classify()
            self.domain = detected["domain"]
            self.domain_info = detected

        self.table_name = table_name or self.domain_info.get("table_name", "DataTable")

    def _find_col(self, candidates: List[str]) -> str:
        """Find the first matching column name in the dataframe."""
        for cand in candidates:
            for col in self.df.columns:
                if cand in col.lower():
                    return col
        return None

    def generate_dax_measures(self) -> List[Dict[str, str]]:
        """Generate domain-specific DAX business measures."""
        cols = list(self.df.columns)
        measures = []

        if self.domain == "marketing":
            measures.extend(self._generate_marketing_measures(cols))
        elif self.domain == "hr":
            measures.extend(self._generate_hr_measures(cols))
        elif self.domain == "inventory":
            measures.extend(self._generate_inventory_measures(cols))
        elif self.domain == "finance":
            measures.extend(self._generate_finance_measures(cols))
        else:
            # Sales domain (or generic)
            measures.extend(self._generate_sales_measures(cols))

        # If no domain-specific measures were triggered, provide fallback statistical measures
        if not measures:
            measures.extend(self._generate_generic_measures(cols))

        return measures

    def _generate_sales_measures(self, cols: List[str]) -> List[Dict[str, str]]:
        measures = []
        rev_col = self._find_col(["total_revenue", "revenue", "sales_amount", "amount"])
        units_col = self._find_col(["units_sold", "quantity", "units", "qty"])
        order_col = self._find_col(["order_id", "invoice_id", "transaction_id", "id"])
        price_col = self._find_col(["unit_price", "price"])
        status_col = self._find_col(["status", "order_status"])

        if rev_col:
            measures.append({
                "name": "Total Revenue",
                "dax": f"Total Revenue = SUM('{self.table_name}'[{rev_col}])",
                "format": "$#,##0.00",
                "description": "Total gross revenue generated across all recorded transactions."
            })

        if units_col:
            measures.append({
                "name": "Total Units Sold",
                "dax": f"Total Units Sold = SUM('{self.table_name}'[{units_col}])",
                "format": "#,##0",
                "description": "Total volume of individual items or units sold."
            })

        if order_col:
            measures.append({
                "name": "Total Orders",
                "dax": f"Total Orders = DISTINCTCOUNT('{self.table_name}'[{order_col}])",
                "format": "#,##0",
                "description": "Count of unique transactions / orders."
            })

        if rev_col and order_col:
            measures.append({
                "name": "Average Order Value",
                "dax": "Average Order Value = DIVIDE([Total Revenue], [Total Orders], 0)",
                "format": "$#,##0.00",
                "description": "Average revenue realized per unique order."
            })

        if price_col:
            measures.append({
                "name": "Average Unit Price",
                "dax": f"Average Unit Price = AVERAGE('{self.table_name}'[{price_col}])",
                "format": "$#,##0.00",
                "description": "Average nominal unit price across catalog sales."
            })

        if status_col:
            statuses = self.df[status_col].dropna().unique()
            for st in statuses:
                clean_st = str(st).strip()
                if rev_col:
                    measures.append({
                        "name": f"{clean_st} Revenue",
                        "dax": f"{clean_st} Revenue = CALCULATE([Total Revenue], '{self.table_name}'[{status_col}] = \"{clean_st}\")",
                        "format": "$#,##0.00",
                        "description": f"Total revenue for orders in '{clean_st}' state."
                    })

            if any("cancel" in str(s).lower() for s in statuses):
                cancel_val = [s for s in statuses if "cancel" in str(s).lower()][0]
                measures.append({
                    "name": "Cancellation Rate",
                    "dax": f"Cancellation Rate = DIVIDE(CALCULATE(COUNTROWS('{self.table_name}'), '{self.table_name}'[{status_col}] = \"{cancel_val}\"), COUNTROWS('{self.table_name}'), 0)",
                    "format": "0.0%",
                    "description": "Percentage of all orders that ended in cancellation."
                })

            if any("complet" in str(s).lower() for s in statuses):
                comp_val = [s for s in statuses if "complet" in str(s).lower()][0]
                measures.append({
                    "name": "Completion Rate",
                    "dax": f"Completion Rate = DIVIDE(CALCULATE(COUNTROWS('{self.table_name}'), '{self.table_name}'[{status_col}] = \"{comp_val}\"), COUNTROWS('{self.table_name}'), 0)",
                    "format": "0.0%",
                    "description": "Percentage of successfully completed orders."
                })

        return measures

    def _generate_marketing_measures(self, cols: List[str]) -> List[Dict[str, str]]:
        measures = []
        spend_col = self._find_col(["ad_spend", "spend", "cost"])
        imp_col = self._find_col(["impressions", "impression", "views"])
        click_col = self._find_col(["clicks", "click"])
        conv_col = self._find_col(["conversions", "conversion", "leads", "lead"])
        val_col = self._find_col(["conversion_value", "revenue", "conv_value"])

        if spend_col:
            measures.append({
                "name": "Total Ad Spend",
                "dax": f"Total Ad Spend = SUM('{self.table_name}'[{spend_col}])",
                "format": "$#,##0.00",
                "description": "Total investment across marketing campaigns and ad groups."
            })

        if imp_col:
            measures.append({
                "name": "Total Impressions",
                "dax": f"Total Impressions = SUM('{self.table_name}'[{imp_col}])",
                "format": "#,##0",
                "description": "Total number of times ads were displayed to audiences."
            })

        if click_col:
            measures.append({
                "name": "Total Clicks",
                "dax": f"Total Clicks = SUM('{self.table_name}'[{click_col}])",
                "format": "#,##0",
                "description": "Total direct user clicks delivered across campaigns."
            })

        if click_col and imp_col:
            measures.append({
                "name": "Click-Through Rate (CTR)",
                "dax": "Click-Through Rate (CTR) = DIVIDE([Total Clicks], [Total Impressions], 0)",
                "format": "0.00%",
                "description": "Percentage of ad impressions that resulted in a click."
            })

        if spend_col and click_col:
            measures.append({
                "name": "Cost Per Click (CPC)",
                "dax": "Cost Per Click (CPC) = DIVIDE([Total Ad Spend], [Total Clicks], 0)",
                "format": "$#,##0.00",
                "description": "Average unit cost incurred for each ad click."
            })

        if conv_col:
            measures.append({
                "name": "Total Conversions",
                "dax": f"Total Conversions = SUM('{self.table_name}'[{conv_col}])",
                "format": "#,##0",
                "description": "Total goal actions, purchases, or qualified leads generated."
            })

        if conv_col and click_col:
            measures.append({
                "name": "Conversion Rate (CVR)",
                "dax": "Conversion Rate (CVR) = DIVIDE([Total Conversions], [Total Clicks], 0)",
                "format": "0.00%",
                "description": "Percentage of clicks that successfully converted."
            })

        if spend_col and conv_col:
            measures.append({
                "name": "Cost Per Acquisition (CPA)",
                "dax": "Cost Per Acquisition (CPA) = DIVIDE([Total Ad Spend], [Total Conversions], 0)",
                "format": "$#,##0.00",
                "description": "Blended customer acquisition cost per confirmed conversion."
            })

        if val_col and spend_col:
            measures.append({
                "name": "Total Conversion Value",
                "dax": f"Total Conversion Value = SUM('{self.table_name}'[{val_col}])",
                "format": "$#,##0.00",
                "description": "Total monetary value realized from ad conversions."
            })
            measures.append({
                "name": "Return on Ad Spend (ROAS)",
                "dax": "Return on Ad Spend (ROAS) = DIVIDE([Total Conversion Value], [Total Ad Spend], 0)",
                "format": "0.00x",
                "description": "Revenue generated for every dollar invested in advertising."
            })

        return measures

    def _generate_hr_measures(self, cols: List[str]) -> List[Dict[str, str]]:
        measures = []
        emp_col = self._find_col(["employee_id", "staff_id", "emp_id", "id"])
        sal_col = self._find_col(["salary", "compensation", "pay_rate"])
        term_col = self._find_col(["termination_date", "exit_date", "term_date"])
        rating_col = self._find_col(["rating", "performance_score", "score"])

        measures.append({
            "name": "Total Headcount",
            "dax": f"Total Headcount = COUNTROWS('{self.table_name}')",
            "format": "#,##0",
            "description": "Total employees recorded in company roster."
        })

        if term_col:
            measures.append({
                "name": "Active Headcount",
                "dax": f"Active Headcount = CALCULATE(COUNTROWS('{self.table_name}'), ISBLANK('{self.table_name}'[{term_col}]))",
                "format": "#,##0",
                "description": "Current employed workforce active on payroll."
            })
            measures.append({
                "name": "Departed Headcount",
                "dax": f"Departed Headcount = CALCULATE(COUNTROWS('{self.table_name}'), NOT(ISBLANK('{self.table_name}'[{term_col}])))",
                "format": "#,##0",
                "description": "Total voluntary and involuntary employee exits."
            })
            measures.append({
                "name": "Attrition Rate",
                "dax": "Attrition Rate = DIVIDE([Departed Headcount], [Total Headcount], 0)",
                "format": "0.0%",
                "description": "Percentage turnover of recorded workforce."
            })

        if sal_col:
            measures.append({
                "name": "Average Salary",
                "dax": f"Average Salary = AVERAGE('{self.table_name}'[{sal_col}])",
                "format": "$#,##0",
                "description": "Mean annual employee base salary."
            })
            measures.append({
                "name": "Total Annual Payroll",
                "dax": f"Total Annual Payroll = SUM('{self.table_name}'[{sal_col}])",
                "format": "$#,##0",
                "description": "Cumulative annual company payroll expenditure."
            })

        if rating_col:
            measures.append({
                "name": "Average Performance Rating",
                "dax": f"Average Performance Rating = AVERAGE('{self.table_name}'[{rating_col}])",
                "format": "0.0",
                "description": "Benchmark performance review score across departments."
            })

        return measures

    def _generate_inventory_measures(self, cols: List[str]) -> List[Dict[str, str]]:
        measures = []
        sku_col = self._find_col(["sku", "item_code", "product_id", "product"])
        stock_col = self._find_col(["units_on_hand", "stock", "quantity", "on_hand"])
        cost_col = self._find_col(["unit_cost", "cost", "price"])
        reorder_col = self._find_col(["reorder_level", "safety_stock", "reorder_point"])
        lead_col = self._find_col(["lead_time_days", "lead_time", "lead_days"])

        if sku_col:
            measures.append({
                "name": "Total SKU Catalog",
                "dax": f"Total SKU Catalog = DISTINCTCOUNT('{self.table_name}'[{sku_col}])",
                "format": "#,##0",
                "description": "Total unique inventory stock-keeping units monitored."
            })

        if stock_col:
            measures.append({
                "name": "Total Units On Hand",
                "dax": f"Total Units On Hand = SUM('{self.table_name}'[{stock_col}])",
                "format": "#,##0",
                "description": "Total physical product count in warehouse locations."
            })

        if stock_col and cost_col:
            measures.append({
                "name": "Total Inventory Value",
                "dax": f"Total Inventory Value = SUMX('{self.table_name}', '{self.table_name}'[{stock_col}] * '{self.table_name}'[{cost_col}])",
                "format": "$#,##0.00",
                "description": "Total monetary valuation of working warehouse inventory."
            })

        if stock_col and sku_col:
            measures.append({
                "name": "Out of Stock SKUs",
                "dax": f"Out of Stock SKUs = CALCULATE(DISTINCTCOUNT('{self.table_name}'[{sku_col}]), '{self.table_name}'[{stock_col}] <= 0)",
                "format": "#,##0",
                "description": "Count of catalog SKUs with zero physical inventory."
            })
            measures.append({
                "name": "Stockout Rate",
                "dax": "Stockout Rate = DIVIDE([Out of Stock SKUs], [Total SKU Catalog], 0)",
                "format": "0.0%",
                "description": "Percentage of catalog items unavailable for fulfillment."
            })

        if stock_col and reorder_col:
            measures.append({
                "name": "Reorder Alert SKUs",
                "dax": f"Reorder Alert SKUs = CALCULATE(COUNTROWS('{self.table_name}'), '{self.table_name}'[{stock_col}] <= '{self.table_name}'[{reorder_col}])",
                "format": "#,##0",
                "description": "Items operating at or beneath minimum safety thresholds."
            })

        if lead_col:
            measures.append({
                "name": "Average Supplier Lead Time",
                "dax": f"Average Supplier Lead Time = AVERAGE('{self.table_name}'[{lead_col}])",
                "format": "0.0 days",
                "description": "Average transit days required to replenish stock."
            })

        return measures

    def _generate_finance_measures(self, cols: List[str]) -> List[Dict[str, str]]:
        measures = []
        rev_col = self._find_col(["revenue", "sales", "income"])
        exp_col = self._find_col(["expenses", "expense", "opex", "cost"])
        budget_col = self._find_col(["budget", "target"])

        if rev_col:
            measures.append({
                "name": "Total Operating Revenue",
                "dax": f"Total Operating Revenue = SUM('{self.table_name}'[{rev_col}])",
                "format": "$#,##0.00",
                "description": "Total gross recognized revenue."
            })

        if exp_col:
            measures.append({
                "name": "Total Operating Expenses",
                "dax": f"Total Operating Expenses = SUM('{self.table_name}'[{exp_col}])",
                "format": "$#,##0.00",
                "description": "Total operational expenditures incurred."
            })

        if rev_col and exp_col:
            measures.append({
                "name": "Net Operating Income",
                "dax": "Net Operating Income = [Total Operating Revenue] - [Total Operating Expenses]",
                "format": "$#,##0.00",
                "description": "Net business earnings before financing and tax adjustments."
            })
            measures.append({
                "name": "Operating Profit Margin",
                "dax": "Operating Profit Margin = DIVIDE([Net Operating Income], [Total Operating Revenue], 0)",
                "format": "0.0%",
                "description": "Percentage of gross revenue converted to operating profit."
            })

        if rev_col and budget_col:
            measures.append({
                "name": "Total Budget Target",
                "dax": f"Total Budget Target = SUM('{self.table_name}'[{budget_col}])",
                "format": "$#,##0.00",
                "description": "Planned financial target allocation."
            })
            measures.append({
                "name": "Budget Variance",
                "dax": "Budget Variance = [Total Operating Revenue] - [Total Budget Target]",
                "format": "$#,##0.00",
                "description": "Actual vs planned revenue surplus or deficit."
            })

        return measures

    def _generate_generic_measures(self, cols: List[str]) -> List[Dict[str, str]]:
        measures = [
            {
                "name": "Total Records",
                "dax": f"Total Records = COUNTROWS('{self.table_name}')",
                "format": "#,##0",
                "description": "Total rows recorded in dataset."
            }
        ]
        # Look for first numeric column
        for c in cols:
            if pd.api.types.is_numeric_dtype(self.df[c]):
                measures.append({
                    "name": f"Total {c.replace('_', ' ').title()}",
                    "dax": f"Total {c.replace('_', ' ').title()} = SUM('{self.table_name}'[{c}])",
                    "format": "#,##0.00",
                    "description": f"Cumulative sum of '{c}'."
                })
                break
        return measures

    def generate_power_query_m(self) -> str:
        """Generate Power Query M code to import the cleaned CSV directly."""
        col_types = []
        for col in self.df.columns:
            dtype = self.df[col].dtype
            if "datetime" in str(dtype):
                m_type = "type datetime"
            elif "float" in str(dtype):
                m_type = "type number"
            elif "int" in str(dtype):
                m_type = "Int64.Type"
            else:
                m_type = "type text"
            col_types.append(f'{{"{col}", {m_type}}}')

        m_types_str = "{" + ", ".join(col_types) + "}"

        m_code = f"""let
    Source = Csv.Document(File.Contents("{self.csv_path}"), [Delimiter=",", Columns={len(self.df.columns)}, Encoding=65001, QuoteStyle=QuoteStyle.None]),
    #"Promoted Headers" = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    #"Changed Type" = Table.TransformColumnTypes(#"Promoted Headers", {m_types_str})
in
    #"Changed Type"
"""
        return m_code

    def export_artifacts(self, output_dir: str) -> dict:
        os.makedirs(output_dir, exist_ok=True)
        measures = self.generate_dax_measures()
        m_code = self.generate_power_query_m()

        # 1. Write DAX Measures file
        dax_file = os.path.join(output_dir, "dax_measures.dax")
        with open(dax_file, "w", encoding="utf-8") as f:
            for m in measures:
                f.write(f"// Measure: {m['name']} ({m['format']})\n")
                f.write(f"// {m['description']}\n")
                f.write(f"{m['dax']}\n\n")

        # 2. Write Power Query M file
        pq_file = os.path.join(output_dir, "LoadData.m")
        with open(pq_file, "w", encoding="utf-8") as f:
            f.write(m_code)

        # 3. Write Markdown Cheatsheet
        md_file = os.path.join(output_dir, "POWER_BI_MEASURES_CHEATSHEET.md")
        with open(md_file, "w", encoding="utf-8") as f:
            f.write(f"# Auto-Generated Power BI Measures for `{self.table_name}` ({self.domain_info.get('label', self.domain)})\n\n")
            f.write("| Measure Name | Format | DAX Expression | Description |\n")
            f.write("| :--- | :--- | :--- | :--- |\n")
            for m in measures:
                dax_escaped = m['dax'].replace('|', '\\|')
                f.write(f"| **{m['name']}** | `{m['format']}` | `{dax_escaped}` | {m['description']} |\n")

        return {
            "dax_file": dax_file,
            "pq_file": pq_file,
            "md_file": md_file,
            "measures_count": len(measures),
            "domain": self.domain,
            "domain_label": self.domain_info.get("label", self.domain)
        }
