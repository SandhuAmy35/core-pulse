from __future__ import annotations

import json
import shutil
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path

from layer1_vault.src.crypto_aes import decrypt_payload, encrypt_payload
from layer1_vault.src.db_manager import VaultDatabase
from layer1_vault.src.nasa_client import SpaceWeatherSnapshot
from layer1_vault.src.payload_validator import TelemetryValidationError, validate_telemetry_payload
from layer1_vault.src.proof_engine import build_vault_proof, verify_integrity_proof
from layer1_vault.src.trng_engine import EntropyEngine
from layer1_vault.src.vault_report import build_report


def _temp_root() -> Path:
    root = Path(__file__).resolve().parents[1] / "data" / "test_artifacts"
    root.mkdir(parents=True, exist_ok=True)
    return root


@contextmanager
def _temp_dir(prefix: str) -> Path:
    path = _temp_root() / f"{prefix}{uuid.uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def fake_snapshot() -> SpaceWeatherSnapshot:
    return SpaceWeatherSnapshot(
        captured_at="2026-04-10T12:00:00Z",
        observed_at="2026-04-10T11:59:00Z",
        xray_flux_wm2=4.7e-7,
        observed_flux_wm2=4.8e-7,
        energy_band="0.1-0.8nm",
        satellite="18",
        flare_count_24h=1,
        strongest_flare_class="M1.0",
        primary_endpoint="https://services.swpc.noaa.gov/json/goes/primary/xrays-1-day.json",
        flare_endpoint="https://kauai.ccmc.gsfc.nasa.gov/DONKI/WS/get/FLR?startDate=2026-04-09&endDate=2026-04-10",
        quality="live",
        payload_digest="abc123digest",
        primary_payload=[{"time_tag": "2026-04-10T11:59:00Z", "flux": 4.7e-7}],
        flare_payload=[{"classType": "M1.0"}],
        status_note="test",
    )


