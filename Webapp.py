import os
import threading
import logging
import math
from datetime import datetime
from flask import Flask, render_template_string
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

# ══════════════════════════════════════════════
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "6143132501:AAF-1TEVnNuKTR1sHT6-8lVo2MdSl9ZvyVM")
ADMIN_ID           = int(os.environ.get("ADMIN_ID", "1993623102"))
WEBAPP_URL         = os.environ.get("WEBAPP_URL", "https://attendance-bot-ap2g.onrender.com/checkin")
if not WEBAPP_URL.endswith("/checkin"):
    WEBAPP_URL = WEBAPP_URL.rstrip("/") + "/checkin"
OFFICE_LAT         = float(os.environ.get("OFFICE_LAT", "41.2995"))
OFFICE_LON         = float(os.environ.get("OFFICE_LON", "69.2401"))
OFFICE_NAME        = os.environ.get("OFFICE_NAME", "Bosh ofis")
ALLOWED_RADIUS_M   = int(os.environ.get("ALLOWED_RADIUS_M", "100"))
WORK_START_HOUR    = int(os.environ.get("WORK_START_HOUR", "9"))
WORK_START_MIN     = int(os.environ.get("WORK_START_MIN", "0"))
# ══════════════════════════════════════════════

attendance       = {}
office_loc       = {"lat": OFFICE_LAT, "lon": OFFICE_LON, "name": OFFICE_NAME}
registered_users = {}

# ─────────────────────────────────────────────
#  FLASK
# ─────────────────────────────────────────────
flask_app = Flask(__name__)

HTML = """<!DOCTYPE html>
<html lang="uz">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Davomat</title>
<script src="https://telegram.org/js/telegram-web-app.js"></script>
<style>
  * { margin:0; padding:0; box-sizing:border-box; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    background: var(--tg-theme-bg-color, #fff);
    color: var(--tg-theme-text-color, #000);
    min-height: 100vh;
    display: flex; flex-direction: column;
    align-items: center; justify-content: center;
    padding: 24px;
  }
  .card {
    width: 100%; max-width: 360px;
    background: var(--tg-theme-secondary-bg-color, #f5f5f5);
    border-radius: 16px; padding: 28px 24px; text-align: center;
  }
  .icon { font-size: 56px; margin-bottom: 16px; }
  h1 { font-size: 22px; font-weight: 600; margin-bottom: 8px; }
  .sub { font-size: 14px; opacity: 0.6; margin-bottom: 28px; line-height: 1.5; }
  .btn {
    width: 100%; padding: 16px; border: none; border-radius: 12px;
    font-size: 16px; font-weight: 600; cursor: pointer;
    background: var(--tg-theme-button-color, #2481cc);
    color: var(--tg-theme-button-text-color, #fff); transition: opacity 0.2s;
  }
  .btn:disabled { opacity: 0.5; cursor: not-allowed; }
  .status { margin-top: 16px; font-size: 14px; min-height: 20px; opacity: 0.7; }
  .status.error { color: #e53935; opacity: 1; }
  .accuracy { margin-top: 8px; font-size: 12px; opacity: 0.5; }
  .spinner {
    display: inline-block; width: 18px; height: 18px;
    border: 2px solid rgba(255,255,255,0.4); border-top-color: #fff;
    border-radius: 50%; animation: spin 0.8s linear infinite;
    vertical-align: middle; margin-right: 8px;
  }
  @keyframes spin { to { transform: rotate(360deg); } }
</style>
</head>
<body>
<div class="card">
  <div class="icon">📍</div>
  <h1>Davomat tasdiqlash</h1>
  <p class="sub">Tugmani bosing — joylashuvingiz avtomatik aniqlanadi.</p>
  <button class="btn" id="btn" onclick="checkin()">✅ Ishga keldim</button>
  <div class="status" id="status"></div>
  <div class="accuracy" id="accuracy"></div>
</div>
<script>
const tg = window.Telegram.WebApp;
tg.ready(); tg.expand();
function setStatus(msg, type) {
  const el = document.getElementById('status');
  el.textContent = msg; el.className = 'status ' + (type || '');
}
function checkin() {
  const btn = document.getElementById('btn');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span>Aniqlanmoqda...';
  if (!navigator.geolocation) {
    btn.disabled = false; btn.textContent = 'Ishga keldim';
    setStatus('GPS qollab-quvvatlanmaydi', 'error'); return;
  }
  navigator.geolocation.getCurrentPosition(
    function(pos) {
      const acc = Math.round(pos.coords.accuracy);
      document.getElementById('accuracy').textContent = 'Aniqlik: +/-' + acc + ' metr';
      if (acc > 300) {
        setStatus('GPS zaif. Tashqariga chiqib urining.', 'error');
        btn.disabled = false; btn.textContent = 'Qayta'; return;
      }
      tg.sendData(JSON.stringify({lat: pos.coords.latitude, lon: pos.coords.longitude, accuracy: acc}));
    },
    function(err) {
      btn.disabled = false; btn.textContent = 'Qayta urinish';
      const msgs = {1:'GPS ruxsati yoq.', 2:'Joylashuv aniqlanmadi.', 3:'Vaqt tugadi.'};
      setStatus(msgs[err.code] || 'GPS xatosi', 'error');
    },
    {enableHighAccuracy: true, timeout: 15000, maximumAge: 0}
  );
}
</script>
</body>
</html>"""

