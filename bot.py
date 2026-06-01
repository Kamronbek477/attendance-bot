import logging
import math
import os
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# ══════════════════════════════════════════════
#  SOZLAMALAR
# ══════════════════════════════════════════════
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "6143132501:AAF-1TEVnNuKTR1sHT6-8lVo2MdSl9ZvyVM")
ADMIN_ID           = int(os.environ.get("ADMIN_ID", "1993623102"))
WEBAPP_URL         = os.environ.get("WEBAPP_URL", "https://YOUR_APP.railway.app")

OFFICE_LAT       = float(os.environ.get("OFFICE_LAT", "41.2995"))
OFFICE_LON       = float(os.environ.get("OFFICE_LON", "69.2401"))
OFFICE_NAME      = os.environ.get("OFFICE_NAME", "Bosh ofis")
ALLOWED_RADIUS_M = int(os.environ.get("ALLOWED_RADIUS_M", "100"))
WORK_START_HOUR  = int(os.environ.get("WORK_START_HOUR", "9"))
WORK_START_MIN   = int(os.environ.get("WORK_START_MIN", "0"))
# ══════════════════════════════════════════════

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

attendance       = {}
office_loc       = {"lat": OFFICE_LAT, "lon": OFFICE_LON, "name": OFFICE_NAME}
registered_users = {}

# ─────────────────────────────────────────────
#  YORDAMCHI
# ─────────────────────────────────────────────
def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

def today_str():
    return datetime.now().strftime("%Y-%m-%d")

def is_late(dt):
    limit = dt.replace(hour=WORK_START_HOUR, minute=WORK_START_MIN, second=0, microsecond=0)
    return dt > limit

def status_emoji(s):
    return {"o_time": "✅", "late": "⏰", "absent": "❌"}.get(s, "❓")

def checkin_webapp_button():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(
            "✅ Ishga keldim",
            web_app=WebAppInfo(url=f"{WEBAPP_URL}/checkin")
        )
    ]])

def admin_menu_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 Bugungi davomat",              callback_data="admin_today")],
        [InlineKeyboardButton("📍 Ofis lokatsiyasini o'rnatish", callback_data="admin_setloc")],
        [InlineKeyboardButton("📋 Xodimlar ro'yxati",            callback_data="admin_users")],
    ])

# ─────────────────────────────────────────────
#  XABAR STILLARI
# ─────────────────────────────────────────────
def msg_success(name, time_str, date_str, dist, late):
    icon = "⏰" if late else "✅"
    holat = "Kech keldingiz" if late else "O'z vaqtida keldingiz"
    return (
        f"{icon} *Davomat tasdiqlandi!*\n"
        f"{'─'*28}\n"
        f"👤 Xodim: *{name}*\n"
        f"🕐 Vaqt: *{time_str}*\n"
        f"📅 Sana: *{date_str}*\n"
        f"📍 Ofisga masofa: *{dist} metr*\n"
        f"📌 Holat: *{holat}*"
    )

def msg_rejected(dist):
    return (
        f"❌ *Davomat tasdiqlanmadi!*\n"
        f"{'─'*28}\n"
        f"📍 Ofis: *{office_loc['name']}*\n"
        f"📏 Sizdan ofisga masofa: *{dist} metr*\n"
        f"✅ Ruxsat etilgan radius: *{ALLOWED_RADIUS_M} metr*\n\n"
        f"🚶 Ofisga yaqinlashib, qayta urinib ko'ring."
    )

def msg_already(rec):
    return (
        f"ℹ️ *Bugun allaqachon davomat qoldirdingiz!*\n"
        f"{'─'*28}\n"
        f"🕐 Vaqt: *{rec['time']}*\n"
        f"📌 Holat: {status_emoji(rec['status'])} *{rec['status_label']}*"
    )

