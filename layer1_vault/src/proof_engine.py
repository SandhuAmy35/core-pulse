from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

try:
    from .crypto_aes import EncryptedPayload
    from .nasa_client import SpaceWeatherSnapshot
    from .payload_validator import TelemetrySummary
    from .trng_engine import EntropyMaterial
except ImportError:
    from crypto_aes import EncryptedPayload
    from nasa_client import SpaceWeatherSnapshot
    from payload_validator import TelemetrySummary
    from trng_engine import EntropyMaterial


@dataclass(frozen=True, slots=True)
class VaultProof:
    integrity_proof: str
    proof_fingerprint: str
    proof_payload_json: str


def build_proof_payload(
    *,
    encrypted: EncryptedPayload,
    entropy: EntropyMaterial,
    snapshot: SpaceWeatherSnapshot,
    telemetry_summary: TelemetrySummary,
) -> dict[str, Any]:
    return {
        "algorithm": encrypted.algorithm,
        "key_fingerprint": encrypted.key_fingerprint,
        "entropy_digest": encrypted.entropy_digest,
        "entropy_policy_version": entropy.policy_version,
        "entropy_quality_tier": entropy.entropy_quality_tier,
        "entropy_sources": entropy.entropy_sources,
        "entropy_fallback_reason": entropy.fallback_reason,
        "supplemental_entropy_count": entropy.supplemental_entropy_count,
        "entropy_journal_sequence": entropy.journal_sequence,
        "entropy_journal_entry_hash": entropy.journal_entry_hash,
        "entropy_journal_merkle_root": entropy.journal_merkle_root,
        "entropy_journal_recovered_entries": entropy.journal_recovered_entries,
        "entropy_journal_tail_truncated": entropy.journal_tail_truncated,
        "entropy_pool_size": entropy.pool_size,
        "entropy_created_at": entropy.created_at,
        "payload_sha256": encrypted.plaintext_sha256,
        "space_weather_digest": snapshot.payload_digest,
        "space_weather_quality": snapshot.quality,
        "sequence": telemetry_summary.sequence,
        "sensor_id": telemetry_summary.sensor_id,
        "team": telemetry_summary.team,
        "employee_count": telemetry_summary.employee_count,
        "avg_focus_score": telemetry_summary.avg_focus_score,
        "avg_burnout_risk": telemetry_summary.avg_burnout_risk,
        "nonce_hex": encrypted.nonce.hex(),
        "ciphertext_sha256": hashlib.sha256(encrypted.ciphertext).hexdigest(),
        "aad_sha256": hashlib.sha256(encrypted.aad_json.encode("utf-8")).hexdigest(),
    }


def calculate_integrity_proof(proof_payload_json: str) -> str:
    return hashlib.sha256(proof_payload_json.encode("utf-8")).hexdigest()


def verify_integrity_proof(proof_payload_json: str, integrity_proof: str) -> bool:
    return calculate_integrity_proof(proof_payload_json) == integrity_proof


def build_vault_proof(
    *,
    encrypted: EncryptedPayload,
    entropy: EntropyMaterial,
    snapshot: SpaceWeatherSnapshot,
    telemetry_summary: TelemetrySummary,
) -> VaultProof:
    proof_payload = build_proof_payload(
        encrypted=encrypted,
        entropy=entropy,
        snapshot=snapshot,
        telemetry_summary=telemetry_summary,
    )
    proof_payload_json = json.dumps(proof_payload, sort_keys=True, separators=(",", ":"))
    integrity_proof = calculate_integrity_proof(proof_payload_json)
    return VaultProof(
        integrity_proof=integrity_proof,
        proof_fingerprint=integrity_proof[:16],
        proof_payload_json=proof_payload_json,
    )
