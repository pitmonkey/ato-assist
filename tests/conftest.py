"""Shared helpers for driving the hook entry points as real processes."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[1]

# What a hook actually does on startup: no venv, no install, just the package on the path.
HOOK_BOOTSTRAP = (
    f"import sys; sys.path.insert(0, {str(PLUGIN_ROOT / 'src')!r}); "
    "import ato_assist.hookio"
)


def run_hook(script: str, stdin: str, cwd: Path | None = None) -> tuple[int, str, str]:
    """Run a hook script the way Claude Code does and return (code, stdout, stderr)."""
    process = subprocess.run(
        [sys.executable, str(PLUGIN_ROOT / "hooks" / script)],
        input=stdin,
        capture_output=True,
        text=True,
        cwd=str(cwd or PLUGIN_ROOT),
        env={**os.environ, "CLAUDE_PLUGIN_ROOT": str(PLUGIN_ROOT)},
    )
    return process.returncode, process.stdout, process.stderr


def hook_json(stdout: str) -> dict[str, Any]:
    return json.loads(stdout) if stdout.strip() else {}
