import os
import threading
import logging
import math
import json
import base64
from datetime import datetime
from flask import Flask, render_template_string, request, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ConversationHandler, filters, ContextTypes
)

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

# ══════════════════════════════════════════════
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "6143132501:AAF-1TEVnNuKTR1sHT6-8lVo2MdSl9ZvyVM")
ADMIN_ID           = int(os.environ.get("ADMIN_ID", "1993623102"))
BASE_URL           = os.environ.get("WEBAPP_URL", "https://attendance-bot-ap2g.onrender.com")
if BASE_URL.endswith("/checkin"):
    BASE_URL = BASE_URL[:-8]
WEBAPP_URL         = BASE_URL.rstrip("/") + "/checkin"
OFFICE_LAT         = float(os.environ.get("OFFICE_LAT", "41.2995"))
OFFICE_LON         = float(os.environ.get("OFFICE_LON", "69.2401"))
OFFICE_NAME        = os.environ.get("OFFICE_NAME", "Bosh ofis")
ALLOWED_RADIUS_M   = int(os.environ.get("ALLOWED_RADIUS_M", "100"))
WORK_START_HOUR    = int(os.environ.get("WORK_START_HOUR", "9"))
WORK_START_MIN     = int(os.environ.get("WORK_START_MIN", "0"))
# ══════════════════════════════════════════════

# Ma'lumotlar bazasi (xotira)
users      = {}       # {uid: {name, username, registered_at}}
attendance = {}       # {uid: {date: {time, status, label, dist, photo}}}
office_loc = {"lat": OFFICE_LAT, "lon": OFFICE_LON, "name": OFFICE_NAME}

# Conversation states
ASK_NAME = 1

# ─────────────────────────────────────────────
#  FLASK
# ─────────────────────────────────────────────
flask_app = Flask(__name__)