class VaultPipelineTests(unittest.TestCase):
    def test_payload_validation_rejects_missing_fields(self) -> None:
        with self.assertRaises(TelemetryValidationError):
            validate_telemetry_payload({"sequence": 1})

    def test_encrypt_round_trip(self) -> None:
        payload = {
            "sequence": 7,
            "timestamp": "2026-04-10T12:00:00Z",
            "sensor_id": "sentinel-test",
            "team": "core-pulse",
            "employees": [
                {
                    "user_id": "U-7",
                    "display_name": "Tester One",
                    "focus_score": 0.9,
                    "burnout_risk": 0.2,
                    "activity_load": 0.6,
                    "context_switches": 2,
                    "keystroke_entropy": 0.7,
                    "flow_minutes": 25,
                    "active_window": "Terminal",
                    "distractions": [],
                }
            ],
            "system_load": {"cpu": 12.0, "memory": 24.0, "network_mbps": 3.0},
            "flags": ["test"],
        }
        telemetry_summary = validate_telemetry_payload(payload)
        with _temp_dir("vault-pipeline-") as temp_dir:
            journal_path = temp_dir / "entropy.wal"
            engine = EntropyEngine(
                machine_salt=b"layer1-test-salt-000000000000000",
                journal_path=journal_path,
            )
            entropy = engine.build_entropy_material(fake_snapshot(), payload, extra_context={"topic": "telemetry_raw"})
            encrypted = encrypt_payload(payload, entropy, topic="telemetry_raw")
            proof = build_vault_proof(
                encrypted=encrypted,
                entropy=entropy,
                snapshot=fake_snapshot(),
                telemetry_summary=telemetry_summary,
            )
            recovered = decrypt_payload(encrypted, entropy.key_bytes)
            self.assertEqual(recovered["sequence"], payload["sequence"])
            self.assertEqual(recovered["sensor_id"], payload["sensor_id"])
            self.assertEqual(entropy.entropy_quality_tier, "BRONZE")
            self.assertGreater(entropy.journal_sequence, 0)
            self.assertTrue(entropy.journal_merkle_root)
            self.assertEqual(len(proof.integrity_proof), 64)
            self.assertTrue(verify_integrity_proof(proof.proof_payload_json, proof.integrity_proof))
            self.assertFalse(verify_integrity_proof(proof.proof_payload_json, "0" * 64))
            proof_payload = json.loads(proof.proof_payload_json)
            self.assertEqual(proof_payload["entropy_quality_tier"], "BRONZE")
            self.assertEqual(proof_payload["entropy_policy_version"], "v1")
            self.assertEqual(proof_payload["entropy_journal_sequence"], entropy.journal_sequence)
            self.assertEqual(proof_payload["entropy_journal_merkle_root"], entropy.journal_merkle_root)

    def test_database_persistence(self) -> None:
        payload = {
            "sequence": 11,
            "timestamp": "2026-04-10T12:30:00Z",
            "sensor_id": "sentinel-test",
            "team": "core-pulse",
            "employees": [
                {
                    "user_id": "U-11",
                    "display_name": "Tester Two",
                    "focus_score": 0.77,
                    "burnout_risk": 0.31,
                    "activity_load": 0.68,
                    "context_switches": 4,
                    "keystroke_entropy": 0.81,
                    "flow_minutes": 33,
                    "active_window": "VS Code",
                    "distractions": ["reddit.com"],
                }
            ],
            "system_load": {"cpu": 31.0, "memory": 44.0, "network_mbps": 8.5},
            "flags": ["test"],
        }
        telemetry_summary = validate_telemetry_payload(payload)
        with _temp_dir("vault-pipeline-") as temp_dir:
            db_path = temp_dir / "vault.db"
            journal_path = temp_dir / "entropy.wal"
            engine = EntropyEngine(
                machine_salt=b"layer1-test-salt-000000000000000",
                journal_path=journal_path,
            )
            entropy = engine.build_entropy_material(fake_snapshot(), payload)
            encrypted = encrypt_payload(payload, entropy, topic="telemetry_raw")
            proof = build_vault_proof(
                encrypted=encrypted,
                entropy=entropy,
                snapshot=fake_snapshot(),
                telemetry_summary=telemetry_summary,
            )
            db = VaultDatabase(db_path)
            try:
                db.initialize()
                snapshot_id = db.upsert_space_weather_snapshot(fake_snapshot())
                row_id = db.insert_encrypted_telemetry(
                    topic="telemetry_raw",
                    payload=payload,
                    telemetry_summary=telemetry_summary,
                    encrypted=encrypted,
                    entropy=entropy,
                    proof=proof,
                    space_weather_sample_id=snapshot_id,
                )
                self.assertGreater(row_id, 0)
                rows = db.fetch_recent_records(limit=1)
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]["sequence"], 11)
                self.assertEqual(rows[0]["employee_count"], 1)
                self.assertEqual(rows[0]["entropy_journal_seq"], entropy.journal_sequence)
                self.assertEqual(rows[0]["entropy_journal_root"], entropy.journal_merkle_root)
                audit_rows = db.fetch_integrity_audit_rows(limit=1)
                self.assertEqual(audit_rows[0]["entropy_quality"], "BRONZE")
                self.assertEqual(audit_rows[0]["entropy_journal_entry_hash"], entropy.journal_entry_hash)
                proofs = db.fetch_recent_proofs(limit=1)
                self.assertEqual(proofs[0]["integrity_proof"], proof.integrity_proof)
                report = build_report(str(db_path), recent_limit=2, verify_integrity=True)
                self.assertEqual(report["summary"]["encrypted_record_count"], 1)
                self.assertEqual(len(report["recent_records"]), 1)
                self.assertEqual(report["integrity_audit"]["records_checked"], 1)
                self.assertEqual(report["integrity_audit"]["failed_count"], 0)
                self.assertTrue(report["recent_audits"][0]["passed"])
                self.assertEqual(report["recent_audits"][0]["entropy_quality_tier"], "BRONZE")
                self.assertEqual(report["recent_audits"][0]["entropy_journal_sequence"], entropy.journal_sequence)
                self.assertEqual(report["recent_audits"][0]["entropy_journal_merkle_root"], entropy.journal_merkle_root)
            finally:
                db.close()

    def test_entropy_journal_recovery_resumes_sequence(self) -> None:
        payload = {
            "sequence": 31,
            "timestamp": "2026-04-10T13:10:00Z",
            "sensor_id": "sentinel-test",
            "team": "core-pulse",
            "employees": [
                {
                    "user_id": "U-31",
                    "display_name": "Tester Three",
                    "focus_score": 0.66,
                    "burnout_risk": 0.48,
                    "activity_load": 0.58,
                    "context_switches": 5,
                    "keystroke_entropy": 0.73,
                    "flow_minutes": 21,
                    "active_window": "Browser",
                    "distractions": ["news.ycombinator.com"],
                }
            ],
            "system_load": {"cpu": 41.0, "memory": 52.0, "network_mbps": 7.0},
            "flags": ["test"],
        }
        with _temp_dir("vault-pipeline-") as temp_dir:
            journal_path = temp_dir / "entropy_resume.wal"
            seed = b"layer1-test-salt-000000000000000"
            first_engine = EntropyEngine(machine_salt=seed, journal_path=journal_path)
            first_entropy = first_engine.build_entropy_material(fake_snapshot(), payload)

            second_engine = EntropyEngine(machine_salt=seed, journal_path=journal_path)
            second_entropy = second_engine.build_entropy_material(fake_snapshot(), payload)

            self.assertEqual(second_entropy.journal_sequence, first_entropy.journal_sequence + 1)
            self.assertGreaterEqual(second_entropy.journal_recovered_entries, 2)


if __name__ == "__main__":
    unittest.main()
