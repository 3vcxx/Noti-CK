from http.server import BaseHTTPRequestHandler
import json
import os
from lib.telegram import send_message

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_len = int(self.headers.get('Content-Length', 0))
        post_body = self.rfile.read(content_len)
        data = json.loads(post_body)
        
        if "message" in data and "text" in data["message"]:
            chat_id = data["message"]["chat"]["id"]
            text = data["message"]["text"]
            
            if text == "/start":
                send_message("🤖 Bot cảnh báo chứng khoán đã sẵn sàng!\n\nLệnh:\n/add SYMBOL — thêm mã\n/list — xem danh sách\n/help — trợ giúp")
            elif text == "/help":
                send_message("📋 Hỗ trợ:\n• /add VCB — thêm VCB\n• /list — xem watchlist\n• Bot tự check 1h/lần 9h-15h")
            else:
                send_message(f"Nhận lệnh: {text}")
        
        self.send_response(200)
        self.end_headers()
