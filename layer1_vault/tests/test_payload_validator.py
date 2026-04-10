from __future__ import annotations

import unittest

from layer1_vault.src.payload_validator import TelemetryValidationError, validate_telemetry_payload


def _valid_payload() -> dict[str, object]:
    return {
        "timestamp": "2026-04-10T13:00:00Z",
        "sequence": 22,
        "sensor_id": "sentinel-01",
        "team": "core-pulse",
        "employees": [
            {
                "user_id": "U-1",
                "display_name": "A",
                "focus_score": 0.8,
                "burnout_risk": 0.2,
                "activity_load": 0.6,
                "context_switches": 3,
                "keystroke_entropy": 0.7,
                "active_window": "VS Code",
                "distractions": ["reddit.com"],
                "flow_minutes": 25,
            },
            {
                "user_id": "U-2",
                "display_name": "B",
                "focus_score": 0.4,
                "burnout_risk": 0.6,
                "activity_load": 0.8,
                "context_switches": 5,
                "keystroke_entropy": 0.65,
                "active_window": "Terminal",
                "distractions": [],
                "flow_minutes": 15,
            },
        ],
        "system_load": {"cpu": 30.0, "memory": 45.0, "network_mbps": 12.0},
        "flags": ["simulation", "telemetry_raw"],
    }


class PayloadValidatorTests(unittest.TestCase):
    def test_validate_returns_expected_summary_metrics(self) -> None:
        summary = validate_telemetry_payload(_valid_payload())
        self.assertEqual(summary.sequence, 22)
        self.assertEqual(summary.employee_count, 2)
        self.assertAlmostEqual(summary.avg_focus_score, 0.6)
        self.assertAlmostEqual(summary.avg_burnout_risk, 0.4)
        self.assertAlmostEqual(summary.avg_activity_load, 0.7)
        self.assertEqual(summary.flags_count, 2)

    def test_validate_rejects_out_of_range_focus_score(self) -> None:
        payload = _valid_payload()
        employees = payload["employees"]  # type: ignore[index]
        first = employees[0]  # type: ignore[index]
        first["focus_score"] = 1.2  # type: ignore[index]

        with self.assertRaises(TelemetryValidationError):
            validate_telemetry_payload(payload)

    def test_validate_rejects_non_string_distraction(self) -> None:
        payload = _valid_payload()
        employees = payload["employees"]  # type: ignore[index]
        first = employees[0]  # type: ignore[index]
        first["distractions"] = ["reddit.com", 42]  # type: ignore[index]

        with self.assertRaises(TelemetryValidationError):
            validate_telemetry_payload(payload)


if __name__ == "__main__":
    unittest.main()
