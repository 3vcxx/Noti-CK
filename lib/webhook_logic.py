import json
from lib.telegram import send_message
from lib.storage import get_watchlist, add_to_watchlist, remove_from_watchlist, get_indicators_config, toggle_indicator
from lib.data import get_ohlcv
from lib.indicators import calculate_indicators, detect_signals

def do_webhook(handler):
    content_len = int(handler.headers.get('Content-Length', 0))
    post_body = handler.rfile.read(content_len)
    
    try:
        data = json.loads(post_body)
    except:
        handler.send_response(200)
        handler.end_headers()
        return
    
    if "message" not in data or "text" not in data["message"]:
        handler.send_response(200)
        handler.end_headers()
        return
    
    chat_id = data["message"]["chat"]["id"]
    text = data["message"]["text"].strip()
    parts = text.split()
    cmd = parts[0].lower()
    
    if cmd == "/start":
        send_message("""🤖 <b>Stock Alert Bot</b>

<b>Lệnh có sẵn:</b>
/add SYMBOL — Thêm mã vào watchlist
/del SYMBOL — Xóa mã khỏi watchlist
/list — Xem danh sách đang theo dõi
/check SYMBOL — Check chỉ báo 1 mã ngay
/indicators — Xem cấu hình chỉ báo
/on INDICATOR — Bật chỉ báo (vd: /on MACD)
/off INDICATOR — Tắt chỉ báo
/help — Trợ giúp

⏰ Bot tự động quét mỗi giờ trong giờ giao dịch.""")
    
    elif cmd == "/help":
        send_message("📋 <b>Trợ giúp</b>\n\nGõ /add VCB để thêm VCB vào danh sách theo dõi.\nGõ /check VCB để kiểm tra chỉ báo ngay lập tức.\nGõ /list để xem tất cả mã đang theo dõi.")
    
    elif cmd == "/list":
        wl = get_watchlist()
        msg = f"📋 <b>Watchlist</b> ({len(wl)} mã):\n" + "\n".join([f"• {s}" for s in wl])
        send_message(msg)
    
    elif cmd == "/add" and len(parts) > 1:
        symbol = parts[1].upper()
        add_to_watchlist(symbol)
        send_message(f"✅ Đã thêm <b>{symbol}</b> vào watchlist.")
    
    elif cmd == "/del" and len(parts) > 1:
        symbol = parts[1].upper()
        remove_from_watchlist(symbol)
        send_message(f"🗑️ Đã xóa <b>{symbol}</b> khỏi watchlist.")
    
    elif cmd == "/check" and len(parts) > 1:
        symbol = parts[1].upper()
        try:
            df = get_ohlcv(symbol, resolution="1H", days_back=60)
            if df is None or len(df) < 200:
                send_message(f"❌ Không đủ dữ liệu cho <b>{symbol}</b>")
            else:
                df = calculate_indicators(df)
                config = get_indicators_config()
                signals = detect_signals(df, symbol, config)
                latest = df.iloc[-1]
                
                lines = [
                    f"📊 <b>{symbol}</b>",
                    f"Giá: <b>{latest['close']:,.0f}</b>",
                    f"MA20: {latest['MA20']:,.0f} | MA50: {latest['MA50']:,.0f} | MA200: {latest['MA200']:,.0f}",
                    f"MACD: {latest['MACD']:.3f} | Signal: {latest['MACD_SIGNAL']:.3f}",
                    f"RSI: {latest['RSI']:.1f}",
                    f"Volume: {latest['volume']:,.0f}",
                ]
                
                if signals:
                    lines.append(f"\n🔔 <b>{len(signals)} tín hiệu phát hiện:</b>")
                    for s in signals:
                        lines.append(f"{s['emoji']} {s['type']}")
                else:
                    lines.append("\n✅ Không có tín hiệu đặc biệt.")
                
                send_message("\n".join(lines))
        except Exception as e:
            send_message(f"❌ Lỗi check {symbol}: {str(e)}")
    
    elif cmd == "/indicators":
        cfg = get_indicators_config()
        lines = ["⚙️ <b>Cấu hình chỉ báo:</b>"]
        for k, v in cfg.items():
            lines.append(f"{'🟢' if v else '🔴'} {k}: {'BẬT' if v else 'TẮT'}")
        send_message("\n".join(lines))
    
    elif cmd == "/on" and len(parts) > 1:
        toggle_indicator(parts[1].upper(), True)
        send_message(f"🟢 Đã bật chỉ báo <b>{parts[1].upper()}</b>")
    
    elif cmd == "/off" and len(parts) > 1:
        toggle_indicator(parts[1].upper(), False)
        send_message(f"🔴 Đã tắt chỉ báo <b>{parts[1].upper()}</b>")
    
    else:
        send_message(f"Không hiểu lệnh: <b>{text}</b>\nGõ /help để xem hướng dẫn.")
    
    handler.send_response(200)
    handler.end_headers()
