#!/usr/bin/env python3
"""SessionStart(matcher "compact") hook: start a new compact epoch so once-per-session reminders may fire again.

/compact keeps session_id but drops earlier hook reminders from the model's context (see lib/compact_epoch.py).
Prints nothing; never blocks.
"""
import importlib.util
import json
import sys
from pathlib import Path


def main():
    try:
        data = json.load(sys.stdin)
        spec = importlib.util.spec_from_file_location("compact_epoch", Path(__file__).resolve().parent.parent / "lib" / "compact_epoch.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        if data.get("source", "compact") == "compact":
            mod.bump(data.get("session_id"))
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
