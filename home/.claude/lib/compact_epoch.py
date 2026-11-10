"""Per-session dedup state keyed by (session_id, compact epoch). Standard library only.

Why: "tell the model once per session" hooks keep their state per session_id, but /compact keeps the
session_id while the summary drops earlier reminders from the model's context. So the dedup unit is
(session_id, compact epoch). hooks/rearm-on-compact.py (SessionStart, matcher "compact") calls bump();
the epoch then differs and every "once" reminder may fire again. Measured 2026-11-10 (audit/17): session_id
is unchanged across /compact; PreCompact, SessionStart(source=compact), PostCompact all fire.

Usage in a hook (load by path, like harness_env):
    ce = load_module(~/.claude/lib/compact_epoch.py)
    path = ce.state_path("claude-my-hook", session_id, data.get("agent_id"))   # $TMPDIR/claude-my-hook/<sid>.c<epoch>[.a<agent_id>].json
Files live under $TMPDIR (tempfile.gettempdir()); the epoch counter is $TMPDIR/claude-compact-epoch/<sid>.
"""
import os
import re
import tempfile


def _sid(session_id):
    return re.sub(r"[^\w-]", "", str(session_id or "nosession"))


def _epoch_path(session_id):
    return os.path.join(tempfile.gettempdir(), "claude-compact-epoch", _sid(session_id))


def epoch(session_id):
    try:
        return int(open(_epoch_path(session_id)).read().strip())
    except (OSError, ValueError):
        return 0


def bump(session_id):
    """Start a new epoch (call after a compact). Returns the new epoch."""
    n = epoch(session_id) + 1
    p = _epoch_path(session_id)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as f:
        f.write(str(n))
    return n


def state_path(namespace, session_id, agent_id=None):
    """Dedup state file for this hook in the current epoch; creates the directory.

    Hooks that fire inside a subagent get the PARENT's session_id plus agent_id (docs: common input fields;
    measured 2026-11-10). So the key is (session_id, agent_id or main, epoch): a subagent consuming a "once per
    epoch" reminder must not use it up for the main conversation, nor the other way round. Pass data.get("agent_id")."""
    d = os.path.join(tempfile.gettempdir(), namespace)
    os.makedirs(d, exist_ok=True)
    who = f".a{_sid(agent_id)}" if agent_id else ""
    return os.path.join(d, f"{_sid(session_id)}.c{epoch(session_id)}{who}.json")