CHECKIN_HTML = """<!DOCTYPE html>
<html lang="uz">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
<title>Davomat</title>
<script src="https://telegram.org/js/telegram-web-app.js"></script>
<style>
  * { margin:0; padding:0; box-sizing:border-box; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    background: var(--tg-theme-bg-color, #1c1c1e);
    color: var(--tg-theme-text-color, #fff);
    min-height: 100vh;
    display: flex; flex-direction: column;
    align-items: center; justify-content: center;
    padding: 20px;
  }
  .card {
    width: 100%; max-width: 380px;
    background: var(--tg-theme-secondary-bg-color, #2c2c2e);
    border-radius: 20px; padding: 32px 24px; text-align: center;
  }
  .icon { font-size: 64px; margin-bottom: 12px; }
  h1 { font-size: 22px; font-weight: 700; margin-bottom: 6px; }
  .sub { font-size: 13px; opacity: 0.55; margin-bottom: 28px; line-height: 1.5; }
  .steps { display: flex; justify-content: center; gap: 8px; margin-bottom: 24px; }
  .step { width: 28px; height: 4px; border-radius: 2px; background: rgba(255,255,255,0.15); }
  .step.active { background: var(--tg-theme-button-color, #2481cc); }
  .step.done { background: #34c759; }
  .btn {
    width: 100%; padding: 16px; border: none; border-radius: 14px;
    font-size: 16px; font-weight: 600; cursor: pointer; margin-bottom: 10px;
    background: var(--tg-theme-button-color, #2481cc);
    color: var(--tg-theme-button-text-color, #fff); transition: opacity 0.2s;
  }
  .btn:disabled { opacity: 0.4; cursor: not-allowed; }
  .btn.secondary {
    background: rgba(255,255,255,0.08);
    color: var(--tg-theme-text-color, #fff);
  }
  .btn.success { background: #34c759; }
  .status { margin-top: 12px; font-size: 13px; min-height: 18px; opacity: 0.65; }
  .status.error { color: #ff453a; opacity: 1; font-weight: 500; }
  .status.success { color: #34c759; opacity: 1; font-weight: 500; }
  .info-row { display: flex; justify-content: space-between; align-items: center;
    background: rgba(255,255,255,0.06); border-radius: 10px; padding: 10px 14px;
    margin-bottom: 8px; font-size: 13px; }
  .info-label { opacity: 0.5; }
  .info-val { font-weight: 600; }
  .info-val.ok { color: #34c759; }
  .info-val.err { color: #ff453a; }
  .preview { width: 100%; border-radius: 12px; margin-bottom: 12px; display: none; }
  .spinner {
    display: inline-block; width: 16px; height: 16px;
    border: 2px solid rgba(255,255,255,0.3); border-top-color: #fff;
    border-radius: 50%; animation: spin 0.7s linear infinite;
    vertical-align: middle; margin-right: 6px;
  }
  @keyframes spin { to { transform: rotate(360deg); } }
</style>
</head>
<body>
<div class="card">
  <div class="icon" id="icon">📍</div>
  <h1 id="title">Davomat tasdiqlash</h1>
  <p class="sub" id="sub">Joylashuvingiz va rasmingiz tekshiriladi</p>

  <div class="steps">
    <div class="step active" id="s1"></div>
    <div class="step" id="s2"></div>
    <div class="step" id="s3"></div>
  </div>

  <div id="step1">
    <button class="btn" id="btnGps" onclick="getGps()">📍 Joylashuvni aniqlash</button>
    <div class="status" id="gpsStatus"></div>
  </div>

  <div id="step2" style="display:none">
    <div class="info-row"><span class="info-label">📍 GPS</span><span class="info-val ok" id="gpsResult">✓</span></div>
    <input type="file" id="photoInput" accept="image/*" capture="environment" style="display:none" onchange="photoSelected(this)">
    <img id="preview" class="preview">
    <button class="btn" id="btnPhoto" onclick="takePhoto()">📸 Rasm olish (kamera)</button>
    <div class="status" id="photoStatus"></div>
  </div>

  <div id="step3" style="display:none">
    <div class="info-row"><span class="info-label">📍 GPS</span><span class="info-val ok">✓ Aniqlandi</span></div>
    <div class="info-row"><span class="info-label">📸 Rasm</span><span class="info-val ok">✓ Olindi</span></div>
    <button class="btn success" id="btnSend" onclick="sendAll()">✅ Tasdiqlash</button>
    <div class="status" id="sendStatus"></div>
  </div>
</div>

<script>
const tg = window.Telegram.WebApp;
tg.ready(); tg.expand();
tg.setHeaderColor('secondary_bg_color');

let gpsData = null;
let photoB64 = null;

function setStep(n) {
  document.getElementById('step1').style.display = n===1?'block':'none';
  document.getElementById('step2').style.display = n===2?'block':'none';
  document.getElementById('step3').style.display = n===3?'block':'none';
  for(let i=1;i<=3;i++){
    const el = document.getElementById('s'+i);
    if(i<n) el.className='step done';
    else if(i===n) el.className='step active';
    else el.className='step';
  }
}

function getGps() {
  const btn = document.getElementById('btnGps');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span>Aniqlanmoqda...';
  document.getElementById('gpsStatus').textContent = '';

  if (!navigator.geolocation) {
    btn.disabled = false; btn.textContent = 'Qayta urinish';
    document.getElementById('gpsStatus').textContent = 'GPS qollab-quvvatlanmaydi';
    document.getElementById('gpsStatus').className = 'status error'; return;
  }

  navigator.geolocation.getCurrentPosition(
    function(pos) {
      gpsData = {lat: pos.coords.latitude, lon: pos.coords.longitude, acc: Math.round(pos.coords.accuracy)};
      document.getElementById('gpsResult').textContent = '+/-' + gpsData.acc + 'm';
      document.getElementById('gpsStatus').textContent = 'GPS muvaffaqiyatli aniqlandi';
      document.getElementById('gpsStatus').className = 'status success';
      setStep(2);
    },
    function(err) {
      btn.disabled = false; btn.textContent = 'Qayta urinish';
      const msgs = {1:'GPS ruxsati berilmagan', 2:'Joylashuv aniqlanmadi', 3:'Vaqt tugadi'};
      document.getElementById('gpsStatus').textContent = msgs[err.code] || 'GPS xatosi';
      document.getElementById('gpsStatus').className = 'status error';
    },
    {enableHighAccuracy: true, timeout: 15000, maximumAge: 0}
  );
}

function takePhoto() {
  document.getElementById('photoInput').click();
}

function photoSelected(input) {
  if (!input.files || !input.files[0]) return;
  const file = input.files[0];
  const btn = document.getElementById('btnPhoto');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span>Rasm yuklanmoqda...';

  const img = new Image();
  const url = URL.createObjectURL(file);
  img.onload = function() {
    const canvas = document.createElement('canvas');
    const MAX = 600;
    let w = img.width, h = img.height;
    if (w > h) { if (w > MAX) { h = h * MAX / w; w = MAX; } }
    else { if (h > MAX) { w = w * MAX / h; h = MAX; } }
    canvas.width = w; canvas.height = h;
    canvas.getContext('2d').drawImage(img, 0, 0, w, h);
    const dataUrl = canvas.toDataURL('image/jpeg', 0.7);
    photoB64 = dataUrl.split(',')[1];
    const preview = document.getElementById('preview');
    preview.src = dataUrl;
    preview.style.display = 'block';
    document.getElementById('photoStatus').textContent = 'Rasm tayyor';
    document.getElementById('photoStatus').className = 'status success';
    URL.revokeObjectURL(url);
    setStep(3);
  };
  img.src = url;
}

function sendAll() {
  const btn = document.getElementById('btnSend');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span>Yuborilmoqda...';

  // Faqat GPS yuboramiz (rasm keyinroq bot so'raydi)
  const payload = {
    lat: gpsData.lat,
    lon: gpsData.lon,
    accuracy: gpsData.acc,
    has_photo: photoB64 ? true : false
  };

  tg.sendData(JSON.stringify(payload));
  tg.close();
}
</script>
</body>
</html>"""

