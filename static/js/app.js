/**
 * app.js - AutoBI Multi-Domain Web Portal Frontend Logic
 * Manages drag-and-drop file ingestion, domain recognition & switching,
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
    const domainBadge = document.getElementById('domainBadge');
    const domainSelect = document.getElementById('domainSelect');

    // Chart Instances
    let chart1Instance = null;
    let chart2Instance = null;

    // Current State
    let currentSessionId = null;
    let currentLastFile = null;
    let currentLastDomain = 'sales';

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
                currentLastFile = files[0];
                handleFileUpload(files[0]);
            }
        });

        dropzone.addEventListener('click', (e) => {
            if (e.target !== browseBtn && e.target !== sampleBtn && !sampleBtn.contains(e.target) && !e.target.classList.contains('demo-pill-btn')) {
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
                currentLastFile = fileInput.files[0];
                handleFileUpload(fileInput.files[0]);
            }
        });
    }

    if (sampleBtn) {
        sampleBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            handleSampleRun('sales');
        });
    }

    // Demo Pills
    document.querySelectorAll('.demo-pill-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            const domain = btn.getAttribute('data-domain');
            handleSampleRun(domain);
        });
    });

    // Domain Switcher in Results Banner
    if (domainSelect) {
        domainSelect.addEventListener('change', () => {
            const selectedDomain = domainSelect.value;
            if (currentLastFile) {
                handleFileUpload(currentLastFile, selectedDomain);
            } else {
                handleSampleRun(selectedDomain);
            }
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

    async function handleFileUpload(file, domainOverride = null) {
        const ext = file.name.split('.').pop().toLowerCase();
        if (!['xlsx', 'xls', 'csv'].includes(ext)) {
            alert(`Unsupported file type: .${ext}. Please upload an Excel (.xlsx, .xls) or CSV file.`);
            return;
        }

        showLoading(file.name);
        const formData = new FormData();
        formData.append('file', file);
        if (domainOverride) {
            formData.append('domain', domainOverride);
        }

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

    async function handleSampleRun(domain = 'sales') {
        currentLastDomain = domain;
        currentLastFile = null;
        showLoading(`Preset: ${domain.toUpperCase()} Demo Dataset`);

        try {
            const res = await fetch('/api/sample', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ domain: domain })
            });
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

        // 1. Domain Badge & Switcher
        const dom = data.domain;
        if (domainBadge && dom) {
            domainBadge.textContent = `${dom.icon} ${dom.label} (${dom.confidence}% match)`;
            if (domainSelect) {
                domainSelect.value = dom.key;
            }
        }

        // Set download link
        if (downloadZipBtn) {
            downloadZipBtn.onclick = () => {
                window.location.href = `/api/download/${currentSessionId}`;
            };
        }

        // 2. Dynamic KPI Cards
        renderKpis(data.kpis);

        // 3. Dynamic Charts
        renderCharts(data.charts);

        // 4. Audit Trail
        renderAuditTrail(data.audit_log);

        // 5. DAX Measures & M Script
        renderCodeBlocks(data.dax_measures, data.power_query_m, data.domain);

        // 6. Clean Table
        renderTable(data.table_columns, data.table_records);

        // Reveal Workspace
        uploadCard.style.display = 'none';
        resultsContainer.style.display = 'block';

        // Re-upload Button in header
        document.getElementById('resetUploadBtn').onclick = () => {
            resultsContainer.style.display = 'none';
            uploadCard.style.display = 'block';
            fileInput.value = '';
            currentLastFile = null;
        };
    }

    // --- Dynamic KPI Rendering ---
    function renderKpis(kpis) {
        const kpiGrid = document.getElementById('kpiGrid');
        kpiGrid.innerHTML = '';

        kpis.forEach(k => {
            const card = document.createElement('div');
            card.className = `kpi-card ${k.theme || ''}`;
            card.innerHTML = `
                <div class="kpi-label">${escapeHtml(k.label)}</div>
                <div class="kpi-value">${escapeHtml(k.value)}</div>
                <div class="kpi-subtext">${escapeHtml(k.sub || '')}</div>
            `;
            kpiGrid.appendChild(card);
        });
    }

    // --- Dynamic Chart Rendering ---
    function renderCharts(charts) {
        if (chart1Instance) chart1Instance.destroy();
        if (chart2Instance) chart2Instance.destroy();

        const colors = [
            '#6366f1', '#06b6d4', '#10b981', '#f59e0b', '#ec4899', '#8b5cf6'
        ];

        // Chart 1
        const c1Config = charts.chart1;
        const c1Title = document.getElementById('chart1Title');
        const c1Canvas = document.getElementById('chart1Canvas');

        if (c1Config && c1Canvas) {
            c1Title.textContent = c1Config.title;
            const ctx1 = c1Canvas.getContext('2d');
            const labels = Object.keys(c1Config.data);
            const values = Object.values(c1Config.data);

            chart1Instance = new Chart(ctx1, {
                type: c1Config.type || 'bar',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'Value',
                        data: values,
                        backgroundColor: c1Config.type === 'doughnut' ? colors : 'rgba(99, 102, 241, 0.85)',
                        borderColor: c1Config.type === 'doughnut' ? '#090d16' : '#6366f1',
                        borderWidth: 1,
                        borderRadius: 6
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: c1Config.type === 'doughnut', labels: { color: '#cbd5e1' } }
                    },
                    scales: c1Config.type === 'doughnut' ? {} : {
                        y: { beginAtZero: true, grid: { color: 'rgba(255, 255, 255, 0.05)' }, ticks: { color: '#94a3b8' } },
                        x: { grid: { display: false }, ticks: { color: '#cbd5e1' } }
                    }
                }
            });
        }

        // Chart 2
        const c2Config = charts.chart2;
        const c2Title = document.getElementById('chart2Title');
        const c2Canvas = document.getElementById('chart2Canvas');

        if (c2Config && c2Canvas) {
            c2Title.textContent = c2Config.title;
            const ctx2 = c2Canvas.getContext('2d');
            const labels = Object.keys(c2Config.data);
            const values = Object.values(c2Config.data);

            chart2Instance = new Chart(ctx2, {
                type: c2Config.type || 'doughnut',
                data: {
                    labels: labels,
                    datasets: [{
                        data: values,
                        backgroundColor: colors,
                        borderColor: '#090d16',
                        borderWidth: 2
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { position: 'bottom', labels: { color: '#cbd5e1', padding: 12 } }
                    },
                    cutout: c2Config.type === 'doughnut' ? '65%' : 0
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
                        <p class="text-xs text-slate-400">Reconstructed missing calculations from existing attributes.</p>
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
    function renderCodeBlocks(daxMeasures, mScript, domain) {
        const daxList = document.getElementById('daxList');
        const daxDomainTitle = document.getElementById('daxDomainTitle');
        const pqTableName = document.getElementById('pqTableName');

        if (daxDomainTitle && domain) {
            daxDomainTitle.textContent = `${domain.label} — DAX Measures (${daxMeasures.length})`;
        }
        if (pqTableName && domain) {
            pqTableName.textContent = `LoadData.m (Target Table: '${domain.table_name}')`;
        }

        daxList.innerHTML = '';
        daxMeasures.forEach(m => {
            const card = document.createElement('div');
            card.className = 'code-card';
            card.innerHTML = `
                <div class="code-card-header">
                    <div>
                        <span class="code-card-title">${escapeHtml(m.name)}</span>
                        <span style="font-size: 11px; color: #94a3b8; margin-left: 8px;">Format: <code>${escapeHtml(m.format)}</code></span>
                    </div>
                    <button class="copy-btn" data-code="${encodeURIComponent(m.dax)}">Copy DAX</button>
                </div>
                <pre class="code-block">${escapeHtml(m.dax)}</pre>
            `;
            daxList.appendChild(card);
        });

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
        return String(str || '')
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

        const trHead = document.createElement('tr');
        columns.forEach(c => {
            const th = document.createElement('th');
            th.textContent = c.replace(/_/g, ' ');
            trHead.appendChild(th);
        });
        thead.appendChild(trHead);

        rows.forEach(row => {
            const tr = document.createElement('tr');
            columns.forEach(c => {
                const td = document.createElement('td');
                const val = row[c];
                if (c === 'status') {
                    const badgeClass = val === 'Completed' ? 'status-completed' : (val === 'Cancelled' ? 'status-cancelled' : 'status-pending');
                    td.innerHTML = `<span class="status-badge ${badgeClass}">${val}</span>`;
                } else if (typeof val === 'number') {
                    if (c.includes('revenue') || c.includes('price') || c.includes('spend') || c.includes('cost') || c.includes('salary') || c.includes('value')) {
                        td.textContent = '$' + val.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
                        td.style.fontWeight = '500';
                    } else {
                        td.textContent = val.toLocaleString();
                    }
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
