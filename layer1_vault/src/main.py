from __future__ import annotations

import argparse
import json
import logging
from dataclasses import dataclass
from pathlib import Path

import zmq

try:
    from .crypto_aes import encrypt_payload
    from .db_manager import VaultDatabase
    from .nasa_client import NASA_DONKI_FLR_URL, SWPC_PRIMARY_XRAY_URL, SpaceWeatherClient
    from .payload_validator import TelemetryValidationError, validate_telemetry_payload
    from .proof_engine import build_vault_proof
    from .trng_engine import EntropyEngine
except ImportError:
    from crypto_aes import encrypt_payload
    from db_manager import VaultDatabase
    from nasa_client import NASA_DONKI_FLR_URL, SWPC_PRIMARY_XRAY_URL, SpaceWeatherClient
    from payload_validator import TelemetryValidationError, validate_telemetry_payload
    from proof_engine import build_vault_proof
    from trng_engine import EntropyEngine


LOGGER = logging.getLogger("core_pulse.vault.daemon")


@dataclass(slots=True)
class VaultConfig:
    zmq_endpoint: str
    zmq_topic: str
    database_path: str
    max_messages: int | None
    primary_endpoint: str
    flare_endpoint: str
    api_timeout: float
    api_cache_ttl: float
    log_level: str


class CosmicVaultDaemon:
    def __init__(self, config: VaultConfig) -> None:
        self.config = config
        self.db = VaultDatabase(config.database_path)
        self.client = SpaceWeatherClient(
            primary_endpoint=config.primary_endpoint,
            flare_endpoint=config.flare_endpoint,
            timeout_seconds=config.api_timeout,
            cache_ttl_seconds=config.api_cache_ttl,
        )
        self.entropy_engine = EntropyEngine()
        self._context = zmq.Context.instance()

    @staticmethod
    def _decode_frames(raw_frames: list[bytes]) -> tuple[str, bytes]:
        if len(raw_frames) >= 2:
            return raw_frames[0].decode("utf-8"), raw_frames[1]
        if not raw_frames:
            raise ValueError("ZeroMQ yielded an empty frame")
        blob = raw_frames[0]
        if b" " in blob:
            topic_blob, payload_blob = blob.split(b" ", 1)
            return topic_blob.decode("utf-8"), payload_blob
        return "telemetry_raw", blob

    def run(self) -> None:
        self.db.initialize()
        socket = self._context.socket(zmq.SUB)
        socket.connect(self.config.zmq_endpoint)
        socket.setsockopt_string(zmq.SUBSCRIBE, self.config.zmq_topic)
        LOGGER.info("layer1 subscribed to %s on %s", self.config.zmq_topic, self.config.zmq_endpoint)
        LOGGER.info("space-weather endpoints: %s | %s", self.config.primary_endpoint, self.config.flare_endpoint)
        processed = 0

        try:
            while self.config.max_messages is None or processed < self.config.max_messages:
                raw_frames = socket.recv_multipart()
                topic, payload_blob = self._decode_frames(list(raw_frames))
                payload = json.loads(payload_blob.decode("utf-8"))
                try:
                    telemetry_summary = validate_telemetry_payload(payload)
                except TelemetryValidationError as exc:
                    LOGGER.error("received invalid telemetry payload: %s", exc)
                    continue

                snapshot = self.client.get_snapshot()
                weather_row_id = self.db.upsert_space_weather_snapshot(snapshot)
                entropy = self.entropy_engine.build_entropy_material(
                    snapshot,
                    payload,
                    extra_context={"topic": topic, "database_path": self.config.database_path},
                )
                encrypted = encrypt_payload(payload, entropy, topic=topic)
                proof = build_vault_proof(
                    encrypted=encrypted,
                    entropy=entropy,
                    snapshot=snapshot,
                    telemetry_summary=telemetry_summary,
                )
                record_id = self.db.insert_encrypted_telemetry(
                    topic=topic,
                    payload=payload,
                    telemetry_summary=telemetry_summary,
                    encrypted=encrypted,
                    entropy=entropy,
                    proof=proof,
                    space_weather_sample_id=weather_row_id,
                )
                processed += 1

                LOGGER.info(
                    "stored record=%s seq=%s key=%s proof=%s xray=%.3e quality=%s",
                    record_id,
                    telemetry_summary.sequence,
                    encrypted.key_fingerprint,
                    proof.proof_fingerprint,
                    snapshot.xray_flux_wm2,
                    snapshot.quality,
                )
        except KeyboardInterrupt:
            LOGGER.info("layer1 vault interrupted")
        finally:
            socket.close(0)
            self.db.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="CORE-PULSE Layer 1 cosmic vault daemon.")
    parser.add_argument("--zmq-endpoint", default="tcp://127.0.0.1:5557")
    parser.add_argument("--zmq-topic", default="telemetry_raw")
    parser.add_argument(
        "--database-path",
        default=str(Path(__file__).resolve().parents[1] / "data" / "vault.db"),
    )
    parser.add_argument("--max-messages", type=int, default=None)
    parser.add_argument("--primary-endpoint", default=SWPC_PRIMARY_XRAY_URL)
    parser.add_argument("--flare-endpoint", default=NASA_DONKI_FLR_URL)
    parser.add_argument("--api-timeout", type=float, default=10.0)
    parser.add_argument("--api-cache-ttl", type=float, default=120.0)
    parser.add_argument("--log-level", default="INFO")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(message)s",
    )
    config = VaultConfig(
        zmq_endpoint=args.zmq_endpoint,
        zmq_topic=args.zmq_topic,
        database_path=args.database_path,
        max_messages=args.max_messages,
        primary_endpoint=args.primary_endpoint,
        flare_endpoint=args.flare_endpoint,
        api_timeout=args.api_timeout,
        api_cache_ttl=args.api_cache_ttl,
        log_level=args.log_level,
    )
    CosmicVaultDaemon(config).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
