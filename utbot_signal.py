import os
import requests
from datetime import datetime

FEISHU_WEBHOOK = os.getenv("FEISHU_WEBHOOK")
now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

msg = f"✅ UT Bot 正常运行 {now}\nBTC ETH SOL BNB DOGE 全币种扫描中"

try:
    requests.post(FEISHU_WEBHOOK, json={
        "msg_type": "text",
        "content": {"text": msg}
    }, timeout=10)
    print("✅ 推送成功")
except:
    print("❌ 推送失败")
