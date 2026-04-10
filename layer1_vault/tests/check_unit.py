from __future__ import annotations

import subprocess
import sys
from pathlib import Path

try:
    from .runtime_env import build_subprocess_env
except ImportError:
    from runtime_env import build_subprocess_env


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    command = [
        sys.executable,
        "-m",
        "unittest",
        "discover",
        "-s",
        "layer1_vault/tests",
        "-v",
    ]
    completed = subprocess.run(
        command,
        cwd=repo_root,
        env=build_subprocess_env(repo_root),
    )
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