@flask_app.route("/checkin")
def checkin_page():
    return render_template_string(HTML)

@flask_app.route("/")
@flask_app.route("/health")
def health():
    return "OK", 200

# ─────────────────────────────────────────────
#  YORDAMCHI
# ─────────────────────────────────────────────
def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin(math.radians(lat2-lat1)/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(math.radians(lon2-lon1)/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

def today_str():
    return datetime.now().strftime("%Y-%m-%d")

def is_late(dt):
    return dt > dt.replace(hour=WORK_START_HOUR, minute=WORK_START_MIN, second=0, microsecond=0)

def se(s):
    return {"o_time": "✅", "late": "⏰", "absent": "❌"}.get(s, "❓")

def checkin_kb():
    return InlineKeyboardMarkup([[InlineKeyboardButton("✅ Ishga keldim", web_app=WebAppInfo(url=WEBAPP_URL))]])

def admin_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 Bugungi davomat", callback_data="admin_today")],
        [InlineKeyboardButton("📍 Ofis lokatsiyasi", callback_data="admin_setloc")],
        [InlineKeyboardButton("📋 Xodimlar",         callback_data="admin_users")],
    ])

# ─────────────────────────────────────────────
#  BOT HANDLERS
# ─────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid  = update.effective_user.id
    name = update.effective_user.full_name
    if uid == ADMIN_ID:
        await update.message.reply_text("👋 *Admin paneli*", parse_mode='Markdown', reply_markup=admin_kb())
    else:
        registered_users[uid] = name
        today = today_str()
        if uid in attendance and today in attendance[uid]:
            rec = attendance[uid][today]
            await update.message.reply_text(
                f"ℹ️ *Bugun allaqachon davomat qoldirdingiz!*\n{'─'*28}\n🕐 *{rec['time']}*\n{se(rec['status'])} *{rec['status_label']}*",
                parse_mode='Markdown')
        else:
            await update.message.reply_text(
                f"👋 Salom, *{name}*!\n\n🏢 *{office_loc['name']}*\n⏰ *{WORK_START_HOUR:02d}:{WORK_START_MIN:02d}*\n📍 Radius: *{ALLOWED_RADIUS_M} m*\n\nTugmani bosing 👇",
                parse_mode='Markdown', reply_markup=checkin_kb())

async def webapp_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid   = update.effective_user.id
    name  = update.effective_user.full_name
    today = today_str()
    if uid in attendance and today in attendance[uid]:
        rec = attendance[uid][today]
        await update.message.reply_text(
            f"ℹ️ *Allaqachon davomat qoldirdingiz!*\n{'─'*28}\n🕐 *{rec['time']}*\n{se(rec['status'])} *{rec['status_label']}*",
            parse_mode='Markdown')
        return
    try:
        import json
        payload = json.loads(update.effective_message.web_app_data.data)
        ulat, ulon = float(payload["lat"]), float(payload["lon"])
    except Exception:
        await update.message.reply_text(
            f"⚠️ *Xatolik!*\n{'─'*28}\nLokatsiya noto'g'ri. Qayta urining.",
            parse_mode='Markdown', reply_markup=checkin_kb())
        return

    dist = int(haversine(ulat, ulon, office_loc['lat'], office_loc['lon']))
    now  = datetime.now()
    if dist > ALLOWED_RADIUS_M:
        await update.message.reply_text(
            f"❌ *Davomat tasdiqlanmadi!*\n{'─'*28}\n📍 Ofis: *{office_loc['name']}*\n📏 Masofa: *{dist} metr*\n✅ Ruxsat: *{ALLOWED_RADIUS_M} metr*\n\n🚶 Yaqinlashib qayta urining.",
            parse_mode='Markdown', reply_markup=checkin_kb())
        return

    late   = is_late(now)
    status = "late" if late else "o_time"
    label  = f"Kech keldi ({now.strftime('%H:%M')})" if late else f"O'z vaqtida ({now.strftime('%H:%M')})"
    if uid not in attendance:
        attendance[uid] = {}
    attendance[uid][today] = {"name": name, "time": now.strftime("%H:%M:%S"), "status": status, "status_label": label, "dist": dist}
    registered_users[uid] = name

    icon = "⏰" if late else "✅"
    await update.message.reply_text(
        f"{icon} *Davomat tasdiqlandi!*\n{'─'*28}\n👤 *{name}*\n🕐 *{now.strftime('%H:%M')}*\n📅 *{now.strftime('%d.%m.%Y')}*\n📍 *{dist} metr*\n📌 *{label}*",
        parse_mode='Markdown')
    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=f"{icon} *Yangi davomat!*\n{'─'*28}\n👤 *{name}*\n🕐 *{now.strftime('%H:%M:%S')}*\n📅 {now.strftime('%d.%m.%Y')}\n📍 *{dist} metr*\n{se(status)} *{label}*",
        parse_mode='Markdown')

