import requests
import os
import json
import pytz
from datetime import datetime
from tradingview_ta import TA_Handler, Interval

FEISHU_WEBHOOK = "https://open.feishu.cn/open-apis/bot/v2/hook/d06d3b84-5c7c-4ef5-9e28-84d07ab758f4"
SEEN_FILE = 'utbot_seen.json'
BEIJING = pytz.timezone('Asia/Shanghai')

SYMBOLS = [
    {'name': 'BTC',   'symbol': 'BTCUSDT',  'exchange': 'BINANCE',  'screener': 'crypto'},
    {'name': 'ETH',   'symbol': 'ETHUSDT',  'exchange': 'BINANCE',  'screener': 'crypto'},
    {'name': 'BNB',   'symbol': 'BNBUSDT',  'exchange': 'BINANCE',  'screener': 'crypto'},
    {'name': '狗狗币', 'symbol': 'DOGEUSDT', 'exchange': 'BINANCE',  'screener': 'crypto'},
    {'name': '黄金',  'symbol': 'XAUUSD',   'exchange': 'OANDA',    'screener': 'CFD'},
    {'name': '道琼斯', 'symbol': 'DJI',      'exchange': 'DJ',       'screener': 'america'},
    {'name': '纳斯达克','symbol': 'IXIC',    'exchange': 'NASDAQ',   'screener': 'america'},
    {'name': '标普500','symbol': 'SPX',      'exchange': 'SP',       'screener': 'america'},
]

def load_seen():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_seen(seen):
    with open(SEEN_FILE, 'w') as f:
        json.dump(seen, f)

def check_signals(seen):
    alerts = []
    now_beijing = datetime.now(BEIJING).strftime('%Y-%m-%d %H:%M')

    for s in SYMBOLS:
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

            print(f"{s['name']} | 推荐:{rec} | 买:{buy_count} | 卖:{sell_count} | 价格:{price}")

            uid = f"{s['name']}_{now_beijing}"

            if rec in ('BUY', 'STRONG_BUY') and uid not in seen:
                alerts.append({
                    'name': s['name'],
                    'signal': '🟢 买入信号 BUY' if rec == 'BUY' else '🟢🟢 强烈买入 STRONG BUY',
                    'price': price,
                    'buy': buy_count,
                    'sell': sell_count,
                    'time': now_beijing,
                    'uid': uid,
                })
                seen[uid] = True

            elif rec in ('SELL', 'STRONG_SELL') and uid not in seen:
                alerts.append({
                    'name': s['name'],
                    'signal': '🔴 卖出信号 SELL' if rec == 'SELL' else '🔴🔴 强烈卖出 STRONG SELL',
                    'price': price,
                    'buy': buy_count,
                    'sell': sell_count,
                    'time': now_beijing,
                    'uid': uid,
                })
                seen[uid] = True

        except Exception as e:
            print(f"❌ {s['name']} 失败: {e}")

    return alerts, seen

def send_to_feishu(alerts):
    now = datetime.now(BEIJING).strftime('%Y-%m-%d %H:%M')
    lines = [
        f"🚨 TradingView 交易信号 {now} (北京时间)",
        "周期: 15分钟",
        "━━━━━━━━━━━━━━━━"
    ]
    for a in alerts:
        lines += [
            f"\n{a['signal']}",
            f"品种: {a['name']}",
            f"信号时间: {a['time']}",
            f"当前价: {a['price']:,.4f}",
            f"买入指标数: {a['buy']} | 卖出指标数: {a['sell']}",
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
        print(f"[{now} 北京时间] 暂无交易信号")
