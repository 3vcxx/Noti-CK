from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json
import os
import traceback

# === Try-except bao toàn bộ import để debug ===
_IMPORT_ERROR = None
try:
    from data import get_ohlcv
    from indicators import calculate_indicators, detect_signals
    from storage import (
        get_watchlist, add_to_watchlist, remove_from_watchlist,
        already_alerted, save_alert, get_indicators_config, toggle_indicator
    )
    from telegram import send_message, send_alert
except Exception as e:
    _IMPORT_ERROR = traceback.format_exc()

CRON_SECRET = os.environ.get("CRON_SECRET")

class handler(BaseHTTPRequestHandler):
    def _json(self, status, data):
        self.send_response(status)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))
    
    def do_GET(self):
        # Nếu import lỗi, trả về ngay để debug
        if _IMPORT_ERROR:
            self._json(500, {"error": "Import failed", "detail": _IMPORT_ERROR})
            return
        
        parsed = urlparse(self.path)
        path = parsed.path.rstrip('/')
        params = parse_qs(parsed.query)
        
        if path in ["/api/index", ""]:
            action = params.get("action", ["scan"])[0]
            
            if action == "scan":
                self._do_scan(params)
            elif action == "check":
                self._do_check(params)
            else:
                self._json(400, {"error": "Unknown action. Use ?action=scan or ?action=check&symbol=VCB"})
        else:
            self._json(404, {"error": "Not found", "path": path})
    
    def do_POST(self):
        if _IMPORT_ERROR:
            self._json(500, {"error": "Import failed", "detail": _IMPORT_ERROR})
            return
        
        parsed = urlparse(self.path)
        path = parsed.path.rstrip('/')
        
        if path in ["/api/index", ""]:
            self._do_webhook()
        else:
            self._json(404, {"error": "Not found"})
    
    def _do_scan(self, params):
        provided_key = params.get("key", [None])[0]
        if CRON_SECRET and provided_key != CRON_SECRET:
            self._json(403, {"error": "Forbidden - wrong key"})
            return
        
        watchlist = get_watchlist()
        config = get_indicators_config()
        alerts_sent = 0
        errors = []
        all_signals = []
        
        for symbol in watchlist:
            try:
                candles = get_ohlcv(symbol, resolution="1H", days_back=60)
                if candles is None or len(candles) < 200:
                    continue
                
                candles = calculate_indicators(candles)
                signals = detect_signals(candles, symbol, config)
                all_signals.extend(signals)
                
                for sig in signals:
                    if not already_alerted(symbol, sig["type"]):
                        send_alert(symbol, sig)
                        save_alert(symbol, sig["type"])
                        alerts_sent += 1
            except Exception as e:
                errors.append(f"{symbol}: {str(e)}")
        
        self._json(200, {
            "ok": True,
            "watchlist": watchlist,
            "alerts_sent": alerts_sent,
            "total_signals": len(all_signals),
            "signals": [{"symbol": s.get("symbol"), "type": s["type"]} for s in all_signals],
            "errors": errors
        })
    
    def _do_check(self, params):
        symbol = params.get("symbol", [None])[0]
        if not symbol:
            self._json(400, {"error": "Thiếu ?symbol=VCB"})
            return
        
        try:
            candles = get_ohlcv(symbol.upper(), resolution="1H", days_back=60)
            if candles is None or len(candles) < 200:
                self._json(404, {"error": f"Không đủ dữ liệu cho {symbol}"})
                return
            
            candles = calculate_indicators(candles)
            config = get_indicators_config()
            signals = detect_signals(candles, symbol.upper(), config)
            latest = candles[-1]
            
            self._json(200, {
                "symbol": symbol.upper(),
                "price": round(latest["close"], 2),
                "ma20": round(latest["MA20"], 2) if latest.get("MA20") else None,
                "ma50": round(latest["MA50"], 2) if latest.get("MA50") else None,
                "ma200": round(latest["MA200"], 2) if latest.get("MA200") else None,
                "macd": round(latest["MACD"], 3) if latest.get("MACD") else None,
                "macd_signal": round(latest["MACD_SIGNAL"], 3) if latest.get("MACD_SIGNAL") else None,
                "rsi": round(latest["RSI"], 1) if latest.get("RSI") else None,
                "volume": latest["volume"],
                "signals": signals,
                "signal_count": len(signals)
            })
        except Exception as e:
            self._json(500, {"error": str(e), "trace": traceback.format_exc()})
    
    def _do_webhook(self):
        content_len = int(self.headers.get('Content-Length', 0))
        post_body = self.rfile.read(content_len)
        
        try:
            data = json.loads(post_body)
        except:
            self.send_response(200)
            self.end_headers()
            return
        
        if "message" not in data or "text" not in data["message"]:
            self.send_response(200)
            self.end_headers()
            return
        
        text = data["message"]["text"].strip()
        parts = text.split()
        cmd = parts[0].lower()
        
        try:
            if cmd == "/start":
                send_message("""🤖 <b>Stock Alert Bot</b>

<b>Lệnh:</b>
/add SYMBOL — Thêm mã
/del SYMBOL — Xóa mã
/list — Xem watchlist
/check SYMBOL — Check chỉ báo ngay
/indicators — Cấu hình chỉ báo
/on INDICATOR — Bật
/off INDICATOR — Tắt
/help — Trợ giúp""")
            
            elif cmd == "/help":
                send_message("📋 Gõ /add VCB để thêm. Gõ /check VCB để kiểm tra. Gõ /list để xem danh sách.")
            
            elif cmd == "/list":
                wl = get_watchlist()
                msg = f"📋 <b>Watchlist</b> ({len(wl)} mã):\n" + "\n".join([f"• {s}" for s in wl])
                send_message(msg)
            
            elif cmd == "/add" and len(parts) > 1:
                add_to_watchlist(parts[1])
                send_message(f"✅ Đã thêm <b>{parts[1].upper()}</b>")
            
            elif cmd == "/del" and len(parts) > 1:
                remove_from_watchlist(parts[1])
                send_message(f"🗑️ Đã xóa <b>{parts[1].upper()}</b>")
            
            elif cmd == "/check" and len(parts) > 1:
                symbol = parts[1].upper()
                candles = get_ohlcv(symbol, resolution="1H", days_back=60)
                if not candles or len(candles) < 200:
                    send_message(f"❌ Không đủ dữ liệu <b>{symbol}</b>")
                else:
                    candles = calculate_indicators(candles)
                    config = get_indicators_config()
                    signals = detect_signals(candles, symbol, config)
                    latest = candles[-1]
                    
                    lines = [
                        f"📊 <b>{symbol}</b>",
                        f"Giá: <b>{latest['close']:,.0f}</b>",
                        f"MA20: {latest.get('MA20',0):,.0f} | MA50: {latest.get('MA50',0):,.0f} | MA200: {latest.get('MA200',0):,.0f}",
                        f"MACD: {latest.get('MACD',0):.3f} | Signal: {latest.get('MACD_SIGNAL',0):.3f}",
                        f"RSI: {latest.get('RSI',0):.1f}",
                        f"Volume: {latest['volume']:,.0f}",
                    ]
                    if signals:
                        lines.append(f"\n🔔 <b>{len(signals)} tín hiệu:</b>")
                        for s in signals:
                            lines.append(f"{s['emoji']} {s['type']}")
                    else:
                        lines.append("\n✅ Không có tín hiệu.")
                    
                    send_message("\n".join(lines))
            
            elif cmd == "/indicators":
                cfg = get_indicators_config()
                lines = ["⚙️ <b>Chỉ báo:</b>"]
                for k, v in cfg.items():
                    lines.append(f"{'🟢' if v else '🔴'} {k}")
                send_message("\n".join(lines))
            
            elif cmd == "/on" and len(parts) > 1:
                toggle_indicator(parts[1].upper(), True)
                send_message(f"🟢 Bật <b>{parts[1].upper()}</b>")
            
            elif cmd == "/off" and len(parts) > 1:
                toggle_indicator(parts[1].upper(), False)
                send_message(f"🔴 Tắt <b>{parts[1].upper()}</b>")
            
            else:
                send_message(f"Không hiểu: <b>{text}</b>\nGõ /help")
        except Exception as e:
            send_message(f"❌ Lỗi: {str(e)}")
        
        self.send_response(200)
        self.end_headers()
