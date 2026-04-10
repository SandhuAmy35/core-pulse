from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from itertools import combinations
from typing import Any

import websockets
import zmq
import zmq.asyncio


LOGGER = logging.getLogger("core_pulse.bridge")


def clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


@dataclass(slots=True)
class BridgeConfig:
    zmq_endpoint: str
    zmq_topic: str
    websocket_host: str
    websocket_port: int
    max_broadcasts: int | None
    log_level: str


class DashboardTransformer:
    def __init__(self) -> None:
        self._history: deque[dict[str, float]] = deque(maxlen=24)

    @staticmethod
    def _risk_band(productivity: float, burnout: float, context_pressure: float) -> str:
        if burnout >= 72 or context_pressure >= 70:
            return "CRITICAL"
        if burnout >= 56 or productivity <= 54:
            return "ELEVATED"
        if burnout >= 42:
            return "WATCH"
        return "STABLE"

    @staticmethod
    def _synergy_score(a: dict[str, Any], b: dict[str, Any]) -> float:
        shared_distractions = len(set(a["distractions"]) & set(b["distractions"]))
        friction = (
            abs(a["focus_score"] - b["focus_score"]) * 0.34
            + abs(a["burnout_risk"] - b["burnout_risk"]) * 0.31
            + abs(a["activity_load"] - b["activity_load"]) * 0.20
            + abs(a["context_switches"] - b["context_switches"]) / 18 * 0.15
            + shared_distractions * 0.06
        )
        return round(clamp(friction, 0, 1), 3)

    def transform(self, payload: dict[str, Any]) -> dict[str, Any]:
        employees = payload["employees"]
        productivity = round(sum(member["productivity_index"] for member in employees) / len(employees) * 100, 1)
        burnout = round(sum(member["burnout_risk"] for member in employees) / len(employees) * 100, 1)
        context_pressure = round(
            sum(member["context_switches"] for member in employees) / len(employees) / 18 * 100,
            1,
        )
        focus_stability = round(sum(member["focus_score"] for member in employees) / len(employees) * 100, 1)

        previous = self._history[-1] if self._history else None
        self._history.append(
            {
                "productivity": productivity,
                "burnout": burnout,
                "context": context_pressure,
            }
        )

        trend = {
            "throughput_delta": round(productivity - previous["productivity"], 1) if previous else 0.0,
            "burnout_delta": round(burnout - previous["burnout"], 1) if previous else 0.0,
            "focus_stability": focus_stability,
        }

        matrix_people = employees[:6]
        synergy_edges = [
            {
                "source": left["display_name"],
                "target": right["display_name"],
                "friction": self._synergy_score(left, right),
            }
            for left, right in combinations(matrix_people, 2)
        ]

        top_alerts = [
            {
                "user_id": member["user_id"],
                "display_name": member["display_name"],
                "message": f"{member['display_name']} showing burnout risk spike",
                "severity": "critical" if member["burnout_risk"] >= 0.75 else "watch",
            }
            for member in sorted(employees, key=lambda item: item["burnout_risk"], reverse=True)[:3]
        ]

        return {
            "type": "dashboard_frame",
            "timestamp": payload["timestamp"],
            "received_at": utc_now(),
            "sequence": payload["sequence"],
            "headline": {
                "team_productivity": productivity,
                "burnout_pressure": burnout,
                "context_switch_pressure": context_pressure,
                "employees_online": len(employees),
                "risk_band": self._risk_band(productivity, burnout, context_pressure),
            },
            "trend": trend,
            "system_load": payload["system_load"],
            "employees": employees,
            "synergy_matrix": {
                "labels": [member["display_name"] for member in matrix_people],
                "edges": synergy_edges,
            },
            "alerts": top_alerts,
            "flags": payload.get("flags", []),
            "source": {
                "zmq_topic": "telemetry_raw",
                "sensor_id": payload.get("sensor_id", "unknown"),
                "team": payload.get("team", "unknown"),
            },
        }


