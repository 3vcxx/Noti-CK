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
    
    # RSI
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
            rs = avg_gain / avg_loss
            rsi[i] = 100 - (100 / (1 + rs))
    
    vol_ma20 = _sma(volumes, 20)
    
    # Gán lại vào candles
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
    
    if config.get("VOLUME") and curr.get("VOL_MA20") and curr["VOL_MA20"] > 0:
        if curr["volume"] > 2.5 * curr["VOL_MA20"]:
            ratio = curr["volume"] / curr["VOL_MA20"]
            signals.append({
                "symbol": symbol, "type": "VOLUME_SPIKE", "emoji": "📊",
                "text": f"<b>{symbol}</b> Volume bùng nổ: <b>{ratio:.1f}x</b> TB20"
            })
    
    if config.get("GOLDEN_CROSS") and prev.get("MA50") and curr.get("MA50"):
        if prev["MA50"] < prev["MA200"] and curr["MA50"] > curr["MA200"]:
            signals.append({
                "symbol": symbol, "type": "GOLDEN_CROSS", "emoji": "👑",
                "text": f"<b>{symbol}</b> <b>GOLDEN CROSS</b>: MA50 cắt lên MA200"
            })
    
    return signals