@flask_app.route("/checkin")
def checkin_page():
    return render_template_string(CHECKIN_HTML)

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

def now_time():
    return datetime.now()

def is_late(dt):
    return dt > dt.replace(hour=WORK_START_HOUR, minute=WORK_START_MIN, second=0, microsecond=0)

def se(s):
    return {"o_time": "✅", "late": "⏰", "absent": "❌"}.get(s, "❓")

def checkin_kb():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Ishga keldim", web_app=WebAppInfo(url=WEBAPP_URL))
    ]])

def admin_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 Bugungi davomat",  callback_data="admin_today")],
        [InlineKeyboardButton("📋 Xodimlar ro'yxati", callback_data="admin_users")],
        [InlineKeyboardButton("📍 Ofis lokatsiyasi",  callback_data="admin_setloc")],
    ])

def main_kb():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Ishga keldim", web_app=WebAppInfo(url=WEBAPP_URL))
    ]])

# ─────────────────────────────────────────────
#  CONVERSATION: RO'YXATDAN O'TISH
# ─────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid  = update.effective_user.id
    name = update.effective_user.full_name

    if uid == ADMIN_ID:
        await update.message.reply_text(
            "👋 *Admin paneli*\n\nXush kelibsiz!",
            parse_mode='Markdown', reply_markup=admin_kb())
        return ConversationHandler.END

    if uid in users:
        today = today_str()
        if uid in attendance and today in attendance[uid]:
            rec = attendance[uid][today]
            await update.message.reply_text(
                f"ℹ️ *Bugun davomat qoldirilgan!*\n{'─'*28}\n🕐 *{rec['time']}*\n{se(rec['status'])} *{rec['status_label']}*",
                parse_mode='Markdown')
        else:
            uname = users[uid]['name']
            await update.message.reply_text(
                f"👋 Salom, *{uname}*!\n\n🏢 *{office_loc['name']}*\n⏰ Ish boshlanishi: *{WORK_START_HOUR:02d}:{WORK_START_MIN:02d}*\n📍 Radius: *{ALLOWED_RADIUS_M} m*\n\nDavomatdan o'tish uchun tugmani bosing 👇",
                parse_mode='Markdown', reply_markup=checkin_kb())
        return ConversationHandler.END

    await update.message.reply_text(
        "👋 *Xush kelibsiz!*\n\n"
        "Tizimdan foydalanish uchun avval ro'yxatdan o'ting.\n\n"
        "📝 *Ism va familyangizni kiriting:*\n"
        "_Misol: Abdullayev Jasur_",
        parse_mode='Markdown')
    return ASK_NAME

