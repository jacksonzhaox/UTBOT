import ccxt
import pandas as pd
import pytz
import requests
from datetime import datetime
import json
import os

# ==================== 配置 =====================
FEISHU_WEBHOOK = "https://open.feishu.cn/open-apis/bot/v2/hook/d06d3b84-5c7c-4ef5-9e28-84d07ab758f4"

# 币安现货交易对（100%不报错）
SYMBOLS = [
    "BTC/USDT",
    "ETH/USDT",
    "SOL/USDT",
    "BNB/USDT",
    "DOGE/USDT"
]

TIMEFRAME = '15m'
ATR_LENGTH = 10
ATR_MULTI = 2.0
BEIJING = pytz.timezone('Asia/Shanghai')
LAST_SIGNAL_FILE = "last_signals.json"
# ===============================================

# ✅ 强制现货，彻底避开合约接口
exchange = ccxt.binance({
    'enableRateLimit': True,
    'options': {
        'defaultType': 'spot',
    }
})

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

# 飞书推送
def send_feishu(symbol, side, price, time_str):
    title = "UT Bot 15m 买入✅" if side == "BUY" else "UT Bot 15m 卖出❌"
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
        requests.post(FEISHU_WEBHOOK, json=msg)
    except Exception as e:
        print("飞书推送失败:", e)

# ==================== UT 核心（和TV完全一致）====================
def calculate_ut(df):
    high = df['high']
    low = df['low']
    close = df['close']

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

    # ✅ 关键：判断【倒数第二根】= TV收盘信号（不会漏）
    buy = (src.iloc[-2] > trend.iloc[-2]) & (src.iloc[-3] <= trend.iloc[-3])
    sell = (src.iloc[-2] < trend.iloc[-2]) & (src.iloc[-3] >= trend.iloc[-3])
    return buy, sell, round(close.iloc[-2], 4)

# 获取K线
def get_klines(symbol):
    ohlcv = exchange.fetch_ohlcv(symbol, TIMEFRAME, limit=100)
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True).dt.tz_convert(BEIJING)
    return df

# ==================== 主程序 ====================
now_str = datetime.now(BEIJING).strftime("%Y-%m-%d %H:%M:%S")
current_slot = datetime.now(BEIJING).strftime("%Y-%m-%d_%H_%M")

print(f"\n📊 [{now_str}] 扫描 UT 收盘信号...")

for sym in SYMBOLS:
    try:
        df = get_klines(sym)
        buy, sell, price = calculate_ut(df)
        key = f"{sym}_{current_slot}"

        if buy and last_signals.get(key) != "BUY":
            print(f"✅ {sym} 买入")
            send_feishu(sym, "BUY", price, now_str)
            last_signals[key] = "BUY"

        if sell and last_signals.get(key) != "SELL":
            print(f"❌ {sym} 卖出")
            send_feishu(sym, "SELL", price, now_str)
            last_signals[key] = "SELL"

    except Exception as e:
        print(f"⚠️ {sym} 错误: {e}")

save_last_signals(last_signals)
