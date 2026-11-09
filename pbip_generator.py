"""
pbip_generator.py - Generates native Microsoft Power BI Project (.pbip) bundle.
Enables 1-click double-launch in Power BI Desktop with semantic model, table
schema, column types, Power Query M partitions, and all calculated DAX measures.
"""

import json
import pandas as pd
from typing import List, Dict, Any


def get_tmsl_data_type(dtype) -> str:
    s = str(dtype).lower()
    if "int" in s:
        return "int64"
    elif "float" in s or "double" in s or "decimal" in s:
        return "double"
    elif "datetime" in s or "date" in s:
        return "dateTime"
    elif "bool" in s:
        return "boolean"
    return "string"


def generate_pbip_artifacts(
    df: pd.DataFrame,
    table_name: str,
    measures: List[Dict[str, str]],
    m_script: str,
    project_name: str = "AutoBI_Project"
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
        dt = get_tmsl_data_type(df[col].dtype)
        col_def: Dict[str, Any] = {
            "name": str(col),
            "dataType": dt,
            "sourceColumn": str(col)
        }
        if dt == "double" and any(k in col.lower() for k in ["price", "rev", "cost", "margin", "profit", "amount", "salary", "spend", "rate"]):
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

    # 5. SemanticModel definition/model.bim
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
            "tables": [
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
