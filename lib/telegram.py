import os
import requests
from datetime import datetime

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

def send_message(text: str):
    if not TOKEN or not CHAT_ID:
        print("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID")
        return
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}, timeout=10)
    except Exception as e:
        print(f"Telegram error: {e}")

def send_alert(symbol: str, signal: dict):
    msg = f"{signal['emoji']} <b>CẢNH BÁO KỸ THUẬT</b> {signal['emoji']}\n\n{signal['text']}\n\n⏰ {datetime.now().strftime('%H:%M %d/%m/%Y')}"
    send_message(msg)
