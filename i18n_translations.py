"""
i18n_translations.py - Trilingual (English, Russian, Uzbek) server-side translations
for AutoBI Studio legal pages, language resolution, and localized responses.
"""

from typing import Any, Dict

SUPPORTED_LANGS = ("en", "ru", "uz")
SUPPORTED_THEMES = ("dark", "light")


def normalize_lang(raw: str) -> str:
    """Normalize a language tag or code to 'en', 'ru', or 'uz'."""
    code = (raw or "").strip().lower().replace("_", "-")
    if code.startswith("ru"):
        return "ru"
    if code.startswith("uz"):
        return "uz"
    if code.startswith("en"):
        return "en"
    return ""


def normalize_theme(raw: str) -> str:
    """Normalize theme name to 'dark' or 'light' (empty string if invalid)."""
    val = (raw or "").strip().lower()
    if val in SUPPORTED_THEMES:
        return val
    return ""


def resolve_theme(req) -> str:
    """Resolve UI theme from ?theme= param or autobi_theme cookie (defaulting to 'dark')."""
    query_theme = normalize_theme(req.args.get("theme", ""))
    if query_theme:
        return query_theme
    cookie_theme = normalize_theme(req.cookies.get("autobi_theme", ""))
    if cookie_theme:
        return cookie_theme
    return "dark"


def resolve_lang(req) -> str:
    """Resolve active UI language from ?lang= param, autobi_lang cookie, or Accept-Language."""
    query_lang = normalize_lang(req.args.get("lang", ""))
    if query_lang in SUPPORTED_LANGS:
        return query_lang

    cookie_lang = normalize_lang(req.cookies.get("autobi_lang", ""))
    if cookie_lang in SUPPORTED_LANGS:
        return cookie_lang

    accept = req.headers.get("Accept-Language", "")
    for part in accept.split(","):
        cand = normalize_lang(part.split(";", 1)[0])
        if cand in SUPPORTED_LANGS:
            return cand

    return "en"


LEGAL_UI: Dict[str, Dict[str, str]] = {
    "en": {
        "brand_tagline": "Multi-Domain Self-Healing Spreadsheet to Power BI Engine",
        "back_to_overview": "Overview",
        "back_to_studio": "← Back to Studio",
        "effective_label": "Effective Date",
        "privacy_tab": "Privacy Policy",
        "terms_tab": "Terms of Service",
        "questions_heading": "Questions or data requests?",
        "questions_body": "Contact the AutoBI Studio team directly at",
        "open_studio": "Open AutoBI Studio",
        "footer_tagline": "AutoBI Studio · Automated Power BI & Executive Analytics",
        "theme_label": "Theme",
    },
    "ru": {
        "brand_tagline": "Мультидоменный движок очистки таблиц и генерации моделей Power BI",
        "back_to_overview": "Обзор",
        "back_to_studio": "← Назад в студию",
        "effective_label": "Дата вступления в силу",
        "privacy_tab": "Политика конфиденциальности",
        "terms_tab": "Условия использования",
        "questions_heading": "Вопросы или запросы по данным?",
        "questions_body": "Свяжитесь с командой AutoBI Studio по адресу",
        "open_studio": "Открыть AutoBI Studio",
        "footer_tagline": "AutoBI Studio · Автоматизация Power BI и управленческой аналитики",
        "theme_label": "Тема",
    },
    "uz": {
        "brand_tagline": "Jadvallarni avtomatik tozalash va Power BI modellarini yaratish tizimi",
        "back_to_overview": "Bosh sahifa",
        "back_to_studio": "← Studiyaga qaytish",
        "effective_label": "Kuchga kirish sanasi",
        "privacy_tab": "Maxfiylik siyosati",
        "terms_tab": "Foydalanish shartlari",
        "questions_heading": "Savollar yoki ma’lumotlar bo‘yicha murojaatlar bormi?",
        "questions_body": "AutoBI Studio jamoasi bilan bevosita bog‘laning:",
        "open_studio": "AutoBI Studio’ni ochish",
        "footer_tagline": "AutoBI Studio · Avtomatlashtirilgan Power BI va boshqaruv tahlili",
        "theme_label": "Mavzu",
    },
}