# ─────────────────────────────────────────────
#  /start
# ─────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid  = update.effective_user.id
    name = update.effective_user.full_name

    if uid == ADMIN_ID:
        await update.message.reply_text(
            "👋 *Admin paneli*\n\nQuyidan kerakli amalni tanlang:",
            parse_mode='Markdown',
            reply_markup=admin_menu_kb()
        )
    else:
        registered_users[uid] = name
        today = today_str()
        if uid in attendance and today in attendance[uid]:
            await update.message.reply_text(
                msg_already(attendance[uid][today]),
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                f"👋 Salom, *{name}*!\n\n"
                f"🏢 Ofis: *{office_loc['name']}*\n"
                f"⏰ Ish boshlanish: *{WORK_START_HOUR:02d}:{WORK_START_MIN:02d}*\n"
                f"📍 Ruxsat etilgan radius: *{ALLOWED_RADIUS_M} metr*\n\n"
                f"Tugmani bosing — joylashuvingiz avtomatik aniqlanadi 👇",
                parse_mode='Markdown',
                reply_markup=checkin_webapp_button()
            )

# ─────────────────────────────────────────────
#  WEBAPP DAN KELGAN MA'LUMOT
# ─────────────────────────────────────────────
async def webapp_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid  = update.effective_user.id
    name = update.effective_user.full_name
    data = update.effective_message.web_app_data.data

    try:
        import json
        payload = json.loads(data)
        ulat = float(payload["lat"])
        ulon = float(payload["lon"])
    except Exception as e:
        logger.error(f"WebApp data xato: {e}")
        await update.message.reply_text(
            f"⚠️ *Xatolik yuz berdi!*\n"
            f"{'─'*28}\n"
            f"Lokatsiya ma'lumoti noto'g'ri keldi.\n"
            f"Qayta urinib ko'ring.",
            parse_mode='Markdown',
            reply_markup=checkin_webapp_button()
        )
        return

    today = today_str()
    if uid in attendance and today in attendance[uid]:
        await update.message.reply_text(
            msg_already(attendance[uid][today]),
            parse_mode='Markdown'
        )
        return

    dist = int(haversine(ulat, ulon, office_loc['lat'], office_loc['lon']))
    now  = datetime.now()

    if dist > ALLOWED_RADIUS_M:
        await update.message.reply_text(
            msg_rejected(dist),
            parse_mode='Markdown',
            reply_markup=checkin_webapp_button()
        )
        return

    late   = is_late(now)
    status = "late" if late else "o_time"
    label  = f"Kech keldi ({now.strftime('%H:%M')})" if late else f"O'z vaqtida ({now.strftime('%H:%M')})"

    if uid not in attendance:
        attendance[uid] = {}
    attendance[uid][today] = {
        "name": name, "time": now.strftime("%H:%M:%S"),
        "status": status, "status_label": label,
        "lat": ulat, "lon": ulon, "dist": dist,
    }
    registered_users[uid] = name

    await update.message.reply_text(
        msg_success(name, now.strftime("%H:%M"), now.strftime("%d.%m.%Y"), dist, late),
        parse_mode='Markdown'
    )

    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=(
            f"{'⏰' if late else '✅'} *Yangi davomat!*\n"
            f"{'─'*28}\n"
            f"👤 *{name}*\n"
            f"🕐 *{now.strftime('%H:%M:%S')}*\n"
            f"📅 {now.strftime('%d.%m.%Y')}\n"
            f"📍 Masofa: *{dist} metr*\n"
            f"📌 {status_emoji(status)} *{label}*"
        ),
        parse_mode='Markdown'
    )

