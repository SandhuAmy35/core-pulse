import zmq
import json

context = zmq.Context()
socket = context.socket(zmq.SUB)
socket.connect("tcp://localhost:5555")

# Subscribe to the exact topic our broadcaster is using
socket.setsockopt_string(zmq.SUBSCRIBE, "bp_critical")

print("[*] The Ear is listening for AI Broadcasts on port 5555...")

try:
    while True:
        # Receive the raw message
        message = socket.recv_string()
        
        # Split the topic ("bp_critical") from the JSON payload
        topic, payload_str = message.split(" ", 1)
        
        # Parse it nicely
        payload = json.loads(payload_str)
        print(f"\n[ALARM RECEIVED] Status: {payload.get('status')} | Burnout: {payload.get('burnout_probability')}")
        print(f"Full Payload: {payload}")
        
except KeyboardInterrupt:
    print("\n[*] Shutting down listener.")