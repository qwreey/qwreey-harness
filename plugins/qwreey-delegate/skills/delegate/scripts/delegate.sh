#!/usr/bin/env bash
# delegate.sh - kept as a path only: running sessions and qwreey-proc-guard call this name. The driver is delegate.py
# next to it (stdlib Python, `python3 -I`); every subcommand, option and exit code is the driver's.
exec python3 -I "$(dirname "$(readlink -f "$0")")/delegate.py" "$@"
