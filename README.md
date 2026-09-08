# AutoBI — Multi-Domain Self-Healing Spreadsheet to Power BI Engine

AutoBI is an intelligent bridge between messy business spreadsheets and Microsoft Power BI. It automatically identifies the business domain, eliminates human errors, prunes corrupting summary rows, reconstructs missing calculated metrics, and generates production-ready Power BI semantic models and tailored DAX measures.

Available as both an interactive **Web Portal** and a **CLI / Desktop Pipeline**.

---

## Key Features

* **Multi-Domain Classification Engine (`domain_classifier.py`):**
  * Auto-scores spreadsheet columns and datatypes against signature matrices for:
    * **🛍️ Sales & E-Commerce**: Orders, Revenue, Units Sold, Unit Price, AOV, Cancellation Rates.
    * **📣 Marketing & Paid Media**: Spend, Impressions, Clicks, Conversions, CTR, CPC, CPA, ROAS.
    * **👥 HR & People Operations**: Headcount, Active vs. Terminated Staff, Attrition Rate, Payroll, Salary.
    * **📦 Inventory & Supply Chain**: Stock Valuation, SKUs, Stockout Rate, Reorder Thresholds, Lead Time.
    * **💳 Finance & Accounting**: Revenue, OPEX, Net Income, Operating Margins, Budget Variance.
  * Instant domain recognition with user-friendly 1-click model switching.

* **Domain-Tailored Power BI DAX Generator (`pbi_model.py`):**
  * Dynamically crafts domain-specific, production-grade DAX measures with format strings and business descriptions.
  * Generates customized Power Query (M) scripts (`LoadData.m`) with automated column type mappings.
  * Produces formatted markdown cheatsheets for analysts.

* **Domain-Aware Self-Healing Data Cleaner (`cleaner.py`):**
  * Auto-detects and prunes human-added summary/trailer rows (e.g. `Total`, `Subtotal`, `Average`) that skew BI models.
  * Reconstructs missing domain calculations:
    * Sales: `Revenue = Units * Price`
    * Marketing: `CTR = Clicks / Impressions`, `CPC = Spend / Clicks`
    * Inventory: `Stock Value = Units On Hand * Unit Cost`
    * Finance: `Net Income = Revenue - Expenses`
  * Sanitizes column names and datatypes, producing a complete JSON audit log.

* **Interactive Web Portal (`web_app.py`):**
  * Built with modern Vanilla CSS (Midnight Slate theme) and dynamic Chart.js visualizations.
  * Drag-and-drop file ingestion for `.xlsx`, `.xls`, and `.csv` files.
  * One-click demo presets for all major domains (Sales, Marketing, HR, Inventory).
  * Live domain classification badge and model switcher.
  * 1-click copy-to-clipboard for all DAX measures and Power Query M code.
  * Instant download of a complete **Power BI Starter Kit (`.zip`)**.

* **Desktop Orchestrator (`run_pipeline.py`):**
  * CLI tool that processes spreadsheets and can automatically locate and launch local `PBIDesktop.exe`.

---

## Quickstart

### 1. Requirements
* Python 3.10+
* Dependencies:
  ```bash
  pip install flask pandas openpyxl
  ```

### 2. Running the Web Portal
```bash
python web_app.py --port 5000
```
Open [http://127.0.0.1:5000](http://127.0.0.1:5000) in your browser.

### 3. Running via CLI
```bash
python run_pipeline.py --input "path/to/your/spreadsheet.xlsx" --launch-pbi
```

### 4. Running the Test Suites
```bash
# Test Domain Classifier & Multi-Domain DAX Modeling
python test_domain_classifier.py

# Test Web Portal Endpoints & Downloads
python test_web_app.py
```

---

## Repository Structure

```
power_bi_automation/
├── domain_classifier.py       # Domain classification & keyword signature engine
├── cleaner.py                 # Multi-domain self-healing data cleaner
├── pbi_model.py               # Domain-tailored Power BI semantic model & DAX generator
├── dashboard_preview.py       # Static HTML dashboard preview renderer
├── run_pipeline.py            # CLI orchestrator & Power BI desktop launcher
├── web_app.py                 # Flask web portal backend & REST API
├── test_domain_classifier.py  # Multi-domain automated test suite
├── test_web_app.py            # Web portal automated test suite
├── templates/
│   └── index.html             # Web portal HTML5 layout with domain switcher
├── static/
│   ├── css/style.css          # Vanilla CSS design system
│   └── js/app.js              # Frontend logic, charts, domain switching
├── output/                    # Sample pipeline artifacts
│   ├── cleaned_sales.csv
│   ├── LoadData.m
│   ├── dax_measures.dax
│   ├── POWER_BI_MEASURES_CHEATSHEET.md
│   └── audit_log.json
└── README.md
```
