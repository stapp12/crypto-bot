"""
Crypto Telegram Bot v4
- Footer + כפתורי לייק/דיסלייק + לינק לערוץ
- הודעות פרטי: תגובה ברירת מחדל + פאנל ניהול לאדמין
"""

import asyncio
import json
import logging
import feedparser
import aiohttp
from datetime import datetime, timezone
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, ContextTypes, ChatMemberHandler,
    CommandHandler, MessageHandler, CallbackQueryHandler, filters
)
from telegram.constants import ParseMode
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from group_manager import load_groups, add_group, remove_group
from config import (
    BOT_TOKEN, COINS, ADMIN_ID,
    PRICE_INTERVAL_MINUTES, NEWS_INTERVAL_MINUTES,
    RANKING_INTERVAL_MINUTES, PUMP_CHECK_INTERVAL_MINUTES,
    RSS_FEEDS, PUMP_PRICE_THRESHOLD, PUMP_VOLUME_MULTIPLIER,
    PRICE_ALERT_THRESHOLD, FOOTER_TEXT, CHANNEL_LINK,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler("bot.log"), logging.StreamHandler()]
)
log = logging.getLogger(__name__)

# ── State ──────────────────────────────────────────────────
active_groups: dict[int, str] = {}
sent_news_ids: set = set()
pump_baseline: dict = {}
# מונה לייקים/דיסלייקים: {message_id: {"up": int, "down": int, "voters": set}}
vote_counts: dict = {}


# ══════════════════════════════════════════════════════════
# כפתורים
# ══════════════════════════════════════════════════════════

def make_post_keyboard(msg_id: str) -> InlineKeyboardMarkup:
    """בונה 2 שורות כפתורים לכל פוסט"""
    votes = vote_counts.get(msg_id, {"up": 0, "down": 0})
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"👍 {votes['up']}", callback_data=f"vote_up_{msg_id}"),
            InlineKeyboardButton(f"👎 {votes['down']}", callback_data=f"vote_down_{msg_id}"),
        ],
        [
            InlineKeyboardButton("📢 לערוץ שלנו", url=CHANNEL_LINK),
        ],
    ])


async def handle_vote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """מטפל בלחיצה על כפתורי לייק/דיסלייק"""
    query = update.callback_query
    await query.answer()

    data = query.data  # vote_up_MSGID או vote_down_MSGID
    parts = data.split("_", 2)
    if len(parts) != 3:
        return

    direction = parts[1]   # up / down
    msg_id    = parts[2]
    user_id   = query.from_user.id

    if msg_id not in vote_counts:
        vote_counts[msg_id] = {"up": 0, "down": 0, "voters": {}}

    voters = vote_counts[msg_id]["voters"]

    # אם כבר הצביע — בטל הצבעה
    if user_id in voters:
        prev = voters.pop(user_id)
        vote_counts[msg_id][prev] -= 1
        if prev == direction:
            # לחץ שוב על אותו כפתור = ביטול
            await query.edit_message_reply_markup(reply_markup=make_post_keyboard(msg_id))
            return

    # הצבעה חדשה
    voters[user_id] = direction
    vote_counts[msg_id][direction] += 1

    await query.edit_message_reply_markup(reply_markup=make_post_keyboard(msg_id))


# ══════════════════════════════════════════════════════════
# פאנל ניהול
# ══════════════════════════════════════════════════════════

def admin_main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 מצב הבוט",        callback_data="admin_status")],
        [InlineKeyboardButton("🪙 ניהול מטבעות",    callback_data="admin_coins"),
         InlineKeyboardButton("📰 ניהול חדשות",     callback_data="admin_news")],
        [InlineKeyboardButton("👥 קבוצות פעילות",   callback_data="admin_groups")],
        [InlineKeyboardButton("⏱ תזמונים",          callback_data="admin_timing")],
        [InlineKeyboardButton("📢 שלח הודעה ידנית", callback_data="admin_broadcast")],
    ])


async def show_admin_panel(bot: Bot, chat_id: int):
    await bot.send_message(
        chat_id=chat_id,
        text=(
            "🛠 *פאנל ניהול הבוט*\n\n"
            "ברוך הבא! בחר פעולה:"
        ),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=admin_main_keyboard(),
    )


async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id == ADMIN_ID:
        await show_admin_panel(context.bot, update.effective_chat.id)
    else:
        await update.message.reply_text(
            "⚠️ הבוט זמין רק לקבוצות ולא תומך כרגע בעדכונים לצ'אטים פרטיים."
        )


