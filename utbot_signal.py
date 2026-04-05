import os
import requests
from datetime import datetime
import time

# 终极兜底：直到发出去为止
webhook = os.getenv("FEISHU_WEBHOOK")
now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
msg = f"✅ UT Bot 定时运行 {now}"

# 核心逻辑：失败重试3次，每2秒一次
success = False
for attempt in range(3):
    try:
        response = requests.post(
            webhook,
            json={"msg_type": "text", "content": {"text": msg}},
            timeout=15
        )
        # 检查飞书返回码
        if response.status_code == 200 and "success" in response.text:
            success = True
            break
        else:
            print(f"⚠️  第 {attempt+1} 次失败，状态码: {response.status_code}")
    except Exception as e:
        print(f"⚠️  第 {attempt+1} 次异常: {e}")
    time.sleep(2)

if success:
    print("✅ 最终发送成功！")
else:
    print("❌ 最终发送失败，请检查飞书机器人配置")
