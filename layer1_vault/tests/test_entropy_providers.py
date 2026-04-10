from __future__ import annotations

import base64
import unittest

from layer1_vault.src.entropy_providers import (
    NasaDonkiDigestClient,
    OutshiftQRNGClient,
    ProviderError,
    RandomOrgClient,
)
from layer1_vault.src.nasa_client import SpaceWeatherSnapshot


def _snapshot(payload_digest: str = "snapshot-digest-001") -> SpaceWeatherSnapshot:
    return SpaceWeatherSnapshot(
        captured_at="2026-04-10T12:00:00Z",
        observed_at="2026-04-10T11:59:00Z",
        xray_flux_wm2=3.7e-7,
        observed_flux_wm2=3.8e-7,
        energy_band="0.1-0.8nm",
        satellite="18",
        flare_count_24h=1,
        strongest_flare_class="M1.0",
        primary_endpoint="https://example.com/primary",
        flare_endpoint="https://example.com/flare?startDate=2026-04-09&endDate=2026-04-10",
        quality="live",
        payload_digest=payload_digest,
        primary_payload=[{"time_tag": "2026-04-10T11:59:00Z", "flux": 3.7e-7}],
        flare_payload=[{"classType": "M1.0"}],
        status_note="test",
    )


class EntropyProviderTests(unittest.TestCase):
    def test_outshift_parse_bytes_candidate_supports_list_hex_and_base64(self) -> None:
        parsed_list = OutshiftQRNGClient._parse_bytes_candidate([0, 1, 255])
        parsed_hex = OutshiftQRNGClient._parse_bytes_candidate("0011ff")
        parsed_base64 = OutshiftQRNGClient._parse_bytes_candidate(base64.b64encode(b"abcd").decode("ascii"))

        self.assertEqual(parsed_list, b"\x00\x01\xff")
        self.assertEqual(parsed_hex, b"\x00\x11\xff")
        self.assertEqual(parsed_base64, b"abcd")

    def test_outshift_extract_bytes_rejects_short_payloads(self) -> None:
        with self.assertRaises(ProviderError) as ctx:
            OutshiftQRNGClient._extract_bytes({"bytes": "00"}, minimum_bytes=2)
        self.assertEqual(ctx.exception.code, "invalid_payload")

    def test_random_org_extract_bytes_reads_result_block(self) -> None:
        payload = {"result": {"random": {"data": ["0011223344"]}}}
        parsed = RandomOrgClient._extract_bytes(payload, minimum_bytes=4)
        self.assertEqual(parsed, bytes.fromhex("00112233"))

    def test_random_org_extract_bytes_maps_quota_error(self) -> None:
        with self.assertRaises(ProviderError) as ctx:
            RandomOrgClient._extract_bytes({"error": {"code": 420, "message": "quota"}}, minimum_bytes=1)
        self.assertEqual(ctx.exception.code, "quota_exceeded")
        self.assertFalse(ctx.exception.retriable)

    def test_nasa_donki_digest_client_requires_non_empty_digest(self) -> None:
        client = NasaDonkiDigestClient()
        with self.assertRaises(ProviderError) as ctx:
            client.get_digest(_snapshot(payload_digest=""))
        self.assertEqual(ctx.exception.code, "invalid_payload")

    def test_nasa_donki_digest_client_returns_context_sample(self) -> None:
        client = NasaDonkiDigestClient()
        sample = client.get_digest(_snapshot())
        self.assertEqual(sample.provider, client.name)
        self.assertEqual(sample.digest_hex, "snapshot-digest-001")
        self.assertEqual(sample.quality, "live")
        self.assertEqual(sample.status, "ok")


if __name__ == "__main__":
    unittest.main()
