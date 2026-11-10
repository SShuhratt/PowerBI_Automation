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
    const sheetPickerWrap = document.getElementById('sheetPickerWrap');
    const sheetSelect = document.getElementById('sheetSelect');
    const previewDashboardBtn = document.getElementById('previewDashboardBtn');
    const purgeDataBtn = document.getElementById('purgeDataBtn');
    const purgeBanner = document.getElementById('purgeBanner');
    const authGateModal = document.getElementById('authGateModal');
    const authForm = document.getElementById('authForm');
    const authEmailInput = document.getElementById('authEmailInput');
    const authPasscodeInput = document.getElementById('authPasscodeInput');
    const authErrorMsg = document.getElementById('authErrorMsg');
    const userStatusBadge = document.getElementById('userStatusBadge');
    const userEmailSpan = document.getElementById('userEmailSpan');
    const logoutBtn = document.getElementById('logoutBtn');
    const tabModeFile = document.getElementById('tabModeFile');
    const tabModeGSheets = document.getElementById('tabModeGSheets');
    const gsheetsSection = document.getElementById('gsheetsSection');
    const gsheetsForm = document.getElementById('gsheetsForm');
    const gsheetsUrlInput = document.getElementById('gsheetsUrlInput');
    const sendTelegramBtn = document.getElementById('sendTelegramBtn');
    const telegramModal = document.getElementById('telegramModal');
    const closeTelegramModalBtn = document.getElementById('closeTelegramModalBtn');
    const telegramDispatchForm = document.getElementById('telegramDispatchForm');
    const telegramChatIdInput = document.getElementById('telegramChatIdInput');
    const telegramBotTokenInput = document.getElementById('telegramBotTokenInput');
    const telegramStatusMsg = document.getElementById('telegramStatusMsg');
    const telegramConfigStatus = document.getElementById('telegramConfigStatus');
    const telegramSubmitBtn = document.getElementById('telegramSubmitBtn');

    // Check workspace authentication status
    async function checkAuthStatus() {
        try {
            const res = await fetch('/api/auth/status');
            const data = await res.json();
            if (data.auth_enabled) {
                if (!data.authenticated) {
                    if (authGateModal) authGateModal.style.display = 'flex';
                    if (userStatusBadge) userStatusBadge.style.display = 'none';
                    if (logoutBtn) logoutBtn.style.display = 'none';
                } else {
                    if (authGateModal) authGateModal.style.display = 'none';
                    if (userStatusBadge) {
                        userStatusBadge.style.display = 'inline-flex';
                        if (userEmailSpan) userEmailSpan.textContent = data.user || 'Authenticated';
                    }
                    if (logoutBtn) logoutBtn.style.display = 'inline-flex';
                }
            } else {
                if (authGateModal) authGateModal.style.display = 'none';
            }
        } catch (e) {
            console.error('Failed to verify auth status', e);
        }
    }

    if (authForm) {
        authForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            if (authErrorMsg) authErrorMsg.style.display = 'none';
            const email = authEmailInput ? authEmailInput.value.trim() : '';
            const passcode = authPasscodeInput ? authPasscodeInput.value.trim() : '';

            try {
                const res = await fetch('/api/auth/login', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ email: email, passcode: passcode })
                });
                const data = await res.json();
                if (data.success) {
                    if (authGateModal) authGateModal.style.display = 'none';
                    if (userStatusBadge) {
                        userStatusBadge.style.display = 'inline-flex';
                        if (userEmailSpan) userEmailSpan.textContent = data.user || email;
                    }
                    if (logoutBtn) logoutBtn.style.display = 'inline-flex';
                } else {
                    if (authErrorMsg) {
                        authErrorMsg.textContent = data.error || 'Authentication failed.';
                        authErrorMsg.style.display = 'block';
                    }
                }
            } catch (err) {
                if (authErrorMsg) {
                    authErrorMsg.textContent = 'Server connection error: ' + err.message;
                    authErrorMsg.style.display = 'block';
                }
            }
        });
    }

    if (logoutBtn) {
        logoutBtn.addEventListener('click', async () => {
            await fetch('/api/auth/logout', { method: 'POST' });
            window.location.reload();
        });
    }

    // Call on load
    checkAuthStatus();

    // --- Telegram Executive Digest Dispatcher ---
    if (sendTelegramBtn) {
        sendTelegramBtn.addEventListener('click', async () => {
            if (!currentSessionId) {
                alert('Please upload or analyze a dataset first before sending report to Telegram.');
                return;
            }

            // Reset status and inputs
            if (telegramStatusMsg) {
                telegramStatusMsg.style.display = 'none';
                telegramStatusMsg.textContent = '';
            }

            // Fetch server Telegram Bot configuration status
            try {
                const configRes = await fetch('/api/telegram/config');
                const configData = await configRes.json();
                if (telegramConfigStatus) {
                    if (configData.configured) {
                        telegramConfigStatus.style.background = 'rgba(16, 185, 129, 0.15)';
                        telegramConfigStatus.style.border = '1px solid rgba(16, 185, 129, 0.3)';
                        telegramConfigStatus.style.color = '#6ee7b7';
                        telegramConfigStatus.innerHTML = `<span>✓ Server bot token active. Default chat ID configured (${configData.default_chat_id}).</span>`;
                        if (telegramChatIdInput) {
                            telegramChatIdInput.placeholder = "Pre-configured in server (leave blank to use default)";
                            telegramChatIdInput.required = false;
                        }
                    } else if (configData.has_token) {
                        const botName = configData.bot_username || '@auto_bibot';
                        const cleanBotName = botName.replace('@', '');
                        telegramConfigStatus.style.background = 'rgba(6, 182, 212, 0.15)';
                        telegramConfigStatus.style.border = '1px solid rgba(6, 182, 212, 0.3)';
                        telegramConfigStatus.style.color = '#67e8f9';
                        telegramConfigStatus.innerHTML = `<span>✓ Server bot connected: <a href="https://t.me/${cleanBotName}" target="_blank" style="color: #38bdf8; font-weight: 700; text-decoration: underline;">${botName}</a>. Enter target Chat ID or Channel username below.</span>`;
                        if (telegramBotTokenInput) {
                            telegramBotTokenInput.placeholder = `Pre-configured (${botName})`;
                        }
                        if (telegramChatIdInput) telegramChatIdInput.required = true;
                    } else {
                        telegramConfigStatus.style.background = 'rgba(245, 158, 11, 0.15)';
                        telegramConfigStatus.style.border = '1px solid rgba(245, 158, 11, 0.3)';
                        telegramConfigStatus.style.color = '#fcd34d';
                        telegramConfigStatus.innerHTML = `<span>⚠️ No server credentials set. Please provide both Chat ID and Bot Token below.</span>`;
                        if (telegramChatIdInput) telegramChatIdInput.required = true;
                    }
                }
            } catch (err) {
                console.warn('Unable to query Telegram config:', err);
            }

            if (telegramModal) telegramModal.style.display = 'flex';
        });
    }

    if (closeTelegramModalBtn && telegramModal) {
        closeTelegramModalBtn.addEventListener('click', () => {
            telegramModal.style.display = 'none';
        });
    }

    if (telegramModal) {
        telegramModal.addEventListener('click', (e) => {
            if (e.target === telegramModal) {
                telegramModal.style.display = 'none';
            }
        });
    }

    if (telegramDispatchForm) {
        telegramDispatchForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            if (!currentSessionId) {
                alert('Session expired. Please re-run analysis.');
                return;
            }

            if (telegramSubmitBtn) {
                telegramSubmitBtn.disabled = true;
                telegramSubmitBtn.textContent = '✈️ Dispatching...';
            }
            if (telegramStatusMsg) {
                telegramStatusMsg.style.display = 'none';
                telegramStatusMsg.textContent = '';
            }

            try {
                const chatIdVal = telegramChatIdInput ? telegramChatIdInput.value.trim() : '';
                const botTokenVal = telegramBotTokenInput ? telegramBotTokenInput.value.trim() : '';

                const res = await fetch('/api/telegram/dispatch', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        session_id: currentSessionId,
                        chat_id: chatIdVal || undefined,
                        bot_token: botTokenVal || undefined
                    })
                });

                const data = await res.json();
                if (res.ok && data.success) {
                    if (telegramStatusMsg) {
                        telegramStatusMsg.style.display = 'block';
                        telegramStatusMsg.style.background = 'rgba(16, 185, 129, 0.15)';
                        telegramStatusMsg.style.borderColor = 'rgba(16, 185, 129, 0.3)';
                        telegramStatusMsg.style.color = '#6ee7b7';
                        telegramStatusMsg.innerHTML = `<b>✓ Dispatched successfully!</b> Sent executive digest and HTML dashboard to Telegram (Msg ID #${data.message_id || 'OK'}).`;
                    }
                    setTimeout(() => {
                        if (telegramModal) telegramModal.style.display = 'none';
                        if (telegramSubmitBtn) {
                            telegramSubmitBtn.disabled = false;
                            telegramSubmitBtn.textContent = '✈️ Send Report';
                        }
                    }, 1800);
                } else {
                    if (telegramStatusMsg) {
                        telegramStatusMsg.style.display = 'block';
                        telegramStatusMsg.style.background = 'rgba(239, 68, 68, 0.15)';
                        telegramStatusMsg.style.borderColor = 'rgba(239, 68, 68, 0.3)';
                        telegramStatusMsg.style.color = '#fca5a5';
                        telegramStatusMsg.textContent = data.error || 'Failed to dispatch report to Telegram.';
                    }
                    if (telegramSubmitBtn) {
                        telegramSubmitBtn.disabled = false;
                        telegramSubmitBtn.textContent = '✈️ Send Report';
                    }
                }
            } catch (err) {
                if (telegramStatusMsg) {
                    telegramStatusMsg.style.display = 'block';
                    telegramStatusMsg.style.background = 'rgba(239, 68, 68, 0.15)';
                    telegramStatusMsg.style.borderColor = 'rgba(239, 68, 68, 0.3)';
                    telegramStatusMsg.style.color = '#fca5a5';
                    telegramStatusMsg.textContent = 'Network error: ' + err.message;
                }
                if (telegramSubmitBtn) {
                    telegramSubmitBtn.disabled = false;
                    telegramSubmitBtn.textContent = '✈️ Send Report';
                }
            }
        });
    }

    // Chart Instances
    let chart1Instance = null;
    let chart2Instance = null;

    // Current State
    let currentSessionId = null;
    let currentLastFile = null;
    let currentLastDomain = 'sales';

    // Ingestion Mode Toggles (File vs Google Sheets)
    if (tabModeFile && tabModeGSheets && dropzone && gsheetsSection) {
        tabModeFile.addEventListener('click', () => {
            tabModeFile.classList.add('active');
            tabModeGSheets.classList.remove('active');
            dropzone.style.display = 'flex';
            gsheetsSection.style.display = 'none';
        });

        tabModeGSheets.addEventListener('click', () => {
            tabModeGSheets.classList.add('active');
            tabModeFile.classList.remove('active');
            dropzone.style.display = 'none';
            gsheetsSection.style.display = 'block';
        });
    }

    if (gsheetsForm) {
        gsheetsForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const url = gsheetsUrlInput ? gsheetsUrlInput.value.trim() : '';
            if (!url) return;

            showLoading('Connecting and analyzing Google Sheet...');
            try {
                const res = await fetch('/api/ingest-url', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ url: url })
                });
                const data = await res.json();
                if (data.success) {
                    renderResults(data);
                } else {
                    alert('Google Sheets Error: ' + (data.error || 'Failed to ingest sheet.'));
                    uploadCard.style.display = 'block';
                }
            } catch (err) {
                alert('Connection Error: ' + err.message);
                uploadCard.style.display = 'block';
            } finally {
                hideLoading();
            }
        });
    }

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
        if (purgeBanner) purgeBanner.style.display = 'none';
        uploadCard.style.display = 'none';
        loadingCard.style.display = 'block';
        resultsContainer.style.display = 'none';
        document.getElementById('loadingFileName').textContent = fileName;
    }

    function hideLoading() {
        loadingCard.style.display = 'none';
    }

    async function handleFileUpload(file, domainOverride = null, sheetOverride = null) {
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
        if (sheetOverride) {
            formData.append('sheet', sheetOverride);
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
        activeFileBadge.textContent = data.is_live_url ? `${data.filename} 🌐 (Live Google Sheet)` : data.filename;

        // 1. Domain Badge & Switcher
        const dom = data.domain;
        if (domainBadge && dom) {
            domainBadge.textContent = `${dom.icon} ${dom.label} (${dom.confidence}% match)`;
            if (domainSelect) {
                domainSelect.value = dom.key;
            }
        }

        // Executive Anomaly Alert Banner
        const alertBanner = document.getElementById('dashboardAlertBanner');
        if (alertBanner) {
            const summary = data.anomaly_summary || {};
            if (summary.has_critical || (summary.total_flags && summary.total_flags > 0)) {
                alertBanner.style.display = 'flex';
                alertBanner.innerHTML = `
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <span>🚨</span>
                        <span><strong>Executive risk alert:</strong> Found ${summary.critical_count || 0} critical risk(s) and ${summary.warning_count || 0} warning(s) in this dataset.</span>
                    </div>
                    <button id="viewAuditRiskLink" style="background: none; border: none; color: #f43f5e; text-decoration: underline; font-weight: 600; cursor: pointer; font-size: 13px;">Review audit details →</button>
                `;
                const btn = document.getElementById('viewAuditRiskLink');
                if (btn) {
                    btn.onclick = () => {
                        const auditTabBtn = document.querySelector('.tab-btn[data-tab="tabAudit"]');
                        if (auditTabBtn) auditTabBtn.click();
                    };
                }
            } else {
                alertBanner.style.display = 'none';
            }
        }

        // Multi-Sheet Tab Picker
        if (sheetPickerWrap && sheetSelect && data.sheet_info) {
            const sheets = data.sheet_info.available_sheets || [];
            if (sheets.length > 1) {
                sheetSelect.innerHTML = '';
                sheets.forEach(s => {
                    const opt = document.createElement('option');
                    opt.value = s;
                    opt.textContent = `📑 ${s}`;
                    if (s === data.sheet_info.selected_sheet) {
                        opt.selected = true;
                    }
                    sheetSelect.appendChild(opt);
                });
                sheetPickerWrap.style.display = 'flex';
                sheetSelect.onchange = () => {
                    if (currentLastFile) {
                        handleFileUpload(currentLastFile, domainSelect ? domainSelect.value : null, sheetSelect.value);
                    }
                };
            } else {
                sheetPickerWrap.style.display = 'none';
            }
        } else if (sheetPickerWrap) {
            sheetPickerWrap.style.display = 'none';
        }

        // Set download link
        if (downloadZipBtn) {
            downloadZipBtn.onclick = () => {
                window.location.href = `/api/download/${currentSessionId}`;
            };
        }

        // Set live executive dashboard preview link
        if (previewDashboardBtn) {
            previewDashboardBtn.href = `/api/preview/${currentSessionId}`;
        }

        // Configure explicit Data Privacy Purge
        if (purgeDataBtn) {
            purgeDataBtn.onclick = async () => {
                if (!confirm("Are you sure you want to permanently purge all data from this session? This will wipe the cleaned dataset and all artifacts from server RAM and disk.")) {
                    return;
                }
                try {
                    const purgeRes = await fetch(`/api/purge/${currentSessionId}`, { method: 'POST' });
                    const purgeJson = await purgeRes.json();

                    // Reset UI to clean state
                    resultsContainer.style.display = 'none';
                    uploadCard.style.display = 'block';
                    fileInput.value = '';
                    currentLastFile = null;
                    currentSessionId = null;

                    // Show purge confirmation
                    if (purgeBanner) {
                        purgeBanner.style.display = 'flex';
                        const textEl = document.getElementById('purgeBannerText');
                        if (textEl && purgeJson.message) {
                            textEl.textContent = purgeJson.message;
                        }
                    }
                } catch (e) {
                    alert('Error purging data: ' + e.message);
                }
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
            if (gsheetsUrlInput) gsheetsUrlInput.value = '';
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

        // 1. CFO Red-Flags & Anomaly Detection Engine
        const anomalies = audit.anomalies || [];
        const anomalySummary = audit.anomaly_summary || {};
        if (anomalies.length > 0) {
            const card = document.createElement('div');
            card.className = 'audit-card';
            card.innerHTML = `
                <div class="audit-card-header">
                    <div class="audit-icon rose">🚨</div>
                    <div style="flex: 1;">
                        <div style="display: flex; align-items: center; justify-content: space-between;">
                            <h3>CFO Red-Flags & Anomaly Detection (${anomalies.length} Flagged)</h3>
                            <div style="display: flex; gap: 6px;">
                                ${anomalySummary.critical_count > 0 ? `<span class="audit-item-badge" style="background: rgba(244,63,94,0.25); color: #fda4af;">${anomalySummary.critical_count} Critical</span>` : ''}
                                ${anomalySummary.warning_count > 0 ? `<span class="audit-item-badge" style="background: rgba(245,158,11,0.25); color: #fde68a;">${anomalySummary.warning_count} Warning</span>` : ''}
                                ${anomalySummary.info_count > 0 ? `<span class="audit-item-badge" style="background: rgba(56,189,248,0.25); color: #bae6fd;">${anomalySummary.info_count} Notice</span>` : ''}
                            </div>
                        </div>
                        <p class="text-xs text-slate-400">Automated audit checks for margin leakage, duplicate transactions, and extreme typo outliers.</p>
                    </div>
                </div>
            `;
            anomalies.forEach(item => {
                const el = document.createElement('div');
                el.className = 'audit-item';
                el.style.flexDirection = 'column';
                el.style.alignItems = 'flex-start';
                el.style.gap = '6px';

                const badgeBg = item.severity === 'critical' ? 'rgba(244,63,94,0.2)' : (item.severity === 'warning' ? 'rgba(245,158,11,0.2)' : 'rgba(56,189,248,0.2)');
                const badgeColor = item.severity === 'critical' ? '#fda4af' : (item.severity === 'warning' ? '#fde68a' : '#bae6fd');

                let sampleStr = '';
                if (item.sample_rows && item.sample_rows.length > 0) {
                    sampleStr = `<div style="font-size: 11px; font-family: monospace; color: #94a3b8; background: rgba(0,0,0,0.2); padding: 4px 8px; border-radius: 4px; width: 100%; overflow-x: auto;">Sample: ${JSON.stringify(item.sample_rows[0])}</div>`;
                }

                el.innerHTML = `
                    <div style="display: flex; justify-content: space-between; width: 100%; align-items: center;">
                        <span style="font-weight: 600; color: #e2e8f0;">[${escapeHtml(item.severity.toUpperCase())}] ${escapeHtml(item.title)}</span>
                        <span class="audit-item-badge" style="background: ${badgeBg}; color: ${badgeColor};">${item.affected_count} record(s) affected</span>
                    </div>
                    <span style="font-size: 12px; color: var(--text-muted);">${escapeHtml(item.description)}</span>
                    ${sampleStr}
                `;
                card.appendChild(el);
            });
            auditList.appendChild(card);
        } else {
            const card = document.createElement('div');
            card.className = 'audit-card';
            card.innerHTML = `
                <div class="audit-card-header">
                    <div class="audit-icon emerald">✓</div>
                    <div>
                        <h3>Clean Bill of Health: 0 Business Anomalies Detected</h3>
                        <p class="text-xs text-slate-400">All records verified with positive unit margins, valid unique IDs, and within 3σ statistical variance.</p>
                    </div>
                </div>
            `;
            auditList.appendChild(card);
        }

        // 2. 1C & ERP Cross-Tab Matrix Flattener
        const unpivot = audit.unpivoted_matrix;
        if (unpivot && unpivot.is_unpivoted) {
            const card = document.createElement('div');
            card.className = 'audit-card';
            card.innerHTML = `
                <div class="audit-card-header">
                    <div class="audit-icon indigo">🔄</div>
                    <div>
                        <h3>1C / ERP Cross-Tab Matrix Flattener Applied</h3>
                        <p class="text-xs text-slate-400">Automatically unpivoted wide monthly columns into standardized time-series rows for Power BI time intelligence.</p>
                    </div>
                </div>
                <div class="audit-item">
                    <span><strong>Temporal Columns Unpivoted:</strong> ${unpivot.temporal_columns.length} columns (${escapeHtml(unpivot.temporal_columns.slice(0, 4).join(', '))}${unpivot.temporal_columns.length > 4 ? '...' : ''})</span>
                    <span class="audit-item-badge">pd.melt() + Table.Unpivot</span>
                </div>
                <div class="audit-item">
                    <span><strong>Pruned Summary Columns:</strong> ${escapeHtml(unpivot.pruned_summary_columns.join(', ') || 'None')}</span>
                    <span class="audit-item-badge">Excluded from unpivot</span>
                </div>
                <div class="audit-item">
                    <span><strong>Row Transformation:</strong> ${unpivot.original_rows} raw matrix rows → ${unpivot.unpivoted_rows} granular records</span>
                    <span class="audit-item-badge">Standard Time Series</span>
                </div>
            `;
            auditList.appendChild(card);
        }

        // 3. Central Bank FX Normalization (CBU.uz)
        const fx = audit.fx_normalization;
        if (fx && fx.is_multi_currency) {
            const card = document.createElement('div');
            card.className = 'audit-card';
            const ratesText = Object.entries(fx.rates_applied || {})
                .filter(([c]) => c !== 'UZS')
                .map(([c, r]) => `1 ${c} = ${Number(r).toLocaleString()} UZS`)
                .join(' | ');

            card.innerHTML = `
                <div class="audit-card-header">
                    <div class="audit-icon indigo">💱</div>
                    <div>
                        <h3>Multi-Currency FX Normalization (CBU.uz)</h3>
                        <p class="text-xs text-slate-400">Converted mixed transaction currencies into standardized UZS and USD via official Central Bank of Uzbekistan rates.</p>
                    </div>
                </div>
                <div class="audit-item">
                    <span><strong>Detected Currencies:</strong> ${escapeHtml((fx.detected_currencies || []).join(', '))}</span>
                    <span class="audit-item-badge">Column: <code>${escapeHtml(fx.currency_column || 'currency')}</code></span>
                </div>
                <div class="audit-item">
                    <span><strong>Official CBU Rates Applied:</strong> ${escapeHtml(ratesText || '1 USD = 12,000 UZS')}</span>
                    <span class="audit-item-badge">CBU Date: ${escapeHtml(fx.cbu_date || 'Today')}</span>
                </div>
                <div class="audit-item">
                    <span><strong>Normalized Columns Added:</strong> <code>${escapeHtml((fx.converted_columns || []).join(', '))}</code></span>
                    <span class="audit-item-badge">UZS & USD Standardized</span>
                </div>
            `;
            auditList.appendChild(card);
        }

        // 4. Pareto (80/20) ABC Segmentation
        const pareto = audit.pareto_segmentation;
        if (pareto && pareto.is_segmented) {
            const card = document.createElement('div');
            card.className = 'audit-card';
            card.innerHTML = `
                <div class="audit-card-header">
                    <div class="audit-icon emerald">🎯</div>
                    <div>
                        <h3>Pareto (80/20) ABC Driver Segmentation</h3>
                        <p class="text-xs text-slate-400">Identified vital high-volume contributors vs. long-tail drivers across <code>${escapeHtml(pareto.dimension_col || 'product')}</code>.</p>
                    </div>
                </div>
                <div class="audit-item">
                    <span><strong>Class A (Top 80% Vital Few):</strong> ${pareto.class_a_count} key driver(s)</span>
                    <span class="audit-item-badge" style="background: rgba(16,185,129,0.2); color: #6ee7b7;">${pareto.class_a_revenue_share}% Volume</span>
                </div>
                <div class="audit-item">
                    <span><strong>Class B (Next 15% Moderate):</strong> ${pareto.class_b_count} secondary driver(s)</span>
                    <span class="audit-item-badge" style="background: rgba(6,182,212,0.2); color: #67e8f9;">${pareto.class_b_revenue_share}% Volume</span>
                </div>
                <div class="audit-item">
                    <span><strong>Class C (Bottom 5% Long-Tail):</strong> ${pareto.class_c_count} minor item(s)</span>
                    <span class="audit-item-badge" style="background: rgba(148,163,184,0.2); color: #cbd5e1;">${pareto.class_c_revenue_share}% Volume</span>
                </div>
            `;
            auditList.appendChild(card);
        }

        // 5. Dropped Summary Rows
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
                } else if (c === 'abc_class') {
                    const badgeBg = val === 'A' ? 'rgba(16,185,129,0.25)' : (val === 'B' ? 'rgba(6,182,212,0.25)' : 'rgba(148,163,184,0.2)');
                    const badgeColor = val === 'A' ? '#6ee7b7' : (val === 'B' ? '#67e8f9' : '#cbd5e1');
                    td.innerHTML = `<span class="audit-item-badge" style="background: ${badgeBg}; color: ${badgeColor}; font-weight: 700;">Class ${val}</span>`;
                } else if (typeof val === 'number') {
                    if (c.includes('_uzs')) {
                        td.textContent = val.toLocaleString() + " so'm";
                        td.style.fontWeight = '500';
                    } else if (c.includes('revenue') || c.includes('price') || c.includes('spend') || c.includes('cost') || c.includes('salary') || c.includes('value') || c.includes('_usd')) {
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
