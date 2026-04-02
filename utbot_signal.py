import yfinance as yf
import pandas as pd
import numpy as np
import requests
import os
import json
import pytz
from datetime import datetime
from tradingview_ta import TA_Handler, Interval

FEISHU_WEBHOOK = "https://open.feishu.cn/open-apis/bot/v2/hook/d06d3b84-5c7c-4ef5-9e28-84d07ab758f4"
SEEN_FILE = 'utbot_seen.json'
BEIJING = pytz.timezone('Asia/Shanghai')

# UT Bot 参数
SENSITIVITY = 2
ATR_PERIOD = 10
INTERVAL_YF = '15m'
PERIOD_YF = '5d'

# yfinance 标的
SYMBOLS_YF = {
    'BTC': 'BTC-USD',
    'ETH': 'ETH-USD',
    'BNB': 'BNB-USD',
    '狗狗币': 'DOGE-USD',
    '黄金': 'GC=F',
    '道琼斯': '^DJI',
    '纳斯达克': '^IXIC',
    '标普500': '^GSPC',
}

# TradingView 标的
SYMBOLS_TV = [
    {'name': 'BTC',    'symbol': 'BTCUSDT',  'exchange': 'BINANCE',  'screener': 'crypto'},
    {'name': 'ETH',    'symbol': 'ETHUSDT',  'exchange': 'BINANCE',  'screener': 'crypto'},
    {'name': 'BNB',    'symbol': 'BNBUSDT',  'exchange': 'BINANCE',  'screener': 'crypto'},
    {'name': '狗狗币',  'symbol': 'DOGEUSDT', 'exchange': 'BINANCE',  'screener': 'crypto'},
    {'name': '黄金',   'symbol': 'XAUUSD',   'exchange': 'OANDA',    'screener': 'CFD'},
    {'name': '道琼斯',  'symbol': 'DJI',      'exchange': 'DJ',       'screener': 'america'},
    {'name': '纳斯达克','symbol': 'IXIC',     'exchange': 'NASDAQ',   'screener': 'america'},
    {'name': '标普500', 'symbol': 'SPX',      'exchange': 'SP',       'screener': 'america'},
]

def load_seen():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_seen(seen):
    with open(SEEN_FILE, 'w') as f:
        json.dump(seen, f)

def compute_utbot(df):
    close = df['Close'].squeeze()
    high = df['High'].squeeze()
    low = df['Low'].squeeze()

    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs()
    ], axis=1).max(axis=1)
    atr = tr.ewm(span=ATR_PERIOD, adjust=False).mean()
    nloss = SENSITIVITY * atr

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

def check_utbot(seen):
    alerts = []
    for name, symbol in SYMBOLS_YF.items():
        try:
            df = yf.download(symbol, period=PERIOD_YF, interval=INTERVAL_YF, progress=False)
            if df.empty:
                continue

            buy, sell, trail = compute_utbot(df)
            close = df['Close'].squeeze()

            i = -2
            ts_utc = df.index[i]
            ts_beijing = ts_utc.tz_convert(BEIJING)
            ts = ts_beijing.strftime('%Y-%m-%d %H:%M')
            price = close.iloc[i]
            trail_val = trail.iloc[i]
            uid = f"utbot_{name}_{ts}"

            print(f"[UTBot] {name} | {ts} | 价格:{price:.4f} | 追踪止损:{trail_val:.4f} | 买:{buy.iloc[i]} | 卖:{sell.iloc[i]}")

            if buy.iloc[i] and uid not in seen:
                alerts.append({
                    'source': 'UT Bot',
                    'name': name,
                    'signal': '🟢 买入信号 BUY',
                    'price': price,
                    'extra': f"追踪止损: {trail_val:.4f}",
                    'time': ts,
                    'uid': uid,
                })
                seen[uid] = True
            elif sell.iloc[i] and uid not in seen:
                alerts.append({
                    'source': 'UT Bot',
                    'name': name,
                    'signal': '🔴 卖出信号 SELL',
                    'price': price,
                    'extra': f"追踪止损: {trail_val:.4f}",
                    'time': ts,
                    'uid': uid,
                })
                seen[uid] = True

        except Exception as e:
            print(f"❌ [UTBot] {name} 失败: {e}")

    return alerts, seen

def check_tv(seen):
    alerts = []
    now_hour = datetime.now(BEIJING).strftime('%Y-%m-%d %H')

    for s in SYMBOLS_TV:
        try:
            handler = TA_Handler(
                symbol=s['symbol'],
                exchange=s['exchange'],
                screener=s['screener'],
                interval=Interval.INTERVAL_15_MINUTES,
            )
            analysis = handler.get_analysis()
            rec = analysis.summary['RECOMMENDATION']
            buy_count = analysis.summary['BUY']
            sell_count = analysis.summary['SELL']
            price = analysis.indicators.get('close', 0)
            uid = f"tv_{s['name']}_{now_hour}"

            print(f"[TV] {s['name']} | 推荐:{rec} | 买:{buy_count} | 卖:{sell_count} | 价格:{price}")

            if rec in ('BUY', 'STRONG_BUY') and uid not in seen:
                alerts.append({
                    'source': 'TradingView综合',
                    'name': s['name'],
                    'signal': '🟢 买入' if rec == 'BUY' else '🟢🟢 强烈买入',
                    'price': price,
                    'extra': f"买入指标:{buy_count} | 卖出指标:{sell_count}",
                    'time': datetime.now(BEIJING).strftime('%Y-%m-%d %H:%M'),
                    'uid': uid,
                })
                seen[uid] = True
            elif rec in ('SELL', 'STRONG_SELL') and uid not in seen:
                alerts.append({
                    'source': 'TradingView综合',
                    'name': s['name'],
                    'signal': '🔴 卖出' if rec == 'SELL' else '🔴🔴 强烈卖出',
                    'price': price,
                    'extra': f"买入指标:{buy_count} | 卖出指标:{sell_count}",
                    'time': datetime.now(BEIJING).strftime('%Y-%m-%d %H:%M'),
                    'uid': uid,
                })
                seen[uid] = True

        except Exception as e:
            print(f"❌ [TV] {s['name']} 失败: {e}")

    return alerts, seen

def send_to_feishu(alerts):
    now = datetime.now(BEIJING).strftime('%Y-%m-%d %H:%M')
    lines = [
        f"🚨 交易信号提醒 {now} (北京时间)",
        "周期: 15分钟",
        "━━━━━━━━━━━━━━━━"
    ]
    for a in alerts:
        lines += [
            f"\n【{a['source']}】{a['signal']}",
            f"品种: {a['name']}",
            f"时间: {a['time']}",
            f"价格: {a['price']:,.4f}",
            f"{a['extra']}",
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

    utbot_alerts, seen = check_utbot(seen)
    tv_alerts, seen = check_tv(seen)

    all_alerts = utbot_alerts + tv_alerts
    save_seen(seen)

    if all_alerts:
        send_to_feishu(all_alerts)
    else:
        now = datetime.now(BEIJING).strftime('%H:%M')
        print(f"[{now} 北京时间] 暂无交易信号")