async def ask_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid      = update.effective_user.id
    username = update.effective_user.username or "—"
    full_name = update.message.text.strip()

    if len(full_name) < 3:
        await update.message.reply_text("❌ Ism juda qisqa. Iltimos, to'liq ism va familya kiriting:")
        return ASK_NAME

    users[uid] = {
        "name":         full_name,
        "username":     username,
        "registered_at": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "tg_name":      update.effective_user.full_name,
    }

    # Adminga xabar
    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=(
            f"🆕 *Yangi xodim ro'yxatdan o'tdi!*\n"
            f"{'─'*28}\n"
            f"👤 *{full_name}*\n"
            f"📱 @{username}\n"
            f"🕐 {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        ),
        parse_mode='Markdown'
    )

    await update.message.reply_text(
        f"✅ *Ro'yxatdan o'tdingiz!*\n"
        f"{'─'*28}\n"
        f"👤 Ism: *{full_name}*\n\n"
        f"🏢 *{office_loc['name']}*\n"
        f"⏰ Ish boshlanishi: *{WORK_START_HOUR:02d}:{WORK_START_MIN:02d}*\n"
        f"📍 Radius: *{ALLOWED_RADIUS_M} m*\n\n"
        f"Davomatdan o'tish uchun tugmani bosing 👇",
        parse_mode='Markdown', reply_markup=checkin_kb()
    )
    return ConversationHandler.END

# ─────────────────────────────────────────────
#  WEBAPP DATA — DAVOMAT TASDIQLASH
# ─────────────────────────────────────────────
async def webapp_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid   = update.effective_user.id
    today = today_str()

    if uid not in users:
        await update.message.reply_text(
            "❌ Avval /start orqali ro'yxatdan o'ting!")
        return

    if uid in attendance and today in attendance[uid]:
        rec = attendance[uid][today]
        await update.message.reply_text(
            f"ℹ️ *Allaqachon davomat qoldirilgan!*\n{'─'*28}\n🕐 *{rec['time']}*\n{se(rec['status'])} *{rec['status_label']}*",
            parse_mode='Markdown')
        return

    try:
        payload = json.loads(update.effective_message.web_app_data.data)
        ulat    = float(payload["lat"])
        ulon    = float(payload["lon"])
        photo   = payload.get("photo")
    except Exception:
        await update.message.reply_text(
            f"⚠️ *Xatolik!*\n{'─'*28}\nMa'lumot noto'g'ri. Qayta urining.",
            parse_mode='Markdown', reply_markup=checkin_kb())
        return

    dist = int(haversine(ulat, ulon, office_loc['lat'], office_loc['lon']))
    now  = now_time()
    name = users[uid]['name']

    if dist > ALLOWED_RADIUS_M:
        await update.message.reply_text(
            f"❌ *Davomat tasdiqlanmadi!*\n"
            f"{'─'*28}\n"
            f"📍 Ofis: *{office_loc['name']}*\n"
            f"📏 Sizdan masofa: *{dist} metr*\n"
            f"✅ Ruxsat etilgan: *{ALLOWED_RADIUS_M} metr*\n\n"
            f"🚶 Ofisga yaqinlashib qayta urining.",
            parse_mode='Markdown', reply_markup=checkin_kb())
        return

    late   = is_late(now)
    status = "late" if late else "o_time"
    label  = f"Kech keldi ({now.strftime('%H:%M')})" if late else f"O'z vaqtida ({now.strftime('%H:%M')})"

    if uid not in attendance:
        attendance[uid] = {}
    attendance[uid][today] = {
        "name": name, "time": now.strftime("%H:%M:%S"),
        "status": status, "status_label": label, "dist": dist,
    }

    icon = "⏰" if late else "✅"

    # Xodimga javob
    await update.message.reply_text(
        f"{icon} *Davomat tasdiqlandi!*\n"
        f"{'─'*28}\n"
        f"👤 *{name}*\n"
        f"🕐 *{now.strftime('%H:%M')}*\n"
        f"📅 *{now.strftime('%d.%m.%Y')}*\n"
        f"📍 *{dist} metr*\n"
        f"📌 *{label}*",
        parse_mode='Markdown')

    # Adminga ma'lumot
    admin_msg = (
        f"{icon} *Yangi davomat!*\n"
        f"{'─'*28}\n"
        f"👤 *{name}*\n"
        f"📱 @{users[uid]['username']}\n"
        f"🕐 *{now.strftime('%H:%M:%S')}*\n"
        f"📅 {now.strftime('%d.%m.%Y')}\n"
        f"📍 *{dist} metr*\n"
        f"{se(status)} *{label}*"
    )
    await context.bot.send_message(chat_id=ADMIN_ID, text=admin_msg, parse_mode='Markdown')

    # Xodimdan rasm so'rash
    context.user_data['awaiting_photo'] = True
    await update.message.reply_text(
        "📸 *Iltimos, hozir kamera orqali rasm yuboring:*\n\n"
        "_Telegramdan 📎 → Kamera → rasm oling va yuboring_",
        parse_mode='Markdown'
    )