async def handle_private_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """כל הודעה פרטית שאינה /start"""
    user_id = update.effective_user.id
    if update.effective_chat.type != "private":
        return
    if user_id == ADMIN_ID:
        # אדמין שולח טקסט חופשי — אפשר להרחיב בעתיד
        await show_admin_panel(context.bot, update.effective_chat.id)
    else:
        await update.message.reply_text(
            "⚠️ הבוט זמין רק לקבוצות ולא תומך כרגע בעדכונים לצ'אטים פרטיים."
        )


async def handle_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if user_id != ADMIN_ID:
        await query.answer("אין לך הרשאה.", show_alert=True)
        return

    data = query.data

    # ── מצב הבוט ──
    if data == "admin_status":
        groups_count = len(active_groups)
        coins_count  = len(COINS)
        text = (
            f"📊 *מצב הבוט*\n\n"
            f"👥 קבוצות פעילות: {groups_count}\n"
            f"🪙 מטבעות במעקב: {coins_count}\n"
            f"📰 מקורות חדשות: {len(RSS_FEEDS)}\n"
            f"⏱ עדכון מחירים: כל {PRICE_INTERVAL_MINUTES} דקות\n"
            f"🏆 דירוג: כל {RANKING_INTERVAL_MINUTES} דקות\n"
            f"🚨 Pump/Dump: כל {PUMP_CHECK_INTERVAL_MINUTES} דקות\n"
            f"📰 חדשות: כל {NEWS_INTERVAL_MINUTES} דקות"
        )
        await query.edit_message_text(
            text=text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 חזרה", callback_data="admin_back")
            ]])
        )

    # ── קבוצות פעילות ──
    elif data == "admin_groups":
        if active_groups:
            lines = [f"👥 *קבוצות פעילות ({len(active_groups)}):*\n"]
            for gid, title in active_groups.items():
                lines.append(f"• {title} (`{gid}`)")
            text = "\n".join(lines)
        else:
            text = "אין קבוצות פעילות כרגע.\nהוסף את הבוט לקבוצה כמנהל."
        await query.edit_message_text(
            text=text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 חזרה", callback_data="admin_back")
            ]])
        )

    # ── מטבעות ──
    elif data == "admin_coins":
        lines = [f"🪙 *מטבעות במעקב ({len(COINS)}):*\n"]
        for c in COINS:
            lines.append(f"• {c}")
        lines.append("\n_לשינוי מטבעות — ערוך את config.py והעלה ל-GitHub_")
        await query.edit_message_text(
            text="\n".join(lines),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 חזרה", callback_data="admin_back")
            ]])
        )

    # ── חדשות ──
    elif data == "admin_news":
        lines = [f"📰 *מקורות חדשות ({len(RSS_FEEDS)}):*\n"]
        for f in RSS_FEEDS:
            lines.append(f"• {f}")
        lines.append("\n_לשינוי מקורות — ערוך את config.py והעלה ל-GitHub_")
        await query.edit_message_text(
            text="\n".join(lines),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 חזרה", callback_data="admin_back")
            ]])
        )

    # ── תזמונים ──
    elif data == "admin_timing":
        text = (
            f"⏱ *תזמונים נוכחיים:*\n\n"
            f"📊 מחירים: כל {PRICE_INTERVAL_MINUTES} דקות\n"
            f"🏆 דירוג: כל {RANKING_INTERVAL_MINUTES} דקות\n"
            f"🚨 Pump/Dump: כל {PUMP_CHECK_INTERVAL_MINUTES} דקות\n"
            f"📰 חדשות: כל {NEWS_INTERVAL_MINUTES} דקות\n\n"
            f"_לשינוי תזמונים — ערוך את config.py והעלה ל-GitHub_"
        )
        await query.edit_message_text(
            text=text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 חזרה", callback_data="admin_back")
            ]])
        )

    # ── שליחה ידנית ──
    elif data == "admin_broadcast":
        await query.edit_message_text(
            text=(
                "📢 *שליחה ידנית לכל הקבוצות*\n\n"
                "שלח לי את ההודעה שאתה רוצה לשדר.\n"
                "כתוב /broadcast ואחריו את הטקסט:\n\n"
                "`/broadcast ההודעה שלי כאן`"
            ),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 חזרה", callback_data="admin_back")
            ]])
        )

    # ── חזרה ──
    elif data == "admin_back":
        await query.edit_message_text(
            text="🛠 *פאנל ניהול הבוט*\n\nברוך הבא! בחר פעולה:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=admin_main_keyboard(),
        )


