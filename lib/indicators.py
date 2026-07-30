import pandas as pd
import numpy as np

def calculate_indicators(df: pd.DataFrame):
    df = df.copy()
    
    # Moving Averages
    df["MA20"] = df["close"].rolling(window=20).mean()
    df["MA50"] = df["close"].rolling(window=50).mean()
    df["MA200"] = df["close"].rolling(window=200).mean()
    
    # MACD
    ema12 = df["close"].ewm(span=12, adjust=False).mean()
    ema26 = df["close"].ewm(span=26, adjust=False).mean()
    df["MACD"] = ema12 - ema26
    df["MACD_SIGNAL"] = df["MACD"].ewm(span=9, adjust=False).mean()
    df["MACD_HIST"] = df["MACD"] - df["MACD_SIGNAL"]
    
    # RSI
    delta = df["close"].diff()
    gain = delta.where(delta > 0, 0).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df["RSI"] = 100 - (100 / (1 + rs))
    
    # Volume MA
    df["VOL_MA20"] = df["volume"].rolling(window=20).mean()
    
    return df

def detect_signals(df: pd.DataFrame, symbol: str) -> list:
    """Phát hiện tín hiệu từ 2 nến gần nhất"""
    if len(df) < 3:
        return []
    
    signals = []
    prev = df.iloc[-2]
    curr = df.iloc[-1]
    
    # 1. Giá cắt lên MA200
    if prev["close"] < prev["MA200"] and curr["close"] > curr["MA200"]:
        signals.append({
            "type": "PRICE_ABOVE_MA200",
            "emoji": "🚀",
            "text": f"<b>{symbol}</b> giá <b>{curr['close']:,.0f}</b> vừa <b>CẮT LÊN</b> MA200 ({curr['MA200']:,.0f})"
        })
    
    # 2. MACD cắt lên Signal từ âm
    if (prev["MACD"] < prev["MACD_SIGNAL"] and 
        curr["MACD"] > curr["MACD_SIGNAL"] and 
        curr["MACD"] < 0):
        signals.append({
            "type": "MACD_CROSS_ABOVE",
            "emoji": "💚",
            "text": f"<b>{symbol}</b> MACD cắt lên Signal từ vùng âm ({curr['MACD']:.3f})"
        })
    
    # 3. RSI thoát quá bán
    if prev["RSI"] < 30 and curr["RSI"] > 30:
        signals.append({
            "type": "RSI_EXIT_OVERSOLD",
            "emoji": "🔥",
            "text": f"<b>{symbol}</b> RSI thoát vùng quá bán: <b>{curr['RSI']:.1f}</b>"
        })
    
    # 4. Volume spike
    if curr["volume"] > 2.5 * curr["VOL_MA20"]:
        ratio = curr["volume"] / curr["VOL_MA20"] if curr["VOL_MA20"] > 0 else 0
        signals.append({
            "type": "VOLUME_SPIKE",
            "emoji": "📊",
            "text": f"<b>{symbol}</b> Volume bùng nổ: <b>{ratio:.1f}x</b> TB20"
        })
    
    # 5. Golden Cross MA50 cắt lên MA200
    if prev["MA50"] < prev["MA200"] and curr["MA50"] > curr["MA200"]:
        signals.append({
            "type": "GOLDEN_CROSS",
            "emoji": "👑",
            "text": f"<b>{symbol}</b> <b>GOLDEN CROSS</b>: MA50 cắt lên MA200"
        })
    
    return signals
