from __future__ import annotations

import hashlib
import hmac
import json
import os
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

try:
    from .nasa_client import iso_utc
except ImportError:
    from nasa_client import iso_utc


def stable_json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def build_merkle_root_hex(entry_hashes: list[str]) -> str:
    if not entry_hashes:
        return ""
    level = [bytes.fromhex(item) for item in entry_hashes]
    while len(level) > 1:
        if len(level) % 2 == 1:
            level.append(level[-1])
        next_level: list[bytes] = []
        for index in range(0, len(level), 2):
            next_level.append(hashlib.sha256(level[index] + level[index + 1]).digest())
        level = next_level
    return level[0].hex()


@dataclass(frozen=True, slots=True)
class EntropyJournalEntry:
    sequence: int
    timestamp: str
    nonce_hex: str
    ciphertext_hex: str
    request_hash: str
    mac_hex: str
    entry_hash: str
    merkle_root: str

    def as_record(self) -> dict[str, Any]:
        return {
            "sequence": self.sequence,
            "timestamp": self.timestamp,
            "nonce_hex": self.nonce_hex,
            "ciphertext_hex": self.ciphertext_hex,
            "request_hash": self.request_hash,
            "mac_hex": self.mac_hex,
            "entry_hash": self.entry_hash,
            "merkle_root": self.merkle_root,
        }


@dataclass(frozen=True, slots=True)
class EntropyJournalState:
    recovered_entries: int
    last_sequence: int
    last_seed: bytes
    merkle_root: str
    tail_truncated: bool


