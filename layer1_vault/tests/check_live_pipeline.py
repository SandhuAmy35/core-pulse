from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
import time
from pathlib import Path


def wait_for_exit(process: subprocess.Popen[str], timeout_seconds: float) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        code = process.poll()
        if code is not None:
            if code != 0:
                raise RuntimeError(f"process exited with code {code}")
            return
        time.sleep(0.25)
    raise TimeoutError("process did not exit before timeout")


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    database_path = repo_root / "layer1_vault" / "data" / "vault_test_check.db"
    entropy_journal_path = repo_root / "layer1_vault" / "data" / "vault_test_check_entropy.wal"
    daemon_log = repo_root / "layer1_vault" / "data" / "vault_test_daemon.log"

    for path in (database_path, entropy_journal_path, daemon_log):
        if path.exists():
            path.unlink()

    daemon_command = [
        sys.executable,
        "layer1_vault/src/main.py",
        "--max-messages",
        "3",
        "--database-path",
        str(database_path),
        "--entropy-journal-path",
        str(entropy_journal_path),
        "--api-cache-ttl",
        "60",
        "--log-level",
        "INFO",
    ]
    publisher_command = [
        sys.executable,
        "layer0_sentinel/mock_publisher.py",
        "--interval",
        "1.0",
        "--messages",
        "6",
    ]

    with daemon_log.open("w", encoding="utf-8") as daemon_output:
        daemon = subprocess.Popen(
            daemon_command,
            cwd=repo_root,
            stdout=daemon_output,
            stderr=subprocess.STDOUT,
            text=True,
        )
        try:
            time.sleep(2.0)
            publisher = subprocess.run(publisher_command, cwd=repo_root, check=True)
            _ = publisher
            wait_for_exit(daemon, timeout_seconds=30.0)
        finally:
            if daemon.poll() is None:
                daemon.terminate()
                try:
                    daemon.wait(timeout=5.0)
                except subprocess.TimeoutExpired:
                    daemon.kill()

    connection = sqlite3.connect(database_path)
    try:
        encrypted_row = connection.execute(
            """
            SELECT COUNT(*), MIN(sequence), MAX(sequence)
            FROM encrypted_telemetry
            """
        ).fetchone()
        proof_row = connection.execute(
            """
            SELECT COUNT(*)
            FROM encrypted_telemetry
            WHERE integrity_proof <> ''
            """
        ).fetchone()
        weather_row = connection.execute(
            """
            SELECT COUNT(*)
            FROM space_weather_samples
            """
        ).fetchone()
    finally:
        connection.close()

    summary = {
        "database_path": str(database_path),
        "encrypted_rows": encrypted_row[0],
        "sequence_min": encrypted_row[1],
        "sequence_max": encrypted_row[2],
        "proof_rows": proof_row[0],
        "space_weather_rows": weather_row[0],
        "entropy_journal_path": str(entropy_journal_path),
        "entropy_journal_exists": entropy_journal_path.exists(),
        "entropy_journal_size": entropy_journal_path.stat().st_size if entropy_journal_path.exists() else 0,
        "daemon_log": str(daemon_log),
    }
    print(json.dumps(summary, indent=2))

    if encrypted_row[0] < 1:
        raise SystemExit("expected at least one encrypted row")
    if proof_row[0] < 1:
        raise SystemExit("expected at least one integrity proof row")
    if weather_row[0] < 1:
        raise SystemExit("expected at least one space weather row")
    if not entropy_journal_path.exists() or entropy_journal_path.stat().st_size == 0:
        raise SystemExit("expected non-empty entropy journal WAL")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
