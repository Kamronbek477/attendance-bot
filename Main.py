# main.py — bot va webapp ni bir vaqtda ishga tushiradi
import threading
import os
from webapp import app as flask_app
from bot import main as bot_main

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    flask_app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    # Flask ni alohida threadda ishga tushir
    t = threading.Thread(target=run_flask, daemon=True)
    t.start()
    # Botni asosiy threadda ishga tushir
    bot_main()