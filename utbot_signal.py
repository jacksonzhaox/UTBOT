import os
import requests

# 强制发飞书，什么都不判断
webhook = os.getenv("FEISHU_WEBHOOK")
print("WEBHOOK:", webhook)

msg = {
    "msg_type": "text",
    "content": {
        "text": "✅ 我是最终测试消息！收到我就说明全通了！"
    }
}

res = requests.post(webhook, json=msg)
print("状态码:", res.status_code)
print("返回:", res.text)
