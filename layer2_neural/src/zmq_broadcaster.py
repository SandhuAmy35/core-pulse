import zmq
import json
import logging

class BurnoutBroadcaster:
    def __init__(self, port=5555, topic="bp_critical"):
        self.port = port
        self.topic = topic
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.PUB)
        self.socket.bind(f"tcp://*:{self.port}")
        logging.info(f"[*] ZeroMQ Broadcaster bound to tcp://*:{self.port} on topic '{self.topic}'")

    def broadcast(self, payload: dict):
        """Packages the dict into JSON and fires it over the socket."""
        try:
            json_payload = json.dumps(payload)
            message = f"{self.topic} {json_payload}"
            self.socket.send_string(message)
            logging.info(f"[+] Broadcast Success: Bp = {payload.get('burnout_probability')}%")
        except Exception as e:
            logging.error(f"[!] ZeroMQ Broadcast failed: {e}")

    def shutdown(self):
        self.socket.close()
        self.context.term()