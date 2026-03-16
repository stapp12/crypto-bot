"""
הגדרות הבוט — ערוך כאן את כל הפרמטרים
"""

# ── טלגרם ──────────────────────────────────────────────────
# קבל את ה-token מ-@BotFather
BOT_TOKEN = "8717551595:AAHTM6v0DIbkUyYCuDGYHsjVpaPRQNtiko0"

# ⚠️ אין צורך להגדיר GROUP_IDS!
# הבוט שומר קבוצות אוטומטית ב-groups.json כשמוסיפים אותו.
# פשוט הוסף אותו לכל קבוצה שרוצים → הוא יזהה אוטומטית.

# ── מטבעות לעקוב ─────────────────────────────────────────
# מזהי CoinGecko: https://api.coingecko.com/api/v3/coins/list
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
PRICE_INTERVAL_MINUTES    = 30   # עדכון מחירים
RANKING_INTERVAL_MINUTES  = 360  # דירוג Top 10 (כל 6 שעות)
PUMP_CHECK_INTERVAL_MINUTES = 15 # בדיקת pump/dump
NEWS_INTERVAL_MINUTES     = 60   # חדשות

# ── התראות מחיר רגילות ────────────────────────────────────
# שלח התראה כשמטבע משנה יותר מ-X% ב-24 שעות
PRICE_ALERT_THRESHOLD = 5.0

# ── זיהוי Pump / Dump ─────────────────────────────────────
# שינוי מחיר מינימלי (%) בין שתי בדיקות רצופות להחשיב כ-pump/dump
PUMP_PRICE_THRESHOLD = 3.0       # % שינוי מחיר מהיר (בין בדיקות)

# מכפיל נפח מסחר — כמה פעמים גדול יותר מהנורמה כדי להחשיב כחריג
# 2.0 = נפח גבוה פי 2 מהממוצע
PUMP_VOLUME_MULTIPLIER = 2.0

# ── מקורות חדשות (RSS) ───────────────────────────────────
RSS_FEEDS = [
    "https://cointelegraph.com/rss",
    "https://decrypt.co/feed",
    "https://cryptonews.com/news/feed/",
    # "https://bitcoinmagazine.com/.rss/full/",
]
