from __future__ import annotations

import argparse
import json
import random
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import zmq


def clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


WINDOW_POOL = (
    "VS Code",
    "Cursor",
    "Slack",
    "Notion",
    "Jira",
    "GitHub",
    "Figma",
    "Terminal",
)

DISTRACTION_POOL = (
    "youtube.com",
    "discord.com",
    "reddit.com",
    "news.ycombinator.com",
    "instagram.com",
)

NAMES = (
    "Aarav",
    "Mira",
    "Kabir",
    "Isha",
    "Neel",
    "Tara",
    "Rohan",
    "Siya",
)


@dataclass(slots=True)
class EmployeeState:
    user_id: str
    display_name: str
    focus_score: float
    burnout_risk: float
    activity_load: float
    context_switches: int
    keystroke_entropy: float
    flow_minutes: int
    active_window: str

    def tick(self, rng: random.Random) -> dict[str, Any]:
        self.focus_score = clamp(self.focus_score + rng.uniform(-0.08, 0.08), 0.18, 0.96)
        self.activity_load = clamp(self.activity_load + rng.uniform(-0.07, 0.07), 0.24, 0.97)
        self.keystroke_entropy = clamp(
            self.keystroke_entropy + rng.uniform(-0.05, 0.05),
            0.35,
            0.99,
        )
        burnout_delta = ((1 - self.focus_score) * 0.08) + rng.uniform(-0.03, 0.05)
        self.burnout_risk = clamp(self.burnout_risk + burnout_delta, 0.08, 0.98)
        self.context_switches = int(clamp(self.context_switches + rng.randint(-2, 3), 1, 18))
        flow_direction = 6 if self.focus_score > 0.68 else -5
        self.flow_minutes = int(clamp(self.flow_minutes + flow_direction + rng.randint(-4, 5), 5, 110))
        self.active_window = rng.choice(WINDOW_POOL)

        distraction_bias = 1 - self.focus_score + (self.context_switches / 22)
        distraction_count = 0
        if distraction_bias > 0.35:
            distraction_count = 1
        if distraction_bias > 0.62:
            distraction_count = 2

        distractions = rng.sample(DISTRACTION_POOL, k=distraction_count) if distraction_count else []
        productivity_index = clamp(
            (self.focus_score * 0.52) + (self.activity_load * 0.38) + (self.keystroke_entropy * 0.10)
            - (self.burnout_risk * 0.25)
            - ((self.context_switches / 18) * 0.15),
            0,
            1,
        )

        return {
            "user_id": self.user_id,
            "display_name": self.display_name,
            "focus_score": round(self.focus_score, 3),
            "burnout_risk": round(self.burnout_risk, 3),
            "activity_load": round(self.activity_load, 3),
            "context_switches": self.context_switches,
            "keystroke_entropy": round(self.keystroke_entropy, 3),
            "flow_minutes": self.flow_minutes,
            "active_window": self.active_window,
            "distractions": distractions,
            "productivity_index": round(productivity_index, 3),
        }


class TelemetrySimulator:
    def __init__(self, seed: int | None = None) -> None:
        self._rng = random.Random(seed)
        self._sequence = 0
        self._employees = [
            EmployeeState(
                user_id=f"U-{8400 + index}",
                display_name=name,
                focus_score=self._rng.uniform(0.45, 0.86),
                burnout_risk=self._rng.uniform(0.12, 0.55),
                activity_load=self._rng.uniform(0.40, 0.88),
                context_switches=self._rng.randint(2, 10),
                keystroke_entropy=self._rng.uniform(0.52, 0.93),
                flow_minutes=self._rng.randint(18, 72),
                active_window=self._rng.choice(WINDOW_POOL),
            )
            for index, name in enumerate(NAMES, start=1)
        ]

    def next_payload(self) -> dict[str, Any]:
        self._sequence += 1
        employees = [employee.tick(self._rng) for employee in self._employees]
        team_productivity = sum(member["productivity_index"] for member in employees) / len(employees)
        burnout_pressure = sum(member["burnout_risk"] for member in employees) / len(employees)

        payload = {
            "timestamp": utc_now(),
            "sequence": self._sequence,
            "sensor_id": "sentinel-sim-01",
            "team": "hack-o-mania-core-pulse",
            "employees": employees,
            "system_load": {
                "cpu": round(self._rng.uniform(28, 81), 2),
                "memory": round(self._rng.uniform(34, 78), 2),
                "network_mbps": round(self._rng.uniform(3.2, 42.8), 2),
            },
            "flags": [
                "simulation",
                "telemetry_raw",
                "e2e_pipe_ready",
                "elevated_attention" if burnout_pressure > 0.6 else "stable",
            ],
            "summary": {
                "team_productivity": round(team_productivity, 3),
                "burnout_pressure": round(burnout_pressure, 3),
            },
        }
        return payload


def publish_loop(endpoint: str, topic: str, interval: float, max_messages: int | None, seed: int | None) -> None:
    context = zmq.Context()
    socket = context.socket(zmq.PUB)
    socket.bind(endpoint)

    simulator = TelemetrySimulator(seed=seed)
    sent = 0

    try:
        while max_messages is None or sent < max_messages:
            payload = simulator.next_payload()
            socket.send_multipart(
                [
                    topic.encode("utf-8"),
                    json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"),
                ]
            )
            sent += 1
            print(
                f"[layer0] seq={payload['sequence']:03d} "
                f"productivity={payload['summary']['team_productivity']:.2f} "
                f"burnout={payload['summary']['burnout_pressure']:.2f}"
            )
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\n[layer0] publisher interrupted")
    finally:
        socket.close(0)
        context.term()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Mock Layer 0 publisher for ZeroMQ integration.")
    parser.add_argument("--endpoint", default="tcp://127.0.0.1:5557")
    parser.add_argument("--topic", default="telemetry_raw")
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument("--messages", type=int, default=None, help="Publish a finite number of frames.")
    parser.add_argument("--seed", type=int, default=7)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    publish_loop(
        endpoint=args.endpoint,
        topic=args.topic,
        interval=args.interval,
        max_messages=args.messages,
        seed=args.seed,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