async def handle_broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """שליחה ידנית: /broadcast טקסט"""
    if update.effective_user.id != ADMIN_ID:
        return
    text = " ".join(context.args)
    if not text:
        await update.message.reply_text("שימוש: /broadcast הטקסט שלך")
        return
    await broadcast(context.bot, text)
    await update.message.reply_text(f"✅ נשלח ל-{len(active_groups)} קבוצות.")


# ══════════════════════════════════════════════════════════
# Auto group detection
# ══════════════════════════════════════════════════════════

async def on_my_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    change = update.my_chat_member
    if not change:
        return
    chat = change.chat
    if chat.type not in ("group", "supergroup"):
        return
    chat_id = chat.id
    title   = chat.title or str(chat_id)
    status  = change.new_chat_member.status

    if status in ("administrator", "member"):
        add_group(active_groups, chat_id, title)
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text="👋 היי! אני בוט קריפטו.\nאשלח לכאן עדכוני מחירים, דירוגים, התראות pump/dump וחדשות. 🚀",
            )
        except Exception as e:
            log.warning(f"Welcome msg failed for {chat_id}: {e}")
    elif status in ("left", "kicked", "restricted"):
        remove_group(active_groups, chat_id)


# ══════════════════════════════════════════════════════════
# CoinGecko helpers
# ══════════════════════════════════════════════════════════

COIN_META = {
    "bitcoin":      ("Bitcoin",    "₿"),
    "ethereum":     ("Ethereum",   "Ξ"),
    "solana":       ("Solana",     "◎"),
    "binancecoin":  ("BNB",        "🔶"),
    "ripple":       ("XRP",        "✦"),
    "cardano":      ("Cardano",    "🔵"),
    "dogecoin":     ("Dogecoin",   "🐕"),
    "tron":         ("TRON",       "🔴"),
    "avalanche-2":  ("Avalanche",  "🏔"),
    "chainlink":    ("Chainlink",  "🔗"),
    "matic-network":("Polygon",    "🟣"),
    "shiba-inu":    ("Shiba Inu",  "🦊"),
    "pepe":         ("PEPE",       "🐸"),
}


def coin_label(coin_id: str) -> tuple:
    return COIN_META.get(coin_id, (coin_id.capitalize(), "🪙"))


def fmt_price(p: float) -> str:
    if p >= 1000:  return f"${p:,.2f}"
    elif p >= 1:   return f"${p:.4f}"
    else:          return f"${p:.6f}"


def fmt_mcap(m: float) -> str:
    if m >= 1e9:   return f"${m/1e9:.2f}B"
    elif m >= 1e6: return f"${m/1e6:.1f}M"
    return ""


async def fetch_market_data(coins: list) -> dict:
    ids = ",".join(coins)
    url = (
        "https://api.coingecko.com/api/v3/simple/price"
        f"?ids={ids}&vs_currencies=usd"
        "&include_24hr_change=true&include_market_cap=true&include_24hr_vol=true"
    )
    async with aiohttp.ClientSession() as s:
        async with s.get(url, timeout=aiohttp.ClientTimeout(total=15)) as r:
            r.raise_for_status()
            return await r.json()


async def fetch_top_coins(limit: int = 10) -> list:
    url = (
        "https://api.coingecko.com/api/v3/coins/markets"
        f"?vs_currency=usd&order=market_cap_desc&per_page={limit}&page=1"
        "&sparkline=false&price_change_percentage=24h"
    )
    async with aiohttp.ClientSession() as s:
        async with s.get(url, timeout=aiohttp.ClientTimeout(total=15)) as r:
            r.raise_for_status()
            return await r.json()


# ══════════════════════════════════════════════════════════
# Message formatters
# ══════════════════════════════════════════════════════════

def with_footer(text: str) -> str:
    if FOOTER_TEXT:
        return text + f"\n\n{FOOTER_TEXT}"
    return text


