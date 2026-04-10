from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


LOGGER = logging.getLogger("core_pulse.vault.nasa")

# Exact endpoints used by Layer 1.
SWPC_PRIMARY_XRAY_URL = "https://services.swpc.noaa.gov/json/goes/primary/xrays-1-day.json"
NASA_DONKI_FLR_URL = "https://kauai.ccmc.gsfc.nasa.gov/DONKI/WS/get/FLR"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_utc(moment: datetime | None = None) -> str:
    current = moment or utc_now()
    return current.isoformat(timespec="seconds").replace("+00:00", "Z")


def flare_rank(class_type: str | None) -> tuple[int, float]:
    if not class_type:
        return (0, 0.0)

    band_weights = {
        "A": 1,
        "B": 2,
        "C": 3,
        "M": 4,
        "X": 5,
    }
    band = class_type[0].upper()
    try:
        magnitude = float(class_type[1:])
    except (TypeError, ValueError):
        magnitude = 0.0
    return (band_weights.get(band, 0), magnitude)


@dataclass(frozen=True, slots=True)
class SpaceWeatherSnapshot:
    captured_at: str
    observed_at: str
    xray_flux_wm2: float
    observed_flux_wm2: float
    energy_band: str
    satellite: str
    flare_count_24h: int
    strongest_flare_class: str
    primary_endpoint: str
    flare_endpoint: str
    quality: str
    payload_digest: str
    primary_payload: list[dict[str, Any]]
    flare_payload: list[dict[str, Any]]
    status_note: str = ""

    def as_record(self) -> dict[str, Any]:
        return {
            "captured_at": self.captured_at,
            "observed_at": self.observed_at,
            "xray_flux_wm2": self.xray_flux_wm2,
            "observed_flux_wm2": self.observed_flux_wm2,
            "energy_band": self.energy_band,
            "satellite": self.satellite,
            "flare_count_24h": self.flare_count_24h,
            "strongest_flare_class": self.strongest_flare_class,
            "primary_endpoint": self.primary_endpoint,
            "flare_endpoint": self.flare_endpoint,
            "quality": self.quality,
            "payload_digest": self.payload_digest,
            "status_note": self.status_note,
            "primary_payload": self.primary_payload,
            "flare_payload": self.flare_payload,
        }


class SpaceWeatherClient:
    def __init__(
        self,
        primary_endpoint: str = SWPC_PRIMARY_XRAY_URL,
        flare_endpoint: str = NASA_DONKI_FLR_URL,
        timeout_seconds: float = 10.0,
        cache_ttl_seconds: float = 120.0,
    ) -> None:
        self.primary_endpoint = primary_endpoint
        self.flare_endpoint = flare_endpoint
        self.timeout_seconds = timeout_seconds
        self.cache_ttl_seconds = cache_ttl_seconds
        self._cached_snapshot: SpaceWeatherSnapshot | None = None
        self._cached_at = 0.0

    def get_snapshot(self, force_refresh: bool = False) -> SpaceWeatherSnapshot:
        now = time.monotonic()
        if not force_refresh and self._cached_snapshot and (now - self._cached_at) < self.cache_ttl_seconds:
            return self._cached_snapshot

        try:
            snapshot = self._fetch_snapshot()
        except (HTTPError, URLError, TimeoutError, ValueError, OSError) as exc:
            LOGGER.warning("space weather refresh failed: %s", exc)
            if self._cached_snapshot is not None:
                stale = replace(
                    self._cached_snapshot,
                    captured_at=iso_utc(),
                    quality="stale",
                    status_note=f"refresh_failed:{exc.__class__.__name__}",
                )
                self._cached_snapshot = stale
                self._cached_at = now
                return stale
            snapshot = self._fallback_snapshot(exc)

        self._cached_snapshot = snapshot
        self._cached_at = now
        return snapshot

    def _fetch_snapshot(self) -> SpaceWeatherSnapshot:
        primary_payload = self._get_json(self.primary_endpoint)
        if not isinstance(primary_payload, list) or not primary_payload:
            raise ValueError("primary X-ray feed returned an unexpected payload")

        selected = self._select_primary_flux_sample(primary_payload)
        captured_at = utc_now()
        flare_payload = self._fetch_flares(captured_at)
        digest = hashlib.sha256(
            json.dumps(
                {
                    "primary": selected,
                    "flare_sample": flare_payload[:8],
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()

        return SpaceWeatherSnapshot(
            captured_at=iso_utc(captured_at),
            observed_at=str(selected.get("time_tag", iso_utc(captured_at))),
            xray_flux_wm2=float(selected.get("flux", 0.0)),
            observed_flux_wm2=float(selected.get("observed_flux", selected.get("flux", 0.0))),
            energy_band=str(selected.get("energy", "0.1-0.8nm")),
            satellite=str(selected.get("satellite", "unknown")),
            flare_count_24h=len(flare_payload),
            strongest_flare_class=self._strongest_flare(flare_payload),
            primary_endpoint=self.primary_endpoint,
            flare_endpoint=self._format_flare_endpoint(captured_at),
            quality="live",
            payload_digest=digest,
            primary_payload=primary_payload[-16:],
            flare_payload=flare_payload,
            status_note="live_space_weather",
        )

    def _fetch_flares(self, captured_at: datetime) -> list[dict[str, Any]]:
        flare_url = self._format_flare_endpoint(captured_at)
        payload = self._get_json(flare_url)
        if isinstance(payload, list):
            return payload
        return []

    def _format_flare_endpoint(self, captured_at: datetime) -> str:
        query = urlencode(
            {
                "startDate": (captured_at - timedelta(days=1)).date().isoformat(),
                "endDate": captured_at.date().isoformat(),
            }
        )
        return f"{self.flare_endpoint}?{query}"

    def _get_json(self, url: str) -> Any:
        request = Request(url, headers={"User-Agent": "CORE-PULSE-Layer1/1.0"})
        with urlopen(request, timeout=self.timeout_seconds) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return json.loads(response.read().decode(charset))

    @staticmethod
    def _select_primary_flux_sample(primary_payload: list[dict[str, Any]]) -> dict[str, Any]:
        short_band = [entry for entry in primary_payload if entry.get("energy") == "0.1-0.8nm"]
        source = short_band or primary_payload
        return source[-1]

    @staticmethod
    def _strongest_flare(flare_payload: list[dict[str, Any]]) -> str:
        if not flare_payload:
            return "NONE"
        strongest = max(flare_payload, key=lambda item: flare_rank(item.get("classType")))
        return str(strongest.get("classType", "UNKNOWN"))

    def _fallback_snapshot(self, exc: Exception) -> SpaceWeatherSnapshot:
        captured_at = utc_now()
        payload_digest = hashlib.sha256(
            f"{captured_at.isoformat()}|{exc.__class__.__name__}|fallback".encode("utf-8")
        ).hexdigest()
        return SpaceWeatherSnapshot(
            captured_at=iso_utc(captured_at),
            observed_at=iso_utc(captured_at),
            xray_flux_wm2=0.0,
            observed_flux_wm2=0.0,
            energy_band="0.1-0.8nm",
            satellite="fallback",
            flare_count_24h=0,
            strongest_flare_class="NONE",
            primary_endpoint=self.primary_endpoint,
            flare_endpoint=self._format_flare_endpoint(captured_at),
            quality="degraded-local",
            payload_digest=payload_digest,
            primary_payload=[],
            flare_payload=[],
            status_note=f"fallback_due_to:{exc.__class__.__name__}",
        )
