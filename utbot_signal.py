import pandas as pd
import pytz
import requests
from datetime import datetime
import json
import os
import yfinance as yf

# ==================== 核心配置（最终固定）=====================
FEISHU_WEBHOOK = os.getenv("FEISHU_WEBHOOK")
FEISHU_KEYWORD = "UT Bot"
BEIJING = pytz.timezone("Asia/Shanghai")
SYMBOLS = ["BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD", "DOGE-USD"]
TIMEFRAME = "15m"
ATR_LENGTH = 10
ATR_MULTI = 2.0
LAST_SIGNAL_FILE = "last_signals.json"

# ==================== 飞书推送（最终极简专业卡片）====================
def send_feishu(symbol, side, price, time_str):
    if not FEISHU_WEBHOOK:
        print("❌ 飞书推送失败：未设置 WEBHOOK")
        return

    direction = "买入" if side == "BUY" else "卖出"
    text = f"UT Bot\n**{symbol}** {direction}\n价格：{price}\n时间：{time_str}"

    msg = {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": "🟢 买入信号" if side == "BUY" else "🔴 卖出信号"},
                "template": "green" if side == "BUY" else "red"
            },
            "elements": [
                {"tag": "div", "text": {"tag": "lark_md", "content": text}}
            ]
        }
    }

    try:
        resp = requests.post(FEISHU_WEBHOOK, json=msg, timeout=10)
        print(f"📤 飞书状态码: {resp.status_code}")
    except Exception as e:
        print(f"📤 推送异常: {e}")

# ==================== 在线状态（极简专业）====================
def send_online_status(time_str):
    if not FEISHU_WEBHOOK:
        return
    msg = {
        "msg_type": "text",
        "content": {"text": f"UT Bot ✅ 正常运行\n{time_str}"}
    }
    try:
        requests.post(FEISHU_WEBHOOK, json=msg, timeout=10)
    except Exception:
        pass

# ==================== UT 算法（最终稳定版）====================
def calculate_ut(df):
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

# 获取K线
def get_klines(symbol):
    return yf.Ticker(symbol).history(period="5d", interval=TIMEFRAME)

# 信号去重
def load_last_signals():
    if os.path.exists(LAST_SIGNAL_FILE):
        with open(LAST_SIGNAL_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_last_signals(data):
    with open(LAST_SIGNAL_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)

# ==================== 主程序（最终）====================
now_str = datetime.now(BEIJING).strftime("%Y-%m-%d %H:%M:%S")
current_slot = datetime.now(BEIJING).strftime("%Y-%m-%d_%H_%M")

send_online_status(now_str)
print(f"\n📊 [{now_str}] UT Bot 扫描中...")

last_signals = load_last_signals()

for sym in SYMBOLS:
    try:
        df = get_klines(sym)
        buy, sell, price = calculate_ut(df)
        key = f"{sym}_{current_slot}"

        if buy and last_signals.get(key) != "BUY":
            print(f"✅ {sym} 买入信号")
            send_feishu(sym, "BUY", price, now_str)
            last_signals[key] = "BUY"

        if sell and last_signals.get(key) != "SELL":
            print(f"❌ {sym} 卖出信号")
            send_feishu(sym, "SELL", price, now_str)
            last_signals[key] = "SELL"

    except Exception as e:
        print(f"⚠️ {sym} 错误: {e}")

save_last_signals(last_signals)
print(f"\n📊 [{now_str}] 扫描完成\n")
