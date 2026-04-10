#!/bin/bash
# Throttles network using Linux 'tc' to induce friction on distractions

INTERFACE="wlan0" # Adjust to 'eth0' or your specific interface

# Clear existing rules
sudo tc qdisc del dev $INTERFACE root 2> /dev/null

# Add a root Token Bucket Filter (TBF)
# Rate limits to 500kbit, introduces a 400ms latency buffer to make doom-scrolling painful
sudo tc qdisc add dev $INTERFACE root handle 1: tbf rate 500kbit burst 32kbit latency 400ms

echo "[$(date +'%H:%M:%S')] Network throttled on $INTERFACE (500kbit limit)."

# Automatically remove the throttle after 60 seconds (aligns with Layer 4 BreathingSync lockout)
sleep 60
sudo tc qdisc del dev $INTERFACE root
echo "[$(date +'%H:%M:%S')] Network parameters restored to nominal."