async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.from_user.id != ADMIN_ID:
        await q.message.reply_text("❌ Admin huquqi yo'q!")
        return
    today = today_str()
    if q.data == "admin_today":
        recs = {u: d[today] for u, d in attendance.items() if today in d}
        if not recs:
            await q.message.reply_text(
                f"📋 *{datetime.now().strftime('%d.%m.%Y')}*\n\n😶 Hali hech kim kelmagan.",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Yangilash", callback_data="admin_today")]]))
            return
        ot = sum(1 for r in recs.values() if r['status'] == 'o_time')
        lt = sum(1 for r in recs.values() if r['status'] == 'late')
        lines = [f"📋 *{datetime.now().strftime('%d.%m.%Y')}*\n",
                 f"✅ O'z vaqtida: *{ot}*", f"⏰ Kech: *{lt}*", f"👥 Jami: *{len(recs)}*\n", "─" * 24]
        for r in sorted(recs.values(), key=lambda x: x['time']):
            lines.append(f"{se(r['status'])} *{r['name']}*\n   🕐 {r['time'][:5]}  📍 {r['dist']} m")
        await q.message.reply_text("\n".join(lines), parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔄 Yangilash", callback_data="admin_today"),
                InlineKeyboardButton("🏠 Menyu",     callback_data="admin_menu")]]))
    elif q.data == "admin_setloc":
        context.user_data['setting_loc'] = True
        await q.message.reply_text("📍 Koordinatani yuboring:\nFormat: `LAT LON`\nMisol: `41.2995 69.2401`", parse_mode='Markdown')
    elif q.data == "admin_users":
        if not registered_users:
            await q.message.reply_text("👥 Hali hech kim yo'q.")
            return
        lines = ["👥 *Xodimlar:*\n"]
        for i, (uid2, uname) in enumerate(registered_users.items(), 1):
            rec = attendance.get(uid2, {}).get(today)
            lines.append(f"{i}. {se(rec['status']) if rec else '❌'} *{uname}*")
        await q.message.reply_text("\n".join(lines), parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Menyu", callback_data="admin_menu")]]))
    elif q.data == "admin_menu":
        await q.message.reply_text("👋 *Admin paneli*", parse_mode='Markdown', reply_markup=admin_kb())

async def admin_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid != ADMIN_ID or not context.user_data.get('setting_loc'):
        return
    try:
        parts = update.message.text.strip().split()
        lat, lon = float(parts[0]), float(parts[1])
        office_loc['lat'], office_loc['lon'] = lat, lon
        context.user_data['setting_loc'] = False
        await update.message.reply_text(
            f"✅ *Ofis saqlandi!*\n📍 `{lat}, {lon}`\n📏 Radius: *{ALLOWED_RADIUS_M} m*",
            parse_mode='Markdown', reply_markup=admin_kb())
    except Exception:
        await update.message.reply_text("❌ Noto'g'ri format. Misol: `41.2995 69.2401`", parse_mode='Markdown')

async def davomat_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid   = update.effective_user.id
    today = today_str()
    if uid in attendance and today in attendance[uid]:
        rec = attendance[uid][today]
        await update.message.reply_text(
            f"📋 *Bugungi davomat*\n{'─'*28}\n🕐 *{rec['time'][:5]}*\n{se(rec['status'])} *{rec['status_label']}*",
            parse_mode='Markdown')
    else:
        await update.message.reply_text("❗ Bugun davomat qoldirmadingiz.", reply_markup=checkin_kb())

# ─────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))

    # Botni background threadda ishga tushir
    def run_bot():
        application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        application.add_handler(CommandHandler("start",   start))
        application.add_handler(CommandHandler("davomat", davomat_cmd))
        application.add_handler(CallbackQueryHandler(admin_callback, pattern="^admin_"))
        application.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, webapp_data))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, admin_text))
        print("Bot ishga tushdi!")
        application.run_polling(allowed_updates=Update.ALL_TYPES)

    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()

    # Flaskni asosiy threadda ishga tushir
    print(f"Flask {port} portda ishga tushdi!")
    flask_app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
