from __future__ import annotations

import base64
import hashlib
import json
import os
import time
from dataclasses import dataclass
from typing import Any, Protocol, TYPE_CHECKING
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

try:
    from .entropy_policy import NASA_DONKI_PROVIDER, OUTSHIFT_QRNG_PROVIDER, RANDOM_ORG_PROVIDER
    from .nasa_client import iso_utc
except ImportError:
    from entropy_policy import NASA_DONKI_PROVIDER, OUTSHIFT_QRNG_PROVIDER, RANDOM_ORG_PROVIDER
    from nasa_client import iso_utc

if TYPE_CHECKING:
    try:
        from .nasa_client import SpaceWeatherSnapshot
    except ImportError:
        from nasa_client import SpaceWeatherSnapshot


OUTSHIFT_QRNG_ENDPOINT = "https://api.outshift.io/v1/qrng/bytes"
RANDOM_ORG_ENDPOINT = "https://api.random.org/json-rpc/4/invoke"


def _stable_json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


class ProviderError(RuntimeError):
    def __init__(self, code: str, message: str, *, retriable: bool = True) -> None:
        super().__init__(message)
        self.code = code
        self.retriable = retriable


@dataclass(frozen=True, slots=True)
class EntropyBytesSample:
    provider: str
    fetched_at: str
    quality: str
    byte_count: int
    entropy_bytes: bytes
    request_hash: str
    response_digest: str
    latency_ms: int
    status: str = "ok"
    error_code: str = ""
    fallback_reason: str = ""

    def as_record(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "kind": "entropy",
            "timestamp": self.fetched_at,
            "bytes_used": self.byte_count,
            "quality": self.quality,
            "request_hash": self.request_hash,
            "response_digest": self.response_digest,
            "latency_ms": self.latency_ms,
            "status": self.status,
            "error_code": self.error_code,
            "fallback_reason": self.fallback_reason,
        }


@dataclass(frozen=True, slots=True)
class ContextDigestSample:
    provider: str
    fetched_at: str
    quality: str
    digest_hex: str
    request_hash: str
    response_digest: str
    latency_ms: int
    status: str = "ok"
    error_code: str = ""
    fallback_reason: str = ""

    def as_record(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "kind": "context",
            "timestamp": self.fetched_at,
            "bytes_used": 0,
            "quality": self.quality,
            "request_hash": self.request_hash,
            "response_digest": self.response_digest,
            "latency_ms": self.latency_ms,
            "status": self.status,
            "error_code": self.error_code,
            "fallback_reason": self.fallback_reason,
        }


class EntropyProvider(Protocol):
    name: str

    def get_bytes(self, byte_count: int) -> EntropyBytesSample:
        ...


class ContextDigestProvider(Protocol):
    name: str

    def get_digest(self, snapshot: SpaceWeatherSnapshot) -> ContextDigestSample:
        ...


def _make_request_hash(provider: str, endpoint: str, request_payload: Any) -> str:
    return hashlib.sha256(
        b"|".join([provider.encode("utf-8"), endpoint.encode("utf-8"), _stable_json_bytes(request_payload)])
    ).hexdigest()


