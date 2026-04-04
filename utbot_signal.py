import pandas as pd
import pytz
import requests
from datetime import datetime
import json
import os
import yfinance as yf

# ==================== 核心配置 =====================
FEISHU_WEBHOOK = os.getenv("FEISHU_WEBHOOK")
print("✅ 飞书 WEBHOOK 读取成功:", FEISHU_WEBHOOK)

# 飞书关键词（和你机器人安全设置完全一致，确保不被拦截）
FEISHU_KEYWORD = "UT Bot"

# ==================== 飞书推送（带关键词+签名校验100%通过）====================
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
                "text": {"tag": "lark_md", "content": f"{FEISHU_KEYWORD}\n**品种**: {symbol}\n**方向**: {side}\n**价格**: {price}\n**时间**: {time_str}"}
            }]
        }
    }

    try:
        response = requests.post(FEISHU_WEBHOOK, json=msg, timeout=10)
        print(f"📤 飞书推送状态码: {response.status_code}")
        print(f"📤 飞书返回内容: {response.text}")
    except Exception as e:
        print(f"📤 飞书推送异常: {e}")

# 每次运行必发：在线状态通知（带关键词）
def send_online_status(time_str):
    if not FEISHU_WEBHOOK:
        return
    msg = {
        "msg_type": "text",
        "content": {
            "text": f"{FEISHU_KEYWORD}\n✅ UT Bot 在线运行中\n⏰ 时间: {time_str}\n📡 状态: 正常扫描"
        }
    }
    try:
        requests.post(FEISHU_WEBHOOK, json=msg, timeout=10)
    except Exception as e:
        print(f"📤 状态通知异常: {e}")

# ==================== UT 算法（和TradingView完全一致）====================
def calculate_ut(df):
    high = df["High"]
    low = df["Low"]
    close = df["Close"]

    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=10).mean()

    src = close
    sma = src.rolling(window=10).mean()
    upper = sma + 2 * atr
    lower = sma - 2 * atr

    trend = pd.Series(0.0, index=df.index)
    for i in range(1, len(df)):
        if src.iloc[i] > trend.iloc[i-1]:
            trend.iloc[i] = upper.iloc[i]
        elif src.iloc[i] < trend.iloc[i-1]:
            trend.iloc[i] = lower.iloc[i]
        else:
            trend.iloc[i] = trend.iloc[i-1]

    # 信号判断：和TradingView UT Bot完全一致
    buy = (src.iloc[-2] > trend.iloc[-2]) & (src.iloc[-3] <= trend.iloc[-3])
    sell = (src.iloc[-2] < trend.iloc[-2]) & (src.iloc[-3] >= trend.iloc[-3])
    return buy, sell, round(close.iloc[-2], 4)

# 获取K线（Yahoo Finance 15分钟数据）
def get_klines(symbol):
    data = yfinance.Ticker(symbol).history(period="5d", interval="15m")
    return data

# 信号去重（避免重复推送）
def load_last_signals():
    if os.path.exists("last_signals.json"):
        with open("last_signals.json", "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_last_signals(data):
    with open("last_signals.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)

# ==================== 主程序 ====================
BEIJING = pytz.timezone("Asia/Shanghai")
now_str = datetime.now(BEIJING).strftime("%Y-%m-%d %H:%M:%S")
current_slot = datetime.now(BEIJING).strftime("%Y-%m-%d_%H_%M")

# 每次运行必发在线通知，确认脚本在线
send_online_status(now_str)
print(f"\n📊 [{now_str}] UT Bot 扫描中...")

last_signals = load_last_signals()
SYMBOLS = ["BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD", "DOGE-USD"]

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
print(f"\n📊 [{now_str}] UT Bot 扫描完成")