def build_price_msg(data: dict) -> str:
    now = datetime.now().strftime("%H:%M · %d/%m/%Y")
    lines = [f"📊 *עדכון מחירי קריפטו*\n🕐 {now}\n"]
    for coin_id, d in data.items():
        price  = d.get("usd", 0) or 0
        change = d.get("usd_24h_change", 0) or 0
        mcap   = d.get("usd_market_cap", 0) or 0
        name, symbol = coin_label(coin_id)
        arrow = "🟢 ▲" if change >= 0 else "🔴 ▼"
        sign  = "+" if change >= 0 else ""
        mc    = f"  |  MCap: {fmt_mcap(mcap)}" if mcap else ""
        lines.append(f"{symbol} *{name}*: {fmt_price(price)}  {arrow} {sign}{change:.2f}%{mc}")
    lines.append("\n_נתונים: CoinGecko_")
    return with_footer("\n".join(lines))


def build_ranking_msg(coins: list) -> str:
    now = datetime.now().strftime("%H:%M · %d/%m/%Y")
    medals = ["🥇","🥈","🥉","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
    lines = [f"🏆 *דירוג מטבעות — Top {len(coins)}*\n🕐 {now}\n"]
    for i, c in enumerate(coins):
        change = c.get("price_change_percentage_24h", 0) or 0
        color  = "🟢" if change >= 0 else "🔴"
        arrow  = "▲" if change >= 0 else "▼"
        sign   = "+" if change >= 0 else ""
        lines.append(
            f"{medals[i]} *{c['name']}*\n"
            f"   {fmt_price(c['current_price'])}  {color} {arrow} {sign}{change:.2f}%  |  {fmt_mcap(c['market_cap'])}"
        )
    lines.append("\n_נתונים: CoinGecko_")
    return with_footer("\n".join(lines))


def build_pump_dump_msg(events: list) -> str:
    now = datetime.now().strftime("%H:%M · %d/%m/%Y")
    lines = [f"🚨 *זוהו תנועות חריגות!*\n🕐 {now}\n"]
    for ev in events:
        icon = "🚀 PUMP" if ev["type"] == "pump" else "💥 DUMP"
        lines.append(
            f"{icon} *{ev['name']}*\n"
            f"   מחיר: {fmt_price(ev['price'])}\n"
            f"   שינוי מחיר: {ev['price_change']:+.2f}%\n"
            f"   נפח מסחר: {ev['volume_change']:+.0f}% vs ממוצע\n"
        )
    lines.append("_⚠️ אין בזה המלצת השקעה_")
    return with_footer("\n".join(lines))


def build_news_msg(articles: list) -> str:
    now = datetime.now().strftime("%H:%M · %d/%m/%Y")
    lines = [f"📰 *חדשות קריפטו אחרונות*\n🕐 {now}\n"]
    for i, a in enumerate(articles[:8], 1):
        lines.append(f"{i}. {a['title']}\n{a['link']}\n   📌 {a['source']}\n")
    return with_footer("\n".join(lines))


# ══════════════════════════════════════════════════════════
# Broadcast עם כפתורים
# ══════════════════════════════════════════════════════════

async def broadcast(bot: Bot, text: str, disable_preview: bool = False):
    if not active_groups:
        log.warning("No active groups.")
        return
    for chat_id, title in list(active_groups.items()):
        try:
            msg_key = f"{chat_id}_{int(datetime.now().timestamp())}"
            vote_counts[msg_key] = {"up": 0, "down": 0, "voters": {}}
            await bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode=ParseMode.MARKDOWN,
                disable_web_page_preview=disable_preview,
                reply_markup=make_post_keyboard(msg_key),
            )
            log.info(f"Sent to '{title}' ({chat_id})")
        except Exception as e:
            log.error(f"Failed '{title}' ({chat_id}): {e}")


# ══════════════════════════════════════════════════════════
# Scheduled jobs
# ══════════════════════════════════════════════════════════

async def job_price_update(bot: Bot):
    log.info("Price update...")
    try:
        data = await fetch_market_data(COINS)
        await broadcast(bot, build_price_msg(data))
        alerts = []
        for coin_id, d in data.items():
            change = d.get("usd_24h_change", 0) or 0
            if abs(change) >= PRICE_ALERT_THRESHOLD:
                name, _ = coin_label(coin_id)
                direction = "🚀 זינק" if change > 0 else "💥 צנח"
                alerts.append(f"{direction} *{name}*: {change:+.1f}% ב-24h")
        if alerts:
            await broadcast(bot, "⚡ *שינויים גדולים ב-24h:*\n" + "\n".join(alerts))
    except Exception as e:
        log.error(f"Price job error: {e}")


