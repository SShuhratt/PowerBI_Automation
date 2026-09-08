"""
pbi_model.py - Intelligent Power BI Semantic Model & DAX Generator
Inspects cleaned data schemas, generates domain-specific DAX measures,
Power Query (M) code, and Power BI Project (.pbip) TMDL definitions.
"""

import os
import uuid
import pandas as pd


class PowerBIModelGenerator:
    def __init__(self, df: pd.DataFrame, csv_path: str = "cleaned_sales.csv", table_name: str = "Sales"):
        self.df = df
        self.csv_path = csv_path.replace("\\", "\\\\") if csv_path else "cleaned_sales.csv"
        self.table_name = table_name

    def generate_dax_measures(self) -> list:
        """Dynamically generate standard business DAX measures based on dataset columns."""
        measures = []
        cols = list(self.df.columns)

        # Revenue measures
        if "total_revenue" in cols:
            measures.append({
                "name": "Total Revenue",
                "dax": f"Total Revenue = SUM('{self.table_name}'[total_revenue])",
                "format": "$#,##0.00",
                "description": "Total gross revenue generated across all recorded transactions."
            })

        # Volume measures
        if "units_sold" in cols:
            measures.append({
                "name": "Total Units Sold",
                "dax": f"Total Units Sold = SUM('{self.table_name}'[units_sold])",
                "format": "#,##0",
                "description": "Total volume of individual items or units sold."
            })

        # Order Count
        if "order_id" in cols:
            measures.append({
                "name": "Total Orders",
                "dax": f"Total Orders = DISTINCTCOUNT('{self.table_name}'[order_id])",
                "format": "#,##0",
                "description": "Count of unique transactions / orders."
            })

        # Average Order Value (AOV)
        if "total_revenue" in cols and "order_id" in cols:
            measures.append({
                "name": "Average Order Value",
                "dax": "Average Order Value = DIVIDE([Total Revenue], [Total Orders], 0)",
                "format": "$#,##0.00",
                "description": "Average revenue realized per unique order."
            })

        # Unit Price / Margins
        if "unit_price" in cols:
            measures.append({
                "name": "Average Unit Price",
                "dax": f"Average Unit Price = AVERAGE('{self.table_name}'[unit_price])",
                "format": "$#,##0.00",
                "description": "Average nominal unit price across catalog sales."
            })

        # Status segmentation measures
        if "status" in cols:
            statuses = self.df["status"].dropna().unique()
            for st in statuses:
                clean_st = str(st).strip()
                if "total_revenue" in cols:
                    measures.append({
                        "name": f"{clean_st} Revenue",
                        "dax": f"{clean_st} Revenue = CALCULATE([Total Revenue], '{self.table_name}'[status] = \"{clean_st}\")",
                        "format": "$#,##0.00",
                        "description": f"Total revenue for orders in '{clean_st}' state."
                    })

            # Rates (e.g. Cancellation Rate, Completion Rate)
            if any("cancel" in str(s).lower() for s in statuses):
                cancel_val = [s for s in statuses if "cancel" in str(s).lower()][0]
                measures.append({
                    "name": "Cancellation Rate",
                    "dax": f"Cancellation Rate = DIVIDE(CALCULATE(COUNTROWS('{self.table_name}'), '{self.table_name}'[status] = \"{cancel_val}\"), COUNTROWS('{self.table_name}'), 0)",
                    "format": "0.0%",
                    "description": "Percentage of all orders that ended in cancellation."
                })

            if any("complet" in str(s).lower() for s in statuses):
                comp_val = [s for s in statuses if "complet" in str(s).lower()][0]
                measures.append({
                    "name": "Completion Rate",
                    "dax": f"Completion Rate = DIVIDE(CALCULATE(COUNTROWS('{self.table_name}'), '{self.table_name}'[status] = \"{comp_val}\"), COUNTROWS('{self.table_name}'), 0)",
                    "format": "0.0%",
                    "description": "Percentage of successfully completed orders."
                })

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
            f.write(f"# Auto-Generated Power BI Measures for `{self.table_name}`\n\n")
            f.write("| Measure Name | Format | DAX Expression | Description |\n")
            f.write("| :--- | :--- | :--- | :--- |\n")
            for m in measures:
                dax_escaped = m['dax'].replace('|', '\\|')
                f.write(f"| **{m['name']}** | `{m['format']}` | `{dax_escaped}` | {m['description']} |\n")

        return {
            "dax_file": dax_file,
            "pq_file": pq_file,
            "md_file": md_file,
            "measures_count": len(measures)
        }
