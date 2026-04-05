import pandas as pd
import pytz
import requests
from datetime import datetime
import os
import time

# ==================== 最终固定配置 =====================
FEISHU_WEBHOOK = os.getenv("FEISHU_WEBHOOK")
BEIJING = pytz.timezone("Asia/Shanghai")
SYMBOLS = ["BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD", "DOGE-USD"]
TIMEFRAME = "15m"
ATR_LENGTH = 10
ATR_MULTI = 2.0

COIN_MAP = {
    "BTC-USD": "bitcoin",
    "ETH-USD": "ethereum",
    "SOL-USD": "solana",
    "BNB-USD": "binancecoin",
    "DOGE-USD": "dogecoin"
}

# ==================== 飞书推送 ====================
def send_signal_card(symbol, side, price, time_str):
    if not FEISHU_WEBHOOK:
        print("❌ 飞书WEBHOOK为空")
        return
    text = f"UT Bot\n**{symbol}** {'买入' if side == 'BUY' else '卖出'}\n价格：{price}\n时间：{time_str}"
    msg = {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": "🟢 买入信号" if side == "BUY" else "🔴 卖出信号"},
                "template": "green" if side == "BUY" else "red"
            },
            "elements": [{"tag": "div", "text": {"tag": "lark_md", "content": text}}]
        }
    }
    try:
        requests.post(FEISHU_WEBHOOK, json=msg, timeout=8)
        print(f"✅ {symbol} 信号推送")
    except:
        print(f"❌ {symbol} 推送失败")

def send_normal_msg(text):
    if not FEISHU_WEBHOOK:
        return
    msg = {
        "msg_type": "text",
        "content": {"text": f"UT Bot\n{text}"}
    }
    try:
        requests.post(FEISHU_WEBHOOK, json=msg, timeout=8)
    except:
        pass

# ==================== 全币种稳定K线获取（永不失败） ====================
def get_safe_klines(symbol, interval="15m"):
    for attempt in range(3):
        try:
            import yfinance as yf
            df = yf.Ticker(symbol).history(period="7d", interval=interval, timeout=6)
            if df is not None and len(df) >= 30:
                return df.dropna()
        except:
            time.sleep(1)
    try:
        coin_id = COIN_MAP[symbol]
        url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/ohlc"
        res = requests.get(url, params={"vs_currency": "usd", "days": 7}, timeout=10).json()
        df = pd.DataFrame(res, columns=["time", "open", "high", "low", "close"])
        df["Open"] = df["open"]
        df["High"] = df["high"]
        df["Low"] = df["low"]
        df["Close"] = df["close"]
        return df
    except:
        return None

# ==================== UT信号计算 ====================
def calculate_ut(df):
    try:
        high = df["High"]
        low = df["Low"]
        close = df["Close"]
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(ATR_LENGTH).mean()
        src = close
        sma = src.rolling(ATR_LENGTH).mean()
        upper = sma + ATR_MULTI * atr
        lower = sma - ATR_MULTI * atr

        trend = pd.Series(0.0, index=df.index)
        for i in range(1, len(df)):
            if src.iloc[i] > trend.iloc[i-1]:
                trend.iloc[i] = upper.iloc[i]
            elif src.iloc[i] < trend.iloc[i-1]:
                trend.iloc[i] = lower.iloc[i]
            else:
                trend.iloc[i] = trend.iloc[i-1]

        buy = (src.iloc[-2] > trend.iloc[-2]) & (src.iloc[-3] <= trend.iloc[-3])
        sell = (src.iloc[-2] < trend.iloc[-2]) & (src.iloc[-3] >= trend.iloc[-3])
        return buy, sell, round(close.iloc[-2], 4)
    except:
        return False, False, 0

# ==================== K线：阴阳 + 形态 ====================
def get_candle_info(df):
    try:
        o = df["Open"].iloc[-2]
        c = df["Close"].iloc[-2]
        h = df["High"].iloc[-2]
        l = df["Low"].iloc[-2]
        body = abs(c - o)
        range = h - l
        up_shadow = h - max(c, o)
        dn_shadow = min(c, o) - l

        candle_type = "阳线" if c >= o else "阴线"

        # K线形态判断
        if range == 0:
            shape = "十字星"
        elif body / range < 0.1:
            shape = "十字线"
        elif up_shadow / range > 0.6 and body / range < 0.2:
            shape = "流星线"
        elif dn_shadow / range > 0.6 and body / range < 0.2:
            shape = "锤子线"
        elif body / range > 0.8:
            shape = "大实体"
        elif up_shadow < body * 0.1 and dn_shadow > body * 0.8:
            shape = "看涨吞没"
        elif dn_shadow < body * 0.1 and up_shadow > body * 0.8:
            shape = "看跌吞没"
        else:
            shape = "常规K线"

        return f"{candle_type} | {shape}"
    except:
        return "获取失败"

# ==================== 主程序（最终版） ====================
now_str = datetime.now(BEIJING).strftime("%Y-%m-%d %H:%M:%S")
print(f"\n📊 [{now_str}] UT Bot 全币种稳定扫描")

for sym in SYMBOLS:
    try:
        df = get_safe_klines(sym, TIMEFRAME)
        if df is None or len(df) < 15:
            send_normal_msg(f"{sym}\n数据获取失败")
            continue

        buy, sell, price = calculate_ut(df)
        candle_info = get_candle_info(df)

        if buy or sell:
            send_signal_card(sym, "BUY" if buy else "SELL", price, now_str)
        else:
            send_normal_msg(f"{sym}\n无信号\nK线：{candle_info}")
            print(f"ℹ️ {sym} 无信号 | {candle_info}")

    except Exception as e:
        send_normal_msg(f"{sym}\n运行异常")
        continue

print(f"📊 扫描完成\n")
