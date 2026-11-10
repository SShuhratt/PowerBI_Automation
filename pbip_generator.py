"""
pbip_generator.py - Generates native Microsoft Power BI Project (.pbip) bundle.
Enables 1-click double-launch in Power BI Desktop with semantic model, table
schema, column types, Power Query M partitions, and all calculated DAX measures.
"""

import json
import pandas as pd
from typing import List, Dict, Any


def get_tmsl_data_type(dtype, col_name: str = "") -> str:
    s = str(dtype).lower()
    c = str(col_name).lower()
    if "datetime" in s or "date" in s or (c and any(k in c for k in ["order_date", "trans_date", "transaction_date", "invoice_date", "hire_date", "created_at"])):
        return "dateTime"
    elif "int" in s:
        return "int64"
    elif "float" in s or "double" in s or "decimal" in s:
        return "double"
    elif "bool" in s:
        return "boolean"
    return "string"


def find_primary_date_column(df: pd.DataFrame) -> str:
    for c in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[c]):
            return c
    for c in df.columns:
        cl = str(c).lower()
        if any(k in cl for k in ["order_date", "trans_date", "transaction_date", "invoice_date", "sale_date", "date", "created_at", "hire_date", "period", "timestamp"]):
            return c
    return None


def generate_pbip_artifacts(
    df: pd.DataFrame,
    table_name: str,
    measures: List[Dict[str, str]],
    m_script: str,
    project_name: str = "AutoBI_Project",
    anomalies: List[Dict[str, Any]] = None,
    fx_info: Dict[str, Any] = None
) -> Dict[str, str]:
    """
    Generates file contents for the complete Power BI Project (.pbip) directory tree.
    Returns a dict mapping relative archive paths to their file contents (strings).
    """
    # 1. Root .pbip pointer
    pbip_json = {
        "version": "1.0",
        "artifacts": [
            {
                "report": {
                    "path": f"{project_name}.Report"
                }
            }
        ],
        "settings": {
            "enableAutoRecovery": True
        }
    }

    # 2. SemanticModel definition.pbism
    pbism_json = {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/1.0.0/schema.json",
        "version": "4.2",
        "settings": {
            "qnaEnabled": True
        }
    }

    # 3. Columns mapping for model.bim
    columns_tmsl = []
    for col in df.columns:
        dt = get_tmsl_data_type(df[col].dtype, col)
        col_def: Dict[str, Any] = {
            "name": str(col),
            "dataType": dt,
            "sourceColumn": str(col)
        }
        if dt == "dateTime":
            col_def["formatString"] = "yyyy-mm-dd"
        elif dt == "double" and any(k in col.lower() for k in ["price", "rev", "cost", "margin", "profit", "amount", "salary", "spend", "rate"]):
            col_def["formatString"] = "$#,##0.00"
        elif dt == "int64":
            col_def["formatString"] = "#,##0"
        columns_tmsl.append(col_def)

    # 4. Measures mapping for model.bim
    measures_tmsl = []
    for m in measures:
        dax_raw = m.get("dax", "")
        # TMSL takes the formula without the "Measure Name = " prefix
        if "=" in dax_raw:
            expr = dax_raw.split("=", 1)[1].strip()
        else:
            expr = dax_raw.strip()

        measure_def: Dict[str, Any] = {
            "name": m.get("name", "Custom Measure"),
            "expression": expr,
            "description": m.get("description", "")
        }
        if m.get("format"):
            measure_def["formatString"] = m["format"]
        measures_tmsl.append(measure_def)

    # Format M script lines as array of strings
    m_lines = [line + "\n" for line in m_script.strip().split("\n")]

    # 5. Tables & Relationships (including Dim_Date Calendar table if dates detected)
    tables = [
        {
            "name": table_name,
            "columns": columns_tmsl,
            "partitions": [
                {
                    "name": f"Partition_{table_name}",
                    "mode": "import",
                    "source": {
                        "type": "m",
                        "expression": m_lines
                    }
                }
            ],
            "measures": measures_tmsl
        }
    ]
    relationships = []

    date_col = find_primary_date_column(df)
    if date_col:
        min_year = 2024
        max_year = 2026
        try:
            dt_series = pd.to_datetime(df[date_col], errors="coerce").dropna()
            if not dt_series.empty:
                min_year = int(dt_series.min().year)
                max_year = int(dt_series.max().year)
        except Exception:
            pass

        if max_year < min_year:
            max_year = min_year
        if min_year == max_year:
            max_year = min_year + 1

        dim_date_table = {
            "name": "Dim_Date",
            "dataCategory": "Time",
            "columns": [
                {
                    "name": "Date",
                    "dataType": "dateTime",
                    "isKey": True,
                    "sourceColumn": "[Date]",
                    "formatString": "yyyy-mm-dd"
                },
                {
                    "name": "Year",
                    "dataType": "int64",
                    "sourceColumn": "[Year]",
                    "formatString": "0"
                },
                {
                    "name": "Quarter",
                    "dataType": "string",
                    "sourceColumn": "[Quarter]"
                },
                {
                    "name": "Month Number",
                    "dataType": "int64",
                    "sourceColumn": "[Month Number]",
                    "formatString": "0"
                },
                {
                    "name": "Month",
                    "dataType": "string",
                    "sourceColumn": "[Month]",
                    "sortByColumn": "Month Number"
                },
                {
                    "name": "Month Year",
                    "dataType": "string",
                    "sourceColumn": "[Month Year]"
                },
                {
                    "name": "Day of Month",
                    "dataType": "int64",
                    "sourceColumn": "[Day of Month]",
                    "formatString": "0"
                },
                {
                    "name": "Day of Week",
                    "dataType": "int64",
                    "sourceColumn": "[Day of Week]",
                    "formatString": "0"
                },
                {
                    "name": "Day Name",
                    "dataType": "string",
                    "sourceColumn": "[Day Name]"
                },
                {
                    "name": "Is Weekend",
                    "dataType": "string",
                    "sourceColumn": "[Is Weekend]"
                }
            ],
            "partitions": [
                {
                    "name": "Dim_Date_Partition",
                    "mode": "import",
                    "source": {
                        "type": "calculated",
                        "expression": [
                            "ADDCOLUMNS(",
                            f"    CALENDAR(DATE({min_year}, 1, 1), DATE({max_year}, 12, 31)),",
                            "    \"Year\", YEAR([Date]),",
                            "    \"Quarter\", \"Q\" & FORMAT([Date], \"Q\"),",
                            "    \"Month Number\", MONTH([Date]),",
                            "    \"Month\", FORMAT([Date], \"mmmm\"),",
                            "    \"Month Year\", FORMAT([Date], \"mmm yyyy\"),",
                            "    \"Day of Month\", DAY([Date]),",
                            "    \"Day of Week\", WEEKDAY([Date], 2),",
                            "    \"Day Name\", FORMAT([Date], \"dddd\"),",
                            "    \"Is Weekend\", IF(WEEKDAY([Date], 2) >= 6, \"Yes\", \"No\")",
                            ")"
                        ]
                    }
                }
            ]
        }
        tables.append(dim_date_table)

        # Mark date_col as dateTime for TMSL relationship integrity
        for c in columns_tmsl:
            if c["name"] == str(date_col):
                c["dataType"] = "dateTime"
                c["formatString"] = "yyyy-mm-dd"

        relationships.append({
            "name": f"Rel_{table_name}_{date_col}_DimDate",
            "fromTable": table_name,
            "fromColumn": str(date_col),
            "toTable": "Dim_Date",
            "toColumn": "Date",
            "crossFilteringBehavior": "oneDirection"
        })

    # Add dedicated Audit_Exceptions table if business anomalies were flagged
    if anomalies and len(anomalies) > 0:
        audit_rows_m = []
        for idx, a in enumerate(anomalies, 1):
            sev = a.get("severity", "warning").capitalize()
            cat = a.get("category", "General").replace("_", " ").title()
            title = str(a.get("title", "")).replace('"', '""')
            desc = str(a.get("description", "")).replace('"', '""')
            cnt = int(a.get("affected_count", 1))
            audit_rows_m.append(f'        {{{idx}, "{sev}", "{cat}", "{title}", "{desc}", {cnt}}}')

        m_rows_joined = ",\n".join(audit_rows_m)
        m_audit_expr = [
            "let\n",
            "    Source = #table(\n",
            "        type table [Exception_ID = Int64.Type, Severity = text, Category = text, Title = text, Description = text, Affected_Rows = Int64.Type],\n",
            "        {\n",
            f"{m_rows_joined}\n",
            "        }\n",
            "    )\n",
            "in\n",
            "    Source\n"
        ]

        audit_table = {
            "name": "Audit_Exceptions",
            "columns": [
                {"name": "Exception_ID", "dataType": "int64", "sourceColumn": "Exception_ID"},
                {"name": "Severity", "dataType": "string", "sourceColumn": "Severity"},
                {"name": "Category", "dataType": "string", "sourceColumn": "Category"},
                {"name": "Title", "dataType": "string", "sourceColumn": "Title"},
                {"name": "Description", "dataType": "string", "sourceColumn": "Description"},
                {"name": "Affected_Rows", "dataType": "int64", "sourceColumn": "Affected_Rows"}
            ],
            "partitions": [
                {
                    "name": "Audit_Exceptions_Partition",
                    "mode": "import",
                    "source": {
                        "type": "m",
                        "expression": m_audit_expr
                    }
                }
            ]
        }
        tables.append(audit_table)

    # Add Currency_Selector disconnected parameter table if multi-currency normalization occurred
    if fx_info and fx_info.get("is_multi_currency"):
        currency_selector_table = {
            "name": "Currency_Selector",
            "columns": [
                {"name": "Currency", "dataType": "string", "sourceColumn": "Currency", "isKey": True},
                {"name": "Symbol", "dataType": "string", "sourceColumn": "Symbol"}
            ],
            "partitions": [
                {
                    "name": "Currency_Selector_Partition",
                    "mode": "import",
                    "source": {
                        "type": "m",
                        "expression": [
                            "let\n",
                            "    Source = #table(\n",
                            "        type table [Currency = text, Symbol = text],\n",
                            "        {\n",
                            "            {\"UZS\", \"so'm\"},\n",
                            "            {\"USD\", \"$\"}\n",
                            "        }\n",
                            "    )\n",
                            "in\n",
                            "    Source\n"
                        ]
                    }
                }
            ]
        }
        tables.append(currency_selector_table)

    # 6. SemanticModel definition/model.bim
    model_bim = {
        "name": f"{table_name}_Model",
        "compatibilityLevel": 1550,
        "model": {
            "culture": "en-US",
            "dataAccessOptions": {
                "legacyRedirects": True,
                "returnErrorValuesAsNull": True
            },
            "defaultPowerBIDataSourceVersion": "powerBI_V3",
            "tables": tables,
            "relationships": relationships
        }
    }

    # 6. Report definition.pbir
    pbir_json = {
        "version": "4.0",
        "datasetReference": {
            "byPath": {
                "path": f"../{project_name}.SemanticModel"
            }
        }
    }

    # 7. Report definition/report.json
    report_json = {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/1.0.0/schema.json",
        "themeSettings": {
            "currentTheme": "Default"
        }
    }

    artifacts = {
        f"{project_name}.pbip": json.dumps(pbip_json, indent=2),
        f"{project_name}.SemanticModel/definition.pbism": json.dumps(pbism_json, indent=2),
        f"{project_name}.SemanticModel/definition/model.bim": json.dumps(model_bim, indent=2),
        f"{project_name}.Report/definition.pbir": json.dumps(pbir_json, indent=2),
        f"{project_name}.Report/definition/report.json": json.dumps(report_json, indent=2),
    }

    return artifacts

