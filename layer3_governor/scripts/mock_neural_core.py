import json
import time
import random
import os

def stream_telemetry():
    filepath = "/home/posiedon/Desktop/Coding/Hack-NMIMS-CHD/core-pulse/layer3_governor/telemetry.json"
    print(f"[Mock Core] Online. Bypassing Network. Writing directly to {filepath}...")
    
    while True:
        bp = 0.90 + random.uniform(0.0, 0.08)
        
        payload = {
            "timestamp": int(time.time()),
            "user_id": "U-8472",
            "burnout_probability": bp,
            "status": "CRITICAL",
            "active_distractions": ["youtube.com", "discord.com"],
            "synergy_friction_score": 0.72
        }

        # Atomically write to the file
        with open(filepath, 'w') as f:
            json.dumps(payload)
            f.write(json.dumps(payload))

        print(f"[{int(time.time())}] Written to disk! (B_p: {bp:.2f})")
        time.sleep(2)

if __name__ == "__main__":
    stream_telemetry()
