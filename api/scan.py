from http.server import BaseHTTPRequestHandler
import json
import os

from lib.data import get_ohlcv
from lib.indicators import calculate_indicators, detect_signals
from lib.storage import already_alerted, save_alert
from lib.telegram import send_alert

WATCHLIST = ["VCB", "VIC", "VNM", "FPT", "HPG", "GAS", "GVR", "SSI", "MSN", "MWG"]
CRON_SECRET = os.environ.get("CRON_SECRET")  # Thêm biến này

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # === BẢO VỆ: Kiểm tra secret key ===
        # URL gọi từ cron-job.org sẽ là:
        # https://your-app.vercel.app/api/scan?key=YOUR_SECRET
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        provided_key = params.get("key", [None])[0]
        
        if not CRON_SECRET or provided_key != CRON_SECRET:
            self.send_response(403)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Forbidden"}).encode())
            return
        
        # === CHẠY QUÉT ===
        alerts_sent = 0
        errors = []
        
        for symbol in WATCHLIST:
            try:
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
        
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({
            "ok": True,
            "alerts_sent": alerts_sent,
            "errors": errors,
            "checked_at": str(pd.Timestamp.now())
        }).encode())
