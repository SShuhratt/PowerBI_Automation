/* ==========================================================================
   AutoBI Studio - Frontend Internationalization (EN / RU / UZ)
   Note: Uzbek UI copy strictly follows O'zbek tili Sentence Case rules.
   ========================================================================== */

(function () {
    const SUPPORTED = ['en', 'ru', 'uz'];

    const DICT = {
        en: {
            page_title: 'AutoBI — Multi-Domain Self-Healing Spreadsheet to Power BI Engine',
            brand_tagline: 'Multi-Domain Self-Healing Spreadsheet to Power BI Engine',
            btn_signin: '🔓 Sign In',
            btn_signout: 'Sign Out',
            badge_engine_active: 'Multi-Domain Engine Active',
            badge_authenticated: 'Authenticated',

            hero_title: 'From Messy Spreadsheets to Power BI in Seconds',
            hero_subtitle: 'Drop any business spreadsheet — Sales, Marketing, HR, Inventory, or Finance. AutoBI auto-detects the domain, cleanses human errors, and generates tailored DAX measures.',

            trust_title: 'Zero-Persistence Guarantee:',
            trust_text: 'Your data is held only in a temporary 2-hour session cache and is never used to train models or permanently archived.',
            trust_chip_ttl: '🔒 Ephemeral 2-Hour Session TTL',
            trust_chip_purge: '⚡ 1-Click Explicit Purge',
            trust_chip_notrain: '🚫 No AI Model Training',

            mode_file: '📁 Upload File (.xlsx, .csv)',
            mode_gsheets: '🌐 Google Sheets (Live Refresh)',
            dropzone_title: 'Drag & Drop your Excel or CSV file here',
            dropzone_sub: 'Auto-detects Sales, Marketing, HR, Inventory, or Finance schemas',
            btn_browse: 'Browse Files',
            btn_sample: '⚡ Try Demo Sample (Sales)',

            gsheets_title: 'Connect Live Google Sheet',
            gsheets_sub: 'Paste your public Google Sheets link. AutoBI cleans it and creates a Power BI model configured with live 1-click cloud refresh.',
            gsheets_placeholder: 'https://docs.google.com/spreadsheets/d/.../edit#gid=0',
            gsheets_submit: '⚡ Ingest & Model',
            gsheets_hint: 'ℹ️ Sharing setting must be set to "Anyone with the link can view".',

            demo_presets_title: 'Or test with multi-domain demo presets:',
            demo_sales: '🛍️ Sales & Orders',
            demo_marketing: '📣 Marketing & Paid Media',
            demo_hr: '👥 HR & People Ops',
            demo_inventory: '📦 Inventory & Supply Chain',

            footer_ttl: 'Ephemeral Retention: Auto-expires in 2h or purge anytime with 1 click',
            footer_dax: 'Instant DAX & Power Query M generation',
            footer_support_label: 'Support:',

            loading_title: 'Analyzing, Classifying & Healing Dataset...',
            loading_sub: 'Processing spreadsheet',
            loading_step1: '1. Identifying Domain',
            loading_step2: '2. Purging Trailer Rows',
            loading_step3: '3. Modeling Domain DAX',

            results_title: 'Dataset Cleansed & Modeled',
            label_source: 'Source:',
            label_sheet_tab: 'Sheet Tab:',
            label_switch_model: 'Switch Model:',
            opt_sales: '🛍️ Sales & Orders',
            opt_marketing: '📣 Marketing & Ads',
            opt_hr: '👥 HR & People Ops',
            opt_inventory: '📦 Inventory & Supply',
            opt_finance: '💳 Finance & Accounting',

            btn_upload_another: 'Upload Another',
            btn_exec_preview: '📊 Executive Preview',
            btn_exec_preview_title: 'Open responsive executive dashboard in new browser tab',
            btn_download_zip: '📥 Download Power BI Starter Kit (.zip)',
            btn_send_telegram: '✈️ Send to Telegram',
            btn_send_telegram_title: 'Dispatch executive digest and dashboard to Telegram',
            btn_purge_data: '🔒 Purge Data',
            btn_purge_data_title: 'Permanently wipe all session data from server RAM and disk',

            tab_dashboard: 'Dashboard',
            tab_dashboard_full: '📊 Executive Dashboard',
            tab_audit_full: '🛡️ Self-Healing Audit Trail',
            tab_dax_full: '📐 Power BI & DAX Studio',
            tab_data_full: '📋 Clean Data Explorer',

            chart1_default: 'Primary Metric Breakdown',
            chart2_default: 'Distribution Breakdown',
            dax_default_title: 'Domain-Tailored DAX Measures',
            dax_default_sub: 'Production business formulas ready for Power BI Desktop.',
            pq_title: 'Power Query (M) Script',
            pq_sub: 'Paste into Power BI Advanced Editor to load with automated column typing.',
            btn_copy_m: 'Copy M Script',
            btn_copy_dax: 'Copy DAX',
            btn_copied: 'Copied!',

            auth_modal_title: 'Unlock AutoBI Workspace',
            auth_modal_sub: 'Sign in with your work email and workspace passcode to analyze datasets, export Power BI packs, and dispatch reports.',
            auth_email_label: 'Work Email',
            auth_email_placeholder: 'analyst@company.com',
            auth_pass_label: 'Workspace Access Passcode',
            auth_pass_placeholder: 'Enter access passcode',
            auth_submit_btn: '🔓 Unlock Workspace',
            auth_footer_sec: '🔒 Protected by isolated multi-worker session security & TLS encryption.',
            auth_footer_support: 'Need workspace access or support?',
            auth_footer_legal_prefix: 'By signing in, you agree to our',
            auth_footer_legal_and: 'and',

            tg_modal_title: 'Telegram Executive Digest',
            tg_modal_sub: 'Dispatch executive KPI summary and interactive HTML dashboard directly to Telegram.',
            tg_direct_title: '📱 1-Click Send to My Telegram',
            tg_detecting: 'Auto-detecting...',
            tg_connected: '✓ Connected',
            tg_connected_banner: '✓ Connected: <b>{user}</b>. Report will be delivered to your Telegram chat!',
            tg_direct_desc: 'No need to find your ID! Just tap below and press <b>START</b> in Telegram:',
            tg_open_bot: '🚀 Open {bot} & Start',
            tg_check_btn: '🔄 Check',
            tg_recent_chats: 'Recent Chats:',
            tg_recipients_label: 'Recipients (Personal Chat, Channel, or Group Links)',
            tg_recipients_placeholder: 'e.g. https://t.me/cfo_channel, @executive_board, @teammate',
            tg_recipients_hint: 'Accepts Telegram links (<code>https://t.me/my_channel</code>), <code>@channel_username</code>, or personal usernames. Separate multiple targets with commas or newlines.',
            tg_cancel: 'Cancel',
            tg_send: '✈️ Send Report',
            tg_sending: '✈️ Dispatching...',
            tg_footer: '📎 Includes interactive HTML dashboard attachment readable on iOS, Android & desktop without Power BI.',
            tg_need_dataset: 'Please upload or analyze a dataset first before sending report to Telegram.',
            tg_session_expired: 'Session expired. Please re-run analysis.',
            tg_need_target: 'Please tap "Open @auto_bibot & Start" in Telegram, or enter at least one recipient link or username.',
            tg_sent_ok: '<b>✓ Dispatched successfully!</b> Sent executive digest and HTML dashboard to <b>{count}</b> recipient(s).',
            tg_send_fail: 'Failed to dispatch report to Telegram.',

            site_footer_tagline: 'AutoBI Studio · Automated Power BI & Executive Analytics',
            link_privacy: 'Privacy Policy',
            link_terms: 'Terms of Service',
            site_footer_help: 'Need help?',

            // Dynamic JS strings
            err_auth_failed: 'Authentication failed.',
            err_server_conn: 'Server connection error: ',
            err_network: 'Network error: ',
            err_unsupported_file: 'Unsupported file type: .{ext}. Please upload an Excel (.xlsx, .xls) or CSV file.',
            err_gsheets: 'Google Sheets Error: ',
            err_gsheets_default: 'Failed to ingest sheet.',
            err_analysis: 'Analysis Error: ',
            err_analysis_default: 'Failed to process spreadsheet.',
            err_sample: 'Sample Run Error: ',
            err_sample_default: 'Failed to load sample dataset.',
            err_server: 'Server Error: ',
            loading_gsheet: 'Connecting and analyzing Google Sheet...',
            loading_preset: 'Preset: {domain} Demo Dataset',
            source_live_gsheet: '{filename} 🌐 (Live Google Sheet)',
            domain_match: '{icon} {label} ({conf}% match)',
            risk_banner: '<strong>Executive risk alert:</strong> Found {crit} critical risk(s) and {warn} warning(s) in this dataset.',
            risk_review_btn: 'Review audit details →',
            confirm_purge: 'Are you sure you want to permanently purge all data from this session? This will wipe the cleaned dataset and all artifacts from server storage.',
            err_purge: 'Error purging data: ',
            dax_measures_title: '{label} — DAX Measures ({count})',
            pq_target_table: "LoadData.m (Target Table: '{table}')",
            dax_format_label: 'Format:',

            audit_flags_title: 'CFO Red-Flags & Anomaly Detection ({count} Flagged)',
            audit_critical: '{n} Critical',
            audit_warning: '{n} Warning',
            audit_notice: '{n} Notice',
            audit_flags_desc: 'Automated audit checks for margin leakage, duplicate transactions, and extreme typo outliers.',
            audit_sample_prefix: 'Sample:',
            audit_affected: '{n} record(s) affected',
            audit_clean_title: 'Clean Bill of Health: 0 Business Anomalies Detected',
            audit_clean_desc: 'All records verified with positive unit margins, valid unique IDs, and within 3σ statistical variance.',
            audit_unpivot_title: '1C / ERP Cross-Tab Matrix Flattener Applied',
            audit_unpivot_desc: 'Automatically unpivoted wide monthly columns into standardized time-series rows for Power BI time intelligence.',
            audit_unpivot_cols: 'Temporal Columns Unpivoted:',
            audit_cols_count: '{n} columns',
            audit_pruned_cols: 'Pruned Summary Columns:',
            audit_excluded: 'Excluded from unpivot',
            audit_row_transform: 'Row Transformation:',
            audit_row_transform_val: '{raw} raw matrix rows → {unpivoted} granular records',
            audit_std_ts: 'Standard Time Series',
            audit_fx_title: 'Multi-Currency FX Normalization (CBU.uz)',
            audit_fx_desc: 'Converted mixed transaction currencies into standardized UZS and USD via official Central Bank of Uzbekistan rates.',
            audit_fx_currencies: 'Detected Currencies:',
            audit_fx_col: 'Column:',
            audit_fx_rates: 'Official CBU Rates Applied:',
            audit_fx_date: 'CBU Date: {date}',
            audit_fx_added: 'Normalized Columns Added:',
            audit_fx_std: 'UZS & USD Standardized',
            audit_pareto_title: 'Pareto (80/20) ABC Driver Segmentation',
            audit_pareto_desc: 'Identified vital high-volume contributors vs. long-tail drivers across <code>{col}</code>.',
            audit_pareto_a: 'Class A (Top 80% Vital Few):',
            audit_pareto_b: 'Class B (Next 15% Moderate):',
            audit_pareto_c: 'Class C (Bottom 5% Long-Tail):',
            audit_drivers_key: '{n} key driver(s)',
            audit_drivers_sec: '{n} secondary driver(s)',
            audit_drivers_min: '{n} minor item(s)',
            audit_volume: '{pct}% Volume',
            audit_dropped_title: 'Eliminated {n} Corrupting Trailer/Summary Row(s)',
            audit_dropped_desc: 'Human totals and blank rows purged to prevent skewing DAX aggregations.',
            audit_row_num: 'Row #{idx}:',
            audit_preview_prefix: 'Preview:',
            audit_inferred_title: 'Auto-Computed {n} Missing Business Metric(s)',
            audit_inferred_desc: 'Reconstructed missing calculations from existing attributes.',
            audit_formula: 'Formula:',
            audit_schema_title: 'Schema Normalization & Datatype Sanitization',
            audit_schema_desc: 'Headers standardized for clean DAX / Power Query syntax.',
            audit_renamed_cols: 'Renamed Columns:',
            audit_renamed_val: '{n} headers standardized.',
            audit_snake_badge: 'No special chars, lowercase snake_case',
            audit_valid_rows: 'Valid Clean Rows:',
            audit_valid_rows_val: '{clean} of {raw} raw rows loaded.',
            audit_verified_badge: '100% Verified',
            class_badge: 'Class {val}',
            none_label: 'None',
        },
        ru: {
            page_title: 'AutoBI — Автоматическая очистка таблиц и генерация моделей Power BI',
            brand_tagline: 'Мультидоменный движок очистки таблиц и генерации моделей Power BI',
            btn_signin: '🔓 Войти',
            btn_signout: 'Выйти',
            badge_engine_active: 'Мультидоменный движок активен',
            badge_authenticated: 'Авторизован',

            hero_title: 'Из хаотичных таблиц в готовый Power BI за секунды',
            hero_subtitle: 'Загрузите любую бизнес-таблицу — Продажи, Маркетинг, HR, Склад или Финансы. AutoBI сам определит домен, исправит ошибки и создаст готовые меры DAX.',

            trust_title: 'Гарантия эфемерного хранения:',
            trust_text: 'Ваши данные хранятся только во временном кэше сессии на 2 часа, не архивируются навсегда и не используются для обучения моделей.',
            trust_chip_ttl: '🔒 Временная сессия (2 часа TTL)',
            trust_chip_purge: '⚡ Удаление в 1 клик',
            trust_chip_notrain: '🚫 Без обучения ИИ-моделей',

            mode_file: '📁 Загрузить файл (.xlsx, .csv)',
            mode_gsheets: '🌐 Google Таблицы (Live-обновление)',
            dropzone_title: 'Перетащите файл Excel или CSV сюда',
            dropzone_sub: 'Автоопределение схем: Продажи, Маркетинг, HR, Склад или Финансы',
            btn_browse: 'Выбрать файл',
            btn_sample: '⚡ Демо-пример (Продажи)',

            gsheets_title: 'Подключить живую Google Таблицу',
            gsheets_sub: 'Вставьте публичную ссылку на Google Таблицу. AutoBI очистит данные и соберет модель Power BI с облачным обновлением в 1 клик.',
            gsheets_placeholder: 'https://docs.google.com/spreadsheets/d/.../edit#gid=0',
            gsheets_submit: '⚡ Загрузить и смоделировать',
            gsheets_hint: 'ℹ️ В настройках доступа выберите «Все, у кого есть ссылка — Читатель».',

            demo_presets_title: 'Или протестируйте на готовых демо-наборах:',
            demo_sales: '🛍️ Продажи и заказы',
            demo_marketing: '📣 Маркетинг и реклама',
            demo_hr: '👥 HR и персонал',
            demo_inventory: '📦 Склад и логистика',

            footer_ttl: 'Временное хранение: автоудаление через 2 часа или мгновенно в 1 клик',
            footer_dax: 'Мгновенная генерация DAX и Power Query M',
            footer_support_label: 'Поддержка:',

            loading_title: 'Анализ, классификация и очистка данных...',
            loading_sub: 'Обработка таблицы',
            loading_step1: '1. Определение домена',
            loading_step2: '2. Удаление итоговых строк',
            loading_step3: '3. Генерация DAX-модели',

            results_title: 'Данные очищены и смоделированы',
            label_source: 'Источник:',
            label_sheet_tab: 'Лист:',
            label_switch_model: 'Сменить модель:',
            opt_sales: '🛍️ Продажи и заказы',
            opt_marketing: '📣 Маркетинг и реклама',
            opt_hr: '👥 HR и персонал',
            opt_inventory: '📦 Склад и закупки',
            opt_finance: '💳 Финансы и учет',

            btn_upload_another: 'Загрузить другой',
            btn_exec_preview: '📊 Предпросмотр отчета',
            btn_exec_preview_title: 'Открыть интерактивный дашборд в новой вкладке',
            btn_download_zip: '📥 Скачать пакет Power BI (.zip)',
            btn_send_telegram: '✈️ Отправить в Telegram',
            btn_send_telegram_title: 'Отправить управленческую сводку и дашборд в Telegram',
            btn_purge_data: '🔒 Удалить данные',
            btn_purge_data_title: 'Полностью стереть данные текущей сессии с сервера',

            tab_dashboard_full: '📊 Управленческий дашборд',
            tab_audit_full: '🛡️ Журнал автоочистки',
            tab_dax_full: '📐 Студия Power BI и DAX',
            tab_data_full: '📋 Просмотр чистых данных',

            chart1_default: 'Разбивка ключевой метрики',
            chart2_default: 'Структура распределения',
            dax_default_title: 'Бизнес-меры DAX для вашего домена',
            dax_default_sub: 'Готовые формулы для вставки в Power BI Desktop.',
            pq_title: 'Скрипт Power Query (M)',
            pq_sub: 'Вставьте в расширенный редактор Power BI для загрузки с автотипизацией столбцов.',
            btn_copy_m: 'Копировать M-скрипт',
            btn_copy_dax: 'Копировать DAX',
            btn_copied: 'Скопировано!',

            auth_modal_title: 'Вход в рабочее пространство AutoBI',
            auth_modal_sub: 'Введите рабочий email и код доступа для анализа таблиц, экспорта пакетов Power BI и отправки отчетов.',
            auth_email_label: 'Рабочий Email',
            auth_email_placeholder: 'analyst@company.com',
            auth_pass_label: 'Код доступа к пространству',
            auth_pass_placeholder: 'Введите код доступа',
            auth_submit_btn: '🔓 Открыть пространство',
            auth_footer_sec: '🔒 Защищено изолированной многоворкерной сессией и TLS-шифрованием.',
            auth_footer_support: 'Нужен доступ или помощь?',
            auth_footer_legal_prefix: 'Выполняя вход, вы принимаете',
            auth_footer_legal_and: 'и',

            tg_modal_title: 'Отправка отчета в Telegram',
            tg_modal_sub: 'Отправьте KPI-сводку и интерактивный HTML-дашборд прямо в Telegram.',
            tg_direct_title: '📱 Отправить в мой Telegram в 1 клик',
            tg_detecting: 'Поиск подключения...',
            tg_connected: '✓ Подключено',
            tg_connected_banner: '✓ Подключено: <b>{user}</b>. Отчет будет отправлен в ваш чат Telegram!',
            tg_direct_desc: 'ID не нужен! Нажмите ниже и нажмите <b>START</b> в Telegram:',
            tg_open_bot: '🚀 Открыть {bot} и Start',
            tg_check_btn: '🔄 Проверить',
            tg_recent_chats: 'Недавние чаты:',
            tg_recipients_label: 'Получатели (личный чат, канал или ссылки на группы)',
            tg_recipients_placeholder: 'напр. https://t.me/cfo_channel, @executive_board, @colleague',
            tg_recipients_hint: 'Принимаются ссылки Telegram (<code>https://t.me/my_channel</code>), <code>@channel_username</code> или @username. Разделяйте запятой или с новой строки.',
            tg_cancel: 'Отмена',
            tg_send: '✈️ Отправить отчет',
            tg_sending: '✈️ Отправка...',
            tg_footer: '📎 Включает интерактивный HTML-дашборд, открывающийся на iOS, Android и ПК без Power BI.',
            tg_need_dataset: 'Сначала загрузите или проанализируйте таблицу перед отправкой в Telegram.',
            tg_session_expired: 'Сессия истекла. Повторите анализ.',
            tg_need_target: 'Нажмите «Открыть @auto_bibot и Start» в Telegram или укажите хотя бы одного получателя.',
            tg_sent_ok: '<b>✓ Успешно отправлено!</b> Дайджест и HTML-дашборд доставлены <b>{count}</b> получателям.',
            tg_send_fail: 'Не удалось отправить отчет в Telegram.',

            site_footer_tagline: 'AutoBI Studio · Автоматизация Power BI и управленческой аналитики',
            link_privacy: 'Политика конфиденциальности',
            link_terms: 'Условия использования',
            site_footer_help: 'Нужна помощь?',

            err_auth_failed: 'Ошибка авторизации.',
            err_server_conn: 'Ошибка соединения с сервером: ',
            err_network: 'Ошибка сети: ',
            err_unsupported_file: 'Неподдерживаемый формат файла: .{ext}. Загрузите Excel (.xlsx, .xls) или CSV.',
            err_gsheets: 'Ошибка Google Таблиц: ',
            err_gsheets_default: 'Не удалось загрузить таблицу.',
            err_analysis: 'Ошибка анализа: ',
            err_analysis_default: 'Не удалось обработать таблицу.',
            err_sample: 'Ошибка демо-примера: ',
            err_sample_default: 'Не удалось загрузить демо-набор.',
            err_server: 'Ошибка сервера: ',
            loading_gsheet: 'Подключение и анализ Google Таблицы...',
            loading_preset: 'Пресет: Демо-набор {domain}',
            source_live_gsheet: '{filename} 🌐 (Живая Google Таблица)',
            domain_match: '{icon} {label} (совпадение {conf}%)',
            risk_banner: '<strong>Предупреждение о рисках:</strong> найдено критических рисков: {crit}, предупреждений: {warn}.',
            risk_review_btn: 'Перейти к аудиту →',
            confirm_purge: 'Вы уверены, что хотите навсегда удалить все данные этой сессии? Очищенный набор и все артефакты будут стерты с сервера.',
            err_purge: 'Ошибка удаления данных: ',
            dax_measures_title: '{label} — меры DAX ({count})',
            pq_target_table: "LoadData.m (Целевая таблица: '{table}')",
            dax_format_label: 'Формат:',

            audit_flags_title: 'CFO-индикаторы и поиск аномалий (найдено: {count})',
            audit_critical: '{n} крит.',
            audit_warning: '{n} предотвр.',
            audit_notice: '{n} инфо',
            audit_flags_desc: 'Автоматический аудит утечки маржи, дублей транзакций и экстремальных выбросов.',
            audit_sample_prefix: 'Пример:',
            audit_affected: 'Затронуто записей: {n}',
            audit_clean_title: 'Данные чисты: бизнес-аномалий не обнаружено (0)',
            audit_clean_desc: 'Все строки прошли проверку положительной маржи, уникальности ID и порога 3σ.',
            audit_unpivot_title: 'Применено разворачивание кросс-таблицы 1С / ERP',
            audit_unpivot_desc: 'Широкие помесячные столбцы автоматически преобразованы в плоские временные ряды для Power BI Time Intelligence.',
            audit_unpivot_cols: 'Развернуто временных столбцов:',
            audit_cols_count: '{n} столбец(ов)',
            audit_pruned_cols: 'Исключенные итоговые столбцы:',
            audit_excluded: 'Исключено из unpivot',
            audit_row_transform: 'Преобразование строк:',
            audit_row_transform_val: '{raw} строк матрицы → {unpivoted} детальных записей',
            audit_std_ts: 'Стандартный временной ряд',
            audit_fx_title: 'Мультивалютная нормализация (CBU.uz)',
            audit_fx_desc: 'Смешанные валюты приведены к единым UZS и USD по официальным курсам ЦБ Узбекистана.',
            audit_fx_currencies: 'Обнаруженные валюты:',
            audit_fx_col: 'Столбец:',
            audit_fx_rates: 'Примененные курсы ЦБ:',
            audit_fx_date: 'Дата ЦБ: {date}',
            audit_fx_added: 'Добавленные столбцы:',
            audit_fx_std: 'Стандартизировано в UZS и USD',
            audit_pareto_title: 'ABC-сегментация Парето (80/20)',
            audit_pareto_desc: 'Выделены ключевые драйверы объема и «длинный хвост» по <code>{col}</code>.',
            audit_pareto_a: 'Класс A (топ-80% ключевых):',
            audit_pareto_b: 'Класс B (следующие 15%):',
            audit_pareto_c: 'Класс C (нижние 5%):',
            audit_drivers_key: '{n} ключевых',
            audit_drivers_sec: '{n} средних',
            audit_drivers_min: '{n} прочих',
            audit_volume: '{pct}% объема',
            audit_dropped_title: 'Удалено итоговых/пустых строк: {n}',
            audit_dropped_desc: 'Ручные строки «Итого» и пустые строки удалены, чтобы не искажать агрегаты DAX.',
            audit_row_num: 'Строка #{idx}:',
            audit_preview_prefix: 'Фрагмент:',
            audit_inferred_title: 'Автоматически вычислено недостающих метрик: {n}',
            audit_inferred_desc: 'Недостающие расчеты восстановлены на основе имеющихся столбцов.',
            audit_formula: 'Формула:',
            audit_schema_title: 'Нормализация схемы и санитарная обработка типов',
            audit_schema_desc: 'Заголовки приведены к чистому синтаксису DAX и Power Query.',
            audit_renamed_cols: 'Переименовано столбцов:',
            audit_renamed_val: 'стандартизировано заголовков: {n}.',
            audit_snake_badge: 'Без спецсимволов, lower snake_case',
            audit_valid_rows: 'Валидные чистые строки:',
            audit_valid_rows_val: 'загружено {clean} из {raw} исходных строк.',
            audit_verified_badge: '100% проверено',
            class_badge: 'Класс {val}',
            none_label: 'Нет',
        },
        uz: {
            page_title: 'AutoBI — Tartibsiz jadvallardan soniyalar ichida Power BI modeliga',
            brand_tagline: 'Jadvallarni avtomatik tozalash va Power BI modellarini yaratish tizimi',
            btn_signin: '🔓 Kirish',
            btn_signout: 'Chiqish',
            badge_engine_active: 'Ko‘p tarmoqli tizim faol',
            badge_authenticated: 'Tasdiqlangan',

            hero_title: 'Tartibsiz jadvallardan soniyalar ichida Power BI modeliga',
            hero_subtitle: 'Istalgan biznes jadvalini yuklang — Savdo, Marketing, HR, Ombor yoki Moliya. AutoBI sohani avtomatik aniqlaydi, xatolarni tuzatadi va mos DAX formulalarini yaratadi.',

            trust_title: 'Vaqtinchalik saqlash kafolati:',
            trust_text: 'Ma’lumotlaringiz faqat 2 soatlik vaqtinchalik sessiya keshida saqlanadi, doimiy arxivlanmaydi va modellarni o‘qitishda ishlatilmaydi.',
            trust_chip_ttl: '🔒 2 soatlik vaqtinchalik sessiya',
            trust_chip_purge: '⚡ 1 bosishda tozalash',
            trust_chip_notrain: '🚫 AI modellarida o‘qitilmaydi',

            mode_file: '📁 Fayl yuklash (.xlsx, .csv)',
            mode_gsheets: '🌐 Google Sheets (jonli yangilanish)',
            dropzone_title: 'Excel yoki CSV faylingizni shu yerga tortib tashlang',
            dropzone_sub: 'Savdo, Marketing, HR, Ombor yoki Moliya tuzilmalarini avtomatik aniqlaydi',
            btn_browse: 'Fayl tanlash',
            btn_sample: '⚡ Demo namunani sinash (Savdo)',

            gsheets_title: 'Jonli Google Sheets jadvalini ulash',
            gsheets_sub: 'Ochiq Google Sheets havolasini joylashtiring. AutoBI uni tozalaydi va 1 bosishda bulutdan yangilanadigan Power BI modelini yaratadi.',
            gsheets_placeholder: 'https://docs.google.com/spreadsheets/d/.../edit#gid=0',
            gsheets_submit: '⚡ Yuklash va modellashtirish',
            gsheets_hint: 'ℹ️ Ulashish sozlamasi «Havolaga ega barcha foydalanuvchilar ko‘rishi mumkin» bo‘lishi kerak.',

            demo_presets_title: 'Yoki ko‘p tarmoqli demo namunalarda sinab ko‘ring:',
            demo_sales: '🛍️ Savdo va buyurtmalar',
            demo_marketing: '📣 Marketing va reklama',
            demo_hr: '👥 HR va kadrlar',
            demo_inventory: '📦 Ombor va ta’minot',

            footer_ttl: 'Vaqtinchalik saqlash: 2 soatda tugaydi yoki istalgan payt 1 bosishda o‘chiriladi',
            footer_dax: 'Tezkor DAX va Power Query M yaratish',
            footer_support_label: 'Yordam:',

            loading_title: 'Jadval tahlil qilinmoqda va tozalanmoqda...',
            loading_sub: 'Jadval qayta ishlanmoqda',
            loading_step1: '1. Soha aniqlanmoqda',
            loading_step2: '2. Ortiqcha jami qatorlar o‘chirilmoqda',
            loading_step3: '3. Sohaga mos DAX tuzilmoqda',

            results_title: 'Ma’lumotlar tozalandi va modellashtirildi',
            label_source: 'Manba:',
            label_sheet_tab: 'Varaq:',
            label_switch_model: 'Modelni almashtirish:',
            opt_sales: '🛍️ Savdo va buyurtmalar',
            opt_marketing: '📣 Marketing va reklama',
            opt_hr: '👥 HR va kadrlar',
            opt_inventory: '📦 Ombor va ta’minot',
            opt_finance: '💳 Moliya va buxgalteriya',

            btn_upload_another: 'Boshqa fayl yuklash',
            btn_exec_preview: '📊 Rahbarlar panelini ko‘rish',
            btn_exec_preview_title: 'Moslashuvchan hisobot panelini yangi oynada ochish',
            btn_download_zip: '📥 Power BI to‘plamini yuklab olish (.zip)',
            btn_send_telegram: '✈️ Telegramga yuborish',
            btn_send_telegram_title: 'Qisqa tahlil va hisobotni Telegramga yuborish',
            btn_purge_data: '🔒 Ma’lumotlarni o‘chirish',
            btn_purge_data_title: 'Joriy sessiya ma’lumotlarini server xotirasidan butunlay o‘chirish',

            tab_dashboard_full: '📊 Rahbarlar paneli',
            tab_audit_full: '🛡️ Avtomatik tozalash jurnali',
            tab_dax_full: '📐 Power BI va DAX studiyasi',
            tab_data_full: '📋 Tozalangan ma’lumotlar',

            chart1_default: 'Asosiy ko‘rsatkichlar taqsimoti',
            chart2_default: 'Tarkibiy taqsimot',
            dax_default_title: 'Sohaga moslashtirilgan DAX formulalari',
            dax_default_sub: 'Power BI Desktop uchun tayyor biznes formulalar.',
            pq_title: 'Power Query (M) skripti',
            pq_sub: 'Ustun turlarini avtomatik belgilash uchun Power BI Advanced Editor’ga joylashtiring.',
            btn_copy_m: 'M skriptni nusxalash',
            btn_copy_dax: 'DAX nusxalash',
            btn_copied: 'Nusxalandi!',

            auth_modal_title: 'AutoBI ish maydonini ochish',
            auth_modal_sub: 'Jadvallarni tahlil qilish, Power BI to‘plamlarini eksport qilish va hisobot yuborish uchun ishchi email hamda kirish kodini kiriting.',
            auth_email_label: 'Ishchi email',
            auth_email_placeholder: 'analyst@company.com',
            auth_pass_label: 'Ish maydoniga kirish kodi',
            auth_pass_placeholder: 'Kirish kodini kiriting',
            auth_submit_btn: '🔓 Ish maydonini ochish',
            auth_footer_sec: '🔒 Ko‘p oqimli sessiya xavfsizligi va TLS shifrlash bilan himoyalangan.',
            auth_footer_support: 'Kirish yoki yordam kerakmi?',
            auth_footer_legal_prefix: 'Kirish orqali siz',
            auth_footer_legal_and: 'va',

            tg_modal_title: 'Telegramga qisqa hisobot yuborish',
            tg_modal_sub: 'Asosiy KPI ko‘rsatkichlari va interaktiv HTML hisobotni to‘g‘ridan-to‘g‘ri Telegramga yuboring.',
            tg_direct_title: '📱 Telegramimga 1 bosishda yuborish',
            tg_detecting: 'Avto-aniqlanmoqda...',
            tg_connected: '✓ Ulandi',
            tg_connected_banner: '✓ Ulandi: <b>{user}</b>. Hisobot Telegram chatingizga yuboriladi!',
            tg_direct_desc: 'ID qidirish shart emas! Quyidagini bosing va Telegramda <b>START</b> tugmasini bosing:',
            tg_open_bot: '🚀 {bot} ochish va Start',
            tg_check_btn: '🔄 Tekshirish',
            tg_recent_chats: 'So‘nggi chatlar:',
            tg_recipients_label: 'Qabul qiluvchilar (shaxsiy chat, kanal yoki guruh havolalari)',
            tg_recipients_placeholder: 'masalan: https://t.me/cfo_channel, @executive_board, @hamkasb',
            tg_recipients_hint: 'Telegram havolalari (<code>https://t.me/my_channel</code>), <code>@channel_username</code> yoki @username qabul qilinadi. Bir nechtasini vergul yoki yangi qator bilan ajrating.',
            tg_cancel: 'Bekor qilish',
            tg_send: '✈️ Hisobotni yuborish',
            tg_sending: '✈️ Yuborilmoqda...',
            tg_footer: '📎 Power BI’siz ham iOS, Android va kompyuterda ochiladigan interaktiv HTML hisobot ilova qilinadi.',
            tg_need_dataset: 'Telegramga yuborishdan oldin avval jadval yuklang yoki tahlil qiling.',
            tg_session_expired: 'Sessiya muddati tugadi. Tahlilni qayta ishga tushiring.',
            tg_need_target: 'Telegramda «@auto_bibot ochish va Start» tugmasini bosing yoki kamida bitta qabul qiluvchi kiriting.',
            tg_sent_ok: '<b>✓ Muvaffaqiyatli yuborildi!</b> Qisqa tahlil va HTML hisobot <b>{count}</b> ta qabul qiluvchiga yetkazildi.',
            tg_send_fail: 'Telegramga hisobot yuborishda xatolik yuz berdi.',

            site_footer_tagline: 'AutoBI Studio · Avtomatlashtirilgan Power BI va boshqaruv tahlili',
            link_privacy: 'Maxfiylik siyosati',
            link_terms: 'Foydalanish shartlari',
            site_footer_help: 'Yordam kerakmi?',

            err_auth_failed: 'Autentifikatsiya xatosi.',
            err_server_conn: 'Server bilan ulanishda xatolik: ',
            err_network: 'Tarmoq xatosi: ',
            err_unsupported_file: 'Qo‘llab-quvvatlanmaydigan fayl turi: .{ext}. Iltimos, Excel (.xlsx, .xls) yoki CSV yuklang.',
            err_gsheets: 'Google Sheets xatosi: ',
            err_gsheets_default: 'Jadvalni yuklab bo‘lmadi.',
            err_analysis: 'Tahlil xatosi: ',
            err_analysis_default: 'Jadvalni qayta ishlab bo‘lmadi.',
            err_sample: 'Demo xatosi: ',
            err_sample_default: 'Demo ma’lumotlarni yuklab bo‘lmadi.',
            err_server: 'Server xatosi: ',
            loading_gsheet: 'Google Sheets jadvaliga ulanilmoqda va tahlil qilinmoqda...',
            loading_preset: 'Namuna: {domain} demo jadvali',
            source_live_gsheet: '{filename} 🌐 (Jonli Google Sheets)',
            domain_match: '{icon} {label} ({conf}% moslik)',
            risk_banner: '<strong>Xavf haqida ogohlantirish:</strong> ushbu jadvalda {crit} ta jiddiy xavf va {warn} ta ogohlantirish topildi.',
            risk_review_btn: 'Audit tafsilotlarini ko‘rish →',
            confirm_purge: 'Ushbu sessiyadagi barcha ma’lumotlarni butunlay o‘chirishga ishonchingiz komilmi? Tozalangan jadval va barcha fayllar serverdan o‘chiriladi.',
            err_purge: 'Ma’lumotlarni o‘chirishda xatolik: ',
            dax_measures_title: '{label} — DAX formulalari ({count})',
            pq_target_table: "LoadData.m (Maqsadli jadval: '{table}')",
            dax_format_label: 'Format:',

            audit_flags_title: 'Moliyaviy xavflar va anomaliyalar tahlili ({count} ta topildi)',
            audit_critical: '{n} ta jiddiy',
            audit_warning: '{n} ta ogohlantirish',
            audit_notice: '{n} ta eslatma',
            audit_flags_desc: 'Marja yo‘qotilishi, takroriy tranzaksiyalar va keskin og‘ishlarni avtomatik tekshirish.',
            audit_sample_prefix: 'Namuna:',
            audit_affected: '{n} ta qatorga ta’sir qilgan',
            audit_clean_title: 'Ma’lumotlar toza: 0 ta biznes anomaliyasi topildi',
            audit_clean_desc: 'Barcha qatorlar ijobiy marja, yagona ID va 3σ statistik me’yor doirasida tasdiqlandi.',
            audit_unpivot_title: '1C / ERP kross-jadvalni tekislash (unpivot) qo‘llanildi',
            audit_unpivot_desc: 'Oylik keng ustunlar Power BI vaqt tahlili uchun standart vaqt qatorlariga aylantirildi.',
            audit_unpivot_cols: 'Tekislangan vaqt ustunlari:',
            audit_cols_count: '{n} ta ustun',
            audit_pruned_cols: 'Chiqarib tashlangan jami ustunlar:',
            audit_excluded: 'Unpivot’dan chiqarildi',
            audit_row_transform: 'Qatorlar o‘zgarishi:',
            audit_row_transform_val: '{raw} ta jadval qatori → {unpivoted} ta batafsil yozuv',
            audit_std_ts: 'Standart vaqt qatori',
            audit_fx_title: 'Ko‘p valyutali normallashtirish (CBU.uz)',
            audit_fx_desc: 'Aralash valyutalar O‘zbekiston Markaziy bankining rasmiy kurslari bo‘yicha UZS va USD’ga o‘tkazildi.',
            audit_fx_currencies: 'Aniqlangan valyutalar:',
            audit_fx_col: 'Ustun:',
            audit_fx_rates: 'Qo‘llangan CBU kurslari:',
            audit_fx_date: 'CBU sanasi: {date}',
            audit_fx_added: 'Qo‘shilgan normallashtirilgan ustunlar:',
            audit_fx_std: 'UZS va USD standartlashtirildi',
            audit_pareto_title: 'Pareto (80/20) ABC segmentatsiyasi',
            audit_pareto_desc: '<code>{col}</code> kesimida asosiy hajm drayverlari va kichik ulushli elementlar ajratildi.',
            audit_pareto_a: 'A sinf (yuqori 80% asosiy):',
            audit_pareto_b: 'B sinf (keyingi 15% o‘rta):',
            audit_pareto_c: 'C sinf (quyi 5% kichik):',
            audit_drivers_key: '{n} ta asosiy drayver',
            audit_drivers_sec: '{n} ta ikkinchi darajali',
            audit_drivers_min: '{n} ta kichik band',
            audit_volume: '{pct}% hajm',
            audit_dropped_title: '{n} ta xato beruvchi jami/bo‘sh qator o‘chirildi',
            audit_dropped_desc: 'DAX jamlamalarini buzmaslik uchun qo‘lda yozilgan «Jami» va bo‘sh qatorlar olib tashlandi.',
            audit_row_num: 'Qator #{idx}:',
            audit_preview_prefix: 'Namuna:',
            audit_inferred_title: '{n} ta yetishmayotgan biznes ko‘rsatkich avtomatik hisoblandi',
            audit_inferred_desc: 'Mavjud ustunlar asosida yetishmayotgan hisob-kitoblar tiklandi.',
            audit_formula: 'Formula:',
            audit_schema_title: 'Sxemani normallashtirish va ma’lumot turlarini tozalash',
            audit_schema_desc: 'Ustun sarlavhalari toza DAX va Power Query sintaksisiga moslashtirildi.',
            audit_renamed_cols: 'Qayta nomlangan ustunlar:',
            audit_renamed_val: '{n} ta sarlavha standartlashtirildi.',
            audit_snake_badge: 'Maxsus belgilarsiz, kichik snake_case',
            audit_valid_rows: 'Yaroqli toza qatorlar:',
            audit_valid_rows_val: '{raw} ta xom qatordan {clean} tasi yuklandi.',
            audit_verified_badge: '100% tasdiqlangan',
            class_badge: '{val} sinf',
            none_label: 'Yo‘q',
        },
    };

    function normalizeLang(raw) {
        if (!raw) return '';
        const lower = String(raw).trim().toLowerCase();
        if (lower.startsWith('ru')) return 'ru';
        if (lower.startsWith('uz')) return 'uz';
        if (lower.startsWith('en')) return 'en';
        return '';
    }

    function readCookie(name) {
        const match = document.cookie.match(new RegExp('(?:^|; )' + name + '=([^;]*)'));
        return match ? decodeURIComponent(match[1]) : '';
    }

    function detectInitialLang() {
        const params = new URLSearchParams(window.location.search);
        const fromUrl = normalizeLang(params.get('lang'));
        if (SUPPORTED.includes(fromUrl)) return fromUrl;

        const fromStorage = normalizeLang(localStorage.getItem('autobi_lang'));
        if (SUPPORTED.includes(fromStorage)) return fromStorage;

        const fromCookie = normalizeLang(readCookie('autobi_lang'));
        if (SUPPORTED.includes(fromCookie)) return fromCookie;

        const fromHtml = normalizeLang(document.documentElement.getAttribute('lang'));
        if (SUPPORTED.includes(fromHtml)) return fromHtml;

        const fromNav = normalizeLang(navigator.language || '');
        if (SUPPORTED.includes(fromNav)) return fromNav;

        return 'en';
    }

    let currentLang = detectInitialLang();
    const listeners = [];

    function t(key, vars) {
        const table = DICT[currentLang] || DICT.en;
        let text = table[key] !== undefined ? table[key] : (DICT.en[key] !== undefined ? DICT.en[key] : key);
        if (vars) {
            Object.keys(vars).forEach((k) => {
                text = text.replace(new RegExp('\\{' + k + '\\}', 'g'), String(vars[k]));
            });
        }
        return text;
    }

    function applyTranslations() {
        document.documentElement.setAttribute('lang', currentLang);
        document.title = t('page_title');

        document.querySelectorAll('[data-i18n]').forEach((el) => {
            const key = el.getAttribute('data-i18n');
            if (key) el.textContent = t(key);
        });
        document.querySelectorAll('[data-i18n-html]').forEach((el) => {
            const key = el.getAttribute('data-i18n-html');
            if (key) el.innerHTML = t(key);
        });
        document.querySelectorAll('[data-i18n-placeholder]').forEach((el) => {
            const key = el.getAttribute('data-i18n-placeholder');
            if (key) el.setAttribute('placeholder', t(key));
        });
        document.querySelectorAll('[data-i18n-title]').forEach((el) => {
            const key = el.getAttribute('data-i18n-title');
            if (key) el.setAttribute('title', t(key));
        });

        document.querySelectorAll('.lang-btn').forEach((btn) => {
            const isActive = btn.getAttribute('data-lang') === currentLang;
            btn.classList.toggle('active', isActive);
            btn.setAttribute('aria-pressed', isActive ? 'true' : 'false');
        });
    }

    function setLang(lang) {
        const normalized = normalizeLang(lang) || 'en';
        currentLang = normalized;
        try {
            localStorage.setItem('autobi_lang', normalized);
        } catch (_) {}
        document.cookie = `autobi_lang=${normalized}; path=/; max-age=31536000; SameSite=Lax`;
        applyTranslations();
        listeners.forEach((cb) => {
            try {
                cb(normalized);
            } catch (_) {}
        });
    }

    window.autobiI18n = {
        getLang: () => currentLang,
        setLang,
        t,
        applyTranslations,
        onChange: (cb) => {
            if (typeof cb === 'function') listeners.push(cb);
        },
    };
})();