# ─────────────────────────────────────────────
#  ADMIN CALLBACK
# ─────────────────────────────────────────────
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
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔄 Yangilash", callback_data="admin_today"),
                    InlineKeyboardButton("🏠 Menyu",     callback_data="admin_menu")
                ]]))
            return
        ot = sum(1 for r in recs.values() if r['status'] == 'o_time')
        lt = sum(1 for r in recs.values() if r['status'] == 'late')
        lines = [
            f"📋 *{datetime.now().strftime('%d.%m.%Y')} — Bugungi davomat*\n",
            f"✅ O'z vaqtida: *{ot}* ta",
            f"⏰ Kech: *{lt}* ta",
            f"👥 Jami: *{len(recs)}* ta\n",
            "─" * 24,
        ]
        for r in sorted(recs.values(), key=lambda x: x['time']):
            lines.append(f"{se(r['status'])} *{r['name']}*\n   🕐 {r['time'][:5]}  📍 {r['dist']} m")
        await q.message.reply_text(
            "\n".join(lines), parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔄 Yangilash", callback_data="admin_today"),
                InlineKeyboardButton("🏠 Menyu",     callback_data="admin_menu")
            ]]))

    elif q.data == "admin_users":
        if not users:
            await q.message.reply_text("👥 Hali hech kim ro'yxatdan o'tmagan.")
            return
        lines = [f"👥 *Xodimlar ro'yxati ({len(users)} ta):*\n"]
        for i, (uid2, u) in enumerate(users.items(), 1):
            rec   = attendance.get(uid2, {}).get(today)
            mark  = se(rec['status']) if rec else "❌"
            uname = f"@{u['username']}" if u['username'] != '—' else ''
            lines.append(f"{i}. {mark} *{u['name']}* {uname}\n   📅 Ro'yxat: {u['registered_at']}")
        await q.message.reply_text(
            "\n".join(lines), parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🏠 Menyu", callback_data="admin_menu")
            ]]))

    elif q.data == "admin_setloc":
        context.user_data['setting_loc'] = True
        await q.message.reply_text(
            "📍 *Ofis koordinatasini yuboring:*\n\nFormat: `LAT LON`\nMisol: `41.2995 69.2401`",
            parse_mode='Markdown')

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
        await update.message.reply_text("❌ Format: `41.2995 69.2401`", parse_mode='Markdown')

async def receive_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid  = update.effective_user.id
    name = users.get(uid, {}).get('name', update.effective_user.full_name)

    if not context.user_data.get('awaiting_photo'):
        return

    context.user_data['awaiting_photo'] = False
    today = today_str()
    rec   = attendance.get(uid, {}).get(today)

    if not rec:
        return

    try:
        photo = update.message.photo[-1]
        caption = (
            f"📸 *Davomat rasmi*\n"
            f"{'─'*28}\n"
            f"👤 *{name}*\n"
            f"🕐 *{rec['time'][:5]}*\n"
            f"📅 {today}\n"
            f"{se(rec['status'])} *{rec['status_label']}*"
        )
        await context.bot.send_photo(
            chat_id=ADMIN_ID,
            photo=photo.file_id,
            caption=caption,
            parse_mode='Markdown'
        )
        await update.message.reply_text("✅ *Rasm qabul qilindi!*", parse_mode='Markdown')
    except Exception as e:
        await update.message.reply_text("⚠️ Rasm yuborishda xato. Qayta yuboring.")

async def davomat_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid   = update.effective_user.id
    today = today_str()
    if uid not in users:
        await update.message.reply_text("❌ Avval /start orqali ro'yxatdan o'ting!")
        return
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

    def run_bot():
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        conv = ConversationHandler(
            entry_points=[CommandHandler("start", start)],
            states={ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_name)]},
            fallbacks=[CommandHandler("start", start)],
        )

        application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        application.add_handler(conv)
        application.add_handler(CommandHandler("davomat", davomat_cmd))
        application.add_handler(CallbackQueryHandler(admin_callback, pattern="^admin_"))
        application.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, webapp_data))
        application.add_handler(MessageHandler(filters.PHOTO, receive_photo))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, admin_text))
        print("Bot ishga tushdi!")
        application.run_polling(
            allowed_updates=["message", "callback_query", "web_app_data"],
            stop_signals=[]
        )

    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()

    print(f"Flask {port} portda ishga tushdi!")
    flask_app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
