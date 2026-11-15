/* ==========================================================================
   AutoBI Studio - Dual Dark / Light Theme Manager
   Persists user preference in localStorage + autobi_theme cookie & respects
   OS prefers-color-scheme on first visit.
   ========================================================================== */

(function () {
    const STORAGE_KEY = 'autobi_theme';
    const COOKIE_NAME = 'autobi_theme';
    const VALID = ['dark', 'light'];
    const listeners = [];

    function normalizeTheme(val) {
        const clean = String(val || '').trim().toLowerCase();
        return VALID.includes(clean) ? clean : '';
    }

    function readCookie(name) {
        const match = document.cookie.match(new RegExp('(?:^|; )' + name + '=([^;]*)'));
        return match ? decodeURIComponent(match[1]) : '';
    }

    function detectInitialTheme() {
        try {
            const params = new URLSearchParams(window.location.search);
            const fromUrl = normalizeTheme(params.get('theme'));
            if (fromUrl) return fromUrl;

            const fromStorage = normalizeTheme(localStorage.getItem(STORAGE_KEY));
            if (fromStorage) return fromStorage;
        } catch (e) { /* storage disabled */ }

        const fromCookie = normalizeTheme(readCookie(COOKIE_NAME));
        if (fromCookie) return fromCookie;

        const fromDom = normalizeTheme(document.documentElement.getAttribute('data-theme'));
        if (fromDom) return fromDom;

        if (window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches) {
            return 'light';
        }
        return 'dark';
    }

    let currentTheme = detectInitialTheme();

    const SUN_SVG = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41"/></svg>';
    const MOON_SVG = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>';

    function applyThemeDom(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        const meta = document.querySelector('meta[name="theme-color"]');
        if (meta) {
            meta.setAttribute('content', theme === 'light' ? '#f4f7fc' : '#090d16');
        }
    }

    function updateControls(theme) {
        const i18n = window.autobiI18n;
        const isDark = theme === 'dark';
        const label = i18n
            ? i18n.t(isDark ? 'theme_light_short' : 'theme_dark_short')
            : (isDark ? 'Light' : 'Dark');
        const title = i18n
            ? i18n.t(isDark ? 'theme_switch_light' : 'theme_switch_dark')
            : (isDark ? 'Switch to Light Mode' : 'Switch to Dark Mode');

        document.querySelectorAll('.theme-toggle-btn').forEach((btn) => {
            btn.setAttribute('aria-pressed', String(!isDark));
            btn.setAttribute('aria-label', title);
            btn.setAttribute('title', title);
            btn.setAttribute('data-active-theme', theme);
            const iconSlot = btn.querySelector('.theme-toggle-icon');
            const labelSlot = btn.querySelector('.theme-toggle-label');
            if (iconSlot) iconSlot.innerHTML = isDark ? SUN_SVG : MOON_SVG;
            if (labelSlot) labelSlot.textContent = label;
        });
    }

    function persistTheme(theme) {
        try {
            localStorage.setItem(STORAGE_KEY, theme);
        } catch (e) { /* ignore */ }
        const sec = window.location.protocol === 'https:' ? '; Secure' : '';
        document.cookie = `${COOKIE_NAME}=${encodeURIComponent(theme)}; path=/; max-age=31536000; SameSite=Lax${sec}`;
    }

    function setTheme(theme, persist = true) {
        const next = normalizeTheme(theme) || 'dark';
        currentTheme = next;
        applyThemeDom(next);
        if (persist) persistTheme(next);
        updateControls(next);
        listeners.forEach((cb) => {
            try { cb(next); } catch (err) { console.warn('theme listener error:', err); }
        });
        return next;
    }

    function toggleTheme() {
        return setTheme(currentTheme === 'dark' ? 'light' : 'dark', true);
    }

    function bindButtons() {
        document.querySelectorAll('.theme-toggle-btn').forEach((btn) => {
            if (btn.dataset.themeBound === '1') return;
            btn.dataset.themeBound = '1';
            btn.addEventListener('click', toggleTheme);
        });
        updateControls(currentTheme);
    }

    // Apply immediately before first paint to prevent theme flicker
    applyThemeDom(currentTheme);

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            bindButtons();
            if (window.autobiI18n && typeof window.autobiI18n.onChange === 'function') {
                window.autobiI18n.onChange(() => updateControls(currentTheme));
            }
        });
    } else {
        bindButtons();
    }

    // Sync if system preference changes and user has not explicitly saved a preference
    if (window.matchMedia) {
        const mq = window.matchMedia('(prefers-color-scheme: light)');
        const onSysChange = (e) => {
            let saved = '';
            try { saved = normalizeTheme(localStorage.getItem(STORAGE_KEY)); } catch (err) { /* ignore */ }
            if (!saved && !normalizeTheme(readCookie(COOKIE_NAME))) {
                setTheme(e.matches ? 'light' : 'dark', false);
            }
        };
        if (typeof mq.addEventListener === 'function') {
            mq.addEventListener('change', onSysChange);
        }
    }

    window.autobiTheme = {
        getTheme: () => currentTheme,
        setTheme: (t) => setTheme(t, true),
        toggleTheme,
        refreshControls: () => updateControls(currentTheme),
        onChange: (cb) => {
            if (typeof cb === 'function') listeners.push(cb);
        },
    };
})();
