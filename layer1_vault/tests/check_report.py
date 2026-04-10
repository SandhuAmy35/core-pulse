from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    database_path = repo_root / "layer1_vault" / "data" / "vault_test_check.db"
    if not database_path.exists():
        raise SystemExit(
            "database not found. Run layer1_vault/tests/check_live_pipeline.py first."
        )

    command = [
        sys.executable,
        "layer1_vault/src/vault_report.py",
        "--database-path",
        str(database_path),
        "--recent-limit",
        "3",
        "--verify-integrity",
    ]
    completed = subprocess.run(command, cwd=repo_root, check=True, capture_output=True, text=True)
    report = json.loads(completed.stdout)
    print(json.dumps(report, indent=2))
    if report["integrity_audit"]["failed_count"] != 0:
        raise SystemExit("expected vault integrity audit to pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
