import json
import os
from urllib.parse import parse_qs, urlparse

from lib.data import get_ohlcv
from lib.indicators import calculate_indicators, detect_signals
from lib.storage import already_alerted, save_alert, get_watchlist, get_indicators_config
from lib.telegram import send_alert, send_message

CRON_SECRET = os.environ.get("CRON_SECRET")

def _check_secret(handler, params):
    provided_key = params.get("key", [None])[0]
    if CRON_SECRET and provided_key != CRON_SECRET:
        handler.send_response(403)
        handler.send_header('Content-type', 'application/json')
        handler.end_headers()
        handler.wfile.write(json.dumps({"error": "Forbidden - wrong key"}).encode())
        return False
    return True

def do_scan(handler, params):
    if not _check_secret(handler, params):
        return
    
    watchlist = get_watchlist()
    config = get_indicators_config()
    alerts_sent = 0
    errors = []
    all_signals = []
    
    for symbol in watchlist:
        try:
            df = get_ohlcv(symbol, resolution="1H", days_back=60)
            if df is None or len(df) < 200:
                continue
            
            df = calculate_indicators(df)
            signals = detect_signals(df, symbol, config)
            all_signals.extend(signals)
            
            for sig in signals:
                if not already_alerted(symbol, sig["type"]):
                    send_alert(symbol, sig)
                    save_alert(symbol, sig["type"])
                    alerts_sent += 1
                    
        except Exception as e:
            errors.append(f"{symbol}: {str(e)}")
    
    handler.send_response(200)
    handler.send_header('Content-type', 'application/json')
    handler.end_headers()
    handler.wfile.write(json.dumps({
        "ok": True,
        "watchlist": watchlist,
        "alerts_sent": alerts_sent,
        "total_signals": len(all_signals),
        "signals": [{"symbol": s.get("symbol"), "type": s["type"]} for s in all_signals],
        "errors": errors
    }, ensure_ascii=False).encode('utf-8'))

def do_check_symbol(handler, params):
    """Check 1 mã ngay lập tức, trả về JSON chi tiết"""
    symbol = params.get("symbol", [None])[0]
    if not symbol:
        handler.send_response(400)
        handler.send_header('Content-type', 'application/json')
        handler.end_headers()
        handler.wfile.write(json.dumps({"error": "Thiếu ?symbol=VCB"}).encode())
        return
    
    try:
        df = get_ohlcv(symbol.upper(), resolution="1H", days_back=60)
        if df is None or len(df) < 200:
            handler.send_response(404)
            handler.send_header('Content-type', 'application/json')
            handler.end_headers()
            handler.wfile.write(json.dumps({"error": f"Không đủ dữ liệu cho {symbol}"}).encode())
            return
        
        df = calculate_indicators(df)
        config = get_indicators_config()
        signals = detect_signals(df, symbol.upper(), config)
        
        latest = df.iloc[-1]
        
        handler.send_response(200)
        handler.send_header('Content-type', 'application/json')
        handler.end_headers()
        handler.wfile.write(json.dumps({
            "symbol": symbol.upper(),
            "price": round(latest["close"], 2),
            "ma20": round(latest["MA20"], 2) if pd.notna(latest["MA20"]) else None,
            "ma50": round(latest["MA50"], 2) if pd.notna(latest["MA50"]) else None,
            "ma200": round(latest["MA200"], 2) if pd.notna(latest["MA200"]) else None,
            "macd": round(latest["MACD"], 3) if pd.notna(latest["MACD"]) else None,
            "macd_signal": round(latest["MACD_SIGNAL"], 3) if pd.notna(latest["MACD_SIGNAL"]) else None,
            "rsi": round(latest["RSI"], 1) if pd.notna(latest["RSI"]) else None,
            "volume": int(latest["volume"]),
            "signals": signals,
            "signal_count": len(signals)
        }, ensure_ascii=False).encode('utf-8'))
        
    except Exception as e:
        handler.send_response(500)
        handler.send_header('Content-type', 'application/json')
        handler.end_headers()
        handler.wfile.write(json.dumps({"error": str(e)}).encode())
