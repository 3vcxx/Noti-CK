from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json
import os
import traceback
import requests
import redis
from datetime import datetime, timedelta

# ============ CONFIG ============
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
REDIS_URL = os.environ.get("REDIS_URL")
CRON_SECRET = os.environ.get("CRON_SECRET")

DEFAULT_WATCHLIST = ["VCB", "VIC", "VNM", "FPT", "HPG", "GAS", "GVR", "SSI", "MSN", "MWG"]
BASE_URL = "https://api.24hmoney.vn/trading-view/api/public/history"

# ============ REDIS HELPERS ============
def _get_redis():
    if not REDIS_URL:
        raise ValueError("REDIS_URL not set")
    return redis.from_url(REDIS_URL, decode_responses=True)

def get_watchlist():
    try:
        r = _get_redis()
        items = r.smembers("watchlist")
        return sorted(list(items)) if items else DEFAULT_WATCHLIST.copy()
    except Exception:
        return DEFAULT_WATCHLIST.copy()

def add_to_watchlist(symbol):
    try:
        _get_redis().sadd("watchlist", symbol.upper())
    except Exception:
        pass

def remove_from_watchlist(symbol):
    try:
        _get_redis().srem("watchlist", symbol.upper())
    except Exception:
        pass

def already_alerted(symbol, signal_type):
    try:
        key = f"alert:{datetime.now().strftime('%Y%m%d')}:{symbol}:{signal_type}"
        return _get_redis().exists(key) == 1
    except Exception:
        return False

def save_alert(symbol, signal_type, ttl_hours=24):
    try:
        key = f"alert:{datetime.now().strftime('%Y%m%d')}:{symbol}:{signal_type}"
        _get_redis().setex(key, ttl_hours * 3600, "1")
    except Exception:
        pass

def get_indicators_config():
    try:
        default = {"MA200": "1", "MACD": "1", "RSI": "1", "VOLUME": "1", "GOLDEN_CROSS": "1"}
        stored = _get_redis().hgetall("indicators_config")
        merged = {**default, **stored}
        return {k: v == "1" for k, v in merged.items()}
    except Exception:
        return {"MA200": True, "MACD": True, "RSI": True, "VOLUME": True, "GOLDEN_CROSS": True}

def toggle_indicator(name, enabled):
    try:
        _get_redis().hset("indicators_config", name.upper(), "1" if enabled else "0")
    except Exception:
        pass

# ============ DATA ============
def get_ohlcv(symbol, resolution="1H", days_back=60):
    end = int(datetime.now().timestamp())
    start = int((datetime.now() - timedelta(days=days_back)).timestamp())
    url = f"{BASE_URL}?symbol={symbol}&resolution={resolution}&from={start}&to={end}&countback=500"
    
    resp = requests.get(url, timeout=10, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    })
    resp.raise_for_status()
    data = resp.json()
    
    if data.get("s") != "ok" or not data.get("t"):
        return None
    
    candles = []
    for i in range(len(data["t"])):
        candles.append({
            "time": data["t"][i],
            "open": float(data["o"][i]),
            "high": float(data["h"][i]),
            "low": float(data["l"][i]),
            "close": float(data["c"][i]),
            "volume": int(data["v"][i])
        })
    return candles

# ============ INDICATORS ============
def _sma(values, window):
    result = []
    for i in range(len(values)):
        if i < window - 1:
            result.append(None)
        else:
            result.append(sum(values[i-window+1:i+1]) / window)
    return result

def _ema(values, window):
    k = 2 / (window + 1)
    result = []
    for i in range(len(values)):
        if i == 0:
            result.append(values[0])
        else:
            result.append(values[i] * k + result[i-1] * (1 - k))
    return result

