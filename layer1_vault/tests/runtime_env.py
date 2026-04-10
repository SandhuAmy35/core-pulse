from __future__ import annotations

import os
from pathlib import Path


def test_artifact_root(repo_root: Path) -> Path:
    temp_root = repo_root / "layer1_vault" / "data" / "test_artifacts"
    temp_root.mkdir(parents=True, exist_ok=True)
    return temp_root


def build_subprocess_env(repo_root: Path) -> dict[str, str]:
    temp_root = test_artifact_root(repo_root)

    env = dict(os.environ)
    temp_path = str(temp_root.resolve())
    env["TMP"] = temp_path
    env["TEMP"] = temp_path
    env["TMPDIR"] = temp_path
    return env
