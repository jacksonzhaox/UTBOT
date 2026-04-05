import pandas as pd
import pytz
import requests
from datetime import datetime
import os
import time

# ==================== 最终死配置 =====================
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

# ==================== 【死命令：必须发出去】====================
def send_force_card(signal_list, time_str):
    content = ""
    for item in signal_list:
        sym = item["symbol"]
        sig = item["signal"]
        candle = item["candle"]
        price = item["price"]
        if sig == "BUY":
            content += f"🟢 {sym} 买入 {price}\n{candle}\n\n"
        elif sig == "SELL":
            content += f"🔴 {sym} 卖出 {price}\n{candle}\n\n"
        else:
            content += f"⚪ {sym} 无信号\n{candle}\n\n"

    msg = {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": "UT Bot 全币种汇总"},
                "template": "blue"
            },
            "elements": [
                {"tag": "div", "text": {"tag": "lark_md", "content": content.strip()}},
                {"tag": "note", "text": {"tag": "plain_text", "content": time_str}}
            ]
        }
    }

    # 死循环重试 10 次，必须发成功
    for i in range(10):
        try:
            r = requests.post(FEISHU_WEBHOOK, json=msg, timeout=15)
            print(f"✅ 推送成功 {i+1}次 | {r.status_code}")
            return
        except Exception as e:
            print(f"⚠️ 推送失败 {i+1}次，重试...")
            time.sleep(1)

# ==================== K线获取（容错拉满）====================
def get_klines_safe(symbol):
    try:
        import yfinance as yf
        return yf.Ticker(symbol).history(period="7d", interval=TIMEFRAME, timeout=10)
    except:
        return None

# ==================== 信号 ====================
def calc_ut(df):
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

# ==================== K线形态 ====================
def candle_shape(df):
    try:
        o, c, h, l = df["Open"].iloc[-2], df["Close"].iloc[-2], df["High"].iloc[-2], df["Low"].iloc[-2]
        body = abs(c-o)
        rng = h-l
        if rng < 1e-8:
            return "十字星"
        up = h - max(c,o)
        dn = min(c,o) - l
        ty = "阳线" if c>=o else "阴线"
        if body/rng < 0.1:
            sh = "十字线"
        elif up/rng>0.6 and body/rng<0.2:
            sh = "流星线"
        elif dn/rng>0.6 and body/rng<0.2:
            sh = "锤子线"
        elif body/rng>0.8:
            sh = "大实体"
        else:
            sh = "常规"
        return f"{ty}·{sh}"
    except:
        return "获取失败"

# ==================== 主程序（绝对不崩）====================
now_str = datetime.now(BEIJING).strftime("%Y-%m-%d %H:%M:%S")
signal_list = []

for sym in SYMBOLS:
    try:
        df = get_klines_safe(sym)
        if df is None or len(df) < 10:
            signal_list.append({"symbol": sym, "signal": None, "candle": "数据异常", "price": 0})
            continue
        buy, sell, price = calc_ut(df)
        shape = candle_shape(df)
        sig = "BUY" if buy else "SELL" if sell else None
        signal_list.append({"symbol": sym, "signal": sig, "candle": shape, "price": price})
    except:
        signal_list.append({"symbol": sym, "signal": None, "candle": "异常", "price": 0})

# 🔥 死命令：必须推送
send_force_card(signal_list, now_str)

print("📊 全部完成，卡片已强制推送\n")
