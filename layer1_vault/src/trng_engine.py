from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import platform
import random
import shutil
import socket
import threading
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

try:
    from .entropy_policy import DEFAULT_ENTROPY_POLICY, LOCAL_CSPRNG_PROVIDER, NASA_DONKI_PROVIDER, EntropyPolicy
    from .entropy_providers import (
        ContextDigestProvider,
        ContextDigestSample,
        EntropyBytesSample,
        EntropyProvider,
        NasaDonkiDigestClient,
        OutshiftQRNGClient,
        ProviderError,
        RandomOrgClient,
    )
    from .nasa_client import SpaceWeatherSnapshot, iso_utc
except ImportError:
    from entropy_policy import DEFAULT_ENTROPY_POLICY, LOCAL_CSPRNG_PROVIDER, NASA_DONKI_PROVIDER, EntropyPolicy
    from entropy_providers import (
        ContextDigestProvider,
        ContextDigestSample,
        EntropyBytesSample,
        EntropyProvider,
        NasaDonkiDigestClient,
        OutshiftQRNGClient,
        ProviderError,
        RandomOrgClient,
    )
    from nasa_client import SpaceWeatherSnapshot, iso_utc


LOGGER = logging.getLogger("core_pulse.vault.entropy")


def stable_json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


@dataclass(slots=True)
class CircuitBreakerState:
    consecutive_failures: int = 0
    open_until_monotonic: float = 0.0


@dataclass(frozen=True, slots=True)
class EntropyMaterial:
    created_at: str
    entropy_digest: str
    key_bytes: bytes
    key_fingerprint: str
    nonce_bytes: bytes
    pool_size: int
    payload_sha256: str
    space_weather_quality: str
    entropy_quality_tier: str
    policy_version: str
    entropy_sources: list[dict[str, Any]]
    fallback_reason: str
    supplemental_entropy_count: int
    evidence: dict[str, Any]


