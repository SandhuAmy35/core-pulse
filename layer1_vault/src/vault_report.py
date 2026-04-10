from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

try:
    from .db_manager import VaultDatabase
except ImportError:
    from db_manager import VaultDatabase


def _rows_to_dicts(rows: list[Any]) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]


def build_report(database_path: str, recent_limit: int) -> dict[str, Any]:
    db = VaultDatabase(database_path)
    try:
        db.initialize()
        summary = dict(db.fetch_vault_summary())
        recent_records = _rows_to_dicts(db.fetch_recent_records(limit=recent_limit))
        recent_proofs = _rows_to_dicts(db.fetch_recent_proofs(limit=recent_limit))
        recent_weather = _rows_to_dicts(db.fetch_recent_space_weather_samples(limit=recent_limit))
    finally:
        db.close()

    return {
        "database_path": str(Path(database_path).resolve()),
        "summary": summary,
        "recent_records": recent_records,
        "recent_proofs": recent_proofs,
        "recent_space_weather_samples": recent_weather,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect Layer 1 vault metadata without exposing plaintext telemetry.")
    parser.add_argument(
        "--database-path",
        default=str(Path(__file__).resolve().parents[1] / "data" / "vault.db"),
    )
    parser.add_argument("--recent-limit", type=int, default=5)
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_report(args.database_path, args.recent_limit)
    if args.pretty:
        print(json.dumps(report, indent=2))
    else:
        print(json.dumps(report, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
