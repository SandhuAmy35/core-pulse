from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

try:
    from .crypto_aes import EncryptedPayload
    from .nasa_client import SpaceWeatherSnapshot
    from .proof_engine import VaultProof
    from .payload_validator import TelemetrySummary
    from .trng_engine import EntropyMaterial
except ImportError:
    from crypto_aes import EncryptedPayload
    from nasa_client import SpaceWeatherSnapshot
    from proof_engine import VaultProof
    from payload_validator import TelemetrySummary
    from trng_engine import EntropyMaterial


class VaultDatabase:
    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.database_path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA journal_mode=WAL;")
        self.connection.execute("PRAGMA foreign_keys=ON;")

    def close(self) -> None:
        self.connection.close()

    @staticmethod
    def _require_int(value: Any, *, field_name: str) -> int:
        if not isinstance(value, int):
            raise RuntimeError(f"expected integer value for {field_name}, got {value!r}")
        return value

    def _ensure_column(self, table_name: str, column_name: str, definition: str) -> None:
        existing_columns = {
            str(row["name"])
            for row in self.connection.execute(f"PRAGMA table_info({table_name})").fetchall()
        }
        if column_name not in existing_columns:
            self.connection.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")

    def initialize(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS space_weather_samples (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                captured_at TEXT NOT NULL,
                observed_at TEXT NOT NULL,
                xray_flux_wm2 REAL NOT NULL,
                observed_flux_wm2 REAL NOT NULL,
                energy_band TEXT NOT NULL,
                satellite TEXT NOT NULL,
                flare_count_24h INTEGER NOT NULL,
                strongest_flare_class TEXT NOT NULL,
                primary_endpoint TEXT NOT NULL,
                flare_endpoint TEXT NOT NULL,
                quality TEXT NOT NULL,
                payload_digest TEXT NOT NULL UNIQUE,
                status_note TEXT NOT NULL,
                primary_payload_json TEXT NOT NULL,
                flare_payload_json TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS encrypted_telemetry (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ingested_at TEXT NOT NULL,
                topic TEXT NOT NULL,
                telemetry_timestamp TEXT NOT NULL,
                sequence INTEGER NOT NULL,
                sensor_id TEXT NOT NULL,
                team TEXT NOT NULL,
                employee_count INTEGER NOT NULL DEFAULT 0,
                avg_focus_score REAL NOT NULL DEFAULT 0,
                avg_burnout_risk REAL NOT NULL DEFAULT 0,
                algorithm TEXT NOT NULL,
                key_fingerprint TEXT NOT NULL,
                entropy_digest TEXT NOT NULL,
                entropy_quality TEXT NOT NULL,
                payload_sha256 TEXT NOT NULL,
                integrity_proof TEXT NOT NULL DEFAULT '',
                proof_payload_json TEXT NOT NULL DEFAULT '',
                aad_json TEXT NOT NULL,
                nonce BLOB NOT NULL,
                ciphertext BLOB NOT NULL,
                space_weather_sample_id INTEGER NOT NULL,
                FOREIGN KEY(space_weather_sample_id) REFERENCES space_weather_samples(id)
            );

            CREATE INDEX IF NOT EXISTS idx_encrypted_telemetry_sequence
            ON encrypted_telemetry(sequence);

            CREATE INDEX IF NOT EXISTS idx_encrypted_telemetry_digest
            ON encrypted_telemetry(entropy_digest);

            CREATE INDEX IF NOT EXISTS idx_encrypted_telemetry_integrity_proof
            ON encrypted_telemetry(integrity_proof);
            """
        )
        self._ensure_column("encrypted_telemetry", "employee_count", "INTEGER NOT NULL DEFAULT 0")
        self._ensure_column("encrypted_telemetry", "avg_focus_score", "REAL NOT NULL DEFAULT 0")
        self._ensure_column("encrypted_telemetry", "avg_burnout_risk", "REAL NOT NULL DEFAULT 0")
        self._ensure_column("encrypted_telemetry", "integrity_proof", "TEXT NOT NULL DEFAULT ''")
        self._ensure_column("encrypted_telemetry", "proof_payload_json", "TEXT NOT NULL DEFAULT ''")
        self.connection.commit()

    def upsert_space_weather_snapshot(self, snapshot: SpaceWeatherSnapshot) -> int:
        self.connection.execute(
            """
            INSERT OR IGNORE INTO space_weather_samples (
                captured_at,
                observed_at,
                xray_flux_wm2,
                observed_flux_wm2,
                energy_band,
                satellite,
                flare_count_24h,
                strongest_flare_class,
                primary_endpoint,
                flare_endpoint,
                quality,
                payload_digest,
                status_note,
                primary_payload_json,
                flare_payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                snapshot.captured_at,
                snapshot.observed_at,
                snapshot.xray_flux_wm2,
                snapshot.observed_flux_wm2,
                snapshot.energy_band,
                snapshot.satellite,
                snapshot.flare_count_24h,
                snapshot.strongest_flare_class,
                snapshot.primary_endpoint,
                snapshot.flare_endpoint,
                snapshot.quality,
                snapshot.payload_digest,
                snapshot.status_note,
                json.dumps(snapshot.primary_payload, sort_keys=True, separators=(",", ":")),
                json.dumps(snapshot.flare_payload, sort_keys=True, separators=(",", ":")),
            ),
        )
        row = self.connection.execute(
            "SELECT id FROM space_weather_samples WHERE payload_digest = ?",
            (snapshot.payload_digest,),
        ).fetchone()
        self.connection.commit()
        if row is None:
            raise RuntimeError("failed to persist space weather snapshot")
        return self._require_int(row["id"], field_name="space_weather_samples.id")

    def insert_encrypted_telemetry(
        self,
        *,
        topic: str,
        payload: dict[str, Any],
        telemetry_summary: TelemetrySummary,
        encrypted: EncryptedPayload,
        entropy: EntropyMaterial,
        proof: VaultProof,
        space_weather_sample_id: int,
    ) -> int:
        cursor = self.connection.execute(
            """
            INSERT INTO encrypted_telemetry (
                ingested_at,
                topic,
                telemetry_timestamp,
                sequence,
                sensor_id,
                team,
                employee_count,
                avg_focus_score,
                avg_burnout_risk,
                algorithm,
                key_fingerprint,
                entropy_digest,
                entropy_quality,
                payload_sha256,
                integrity_proof,
                proof_payload_json,
                aad_json,
                nonce,
                ciphertext,
                space_weather_sample_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entropy.created_at,
                topic,
                telemetry_summary.timestamp,
                telemetry_summary.sequence,
                telemetry_summary.sensor_id,
                telemetry_summary.team,
                telemetry_summary.employee_count,
                telemetry_summary.avg_focus_score,
                telemetry_summary.avg_burnout_risk,
                encrypted.algorithm,
                encrypted.key_fingerprint,
                encrypted.entropy_digest,
                entropy.entropy_quality_tier,
                encrypted.plaintext_sha256,
                proof.integrity_proof,
                proof.proof_payload_json,
                encrypted.aad_json,
                encrypted.nonce,
                encrypted.ciphertext,
                space_weather_sample_id,
            ),
        )
        self.connection.commit()
        return self._require_int(cursor.lastrowid, field_name="encrypted_telemetry.id")

    def fetch_recent_records(self, limit: int = 5) -> list[sqlite3.Row]:
        rows = self.connection.execute(
            """
            SELECT
                id,
                ingested_at,
                sequence,
                sensor_id,
                team,
                employee_count,
                avg_focus_score,
                avg_burnout_risk,
                key_fingerprint,
                entropy_digest,
                integrity_proof
            FROM encrypted_telemetry
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return list(rows)

    def fetch_recent_proofs(self, limit: int = 5) -> list[sqlite3.Row]:
        rows = self.connection.execute(
            """
            SELECT
                id,
                ingested_at,
                sequence,
                sensor_id,
                team,
                integrity_proof,
                proof_payload_json
            FROM encrypted_telemetry
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return list(rows)

    def fetch_integrity_audit_rows(self, limit: int = 5) -> list[sqlite3.Row]:
        rows = self.connection.execute(
            """
            SELECT
                telemetry.id,
                telemetry.ingested_at,
                telemetry.sequence,
                telemetry.sensor_id,
                telemetry.team,
                telemetry.employee_count,
                telemetry.avg_focus_score,
                telemetry.avg_burnout_risk,
                telemetry.key_fingerprint,
                telemetry.entropy_digest,
                telemetry.entropy_quality,
                telemetry.payload_sha256,
                telemetry.integrity_proof,
                telemetry.proof_payload_json,
                telemetry.aad_json,
                telemetry.nonce,
                telemetry.ciphertext,
                weather.payload_digest AS space_weather_digest,
                weather.quality AS space_weather_quality
            FROM encrypted_telemetry AS telemetry
            INNER JOIN space_weather_samples AS weather
                ON weather.id = telemetry.space_weather_sample_id
            ORDER BY telemetry.id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return list(rows)

    def fetch_recent_space_weather_samples(self, limit: int = 5) -> list[sqlite3.Row]:
        rows = self.connection.execute(
            """
            SELECT
                id,
                captured_at,
                observed_at,
                xray_flux_wm2,
                strongest_flare_class,
                flare_count_24h,
                quality
            FROM space_weather_samples
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return list(rows)

    def fetch_vault_summary(self) -> sqlite3.Row:
        row = self.connection.execute(
            """
            SELECT
                COUNT(*) AS encrypted_record_count,
                COALESCE(MAX(sequence), 0) AS latest_sequence,
                COALESCE(MAX(ingested_at), '') AS latest_ingested_at,
                COALESCE(AVG(employee_count), 0) AS average_employee_count,
                COALESCE(AVG(avg_focus_score), 0) AS average_focus_score,
                COALESCE(AVG(avg_burnout_risk), 0) AS average_burnout_risk,
                COUNT(DISTINCT integrity_proof) AS proof_count
            FROM encrypted_telemetry
            """
        ).fetchone()
        if row is None:
            raise RuntimeError("failed to query vault summary")
        return row