class EntropyJournal:
    def __init__(self, journal_path: str | Path, *, key_material: bytes) -> None:
        self.journal_path = Path(journal_path)
        self.journal_path.parent.mkdir(parents=True, exist_ok=True)
        self._enc_key = hashlib.sha256(b"entropy-journal-enc|" + key_material).digest()
        self._mac_key = hashlib.sha256(b"entropy-journal-mac|" + key_material).digest()
        self._lock = threading.Lock()
        self._entry_hashes: list[str] = []
        self._last_seed = b""
        self._last_sequence = 0
        self._state = self._recover_state()

    @property
    def state(self) -> EntropyJournalState:
        return self._state

    def append_seed(self, seed: bytes, *, request_hash: str) -> EntropyJournalEntry:
        if not seed:
            raise ValueError("seed must be non-empty")
        if len(seed) < 16:
            raise ValueError("seed must be at least 16 bytes")
        timestamp = iso_utc()
        with self._lock:
            sequence = self._last_sequence + 1
            nonce = os.urandom(12)
            aad = stable_json_bytes(
                {
                    "sequence": sequence,
                    "timestamp": timestamp,
                    "request_hash": request_hash,
                }
            )
            ciphertext = AESGCM(self._enc_key).encrypt(nonce, seed, aad)
            base_record = {
                "v": 1,
                "sequence": sequence,
                "timestamp": timestamp,
                "nonce_hex": nonce.hex(),
                "ciphertext_hex": ciphertext.hex(),
                "request_hash": request_hash,
            }
            mac_hex = hmac.new(self._mac_key, stable_json_bytes(base_record), hashlib.sha256).hexdigest()
            record = dict(base_record)
            record["mac_hex"] = mac_hex
            entry_hash = hashlib.sha256(stable_json_bytes(record)).hexdigest()
            self._entry_hashes.append(entry_hash)
            merkle_root = build_merkle_root_hex(self._entry_hashes)
            record["entry_hash"] = entry_hash
            record["merkle_root"] = merkle_root

            self._append_record(record)

            self._last_sequence = sequence
            self._last_seed = seed
            self._state = EntropyJournalState(
                recovered_entries=len(self._entry_hashes),
                last_sequence=self._last_sequence,
                last_seed=self._last_seed,
                merkle_root=merkle_root,
                tail_truncated=False,
            )
            return EntropyJournalEntry(
                sequence=sequence,
                timestamp=timestamp,
                nonce_hex=record["nonce_hex"],
                ciphertext_hex=record["ciphertext_hex"],
                request_hash=request_hash,
                mac_hex=mac_hex,
                entry_hash=entry_hash,
                merkle_root=merkle_root,
            )

    def _append_record(self, record: dict[str, Any]) -> None:
        line = stable_json_bytes(record) + b"\n"
        with self.journal_path.open("ab") as handle:
            handle.write(line)
            handle.flush()
            os.fsync(handle.fileno())

    def _recover_state(self) -> EntropyJournalState:
        if not self.journal_path.exists():
            return EntropyJournalState(
                recovered_entries=0,
                last_sequence=0,
                last_seed=b"",
                merkle_root="",
                tail_truncated=False,
            )

        entry_hashes: list[str] = []
        last_seed = b""
        last_sequence = 0
        valid_tail_offset = 0
        tail_truncated = False
        expected_next_sequence = 1

        with self.journal_path.open("rb") as handle:
            offset = 0
            for raw_line in handle:
                offset += len(raw_line)
                line = raw_line.strip()
                if not line:
                    valid_tail_offset = offset
                    continue
                try:
                    record = json.loads(line.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    tail_truncated = True
                    break

                try:
                    self._validate_record_shape(record)
                    if int(record["sequence"]) != expected_next_sequence:
                        tail_truncated = True
                        break
                    base_record = {
                        "v": record["v"],
                        "sequence": record["sequence"],
                        "timestamp": record["timestamp"],
                        "nonce_hex": record["nonce_hex"],
                        "ciphertext_hex": record["ciphertext_hex"],
                        "request_hash": record["request_hash"],
                    }
                    expected_mac = hmac.new(self._mac_key, stable_json_bytes(base_record), hashlib.sha256).hexdigest()
                    if not hmac.compare_digest(expected_mac, str(record["mac_hex"])):
                        tail_truncated = True
                        break
                    expected_entry_hash = hashlib.sha256(stable_json_bytes({**base_record, "mac_hex": record["mac_hex"]})).hexdigest()
                    if expected_entry_hash != str(record["entry_hash"]):
                        tail_truncated = True
                        break

                    nonce = bytes.fromhex(str(record["nonce_hex"]))
                    ciphertext = bytes.fromhex(str(record["ciphertext_hex"]))
                    aad = stable_json_bytes(
                        {
                            "sequence": int(record["sequence"]),
                            "timestamp": str(record["timestamp"]),
                            "request_hash": str(record["request_hash"]),
                        }
                    )
                    seed = AESGCM(self._enc_key).decrypt(nonce, ciphertext, aad)
                    if len(seed) < 16:
                        tail_truncated = True
                        break

                    entry_hashes.append(expected_entry_hash)
                    expected_merkle_root = build_merkle_root_hex(entry_hashes)
                    if str(record["merkle_root"]) != expected_merkle_root:
                        tail_truncated = True
                        break
                    last_seed = seed
                    last_sequence = int(record["sequence"])
                    expected_next_sequence = last_sequence + 1
                    valid_tail_offset = offset
                except Exception:
                    tail_truncated = True
                    break

        if tail_truncated:
            self._truncate_to(valid_tail_offset)

        self._entry_hashes = entry_hashes
        self._last_seed = last_seed
        self._last_sequence = last_sequence
        merkle_root = build_merkle_root_hex(entry_hashes)
        return EntropyJournalState(
            recovered_entries=len(entry_hashes),
            last_sequence=last_sequence,
            last_seed=last_seed,
            merkle_root=merkle_root,
            tail_truncated=tail_truncated,
        )

    def _truncate_to(self, length: int) -> None:
        with self.journal_path.open("rb+") as handle:
            handle.truncate(length)
            handle.flush()
            os.fsync(handle.fileno())

    @staticmethod
    def _validate_record_shape(record: Any) -> None:
        if not isinstance(record, dict):
            raise ValueError("journal record is not an object")
        required = {
            "v": int,
            "sequence": int,
            "timestamp": str,
            "nonce_hex": str,
            "ciphertext_hex": str,
            "request_hash": str,
            "mac_hex": str,
            "entry_hash": str,
            "merkle_root": str,
        }
        for field_name, expected_type in required.items():
            if field_name not in record or not isinstance(record[field_name], expected_type):
                raise ValueError(f"missing/invalid field {field_name}")
        if int(record["v"]) != 1:
            raise ValueError("unsupported journal version")
