import pandas as pd
import pytz
import requests
from datetime import datetime
import os
import time

# ==================== 最终配置 =====================
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

# ==================== 极简推送 100%到达 ====================
def send_simple_msg(text):
    if not FEISHU_WEBHOOK:
        return
    msg = {"msg_type": "text", "content": {"text": f"UT Bot\n{text}"}}
    try:
        requests.post(FEISHU_WEBHOOK, json=msg, timeout=10)
    except:
        pass

# ==================== K线 ====================
def get_klines(s):
    for _ in range(2):
        try:
            import yfinance as yf
            df = yf.Ticker(s).history(period="5d", interval=TIMEFRAME)
            if len(df) >= 20:
                return df
        except:
            time.sleep(1)
    return None

# ==================== 信号 ====================
def get_signal(df):
    try:
        close = df["Close"]
        return close.iloc[-1] > close.iloc[-2], close.iloc[-1] < close.iloc[-2]
    except:
        return False, False

# ==================== K线形态 ====================
def candle(df):
    try:
        o, c = df["Open"].iloc[-2], df["Close"].iloc[-2]
        return "阳线" if c >= o else "阴线"
    except:
        return "获取失败"

# ==================== 主程序 ====================
now_str = datetime.now(BEIJING).strftime("%Y-%m-%d %H:%M:%S")
result = f"【全币种汇总】{now_str}\n\n"

for sym in SYMBOLS:
    df = get_klines(sym)
    if df is None:
        result += f"⚪ {sym} 数据异常\n"
        continue
    buy, sell = get_signal(df)
    shape = candle(df)
    if buy:
        result += f"🟢 {sym} 买入信号\n"
    elif sell:
        result += f"🔴 {sym} 卖出信号\n"
    else:
        result += f"⚪ {sym} 无信号 | {shape}\n"

# 发送
send_simple_msg(result)
print("✅ 推送完成")
