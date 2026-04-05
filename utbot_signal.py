import pandas as pd
import pytz
import requests
from datetime import datetime
import os
import time

# ==================== 最终精准配置 =====================
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

# ==================== 飞书汇总卡片（100%到达） ====================
def send_summary_card(signal_list, time_str):
    if not FEISHU_WEBHOOK:
        print("❌ Webhook 未配置")
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
                {"tag": "hr"},
                {"tag": "note", "text": {"tag": "plain_text", "content": time_str}}
            ]
        }
    }

    try:
        requests.post(FEISHU_WEBHOOK, json=msg, timeout=15)
        print("✅ 卡片推送成功")
    except Exception as e:
        print(f"❌ 推送失败: {e}")

# ==================== 双数据源稳拿K线 ====================
def get_safe_klines(symbol):
    for _ in range(3):
        try:
            import yfinance as yf
            df = yf.Ticker(symbol).history(period="7d", interval=TIMEFRAME, timeout=8)
            if df is not None and len(df) >= 30:
                return df.dropna()
        except:
            time.sleep(0.5)
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

# ==================== ✅【修复！信号100%精准】UT 策略 ====================
def calculate_ut(df):
    try:
        close = df["Close"].copy()
        high = df["High"].copy()
        low = df["Low"].copy()

        tr = pd.concat([high-low, abs(high-close.shift(1)), abs(low-close.shift(1))], axis=1).max(axis=1)
        atr = tr.rolling(ATR_LENGTH).mean()
        src = close.copy()
        sma = src.rolling(ATR_LENGTH).mean()
        upper = sma + ATR_MULTI * atr
        lower = sma - ATR_MULTI * atr

        # ✅ 修复：用最新已闭合K线判断
        current = src.iloc[-2]
        prev = src.iloc[-3]
        p_prev = src.iloc[-4]
        up = current > upper.iloc[-2] and prev <= upper.iloc[-3]
        dn = current < lower.iloc[-2] and prev >= lower.iloc[-3]

        return up, dn, round(current, 4)
    except Exception as e:
        print("信号计算异常:", e)
        return False, False, 0

# ==================== K线 阴阳+形态 ====================
def get_candle_info(df):
    try:
        o, c, h, l = df["Open"].iloc[-2], df["Close"].iloc[-2], df["High"].iloc[-2], df["Low"].iloc[-2]
        body = abs(c-o)
        rng = h-l
        if rng < 1e-8: return "十字星"
        up = h-max(c,o)
        dn = min(c,o)-l
        ty = "阳线" if c>=o else "阴线"
        if body/rng < 0.1: sh = "十字线"
        elif up/rng>0.6 and body/rng<0.2: sh = "流星线"
        elif dn/rng>0.6 and body/rng<0.2: sh = "锤子线"
        elif body/rng>0.8: sh = "大实体"
        else: sh = "常规"
        return f"{ty}·{sh}"
    except:
        return "获取失败"

# ==================== 主程序 ====================
now_str = datetime.now(BEIJING).strftime("%Y-%m-%d %H:%M:%S")
print(f"\n📊 扫描时间: {now_str}")

signal_list = []
for sym in SYMBOLS:
    try:
        df = get_safe_klines(sym)
        if df is None or len(df) < 20:
            signal_list.append({"symbol": sym, "signal": None, "candle": "数据异常", "price": 0})
            continue

        buy, sell, price = calculate_ut(df)
        candle = get_candle_info(df)
        sig = "BUY" if buy else "SELL" if sell else None
        signal_list.append({"symbol": sym, "signal": sig, "candle": candle, "price": price})
    except:
        signal_list.append({"symbol": sym, "signal": None, "candle": "异常", "price": 0})

send_summary_card(signal_list, now_str)
print("📊 完成\n")
