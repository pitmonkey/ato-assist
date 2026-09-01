#!/usr/bin/env python3
"""SessionStart hook: open a session with the marking, the glossary, and derived status.

Inert outside an assessment repository. Same envelope as the guards: never raise, exit 0.
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
    from ato_assist.session import brief

    context = brief(payload.get("cwd") or ".")
    if context:
        sys.stdout.write(
            json.dumps(
                {
                    "hookSpecificOutput": {"hookEventName": "SessionStart"},
                    "additionalContext": context,
                }
            )
        )


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass  # never disrupt the session
    sys.exit(0)
