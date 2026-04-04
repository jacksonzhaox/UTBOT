import os
import requests

# 读取正确的变量名：FEISHU_WEBHOOK
webhook = os.getenv("FEISHU_WEBHOOK")
print("WEBHOOK =", webhook)

# 飞书最简单、最不会错的文本消息格式，加上关键词！
msg = {
    "msg_type": "text",
    "content": {
        "text": "UT Bot ✅ 这是最终测试！收到这条就全通了！"
    }
}

response = requests.post(webhook, json=msg)
print("状态码:", response.status_code)
print("返回:", response.text)