class EntropyEngine:
    def __init__(
        self,
        machine_salt: bytes | None = None,
        *,
        policy: EntropyPolicy = DEFAULT_ENTROPY_POLICY,
        supplemental_providers: list[EntropyProvider] | None = None,
        context_provider: ContextDigestProvider | None = None,
    ) -> None:
        self.policy = policy
        self._machine_salt = machine_salt or self._require_local_csprng(32, purpose="machine_salt")
        self._supplemental_providers = supplemental_providers or [
            OutshiftQRNGClient(timeout_seconds=policy.remote_timeout_seconds),
            RandomOrgClient(timeout_seconds=policy.remote_timeout_seconds),
        ]
        self._context_provider = context_provider or NasaDonkiDigestClient()
        self._circuit_breakers: dict[str, CircuitBreakerState] = {
            provider.name: CircuitBreakerState() for provider in self._supplemental_providers
        }
        self._circuit_breakers.setdefault(self._context_provider.name, CircuitBreakerState())

    def build_entropy_material(
        self,
        snapshot: SpaceWeatherSnapshot,
        telemetry_payload: dict[str, Any],
        *,
        extra_context: dict[str, Any] | None = None,
    ) -> EntropyMaterial:
        payload_bytes = stable_json_bytes(telemetry_payload)
        local_csprng_seed = self._require_local_csprng(32, purpose="key_seed")
        local_observed_entropy = self._collect_local_entropy(telemetry_payload)
        context_bytes = stable_json_bytes(extra_context or {})
        snapshot_bytes = stable_json_bytes(snapshot.as_record())
        payload_sha256 = hashlib.sha256(payload_bytes).hexdigest()

        context_sample, context_record = self._collect_context_digest(snapshot)
        supplemental_samples, supplemental_records, fallback_reasons = self._collect_supplemental_entropy()

        supplemental_entropy = b"".join(sample.entropy_bytes for sample in supplemental_samples)
        entropy_sources = [context_record, *supplemental_records]
        entropy_quality_tier = self.policy.classify_quality_tier(len(supplemental_samples))
        fallback_reason = ",".join(fallback_reasons)

        # Policy rule: local CSPRNG remains mandatory; remote providers are additive/contextual.
        local_entropy_input = b"|".join(
            [
                b"core-pulse-local",
                local_csprng_seed,
                local_observed_entropy,
                supplemental_entropy,
            ]
        )
        context_material = b"|".join(
            [
                b"core-pulse-context",
                context_sample.digest_hex.encode("utf-8"),
                snapshot_bytes,
                payload_bytes,
                context_bytes,
            ]
        )
        salt = hashlib.sha256(b"salt|" + self._machine_salt + payload_bytes).digest()
        context_digest = hashlib.sha256(context_material).digest()

        key_bytes = self._hkdf_sha256(
            ikm=local_entropy_input,
            salt=salt,
            info=b"core-pulse-layer1-key|" + context_digest,
            length=32,
        )
        nonce_seed = self._require_local_csprng(16, purpose="nonce_seed")
        nonce_bytes = self._hkdf_sha256(
            ikm=local_entropy_input + b"|" + nonce_seed,
            salt=salt,
            info=b"core-pulse-layer1-nonce|" + context_digest,
            length=12,
        )

        pool = b"|".join([local_entropy_input, context_material, salt, nonce_seed])
        entropy_digest = hashlib.sha256(b"digest|" + pool).hexdigest()

        evidence = {
            "policy_version": self.policy.version,
            "local_entropy_provider": LOCAL_CSPRNG_PROVIDER,
            "supplemental_entropy_sources": [sample.provider for sample in supplemental_samples],
            "context_sources": [context_sample.provider],
            "remote_timeout_seconds": self.policy.remote_timeout_seconds,
            "remote_retry_count": self.policy.remote_retry_count,
            "circuit_breaker_failure_threshold": self.policy.circuit_breaker_failure_threshold,
            "circuit_breaker_cooldown_seconds": self.policy.circuit_breaker_cooldown_seconds,
            "snapshot_digest": snapshot.payload_digest,
            "space_weather_quality": snapshot.quality,
            "xray_flux_wm2": snapshot.xray_flux_wm2,
            "flare_count_24h": snapshot.flare_count_24h,
            "strongest_flare_class": snapshot.strongest_flare_class,
            "payload_sha256": payload_sha256,
            "entropy_quality_tier": entropy_quality_tier,
            "entropy_sources": entropy_sources,
            "fallback_reason": fallback_reason,
        }

        LOGGER.info(
            "entropy material built tier=%s supplemental=%s fallback=%s",
            entropy_quality_tier,
            len(supplemental_samples),
            fallback_reason or "none",
        )

        return EntropyMaterial(
            created_at=iso_utc(),
            entropy_digest=entropy_digest,
            key_bytes=key_bytes,
            key_fingerprint=hashlib.sha256(key_bytes).hexdigest()[:16],
            nonce_bytes=nonce_bytes,
            pool_size=len(pool),
            payload_sha256=payload_sha256,
            space_weather_quality=snapshot.quality,
            entropy_quality_tier=entropy_quality_tier,
            policy_version=self.policy.version,
            entropy_sources=entropy_sources,
            fallback_reason=fallback_reason,
            supplemental_entropy_count=len(supplemental_samples),
            evidence=evidence,
        )

    def _collect_context_digest(self, snapshot: SpaceWeatherSnapshot) -> tuple[ContextDigestSample, dict[str, Any]]:
        def run() -> ContextDigestSample:
            return self._context_provider.get_digest(snapshot)

        provider_name = self._context_provider.name
        try:
            sample = self._run_with_resilience(provider_name, run)
            LOGGER.info(
                "context provider %s status=%s quality=%s latency_ms=%s",
                provider_name,
                sample.status,
                sample.quality,
                sample.latency_ms,
            )
            return sample, sample.as_record()
        except ProviderError as exc:
            fallback_digest = snapshot.payload_digest or hashlib.sha256(snapshot.observed_at.encode("utf-8")).hexdigest()
            fallback_reason = f"{provider_name}:{exc.code}"
            record = {
                "provider": provider_name,
                "kind": "context",
                "timestamp": iso_utc(),
                "bytes_used": 0,
                "quality": "fallback-local",
                "request_hash": "",
                "response_digest": fallback_digest,
                "latency_ms": 0,
                "status": "failed",
                "error_code": exc.code,
                "fallback_reason": fallback_reason,
            }
            LOGGER.warning("context provider %s failed code=%s using snapshot fallback", provider_name, exc.code)
            return (
                ContextDigestSample(
                    provider=NASA_DONKI_PROVIDER,
                    fetched_at=iso_utc(),
                    quality="fallback-local",
                    digest_hex=fallback_digest,
                    request_hash="",
                    response_digest=fallback_digest,
                    latency_ms=0,
                    status="fallback",
                    error_code=exc.code,
                    fallback_reason=fallback_reason,
                ),
                record,
            )

    def _collect_supplemental_entropy(self) -> tuple[list[EntropyBytesSample], list[dict[str, Any]], list[str]]:
        successful_samples: list[EntropyBytesSample] = []
        records: list[dict[str, Any]] = []
        fallback_reasons: list[str] = []

        for provider in self._supplemental_providers:
            provider_name = provider.name

            def run() -> EntropyBytesSample:
                return provider.get_bytes(self.policy.supplemental_provider_bytes)

            try:
                sample = self._run_with_resilience(provider_name, run)
                successful_samples.append(sample)
                records.append(sample.as_record())
                LOGGER.info(
                    "supplemental provider %s status=%s bytes=%s latency_ms=%s",
                    provider_name,
                    sample.status,
                    sample.byte_count,
                    sample.latency_ms,
                )
            except ProviderError as exc:
                reason = f"{provider_name}:{exc.code}"
                fallback_reasons.append(reason)
                records.append(
                    {
                        "provider": provider_name,
                        "kind": "entropy",
                        "timestamp": iso_utc(),
                        "bytes_used": 0,
                        "quality": "unavailable",
                        "request_hash": "",
                        "response_digest": "",
                        "latency_ms": 0,
                        "status": "failed",
                        "error_code": exc.code,
                        "fallback_reason": reason,
                    }
                )
                LOGGER.warning("supplemental provider %s failed code=%s fallback=local-only", provider_name, exc.code)
        return successful_samples, records, fallback_reasons

    def _run_with_resilience(self, provider_name: str, operation: Callable[[], Any]) -> Any:
        max_attempts = self.policy.remote_retry_count + 1
        last_error: ProviderError | None = None

        for attempt in range(max_attempts):
            if self._is_circuit_open(provider_name):
                raise ProviderError("circuit_open", f"circuit open for provider {provider_name}", retriable=False)
            try:
                result = self._run_with_timeout(operation, timeout_seconds=self.policy.remote_timeout_seconds)
                self._reset_circuit(provider_name)
                return result
            except ProviderError as exc:
                last_error = exc
                self._record_failure(provider_name)
                if attempt >= max_attempts - 1 or not exc.retriable:
                    break
                self._sleep_with_backoff(attempt)

        if last_error is None:
            raise ProviderError("unknown", f"provider {provider_name} failed without an explicit error")
        raise last_error

    @staticmethod
    def _run_with_timeout(operation: Callable[[], Any], *, timeout_seconds: float) -> Any:
        executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="entropy-provider")
        future = executor.submit(operation)
        try:
            return future.result(timeout=timeout_seconds)
        except FuturesTimeout as exc:
            future.cancel()
            raise ProviderError("timeout", "provider call timed out") from exc
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

    def _is_circuit_open(self, provider_name: str) -> bool:
        state = self._circuit_breakers.setdefault(provider_name, CircuitBreakerState())
        return time.monotonic() < state.open_until_monotonic

    def _record_failure(self, provider_name: str) -> None:
        state = self._circuit_breakers.setdefault(provider_name, CircuitBreakerState())
        state.consecutive_failures += 1
        if state.consecutive_failures >= self.policy.circuit_breaker_failure_threshold:
            state.open_until_monotonic = time.monotonic() + self.policy.circuit_breaker_cooldown_seconds
            state.consecutive_failures = 0

    def _reset_circuit(self, provider_name: str) -> None:
        state = self._circuit_breakers.setdefault(provider_name, CircuitBreakerState())
        state.consecutive_failures = 0
        state.open_until_monotonic = 0.0

    @staticmethod
    def _sleep_with_backoff(attempt: int) -> None:
        base_seconds = 0.1
        jitter = random.uniform(0.0, 0.05)
        time.sleep(base_seconds * (2**attempt) + jitter)

    def _require_local_csprng(self, length: int, *, purpose: str) -> bytes:
        if length <= 0:
            raise ValueError(f"length must be positive for {purpose}")
        if not self.policy.local_csprng_required:
            return os.urandom(length)
        try:
            random_bytes = os.urandom(length)
        except Exception as exc:  # pragma: no cover - platform level failure path
            raise RuntimeError(
                f"local OS CSPRNG is unavailable for {purpose}; refusing remote-only entropy generation"
            ) from exc
        if len(random_bytes) != length:
            raise RuntimeError(f"local OS CSPRNG returned {len(random_bytes)} bytes for {purpose}, expected {length}")
        return random_bytes

    @staticmethod
    def _hkdf_sha256(*, ikm: bytes, salt: bytes, info: bytes, length: int) -> bytes:
        if length <= 0:
            raise ValueError("HKDF output length must be positive")
        prk = hmac.new(salt, ikm, hashlib.sha256).digest()
        okm = b""
        previous_block = b""
        counter = 1
        while len(okm) < length:
            previous_block = hmac.new(prk, previous_block + info + bytes([counter]), hashlib.sha256).digest()
            okm += previous_block
            counter += 1
        return okm[:length]

    def _collect_local_entropy(self, telemetry_payload: dict[str, Any]) -> bytes:
        telemetry_summary = {
            "sequence": telemetry_payload.get("sequence"),
            "employee_count": len(telemetry_payload.get("employees", [])),
            "system_load": telemetry_payload.get("system_load", {}),
        }
        perf_samples = []
        last_tick = time.perf_counter_ns()
        for _ in range(8):
            current = time.perf_counter_ns()
            perf_samples.append(current - last_tick)
            last_tick = current

        usage = shutil.disk_usage(Path.cwd())
        loadavg = getattr(os, "getloadavg", lambda: (0.0, 0.0, 0.0))()

        machine_view = {
            "pid": os.getpid(),
            "native_thread_id": getattr(threading, "get_native_id", threading.get_ident)(),
            "hostname": socket.gethostname(),
            "platform": platform.platform(),
            "time_ns": time.time_ns(),
            "monotonic_ns": time.monotonic_ns(),
            "perf_samples": perf_samples,
            "cwd_free_bytes": usage.free,
            "cwd_used_bytes": usage.used,
            "loadavg": loadavg,
            "telemetry_summary": telemetry_summary,
        }
        return stable_json_bytes(machine_view)
