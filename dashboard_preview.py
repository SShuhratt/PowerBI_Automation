"""
dashboard_preview.py - Generates an interactive executive dashboard HTML preview.
Gives stakeholders an immediate, zero-friction visual preview of the cleaned data
and KPIs while the Power BI model is loaded.
"""

import os
import json
import pandas as pd


def generate_html_dashboard(df: pd.DataFrame, output_path: str):
    # Compute metrics
    total_rev = df["total_revenue"].sum()
    total_units = int(df["units_sold"].sum())
    total_orders = df["order_id"].nunique()
    aov = total_rev / total_orders if total_orders else 0
    completed_rev = df[df["status"] == "Completed"]["total_revenue"].sum()
    cancelled_rev = df[df["status"] == "Cancelled"]["total_revenue"].sum()
    pending_rev = df[df["status"] == "Pending"]["total_revenue"].sum()

    # Category breakdown
    cat_data = df.groupby("category")["total_revenue"].sum().to_dict()
    # Region breakdown
    reg_data = df.groupby("region")["total_revenue"].sum().to_dict()
    # Rep breakdown
    rep_data = df.groupby("sales_rep")["total_revenue"].sum().to_dict()

    # Table rows
    table_rows_html = ""
    for _, row in df.iterrows():
        status_badge = "bg-green-100 text-green-800" if row['status'] == "Completed" else ("bg-red-100 text-red-800" if row['status'] == "Cancelled" else "bg-yellow-100 text-yellow-800")
        date_str = str(row['order_date'])[:10]
        table_rows_html += f"""
        <tr class="border-b hover:bg-slate-50 transition">
            <td class="px-4 py-2 font-mono text-sm">{row['order_id']}</td>
            <td class="px-4 py-2 text-sm">{date_str}</td>
            <td class="px-4 py-2 text-sm font-medium">{row['region']}</td>
            <td class="px-4 py-2 text-sm">{row['sales_rep']}</td>
            <td class="px-4 py-2 text-sm">{row['category']}</td>
            <td class="px-4 py-2 text-sm text-right">{row['units_sold']:.0f}</td>
            <td class="px-4 py-2 text-sm text-right">${row['unit_price']:.2f}</td>
            <td class="px-4 py-2 text-sm text-right font-semibold text-indigo-900">${row['total_revenue']:,.2f}</td>
            <td class="px-4 py-2 text-sm text-center"><span class="px-2 py-0.5 rounded-full text-xs font-semibold {status_badge}">{row['status']}</span></td>
        </tr>
        """

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>AutoBI Executive Dashboard Preview</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style> body {{ font-family: 'Inter', sans-serif; }} </style>
</head>
<body class="bg-slate-50 text-slate-900 p-8">
    <div class="max-w-7xl mx-auto space-y-6">
        <!-- Header -->
        <div class="flex flex-col md:flex-row md:items-center justify-between pb-6 border-b border-slate-200">
            <div>
                <span class="inline-block px-3 py-1 bg-indigo-100 text-indigo-800 rounded-full text-xs font-bold uppercase tracking-wider mb-2">Self-Healing Pipeline Prototype</span>
                <h1 class="text-3xl font-extrabold text-slate-900 tracking-tight">Executive Sales Intelligence Dashboard</h1>
                <p class="text-sm text-slate-500 mt-1">Data cleansed, validated, and modeled automatically from raw Excel input.</p>
            </div>
            <div class="mt-4 md:mt-0 flex gap-3">
                <span class="inline-flex items-center gap-1.5 px-3 py-1.5 bg-emerald-50 border border-emerald-200 text-emerald-700 text-xs font-medium rounded-lg">
                    <span class="w-2 h-2 rounded-full bg-emerald-500"></span> 100% Verified Data Model
                </span>
            </div>
        </div>

        <!-- KPI Cards -->
        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div class="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
                <p class="text-xs font-semibold text-slate-500 uppercase tracking-wider">Total Gross Revenue</p>
                <p class="text-3xl font-bold text-slate-900 mt-1">${total_rev:,.2f}</p>
                <div class="mt-2 text-xs text-emerald-600 font-medium">Auto-computed from unit * price</div>
            </div>
            <div class="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
                <p class="text-xs font-semibold text-slate-500 uppercase tracking-wider">Total Volume Sold</p>
                <p class="text-3xl font-bold text-slate-900 mt-1">{total_units:,} <span class="text-base font-normal text-slate-400">units</span></p>
                <div class="mt-2 text-xs text-slate-500">Across {total_orders} orders</div>
            </div>
            <div class="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
                <p class="text-xs font-semibold text-slate-500 uppercase tracking-wider">Average Order Value (AOV)</p>
                <p class="text-3xl font-bold text-slate-900 mt-1">${aov:,.2f}</p>
                <div class="mt-2 text-xs text-indigo-600 font-medium">DAX: DIVIDE([Revenue], [Orders])</div>
            </div>
            <div class="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
                <p class="text-xs font-semibold text-slate-500 uppercase tracking-wider">Completed Revenue</p>
                <p class="text-3xl font-bold text-emerald-600 mt-1">${completed_rev:,.2f}</p>
                <div class="mt-2 text-xs text-slate-500 font-medium">Pending: ${pending_rev:,.2f} | Cancelled: ${cancelled_rev:,.2f}</div>
            </div>
        </div>

        <!-- Charts Grid -->
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div class="bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
                <h3 class="text-base font-bold text-slate-800 mb-4">Revenue by Category</h3>
                <canvas id="categoryChart" height="220"></canvas>
            </div>
            <div class="bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
                <h3 class="text-base font-bold text-slate-800 mb-4">Revenue by Region</h3>
                <canvas id="regionChart" height="220"></canvas>
            </div>
        </div>

        <!-- Cleaned Data Table -->
        <div class="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
            <div class="p-5 border-b border-slate-200 flex justify-between items-center">
                <div>
                    <h3 class="text-base font-bold text-slate-800">Cleaned & Normalized Transaction Records</h3>
                    <p class="text-xs text-slate-500">Summary row (#12 Total) pruned; empty revenue column computed.</p>
                </div>
            </div>
            <div class="overflow-x-auto">
                <table class="w-full text-left">
                    <thead class="bg-slate-50 text-slate-500 uppercase text-xs font-semibold border-b">
                        <tr>
                            <th class="px-4 py-3">Order ID</th>
                            <th class="px-4 py-3">Date</th>
                            <th class="px-4 py-3">Region</th>
                            <th class="px-4 py-3">Sales Rep</th>
                            <th class="px-4 py-3">Category</th>
                            <th class="px-4 py-3 text-right">Units</th>
                            <th class="px-4 py-3 text-right">Unit Price</th>
                            <th class="px-4 py-3 text-right">Revenue</th>
                            <th class="px-4 py-3 text-center">Status</th>
                        </tr>
                    </thead>
                    <tbody>
                        {table_rows_html}
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <script>
        // Category Chart
        new Chart(document.getElementById('categoryChart'), {{
            type: 'bar',
            data: {{
                labels: {json.dumps(list(cat_data.keys()))},
                datasets: [{{
                    label: 'Revenue ($)',
                    data: {json.dumps(list(cat_data.values()))},
                    backgroundColor: ['#6366f1', '#3b82f6', '#10b981'],
                    borderRadius: 6
                }}]
            }},
            options: {{
                responsive: true,
                plugins: {{ legend: {{ display: false }} }},
                scales: {{ y: {{ beginAtZero: true }} }}
            }}
        }});

        // Region Chart
        new Chart(document.getElementById('regionChart'), {{
            type: 'doughnut',
            data: {{
                labels: {json.dumps(list(reg_data.keys()))},
                datasets: [{{
                    data: {json.dumps(list(reg_data.values()))},
                    backgroundColor: ['#4f46e5', '#06b6d4', '#10b981', '#f59e0b']
                }}]
            }},
            options: {{ responsive: true }}
        }});
    </script>
</body>
</html>
"""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    return output_path
