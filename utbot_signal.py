import os
import requests
from datetime import datetime

webhook = os.getenv("FEISHU_WEBHOOK")
now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
text = f"✅ UT Bot {now} - 正常运行"

try:
    requests.post(webhook, json={
        "msg_type": "text",
        "content": {"text": text}
    }, timeout=10)
    print("OK")
except:
    print("FAIL")
