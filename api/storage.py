import os
import redis
from datetime import datetime

REDIS_URL = os.environ.get("REDIS_URL")

def _get_redis():
    if not REDIS_URL:
        raise ValueError("REDIS_URL not set")
    return redis.from_url(REDIS_URL, decode_responses=True)

DEFAULT_WATCHLIST = ["VCB", "VIC", "VNM", "FPT", "HPG", "GAS", "GVR", "SSI", "MSN", "MWG"]

def get_watchlist():
    try:
        r = _get_redis()
        items = r.smembers("watchlist")
        return sorted(list(items)) if items else DEFAULT_WATCHLIST.copy()
    except:
        return DEFAULT_WATCHLIST.copy()

def add_to_watchlist(symbol):
    try:
        r = _get_redis()
        r.sadd("watchlist", symbol.upper())
    except:
        pass

def remove_from_watchlist(symbol):
    try:
        r = _get_redis()
        r.srem("watchlist", symbol.upper())
    except:
        pass

def already_alerted(symbol, signal_type):
    try:
        r = _get_redis()
        key = f"alert:{datetime.now().strftime('%Y%m%d')}:{symbol}:{signal_type}"
        return r.exists(key) == 1
    except:
        return False

def save_alert(symbol, signal_type, ttl_hours=24):
    try:
        r = _get_redis()
        key = f"alert:{datetime.now().strftime('%Y%m%d')}:{symbol}:{signal_type}"
        r.setex(key, ttl_hours * 3600, "1")
    except:
        pass

def get_indicators_config():
    try:
        r = _get_redis()
        default = {"MA200": "1", "MACD": "1", "RSI": "1", "VOLUME": "1", "GOLDEN_CROSS": "1"}
        stored = r.hgetall("indicators_config")
        merged = {**default, **stored}
        return {k: v == "1" for k, v in merged.items()}
    except:
        return {"MA200": True, "MACD": True, "RSI": True, "VOLUME": True, "GOLDEN_CROSS": True}

def toggle_indicator(name, enabled):
    try:
        r = _get_redis()
        r.hset("indicators_config", name.upper(), "1" if enabled else "0")
    except:
        pass
