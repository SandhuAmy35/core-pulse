from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import socket
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from .nasa_client import SpaceWeatherSnapshot, iso_utc
except ImportError:
    from nasa_client import SpaceWeatherSnapshot, iso_utc


def stable_json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


@dataclass(frozen=True, slots=True)
class EntropyMaterial:
    created_at: str
    entropy_digest: str
    key_bytes: bytes
    key_fingerprint: str
    nonce_bytes: bytes
    pool_size: int
    payload_sha256: str
    space_weather_quality: str
    evidence: dict[str, Any]


class EntropyEngine:
    def __init__(self, machine_salt: bytes | None = None) -> None:
        self._machine_salt = machine_salt or os.urandom(32)

    def build_entropy_material(
        self,
        snapshot: SpaceWeatherSnapshot,
        telemetry_payload: dict[str, Any],
        *,
        extra_context: dict[str, Any] | None = None,
    ) -> EntropyMaterial:
        payload_bytes = stable_json_bytes(telemetry_payload)
        local_entropy = self._collect_local_entropy(telemetry_payload)
        context_bytes = stable_json_bytes(extra_context or {})
        snapshot_bytes = stable_json_bytes(snapshot.as_record())

        parts = [
            b"core-pulse-layer1",
            self._machine_salt,
            snapshot_bytes,
            payload_bytes,
            context_bytes,
            local_entropy,
        ]
        pool = b"|".join(parts)
        key_bytes = hashlib.sha256(pool).digest()
        entropy_digest = hashlib.sha256(b"digest|" + pool).hexdigest()
        nonce_bytes = hashlib.sha256(b"nonce|" + pool + os.urandom(16)).digest()[:12]
        payload_sha256 = hashlib.sha256(payload_bytes).hexdigest()

        evidence = {
            "snapshot_digest": snapshot.payload_digest,
            "space_weather_quality": snapshot.quality,
            "xray_flux_wm2": snapshot.xray_flux_wm2,
            "flare_count_24h": snapshot.flare_count_24h,
            "strongest_flare_class": snapshot.strongest_flare_class,
            "payload_sha256": payload_sha256,
        }

        return EntropyMaterial(
            created_at=iso_utc(),
            entropy_digest=entropy_digest,
            key_bytes=key_bytes,
            key_fingerprint=hashlib.sha256(key_bytes).hexdigest()[:16],
            nonce_bytes=nonce_bytes,
            pool_size=len(pool),
            payload_sha256=payload_sha256,
            space_weather_quality=snapshot.quality,
            evidence=evidence,
        )

    def _collect_local_entropy(self, telemetry_payload: dict[str, Any]) -> bytes:
        telemetry_summary = {
            "sequence": telemetry_payload.get("sequence"),
            "employee_count": len(telemetry_payload.get("employees", [])),
            "system_load": telemetry_payload.get("system_load", {}),
        }
        perf_samples = []
        last_tick = time.perf_counter_ns()
        for _ in range(8):
            current = time.perf_counter_ns()
            perf_samples.append(current - last_tick)
            last_tick = current

        usage = shutil.disk_usage(Path.cwd())
        loadavg = getattr(os, "getloadavg", lambda: (0.0, 0.0, 0.0))()

        machine_view = {
            "pid": os.getpid(),
            "native_thread_id": getattr(threading, "get_native_id", threading.get_ident)(),
            "hostname": socket.gethostname(),
            "platform": platform.platform(),
            "time_ns": time.time_ns(),
            "monotonic_ns": time.monotonic_ns(),
            "perf_samples": perf_samples,
            "cwd_free_bytes": usage.free,
            "cwd_used_bytes": usage.used,
            "loadavg": loadavg,
            "telemetry_summary": telemetry_summary,
        }
        return stable_json_bytes(machine_view)
