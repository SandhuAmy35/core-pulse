from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

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


def build_vault_proof(
    *,
    encrypted: EncryptedPayload,
    entropy: EntropyMaterial,
    snapshot: SpaceWeatherSnapshot,
    telemetry_summary: TelemetrySummary,
) -> VaultProof:
    proof_payload = {
        "algorithm": encrypted.algorithm,
        "key_fingerprint": encrypted.key_fingerprint,
        "entropy_digest": encrypted.entropy_digest,
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
    proof_payload_json = json.dumps(proof_payload, sort_keys=True, separators=(",", ":"))
    integrity_proof = hashlib.sha256(proof_payload_json.encode("utf-8")).hexdigest()
    return VaultProof(
        integrity_proof=integrity_proof,
        proof_fingerprint=integrity_proof[:16],
        proof_payload_json=proof_payload_json,
    )
