from __future__ import annotations

from dataclasses import dataclass


ENTROPY_POLICY_VERSION = "v1"
LOCAL_CSPRNG_PROVIDER = "local_os_csprng"
OUTSHIFT_QRNG_PROVIDER = "outshift_qrng"
RANDOM_ORG_PROVIDER = "random_org"
NASA_DONKI_PROVIDER = "nasa_donki"

ENTROPY_TIER_GOLD = "GOLD"
ENTROPY_TIER_SILVER = "SILVER"
ENTROPY_TIER_BRONZE = "BRONZE"


@dataclass(frozen=True, slots=True)
class EntropyPolicy:
    version: str = ENTROPY_POLICY_VERSION
    local_csprng_required: bool = True
    remote_timeout_seconds: float = 0.8
    remote_retry_count: int = 1
    circuit_breaker_failure_threshold: int = 3
    circuit_breaker_cooldown_seconds: int = 300
    supplemental_provider_bytes: int = 32

    def classify_quality_tier(self, supplemental_entropy_count: int) -> str:
        if supplemental_entropy_count >= 2:
            return ENTROPY_TIER_GOLD
        if supplemental_entropy_count == 1:
            return ENTROPY_TIER_SILVER
        return ENTROPY_TIER_BRONZE


DEFAULT_ENTROPY_POLICY = EntropyPolicy()
