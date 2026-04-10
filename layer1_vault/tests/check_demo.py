from __future__ import annotations

import subprocess
import sys
from pathlib import Path

try:
    from .runtime_env import build_subprocess_env, test_artifact_root
except ImportError:
    from runtime_env import build_subprocess_env, test_artifact_root


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    artifact_root = test_artifact_root(repo_root)
    entropy_journal_path = artifact_root / "check_demo_entropy.wal"
    if entropy_journal_path.exists():
        entropy_journal_path.unlink()
    command = [
        sys.executable,
        "layer1_vault/ui_sim/flex_demo.py",
        "--rounds",
        "1",
        "--guesses-per-round",
        "10",
        "--refresh-delay",
        "0",
        "--entropy-journal-path",
        str(entropy_journal_path),
    ]
    completed = subprocess.run(
        command,
        cwd=repo_root,
        env=build_subprocess_env(repo_root),
    )
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
