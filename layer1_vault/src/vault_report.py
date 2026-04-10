from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

try:
    from .db_manager import VaultDatabase
    from .proof_engine import verify_integrity_proof
except ImportError:
    from db_manager import VaultDatabase
    from proof_engine import verify_integrity_proof


def _rows_to_dicts(rows: list[Any]) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]


def _audit_recent_rows(rows: list[Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    audit_results: list[dict[str, Any]] = []
    for row in rows:
        proof_payload_json = str(row["proof_payload_json"])
        proof_payload = json.loads(proof_payload_json)
        issues: list[str] = []

        if not verify_integrity_proof(proof_payload_json, str(row["integrity_proof"])):
            issues.append("integrity_proof_mismatch")

        expected_pairs = {
            "key_fingerprint": row["key_fingerprint"],
            "entropy_digest": row["entropy_digest"],
            "payload_sha256": row["payload_sha256"],
            "space_weather_digest": row["space_weather_digest"],
            "space_weather_quality": row["space_weather_quality"],
            "entropy_journal_sequence": row["entropy_journal_seq"],
            "entropy_journal_entry_hash": row["entropy_journal_entry_hash"],
            "entropy_journal_merkle_root": row["entropy_journal_root"],
            "sequence": row["sequence"],
            "sensor_id": row["sensor_id"],
            "team": row["team"],
            "employee_count": row["employee_count"],
            "avg_focus_score": row["avg_focus_score"],
            "avg_burnout_risk": row["avg_burnout_risk"],
            "nonce_hex": bytes(row["nonce"]).hex(),
            "ciphertext_sha256": hashlib.sha256(bytes(row["ciphertext"])).hexdigest(),
            "aad_sha256": hashlib.sha256(str(row["aad_json"]).encode("utf-8")).hexdigest(),
        }
        for field_name, expected_value in expected_pairs.items():
            if proof_payload.get(field_name) != expected_value:
                issues.append(f"{field_name}_mismatch")

        proof_entropy_quality = proof_payload.get("entropy_quality_tier", proof_payload.get("space_weather_quality"))
        if proof_entropy_quality != row["entropy_quality"]:
            issues.append("entropy_quality_mismatch")

        audit_results.append(
            {
                "id": row["id"],
                "sequence": row["sequence"],
                "sensor_id": row["sensor_id"],
                "team": row["team"],
                "passed": not issues,
                "issues": issues,
                "proof_fingerprint": str(row["integrity_proof"])[:16],
                "space_weather_quality": row["space_weather_quality"],
                "entropy_quality_tier": row["entropy_quality"],
                "entropy_journal_sequence": row["entropy_journal_seq"],
                "entropy_journal_merkle_root": row["entropy_journal_root"],
            }
        )

    failed_count = sum(1 for result in audit_results if not result["passed"])
    summary = {
        "records_checked": len(audit_results),
        "passed_count": len(audit_results) - failed_count,
        "failed_count": failed_count,
    }
    return summary, audit_results


def build_report(database_path: str, recent_limit: int, verify_integrity: bool = False) -> dict[str, Any]:
    db = VaultDatabase(database_path)
    try:
        db.initialize()
        summary = dict(db.fetch_vault_summary())
        recent_records = _rows_to_dicts(db.fetch_recent_records(limit=recent_limit))
        recent_proofs = _rows_to_dicts(db.fetch_recent_proofs(limit=recent_limit))
        recent_weather = _rows_to_dicts(db.fetch_recent_space_weather_samples(limit=recent_limit))
        audit_rows = db.fetch_integrity_audit_rows(limit=recent_limit) if verify_integrity else []
    finally:
        db.close()

    report = {
        "database_path": str(Path(database_path).resolve()),
        "summary": summary,
        "recent_records": recent_records,
        "recent_proofs": recent_proofs,
        "recent_space_weather_samples": recent_weather,
    }
    if verify_integrity:
        audit_summary, audit_results = _audit_recent_rows(audit_rows)
        report["integrity_audit"] = audit_summary
        report["recent_audits"] = audit_results
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect Layer 1 vault metadata without exposing plaintext telemetry.")
    parser.add_argument(
        "--database-path",
        default=str(Path(__file__).resolve().parents[1] / "data" / "vault.db"),
    )
    parser.add_argument("--recent-limit", type=int, default=5)
    parser.add_argument("--verify-integrity", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_report(args.database_path, args.recent_limit, verify_integrity=args.verify_integrity)
    if args.pretty:
        print(json.dumps(report, indent=2))
    else:
        print(json.dumps(report, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
