import json
from lib.telegram import send_message

def do_webhook(handler):
    content_len = int(handler.headers.get('Content-Length', 0))
    post_body = handler.rfile.read(content_len)
    
    try:
        data = json.loads(post_body)
    except:
        handler.send_response(200)
        handler.end_headers()
        return
    
    if "message" in data and "text" in data["message"]:
        text = data["message"]["text"]
        
        if text == "/start":
            send_message("🤖 Bot cảnh báo chứng khoán đã sẵn sàng!\n\nLệnh:\n/add SYMBOL — thêm mã\n/list — xem danh sách\n/help — trợ giúp")
        elif text == "/help":
            send_message("📋 Hỗ trợ:\n• /add VCB — thêm VCB\n• /list — xem watchlist\n• Bot tự check 1h/lần 9h-15h")
        else:
            send_message(f"Nhận lệnh: {text}")
    
    handler.send_response(200)
    handler.end_headers()
