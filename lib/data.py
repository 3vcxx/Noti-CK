import requests
import pandas as pd
from datetime import datetime, timedelta

BASE_URL = "https://api.24hmoney.vn/trading-view/api/public/history"

def get_ohlcv(symbol: str, resolution: str = "1H", days_back: int = 60):
    """
    Lấy dữ liệu nến từ 24hmoney.
    resolution: 1, 5, 15, 30, 1H, 1D, 1W, 1M
    """
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
    
    df = pd.DataFrame({
        "time": pd.to_datetime(data["t"], unit="s"),
        "open": data["o"],
        "high": data["h"],
        "low": data["l"],
        "close": data["c"],
        "volume": data["v"]
    })
    return df.sort_values("time").reset_index(drop=True)
