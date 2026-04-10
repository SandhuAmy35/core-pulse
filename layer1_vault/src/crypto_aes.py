from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

try:
    from .trng_engine import EntropyMaterial
except ImportError:
    from trng_engine import EntropyMaterial


def stable_json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


@dataclass(frozen=True, slots=True)
class EncryptedPayload:
    algorithm: str
    ciphertext: bytes
    nonce: bytes
    aad_json: str
    key_fingerprint: str
    entropy_digest: str
    plaintext_sha256: str


def encrypt_payload(
    payload: dict[str, Any],
    entropy: EntropyMaterial,
    *,
    topic: str,
    source_label: str = "layer1_vault",
) -> EncryptedPayload:
    plaintext = stable_json_bytes(payload)
    aad = {
        "source_label": source_label,
        "topic": topic,
        "sequence": payload.get("sequence"),
        "sensor_id": payload.get("sensor_id"),
        "team": payload.get("team"),
        "entropy_digest": entropy.entropy_digest,
        "entropy_quality_tier": entropy.entropy_quality_tier,
        "entropy_policy_version": entropy.policy_version,
        "space_weather_quality": entropy.space_weather_quality,
    }
    aad_json = json.dumps(aad, sort_keys=True, separators=(",", ":"))
    cipher = AESGCM(entropy.key_bytes)
    ciphertext = cipher.encrypt(entropy.nonce_bytes, plaintext, aad_json.encode("utf-8"))
    return EncryptedPayload(
        algorithm="AES-256-GCM",
        ciphertext=ciphertext,
        nonce=entropy.nonce_bytes,
        aad_json=aad_json,
        key_fingerprint=entropy.key_fingerprint,
        entropy_digest=entropy.entropy_digest,
        plaintext_sha256=hashlib.sha256(plaintext).hexdigest(),
    )


def decrypt_payload(encrypted: EncryptedPayload, key_bytes: bytes) -> dict[str, Any]:
    cipher = AESGCM(key_bytes)
    plaintext = cipher.decrypt(encrypted.nonce, encrypted.ciphertext, encrypted.aad_json.encode("utf-8"))
    return json.loads(plaintext.decode("utf-8"))