class ZeroMqToWebsocketBridge:
    def __init__(self, config: BridgeConfig) -> None:
        self._config = config
        self._context = zmq.asyncio.Context.instance()
        self._clients: set[Any] = set()
        self._transformer = DashboardTransformer()
        self._broadcast_count = 0
        self._last_frame: dict[str, Any] | None = None
        self._stop_event = asyncio.Event()

    async def _handle_client(self, websocket: Any) -> None:
        self._clients.add(websocket)
        LOGGER.info("dashboard client connected (%s active)", len(self._clients))
        try:
            if self._last_frame is not None:
                await websocket.send(json.dumps(self._last_frame))
            await websocket.wait_closed()
        finally:
            self._clients.discard(websocket)
            LOGGER.info("dashboard client disconnected (%s active)", len(self._clients))

    async def _broadcast(self, frame: dict[str, Any]) -> None:
        self._last_frame = frame
        if not self._clients:
            return

        dead_clients = []
        payload = json.dumps(frame, separators=(",", ":"), sort_keys=True)
        for client in self._clients:
            try:
                await client.send(payload)
            except Exception:
                dead_clients.append(client)

        for client in dead_clients:
            self._clients.discard(client)

    @staticmethod
    def _coerce_frames(raw_frames: list[bytes]) -> tuple[str, bytes]:
        if len(raw_frames) >= 2:
            return raw_frames[0].decode("utf-8"), raw_frames[1]
        if not raw_frames:
            raise ValueError("received empty ZeroMQ frame set")

        blob = raw_frames[0]
        if b" " in blob:
            topic_blob, payload_blob = blob.split(b" ", 1)
            return topic_blob.decode("utf-8"), payload_blob
        return "telemetry_raw", blob

    async def _consume_forever(self) -> None:
        socket = self._context.socket(zmq.SUB)
        socket.connect(self._config.zmq_endpoint)
        socket.setsockopt_string(zmq.SUBSCRIBE, self._config.zmq_topic)
        LOGGER.info("subscribed to %s on %s", self._config.zmq_topic, self._config.zmq_endpoint)

        try:
            while not self._stop_event.is_set():
                raw_frames = await socket.recv_multipart()
                topic, payload_blob = self._coerce_frames(list(raw_frames))
                payload = json.loads(payload_blob.decode("utf-8"))
                frame = self._transformer.transform(payload)
                frame["source"]["zmq_topic"] = topic
                await self._broadcast(frame)

                self._broadcast_count += 1
                LOGGER.info(
                    "broadcast seq=%s productivity=%s burnout=%s clients=%s",
                    frame["sequence"],
                    frame["headline"]["team_productivity"],
                    frame["headline"]["burnout_pressure"],
                    len(self._clients),
                )
                if self._config.max_broadcasts and self._broadcast_count >= self._config.max_broadcasts:
                    self._stop_event.set()
                    break
        finally:
            socket.close(0)

    async def run(self) -> None:
        async with websockets.serve(
            self._handle_client,
            self._config.websocket_host,
            self._config.websocket_port,
        ):
            LOGGER.info(
                "websocket bridge live on ws://%s:%s",
                self._config.websocket_host,
                self._config.websocket_port,
            )
            await self._consume_forever()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bridge ZeroMQ telemetry to WebSocket dashboards.")
    parser.add_argument("--zmq-endpoint", default="tcp://127.0.0.1:5557")
    parser.add_argument("--zmq-topic", default="telemetry_raw")
    parser.add_argument("--websocket-host", default="127.0.0.1")
    parser.add_argument("--websocket-port", type=int, default=8765)
    parser.add_argument("--max-broadcasts", type=int, default=None)
    parser.add_argument("--log-level", default="INFO")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if sys.platform.startswith("win"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(message)s",
    )
    config = BridgeConfig(
        zmq_endpoint=args.zmq_endpoint,
        zmq_topic=args.zmq_topic,
        websocket_host=args.websocket_host,
        websocket_port=args.websocket_port,
        max_broadcasts=args.max_broadcasts,
        log_level=args.log_level,
    )
    asyncio.run(ZeroMqToWebsocketBridge(config).run())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
