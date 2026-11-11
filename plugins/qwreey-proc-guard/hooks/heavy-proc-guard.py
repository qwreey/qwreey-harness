#!/usr/bin/env python3
"""PreToolUse(Bash) guard: heavy runs (bench/fuzz/perf/stress) must be wrapped in choom.

Why: the container's memory cgroup is shared with every Claude session. A benchmark that
eats the remaining headroom triggers the cgroup OOM killer, which picks by oom_score —
and once killed a Claude process (2026-09-28, Q135 bench exit 137). We cannot lower
Claude's score (no CAP_SYS_RESOURCE), but raising a child's score is unprivileged and
inherited across exec, so `choom -n 1000 -- <cmd>` makes the heavy tree the first victim.

Heuristic (cheap on purpose — a false positive only costs a retry with choom):
  block when the command mentions a heavy keyword AND some segment executes a program
  (luau / lune / bash / sh / python / node / hyperfine / ./x.sh), unless the command
  already contains the wrapper or is a git/gh command (commit messages mention these words).

Portable: the wrapper comes from ~/.claude/harness.env (HARNESS_HEAVY_WRAP). Empty, or its program not
installed (no choom in this sandbox) -> the guard allows everything. Executors are a base set plus a
per-toolkit table, filtered by HARNESS_TOOLKITS; HARNESS_HEAVY_EXECUTORS / _KEYWORDS add more.
"""
import importlib.util
import json
import os
import re
import shutil
import sys
from pathlib import Path

BASE_KEYWORDS = ["bench", "fuzz", "perf(?:orm(?:ance)?)?(?![A-Za-z])", "stress", "soak", "load-?test", "hyperfine"]
BASE_EXECUTORS = {"bash", "sh", "zsh", "python", "python3", "node", "hyperfine"}
# 툴킷마다 무거운 실행을 띄우는 실행기. 새 툴킷은 여기에 한 줄 더한다(q 플러그인 skills/doctor/references/toolkits/README.md).
TOOLKIT_EXECUTORS = {
    "luau": {"luau", "lune", "lute"},
    "web": {"npm", "npx", "pnpm", "yarn", "bun", "deno", "vitest"},
    "rust": {"cargo"},
}
PREFIX_WORDS = {"(", "{", "time", "nice", "env", "command", "exec", "nohup"}
EXEMPT_HEADS = {"git", "gh"}


def segment_heads(cmd):
    for seg in re.split(r"&&|\|\||[;|\n]", cmd):
        words = seg.replace("(", " ( ").split()
        i = 0
        while i < len(words):
            w = words[i]
            if w in PREFIX_WORDS or re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=\S*", w):
                i += 1
            elif w == "timeout":
                i += 1
                while i < len(words) and (words[i].startswith("-") or re.fullmatch(r"[\d.]+[smhd]?", words[i])):
                    i += 2 if words[i] in ("-s", "-k", "--signal", "--kill-after") else 1
            elif w == "mise" and i + 1 < len(words) and words[i + 1] == "exec":
                i += 2
                if i < len(words) and words[i] == "--":
                    i += 1
            else:
                break
        if i < len(words):
            yield words[i]


def is_executor(head, executors):
    return head in executors or head.endswith(".sh") or head.startswith("./")


def load_env():
    """~/.claude/lib/harness_env.py 로 harness.env 를 읽는다. 없거나 깨졌으면 {}(= 기본값 auto)."""
    home = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
    try:
        spec = importlib.util.spec_from_file_location("harness_env", home / "lib" / "harness_env.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.load([home / "harness.env"])
    except Exception:
        return {}


def wrap_argv(env):
    w = (env.get("HARNESS_HEAVY_WRAP", "auto") or "").strip()
    if w == "auto":
        w = "choom -n 1000 --" if shutil.which("choom") else ""
    argv = w.split()
    return argv if argv and shutil.which(argv[0]) else []


def rules(env):
    enabled = set((env.get("HARNESS_TOOLKITS") or "").split()) or set(TOOLKIT_EXECUTORS)
    executors = set(BASE_EXECUTORS) | set((env.get("HARNESS_HEAVY_EXECUTORS") or "").split())
    for tk in enabled:
        executors |= TOOLKIT_EXECUTORS.get(tk, set())
    kws = BASE_KEYWORDS + [re.escape(k) for k in (env.get("HARNESS_HEAVY_KEYWORDS") or "").split()]
    return executors, re.compile(r"(?<![A-Za-z])(" + "|".join(kws) + ")", re.I)


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0
    cmd = (data.get("tool_input") or {}).get("command") or ""
    env = load_env()
    wrap = wrap_argv(env)
    if not wrap:  # 래퍼를 끈 환경이거나 래퍼 프로그램이 없다(choom 없는 sandbox) — 막지 않는다
        return 0
    executors, heavy = rules(env)
    # delegate.sh / agy-delegate.sh puts choom in front of its own setpriv launch, so the whole agy tree
    # is already the preferred victim; its prompt text may mention bench/perf freely.
    if wrap[0] in cmd or "delegate.sh" in cmd or not heavy.search(cmd):
        return 0
    heads = list(segment_heads(cmd))
    if heads and heads[0] in EXEMPT_HEADS:
        return 0
    if not any(is_executor(h, executors) for h in heads):
        return 0
    if wrap[0] == "choom":
        how = ("Re-run with `choom -n 1000 -p $$;` prepended (this shell and its children become the first OOM victims), "
               "or wrap it: `choom -n 1000 -- prlimit --data=3221225472 -- <command>`.")
    else:
        how = f"Re-run wrapped as `{' '.join(wrap)} <command>`."
    reason = (
        "Bench/fuzz/perf/stress-looking runs must raise their OOM-victim rank first. The container's memory cgroup is shared "
        "by every Claude session, and the OOM killer has killed a Claude process before (quad 2026-09-28). " + how +
        " If this is a false positive, wrapping the same way passes."
    )
    reason = f'<harness-hook name="heavy-proc-guard" level="action">\n{reason}\n</harness-hook>'
    json.dump({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": reason,
    }}, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
