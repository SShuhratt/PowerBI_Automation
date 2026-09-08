# AutoBI — Self-Healing Spreadsheet to Power BI Engine

AutoBI is an intelligent, automated bridge between messy business spreadsheets and Microsoft Power BI. It eliminates human errors, prunes corrupting summary rows, reconstructs missing calculated metrics, and generates production-ready Power BI semantic models and DAX measures.

Available as both an interactive **Web Portal** and a **CLI / Desktop Pipeline**.

---

## Key Features

* **Intelligent Self-Healing Cleaner (`cleaner.py`):**
  * Auto-detects and prunes human-added summary/trailer rows (e.g. `Total`, `Subtotal`) that skew aggregations.
  * Inferred business column calculation (e.g., auto-detects `units_sold` and `unit_price` when `total_revenue` is completely blank).
  * Schema sanitization (removes currency symbols, standardizes column headers to snake_case).
  * Datatype inference and normalization (datetime, numeric, strings).
  * Full JSON audit logging of all healing operations.

* **Power BI Semantic Layer & DAX Generator (`pbi_model.py`):**
  * Generates production-grade domain DAX measures (`Total Revenue`, `Total Units Sold`, `Average Order Value`, `Cancellation Rate`, `Completion Rate`, etc.).
  * Generates Power Query (M) script (`LoadData.m`) with automated type transformations.
  * Produces markdown measure cheatsheets for analysts.

* **Interactive Web Portal (`web_app.py`):**
  * Built with modern Vanilla CSS (Midnight Slate theme) and Chart.js.
  * Drag-and-drop ingestion of `.xlsx`, `.xls`, and `.csv` files.
  * **⚡ Try Demo Sample** button for 1-click instant evaluation.
  * Executive Dashboard with KPI cards and interactive charts.
  * Self-Healing Audit Trail inspector.
  * 1-click copy-to-clipboard for DAX formulas.
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

### 4. Running the Automated Test Suite
```bash
python test_web_app.py
```

---

## Repository Structure

```
power_bi_automation/
├── cleaner.py                 # Self-healing data ingestion engine
├── pbi_model.py               # Power BI semantic model & DAX generator
├── dashboard_preview.py       # Static HTML dashboard preview renderer
├── run_pipeline.py            # CLI orchestrator & Power BI desktop launcher
├── web_app.py                 # Flask web portal backend & REST API
├── test_web_app.py            # Automated test suite
├── templates/
│   └── index.html             # Web portal HTML5 layout
├── static/
│   ├── css/style.css          # Vanilla CSS design system
│   └── js/app.js              # Frontend logic, charts & interactions
├── output/                    # Sample pipeline artifacts
│   ├── cleaned_sales.csv
│   ├── LoadData.m
│   ├── dax_measures.dax
│   ├── POWER_BI_MEASURES_CHEATSHEET.md
│   └── audit_log.json
└── README.md
```
