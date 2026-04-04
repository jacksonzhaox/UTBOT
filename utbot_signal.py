import os
import requests

# 读取你正确的变量名：FEISHU_WEBHOOK
webhook = os.getenv("FEISHU_WEBHOOK")

print("WEBHOOK =", webhook)

# 直接发飞书
msg = {
    "msg_type": "text",
    "content": {
        "text": "✅ 这是最终测试！收到这条就全通了！"
    }
}

response = requests.post(webhook, json=msg)

print("状态码:", response.status_code)
print("返回:", response.text)
