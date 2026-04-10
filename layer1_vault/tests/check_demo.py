from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    command = [
        sys.executable,
        "layer1_vault/ui_sim/flex_demo.py",
        "--rounds",
        "1",
        "--guesses-per-round",
        "10",
        "--refresh-delay",
        "0",
    ]
    completed = subprocess.run(command, cwd=repo_root)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
