import os
import redis
from datetime import datetime

REDIS_URL = os.environ.get("REDIS_URL")

def get_redis():
    if not REDIS_URL:
        raise ValueError("REDIS_URL not set")
    return redis.from_url(REDIS_URL, decode_responses=True)

def already_alerted(symbol: str, signal_type: str) -> bool:
    r = get_redis()
    key = f"alert:{datetime.now().strftime('%Y%m%d')}:{symbol}:{signal_type}"
    return r.exists(key) == 1

def save_alert(symbol: str, signal_type: str, ttl_hours: int = 24):
    r = get_redis()
    key = f"alert:{datetime.now().strftime('%Y%m%d')}:{symbol}:{signal_type}"
    r.setex(key, ttl_hours * 3600, "1")

# === WATCHLIST ===
DEFAULT_WATCHLIST = ["VCB", "VIC", "VNM", "FPT", "HPG", "GAS", "GVR", "SSI", "MSN", "MWG"]

def get_watchlist() -> list:
    r = get_redis()
    items = r.smembers("watchlist")
    return sorted(list(items)) if items else DEFAULT_WATCHLIST.copy()

def add_to_watchlist(symbol: str):
    r = get_redis()
    r.sadd("watchlist", symbol.upper())

def remove_from_watchlist(symbol: str):
    r = get_redis()
    r.srem("watchlist", symbol.upper())

def get_indicators_config() -> dict:
    """Lấy cấu hình chỉ báo đang bật"""
    r = get_redis()
    default = {"MA200": True, "MACD": True, "RSI": True, "VOLUME": True, "GOLDEN_CROSS": True}
    stored = r.hgetall("indicators_config")
    return {**default, **stored} if stored else default

def toggle_indicator(name: str, enabled: bool):
    r = get_redis()
    r.hset("indicators_config", name, "1" if enabled else "0")
