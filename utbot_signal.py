import pandas as pd
import pytz
import requests
from datetime import datetime
import os
import yfinance as yf

# ==================== 配置（最终固定）=====================
FEISHU_WEBHOOK = os.getenv("FEISHU_WEBHOOK")
BEIJING = pytz.timezone("Asia/Shanghai")
SYMBOLS = ["BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD", "DOGE-USD"]
TIMEFRAME = "15m"
ATR_LENGTH = 10
ATR_MULTI = 2.0

# ==================== 飞书信号卡片 ====================
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
        requests.post(FEISHU_WEBHOOK, json=msg, timeout=10)
        print(f"✅ {symbol} 信号推送")
    except Exception as e:
        print(f"❌ {symbol} 推送失败: {e}")

# ==================== 飞书常规通知（无信号/阴阳线）====================
def send_normal_msg(text):
    if not FEISHU_WEBHOOK:
        return
    msg = {
        "msg_type": "text",
        "content": {"text": f"UT Bot\n{text}"}
    }
    try:
        requests.post(FEISHU_WEBHOOK, json=msg, timeout=10)
    except:
        pass

# ==================== UT 信号计算（实时触发）====================
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

# ==================== 阴阳线判断 ====================
def get_candle_type(df):
    c = df["Close"].iloc[-2]
    o = df["Open"].iloc[-2]
    return "阳线" if c >= o else "阴线"

# ==================== 主程序（最终逻辑）====================
now_str = datetime.now(BEIJING).strftime("%Y-%m-%d %H:%M:%S")
print(f"\n📊 [{now_str}] 开始扫描")

for sym in SYMBOLS:
    try:
        df = yf.Ticker(sym).history(period="5d", interval=TIMEFRAME)
        if len(df) < 3:
            continue

        buy, sell, price = calculate_ut(df)
        candle = get_candle_type(df)

        # ============== 你要的核心规则 ==============
        if buy or sell:
            # 有信号 → 立即发卡片
            send_signal_card(sym, "BUY" if buy else "SELL", price, now_str)
        else:
            # 无信号 → 通知：无信号 + 阴阳线
            msg = f"{sym}\n无信号\nK线：{candle}"
            send_normal_msg(msg)
            print(f"ℹ️ {sym} 无信号，{candle}")

    except Exception as e:
        print(f"⚠️ {sym} 错误: {e}")

print(f"📊 扫描完成\n")
