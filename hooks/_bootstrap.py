"""Put the ato_assist package on the path without a venv, an install, or an import cost.

An installed plugin has no virtualenv and nothing to pip install, so a hook finds its own
package next to itself. ``CLAUDE_PLUGIN_ROOT`` is used when set; falling back to the
script's own location keeps the hooks runnable straight from a checkout.
"""

import os
import sys
from pathlib import Path


def bootstrap() -> None:
    root = os.environ.get("CLAUDE_PLUGIN_ROOT") or str(Path(__file__).resolve().parent.parent)
    source = str(Path(root) / "src")
    if source not in sys.path:
        sys.path.insert(0, source)
