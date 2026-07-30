import os
import redis
from datetime import datetime

# Lấy từ Vercel Environment Variables
REDIS_URL = os.environ.get("REDIS_URL")  # format: redis://default:pass@host:port

def get_redis():
    if not REDIS_URL:
        raise ValueError("REDIS_URL not set")
    return redis.from_url(REDIS_URL, decode_responses=True)

def already_alerted(symbol: str, signal_type: str) -> bool:
    """Kiểm tra đã cảnh báo tín hiệu này hôm nay chưa"""
    r = get_redis()
    key = f"alert:{datetime.now().strftime('%Y%m%d')}:{symbol}:{signal_type}"
    return r.exists(key) == 1

def save_alert(symbol: str, signal_type: str, ttl_hours: int = 24):
    """Đánh dấu đã cảnh báo, tự xóa sau 24h"""
    r = get_redis()
    key = f"alert:{datetime.now().strftime('%Y%m%d')}:{symbol}:{signal_type}"
    r.setex(key, ttl_hours * 3600, "1")