def calculate_indicators(candles):
    closes = [c["close"] for c in candles]
    volumes = [c["volume"] for c in candles]
    n = len(candles)
    
    ma20 = _sma(closes, 20)
    ma50 = _sma(closes, 50)
    ma200 = _sma(closes, 200)
    
    ema12 = _ema(closes, 12)
    ema26 = _ema(closes, 26)
    macd = [ema12[i] - ema26[i] for i in range(n)]
    macd_signal = _ema(macd, 9)
    macd_hist = [macd[i] - macd_signal[i] for i in range(n)]
    
    rsi = [None] * n
    gains = []
    losses = []
    for i in range(1, n):
        diff = closes[i] - closes[i-1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    
    for i in range(14, n):
        avg_gain = sum(gains[i-14:i]) / 14
        avg_loss = sum(losses[i-14:i]) / 14
        if avg_loss == 0:
            rsi[i] = 100
        else:
            rsi[i] = 100 - (100 / (1 + avg_gain / avg_loss))
    
    vol_ma20 = _sma(volumes, 20)
    
    for i in range(n):
        candles[i]["MA20"] = ma20[i]
        candles[i]["MA50"] = ma50[i]
        candles[i]["MA200"] = ma200[i]
        candles[i]["MACD"] = macd[i]
        candles[i]["MACD_SIGNAL"] = macd_signal[i]
        candles[i]["MACD_HIST"] = macd_hist[i]
        candles[i]["RSI"] = rsi[i]
        candles[i]["VOL_MA20"] = vol_ma20[i]
    
    return candles

def detect_signals(candles, symbol, config=None):
    if config is None:
        config = {"MA200": True, "MACD": True, "RSI": True, "VOLUME": True, "GOLDEN_CROSS": True}
    if len(candles) < 3:
        return []
    
    prev = candles[-2]
    curr = candles[-1]
    signals = []
    
    if config.get("MA200") and prev.get("MA200") and curr.get("MA200"):
        if prev["close"] < prev["MA200"] and curr["close"] > curr["MA200"]:
            signals.append({
                "symbol": symbol, "type": "PRICE_ABOVE_MA200", "emoji": "🚀",
                "text": f"<b>{symbol}</b> giá <b>{curr['close']:,.0f}</b> vừa <b>CẮT LÊN</b> MA200 ({curr['MA200']:,.0f})"
            })
    
    if config.get("MACD") and prev.get("MACD") and curr.get("MACD"):
        if prev["MACD"] < prev["MACD_SIGNAL"] and curr["MACD"] > curr["MACD_SIGNAL"] and curr["MACD"] < 0:
            signals.append({
                "symbol": symbol, "type": "MACD_CROSS_ABOVE", "emoji": "💚",
                "text": f"<b>{symbol}</b> MACD cắt lên Signal từ vùng âm ({curr['MACD']:.3f})"
            })
    
    if config.get("RSI") and prev.get("RSI") and curr.get("RSI"):
        if prev["RSI"] < 30 and curr["RSI"] > 30:
            signals.append({
                "symbol": symbol, "type": "RSI_EXIT_OVERSOLD", "emoji": "🔥",
                "text": f"<b>{symbol}</b> RSI thoát vùng quá bán: <b>{curr['RSI']:.1f}</b>"
            })
    
    if config.get("VOLUME") and curr.get("VOL_MA20") and curr["VOL_MA20"] and curr["VOL_MA20"] > 0:
        if curr["volume"] > 2.5 * curr["VOL_MA20"]:
            ratio = curr["volume"] / curr["VOL_MA20"]
            signals.append({
                "symbol": symbol, "type": "VOLUME_SPIKE", "emoji": "📊",
                "text": f"<b>{symbol}</b> Volume bùng nổ: <b>{ratio:.1f}x</b> TB20"
            })
    
    if config.get("GOLDEN_CROSS") and prev.get("MA50") and curr.get("MA50") and prev.get("MA200") and curr.get("MA200"):
        if prev["MA50"] < prev["MA200"] and curr["MA50"] > curr["MA200"]:
            signals.append({
                "symbol": symbol, "type": "GOLDEN_CROSS", "emoji": "👑",
                "text": f"<b>{symbol}</b> <b>GOLDEN CROSS</b>: MA50 cắt lên MA200"
            })
    
    return signals

# ============ TELEGRAM ============
def send_message(text):
    if not TOKEN or not CHAT_ID:
        print("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID")
        return False
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try:
        resp = requests.post(url, json={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}, timeout=10)
        return resp.status_code == 200
    except Exception as e:
        print(f"Telegram error: {e}")
        return False

def send_alert(symbol, signal):
    msg = f"{signal['emoji']} <b>CẢNH BÁO KỸ THUẬT</b> {signal['emoji']}\n\n{signal['text']}\n\n⏰ {datetime.now().strftime('%H:%M %d/%m/%Y')}"
    send_message(msg)

# ============ HANDLER ============
class handler(BaseHTTPRequestHandler):
    def _json(self, status, data):
        self.send_response(status)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))
    
    def do_GET(self):
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
                    lines.append(f"{'🟢' if v else '🔴'} {k}: {'BẬT' if v else 'TẮT'}")
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
