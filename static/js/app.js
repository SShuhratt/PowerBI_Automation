/**
 * app.js - AutoBI Web Portal Frontend Logic
 * Manages drag-and-drop file ingestion, asynchronous processing,
 * interactive Chart.js visualization, DAX copying, and zip export.
 */

document.addEventListener('DOMContentLoaded', () => {
    // DOM Elements
    const dropzone = document.getElementById('dropzone');
    const fileInput = document.getElementById('fileInput');
    const browseBtn = document.getElementById('browseBtn');
    const sampleBtn = document.getElementById('sampleBtn');
    const uploadCard = document.getElementById('uploadCard');
    const loadingCard = document.getElementById('loadingCard');
    const resultsContainer = document.getElementById('resultsContainer');
    const downloadZipBtn = document.getElementById('downloadZipBtn');
    const activeFileBadge = document.getElementById('activeFileBadge');

    // Chart Instances
    let catChartInstance = null;
    let regChartInstance = null;
    let statusChartInstance = null;

    // Current Session
    let currentSessionId = null;

    // --- Drag and Drop Events ---
    if (dropzone) {
        ['dragenter', 'dragover'].forEach(eventName => {
            dropzone.addEventListener(eventName, (e) => {
                e.preventDefault();
                e.stopPropagation();
                dropzone.classList.add('drag-over');
            }, false);
        });

        ['dragleave', 'drop'].forEach(eventName => {
            dropzone.addEventListener(eventName, (e) => {
                e.preventDefault();
                e.stopPropagation();
                dropzone.classList.remove('drag-over');
            }, false);
        });

        dropzone.addEventListener('drop', (e) => {
            const dt = e.dataTransfer;
            const files = dt.files;
            if (files.length > 0) {
                handleFileUpload(files[0]);
            }
        });

        dropzone.addEventListener('click', (e) => {
            if (e.target !== browseBtn && e.target !== sampleBtn && !sampleBtn.contains(e.target)) {
                fileInput.click();
            }
        });
    }

    if (browseBtn) {
        browseBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            fileInput.click();
        });
    }

    if (fileInput) {
        fileInput.addEventListener('change', () => {
            if (fileInput.files.length > 0) {
                handleFileUpload(fileInput.files[0]);
            }
        });
    }

    if (sampleBtn) {
        sampleBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            handleSampleRun();
        });
    }

    // --- API Calls ---
    function showLoading(fileName) {
        uploadCard.style.display = 'none';
        loadingCard.style.display = 'block';
        resultsContainer.style.display = 'none';
        document.getElementById('loadingFileName').textContent = fileName;
    }

    function hideLoading() {
        loadingCard.style.display = 'none';
    }

    async function handleFileUpload(file) {
        const ext = file.name.split('.').pop().toLowerCase();
        if (!['xlsx', 'xls', 'csv'].includes(ext)) {
            alert(`Unsupported file type: .${ext}. Please upload an Excel (.xlsx, .xls) or CSV file.`);
            return;
        }

        showLoading(file.name);
        const formData = new FormData();
        formData.append('file', file);

        try {
            const res = await fetch('/api/upload', {
                method: 'POST',
                body: formData
            });
            const data = await res.json();
            if (data.success) {
                renderResults(data);
            } else {
                alert('Analysis Error: ' + (data.error || 'Failed to process spreadsheet.'));
                uploadCard.style.display = 'block';
            }
        } catch (err) {
            alert('Server Error: ' + err.message);
            uploadCard.style.display = 'block';
        } finally {
            hideLoading();
        }
    }

    async function handleSampleRun() {
        showLoading('power_bi_test_sample.xlsx (Demo File)');
        try {
            const res = await fetch('/api/sample', { method: 'POST' });
            const data = await res.json();
            if (data.success) {
                renderResults(data);
            } else {
                alert('Sample Run Error: ' + (data.error || 'Failed to load sample dataset.'));
                uploadCard.style.display = 'block';
            }
        } catch (err) {
            alert('Server Error: ' + err.message);
            uploadCard.style.display = 'block';
        } finally {
            hideLoading();
        }
    }

    // --- Render Results ---
    function renderResults(data) {
        currentSessionId = data.session_id;
        activeFileBadge.textContent = data.filename;

        // Set download link
        if (downloadZipBtn) {
            downloadZipBtn.onclick = () => {
                window.location.href = `/api/download/${currentSessionId}`;
            };
        }

        // 1. KPI Cards
        const kpis = data.kpis;
        document.getElementById('kpiRev').textContent = formatCurrency(kpis.total_revenue);
        document.getElementById('kpiUnits').textContent = kpis.total_units.toLocaleString();
        document.getElementById('kpiOrders').textContent = kpis.total_orders.toLocaleString();
        document.getElementById('kpiAov').textContent = formatCurrency(kpis.aov);
        document.getElementById('kpiCompletedRev').textContent = formatCurrency(kpis.completed_rev);
        document.getElementById('kpiCancelRate').textContent = kpis.cancellation_rate + '%';
        document.getElementById('kpiCancelSub').textContent = `Lost Rev: ${formatCurrency(kpis.cancelled_rev)}`;

        // 2. Charts
        renderCharts(data.charts);

        // 3. Audit Trail
        renderAuditTrail(data.audit_log);

        // 4. DAX Measures & M Script
        renderCodeBlocks(data.dax_measures, data.power_query_m);

        // 5. Clean Table
        renderTable(data.table_columns, data.table_records);

        // Reveal Workspace
        uploadCard.style.display = 'none';
        resultsContainer.style.display = 'block';

        // Re-upload Button in header
        document.getElementById('resetUploadBtn').onclick = () => {
            resultsContainer.style.display = 'none';
            uploadCard.style.display = 'block';
            fileInput.value = '';
        };
    }

    // --- Formatters ---
    function formatCurrency(val) {
        return '$' + Number(val || 0).toLocaleString('en-US', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        });
    }

    // --- Chart Rendering ---
    function renderCharts(charts) {
        // Destroy old charts if exist
        if (catChartInstance) catChartInstance.destroy();
        if (regChartInstance) regChartInstance.destroy();

        // 1. Category Bar Chart
        const catCanvas = document.getElementById('categoryChart');
        if (catCanvas && charts.category) {
            const ctx = catCanvas.getContext('2d');
            const labels = Object.keys(charts.category);
            const values = Object.values(charts.category);

            catChartInstance = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'Gross Revenue ($)',
                        data: values,
                        backgroundColor: [
                            'rgba(99, 102, 241, 0.85)',
                            'rgba(6, 182, 212, 0.85)',
                            'rgba(16, 185, 129, 0.85)',
                            'rgba(245, 158, 11, 0.85)',
                        ],
                        borderColor: [
                            '#6366f1',
                            '#06b6d4',
                            '#10b981',
                            '#f59e0b',
                        ],
                        borderWidth: 1,
                        borderRadius: 6
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false },
                        tooltip: {
                            callbacks: {
                                label: (item) => 'Revenue: ' + formatCurrency(item.raw)
                            }
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            grid: { color: 'rgba(255, 255, 255, 0.05)' },
                            ticks: {
                                color: '#94a3b8',
                                callback: (v) => '$' + Number(v).toLocaleString()
                            }
                        },
                        x: {
                            grid: { display: false },
                            ticks: { color: '#cbd5e1', font: { weight: '500' } }
                        }
                    }
                }
            });
        }

        // 2. Region Doughnut Chart
        const regCanvas = document.getElementById('regionChart');
        if (regCanvas && charts.region) {
            const ctx = regCanvas.getContext('2d');
            const labels = Object.keys(charts.region);
            const values = Object.values(charts.region);

            regChartInstance = new Chart(ctx, {
                type: 'doughnut',
                data: {
                    labels: labels,
                    datasets: [{
                        data: values,
                        backgroundColor: [
                            '#6366f1',
                            '#06b6d4',
                            '#10b981',
                            '#f59e0b',
                            '#ec4899'
                        ],
                        borderWidth: 2,
                        borderColor: '#090d16'
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'bottom',
                            labels: { color: '#cbd5e1', padding: 14 }
                        },
                        tooltip: {
                            callbacks: {
                                label: (item) => `${item.label}: ${formatCurrency(item.raw)}`
                            }
                        }
                    },
                    cutout: '68%'
                }
            });
        }
    }

    // --- Audit Trail ---
    function renderAuditTrail(audit) {
        const auditList = document.getElementById('auditList');
        auditList.innerHTML = '';

        // Dropped Summary Rows
        if (audit.dropped_rows && audit.dropped_rows.length > 0) {
            const card = document.createElement('div');
            card.className = 'audit-card';
            card.innerHTML = `
                <div class="audit-card-header">
                    <div class="audit-icon rose">✕</div>
                    <div>
                        <h3>Eliminated ${audit.dropped_rows.length} Corrupting Trailer/Summary Row(s)</h3>
                        <p class="text-xs text-slate-400">Human totals and blank rows purged to prevent skewing DAX aggregations.</p>
                    </div>
                </div>
            `;
            audit.dropped_rows.forEach(item => {
                const el = document.createElement('div');
                el.className = 'audit-item';
                el.innerHTML = `
                    <span><strong>Row #${item.row_index}:</strong> ${item.reason}</span>
                    <span class="audit-item-badge">Preview: ${JSON.stringify(item.content_preview)}</span>
                `;
                card.appendChild(el);
            });
            auditList.appendChild(card);
        }

        // Inferred Calculations
        if (audit.inferred_calculations && audit.inferred_calculations.length > 0) {
            const card = document.createElement('div');
            card.className = 'audit-card';
            card.innerHTML = `
                <div class="audit-card-header">
                    <div class="audit-icon emerald">✓</div>
                    <div>
                        <h3>Auto-Computed ${audit.inferred_calculations.length} Missing Business Metric(s)</h3>
                        <p class="text-xs text-slate-400">Detected completely blank critical columns and reconstructed them.</p>
                    </div>
                </div>
            `;
            audit.inferred_calculations.forEach(item => {
                const el = document.createElement('div');
                el.className = 'audit-item';
                el.innerHTML = `
                    <span><strong>Column: <code>${item.column}</code></strong> → Formula: <code>${item.formula}</code></span>
                    <span class="audit-item-badge">${item.status}</span>
                `;
                card.appendChild(el);
            });
            auditList.appendChild(card);
        }

        // Schema Sanitization
        const card = document.createElement('div');
        card.className = 'audit-card';
        card.innerHTML = `
            <div class="audit-card-header">
                <div class="audit-icon indigo">⚙</div>
                <div>
                    <h3>Schema Normalization & Datatype Sanitization</h3>
                    <p class="text-xs text-slate-400">Headers standardized for clean DAX / Power Query syntax.</p>
                </div>
            </div>
            <div class="audit-item">
                <span><strong>Renamed Columns:</strong> ${Object.keys(audit.renamed_columns || {}).length} headers standardized.</span>
                <span class="audit-item-badge">No special chars, lowercase snake_case</span>
            </div>
            <div class="audit-item">
                <span><strong>Valid Clean Rows:</strong> ${audit.cleaned_row_count} of ${audit.raw_row_count} raw rows loaded.</span>
                <span class="audit-item-badge">100% Verified</span>
            </div>
        `;
        auditList.appendChild(card);
    }

    // --- DAX & Power Query Code Blocks ---
    function renderCodeBlocks(daxMeasures, mScript) {
        const daxList = document.getElementById('daxList');
        daxList.innerHTML = '';

        daxMeasures.forEach(m => {
            const card = document.createElement('div');
            card.className = 'code-card';
            card.innerHTML = `
                <div class="code-card-header">
                    <div>
                        <span class="code-card-title">${m.name}</span>
                        <span style="font-size: 11px; color: #94a3b8; margin-left: 8px;">Format: <code>${m.format}</code></span>
                    </div>
                    <button class="copy-btn" data-code="${encodeURIComponent(m.dax)}">Copy DAX</button>
                </div>
                <pre class="code-block">${escapeHtml(m.dax)}</pre>
            `;
            daxList.appendChild(card);
        });

        // Power Query M Script
        const pqCode = document.getElementById('powerQueryMCode');
        if (pqCode) {
            pqCode.textContent = mScript;
            const copyMBtn = document.getElementById('copyMBtn');
            if (copyMBtn) {
                copyMBtn.onclick = () => copyToClipboard(mScript, copyMBtn);
            }
        }

        // Attach copy handlers
        document.querySelectorAll('.copy-btn').forEach(btn => {
            btn.onclick = () => {
                const code = decodeURIComponent(btn.getAttribute('data-code'));
                copyToClipboard(code, btn);
            };
        });
    }

    function copyToClipboard(text, btn) {
        navigator.clipboard.writeText(text).then(() => {
            const originalText = btn.textContent;
            btn.textContent = 'Copied!';
            btn.classList.add('copied');
            setTimeout(() => {
                btn.textContent = originalText;
                btn.classList.remove('copied');
            }, 2000);
        });
    }

    function escapeHtml(str) {
        return str
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');
    }

    // --- Clean Data Explorer Table ---
    function renderTable(columns, rows) {
        const thead = document.getElementById('tableThead');
        const tbody = document.getElementById('tableTbody');
        thead.innerHTML = '';
        tbody.innerHTML = '';

        // Headers
        const trHead = document.createElement('tr');
        columns.forEach(c => {
            const th = document.createElement('th');
            th.textContent = c.replace(/_/g, ' ');
            trHead.appendChild(th);
        });
        thead.appendChild(trHead);

        // Rows
        rows.forEach(row => {
            const tr = document.createElement('tr');
            columns.forEach(c => {
                const td = document.createElement('td');
                const val = row[c];
                if (c === 'status') {
                    const badgeClass = val === 'Completed' ? 'status-completed' : (val === 'Cancelled' ? 'status-cancelled' : 'status-pending');
                    td.innerHTML = `<span class="status-badge ${badgeClass}">${val}</span>`;
                } else if (c.includes('revenue') || c.includes('price')) {
                    td.textContent = formatCurrency(val);
                    td.style.fontWeight = '500';
                } else {
                    td.textContent = val !== null && val !== undefined ? val : '';
                }
                tr.appendChild(td);
            });
            tbody.appendChild(tr);
        });
    }

    // --- Tab Switching ---
    const tabBtns = document.querySelectorAll('.tab-btn');
    const tabPanels = document.querySelectorAll('.tab-panel');

    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const target = btn.getAttribute('data-tab');

            tabBtns.forEach(b => b.classList.remove('active'));
            tabPanels.forEach(p => p.classList.remove('active'));

            btn.classList.add('active');
            const panel = document.getElementById(target);
            if (panel) panel.classList.add('active');
        });
    });
});
