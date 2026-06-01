<<<<<<< HEAD
# Davomat Mini App Bot

## Fayllar
- `bot.py` — Telegram bot
- `webapp.py` — GPS oluvchi mini app (Flask)
- `main.py` — ikkalasini birga ishga tushiradi
- `requirements.txt` — kutubxonalar
- `Procfile` — Railway uchun

---

## Railway ga deploy qilish (bepul)

### 1. GitHub ga yuklang
```bash
git init
git add .
git commit -m "first commit"
git branch -M main
git remote add origin https://github.com/SIZNING_USERNAME/attendance-bot.git
git push -u origin main
```

### 2. Railway.app
1. https://railway.app ga kiring → "Start a New Project"
2. "Deploy from GitHub repo" → repongizni tanlang
3. "Variables" bo'limiga o'ting va quyidagilarni kiriting:

| Variable | Qiymat |
|----------|--------|
| TELEGRAM_BOT_TOKEN | @BotFather dan |
| ADMIN_ID | @userinfobot dan |
| OFFICE_LAT | 41.2995 (ofis koordinatasi) |
| OFFICE_LON | 69.2401 |
| OFFICE_NAME | Bosh ofis |
| ALLOWED_RADIUS_M | 100 |
| WORK_START_HOUR | 9 |
| WORK_START_MIN | 0 |

4. "Settings" → "Domains" → "Generate Domain" → URL ni nusxalab oling
5. Shu URL ni WEBAPP_URL variable ga kiriting:
   `WEBAPP_URL=https://your-app.railway.app`

### 3. BotFather da Web App sozlash
1. @BotFather ga yozing
2. `/setmenubutton` → botingizni tanlang
3. URL: `https://your-app.railway.app/checkin`

---

## Xodim uchun
1. Botga `/start` → "✅ Ishga keldim" tugmasi
2. Tugmani bosadi → mini app ochiladi
3. "Ishga keldim" bosiladi → GPS avtomatik olinadi
4. 100m ichida bo'lsa ✅ tasdiqlanadi

## Admin uchun
- "Bugungi davomat" → kim kelgan, qaysi vaqtda
- "Ofis lokatsiyasini o'rnatish" → koordinata yuborish (`LAT LON`)
=======
# attendance-bot
davomatdan otish uchun
>>>>>>> 8f9be7f1a96264db5c885310d2112212b2ef7cd8
