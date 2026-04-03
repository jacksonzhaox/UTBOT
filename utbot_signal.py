import ccxt
import pandas as pd
import pytz
import requests
from datetime import datetime

# ==================== 配置（直接用）====================
FEISHU_WEBHOOK = "https://open.feishu.cn/open-apis/bot/v2/hook/d06d3b84-5c7c-4ef5-9e28-84d07ab758f4"
SYMBOLS = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT"]
TIMEFRAME = '15m'
ATR_LENGTH = 10
ATR_MULTI = 2.0
BEIJING = pytz.timezone('Asia/Shanghai')
# ======================================================

# 币安交易所（无需 API Key，只读公共数据）
exchange = ccxt.binance({
    'enableRateLimit': True,
})

# 飞书卡片推送
def send_feishu(symbol, side, price, time_str):
    title = "UT Bot 15m 买入✅" if side == "BUY" else "UT Bot 15m 卖出❌"
    color = "green" if side == "BUY" else "red"

    msg = {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": title},
                "template": color
            },
            "elements": [{
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**品种**: {symbol}\n**方向**: {side}\n**价格**: {price}\n**时间**: {time_str}"
                }
            }]
        }
    }
    try:
        requests.post(FEISHU_WEBHOOK, json=msg)
    except Exception as e:
        print("飞书推送失败", e)

# UT Bot 核心算法（和 TradingView 完全一样）
def calculate_ut(df):
    high = df['high']
    low = df['low']
    close = df['close']

    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
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

    buy = (src > trend.shift(1)) & (src.shift(1) <= trend.shift(2))
    sell = (src < trend.shift(1)) & (src.shift(1) >= trend.shift(2))
    return buy.iloc[-1], sell.iloc[-1], round(close.iloc[-1], 2)

# 获取 K 线
def get_klines(symbol):
    ohlcv = exchange.fetch_ohlcv(symbol, TIMEFRAME, limit=100)
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True).dt.tz_convert(BEIJING)
    return df

# 主程序
now_str = datetime.now(BEIJING).strftime("%Y-%m-%d %H:%M:%S")
print(f"\n📊 [{now_str}] 扫描 UT Bot 信号...")

for sym in SYMBOLS:
    try:
        df = get_klines(sym)
        buy, sell, price = calculate_ut(df)

        if buy:
            print(f"✅ {sym} 买入信号")
            send_feishu(sym, "BUY", price, now_str)
        if sell:
            print(f"❌ {sym} 卖出信号")
            send_feishu(sym, "SELL", price, now_str)

    except Exception as e:
        print(f"⚠️ {sym} 错误: {e}")
