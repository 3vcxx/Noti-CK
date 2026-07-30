from http.server import BaseHTTPRequestHandler
import json
import os

from lib.data import get_ohlcv
from lib.indicators import calculate_indicators, detect_signals
from lib.storage import already_alerted, save_alert
from lib.telegram import send_alert

# Danh sách mã theo dõi (có thể lưu trong Redis hoặc hardcode)
WATCHLIST = ["VCB", "VIC", "VNM", "FPT", "HPG", "GAS", "GVR", "SSI", "MSN", "MWG"]

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        alerts_sent = 0
        errors = []
        
        for symbol in WATCHLIST:
            try:
                # Lấy 60 ngày dữ liệu 1H (~360 nến, đủ cho MA200 trên 1H)
                df = get_ohlcv(symbol, resolution="1H", days_back=60)
                if df is None or len(df) < 200:
                    continue
                
                df = calculate_indicators(df)
                signals = detect_signals(df, symbol)
                
                for sig in signals:
                    if not already_alerted(symbol, sig["type"]):
                        send_alert(symbol, sig)
                        save_alert(symbol, sig["type"])
                        alerts_sent += 1
                        
            except Exception as e:
                errors.append(f"{symbol}: {str(e)}")
        
        # Response cho Vercel Cron (không quan trọng lắm)
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({
            "ok": True,
            "alerts_sent": alerts_sent,
            "errors": errors
        }).encode())
