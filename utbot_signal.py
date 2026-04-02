import yfinance as yf
import pandas as pd
import numpy as np
import requests
import os
import json
import pytz
from datetime import datetime

FEISHU_WEBHOOK = "https://open.feishu.cn/open-apis/bot/v2/hook/d06d3b84-5c7c-4ef5-9e28-84d07ab758f4"
SEEN_FILE = 'utbot_seen.json'

# UT Bot 参数
SENSITIVITY = 2
ATR_PERIOD = 10
INTERVAL = '15m'
PERIOD = '5d'
BEIJING = pytz.timezone('Asia/Shanghai')

SYMBOLS = {
    'BTC': 'BTC-USD',
    'ETH': 'ETH-USD',
    'BNB': 'BNB-USD',
    '狗狗币': 'DOGE-USD',
    '黄金': 'GC=F',
    '道琼斯': '^DJI',
    '纳斯达克': '^IXIC',
    '标普500': '^GSPC',
}

def load_seen():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_seen(seen):
    with open(SEEN_FILE, 'w') as f:
        json.dump(seen, f)

def compute_utbot(df, sensitivity=2, atr_period=10):
    close = df['Close'].squeeze()
    high = df['High'].squeeze()
    low = df['Low'].squeeze()

    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs()
    ], axis=1).max(axis=1)
    atr = tr.ewm(span=atr_period, adjust=False).mean()
    nloss = sensitivity * atr

    xATRTrailingStop = pd.Series(0.0, index=close.index)
    for i in range(1, len(close)):
        prev = xATRTrailingStop.iloc[i-1]
        src = close.iloc[i]
        src_prev = close.iloc[i-1]
        nl = nloss.iloc[i]
        if src > prev and src_prev > prev:
            xATRTrailingStop.iloc[i] = max(prev, src - nl)
        elif src < prev and src_prev < prev:
            xATRTrailingStop.iloc[i] = min(prev, src + nl)
        elif src > prev:
            xATRTrailingStop.iloc[i] = src - nl
        else:
            xATRTrailingStop.iloc[i] = src + nl

    ema = close.ewm(span=1, adjust=False).mean()
    above = (ema > xATRTrailingStop) & (ema.shift() <= xATRTrailingStop.shift())
    below = (ema < xATRTrailingStop) & (ema.shift() >= xATRTrailingStop.shift())
    buy = (close > xATRTrailingStop) & above
    sell = (close < xATRTrailingStop) & below

    return buy, sell, xATRTrailingStop

def check_signals(seen):
    alerts = []
    for name, symbol in SYMBOLS.items():
        try:
            df = yf.download(symbol, period=PERIOD, interval=INTERVAL, progress=False)
            if df.empty:
                print(f"⚠️ {name}: 数据为空")
                continue

            buy, sell, trail = compute_utbot(df, SENSITIVITY, ATR_PERIOD)
            close = df['Close'].squeeze()

            # 用倒数第二根K线（已收盘确认，与TradingView一致）
            i = -2
            ts_utc = df.index[i]
            ts_beijing = ts_utc.tz_convert(BEIJING)
            ts = ts_beijing.strftime('%Y-%m-%d %H:%M')
            price = close.iloc[i]
            trail_val = trail.iloc[i]
            uid = f"{name}_{ts}"

            print(f"{name} | 北京时间:{ts} | 价格:{price:.4f} | 追踪止损:{trail_val:.4f} | 买入:{buy.iloc[i]} | 卖出:{sell.iloc[i]}")

            if buy.iloc[i] and uid not in seen:
                alerts.append({
                    'name': name,
                    'signal': '🟢 买入信号 BUY',
                    'price': price,
                    'trail': trail_val,
                    'time': ts,
                    'uid': uid,
                })
                seen[uid] = True

            elif sell.iloc[i] and uid not in seen:
                alerts.append({
                    'name': name,
                    'signal': '🔴 卖出信号 SELL',
                    'price': price,
                    'trail': trail_val,
                    'time': ts,
                    'uid': uid,
                })
                seen[uid] = True

        except Exception as e:
            print(f"❌ {name} 失败: {e}")

    return alerts, seen

def send_to_feishu(alerts):
    now = datetime.now(BEIJING).strftime('%Y-%m-%d %H:%M')
    lines = [
        f"🚨 UT Bot 交易信号 {now}",
        f"参数: 灵敏度={SENSITIVITY} | ATR={ATR_PERIOD} | 周期=15分钟",
        "━━━━━━━━━━━━━━━━"
    ]
    for a in alerts:
        lines += [
            f"\n{a['signal']}",
            f"品种: {a['name']}",
            f"信号时间: {a['time']} (北京时间)",
            f"当前价: {a['price']:,.4f}",
            f"追踪止损线: {a['trail']:,.4f}",
        ]
    lines += [
        "\n━━━━━━━━━━━━━━━━",
        "⚠️ 仅供参考，注意风险"
    ]
    content = "\n".join(lines)
    print(content)
    requests.post(FEISHU_WEBHOOK, json={"msg_type": "text", "content": {"text": content}})
    print("✅ 推送完成")

if __name__ == '__main__':
    seen = load_seen()
    alerts, seen = check_signals(seen)
    save_seen(seen)
    if alerts:
        send_to_feishu(alerts)
    else:
        now = datetime.now(BEIJING).strftime('%H:%M')
        print(f"[{now} 北京时间] 暂无 UT Bot 信号")
