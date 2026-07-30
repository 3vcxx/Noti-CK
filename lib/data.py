import requests
from datetime import datetime, timedelta

BASE_URL = "https://api.24hmoney.vn/trading-view/api/public/history"

def get_ohlcv(symbol: str, resolution: str = "1H", days_back: int = 60):
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
    
    # Trả về list dict (không dùng pandas)
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
