import os
import requests

webhook = os.getenv("FEISHU_WEBHOOK")

msg = "✅ UT Bot 已运行 - 测试消息"

try:
    requests.post(
        webhook,
        json={"msg_type": "text", "content": {"text": msg}},
        timeout=10
    )
    print("发送成功")
except Exception as e:
    print("发送失败:", e)
