"""
run_pipeline.py - Master Orchestrator for Self-Healing Spreadsheet to Power BI Pipeline
Run:
    python run_pipeline.py --input "D:\Documents\power_bi_test_sample.xlsx" --launch-pbi
"""

import os
import sys
import argparse
import subprocess

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from cleaner import SelfHealingCleaner
from pbi_model import PowerBIModelGenerator
from dashboard_preview import generate_html_dashboard


def find_power_bi_desktop():
    """Locate Power BI Desktop executable or Windows App URI."""
    candidates = [
        r"C:\Program Files\Microsoft Power BI Desktop\bin\PBIDesktop.exe",
        r"C:\Program Files (x86)\Microsoft Power BI Desktop\bin\PBIDesktop.exe",
    ]
    for c in candidates:
        if os.path.exists(c):
            return c

    # Fallback to Store protocol / command
    return "PBIDesktop"


def main():
    parser = argparse.ArgumentParser(description="Self-Healing Spreadsheet to Power BI Pipeline")
    parser.add_argument("--input", "-i", type=str, default=r"D:\Documents\power_bi_test_sample.xlsx",
                        help="Path to raw Excel or CSV spreadsheet")
    parser.add_argument("--outdir", "-o", type=str,
                        default=os.path.join(os.path.dirname(__file__), "output"),
                        help="Output directory for cleaned data and BI artifacts")
    parser.add_argument("--launch-pbi", action="store_true",
                        help="Automatically open Power BI Desktop once pipeline completes")

    args = parser.parse_args()

    print("=" * 80)
    print("[*] STARTING SELF-HEALING DATA PIPELINE & POWER BI MODEL GENERATOR")
    print("=" * 80)
    print(f"[-] Input File:  {args.input}")
    print(f"[-] Output Dir:  {args.outdir}\n")

    # Step 1: Self-Healing Ingestion & Cleaning
    print("[1/3] Ingesting & Healing Raw Data...")
    cleaner = SelfHealingCleaner(args.input)
    clean_results = cleaner.save_clean_data(args.outdir)
    df = clean_results["df"]
    audit = clean_results["audit_log"]

    print(f"  [+] Ingested raw rows: {audit['raw_row_count']}")
    print(f"  [+] Cleaned valid rows: {audit['cleaned_row_count']}")

    if audit["dropped_rows"]:
        print(f"  [+] Auto-Healed {len(audit['dropped_rows'])} corrupting/trailer row(s):")
        for drop in audit["dropped_rows"]:
            print(f"      - Dropped row #{drop['row_index']}: {drop['reason']} (Preview: {drop['content_preview']})")

    if audit["inferred_calculations"]:
        print(f"  [+] Auto-Computed {len(audit['inferred_calculations'])} missing business column(s):")
        for calc in audit["inferred_calculations"]:
            print(f"      - Calculated '{calc['column']}': {calc['formula']} ({calc['status']})")

    print(f"  [+] Clean dataset exported to: {clean_results['csv_path']}\n")

    # Step 2: Semantic Modeling & DAX Generation
    print("[2/3] Generating Power BI Semantic Model & Business DAX...")
    generator = PowerBIModelGenerator(df, clean_results["csv_path"], table_name="Sales")
    pbi_results = generator.export_artifacts(args.outdir)

    print(f"  [+] Generated {pbi_results['measures_count']} production-grade DAX measures:")
    for m in generator.generate_dax_measures():
        print(f"      * {m['name']} ({m['format']}): {m['dax']}")

    # Generate HTML Executive Preview
    html_preview_path = os.path.join(args.outdir, "dashboard_preview.html")
    generate_html_dashboard(df, html_preview_path)

    print(f"\n  [+] Artifacts saved:")
    print(f"      |- Interactive Dashboard:   {html_preview_path}")
    print(f"      |- DAX Measures File:       {pbi_results['dax_file']}")
    print(f"      |- Power Query M Script:    {pbi_results['pq_file']}")
    print(f"      |- BI Measures Cheatsheet:  {pbi_results['md_file']}")
    print(f"      |- Audit Log (JSON):        {clean_results['audit_path']}\n")

    # Display Clean Data Sample
    print("[DATA PREVIEW] Cleaned & Normalized Rows:")
    print("-" * 80)
    print(df.to_string(index=False))
    print("-" * 80)

    # Step 3: Launch Power BI Desktop
    if args.launch_pbi:
        print("\n[3/3] Launching Power BI Desktop...")
        pbi_target = find_power_bi_desktop()
        try:
            if pbi_target.endswith(".exe"):
                subprocess.Popen([pbi_target])
                print(f"  [+] Power BI Desktop launched from: {pbi_target}")
            else:
                subprocess.Popen(["powershell", "-Command", "Start-Process PBIDesktop"], shell=True)
                print("  [+] Power BI Desktop launch signal sent successfully.")
        except Exception as e:
            print(f"  [!] Could not auto-launch Power BI Desktop: {e}")
            print("  [i] You can open Power BI Desktop manually and load the generated files.")
    else:
        print("\n[i] Tip: Run with --launch-pbi to automatically open Power BI Desktop!")

    print("\n[SUCCESS] PIPELINE COMPLETED!")
    print("=" * 80)


if __name__ == "__main__":
    main()
