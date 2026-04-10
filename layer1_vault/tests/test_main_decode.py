from __future__ import annotations

import unittest

from layer1_vault.src.main import CosmicVaultDaemon


class DecodeFramesTests(unittest.TestCase):
    def test_decode_two_frames(self) -> None:
        topic, payload = CosmicVaultDaemon._decode_frames([b"telemetry_raw", b'{"sequence":1}'])
        self.assertEqual(topic, "telemetry_raw")
        self.assertEqual(payload, b'{"sequence":1}')

    def test_decode_single_frame_with_embedded_topic(self) -> None:
        topic, payload = CosmicVaultDaemon._decode_frames([b"telemetry_raw {\"sequence\":2}"])
        self.assertEqual(topic, "telemetry_raw")
        self.assertEqual(payload, b'{"sequence":2}')

    def test_decode_single_frame_without_topic_defaults(self) -> None:
        topic, payload = CosmicVaultDaemon._decode_frames([b'{"sequence":3}'])
        self.assertEqual(topic, "telemetry_raw")
        self.assertEqual(payload, b'{"sequence":3}')

    def test_decode_empty_frame_list_raises(self) -> None:
        with self.assertRaises(ValueError):
            CosmicVaultDaemon._decode_frames([])


if __name__ == "__main__":
    unittest.main()