def _http_get_json(url: str, *, headers: dict[str, str], timeout_seconds: float) -> Any:
    request = Request(url, headers=headers, method="GET")
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return json.loads(response.read().decode(charset))
    except HTTPError as exc:
        if exc.code == 401 or exc.code == 403:
            raise ProviderError("auth", f"provider auth failed: HTTP {exc.code}", retriable=False) from exc
        if exc.code == 429:
            raise ProviderError("quota_exceeded", "provider rate/quota exceeded", retriable=False) from exc
        raise ProviderError(f"http_{exc.code}", f"provider HTTP error {exc.code}") from exc
    except URLError as exc:
        raise ProviderError("network", f"provider network error: {exc}") from exc
    except TimeoutError as exc:
        raise ProviderError("timeout", "provider request timed out") from exc
    except OSError as exc:
        raise ProviderError("network", f"provider transport error: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ProviderError("invalid_payload", "provider JSON payload malformed", retriable=False) from exc


def _http_post_json(url: str, *, headers: dict[str, str], timeout_seconds: float, payload: dict[str, Any]) -> Any:
    body = _stable_json_bytes(payload)
    request = Request(url, headers=headers, method="POST", data=body)
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return json.loads(response.read().decode(charset))
    except HTTPError as exc:
        if exc.code == 401 or exc.code == 403:
            raise ProviderError("auth", f"provider auth failed: HTTP {exc.code}", retriable=False) from exc
        if exc.code == 429:
            raise ProviderError("quota_exceeded", "provider rate/quota exceeded", retriable=False) from exc
        raise ProviderError(f"http_{exc.code}", f"provider HTTP error {exc.code}") from exc
    except URLError as exc:
        raise ProviderError("network", f"provider network error: {exc}") from exc
    except TimeoutError as exc:
        raise ProviderError("timeout", "provider request timed out") from exc
    except OSError as exc:
        raise ProviderError("network", f"provider transport error: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ProviderError("invalid_payload", "provider JSON payload malformed", retriable=False) from exc


class NasaDonkiDigestClient:
    name = NASA_DONKI_PROVIDER

    def get_digest(self, snapshot: SpaceWeatherSnapshot) -> ContextDigestSample:
        started = time.monotonic()
        digest_hex = str(snapshot.payload_digest or "")
        if not digest_hex:
            raise ProviderError("invalid_payload", "space weather payload digest is empty", retriable=False)
        request_payload = {
            "captured_at": snapshot.captured_at,
            "primary_endpoint": snapshot.primary_endpoint,
            "flare_endpoint": snapshot.flare_endpoint,
        }
        request_hash = _make_request_hash(self.name, str(snapshot.flare_endpoint), request_payload)
        elapsed_ms = int((time.monotonic() - started) * 1000)
        return ContextDigestSample(
            provider=self.name,
            fetched_at=iso_utc(),
            quality=str(snapshot.quality),
            digest_hex=digest_hex,
            request_hash=request_hash,
            response_digest=digest_hex,
            latency_ms=elapsed_ms,
        )


class OutshiftQRNGClient:
    name = OUTSHIFT_QRNG_PROVIDER

    def __init__(
        self,
        *,
        endpoint: str = OUTSHIFT_QRNG_ENDPOINT,
        api_key: str | None = None,
        timeout_seconds: float = 0.8,
    ) -> None:
        self.endpoint = endpoint
        self.api_key = (api_key or os.getenv("OUTSHIFT_QRNG_API_KEY", "")).strip() or None
        self.timeout_seconds = timeout_seconds

    def get_bytes(self, byte_count: int) -> EntropyBytesSample:
        if byte_count <= 0:
            raise ValueError("byte_count must be positive")
        if not self.api_key:
            raise ProviderError("unconfigured", "OUTSHIFT_QRNG_API_KEY is not configured", retriable=False)

        params = urlencode({"n": byte_count})
        request_url = f"{self.endpoint}?{params}"
        request_payload = {"n": byte_count}
        started = time.monotonic()
        payload = _http_get_json(
            request_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "User-Agent": "CORE-PULSE-Layer1/1.0",
            },
            timeout_seconds=self.timeout_seconds,
        )
        entropy_bytes = self._extract_bytes(payload, byte_count)
        elapsed_ms = int((time.monotonic() - started) * 1000)
        return EntropyBytesSample(
            provider=self.name,
            fetched_at=iso_utc(),
            quality=str(payload.get("quality", "live")) if isinstance(payload, dict) else "live",
            byte_count=len(entropy_bytes),
            entropy_bytes=entropy_bytes,
            request_hash=_make_request_hash(self.name, self.endpoint, request_payload),
            response_digest=hashlib.sha256(_stable_json_bytes(payload)).hexdigest(),
            latency_ms=elapsed_ms,
        )

    @staticmethod
    def _extract_bytes(payload: Any, minimum_bytes: int) -> bytes:
        candidate: Any = None
        if isinstance(payload, dict):
            for key in ("bytes", "random_bytes", "data", "blob"):
                if key in payload:
                    candidate = payload[key]
                    break
            if candidate is None and "result" in payload and isinstance(payload["result"], dict):
                result = payload["result"]
                for key in ("bytes", "random_bytes", "data", "blob"):
                    if key in result:
                        candidate = result[key]
                        break

        parsed = OutshiftQRNGClient._parse_bytes_candidate(candidate)
        if len(parsed) < minimum_bytes:
            raise ProviderError("invalid_payload", f"outshift returned {len(parsed)} bytes", retriable=False)
        return parsed[:minimum_bytes]

    @staticmethod
    def _parse_bytes_candidate(candidate: Any) -> bytes:
        if isinstance(candidate, bytes):
            return candidate
        if isinstance(candidate, list) and all(isinstance(value, int) and 0 <= value <= 255 for value in candidate):
            return bytes(candidate)
        if isinstance(candidate, str):
            compact = candidate.strip()
            try:
                return bytes.fromhex(compact)
            except ValueError:
                pass
            try:
                return base64.b64decode(compact, validate=True)
            except (ValueError, TypeError):
                pass
        raise ProviderError("invalid_payload", "unable to parse outshift bytes payload", retriable=False)


class RandomOrgClient:
    name = RANDOM_ORG_PROVIDER

    def __init__(
        self,
        *,
        endpoint: str = RANDOM_ORG_ENDPOINT,
        api_key: str | None = None,
        timeout_seconds: float = 0.8,
    ) -> None:
        self.endpoint = endpoint
        self.api_key = (api_key or os.getenv("RANDOM_ORG_API_KEY", "")).strip() or None
        self.timeout_seconds = timeout_seconds

    def get_bytes(self, byte_count: int) -> EntropyBytesSample:
        if byte_count <= 0:
            raise ValueError("byte_count must be positive")
        if not self.api_key:
            raise ProviderError("unconfigured", "RANDOM_ORG_API_KEY is not configured", retriable=False)

        request_payload = {
            "jsonrpc": "2.0",
            "method": "generateBlobs",
            "params": {
                "apiKey": self.api_key,
                "n": 1,
                "size": byte_count * 8,
                "format": "hex",
            },
            "id": int(time.time_ns() % 1_000_000),
        }
        started = time.monotonic()
        payload = _http_post_json(
            self.endpoint,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "CORE-PULSE-Layer1/1.0",
            },
            timeout_seconds=self.timeout_seconds,
            payload=request_payload,
        )
        entropy_bytes = self._extract_bytes(payload, byte_count)
        elapsed_ms = int((time.monotonic() - started) * 1000)
        return EntropyBytesSample(
            provider=self.name,
            fetched_at=iso_utc(),
            quality="live",
            byte_count=len(entropy_bytes),
            entropy_bytes=entropy_bytes,
            request_hash=_make_request_hash(
                self.name,
                self.endpoint,
                {
                    "jsonrpc": "2.0",
                    "method": "generateBlobs",
                    "params": {"n": 1, "size": byte_count * 8, "format": "hex"},
                },
            ),
            response_digest=hashlib.sha256(_stable_json_bytes(payload)).hexdigest(),
            latency_ms=elapsed_ms,
        )

    @staticmethod
    def _extract_bytes(payload: Any, minimum_bytes: int) -> bytes:
        if not isinstance(payload, dict):
            raise ProviderError("invalid_payload", "random.org payload is not a JSON object", retriable=False)

        error = payload.get("error")
        if isinstance(error, dict):
            error_code = str(error.get("code", "unknown"))
            if error_code in {"402", "420"}:
                raise ProviderError("quota_exceeded", "random.org quota exceeded", retriable=False)
            raise ProviderError(f"random_org_error_{error_code}", str(error.get("message", "unknown")), retriable=False)

        result = payload.get("result")
        if not isinstance(result, dict):
            raise ProviderError("invalid_payload", "random.org result is missing", retriable=False)

        random_block = result.get("random")
        if not isinstance(random_block, dict):
            raise ProviderError("invalid_payload", "random.org random block is missing", retriable=False)

        data = random_block.get("data")
        if not isinstance(data, list) or not data or not isinstance(data[0], str):
            raise ProviderError("invalid_payload", "random.org data is malformed", retriable=False)

        try:
            parsed = bytes.fromhex(data[0].strip())
        except ValueError as exc:
            raise ProviderError("invalid_payload", "random.org data[0] is not valid hex", retriable=False) from exc

        if len(parsed) < minimum_bytes:
            raise ProviderError("invalid_payload", f"random.org returned {len(parsed)} bytes", retriable=False)
        return parsed[:minimum_bytes]
