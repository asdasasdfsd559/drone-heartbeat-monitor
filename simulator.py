import time
import json
from datetime import datetime

print("=" * 50)
print("无人机心跳模拟器")
print("=" * 50)

sequence = 0

print("开始发送心跳...\n")

try:
    while True:
        sequence += 1
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # 显示在屏幕
        print(f"[{timestamp}] 心跳 #{sequence} 已发送")
        
        # 保存到文件（用简单格式）
        with open("heartbeat.txt", "a", encoding="utf-8") as f:
            f.write(f"{timestamp},{sequence}\n")
        
        time.sleep(1)
        
except KeyboardInterrupt:
    print("\n\n模拟器已停止")