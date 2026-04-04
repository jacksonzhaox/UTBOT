import pandas as pd
import pytz
import requests
from datetime import datetime
import json
import os
import yfinance as yf

# ==================== 配置 =====================
FEISHU_WEBHOOK = os.getenv("FEISHU_WEBHOOK")
print("✅ 飞书 WEBHOOK 读取成功:", FEISHU_WEBHOOK)

SYMBOLS = [
    "BTC-USD",
    "ETH-USD",
    "SOL-USD",
    "BNB-USD",
    "DOGE-USD"
]

TIMEFRAME = "15m"
ATR_LENGTH = 10
ATR_LENGTH = 10
ATR_MULTI = 2.0
BEIJING = pytz.timezone("Asia/Shanghai")
LAST_SIGNAL_FILE = "last_signals.json"
# ====================================================

# 信号去重
def load_last_signals():
    if os.path.exists(LAST_SIGNAL_FILE):
        with open(LAST_SIGNAL_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_last_signals(data):
    with open(LAST_SIGNAL_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)

last_signals = load_last_signals()

# ==================== 飞书推送（100%可用版）====================
def send_feishu(symbol, side, price, time_str):
    if not FEISHU_WEBHOOK:
        print("❌ 飞书推送失败：未设置 WEBHOOK")
        return

    title = "✅ UT Bot 买入信号" if side == "BUY" else "❌ UT Bot 卖出信号"
    color = "green" if side == "BUY" else "red"

    msg = {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "header": {"title": {"tag": "plain_text", "content": title}, "template": color},
            "elements": [{
                "tag": "div",
                "text": {"tag": "lark_md", "content": f"**品种**: {symbol}\n**方向**: {side}\n**价格**: {price}\n**时间**: {time_str}"}
            }]
        }
    }

    try:
        response = requests.post(FEISHU_WEBHOOK, json=msg, timeout=10)
        print(f"📤 飞书推送状态码: {response.status_code}")
        print(f"📤 飞书返回内容: {response.text}")
    except Exception as e:
        print(f"📤 飞书推送异常: {e}")

# 每次运行必发：在线状态通知
def send_online_status(time_str):
    if not FEISHU_WEBHOOK:
        return
    msg = {
        "msg_type": "text",
        "content": {
            "text": f"✅ UT Bot 在线运行中\n⏰ 时间: {time_str}\n📡 状态: 正常扫描"
        }
    }
    try:
        requests.post(FEISHU_WEBHOOK, json=msg, timeout=10)
    except:
        pass

# ==================== UT 算法 ====================
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
    data = yf.Ticker(symbol).history(period="5d", interval=TIMEFRAME)
    return data

# ==================== 主程序 ====================
now_str = datetime.now(BEIJING).strftime("%Y-%m-%d %H:%M:%S")
current_slot = datetime.now(BEIJING).strftime("%Y-%m-%d_%H_%M")

# ========== 每次运行 100% 发飞书 ==========
send_online_status(now_str)

print(f"\n📊 [{now_str}] UT Bot 扫描中...")

for sym in SYMBOLS:
    try:
        df = get_klines(sym)
        buy, sell, price = calculate_ut(df)
        key = f"{sym}_{current_slot}"

        if buy and last_signals.get(key) != "BUY":
            print(f"✅ {sym} 买入信号触发")
            send_feishu(sym, "BUY", price, now_str)
            last_signals[key] = "BUY"

        if sell and last_signals.get(key) != "SELL":
            print(f"❌ {sym} 卖出信号触发")
            send_feishu(sym, "SELL", price, now_str)
            last_signals[key] = "SELL"

    except Exception as e:
        print(f"⚠️ {sym} 错误: {e}")

save_last_signals(last_signals)
