#!/usr/bin/env python3

import os
import socket
import json
import time
from collections import deque

# --- CONFIGURATION ---
# Add your worst distractions here (lowercase app classes)
# --- CONFIGURATION ---
# Expanded generalized blacklist
BLACKLIST = [
    # Social Media
    "reddit", "twitter", "x.com", "instagram", "facebook", "tiktok", "pinterest", "snapchat",
    
    # Video & Streaming
    "youtube", "netflix", "twitch", "prime", "hulu", "disney", "crunchyroll", "vimeo",
    
    # Gaming & Emulation
    "steam", "epicgames", "riot", "discord", "retroarch", "yuzu", "ryujinx", "minecraft", "roblox",
    
    # Messaging (Non-Work)
    "whatsapp", "telegram", "messenger", "signal", 
    
    # Shopping & Food Delivery
    "amazon", "flipkart", "myntra", "zomato", "swiggy", "ebay",
    
    # Browsers (If you use a specific browser ONLY for messing around)
    # "zen-browser", # Uncomment if Zen is strictly your distraction browser
    
    # Entertainment & Music (Optional - comment out if you listen to music while coding)
    "spotify", "applemusic", "tidal"
]
HISTORY_WINDOW_SEC = 60
MAX_HEALTHY_SWITCHES = 15.0 # If you switch windows 15 times a min, you are thrashing

def get_socket_path():
    his = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")
    if not his:
        print("FATAL: HYPRLAND_INSTANCE_SIGNATURE not set. Are you running Hyprland?")
        exit(1)
        
    # Check standard XDG path first, fallback to /tmp
    xdg = os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
    path = f"{xdg}/hypr/{his}/.socket2.sock"
    if not os.path.exists(path):
        path = f"/tmp/hypr/{his}/.socket2.sock"
    return path

def write_context(active_app, active_title, thrashing_score, penalty):
    filepath = "/home/posiedon/Desktop/Coding/Hack-NMIMS-CHD/core-pulse/layer3_governor/context.json"
    
    # Normalize thrashing to a 0.0 - 1.0 multiplier
    normalized_thrashing = min(thrashing_score / MAX_HEALTHY_SWITCHES, 1.0)
    
    data = {
        "timestamp": int(time.time()),
        "active_app": active_app,
        "active_title": active_title,
        "context_thrashing": normalized_thrashing,
        "distraction_penalty": penalty
    }
    
    # Atomic write to prevent C++ read crashes
    with open(filepath + ".tmp", 'w') as f:
        json.dump(data, f)
    os.rename(filepath + ".tmp", filepath)

def main():
    sock_path = get_socket_path()
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    client.connect(sock_path)
    print(f"[Layer 1] Tapped into Hyprland IPC: {sock_path}")

    current_app = "Unknown"
    current_title = "Desktop"
    switch_history = deque()

    # Create initial file
    write_context(current_app, current_title, 0.0, 0.0)

    # Listen to the infinite stream
    file_io = client.makefile('r')
    for line in file_io:
        line = line.strip()
        now = time.time()
        
        # Clean old history out of the 60-second window
        while switch_history and now - switch_history[0] > HISTORY_WINDOW_SEC:
            switch_history.popleft()

        if line.startswith("activewindow>>") or line.startswith("workspace>>"):
            if line.startswith("activewindow>>"):
                parts = line.split(">>", 1)[1].split(",", 1)
                if len(parts) == 2:
                    current_app = parts[0].strip().lower()
                    current_title = parts[1].strip()

            # Record the switch event
            switch_history.append(now)
            
            # Apply instant penalty if the app is a known distraction
            penalty = 0.35 if any(b in current_app for b in BLACKLIST) else 0.0
            
            print(f"[{time.strftime('%H:%M:%S')}] App: {current_app} | Thrashing Load: {len(switch_history)}/min | Penalty: {penalty}")
            write_context(current_app, current_title, len(switch_history), penalty)

if __name__ == "__main__":
    main()
