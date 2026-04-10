from __future__ import annotations

import subprocess
import sys
from pathlib import Path

try:
    from .runtime_env import build_subprocess_env
except ImportError:
    from runtime_env import build_subprocess_env


def run_check(repo_root: Path, script_relative_path: str, env: dict[str, str]) -> None:
    command = [sys.executable, script_relative_path]
    completed = subprocess.run(command, cwd=repo_root, env=env)
    if completed.returncode != 0:
        raise SystemExit(f"check failed: {script_relative_path}")


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    env = build_subprocess_env(repo_root)
    checks = [
        "layer1_vault/tests/check_unit.py",
        "layer1_vault/tests/check_live_pipeline.py",
        "layer1_vault/tests/check_report.py",
        "layer1_vault/tests/check_demo.py",
    ]
    for check in checks:
        run_check(repo_root, check, env)
    print("All Layer 1 checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
