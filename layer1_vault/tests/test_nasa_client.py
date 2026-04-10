from __future__ import annotations

import unittest
from unittest.mock import patch
from urllib.error import URLError

from layer1_vault.src.nasa_client import SpaceWeatherClient


def _cached_snapshot_dict() -> dict[str, object]:
    return {
        "captured_at": "2026-04-10T12:00:00Z",
        "observed_at": "2026-04-10T11:59:00Z",
        "xray_flux_wm2": 5.1e-7,
        "observed_flux_wm2": 5.2e-7,
        "energy_band": "0.1-0.8nm",
        "satellite": "18",
        "flare_count_24h": 2,
        "strongest_flare_class": "M2.2",
        "primary_endpoint": "https://example.com/primary",
        "flare_endpoint": "https://example.com/flare?startDate=2026-04-09&endDate=2026-04-10",
        "quality": "live",
        "payload_digest": "digest-123",
        "primary_payload": [{"energy": "0.1-0.8nm", "time_tag": "2026-04-10T11:59:00Z", "flux": 5.1e-7}],
        "flare_payload": [{"classType": "M2.2"}],
        "status_note": "cached",
    }


class SpaceWeatherClientTests(unittest.TestCase):
    def test_select_primary_flux_sample_prefers_short_band(self) -> None:
        payload = [
            {"energy": "0.05-0.4nm", "flux": 3.3e-8, "time_tag": "old-wide"},
            {"energy": "0.1-0.8nm", "flux": 4.0e-7, "time_tag": "old-short"},
            {"energy": "0.1-0.8nm", "flux": 5.0e-7, "time_tag": "new-short"},
        ]
        selected = SpaceWeatherClient._select_primary_flux_sample(payload)
        self.assertEqual(selected["time_tag"], "new-short")

    def test_strongest_flare_ranks_class_then_magnitude(self) -> None:
        strongest = SpaceWeatherClient._strongest_flare(
            [
                {"classType": "M3.1"},
                {"classType": "X1.0"},
                {"classType": "X1.8"},
                {"classType": "C8.0"},
            ]
        )
        self.assertEqual(strongest, "X1.8")
        self.assertEqual(SpaceWeatherClient._strongest_flare([]), "NONE")

    def test_get_snapshot_uses_stale_cache_on_refresh_failure(self) -> None:
        client = SpaceWeatherClient(cache_ttl_seconds=0.0)
        cached = client._fallback_snapshot(TimeoutError("bootstrap"))
        cached = type(cached)(**{**cached.as_record(), **_cached_snapshot_dict()})
        client._cached_snapshot = cached
        client._cached_at = 0.0

        with patch.object(client, "_fetch_snapshot", side_effect=URLError("offline")):
            stale = client.get_snapshot(force_refresh=True)

        self.assertEqual(stale.quality, "stale")
        self.assertTrue(stale.status_note.startswith("refresh_failed:"))
        self.assertEqual(stale.payload_digest, cached.payload_digest)

    def test_get_snapshot_returns_degraded_fallback_without_cache(self) -> None:
        client = SpaceWeatherClient(cache_ttl_seconds=0.0)
        with patch.object(client, "_fetch_snapshot", side_effect=TimeoutError("slow")):
            snapshot = client.get_snapshot(force_refresh=True)

        self.assertEqual(snapshot.quality, "degraded-local")
        self.assertEqual(snapshot.flare_count_24h, 0)
        self.assertIn("fallback_due_to:TimeoutError", snapshot.status_note)

    def test_fetch_snapshot_maps_primary_and_flare_payloads(self) -> None:
        client = SpaceWeatherClient(primary_endpoint="https://example.com/primary", flare_endpoint="https://example.com/flare")
        primary_payload = [
            {"energy": "0.05-0.4nm", "flux": 1.1e-8, "satellite": "17", "time_tag": "2026-04-10T10:00:00Z"},
            {
                "energy": "0.1-0.8nm",
                "flux": 4.9e-7,
                "observed_flux": 5.0e-7,
                "satellite": "18",
                "time_tag": "2026-04-10T11:59:00Z",
            },
        ]
        flare_payload = [{"classType": "M1.2"}, {"classType": "X1.0"}]

        with patch.object(client, "_get_json", side_effect=[primary_payload, flare_payload]):
            snapshot = client._fetch_snapshot()

        self.assertEqual(snapshot.quality, "live")
        self.assertEqual(snapshot.energy_band, "0.1-0.8nm")
        self.assertEqual(snapshot.xray_flux_wm2, 4.9e-7)
        self.assertEqual(snapshot.observed_flux_wm2, 5.0e-7)
        self.assertEqual(snapshot.strongest_flare_class, "X1.0")
        self.assertTrue(snapshot.flare_endpoint.startswith("https://example.com/flare?"))


if __name__ == "__main__":
    unittest.main()
