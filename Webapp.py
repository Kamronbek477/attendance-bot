import os
from flask import Flask, render_template_string, request, jsonify

app = Flask(__name__)
WEBAPP_URL = os.environ.get("WEBAPP_URL", "https://YOUR_APP.railway.app")

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
    border-radius: 16px;
    padding: 28px 24px;
    text-align: center;
  }
  .icon { font-size: 56px; margin-bottom: 16px; }
  h1 { font-size: 22px; font-weight: 600; margin-bottom: 8px; }
  .sub { font-size: 14px; opacity: 0.6; margin-bottom: 28px; line-height: 1.5; }
  .btn {
    width: 100%;
    padding: 16px;
    border: none;
    border-radius: 12px;
    font-size: 16px;
    font-weight: 600;
    cursor: pointer;
    background: var(--tg-theme-button-color, #2481cc);
    color: var(--tg-theme-button-text-color, #fff);
    transition: opacity 0.2s;
  }
  .btn:disabled { opacity: 0.5; cursor: not-allowed; }
  .btn:active:not(:disabled) { opacity: 0.8; }
  .status {
    margin-top: 16px;
    font-size: 14px;
    min-height: 20px;
    opacity: 0.7;
  }
  .status.error { color: #e53935; opacity: 1; }
  .status.success { color: #43a047; opacity: 1; }
  .accuracy {
    margin-top: 8px;
    font-size: 12px;
    opacity: 0.5;
  }
  .spinner {
    display: inline-block;
    width: 18px; height: 18px;
    border: 2px solid rgba(255,255,255,0.4);
    border-top-color: #fff;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
    vertical-align: middle;
    margin-right: 8px;
  }
  @keyframes spin { to { transform: rotate(360deg); } }
</style>
</head>
<body>
<div class="card">
  <div class="icon" id="icon">📍</div>
  <h1 id="title">Davomat tasdiqlash</h1>
  <p class="sub" id="sub">Tugmani bosing — joylashuvingiz avtomatik aniqlanadi va ofisga masofangiz tekshiriladi.</p>
  <button class="btn" id="btn" onclick="checkin()">✅ Ishga keldim</button>
  <div class="status" id="status"></div>
  <div class="accuracy" id="accuracy"></div>
</div>

<script>
const tg = window.Telegram.WebApp;
tg.ready();
tg.expand();

function setStatus(msg, type) {
  const el = document.getElementById('status');
  el.textContent = msg;
  el.className = 'status ' + (type || '');
}

function checkin() {
  const btn = document.getElementById('btn');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span>Joylashuv aniqlanmoqda...';
  setStatus('');
  document.getElementById('accuracy').textContent = '';

  if (!navigator.geolocation) {
    btn.disabled = false;
    btn.textContent = '✅ Ishga keldim';
    setStatus('❌ Brauzeringiz GPS ni qollab-quvvatlamaydi', 'error');
    return;
  }

  navigator.geolocation.getCurrentPosition(
    function(pos) {
      const lat = pos.coords.latitude;
      const lon = pos.coords.longitude;
      const acc = Math.round(pos.coords.accuracy);

      document.getElementById('accuracy').textContent = 'Aniqlik: ±' + acc + ' metr';

      // GPS aniqlik juda past bo'lsa ogohlantirish
      if (acc > 200) {
        setStatus('⚠️ GPS signali zaif. Tashqariga chiqib qayta urining.', 'error');
        btn.disabled = false;
        btn.textContent = '🔄 Qayta urinish';
        return;
      }

      // Ma'lumotni botga yuborish
      tg.sendData(JSON.stringify({ lat: lat, lon: lon, accuracy: acc }));
    },
    function(err) {
      btn.disabled = false;
      btn.textContent = '🔄 Qayta urinish';
      const msgs = {
        1: '❌ GPS ruxsati berilmagan. Telefon sozlamalaridan ruxsat bering.',
        2: '❌ Joylashuv aniqlanmadi. Tashqariga chiqib qayta urining.',
        3: '❌ Vaqt tugadi. Qayta urinib ko\'ring.'
      };
      setStatus(msgs[err.code] || '❌ GPS xatosi', 'error');
    },
    {
      enableHighAccuracy: true,
      timeout: 15000,
      maximumAge: 0
    }
  );
}
</script>
</body>
</html>"""

@app.route("/checkin")
def checkin_page():
    return render_template_string(HTML)

@app.route("/health")
def health():
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)