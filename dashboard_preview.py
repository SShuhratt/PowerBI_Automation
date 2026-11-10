"""
dashboard_preview.py - Standalone Interactive Executive HTML Dashboard Generator
Generates a self-contained, responsive HTML/JS dashboard that stakeholders can
double-click and open immediately in any browser without Power BI installed.
"""

import os
import json
import pandas as pd


def generate_html_dashboard(
    df: pd.DataFrame,
    kpis: list,
    charts: dict,
    domain_info: dict,
    filename: str,
    anomalies: list = None,
    anomaly_summary: dict = None,
    fx_info: dict = None,
    pareto_info: dict = None
) -> str:
    domain_label = domain_info.get("label", "Business Analytics")
    domain_icon = domain_info.get("icon", "📊")
    anomalies = anomalies or []
    anomaly_summary = anomaly_summary or {"total_flags": 0, "critical_count": 0, "warning_count": 0, "info_count": 0, "has_critical": False}
    fx_info = fx_info or {}
    pareto_info = pareto_info or {}

    # Multi-currency banner HTML
    fx_banner_html = ""
    if fx_info.get("is_multi_currency"):
        rates_str = ", ".join([f"{c}: {r:,.1f} UZS" for c, r in fx_info.get("rates_applied", {}).items() if c != "UZS"])
        fx_banner_html = f"""
        <div class="glass-card rounded-xl px-4 py-3 border border-indigo-500/30 bg-indigo-500/5 flex flex-wrap items-center justify-between gap-3 text-xs">
            <div class="flex items-center gap-2 text-indigo-300">
                <span class="text-base">💱</span>
                <span><strong>Multi-Currency FX Normalization:</strong> Converted ({', '.join(fx_info.get('detected_currencies', []))}) via <strong>CBU.uz</strong> official rates ({rates_str}).</span>
            </div>
            <span class="px-2.5 py-0.5 rounded bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 font-mono text-[11px]">CBU Date: {fx_info.get('cbu_date', 'Today')}</span>
        </div>
        """

    # Pareto 80/20 banner HTML
    pareto_banner_html = ""
    if pareto_info.get("is_segmented"):
        pareto_banner_html = f"""
        <div class="glass-card rounded-xl px-4 py-3 border border-amber-500/30 bg-amber-500/5 flex flex-wrap items-center justify-between gap-3 text-xs">
            <div class="flex items-center gap-2 text-amber-300">
                <span class="text-base">🎯</span>
                <span><strong>Pareto (80/20) Segmentation:</strong> <strong>{pareto_info.get('class_a_count', 0)}</strong> Class A {pareto_info.get('dimension_col', 'items')} generate <strong>{pareto_info.get('class_a_revenue_share', 0)}%</strong> of total volume.</span>
            </div>
            <div class="flex items-center gap-2 font-mono text-[11px]">
                <span class="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">Class A: {pareto_info.get('class_a_revenue_share', 0)}%</span>
                <span class="px-2 py-0.5 rounded bg-cyan-500/20 text-cyan-300 border border-cyan-500/30">Class B: {pareto_info.get('class_b_revenue_share', 0)}%</span>
                <span class="px-2 py-0.5 rounded bg-slate-700 text-slate-300">Class C: {pareto_info.get('class_c_revenue_share', 0)}%</span>
            </div>
        </div>
        """

    # Format Anomaly Alerts HTML
    if anomalies:
        alerts_html = f"""
        <section class="glass-card rounded-2xl p-6 border border-rose-500/30 bg-rose-500/5">
            <div class="flex items-center justify-between mb-4">
                <div class="flex items-center gap-2.5">
                    <span class="text-2xl">🚨</span>
                    <div>
                        <h3 class="text-base font-bold text-white">Executive Red-Flags & Audit Alerts</h3>
                        <p class="text-xs text-slate-400">Automated risk detection identified {anomaly_summary.get('total_flags', len(anomalies))} business anomalie(s) requiring management review.</p>
                    </div>
                </div>
                <div class="flex items-center gap-2">
                    {f'<span class="px-2.5 py-1 bg-rose-500/20 border border-rose-500/40 text-rose-300 rounded-full text-xs font-semibold">{anomaly_summary.get("critical_count", 0)} Critical</span>' if anomaly_summary.get("critical_count", 0) > 0 else ''}
                    {f'<span class="px-2.5 py-1 bg-amber-500/20 border border-amber-500/40 text-amber-300 rounded-full text-xs font-semibold">{anomaly_summary.get("warning_count", 0)} Warning</span>' if anomaly_summary.get("warning_count", 0) > 0 else ''}
                    {f'<span class="px-2.5 py-1 bg-sky-500/20 border border-sky-500/40 text-sky-300 rounded-full text-xs font-semibold">{anomaly_summary.get("info_count", 0)} Notice</span>' if anomaly_summary.get("info_count", 0) > 0 else ''}
                </div>
            </div>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        """
        for a in anomalies:
            sev = a.get("severity", "warning")
            badge_color = "rose" if sev == "critical" else ("amber" if sev == "warning" else "sky")
            alerts_html += f"""
                <div class="p-4 rounded-xl bg-slate-900/60 border border-slate-800 hover:border-slate-700 transition space-y-2">
                    <div class="flex items-center justify-between">
                        <span class="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-{badge_color}-500/20 text-{badge_color}-400 border border-{badge_color}-500/30">
                            {sev.upper()}
                        </span>
                        <span class="text-xs font-mono text-slate-400">{a.get('affected_count', 1)} record(s)</span>
                    </div>
                    <div class="text-sm font-semibold text-slate-200">{a.get('title', '')}</div>
                    <p class="text-xs text-slate-400 leading-relaxed">{a.get('description', '')}</p>
                </div>
            """
        alerts_html += """
            </div>
        </section>
        """
    else:
        alerts_html = """
        <section class="glass-card rounded-2xl p-4 border border-emerald-500/20 bg-emerald-500/5 flex items-center justify-between">
            <div class="flex items-center gap-2.5">
                <span class="text-emerald-400 text-lg">✓</span>
                <span class="text-xs text-emerald-300 font-medium">Clean Audit Certification: 0 duplicate invoices, negative margins, or statistical outliers detected.</span>
            </div>
            <span class="text-[11px] text-emerald-400/80 font-mono">100% Data Integrity</span>
        </section>
        """

    # Format KPI cards HTML
    kpis_html = ""
    for k in kpis:
        kpis_html += f"""
        <div class="bg-white rounded-xl shadow-sm border border-slate-200 p-5 hover:shadow-md transition">
            <div class="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-1">{k.get('label', '')}</div>
            <div class="text-2xl font-bold text-slate-900 mb-1">{k.get('value', '')}</div>
            <div class="text-xs text-slate-400">{k.get('sub', '')}</div>
        </div>
        """

    # Format Table records
    table_headers_html = "".join([f'<th class="px-4 py-3 text-left text-xs font-bold text-slate-600 uppercase tracking-wider">{c}</th>' for c in df.columns[:10]])
    table_rows_html = ""
    for _, row in df.head(50).iterrows():
        cells = "".join([f'<td class="px-4 py-2.5 text-sm text-slate-700 whitespace-nowrap">{str(row[c]) if pd.notna(row[c]) else ""}</td>' for c in df.columns[:10]])
        table_rows_html += f'<tr class="border-b border-slate-100 hover:bg-slate-50 transition">{cells}</tr>'

    charts_json = json.dumps(charts or {}, ensure_ascii=False)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AutoBI Executive Dashboard — {filename}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        body {{ font-family: 'Plus Jakarta Sans', sans-serif; background-color: #0f172a; color: #f8fafc; }}
        .glass-card {{ background: rgba(30, 41, 59, 0.7); backdrop-filter: blur(12px); border: 1px solid rgba(255, 255, 255, 0.08); }}
    </style>
</head>
<body class="p-6 md:p-10 min-h-screen">
    <div class="max-w-7xl mx-auto space-y-8">
        <!-- Header -->
        <header class="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-6 border-b border-slate-800">
            <div>
                <div class="flex items-center gap-3">
                    <span class="text-3xl">{domain_icon}</span>
                    <h1 class="text-2xl md:text-3xl font-extrabold text-white tracking-tight">{domain_label} Executive Overview</h1>
                </div>
                <p class="text-slate-400 text-sm mt-1">Generated by AutoBI Studio from <span class="text-indigo-400 font-semibold">{filename}</span></p>
            </div>
            <div class="flex items-center gap-3">
                <span class="px-3 py-1 bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 rounded-full text-xs font-semibold flex items-center gap-1.5">
                    <span class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span> Modeled & Cleaned
                </span>
                <button onclick="window.print()" class="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium rounded-lg border border-slate-700 transition">
                    🖨️ Export PDF / Print
                </button>
            </div>
        </header>

        <!-- CFO Red-Flags & Audit Exceptions -->
        {alerts_html}

        <!-- Multi-Currency & Pareto Insights -->
        {fx_banner_html}
        {pareto_banner_html}

        <!-- KPI Grid -->
        <section class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
            <!-- Dynamic KPIs -->
            {''.join([f'''
            <div class="glass-card rounded-xl p-4 hover:border-indigo-500/30 transition">
                <div class="text-[11px] font-semibold uppercase tracking-wider text-slate-400 mb-1">{k.get('label', '')}</div>
                <div class="text-xl md:text-2xl font-bold text-white mb-1">{k.get('value', '')}</div>
                <div class="text-[11px] text-slate-500">{k.get('sub', '')}</div>
            </div>
            ''' for k in kpis])}
        </section>

        <!-- Interactive Visualizations -->
        <section class="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div class="glass-card rounded-2xl p-6">
                <h3 id="chart1Title" class="text-base font-bold text-slate-200 mb-4">Breakdown Analysis</h3>
                <div class="relative h-64 md:h-80">
                    <canvas id="chart1Canvas"></canvas>
                </div>
            </div>
            <div class="glass-card rounded-2xl p-6">
                <h3 id="chart2Title" class="text-base font-bold text-slate-200 mb-4">Distribution Analysis</h3>
                <div class="relative h-64 md:h-80">
                    <canvas id="chart2Canvas"></canvas>
                </div>
            </div>
        </section>

        <!-- Data Preview Table -->
        <section class="glass-card rounded-2xl p-6 overflow-hidden">
            <div class="flex items-center justify-between mb-4">
                <h3 class="text-base font-bold text-slate-200">Modeled Records Preview (First 50 Rows)</h3>
                <span class="text-xs text-slate-400 font-mono">Total Records: {len(df):,}</span>
            </div>
            <div class="overflow-x-auto">
                <table class="w-full text-left border-collapse">
                    <thead>
                        <tr class="border-b border-slate-700 bg-slate-900/50">
                            {table_headers_html}
                        </tr>
                    </thead>
                    <tbody class="divide-y divide-slate-800 text-sm text-slate-300 font-mono">
                        {table_rows_html}
                    </tbody>
                </table>
            </div>
        </section>

        <!-- Footer -->
        <footer class="pt-6 border-t border-slate-800 text-center text-xs text-slate-500">
            AutoBI Engine — Power BI Ready Semantic Architecture
        </footer>
    </div>

    <script>
        const chartData = {charts_json};
        
        // Render Chart 1
        if (chartData.chart1) {{
            document.getElementById('chart1Title').textContent = chartData.chart1.title || 'Analysis';
            const ctx1 = document.getElementById('chart1Canvas').getContext('2d');
            new Chart(ctx1, {{
                type: chartData.chart1.type || 'bar',
                data: {{
                    labels: Object.keys(chartData.chart1.data || {{}}),
                    datasets: [{{
                        label: chartData.chart1.title,
                        data: Object.values(chartData.chart1.data || {{}}),
                        backgroundColor: chartData.chart1.type === 'doughnut' ? 
                            ['#6366f1', '#06b6d4', '#10b981', '#f59e0b', '#ec4899', '#8b5cf6', '#3b82f6', '#14b8a6'] : '#6366f1',
                        borderRadius: 6
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{ legend: {{ labels: {{ color: '#94a3b8' }} }} }},
                    scales: chartData.chart1.type === 'bar' ? {{
                        x: {{ ticks: {{ color: '#94a3b8' }}, grid: {{ color: 'rgba(255,255,255,0.05)' }} }},
                        y: {{ ticks: {{ color: '#94a3b8' }}, grid: {{ color: 'rgba(255,255,255,0.05)' }} }}
                    }} : {{}}
                }}
            }});
        }}

        // Render Chart 2
        if (chartData.chart2) {{
            document.getElementById('chart2Title').textContent = chartData.chart2.title || 'Distribution';
            const ctx2 = document.getElementById('chart2Canvas').getContext('2d');
            new Chart(ctx2, {{
                type: chartData.chart2.type || 'doughnut',
                data: {{
                    labels: Object.keys(chartData.chart2.data || {{}}),
                    datasets: [{{
                        label: chartData.chart2.title,
                        data: Object.values(chartData.chart2.data || {{}}),
                        backgroundColor: ['#06b6d4', '#10b981', '#6366f1', '#f59e0b', '#ec4899', '#8b5cf6', '#3b82f6', '#14b8a6'],
                        borderRadius: 6
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{ legend: {{ labels: {{ color: '#94a3b8' }} }} }},
                    scales: chartData.chart2.type === 'bar' ? {{
                        x: {{ ticks: {{ color: '#94a3b8' }}, grid: {{ color: 'rgba(255,255,255,0.05)' }} }},
                        y: {{ ticks: {{ color: '#94a3b8' }}, grid: {{ color: 'rgba(255,255,255,0.05)' }} }}
                    }} : {{}}
                }}
            }});
        }}
    </script>
</body>
</html>
"""
    return html