async def job_ranking(bot: Bot):
    log.info("Ranking update...")
    try:
        coins = await fetch_top_coins(10)
        await broadcast(bot, build_ranking_msg(coins))
    except Exception as e:
        log.error(f"Ranking job error: {e}")


async def job_pump_dump(bot: Bot):
    log.info("Pump/dump check...")
    try:
        data = await fetch_market_data(COINS)
        now = datetime.now(tz=timezone.utc)
        events = []
        for coin_id, d in data.items():
            price  = d.get("usd", 0) or 0
            volume = d.get("usd_24h_vol", 0) or 0
            if coin_id in pump_baseline:
                base = pump_baseline[coin_id]
                if base["price"] > 0 and base["volume"] > 0:
                    pc = ((price - base["price"]) / base["price"]) * 100
                    vr = volume / base["volume"]
                    if abs(pc) >= PUMP_PRICE_THRESHOLD and vr >= PUMP_VOLUME_MULTIPLIER:
                        name, _ = coin_label(coin_id)
                        events.append({
                            "name": name, "type": "pump" if pc > 0 else "dump",
                            "price": price, "price_change": pc,
                            "volume_change": (vr - 1) * 100,
                        })
            pump_baseline[coin_id] = {"price": price, "volume": volume, "timestamp": now}
        if events:
            await broadcast(bot, build_pump_dump_msg(events))
    except Exception as e:
        log.error(f"Pump/dump job error: {e}")


async def job_news(bot: Bot):
    log.info("News update...")
    try:
        articles = []
        for feed_url in RSS_FEEDS:
            try:
                feed = feedparser.parse(feed_url)
                for entry in feed.entries[:5]:
                    aid = entry.get("id") or entry.get("link", "")
                    articles.append({
                        "id": aid, "title": entry.get("title", ""),
                        "link": entry.get("link", ""),
                        "source": feed.feed.get("title", "חדשות"),
                    })
            except Exception as e:
                log.error(f"RSS error {feed_url}: {e}")
        new = [a for a in articles if a["id"] not in sent_news_ids]
        if not new:
            return
        for a in new:
            sent_news_ids.add(a["id"])
        if len(sent_news_ids) > 500:
            for item in list(sent_news_ids)[:200]:
                sent_news_ids.discard(item)
        await broadcast(bot, build_news_msg(new), disable_preview=True)
    except Exception as e:
        log.error(f"News job error: {e}")


# ══════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════

async def main():
    global active_groups
    active_groups = load_groups()
    log.info(f"Loaded {len(active_groups)} group(s): {list(active_groups.values())}")

    app = Application.builder().token(BOT_TOKEN).build()

    # Handlers
    app.add_handler(ChatMemberHandler(on_my_chat_member, ChatMemberHandler.MY_CHAT_MEMBER))
    app.add_handler(CommandHandler("start", handle_start))
    app.add_handler(CommandHandler("broadcast", handle_broadcast_command))
    app.add_handler(CallbackQueryHandler(handle_vote,          pattern=r"^vote_"))
    app.add_handler(CallbackQueryHandler(handle_admin_callback, pattern=r"^admin_"))
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE & ~filters.COMMAND, handle_private_message))

    bot = app.bot
    scheduler = AsyncIOScheduler(timezone="Asia/Jerusalem")
    now_utc = datetime.now(tz=timezone.utc)

    scheduler.add_job(job_price_update, "interval", minutes=PRICE_INTERVAL_MINUTES,
                      args=[bot], next_run_time=now_utc)
    scheduler.add_job(job_ranking,      "interval", minutes=RANKING_INTERVAL_MINUTES,
                      args=[bot], next_run_time=now_utc)
    scheduler.add_job(job_pump_dump,    "interval", minutes=PUMP_CHECK_INTERVAL_MINUTES,
                      args=[bot])
    scheduler.add_job(job_news,         "interval", minutes=NEWS_INTERVAL_MINUTES,
                      args=[bot], next_run_time=now_utc)

    scheduler.start()
    log.info(f"Bot started | Prices:{PRICE_INTERVAL_MINUTES}m | Ranking:{RANKING_INTERVAL_MINUTES}m | Pump:{PUMP_CHECK_INTERVAL_MINUTES}m | News:{NEWS_INTERVAL_MINUTES}m")

    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)

    try:
        while True:
            await asyncio.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        scheduler.shutdown()
        await app.updater.stop()
        await app.stop()
        await app.shutdown()
        log.info("Bot stopped.")


if __name__ == "__main__":
    asyncio.run(main())
