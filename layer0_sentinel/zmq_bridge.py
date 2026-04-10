#!/usr/bin/env python3

import os
import time
import json
import zmq

# Paths based on loader.cpp
RAW_HW_PIPE = "/home/posiedon/Desktop/Coding/Hack-NMIMS-CHD/core-pulse/layer1_vault/raw_hardware.json"
TUI_PIPE = "/home/posiedon/Desktop/Coding/Hack-NMIMS-CHD/core-pulse/layer3_governor/telemetry.json"
ZMQ_ENDPOINT = "tcp://127.0.0.1:5557"

def run_bridge():
    print("[Bridge] Online. Splitting File Pipe to UI and ZMQ Vault...")
    
    context = zmq.Context()
    socket = context.socket(zmq.PUB)
    socket.bind(ZMQ_ENDPOINT)
    
    last_content = ""
    sequence = 0
    
    while True:
        time.sleep(0.1) # Fast poll to keep the UI smooth
        
        if not os.path.exists(RAW_HW_PIPE): continue
            
        try:
            with open(RAW_HW_PIPE, "r") as f: current_content = f.read()
        except OSError: continue
            
        if not current_content or current_content == last_content: continue
            
        try: cpp_payload = json.loads(current_content)
        except json.JSONDecodeError: continue

        last_content = current_content
        sequence += 1
        
        # --- STREAM 1: Fast Pipe to Layer 3 (TUI) ---
        # Forward exactly what loader.cpp outputted directly to the UI
        with open(TUI_PIPE + ".tmp", "w") as f:
            json.dump(cpp_payload, f)
        os.rename(TUI_PIPE + ".tmp", TUI_PIPE)
        
        # --- STREAM 2: Enterprise Schema for Layer 1 (Vault) ---
        bp = cpp_payload.get("burnout_probability", 0.0)
        distractions = cpp_payload.get("active_distractions", [])
        
        enterprise_payload = {
            "payload": {
                "timestamp": str(cpp_payload.get("timestamp", int(time.time()))),
                "sequence": sequence,
                "sensor_id": "rog-zephyrus-g16-ebpf",
                "team": "core-pulse-alpha",
                "employees": [{
                    "user_id": cpp_payload.get("user_id", "posiedon-local"),
                    "display_name": "Armaan",
                    "focus_score": max(0.0, 1.0 - bp),
                    "burnout_risk": bp,
                    "activity_load": cpp_payload.get("synergy_friction_score", 0.0),
                    "context_switches": len(distractions),
                    "keystroke_entropy": 0.5, 
                    "active_window": "unknown",
                    "distractions": distractions,
                    "flow_minutes": 0
                }],
                "system_load": { "cpu": 15.0, "memory": 45.0, "network_mbps": 10.0 },
                "flags": ["intervention_active"] if cpp_payload.get("status") == "CRITICAL" else []
            }
        }
        
        # Broadcast via ZeroMQ for your teammates' code to catch
        message = f"telemetry_raw {json.dumps(enterprise_payload)}".encode('utf-8')
        socket.send(message)
        print(f"[Bridge] Routed Sequence {sequence} -> Vault & TUI | B_p: {bp:.2f}")

if __name__ == "__main__":
    run_bridge()
