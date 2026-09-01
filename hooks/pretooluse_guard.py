#!/usr/bin/env python3
"""PreToolUse hook: enforce the ato-assist file contract.

House envelope: never raise, never block by accident, always exit 0. The only intentional
non-pass outcome is a structured deny from the validator.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _bootstrap import bootstrap  # noqa: E402


def main() -> None:
    payload = json.loads(sys.stdin.read())
    if not isinstance(payload, dict):
        return
    bootstrap()
    from ato_assist.hookio import handle_pre

    result = handle_pre(payload)
    if result:
        sys.stdout.write(json.dumps(result))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass  # never disrupt the session
    sys.exit(0)
