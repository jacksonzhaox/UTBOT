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

# ==================== 【强制必发】全币种一张卡片 ====================
def send_all_in_one_card(signal_list, time_str):
    if not FEISHU_WEBHOOK:
        print("❌ WEBHOOK 为空")
        return

    content = ""
    has_signal = False

    for item in signal_list:
        sym = item["symbol"]
        sig = item["signal"]
        candle = item["candle"]
        price = item["price"]

        if sig == "BUY":
            content += f"🟢 **{sym} 买入** | 价格：{price}\nK线：{candle}\n\n"
            has_signal = True
        elif sig == "SELL":
            content += f"🔴 **{sym} 卖出** | 价格：{price}\nK线：{candle}\n\n"
            has_signal = True
        else:
            content += f"⚪ {sym} 无信号\nK线：{candle}\n\n"

    title = "UT Bot 全币种汇总（有信号）" if has_signal else "UT Bot 全币种汇总"

    msg = {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": title},
                "template": "blue"
            },
            "elements": [
                {"tag": "div", "text": {"tag": "lark_md", "content": content.strip()}},
                {"tag": "hr"},
                {"tag": "note", "text": {"tag": "plain_text", "content": f"{time_str}"}}
            ]
        }
    }

    try:
        resp = requests.post(FEISHU_WEBHOOK, json=msg, timeout=12)
        print(f"✅ 卡片推送成功 | {resp.status_code}")
    except Exception as e:
        print(f"❌ 推送失败：{e}")

# ==================== 稳定K线（永不失败） ====================
def get_safe_klines(symbol, interval="15m"):
    for _ in range(3):
        try:
            import yfinance as yf
            df = yf.Ticker(symbol).history(period="7d", interval=interval, timeout=6)
            if df is not None and len(df) >= 20:
                return df.dropna()
        except:
            time.sleep(0.7)
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

# ==================== UT 信号 ====================
def calculate_ut(df):
    try:
        high, low, close = df["High"], df["Low"], df["Close"]
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

# ==================== K线阴阳 + 形态 ====================
def get_candle_info(df):
    try:
        o, c, h, l = df["Open"].iloc[-2], df["Close"].iloc[-2], df["High"].iloc[-2], df["Low"].iloc[-2]
        body = abs(c - o)
        rng = h - l
        if rng < 1e-8:
            return "十字星"
        up = h - max(c, o)
        dn = min(c, o) - l
        candle = "阳线" if c >= o else "阴线"

        if body / rng < 0.1:
            shape = "十字线"
        elif up / rng > 0.6 and body / rng < 0.2:
            shape = "流星线"
        elif dn / rng > 0.6 and body / rng < 0.2:
            shape = "锤子线"
        elif body / rng > 0.8:
            shape = "大实体"
        else:
            shape = "常规"
        return f"{candle}·{shape}"
    except:
        return "获取失败"

# ==================== 主程序（强制必发，永不消失） ====================
now_str = datetime.now(BEIJING).strftime("%Y-%m-%d %H:%M:%S")
print(f"\n📊 [{now_str}] 全币种扫描")

signal_list = []

for sym in SYMBOLS:
    try:
        df = get_safe_klines(sym, TIMEFRAME)
        if df is None or len(df) < 10:
            signal_list.append({"symbol": sym, "signal": None, "candle": "数据失败", "price": 0})
            continue

        buy, sell, price = calculate_ut(df)
        candle = get_candle_info(df)
        sig = "BUY" if buy else "SELL" if sell else None

        signal_list.append({"symbol": sym, "signal": sig, "candle": candle, "price": price})
    except:
        signal_list.append({"symbol": sym, "signal": None, "candle": "异常", "price": 0})

# 🔥 强制发送：不管有没有信号，必发一张！
send_all_in_one_card(signal_list, now_str)

print("📊 全部完成\n")