# ─────────────────────────────────────────────
#  ADMIN CALLBACK
# ─────────────────────────────────────────────
async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q   = update.callback_query
    await q.answer()
    uid = q.from_user.id

    if uid != ADMIN_ID:
        await q.message.reply_text("❌ Sizda admin huquqi yo'q!")
        return

    today = today_str()

    if q.data == "admin_today":
        recs = {u: d[today] for u, d in attendance.items() if today in d}
        if not recs:
            await q.message.reply_text(
                f"📋 *{datetime.now().strftime('%d.%m.%Y')} — Bugungi davomat*\n\n"
                "😶 Hali hech kim davomat qoldirmagan.",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 Yangilash", callback_data="admin_today")]
                ])
            )
            return
        ot   = sum(1 for r in recs.values() if r['status'] == 'o_time')
        late = sum(1 for r in recs.values() if r['status'] == 'late')
        lines = [
            f"📋 *{datetime.now().strftime('%d.%m.%Y')} — Bugungi davomat*\n",
            f"✅ O'z vaqtida: *{ot}* ta",
            f"⏰ Kech: *{late}* ta",
            f"👥 Jami: *{len(recs)}* ta\n",
            "─" * 24,
        ]
        for rec in sorted(recs.values(), key=lambda x: x['time']):
            lines.append(f"{status_emoji(rec['status'])} *{rec['name']}*\n   🕐 {rec['time'][:5]}  📍 {rec['dist']} m")
        await q.message.reply_text(
            "\n".join(lines), parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Yangilash", callback_data="admin_today"),
                 InlineKeyboardButton("🏠 Menyu",     callback_data="admin_menu")]
            ])
        )

    elif q.data == "admin_setloc":
        await q.message.reply_text(
            f"📍 *Ofis lokatsiyasini o'rnatish*\n\n"
            f"Hozirgi: `{office_loc['lat']}, {office_loc['lon']}`\n\n"
            f"Yangi koordinatalarni yuboring:\n`LAT LON`\nMisol: `41.2995 69.2401`",
            parse_mode='Markdown'
        )
        context.user_data['setting_loc'] = True

    elif q.data == "admin_users":
        if not registered_users:
            await q.message.reply_text("👥 Hali hech kim ro'yxatdan o'tmagan.")
            return
        lines = ["👥 *Xodimlar:*\n"]
        for i, (uid2, uname) in enumerate(registered_users.items(), 1):
            rec = attendance.get(uid2, {}).get(today)
            mark = status_emoji(rec['status']) if rec else "❌"
            lines.append(f"{i}. {mark} *{uname}*")
        await q.message.reply_text("\n".join(lines), parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Menyu", callback_data="admin_menu")]]))

    elif q.data == "admin_menu":
        await q.message.reply_text("👋 *Admin paneli*", parse_mode='Markdown', reply_markup=admin_menu_kb())

async def admin_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid != ADMIN_ID or not context.user_data.get('setting_loc'):
        return
    try:
        parts = update.message.text.strip().split()
        lat, lon = float(parts[0]), float(parts[1])
        office_loc['lat'] = lat
        office_loc['lon'] = lon
        context.user_data['setting_loc'] = False
        await update.message.reply_text(
            f"✅ *Ofis lokatsiyasi saqlandi!*\n"
            f"{'─'*28}\n"
            f"📍 `{lat}, {lon}`\n"
            f"📏 Radius: *{ALLOWED_RADIUS_M} metr*",
            parse_mode='Markdown', reply_markup=admin_menu_kb()
        )
    except Exception:
        await update.message.reply_text("❌ Noto'g'ri format. Misol: `41.2995 69.2401`", parse_mode='Markdown')

async def davomat_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    today = today_str()
    if uid in attendance and today in attendance[uid]:
        await update.message.reply_text(msg_already(attendance[uid][today]), parse_mode='Markdown')
    else:
        await update.message.reply_text("❗ Bugun hali davomat qoldirmadingiz.", reply_markup=checkin_webapp_button())

# ─────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────
def main():
    if TELEGRAM_BOT_TOKEN == "SIZNING_BOT_TOKENINGIZ":
        print("TELEGRAM_BOT_TOKEN ni kiriting!")
        return

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start",   start))
    app.add_handler(CommandHandler("davomat", davomat_cmd))
    app.add_handler(CallbackQueryHandler(admin_callback, pattern="^admin_"))
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, webapp_data))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, admin_text))

    print("Bot ishga tushdi!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()