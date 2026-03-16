"""
הגדרות הבוט — ערוך כאן את כל הפרמטרים
"""

# ── טלגרם ──────────────────────────────────────────────────
BOT_TOKEN = "8717551595:AAHTM6v0DIbkUyYCuDGYHsjVpaPRQNtiko0"

# ה-ID שלך — פאנל הניהול יופיע רק לך
ADMIN_ID = 6300100326

# ⚠️ אין צורך להגדיר GROUP_IDS — הבוט שומר קבוצות אוטומטית

# ── תוכן הודעות ────────────────────────────────────────────
# Footer שמופיע בסוף כל הודעה
FOOTER_TEXT = (
    "שיווק ופרסום ברמה הגבוהה ביותר + גרפיקות ברמת קצה\n"
    "@PIXELSAI\n"
    "שלחו הודעה עכשיו!"
)

# לינק לכפתור "לערוץ שלנו"
CHANNEL_LINK = "https://t.me/+xw7AIT7N4RczMWZk"

# ── מטבעות לעקוב ─────────────────────────────────────────
COINS = [
    "bitcoin",
    "ethereum",
    "solana",
    "binancecoin",
    "ripple",
    "cardano",
    "dogecoin",
    "tron",
    "avalanche-2",
    "chainlink",
    "shiba-inu",
    "pepe",
]

# ── תזמון ─────────────────────────────────────────────────
PRICE_INTERVAL_MINUTES      = 30
RANKING_INTERVAL_MINUTES    = 360
PUMP_CHECK_INTERVAL_MINUTES = 15
NEWS_INTERVAL_MINUTES       = 60

# ── התראות ────────────────────────────────────────────────
PRICE_ALERT_THRESHOLD  = 5.0
PUMP_PRICE_THRESHOLD   = 3.0
PUMP_VOLUME_MULTIPLIER = 2.0

# ── מקורות חדשות (RSS) ───────────────────────────────────
RSS_FEEDS = [
    "https://cointelegraph.com/rss",
    "https://decrypt.co/feed",
    "https://cryptonews.com/news/feed/",
]
