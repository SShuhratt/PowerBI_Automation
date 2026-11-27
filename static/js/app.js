/**
 * app.js - AutoBI Multi-Domain Web Portal Frontend Logic
 * Manages drag-and-drop file ingestion, domain recognition & switching,
 * interactive Chart.js visualization, DAX copying, and zip export.
 */

document.addEventListener('DOMContentLoaded', () => {
    const i18n = window.autobiI18n;
    const t = (key, vars) => (i18n ? i18n.t(key, vars) : key);
    if (i18n) {
        i18n.applyTranslations();
        document.querySelectorAll('.lang-btn[data-lang]').forEach((btn) => {
            btn.addEventListener('click', () => {
                i18n.setLang(btn.getAttribute('data-lang'));
            });
        });
    }

    // Utility: XSS prevention
    function escapeHtml(text) {
        if (text === null || text === undefined) return '';
        return String(text)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

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
    const closeAuthModalBtn = document.getElementById('closeAuthModalBtn');
    const openAuthBtn = document.getElementById('openAuthBtn');
    const authForm = document.getElementById('authForm');
    const authTabLogin = document.getElementById('authTabLogin');
    const authTabRegister = document.getElementById('authTabRegister');
    const authFullNameGroup = document.getElementById('authFullNameGroup');
    const authFullNameInput = document.getElementById('authFullNameInput');
    const authEmailInput = document.getElementById('authEmailInput');
    const authPasscodeInput = document.getElementById('authPasscodeInput');
    const authConfirmGroup = document.getElementById('authConfirmGroup');
    const authConfirmInput = document.getElementById('authConfirmInput');
    const authSubmitBtn = document.getElementById('authSubmitBtn');
    const authSwitchPrompt = document.getElementById('authSwitchPrompt');
    const authSwitchLinkBtn = document.getElementById('authSwitchLinkBtn');
    const authErrorMsg = document.getElementById('authErrorMsg');
    const userStatusBadge = document.getElementById('userStatusBadge');
    const userEmailSpan = document.getElementById('userEmailSpan');
    const logoutBtn = document.getElementById('logoutBtn');
    const tabModeFile = document.getElementById('tabModeFile');
    const tabModeGSheets = document.getElementById('tabModeGSheets');
    const tabModeSql = document.getElementById('tabModeSql');
    const gsheetsSection = document.getElementById('gsheetsSection');
    const gsheetsForm = document.getElementById('gsheetsForm');
    const gsheetsUrlInput = document.getElementById('gsheetsUrlInput');
    const sqlSection = document.getElementById('sqlSection');
    const sqlForm = document.getElementById('sqlForm');
    const sqlUriInput = document.getElementById('sqlUriInput');
    const sqlQueryInput = document.getElementById('sqlQueryInput');
    const sendTelegramBtn = document.getElementById('sendTelegramBtn');
    const telegramModal = document.getElementById('telegramModal');
    const closeTelegramModalBtn = document.getElementById('closeTelegramModalBtn');
    const telegramDispatchForm = document.getElementById('telegramDispatchForm');
    const tgDirectStartLink = document.getElementById('tgDirectStartLink');
    const tgCheckConnectBtn = document.getElementById('tgCheckConnectBtn');
    const tgDetectBadge = document.getElementById('tgDetectBadge');
    const tgConnectedUserBanner = document.getElementById('tgConnectedUserBanner');
    const tgRecentChatsWrap = document.getElementById('tgRecentChatsWrap');
    const tgRecentPills = document.getElementById('tgRecentPills');
    const telegramTargetsInput = document.getElementById('telegramTargetsInput');
    const telegramStatusMsg = document.getElementById('telegramStatusMsg');
    const telegramConfigStatus = document.getElementById('telegramConfigStatus');
    const telegramSubmitBtn = document.getElementById('telegramSubmitBtn');

    // Progressive Auth State (UX: do not block initial landing view)
    let authEnabled = true;
    let isAuthenticated = false;
    let pendingAuthAction = null;
    let authMode = 'login'; // 'login' | 'register'
    let activeFilters = {};
    let activeDateRange = { from: '', to: '' };
    let activeChartOverrides = {};
    let currentReportId = null;
    let pendingRefreshReportId = null;
    const myReportsSection = document.getElementById('myReportsSection');
    const myReportsGrid = document.getElementById('myReportsGrid');
    const refreshFileInput = document.getElementById('refreshFileInput');
    const saveReportBtn = document.getElementById('saveReportBtn');
    const refreshReportBtn = document.getElementById('refreshReportBtn');

    function showAuthError(msg) {
        if (!authErrorMsg) return;
        authErrorMsg.textContent = msg;
        authErrorMsg.style.display = 'block';
    }

    function setAuthMode(mode) {
        authMode = mode === 'register' ? 'register' : 'login';
        const isReg = authMode === 'register';
        if (authErrorMsg) authErrorMsg.style.display = 'none';
        if (authTabLogin) {
            authTabLogin.classList.toggle('active', !isReg);
            authTabLogin.setAttribute('aria-selected', String(!isReg));
        }
        if (authTabRegister) {
            authTabRegister.classList.toggle('active', isReg);
            authTabRegister.setAttribute('aria-selected', String(isReg));
        }
        if (authFullNameGroup) authFullNameGroup.style.display = isReg ? 'flex' : 'none';
        if (authConfirmGroup) authConfirmGroup.style.display = isReg ? 'flex' : 'none';
        if (authPasscodeInput) {
            authPasscodeInput.setAttribute('autocomplete', isReg ? 'new-password' : 'current-password');
        }
        if (authSubmitBtn) {
            authSubmitBtn.textContent = isReg ? t('auth_register_submit_btn') : t('auth_submit_btn');
        }
        if (authSwitchPrompt) {
            authSwitchPrompt.textContent = isReg ? t('auth_switch_has_account') : t('auth_switch_no_account');
        }
        if (authSwitchLinkBtn) {
            authSwitchLinkBtn.textContent = isReg ? t('auth_switch_signin') : t('auth_switch_create');
        }
    }

    function openAuthModal(actionAfterLogin = null, mode = 'login') {
        pendingAuthAction = actionAfterLogin;
        setAuthMode(mode);
        if (authErrorMsg) authErrorMsg.style.display = 'none';
        // Never prefill credentials
        if (authFullNameInput) authFullNameInput.value = '';
        if (authEmailInput) authEmailInput.value = '';
        if (authPasscodeInput) authPasscodeInput.value = '';
        if (authConfirmInput) authConfirmInput.value = '';
        if (authGateModal) authGateModal.style.display = 'flex';
        if (authEmailInput) {
            setTimeout(() => authEmailInput.focus(), 50);
        }
    }

    if (authTabLogin) authTabLogin.addEventListener('click', () => setAuthMode('login'));
    if (authTabRegister) authTabRegister.addEventListener('click', () => setAuthMode('register'));
    if (authSwitchLinkBtn) {
        authSwitchLinkBtn.addEventListener('click', () => {
            setAuthMode(authMode === 'login' ? 'register' : 'login');
        });
    }
    if (i18n && typeof i18n.onChange === 'function') {
        i18n.onChange(() => setAuthMode(authMode));
    }

    function closeAuthModal() {
        if (authGateModal) authGateModal.style.display = 'none';
        pendingAuthAction = null;
    }

    function requireWorkspaceAuth(actionFn) {
        if (!authEnabled || isAuthenticated) {
            actionFn();
        } else {
            openAuthModal(actionFn);
        }
    }

    // Check workspace authentication status without popup gate on load
    async function checkAuthStatus() {
        try {
            const res = await fetch('/api/auth/status');
            const data = await res.json();
            authEnabled = Boolean(data.auth_enabled);
            if (data.auth_enabled) {
                if (!data.authenticated) {
                    isAuthenticated = false;
                    if (authGateModal) authGateModal.style.display = 'none';
                    if (openAuthBtn) openAuthBtn.style.display = 'inline-flex';
                    if (userStatusBadge) userStatusBadge.style.display = 'none';
                    if (logoutBtn) logoutBtn.style.display = 'none';
                } else {
                    isAuthenticated = true;
                    if (authGateModal) authGateModal.style.display = 'none';
                    if (openAuthBtn) openAuthBtn.style.display = 'none';
                    if (userStatusBadge) {
                        userStatusBadge.style.display = 'inline-flex';
                        if (userEmailSpan) userEmailSpan.textContent = data.user || t('badge_authenticated');
                    }
                    if (logoutBtn) logoutBtn.style.display = 'inline-flex';
                }
            } else {
                isAuthenticated = true;
                if (authGateModal) authGateModal.style.display = 'none';
                if (openAuthBtn) openAuthBtn.style.display = 'none';
            }
        } catch (e) {
            console.error('Failed to verify auth status', e);
        }
    }

    if (openAuthBtn) {
        openAuthBtn.addEventListener('click', () => openAuthModal(null));
    }

    if (closeAuthModalBtn) {
        closeAuthModalBtn.addEventListener('click', closeAuthModal);
    }

    if (authGateModal) {
        authGateModal.addEventListener('click', (e) => {
            if (e.target === authGateModal) closeAuthModal();
        });
    }

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && authGateModal && authGateModal.style.display === 'flex') {
            closeAuthModal();
        }
    });

    if (authForm) {
        authForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            if (authErrorMsg) authErrorMsg.style.display = 'none';
            const fullName = authFullNameInput ? authFullNameInput.value.trim() : '';
            const email = authEmailInput ? authEmailInput.value.trim() : '';
            const password = authPasscodeInput ? authPasscodeInput.value.trim() : '';
            const confirmPassword = authConfirmInput ? authConfirmInput.value.trim() : '';

            // Localized client-side validation (avoids browser OS-language tooltips)
            if (!email) {
                showAuthError(t('err_email_required'));
                if (authEmailInput) authEmailInput.focus();
                return;
            }
            if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
                showAuthError(t('err_email_invalid'));
                if (authEmailInput) authEmailInput.focus();
                return;
            }
            if (!password) {
                showAuthError(t('err_password_required'));
                if (authPasscodeInput) authPasscodeInput.focus();
                return;
            }
            if (authMode === 'register') {
                if (password.length < 8) {
                    showAuthError(t('err_password_min'));
                    if (authPasscodeInput) authPasscodeInput.focus();
                    return;
                }
                if (password !== confirmPassword) {
                    showAuthError(t('err_password_mismatch'));
                    if (authConfirmInput) authConfirmInput.focus();
                    return;
                }
            }

            const endpoint = authMode === 'register' ? '/api/auth/register' : '/api/auth/login';
            const bodyPayload = authMode === 'register'
                ? { full_name: fullName, email: email, password: password }
                : { email: email, password: password };

            try {
                const res = await fetch(endpoint, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(bodyPayload)
                });
                const data = await res.json();
                if (data.success) {
                    isAuthenticated = true;
                    const resumeAction = pendingAuthAction;
                    pendingAuthAction = null;
                    if (authGateModal) authGateModal.style.display = 'none';
                    if (openAuthBtn) openAuthBtn.style.display = 'none';
                    if (userStatusBadge) {
                        userStatusBadge.style.display = 'inline-flex';
                        if (userEmailSpan) userEmailSpan.textContent = data.user || email;
                    }
                    if (logoutBtn) logoutBtn.style.display = 'inline-flex';
                    loadSavedReports();
                    if (typeof resumeAction === 'function') {
                        resumeAction();
                    }
                } else {
                    const translated = data.error_code ? t(data.error_code) : null;
                    const msg = (translated && translated !== data.error_code) ? translated : (data.error || t('err_auth_failed'));
                    showAuthError(msg);
                }
            } catch (err) {
                showAuthError(t('err_server_conn') + err.message);
            }
        });
    }

    if (logoutBtn) {
        logoutBtn.addEventListener('click', async () => {
            await fetch('/api/auth/logout', { method: 'POST' });
            window.location.reload();
        });
    }

    // Call on load (and optionally launch ?demo=<domain> clicked from the 3D landing page)
    checkAuthStatus().then(() => {
        if (isAuthenticated) {
            loadSavedReports();
        }
        const params = new URLSearchParams(window.location.search);
        const demoDomain = (params.get('demo') || '').trim().toLowerCase();
        if (['sales', 'marketing', 'hr', 'inventory', 'finance', 'generic'].includes(demoDomain)) {
            if (window.history && window.history.replaceState) {
                params.delete('demo');
                const cleanSearch = params.toString();
                window.history.replaceState({}, '', window.location.pathname + (cleanSearch ? '?' + cleanSearch : ''));
            }
            requireWorkspaceAuth(() => handleSampleRun(demoDomain));
        }
    });

    if (window.autobiTheme && typeof window.autobiTheme.onChange === 'function') {
        window.autobiTheme.onChange(() => {
            if (lastRenderedData && lastRenderedData.charts) {
                renderCharts(lastRenderedData.charts);
            }
        });
    }

    // --- Telegram Executive Digest Dispatcher ---
    let tgConnectCode = null;
    let tgPollTimer = null;
    let connectedChatId = null;
    let connectedUserLabel = null;

    async function checkTelegramConnection() {
        if (!tgConnectCode) return;
        try {
            const res = await fetch(`/api/telegram/poll-connection?code=${tgConnectCode}`);
            const data = await res.json();
            if (data.connected && data.chat_id) {
                connectedChatId = data.chat_id;
                connectedUserLabel = data.label || data.first_name || data.username || String(data.chat_id);
                if (tgDetectBadge) {
                    tgDetectBadge.textContent = t('tg_connected');
                    tgDetectBadge.style.background = 'rgba(16, 185, 129, 0.25)';
                    tgDetectBadge.style.color = '#6ee7b7';
                }
                if (tgConnectedUserBanner) {
                    tgConnectedUserBanner.style.display = 'block';
                    tgConnectedUserBanner.innerHTML = t('tg_connected_banner', { user: escapeHtml(connectedUserLabel) });
                }
                if (tgPollTimer) {
                    clearInterval(tgPollTimer);
                    tgPollTimer = null;
                }
            }
        } catch (e) {
            console.warn('Telegram poll error:', e);
        }
    }

    function closeTgModal() {
        if (telegramModal) telegramModal.style.display = 'none';
        if (tgPollTimer) {
            clearInterval(tgPollTimer);
            tgPollTimer = null;
        }
    }

    if (sendTelegramBtn) {
        sendTelegramBtn.addEventListener('click', async () => {
            if (!currentSessionId) {
                alert(t('tg_need_dataset'));
                return;
            }

            // Reset state
            connectedChatId = null;
            connectedUserLabel = null;
            if (tgConnectedUserBanner) tgConnectedUserBanner.style.display = 'none';
            if (tgDetectBadge) {
                tgDetectBadge.textContent = t('tg_detecting');
                tgDetectBadge.style.background = 'rgba(255,255,255,0.08)';
                tgDetectBadge.style.color = 'var(--text-muted)';
            }
            if (telegramStatusMsg) {
                telegramStatusMsg.style.display = 'none';
                telegramStatusMsg.textContent = '';
            }

            // Generate unique connection token
            tgConnectCode = 'c' + Math.random().toString(36).substring(2, 8);

            // Fetch server Telegram Bot configuration & recent subscribers
            try {
                const configRes = await fetch('/api/telegram/config');
                const configData = await configRes.json();
                const botName = configData.bot_username || '@auto_bibot';
                const cleanBotName = botName.replace('@', '');

                if (tgDirectStartLink) {
                    tgDirectStartLink.href = `https://t.me/${cleanBotName}?start=${tgConnectCode}`;
                    tgDirectStartLink.textContent = t('tg_open_bot', { bot: botName });
                }

                // Render recent subscriber pills
                if (tgRecentPills && tgRecentChatsWrap) {
                    const recents = configData.recent_subscribers || [];
                    if (recents.length > 0) {
                        tgRecentPills.innerHTML = '';
                        recents.forEach(sub => {
                            const pill = document.createElement('button');
                            pill.type = 'button';
                            pill.className = 'btn btn-secondary';
                            pill.style.cssText = 'padding: 4px 10px; font-size: 11px; border-radius: 12px; margin: 0;';
                            pill.textContent = `+ ${sub.label}`;
                            pill.title = 'Click to add to recipients';
                            pill.onclick = () => {
                                const current = telegramTargetsInput ? telegramTargetsInput.value.trim() : '';
                                const targetVal = sub.username ? `@${sub.username}` : String(sub.chat_id);
                                if (telegramTargetsInput) {
                                    telegramTargetsInput.value = current ? `${current}, ${targetVal}` : targetVal;
                                    telegramTargetsInput.focus();
                                }
                            };
                            tgRecentPills.appendChild(pill);
                        });
                        tgRecentChatsWrap.style.display = 'block';
                    } else {
                        tgRecentChatsWrap.style.display = 'none';
                    }
                }
            } catch (err) {
                console.warn('Unable to query Telegram config:', err);
            }

            if (telegramModal) telegramModal.style.display = 'flex';

            // Load existing digest schedule if a report is active
            loadReportScheduleState();

            // Start polling for user /start
            if (tgPollTimer) clearInterval(tgPollTimer);
            tgPollTimer = setInterval(checkTelegramConnection, 1800);
        });
    }

    const tgScheduleBadge = document.getElementById('tgScheduleBadge');
    const tgScheduleCadence = document.getElementById('tgScheduleCadence');
    const tgScheduleHour = document.getElementById('tgScheduleHour');
    const tgAlertAnomaliesOnly = document.getElementById('tgAlertAnomaliesOnly');
    const tgSaveScheduleBtn = document.getElementById('tgSaveScheduleBtn');
    const tgTestRunScheduleBtn = document.getElementById('tgTestRunScheduleBtn');
    const tgDeleteScheduleBtn = document.getElementById('tgDeleteScheduleBtn');

    function gatherTelegramTargets() {
        const list = [];
        if (connectedChatId) list.push(String(connectedChatId));
        const raw = telegramTargetsInput ? telegramTargetsInput.value.trim() : '';
        if (raw) {
            raw.split(/[,;\n\r]+/).forEach(p => {
                const c = p.trim();
                if (c && !list.includes(c)) list.push(c);
            });
        }
        return list;
    }

    async function ensureSavedReportId() {
        if (currentReportId) return currentReportId;
        if (!currentSessionId || !lastRenderedData) return null;
        const res = await fetch('/api/reports', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: currentSessionId,
                title: lastRenderedData.filename || 'Scheduled AutoBI Report',
            }),
        });
        const json = await res.json();
        if (json.success && json.report) {
            currentReportId = json.report.report_id;
            lastRenderedData.report_meta = json.report;
            if (saveReportBtn) saveReportBtn.style.display = 'none';
            if (refreshReportBtn) refreshReportBtn.style.display = 'inline-flex';
            loadSavedReports();
            return currentReportId;
        }
        return null;
    }

    function applyScheduleUiState(sched) {
        if (!tgScheduleBadge) return;
        if (sched && sched.enabled) {
            tgScheduleBadge.textContent = t('tg_sched_active');
            tgScheduleBadge.classList.add('active');
            if (tgScheduleCadence && sched.cadence) tgScheduleCadence.value = sched.cadence;
            if (tgScheduleHour && sched.hour_utc !== undefined) tgScheduleHour.value = String(sched.hour_utc);
            if (tgAlertAnomaliesOnly) tgAlertAnomaliesOnly.checked = Boolean(sched.alert_only_on_anomalies);
            if (tgDeleteScheduleBtn) tgDeleteScheduleBtn.style.display = 'inline-flex';
            if (telegramTargetsInput && (!telegramTargetsInput.value.trim()) && Array.isArray(sched.targets)) {
                telegramTargetsInput.value = sched.targets.join(', ');
            }
        } else {
            tgScheduleBadge.textContent = t('tg_sched_off');
            tgScheduleBadge.classList.remove('active');
            if (tgDeleteScheduleBtn) tgDeleteScheduleBtn.style.display = 'none';
        }
    }

    async function loadReportScheduleState() {
        if (!currentReportId) {
            applyScheduleUiState(null);
            return;
        }
        try {
            const res = await fetch(`/api/reports/${encodeURIComponent(currentReportId)}/schedule`);
            if (!res.ok) return;
            const json = await res.json();
            applyScheduleUiState(json.schedule);
        } catch (_) {}
    }

    function showTgStatus(htmlMsg, isOk) {
        if (!telegramStatusMsg) return;
        telegramStatusMsg.style.display = 'block';
        telegramStatusMsg.style.background = isOk ? 'rgba(16, 185, 129, 0.15)' : 'rgba(245, 158, 11, 0.15)';
        telegramStatusMsg.style.borderColor = isOk ? 'rgba(16, 185, 129, 0.35)' : 'rgba(245, 158, 11, 0.35)';
        telegramStatusMsg.style.color = isOk ? '#6ee7b7' : '#fcd34d';
        telegramStatusMsg.innerHTML = htmlMsg;
    }

    if (tgSaveScheduleBtn) {
        tgSaveScheduleBtn.addEventListener('click', async () => {
            const targets = gatherTelegramTargets();
            if (!targets.length) {
                showTgStatus(escapeHtml(t('tg_need_target')), false);
                return;
            }
            const rid = await ensureSavedReportId();
            if (!rid) {
                showTgStatus(escapeHtml(t('tg_session_expired')), false);
                return;
            }
            const res = await fetch(`/api/reports/${encodeURIComponent(rid)}/schedule`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    cadence: tgScheduleCadence ? tgScheduleCadence.value : 'weekly_mon',
                    hour_utc: tgScheduleHour ? parseInt(tgScheduleHour.value, 10) : 4,
                    targets: targets,
                    alert_only_on_anomalies: Boolean(tgAlertAnomaliesOnly && tgAlertAnomaliesOnly.checked),
                    enabled: true,
                }),
            });
            const json = await res.json();
            if (json.success) {
                applyScheduleUiState(json.schedule);
                showTgStatus(escapeHtml(t('tg_sched_saved_ok')), true);
            } else {
                showTgStatus(escapeHtml(json.error || t('tg_send_fail')), false);
            }
        });
    }

    if (tgTestRunScheduleBtn) {
        tgTestRunScheduleBtn.addEventListener('click', async () => {
            const targets = gatherTelegramTargets();
            const rid = await ensureSavedReportId();
            if (!rid) {
                showTgStatus(escapeHtml(t('tg_session_expired')), false);
                return;
            }
            const res = await fetch(`/api/reports/${encodeURIComponent(rid)}/schedule/test-run`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ targets }),
            });
            const json = await res.json();
            if (json.success) {
                showTgStatus(escapeHtml(t('tg_sched_ran_ok')), true);
            } else {
                showTgStatus(escapeHtml(json.error || t('tg_send_fail')), false);
            }
        });
    }

    if (tgDeleteScheduleBtn) {
        tgDeleteScheduleBtn.addEventListener('click', async () => {
            if (!currentReportId) return;
            const res = await fetch(`/api/reports/${encodeURIComponent(currentReportId)}/schedule`, { method: 'DELETE' });
            const json = await res.json();
            if (json.success) {
                applyScheduleUiState(null);
                showTgStatus(escapeHtml(t('tg_sched_disabled_ok')), true);
            }
        });
    }

    if (tgCheckConnectBtn) {
        tgCheckConnectBtn.addEventListener('click', checkTelegramConnection);
    }

    if (closeTelegramModalBtn) closeTelegramModalBtn.addEventListener('click', closeTgModal);

    if (telegramModal) {
        telegramModal.addEventListener('click', (e) => {
            if (e.target === telegramModal) closeTgModal();
        });
    }

    if (telegramDispatchForm) {
        telegramDispatchForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            if (!currentSessionId) {
                alert(t('tg_session_expired'));
                return;
            }

            // Gather all recipient targets
            const rawTargets = telegramTargetsInput ? telegramTargetsInput.value.trim() : '';
            const targetsList = [];

            // Add connected user chat if active
            if (connectedChatId) {
                targetsList.push(String(connectedChatId));
            }

            // Parse additional comma or newline separated links/usernames
            if (rawTargets) {
                const parts = rawTargets.split(/[,;\n\r]+/);
                parts.forEach(p => {
                    const clean = p.trim();
                    if (clean && !targetsList.includes(clean)) {
                        targetsList.push(clean);
                    }
                });
            }

            if (targetsList.length === 0) {
                if (telegramStatusMsg) {
                    telegramStatusMsg.style.display = 'block';
                    telegramStatusMsg.style.background = 'rgba(245, 158, 11, 0.15)';
                    telegramStatusMsg.style.borderColor = 'rgba(245, 158, 11, 0.3)';
                    telegramStatusMsg.style.color = '#fcd34d';
                    telegramStatusMsg.textContent = t('tg_need_target');
                }
                return;
            }

            if (telegramSubmitBtn) {
                telegramSubmitBtn.disabled = true;
                telegramSubmitBtn.textContent = t('tg_sending');
            }
            if (telegramStatusMsg) {
                telegramStatusMsg.style.display = 'none';
                telegramStatusMsg.textContent = '';
            }

            try {
                const res = await fetch('/api/telegram/dispatch', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        session_id: currentSessionId,
                        targets: targetsList
                    })
                });

                const data = await res.json();
                if (res.ok && data.success) {
                    if (telegramStatusMsg) {
                        telegramStatusMsg.style.display = 'block';
                        telegramStatusMsg.style.background = 'rgba(16, 185, 129, 0.15)';
                        telegramStatusMsg.style.borderColor = 'rgba(16, 185, 129, 0.3)';
                        telegramStatusMsg.style.color = '#6ee7b7';
                        const count = data.dispatched_count || (data.dispatched ? data.dispatched.length : 1);
                        telegramStatusMsg.innerHTML = t('tg_sent_ok', { count });
                    }
                    setTimeout(() => {
                        closeTgModal();
                        if (telegramSubmitBtn) {
                            telegramSubmitBtn.disabled = false;
                            telegramSubmitBtn.textContent = t('tg_send');
                        }
                    }, 2000);
                } else {
                    if (telegramStatusMsg) {
                        telegramStatusMsg.style.display = 'block';
                        telegramStatusMsg.style.background = 'rgba(239, 68, 68, 0.15)';
                        telegramStatusMsg.style.borderColor = 'rgba(239, 68, 68, 0.3)';
                        telegramStatusMsg.style.color = '#fca5a5';
                        telegramStatusMsg.textContent = data.error || t('tg_send_fail');
                    }
                    if (telegramSubmitBtn) {
                        telegramSubmitBtn.disabled = false;
                        telegramSubmitBtn.textContent = t('tg_send');
                    }
                }
            } catch (err) {
                if (telegramStatusMsg) {
                    telegramStatusMsg.style.display = 'block';
                    telegramStatusMsg.style.background = 'rgba(239, 68, 68, 0.15)';
                    telegramStatusMsg.style.borderColor = 'rgba(239, 68, 68, 0.3)';
                    telegramStatusMsg.style.color = '#fca5a5';
                    telegramStatusMsg.textContent = t('err_network') + err.message;
                }
                if (telegramSubmitBtn) {
                    telegramSubmitBtn.disabled = false;
                    telegramSubmitBtn.textContent = t('tg_send');
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
    let lastRenderedData = null;

    if (i18n) {
        i18n.onChange(() => {
            if (lastRenderedData) renderResults(lastRenderedData);
        });
    }

    // Ingestion Mode Toggles (File vs Google Sheets vs Read-Only SQL)
    function setUploadMode(mode) {
        if (tabModeFile) tabModeFile.classList.toggle('active', mode === 'file');
        if (tabModeGSheets) tabModeGSheets.classList.toggle('active', mode === 'gsheets');
        if (tabModeSql) tabModeSql.classList.toggle('active', mode === 'sql');
        if (dropzone) dropzone.style.display = mode === 'file' ? 'flex' : 'none';
        if (gsheetsSection) gsheetsSection.style.display = mode === 'gsheets' ? 'block' : 'none';
        if (sqlSection) sqlSection.style.display = mode === 'sql' ? 'block' : 'none';
    }

    if (tabModeFile) tabModeFile.addEventListener('click', () => setUploadMode('file'));
    if (tabModeGSheets) tabModeGSheets.addEventListener('click', () => setUploadMode('gsheets'));
    if (tabModeSql) tabModeSql.addEventListener('click', () => setUploadMode('sql'));

    async function ingestSqlDatabase(uri, query) {
        showLoading(t('loading_sql'));
        try {
            const res = await fetch('/api/ingest-sql', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ uri, query })
            });
            const data = await res.json();
            if (res.status === 401 && data.auth_required) {
                isAuthenticated = false;
                uploadCard.style.display = 'block';
                openAuthModal(() => ingestSqlDatabase(uri, query));
                return;
            }
            if (data.success) {
                renderResults(data);
            } else {
                alert(t('err_analysis') + (data.error || t('err_analysis_default')));
                uploadCard.style.display = 'block';
            }
        } catch (err) {
            alert(t('err_server_conn') + err.message);
            uploadCard.style.display = 'block';
        } finally {
            hideLoading();
        }
    }

    if (sqlForm) {
        sqlForm.addEventListener('submit', (e) => {
            e.preventDefault();
            const uri = sqlUriInput ? sqlUriInput.value.trim() : '';
            const query = sqlQueryInput ? sqlQueryInput.value.trim() : '';
            if (!uri || !query) {
                alert(t('err_sql_required'));
                return;
            }
            requireWorkspaceAuth(() => ingestSqlDatabase(uri, query));
        });
    }

    async function ingestGoogleSheetUrl(url) {
        showLoading(t('loading_gsheet'));
        try {
            const res = await fetch('/api/ingest-url', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url: url })
            });
            const data = await res.json();
            if (res.status === 401 && data.auth_required) {
                isAuthenticated = false;
                uploadCard.style.display = 'block';
                openAuthModal(() => ingestGoogleSheetUrl(url));
                return;
            }
            if (data.success) {
                renderResults(data);
            } else {
                alert(t('err_gsheets') + (data.error || t('err_gsheets_default')));
                uploadCard.style.display = 'block';
            }
        } catch (err) {
            alert(t('err_server_conn') + err.message);
            uploadCard.style.display = 'block';
        } finally {
            hideLoading();
        }
    }

    if (gsheetsForm) {
        gsheetsForm.addEventListener('submit', (e) => {
            e.preventDefault();
            const url = gsheetsUrlInput ? gsheetsUrlInput.value.trim() : '';
            if (!url) {
                alert(t('err_gsheets_url_required'));
                if (gsheetsUrlInput) gsheetsUrlInput.focus();
                return;
            }
            requireWorkspaceAuth(() => ingestGoogleSheetUrl(url));
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
                const droppedFile = files[0];
                requireWorkspaceAuth(() => {
                    currentLastFile = droppedFile;
                    handleFileUpload(droppedFile);
                });
            }
        });

        dropzone.addEventListener('click', (e) => {
            if (e.target !== browseBtn && e.target !== sampleBtn && !sampleBtn.contains(e.target) && !e.target.classList.contains('demo-pill-btn')) {
                requireWorkspaceAuth(() => fileInput.click());
            }
        });
    }

    if (browseBtn) {
        browseBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            requireWorkspaceAuth(() => fileInput.click());
        });
    }

    if (fileInput) {
        fileInput.addEventListener('change', () => {
            if (fileInput.files.length > 0) {
                const chosenFile = fileInput.files[0];
                requireWorkspaceAuth(() => {
                    currentLastFile = chosenFile;
                    handleFileUpload(chosenFile);
                });
            }
        });
    }

    if (sampleBtn) {
        sampleBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            requireWorkspaceAuth(() => handleSampleRun('sales'));
        });
    }

    // Demo Pills
    document.querySelectorAll('.demo-pill-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            const domain = btn.getAttribute('data-domain');
            requireWorkspaceAuth(() => handleSampleRun(domain));
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
            alert(t('err_unsupported_file', { ext }));
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
            if (res.status === 401 && data.auth_required) {
                isAuthenticated = false;
                uploadCard.style.display = 'block';
                openAuthModal(() => handleFileUpload(file, domainOverride, sheetOverride));
                return;
            }
            if (data.success) {
                renderResults(data);
            } else {
                alert(t('err_analysis') + (data.error || t('err_analysis_default')));
                uploadCard.style.display = 'block';
            }
        } catch (err) {
            alert(t('err_server') + err.message);
            uploadCard.style.display = 'block';
        } finally {
            hideLoading();
        }
    }

    async function handleSampleRun(domain = 'sales') {
        currentLastDomain = domain;
        currentLastFile = null;
        showLoading(t('loading_preset', { domain: domain.toUpperCase() }));

        try {
            const res = await fetch('/api/sample', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ domain: domain })
            });
            const data = await res.json();
            if (res.status === 401 && data.auth_required) {
                isAuthenticated = false;
                uploadCard.style.display = 'block';
                openAuthModal(() => handleSampleRun(domain));
                return;
            }
            if (data.success) {
                renderResults(data);
            } else {
                alert(t('err_sample') + (data.error || t('err_sample_default')));
                uploadCard.style.display = 'block';
            }
        } catch (err) {
            alert(t('err_server') + err.message);
            uploadCard.style.display = 'block';
        } finally {
            hideLoading();
        }
    }

    // --- Render Results ---
    function renderResults(data) {
        lastRenderedData = data;
        currentSessionId = data.session_id;
        currentReportId = (data.report_meta && data.report_meta.report_id) ? data.report_meta.report_id : null;
        activeFileBadge.textContent = data.is_live_url ? t('source_live_gsheet', { filename: data.filename }) : data.filename;

        if (saveReportBtn) {
            saveReportBtn.style.display = currentReportId ? 'none' : 'inline-flex';
            saveReportBtn.disabled = false;
            saveReportBtn.textContent = t('btn_save_report');
        }
        if (refreshReportBtn) {
            refreshReportBtn.style.display = currentReportId ? 'inline-flex' : 'none';
        }

        // 1. Domain Badge & Switcher
        const dom = data.domain;
        if (domainBadge && dom) {
            domainBadge.textContent = t('domain_match', { icon: dom.icon, label: dom.label, conf: dom.confidence });
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
                        <span>${t('risk_banner', { crit: summary.critical_count || 0, warn: summary.warning_count || 0 })}</span>
                    </div>
                    <button id="viewAuditRiskLink" style="background: none; border: none; color: #f43f5e; text-decoration: underline; font-weight: 600; cursor: pointer; font-size: 13px;">${escapeHtml(t('risk_review_btn'))}</button>
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
                if (!confirm(t('confirm_purge'))) {
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
                    lastRenderedData = null;

                    // Show purge confirmation
                    if (purgeBanner) {
                        purgeBanner.style.display = 'flex';
                        const textEl = document.getElementById('purgeBannerText');
                        if (textEl && purgeJson.message) {
                            textEl.textContent = purgeJson.message;
                        }
                    }
                } catch (e) {
                    alert(t('err_purge') + e.message);
                }
            };
        }

        // 2. Dynamic KPI Cards
        renderKpis(data.kpis);

        // 3. Dynamic Charts
        renderCharts(data.charts);

        // 3b. Interactive Top-Bar Slicers & Chart Builder Controls
        setupInteractiveControls(data);

        // 4. Audit Trail
        renderAuditTrail(data.audit_log);

        // 5. DAX Measures & M Script
        renderCodeBlocks(data.dax_measures, data.power_query_m, data.domain);

        // 6. Clean Table
        const displayLabels = data.display_labels || (data.audit_log && data.audit_log.display_labels) || {};
        renderTable(data.table_columns, data.table_records, displayLabels);

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

    // --- Phase 2: Interactive Slicers & Chart Builder ---
    let interactiveQueryTimer = null;
    async function runInteractiveQuery() {
        if (!currentSessionId || !lastRenderedData) return;
        try {
            const res = await fetch(`/api/session/${currentSessionId}/query`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    filters: activeFilters,
                    date_from: activeDateRange.from,
                    date_to: activeDateRange.to,
                    chart_overrides: activeChartOverrides,
                    save: true,
                }),
            });
            const json = await res.json();
            if (!res.ok || !json.success) return;

            lastRenderedData.kpis = json.kpis;
            lastRenderedData.charts = json.charts;
            lastRenderedData.table_records = json.table_records;

            renderKpis(json.kpis);
            renderCharts(json.charts);
            const displayLabels = lastRenderedData.display_labels || (lastRenderedData.audit_log && lastRenderedData.audit_log.display_labels) || {};
            renderTable(lastRenderedData.table_columns, json.table_records, displayLabels);

            const countPill = document.getElementById('slicerCountBadge');
            if (countPill) {
                countPill.textContent = t('slicer_rows', {
                    filtered: json.row_count,
                    total: json.total_row_count
                });
            }
        } catch (_) {}
    }

    function setupInteractiveControls(data) {
        activeFilters = {};
        activeDateRange = { from: '', to: '' };
        activeChartOverrides = (data && data.chart_overrides && typeof data.chart_overrides === 'object')
            ? JSON.parse(JSON.stringify(data.chart_overrides))
            : {};

        const schema = (data && data.interactive_schema) || {};
        const slicers = schema.slicers || [];
        const dateCol = schema.date_col || null;
        const dims = schema.dimension_cols || [];
        const nums = schema.numeric_cols || [];

        const slicerBar = document.getElementById('slicerBar');
        const slicerInputs = document.getElementById('slicerInputs');
        const countPill = document.getElementById('slicerCountBadge');
        const resetSlicersBtn = document.getElementById('resetSlicersBtn');

        if (slicerBar && slicerInputs) {
            slicerInputs.innerHTML = '';
            const hasSlicers = slicers.length > 0 || Boolean(dateCol);
            slicerBar.style.display = hasSlicers ? 'flex' : 'none';

            slicers.forEach(s => {
                const wrap = document.createElement('label');
                wrap.className = 'slicer-field';
                const lbl = document.createElement('span');
                lbl.textContent = s.label;
                const sel = document.createElement('select');
                sel.className = 'slicer-select';
                sel.setAttribute('data-filter-col', s.key);
                const optAll = document.createElement('option');
                optAll.value = '__all__';
                optAll.textContent = `${s.label}: ${t('slicer_all')}`;
                sel.appendChild(optAll);
                (s.values || []).forEach(v => {
                    const o = document.createElement('option');
                    o.value = v;
                    o.textContent = v;
                    sel.appendChild(o);
                });
                sel.onchange = () => {
                    if (sel.value === '__all__') {
                        delete activeFilters[s.key];
                    } else {
                        activeFilters[s.key] = sel.value;
                    }
                    runInteractiveQuery();
                };
                wrap.appendChild(lbl);
                wrap.appendChild(sel);
                slicerInputs.appendChild(wrap);
            });

            if (dateCol) {
                const dWrap = document.createElement('div');
                dWrap.className = 'slicer-date-group';
                const dLbl = document.createElement('span');
                dLbl.textContent = dateCol.label;
                const inpFrom = document.createElement('input');
                inpFrom.type = 'date';
                inpFrom.className = 'slicer-select slicer-date';
                inpFrom.value = dateCol.min || '';
                inpFrom.min = dateCol.min || '';
                inpFrom.max = dateCol.max || '';
                const inpTo = document.createElement('input');
                inpTo.type = 'date';
                inpTo.className = 'slicer-select slicer-date';
                inpTo.value = dateCol.max || '';
                inpTo.min = dateCol.min || '';
                inpTo.max = dateCol.max || '';
                const onDateChange = () => {
                    activeDateRange.from = inpFrom.value || '';
                    activeDateRange.to = inpTo.value || '';
                    clearTimeout(interactiveQueryTimer);
                    interactiveQueryTimer = setTimeout(runInteractiveQuery, 150);
                };
                inpFrom.onchange = onDateChange;
                inpTo.onchange = onDateChange;
                dWrap.appendChild(dLbl);
                dWrap.appendChild(inpFrom);
                dWrap.appendChild(inpTo);
                slicerInputs.appendChild(dWrap);
            }

            if (countPill) {
                const totalRows = (data.audit_log && data.audit_log.cleaned_row_count) || (data.table_records ? data.table_records.length : 0);
                countPill.textContent = t('slicer_rows', { filtered: totalRows, total: totalRows });
            }

            if (resetSlicersBtn) {
                resetSlicersBtn.onclick = () => {
                    activeFilters = {};
                    activeDateRange = { from: '', to: '' };
                    slicerInputs.querySelectorAll('select[data-filter-col]').forEach(el => { el.value = '__all__'; });
                    if (dateCol) {
                        const dateInputs = slicerInputs.querySelectorAll('input[type="date"]');
                        if (dateInputs[0]) dateInputs[0].value = dateCol.min || '';
                        if (dateInputs[1]) dateInputs[1].value = dateCol.max || '';
                    }
                    runInteractiveQuery();
                };
            }
        }

        // Toggle chart builder toolbars
        document.querySelectorAll('.chart-customize-toggle[data-target]').forEach(btn => {
            btn.onclick = () => {
                const targetEl = document.getElementById(btn.getAttribute('data-target'));
                if (!targetEl) return;
                const open = targetEl.style.display !== 'flex';
                targetEl.style.display = open ? 'flex' : 'none';
                btn.classList.toggle('active', open);
            };
        });

        // Populate chart builder selects for chart1 & chart2
        ['chart1', 'chart2'].forEach((slot, idx) => {
            const bar = document.getElementById(`${slot}Controls`);
            if (!bar) return;
            const typeSel = bar.querySelector('.cb-type');
            const dimSel = bar.querySelector('.cb-dim');
            const metricSel = bar.querySelector('.cb-metric');
            const aggSel = bar.querySelector('.cb-agg');
            const currentCfg = (data.charts && data.charts[slot]) || {};
            const savedSpec = activeChartOverrides[slot] || {};

            if (dimSel) {
                dimSel.innerHTML = '';
                dims.forEach(d => {
                    const o = document.createElement('option');
                    o.value = d.key;
                    o.textContent = d.label;
                    dimSel.appendChild(o);
                });
                if (savedSpec.dim && dims.some(d => d.key === savedSpec.dim)) {
                    dimSel.value = savedSpec.dim;
                } else if (dims.length > idx) {
                    dimSel.value = dims[idx].key;
                }
            }
            if (metricSel) {
                metricSel.innerHTML = '';
                nums.forEach(m => {
                    const o = document.createElement('option');
                    o.value = m.key;
                    o.textContent = m.label;
                    metricSel.appendChild(o);
                });
                const cntOpt = document.createElement('option');
                cntOpt.value = '__count__';
                cntOpt.textContent = t('cb_record_count');
                metricSel.appendChild(cntOpt);

                if (savedSpec.metric) {
                    metricSel.value = savedSpec.metric;
                } else if (nums.length > 0) {
                    metricSel.value = nums[0].key;
                } else {
                    metricSel.value = '__count__';
                }
            }
            if (typeSel) {
                typeSel.value = savedSpec.type || currentCfg.type || (slot === 'chart1' ? 'bar' : 'doughnut');
            }
            if (aggSel) {
                aggSel.value = savedSpec.agg || 'sum';
            }

            const onBuilderChange = () => {
                if (!dimSel || !dimSel.value) return;
                activeChartOverrides[slot] = {
                    type: typeSel ? typeSel.value : 'bar',
                    dim: dimSel.value,
                    metric: metricSel ? metricSel.value : '__count__',
                    agg: aggSel ? aggSel.value : 'sum',
                };
                runInteractiveQuery();
            };

            [typeSel, dimSel, metricSel, aggSel].forEach(sel => {
                if (sel) sel.onchange = onBuilderChange;
            });
        });
    }

    // --- Dynamic KPI Rendering ---
    function renderKpis(kpis) {
        const kpiGrid = document.getElementById('kpiGrid');
        kpiGrid.innerHTML = '';

        kpis.forEach(k => {
            const card = document.createElement('div');
            card.className = `kpi-card ${k.theme || ''}`;
            const deltaHtml = k.delta_text
                ? `<div class="kpi-delta delta-${escapeHtml(k.delta_dir || 'flat')}">${k.delta_dir === 'up' ? '▲' : (k.delta_dir === 'down' ? '▼' : '•')} ${escapeHtml(k.delta_text)}</div>`
                : '';
            card.innerHTML = `
                <div class="kpi-label">${escapeHtml(k.label)}</div>
                <div class="kpi-value">${escapeHtml(k.value)}</div>
                ${deltaHtml}
                <div class="kpi-subtext">${escapeHtml(k.sub || '')}</div>
            `;
            kpiGrid.appendChild(card);
        });
    }

    // --- Phase 3: Persistent My Reports Gallery & MoM Refresh ---
    async function loadSavedReports() {
        if (!myReportsSection || !myReportsGrid || !isAuthenticated) return;
        try {
            const res = await fetch('/api/reports');
            if (!res.ok) return;
            const json = await res.json();
            const reports = json.reports || [];
            myReportsGrid.innerHTML = '';
            if (!reports.length) {
                myReportsSection.style.display = 'none';
                return;
            }
            myReportsSection.style.display = 'block';
            reports.forEach(r => {
                const card = document.createElement('div');
                card.className = 'saved-report-card';
                const topKpi = (r.latest_kpis && r.latest_kpis[0])
                    ? `${escapeHtml(r.latest_kpis[0].label)}: <strong>${escapeHtml(r.latest_kpis[0].value)}</strong>`
                    : '';
                const domIcon = (r.domain && r.domain.icon) || '📊';
                const domLbl = (r.domain && r.domain.label) || '';
                card.innerHTML = `
                    <div class="sr-head">
                        <span class="sr-title">${domIcon} ${escapeHtml(r.title)}</span>
                        <span class="sr-snaps">${escapeHtml(t('snaps_count', { n: r.snapshot_count || 1 }))}</span>
                    </div>
                    <div class="sr-meta">${escapeHtml(domLbl)}${r.latest_period ? ' · ' + escapeHtml(r.latest_period) : ''}</div>
                    <div class="sr-kpi">${topKpi}</div>
                    <div class="sr-actions">
                        <button type="button" class="btn btn-primary sr-open" style="padding: 5px 10px; font-size: 11.5px;">${escapeHtml(t('btn_open_report'))}</button>
                        <button type="button" class="btn btn-secondary sr-refresh" style="padding: 5px 10px; font-size: 11.5px;">${escapeHtml(t('btn_refresh_report'))}</button>
                        <button type="button" class="btn btn-danger-outline sr-del" style="padding: 5px 9px; font-size: 11.5px;">🗑</button>
                    </div>
                `;
                card.querySelector('.sr-open').onclick = () => openSavedReport(r.report_id);
                card.querySelector('.sr-refresh').onclick = () => triggerReportRefresh(r.report_id, r.is_live_url);
                card.querySelector('.sr-del').onclick = () => deleteSavedReport(r.report_id);
                myReportsGrid.appendChild(card);
            });
        } catch (_) {}
    }

    async function openSavedReport(reportId) {
        showLoading(t('loading_title'));
        try {
            const res = await fetch(`/api/reports/${encodeURIComponent(reportId)}`);
            const json = await res.json();
            if (json.success) {
                renderResults(json);
            } else {
                alert(json.error || t('err_analysis_default'));
            }
        } catch (e) {
            alert(t('err_server') + e.message);
        } finally {
            hideLoading();
        }
    }

    function triggerReportRefresh(reportId, isLive) {
        if (!reportId) return;
        if (isLive) {
            refreshReportFromServer(reportId, null);
            return;
        }
        pendingRefreshReportId = reportId;
        if (refreshFileInput) {
            refreshFileInput.value = '';
            refreshFileInput.click();
        }
    }

    async function refreshReportFromServer(reportId, fileObj) {
        showLoading(t('loading_title'));
        try {
            let res;
            if (fileObj) {
                const fd = new FormData();
                fd.append('file', fileObj);
                res = await fetch(`/api/reports/${encodeURIComponent(reportId)}/refresh`, { method: 'POST', body: fd });
            } else {
                res = await fetch(`/api/reports/${encodeURIComponent(reportId)}/refresh`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ use_source_url: true })
                });
            }
            const json = await res.json();
            if (json.success) {
                renderResults(json);
                loadSavedReports();
            } else {
                alert(json.error || t('err_analysis_default'));
            }
        } catch (e) {
            alert(t('err_server') + e.message);
        } finally {
            hideLoading();
        }
    }

    async function deleteSavedReport(reportId) {
        if (!confirm(t('confirm_delete_report'))) return;
        try {
            const res = await fetch(`/api/reports/${encodeURIComponent(reportId)}`, { method: 'DELETE' });
            const json = await res.json();
            if (json.success) {
                if (currentReportId === reportId) currentReportId = null;
                loadSavedReports();
            }
        } catch (_) {}
    }

    if (refreshFileInput) {
        refreshFileInput.addEventListener('change', (e) => {
            if (e.target.files.length > 0 && pendingRefreshReportId) {
                const f = e.target.files[0];
                const rid = pendingRefreshReportId;
                pendingRefreshReportId = null;
                refreshReportFromServer(rid, f);
            }
        });
    }

    if (saveReportBtn) {
        saveReportBtn.addEventListener('click', async () => {
            if (!currentSessionId || !lastRenderedData) return;
            const suggested = lastRenderedData.filename || 'AutoBI Report';
            const title = prompt(t('prompt_report_title'), suggested);
            if (title === null) return;
            saveReportBtn.disabled = true;
            try {
                const res = await fetch('/api/reports', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ session_id: currentSessionId, title: title.trim() || suggested })
                });
                const json = await res.json();
                if (json.success && json.report) {
                    currentReportId = json.report.report_id;
                    lastRenderedData.report_meta = json.report;
                    saveReportBtn.textContent = t('btn_report_saved');
                    if (refreshReportBtn) refreshReportBtn.style.display = 'inline-flex';
                    loadSavedReports();
                } else {
                    alert(json.error || 'Could not save report.');
                    saveReportBtn.disabled = false;
                }
            } catch (e) {
                alert(t('err_server') + e.message);
                saveReportBtn.disabled = false;
            }
        });
    }

    if (refreshReportBtn) {
        refreshReportBtn.addEventListener('click', () => {
            if (currentReportId) {
                triggerReportRefresh(currentReportId, Boolean(lastRenderedData && lastRenderedData.is_live_url));
            }
        });
    }

    // --- Dynamic Chart Rendering ---
    function renderCharts(charts) {
        if (chart1Instance) chart1Instance.destroy();
        if (chart2Instance) chart2Instance.destroy();

        const colors = [
            '#6366f1', '#06b6d4', '#10b981', '#f59e0b', '#ec4899', '#8b5cf6'
        ];
        const isLightTheme = (window.autobiTheme && window.autobiTheme.getTheme() === 'light')
            || document.documentElement.getAttribute('data-theme') === 'light';
        const chartLegendColor = isLightTheme ? '#334155' : '#cbd5e1';
        const chartTickColor = isLightTheme ? '#64748b' : '#94a3b8';
        const chartGridColor = isLightTheme ? 'rgba(15, 23, 42, 0.08)' : 'rgba(255, 255, 255, 0.05)';
        const chartSurfaceBorder = isLightTheme ? '#ffffff' : '#090d16';

        function createChartInstance(cfg, canvasEl, titleEl, defaultType, multiBar) {
            if (!cfg || !canvasEl) return null;
            const cType = cfg.type || defaultType;
            const isDoughnut = cType === 'doughnut';
            const isLine = cType === 'line';
            if (titleEl) titleEl.textContent = cfg.title || '';
            const ctx = canvasEl.getContext('2d');
            const labels = Object.keys(cfg.data || {});
            const values = Object.values(cfg.data || {});

            let bgColor = 'rgba(99, 102, 241, 0.85)';
            let bdColor = '#6366f1';
            if (isDoughnut) {
                bgColor = colors;
                bdColor = chartSurfaceBorder;
            } else if (isLine) {
                const grad = ctx.createLinearGradient(0, 0, 0, canvasEl.height || 240);
                grad.addColorStop(0, isLightTheme ? 'rgba(99, 102, 241, 0.28)' : 'rgba(99, 102, 241, 0.34)');
                grad.addColorStop(1, 'rgba(99, 102, 241, 0.0)');
                bgColor = grad;
                bdColor = '#6366f1';
            } else if (multiBar) {
                bgColor = colors;
                bdColor = colors;
            }

            return new Chart(ctx, {
                type: cType,
                data: {
                    labels: labels,
                    datasets: [{
                        label: cfg.series_label || cfg.title || 'Value',
                        data: values,
                        backgroundColor: bgColor,
                        borderColor: bdColor,
                        borderWidth: isLine ? 2.5 : (isDoughnut ? 2 : 1),
                        tension: isLine ? 0.35 : 0,
                        fill: isLine,
                        pointRadius: isLine ? (labels.length > 24 ? 2 : 3.5) : 0,
                        pointHoverRadius: isLine ? 5.5 : 0,
                        borderRadius: (isDoughnut || isLine) ? 0 : 6
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            display: isDoughnut,
                            position: 'bottom',
                            labels: { color: chartLegendColor, padding: 12 }
                        }
                    },
                    cutout: isDoughnut ? '65%' : 0,
                    scales: isDoughnut ? {} : {
                        y: { beginAtZero: !isLine, grid: { color: chartGridColor }, ticks: { color: chartTickColor } },
                        x: { grid: { display: false }, ticks: { color: chartLegendColor, maxRotation: 35, autoSkip: true } }
                    }
                }
            });
        }

        // Chart 1 & Chart 2
        chart1Instance = createChartInstance(
            charts.chart1,
            document.getElementById('chart1Canvas'),
            document.getElementById('chart1Title'),
            'bar',
            false
        );
        chart2Instance = createChartInstance(
            charts.chart2,
            document.getElementById('chart2Canvas'),
            document.getElementById('chart2Title'),
            'doughnut',
            true
        );
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
                            <h3>${escapeHtml(t('audit_flags_title', { count: anomalies.length }))}</h3>
                            <div style="display: flex; gap: 6px;">
                                ${anomalySummary.critical_count > 0 ? `<span class="audit-item-badge" style="background: rgba(244,63,94,0.16); color: var(--accent-rose); border-color: rgba(244,63,94,0.35);">${escapeHtml(t('audit_critical', { n: anomalySummary.critical_count }))}</span>` : ''}
                                ${anomalySummary.warning_count > 0 ? `<span class="audit-item-badge" style="background: rgba(245,158,11,0.16); color: var(--accent-amber); border-color: rgba(245,158,11,0.35);">${escapeHtml(t('audit_warning', { n: anomalySummary.warning_count }))}</span>` : ''}
                                ${anomalySummary.info_count > 0 ? `<span class="audit-item-badge" style="background: rgba(6,182,212,0.16); color: var(--accent-cyan); border-color: rgba(6,182,212,0.35);">${escapeHtml(t('audit_notice', { n: anomalySummary.info_count }))}</span>` : ''}
                            </div>
                        </div>
                        <p class="text-xs" style="color: var(--text-muted);">${escapeHtml(t('audit_flags_desc'))}</p>
                    </div>
                </div>
            `;
            anomalies.forEach(item => {
                const el = document.createElement('div');
                el.className = 'audit-item';
                el.style.flexDirection = 'column';
                el.style.alignItems = 'flex-start';
                el.style.gap = '6px';

                const badgeBg = item.severity === 'critical' ? 'rgba(244,63,94,0.16)' : (item.severity === 'warning' ? 'rgba(245,158,11,0.16)' : 'rgba(6,182,212,0.16)');
                const badgeColor = item.severity === 'critical' ? 'var(--accent-rose)' : (item.severity === 'warning' ? 'var(--accent-amber)' : 'var(--accent-cyan)');

                let sampleStr = '';
                if (item.sample_rows && item.sample_rows.length > 0) {
                    sampleStr = `<div style="font-size: 11px; font-family: var(--font-mono); color: var(--text-muted); background: var(--bg-code); border: 1px solid var(--border-subtle); padding: 4px 8px; border-radius: 4px; width: 100%; overflow-x: auto;">${escapeHtml(t('audit_sample_prefix'))} ${escapeHtml(JSON.stringify(item.sample_rows[0]))}</div>`;
                }

                el.innerHTML = `
                    <div style="display: flex; justify-content: space-between; width: 100%; align-items: center;">
                        <span style="font-weight: 600; color: var(--text-primary);">[${escapeHtml(item.severity.toUpperCase())}] ${escapeHtml(item.title)}</span>
                        <span class="audit-item-badge" style="background: ${badgeBg}; color: ${badgeColor};">${escapeHtml(t('audit_affected', { n: item.affected_count }))}</span>
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
                        <h3>${escapeHtml(t('audit_clean_title'))}</h3>
                        <p class="text-xs text-slate-400">${escapeHtml(t('audit_clean_desc'))}</p>
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
                        <h3>${escapeHtml(t('audit_unpivot_title'))}</h3>
                        <p class="text-xs text-slate-400">${escapeHtml(t('audit_unpivot_desc'))}</p>
                    </div>
                </div>
                <div class="audit-item">
                    <span><strong>${escapeHtml(t('audit_unpivot_cols'))}</strong> ${escapeHtml(t('audit_cols_count', { n: unpivot.temporal_columns.length }))} (${escapeHtml(unpivot.temporal_columns.slice(0, 4).join(', '))}${unpivot.temporal_columns.length > 4 ? '...' : ''})</span>
                    <span class="audit-item-badge">pd.melt() + Table.Unpivot</span>
                </div>
                <div class="audit-item">
                    <span><strong>${escapeHtml(t('audit_pruned_cols'))}</strong> ${escapeHtml(unpivot.pruned_summary_columns.join(', ') || t('none_label'))}</span>
                    <span class="audit-item-badge">${escapeHtml(t('audit_excluded'))}</span>
                </div>
                <div class="audit-item">
                    <span><strong>${escapeHtml(t('audit_row_transform'))}</strong> ${escapeHtml(t('audit_row_transform_val', { raw: unpivot.original_rows, unpivoted: unpivot.unpivoted_rows }))}</span>
                    <span class="audit-item-badge">${escapeHtml(t('audit_std_ts'))}</span>
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
                        <h3>${escapeHtml(t('audit_fx_title'))}</h3>
                        <p class="text-xs text-slate-400">${escapeHtml(t('audit_fx_desc'))}</p>
                    </div>
                </div>
                <div class="audit-item">
                    <span><strong>${escapeHtml(t('audit_fx_currencies'))}</strong> ${escapeHtml((fx.detected_currencies || []).join(', '))}</span>
                    <span class="audit-item-badge">${escapeHtml(t('audit_fx_col'))} <code>${escapeHtml(fx.currency_column || 'currency')}</code></span>
                </div>
                <div class="audit-item">
                    <span><strong>${escapeHtml(t('audit_fx_rates'))}</strong> ${escapeHtml(ratesText || '1 USD = 12,000 UZS')}</span>
                    <span class="audit-item-badge">${escapeHtml(t('audit_fx_date', { date: fx.cbu_date || 'Today' }))}</span>
                </div>
                <div class="audit-item">
                    <span><strong>${escapeHtml(t('audit_fx_added'))}</strong> <code>${escapeHtml((fx.converted_columns || []).join(', '))}</code></span>
                    <span class="audit-item-badge">${escapeHtml(t('audit_fx_std'))}</span>
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
                        <h3>${escapeHtml(t('audit_pareto_title'))}</h3>
                        <p class="text-xs text-slate-400">${t('audit_pareto_desc', { col: escapeHtml(pareto.dimension_col || 'product') })}</p>
                    </div>
                </div>
                <div class="audit-item">
                    <span><strong>${escapeHtml(t('audit_pareto_a'))}</strong> ${escapeHtml(t('audit_drivers_key', { n: pareto.class_a_count }))}</span>
                    <span class="audit-item-badge" style="background: rgba(16,185,129,0.2); color: #6ee7b7;">${escapeHtml(t('audit_volume', { pct: pareto.class_a_revenue_share }))}</span>
                </div>
                <div class="audit-item">
                    <span><strong>${escapeHtml(t('audit_pareto_b'))}</strong> ${escapeHtml(t('audit_drivers_sec', { n: pareto.class_b_count }))}</span>
                    <span class="audit-item-badge" style="background: rgba(6,182,212,0.2); color: #67e8f9;">${escapeHtml(t('audit_volume', { pct: pareto.class_b_revenue_share }))}</span>
                </div>
                <div class="audit-item">
                    <span><strong>${escapeHtml(t('audit_pareto_c'))}</strong> ${escapeHtml(t('audit_drivers_min', { n: pareto.class_c_count }))}</span>
                    <span class="audit-item-badge" style="background: rgba(148,163,184,0.2); color: #cbd5e1;">${escapeHtml(t('audit_volume', { pct: pareto.class_c_revenue_share }))}</span>
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
                        <h3>${escapeHtml(t('audit_dropped_title', { n: audit.dropped_rows.length }))}</h3>
                        <p class="text-xs text-slate-400">${escapeHtml(t('audit_dropped_desc'))}</p>
                    </div>
                </div>
            `;
            audit.dropped_rows.forEach(item => {
                const el = document.createElement('div');
                el.className = 'audit-item';
                el.innerHTML = `
                    <span><strong>${escapeHtml(t('audit_row_num', { idx: item.row_index }))}</strong> ${escapeHtml(item.reason)}</span>
                    <span class="audit-item-badge">${escapeHtml(t('audit_preview_prefix'))} ${escapeHtml(JSON.stringify(item.content_preview))}</span>
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
                        <h3>${escapeHtml(t('audit_inferred_title', { n: audit.inferred_calculations.length }))}</h3>
                        <p class="text-xs text-slate-400">${escapeHtml(t('audit_inferred_desc'))}</p>
                    </div>
                </div>
            `;
            audit.inferred_calculations.forEach(item => {
                const el = document.createElement('div');
                el.className = 'audit-item';
                el.innerHTML = `
                    <span><strong><code>${escapeHtml(item.column)}</code></strong> → ${escapeHtml(t('audit_formula'))} <code>${escapeHtml(item.formula)}</code></span>
                    <span class="audit-item-badge">${escapeHtml(item.status)}</span>
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
                    <h3>${escapeHtml(t('audit_schema_title'))}</h3>
                    <p class="text-xs text-slate-400">${escapeHtml(t('audit_schema_desc'))}</p>
                </div>
            </div>
            <div class="audit-item">
                <span><strong>${escapeHtml(t('audit_renamed_cols'))}</strong> ${escapeHtml(t('audit_renamed_val', { n: Object.keys(audit.renamed_columns || {}).length }))}</span>
                <span class="audit-item-badge">${escapeHtml(t('audit_snake_badge'))}</span>
            </div>
            <div class="audit-item">
                <span><strong>${escapeHtml(t('audit_valid_rows'))}</strong> ${escapeHtml(t('audit_valid_rows_val', { clean: audit.cleaned_row_count, raw: audit.raw_row_count }))}</span>
                <span class="audit-item-badge">${escapeHtml(t('audit_verified_badge'))}</span>
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
            daxDomainTitle.textContent = t('dax_measures_title', { label: domain.label, count: daxMeasures.length });
        }
        if (pqTableName && domain) {
            pqTableName.textContent = t('pq_target_table', { table: domain.table_name });
        }

        daxList.innerHTML = '';
        daxMeasures.forEach(m => {
            const card = document.createElement('div');
            card.className = 'code-card';
            card.innerHTML = `
                <div class="code-card-header">
                    <div>
                        <span class="code-card-title">${escapeHtml(m.name)}</span>
                        <span style="font-size: 11px; color: #94a3b8; margin-left: 8px;">${escapeHtml(t('dax_format_label'))} <code>${escapeHtml(m.format)}</code></span>
                    </div>
                    <button class="copy-btn" data-code="${encodeURIComponent(m.dax)}">${escapeHtml(t('btn_copy_dax'))}</button>
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
            btn.textContent = t('btn_copied');
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
    function renderTable(columns, rows, displayLabels = {}) {
        const thead = document.getElementById('tableThead');
        const tbody = document.getElementById('tableTbody');
        thead.innerHTML = '';
        tbody.innerHTML = '';

        const trHead = document.createElement('tr');
        columns.forEach(c => {
            const th = document.createElement('th');
            const label = displayLabels[c] || c.replace(/^col_+/, '').replace(/_/g, ' ');
            th.textContent = label;
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
                    td.innerHTML = `<span class="audit-item-badge" style="background: ${badgeBg}; color: ${badgeColor}; font-weight: 700;">${escapeHtml(t('class_badge', { val }))}</span>`;
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