LEGAL_DOCUMENTS: Dict[str, Dict[str, Dict[str, Any]]] = {
    "privacy": {
        "en": {
            "doc_type": "privacy",
            "page_title": "Privacy Policy",
            "meta_description": "How AutoBI Studio handles uploaded spreadsheets, temporary sessions, cookies, and optional integrations.",
            "effective_date": "November 15, 2026",
            "heading": "Privacy Policy",
            "lead": "How AutoBI Studio collects, temporarily processes, protects, and purges data when you use autobi.uz.",
            "sections": [
                {
                    "title": "1. Information You Provide",
                    "paragraphs": [
                        "AutoBI Studio processes spreadsheets (.csv, .xlsx, .xls, up to 32 MB) and public Google Sheets URLs that you voluntarily submit for cleaning, modeling, and Power BI export.",
                    ],
                    "bullets": [
                        "Workspace sign-in: When workspace authentication is used, we store your entered work email in a cryptographically signed HTTP-only cookie (autobi_user, SameSite=Lax, Secure over HTTPS, up to 30 days) so your authenticated session persists across browser refreshes.",
                        "Support inquiries: Emails sent to support@autobi.uz are forwarded via Cloudflare Email Routing and answered via our configured mail relay (Brevo) solely to handle your request.",
                        "Optional Telegram dispatch: If you trigger a Telegram Executive Digest, we process only the bot connection state or recipient usernames/links you supply for that delivery.",
                    ],
                },
                {
                    "title": "2. Ephemeral Session Storage & Data Retention",
                    "paragraphs": [
                        "We do not sell your datasets, and we do not use your spreadsheets to train AI or machine-learning models.",
                        "To support multi-worker dashboard previews, .zip/.pbip downloads, and optional Telegram delivery, processed session artifacts are held temporarily in the server's ephemeral session store (SQLite WAL or configured Redis) for up to 2 hours (7,200 seconds) and automatically pruned upon expiry.",
                    ],
                    "bullets": [
                        "Immediate user purge: You can permanently erase your session dataset and generated artifacts from server storage at any time using the Purge button (/api/purge/<session_id>).",
                        "Local sign-out: Clicking Sign Out immediately expires the autobi_user authentication cookie.",
                    ],
                },
                {
                    "title": "3. Third-Party Services & Infrastructure",
                    "paragraphs": [
                        "Depending on the features you invoke, requests interact with limited infrastructure or user-initiated integrations:",
                    ],
                    "bullets": [
                        "Cloudflare: Provides DNS, TLS encryption, reverse-proxy security, and email routing for autobi.uz. Standard HTTP connection metadata (including client IP via CF-Connecting-IP) is used transiently for brute-force login rate limiting.",
                        "Google Sheets: Only accessed when you explicitly submit a Google Sheets URL to ingest.",
                        "Central Bank of Uzbekistan (cbu.uz): Queried strictly for public daily exchange rates when UZS/USD normalization runs; no dataset rows are sent to CBU.",
                        "Telegram Bot API: Contacted only when you connect @auto_bibot or click Send Report to deliver your generated digest.",
                    ],
                },
                {
                    "title": "4. Security Controls",
                    "paragraphs": [
                        "AutoBI enforces HTTPS transport security, HMAC-SHA256 cookie verification, login rate limiting, SSRF host validation on remote URLs, CSV/Excel formula injection sanitization, and strict browser security headers (Content-Security-Policy, X-Frame-Options, and X-Content-Type-Options).",
                    ],
                    "bullets": [],
                },
                {
                    "title": "5. Your Choices & Contact",
                    "paragraphs": [
                        "You may purge any active dataset session immediately in the UI, revoke your browser cookie via Sign Out, or contact us with privacy, deletion, or security questions at support@autobi.uz.",
                    ],
                    "bullets": [],
                },
            ],
        },
        "ru": {
            "doc_type": "privacy",
            "page_title": "Политика конфиденциальности",
            "meta_description": "Как AutoBI Studio обрабатывает загруженные таблицы, временные сессии, cookie и внешние интеграции.",
            "effective_date": "15 ноября 2026 г.",
            "heading": "Политика конфиденциальности",
            "lead": "Как AutoBI Studio собирает, временно обрабатывает, защищает и удаляет данные при использовании autobi.uz.",
            "sections": [
                {
                    "title": "1. Какие данные вы предоставляете",
                    "paragraphs": [
                        "AutoBI Studio обрабатывает таблицы (.csv, .xlsx, .xls, размером до 32 МБ) и публичные ссылки Google Sheets, которые вы добровольно загружаете для очистки, моделирования и экспорта в Power BI.",
                    ],
                    "bullets": [
                        "Вход в рабочее пространство: при использовании авторизации указанный вами рабочий email сохраняется в криптографически подписанном HTTP-only cookie (autobi_user, SameSite=Lax, Secure по HTTPS, сроком до 30 дней) для сохранения сессии при обновлении страницы.",
                        "Обращения в поддержку: письма на support@autobi.uz пересылаются через Cloudflare Email Routing и обрабатываются через почтовый шлюз Brevo исключительно для ответа на ваш запрос.",
                        "Отправка в Telegram (по желанию): при запуске отправки дайджеста обрабатываются только статус подключения бота или указанные вами получатели/ссылки.",
                    ],
                },
                {
                    "title": "2. Временное хранение сессий и сроки удаления",
                    "paragraphs": [
                        "Мы не продаем ваши данные и не используем загруженные таблицы для обучения моделей ИИ или машинного обучения.",
                        "Для работы предпросмотра дашборда, скачивания .zip/.pbip и отправки в Telegram между воркерами сервера результаты сессии временно хранятся в эфемерном хранилище (SQLite WAL или Redis) до 2 часов (7 200 секунд), после чего автоматически удаляются по истечении срока.",
                    ],
                    "bullets": [
                        "Мгновенное удаление пользователем: вы можете в любой момент полностью стереть данные текущей сессии с сервера кнопкой очистки (/api/purge/<session_id>).",
                        "Выход из аккаунта: нажатие «Выйти» немедленно аннулирует cookie авторизации autobi_user.",
                    ],
                },
                {
                    "title": "3. Сторонние сервисы и инфраструктура",
                    "paragraphs": [
                        "В зависимости от выбранных вами функций запросы могут взаимодействовать со следующей инфраструктурой и интеграциями:",
                    ],
                    "bullets": [
                        "Cloudflare: обеспечивает DNS, TLS-шифрование, защиту обратного прокси и маршрутизацию почты для autobi.uz. Технические метаданные подключения (включая IP через CF-Connecting-IP) используются временно только для защиты входа от перебора паролей.",
                        "Google Sheets: загружается только при явной отправке вами ссылки на таблицу Google.",
                        "Центральный банк Узбекистана (cbu.uz): запрашиваются только официальные курсы валют для нормализации UZS/USD; строки ваших таблиц в ЦБ не передаются.",
                        "Telegram Bot API: вызывается только когда вы подключаете @auto_bibot или нажимаете «Отправить отчет».",
                    ],
                },
                {
                    "title": "4. Меры безопасности",
                    "paragraphs": [
                        "AutoBI применяет шифрование HTTPS, проверку cookie по HMAC-SHA256, ограничение частоты неудачных попыток входа, проверку SSRF для внешних URL, защиту от инъекций формул в CSV/Excel и строгие HTTP-заголовки безопасности (Content-Security-Policy, X-Frame-Options, X-Content-Type-Options).",
                    ],
                    "bullets": [],
                },
                {
                    "title": "5. Ваши права и контакты",
                    "paragraphs": [
                        "Вы можете мгновенно удалить активную сессию в интерфейсе, очистить cookie через «Выйти» или направить любые вопросы о конфиденциальности и удалении данных на support@autobi.uz.",
                    ],
                    "bullets": [],
                },
            ],
        },
        "uz": {
            "doc_type": "privacy",
            "page_title": "Maxfiylik siyosati",
            "meta_description": "AutoBI Studio yuklangan jadvallar, vaqtinchalik sessiyalar, cookie va integratsiyalarni qanday qayta ishlashi haqida.",
            "effective_date": "2026-yil 15-noyabr",
            "heading": "Maxfiylik siyosati",
            "lead": "autobi.uz platformasidan foydalanganda AutoBI Studio ma’lumotlarni qanday qabul qilishi, vaqtincha qayta ishlashi, himoyalashi va o‘chirishi haqida.",
            "sections": [
                {
                    "title": "1. Siz taqdim etadigan ma’lumotlar",
                    "paragraphs": [
                        "AutoBI Studio tozalash, modellashtirish va Power BI eksporti uchun siz ixtiyoriy ravishda yuborgan jadvallarni (.csv, .xlsx, .xls, 32 MB gacha) hamda ochiq Google Sheets havolalarini qayta ishlaydi.",
                    ],
                    "bullets": [
                        "Ish maydoniga kirish: autentifikatsiya yoqilganda, kiritilgan ishchi elektron pochta manzilingiz kriptografik imzolangan HTTP-only cookie’da (autobi_user, SameSite=Lax, HTTPS orqali Secure, 30 kungacha) saqlanadi — bu sahifani yangilaganda sessiyani saqlab qolish uchun xizmat qiladi.",
                        "Qo‘llab-quvvatlash murojaatlari: support@autobi.uz manziliga yuborilgan xatlar Cloudflare Email Routing orqali yo‘naltiriladi va faqat murojaatingizga javob berish uchun Brevo pochta tizimi orqali qayta ishlanadi.",
                        "Ixtiyoriy Telegram yuborish: Telegram hisobotini yuborishni tanlaganingizda, faqat bot ulanish holati yoki siz ko‘rsatgan qabul qiluvchi manzillari/havolalari qayta ishlanadi.",
                    ],
                },
                {
                    "title": "2. Vaqtinchalik sessiya saqlanishi va o‘chirish muddati",
                    "paragraphs": [
                        "Biz ma’lumotlaringizni sotmaymiz va jadvallaringizdan AI yoki mashinaviy o‘rganish modellarini o‘qitish uchun foydalanmaymiz.",
                        "Ko‘p oqimli serverda dastlabki ko‘rish, .zip/.pbip yuklab olish va Telegram orqali yuborish ishlashi uchun qayta ishlangan sessiya natijalari serverning vaqtinchalik xotirasida (SQLite WAL yoki Redis) ko‘pi bilan 2 soat (7 200 soniya) saqlanadi va muddati tugagach avtomatik o‘chiriladi.",
                    ],
                    "bullets": [
                        "Foydalanuvchi tomonidan darhol tozalash: istalgan vaqtda tozalash tugmasi (/api/purge/<session_id>) orqali joriy sessiya ma’lumotlarini server xotirasidan butunlay o‘chirishingiz mumkin.",
                        "Tizimdan chiqish: «Chiqish» tugmasini bosish autobi_user cookie’sini darhol bekor qiladi.",
                    ],
                },
                {
                    "title": "3. Uchinchi tomon xizmatlari va infratuzilma",
                    "paragraphs": [
                        "Siz tanlagan funksiyalarga qarab, so‘rovlar quyidagi infratuzilma yoki siz boshlagan integratsiyalar bilan ishlashi mumkin:",
                    ],
                    "bullets": [
                        "Cloudflare: autobi.uz uchun DNS, TLS shifrlash, proksi himoyasi va pochta yo‘naltirishni ta’minlaydi. Ulanishning texnik ma’lumotlari (jumladan CF-Connecting-IP orqali mijoz IP manzili) kirishni brute-force hujumlardan cheklash uchun vaqtincha ishlatiladi.",
                        "Google Sheets: faqat siz Google Sheets havolasini yuborganingizda ma’lumot yuklab olinadi.",
                        "O‘zbekiston Markaziy banki (cbu.uz): UZS/USD valyuta normallashtirish ishlaganda faqat rasmiy kunlik kurslar so‘raladi; jadvalingizdagi birorta qator CBU’ga yuborilmaydi.",
                        "Telegram Bot API: faqat @auto_bibot’ni ulaganingizda yoki «Hisobotni yuborish» tugmasini bosganingizda ishlatiladi.",
                    ],
                },
                {
                    "title": "4. Xavfsizlik choralari",
                    "paragraphs": [
                        "AutoBI HTTPS shifrlash, HMAC-SHA256 cookie tekshiruvi, kirish urinishlarini cheklash, tashqi URL manzillarida SSRF tekshiruvi, CSV/Excel formulalar inyeksiyasidan tozalash va qat’iy brauzer xavfsizlik sarlavhalarini (Content-Security-Policy, X-Frame-Options, X-Content-Type-Options) qo‘llaydi.",
                    ],
                    "bullets": [],
                },
                {
                    "title": "5. Sizning huquqlaringiz va aloqa",
                    "paragraphs": [
                        "Siz faol sessiyani interfeysda darhol tozalashingiz, «Chiqish» orqali cookie’ni o‘chirishingiz yoki maxfiylik va ma’lumotlarni o‘chirish bo‘yicha savollar bilan support@autobi.uz manziliga murojaat qilishingiz mumkin.",
                    ],
                    "bullets": [],
                },
            ],
        },
    },
    "terms": {
        "en": {
            "doc_type": "terms",
            "page_title": "Terms of Service",
            "meta_description": "Terms governing access to and use of AutoBI Studio at autobi.uz.",
            "effective_date": "November 15, 2026",
            "heading": "Terms of Service",
            "lead": "The rules, ownership rights, and disclaimers that apply when you use AutoBI Studio at autobi.uz.",
            "sections": [
                {
                    "title": "1. Acceptance of Terms",
                    "paragraphs": [
                        "By accessing or using AutoBI Studio (https://autobi.uz), including uploading files, connecting spreadsheets, or downloading generated Power BI artifacts, you agree to be bound by these Terms of Service and our Privacy Policy.",
                    ],
                    "bullets": [],
                },
                {
                    "title": "2. Ownership & Your Data Responsibilities",
                    "paragraphs": [
                        "You retain all ownership and intellectual property rights in the spreadsheets you upload and the outputs generated for you (including cleaned CSVs, Power Query M scripts, DAX formulas, HTML previews, and .pbip bundles).",
                    ],
                    "bullets": [
                        "You confirm that you have all necessary rights and organizational permissions to upload and process any business or financial data you submit.",
                        "You agree not to upload unlawful or malicious payloads, probe or bypass access controls or rate limits, or disrupt service availability for other users.",
                    ],
                },
                {
                    "title": "3. Automated Analytics & Output Verification",
                    "paragraphs": [
                        "AutoBI Studio uses automated heuristics to classify business domains, repair malformed spreadsheet cells, detect statistical anomalies, fetch public CBU.uz reference rates, and generate Power BI DAX and M scripts.",
                        "Outputs are provided for analytical assistance only. You are solely responsible for reviewing and validating cleaned datasets, exchange-rate conversions, and generated formulas before relying on them for financial reporting, tax, compliance, or executive decisions.",
                    ],
                    "bullets": [],
                },
                {
                    "title": "4. Ephemeral Availability & Session Expiry",
                    "paragraphs": [
                        "Active analysis sessions expire automatically after 2 hours and may be cleared sooner via explicit Purge or server maintenance. Always download your Power BI starter pack (.zip/.pbip) before leaving or purging a session; AutoBI Studio is not a backup or archival service.",
                    ],
                    "bullets": [],
                },
                {
                    "title": "5. Disclaimer & Limitation of Liability",
                    "paragraphs": [
                        "AutoBI Studio is provided on an \"as-is\" and \"as-available\" basis without warranties of any kind, express or implied, including merchantability, fitness for a particular purpose, or uninterrupted uptime.",
                        "To the maximum extent permitted by applicable law, AutoBI Studio and its operators shall not be liable for any indirect, incidental, consequential, or data-loss damages arising out of your use of or inability to use the service.",
                    ],
                    "bullets": [],
                },
                {
                    "title": "6. Changes & Contact",
                    "paragraphs": [
                        "We may update these Terms or our Privacy Policy from time to time by updating the Effective Date on this page. Questions about these Terms may be sent to support@autobi.uz.",
                    ],
                    "bullets": [],
                },
            ],
        },
        "ru": {
            "doc_type": "terms",
            "page_title": "Условия использования",
            "meta_description": "Правила доступа и использования сервиса AutoBI Studio на autobi.uz.",
            "effective_date": "15 ноября 2026 г.",
            "heading": "Условия использования",
            "lead": "Правила, права собственности и ограничения ответственности при работе с AutoBI Studio на autobi.uz.",
            "sections": [
                {
                    "title": "1. Принятие условий",
                    "paragraphs": [
                        "Используя сервис AutoBI Studio (https://autobi.uz), включая загрузку файлов, подключение таблиц и скачивание сгенерированных пакетов Power BI, вы соглашаетесь с настоящими Условиями использования и Политикой конфиденциальности.",
                    ],
                    "bullets": [],
                },
                {
                    "title": "2. Права собственности и ответственность за данные",
                    "paragraphs": [
                        "Все права собственности и интеллектуальной собственности на загруженные таблицы и сгенерированные результаты (очищенный CSV, скрипты Power Query M, формулы DAX, HTML-отчеты и пакеты .pbip) полностью принадлежат вам.",
                    ],
                    "bullets": [
                        "Вы подтверждаете, что обладаете всеми необходимыми правами и разрешениями на загрузку и обработку передаваемых деловых и финансовых данных.",
                        "Вы обязуетесь не загружать вредоносные файлы, не обходить механизмы авторизации и ограничения запросов и не нарушать работоспособность сервиса.",
                    ],
                },
                {
                    "title": "3. Автоматическая аналитика и проверка результатов",
                    "paragraphs": [
                        "AutoBI Studio применяет автоматические алгоритмы для определения бизнес-домена, исправления ячеек, поиска аномалий, получения открытых курсов CBU.uz и генерации формул DAX и Power Query M.",
                        "Результаты носят вспомогательный аналитический характер. Вы несете самостоятельную ответственность за проверку очищенных таблиц, валютных пересчетов и формул перед использованием в финансовой, налоговой или управленческой отчетности.",
                    ],
                    "bullets": [],
                },
                {
                    "title": "4. Временный характер сессий",
                    "paragraphs": [
                        "Активные сессии автоматически удаляются через 2 часа или раньше при нажатии кнопки очистки либо обслуживании сервера. Всегда скачивайте пакет Power BI (.zip/.pbip) до закрытия или очистки сессии; AutoBI Studio не является сервисом резервного копирования или архивного хранения.",
                    ],
                    "bullets": [],
                },
                {
                    "title": "5. Отказ от гарантий и ограничение ответственности",
                    "paragraphs": [
                        "Сервис AutoBI Studio предоставляется «как есть» и «по мере доступности» без каких-либо явных или подразумеваемых гарантий бесперебойной работы или пригодности для конкретной цели.",
                        "В максимальной степени, допускаемой применимым законодательством, AutoBI Studio и его операторы не несут ответственности за косвенные, случайные убытки или потерю данных, возникшие при использовании сервиса.",
                    ],
                    "bullets": [],
                },
                {
                    "title": "6. Изменения и контакты",
                    "paragraphs": [
                        "Мы можем периодически обновлять настоящие Условия или Политику конфиденциальности с изменением даты вступления в силу на этой странице. По всем вопросам пишите на support@autobi.uz.",
                    ],
                    "bullets": [],
                },
            ],
        },
        "uz": {
            "doc_type": "terms",
            "page_title": "Foydalanish shartlari",
            "meta_description": "autobi.uz manzilidagi AutoBI Studio xizmatidan foydalanish shartlari va qoidalari.",
            "effective_date": "2026-yil 15-noyabr",
            "heading": "Foydalanish shartlari",
            "lead": "autobi.uz’da AutoBI Studio xizmatidan foydalanishda amal qiladigan qoidalar, mulkchilik huquqlari va mas’uliyat chegaralari.",
            "sections": [
                {
                    "title": "1. Shartlarni qabul qilish",
                    "paragraphs": [
                        "AutoBI Studio (https://autobi.uz) xizmatiga kirish yoki undan foydalanish, jumladan fayllar yuklash, jadvallarni ulash yoki yaratilgan Power BI fayllarini yuklab olish orqali siz ushbu Foydalanish shartlari va Maxfiylik siyosatiga rozilik bildirasiz.",
                    ],
                    "bullets": [],
                },
                {
                    "title": "2. Mulkchilik huquqi va ma’lumotlar bo‘yicha mas’uliyat",
                    "paragraphs": [
                        "Siz yuklagan jadvallar hamda siz uchun yaratilgan barcha natijalar (tozalangan CSV, Power Query M skriptlari, DAX formulalari, HTML hisobotlar va .pbip to‘plamlari) ustidan barcha mulkchilik va intellektual mulk huquqlari to‘liq sizga tegishli.",
                    ],
                    "bullets": [
                        "Siz taqdim etayotgan biznes yoki moliyaviy ma’lumotlarni yuklash va qayta ishlash uchun barcha zarur huquq va ruxsatlarga ega ekanligingizni tasdiqlaysiz.",
                        "Siz zararli yoki noqonuniy fayllarni yuklamaslikka, kirish nazorati yoki so‘rov cheklovlarini chetlab o‘tmaslikka va boshqa foydalanuvchilar uchun xizmat barqarorligini buzmaslikka rozilik bildirasiz.",
                    ],
                },
                {
                    "title": "3. Avtomatlashtirilgan tahlil va natijalarni tekshirish",
                    "paragraphs": [
                        "AutoBI Studio biznes sohasini aniqlash, xato kataklarni tuzatish, statistik anomaliyalarni topish, CBU.uz ochiq valyuta kurslarini olish hamda Power BI DAX va M skriptlarini yaratish uchun avtomatik algoritmlardan foydalanadi.",
                        "Natijalar faqat tahliliy yordam sifatida taqdim etiladi. Moliyaviy hisobot, soliq, audit yoki boshqaruv qarorlarida ishlatishdan oldin tozalangan ma’lumotlarni, valyuta hisob-kitoblarini va yaratilgan formulalarni tekshirish uchun siz shaxsan javobgarsiz.",
                    ],
                    "bullets": [],
                },
                {
                    "title": "4. Vaqtinchalik sessiyalar va muddat tugashi",
                    "paragraphs": [
                        "Faol tahlil sessiyalari 2 soatdan so‘ng avtomatik ravishda tugaydi yoki tozalash tugmasi yoxud server texnik xizmati vaqtida ertaroq o‘chirilishi mumkin. Sessiyani yopish yoki tozalashdan oldin Power BI to‘plamini (.zip/.pbip) albatta yuklab oling; AutoBI Studio zaxira nusxa yoki arxiv saqlash xizmati emas.",
                    ],
                    "bullets": [],
                },
                {
                    "title": "5. Kafolatdan voz kechish va javobgarlikni cheklash",
                    "paragraphs": [
                        "AutoBI Studio «bor holaticha» va «mavjud bo‘lishiga qarab» tamoyili asosida, uzluksiz ishlash yoki muayyan maqsadga moslik bo‘yicha hech qanday bevosita yoki bilvosita kafolatlarsiz taqdim etiladi.",
                        "Amaldagi qonunchilik ruxsat etgan maksimal darajada AutoBI Studio va uning operatorlari xizmatdan foydalanish yoki foydalana olmaslik oqibatida yuzaga kelgan bilvosita, tasodifiy zararlar yoki ma’lumot yo‘qotilishi uchun javobgar bo‘lmaydi.",
                    ],
                    "bullets": [],
                },
                {
                    "title": "6. O‘zgarishlar va aloqa",
                    "paragraphs": [
                        "Biz ushbu Shartlarni yoki Maxfiylik siyosatini vaqti-vaqti bilan sahifadagi kuchga kirish sanasini yangilash orqali o‘zgartirishimiz mumkin. Ushbu shartlar bo‘yicha savollarni support@autobi.uz manziliga yuborishingiz mumkin.",
                    ],
                    "bullets": [],
                },
            ],
        },
    },
}
