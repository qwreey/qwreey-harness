#!/usr/bin/env python3
"""PreToolUse(Bash) guard: heavy runs (bench/fuzz/perf/stress) must be wrapped in choom.

Why: the container's memory cgroup is shared with every Claude session. A benchmark that
eats the remaining headroom triggers the cgroup OOM killer, which picks by oom_score —
and once killed a Claude process (2026-09-28, Q135 bench exit 137). We cannot lower
Claude's score (no CAP_SYS_RESOURCE), but raising a child's score is unprivileged and
inherited across exec, so `choom -n 1000 -- <cmd>` makes the heavy tree the first victim.

Heuristic (cheap on purpose — a false positive only costs a retry with choom):
  block when ONE segment (split on && || ; | newline) executes a program (luau / lune / bash / sh /
  python / node / hyperfine / ./x.sh) and that same segment mentions a heavy keyword, unless the command
  already contains the wrapper or is a git/gh command (commit messages mention these words).
  Heredoc bodies are dropped first: they are data (reports, edit scripts), and their lines would
  otherwise be mistaken for segment heads.
  A variable assigned a keyword value (`F=a/fuzz.luau; luau $F`) carries the keyword to the segments that expand it. Keywords in other segments do not count, except a `cd` into a keyword directory, which carries over to later toolkit runners and scripts (`cd fuzz && luau a.luau`, `cd bench && ./run.sh`) but not to interpreters (`cd bench && python3 summarize.py`).

Portable: the wrapper comes from ~/.claude/harness.env (HARNESS_HEAVY_WRAP). Empty, or its program not
installed (no choom in this sandbox) -> the guard allows everything. Executors are a base set plus a
per-toolkit table, filtered by HARNESS_TOOLKITS; HARNESS_HEAVY_EXECUTORS / _KEYWORDS add more.
"""
import json
import os
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # python3 -I 는 스크립트 디렉터리를 path 에 넣지 않는다
from shell_segments import segments, strip_heredocs  # self-match-guard.py 와 같이 쓴다

BASE_KEYWORDS = ["bench", "fuzz", "perf(?:orm(?:ance)?)?(?![A-Za-z])", "stress", "soak", "load-?test", "hyperfine"]
BASE_EXECUTORS = {"bash", "sh", "zsh", "python", "python3", "node", "hyperfine"}
# 툴킷마다 무거운 실행을 띄우는 실행기. 새 툴킷은 여기에 한 줄 더한다(q 플러그인 skills/doctor/references/toolkits/README.md).
TOOLKIT_EXECUTORS = {
    "luau": {"luau", "lune", "lute"},
    "web": {"npm", "npx", "pnpm", "yarn", "bun", "deno", "vitest"},
    "rust": {"cargo"},
}
# 이 훅만 읽는 harness.env 키: 위 표에 더할 실행기와 키워드(공백 구분). 더하기만 하므로 저장소 층도 정할 수 있다.
# HARNESS_HEAVY_WRAP, HARNESS_TOOLKITS 는 여러 플러그인이 읽는 키라 harness_env.DEFAULTS 에 있다.
ENV_DEFAULTS = {"HARNESS_HEAVY_EXECUTORS": "", "HARNESS_HEAVY_KEYWORDS": ""}
EXEMPT_HEADS = {"git", "gh"}
DELEGATE_SCRIPTS = ("delegate.py", "delegate.sh")  # file names of qwreey-delegate's driver; see main()


ASSIGN = re.compile(r"(?:^|[;&|\s(])([A-Za-z_][A-Za-z0-9_]*)=(\S*)")


# Timing calls mark a benchmark far more precisely than the keywords; used only on heredoc bodies.
TIMING = re.compile(r"os\.clock\(|perf_counter|timeit|performance\.now\(|hrtime|Instant::now")


def is_executor(head, executors):
    return head in executors or head.endswith(".sh") or head.startswith("./")


def load_env(cwd=None):
    """harness.env 층(옆의 harness_env.py 사본). 깨졌으면 {}(= 기본값 auto).
    HARNESS_HEAVY_WRAP 은 USER_ONLY 라 저장소 파일이 바꾸지 못한다. 저장소는 실행기와 키워드를 더할 수만 있다."""
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import harness_env
        return harness_env.load_layers(harness_env.project_dir(cwd), defaults=ENV_DEFAULTS)
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


def runs_heavy(segs, executors, heavy, uses, timed=False):
    """True when an executor segment names a heavy keyword (directly or via a keyword variable).

    `cd <fuzz-dir> && luau axes.luau` keeps the keyword in the cd segment; the directory carries over to
    later segments, but only for toolkit runners and scripts (`./x`, `*.sh`). Interpreters (python3, bash -c)
    run inside such directories mostly to aggregate or edit results, so they do not inherit it.
    `timed` (a heredoc body with timing calls: `cat > b.luau <<EOF ... os.clock() ... EOF; luau b.luau`)
    carries over the same way.
    """
    carry = timed
    for h, seg in segs:
        if h in ("cd", "pushd"):
            carry = carry or bool(heavy.search(seg))
            continue
        if not is_executor(h, executors):
            continue
        if heavy.search(seg) or (uses and uses.search(seg)):
            return True
        if carry and (h not in BASE_EXECUTORS or h.startswith("./") or h.endswith(".sh")):
            return True
    return False


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0
    if not isinstance(data, dict):  # 객체가 아닌 입력은 읽지 않는다(다른 훅과 같이 조용히 끝난다)
        return 0
    if os.name == "nt":  # choom 과 공유 메모리 cgroup 은 Linux 의 일이다. Windows 에서는 래퍼 설정과 상관없이 막지 않는다
        return 0
    tool_input = data.get("tool_input")
    cmd = tool_input.get("command") if isinstance(tool_input, dict) else None
    cmd = cmd if isinstance(cmd, str) else ""
    env = load_env(data.get("cwd"))
    wrap = wrap_argv(env)
    if not wrap:  # 래퍼를 끈 환경이거나 래퍼 프로그램이 없다(choom 없는 sandbox) - 막지 않는다
        return 0
    executors, heavy = rules(env)
    # The delegate driver (delegate.py, its delegate.sh wrapper, the old agy-delegate.sh) puts choom in front of its
    # own setpriv launch, so the whole agent tree is already the preferred victim; its prompt text may mention
    # bench/perf freely.
    if wrap[0] in cmd or any(d in cmd for d in DELEGATE_SCRIPTS) or not (heavy.search(cmd) or TIMING.search(cmd)):
        return 0
    segs = list(segments(cmd))
    if segs and segs[0][0] in EXEMPT_HEADS:
        return 0
    # `F=x/fuzz.luau; luau $F` keeps the keyword in the assignment segment: a variable whose value
    # carries a keyword counts as a keyword wherever it is expanded.
    bodies = []
    names = [m.group(1) for m in ASSIGN.finditer(strip_heredocs(cmd, bodies)) if heavy.search(m.group(2))]
    uses = re.compile(r"\$\{?(?:" + "|".join(names) + r")(?![A-Za-z0-9_])") if names else None
    if not runs_heavy(segs, executors, heavy, uses, bool(TIMING.search("\n".join(bodies)))):
        return 0
    if wrap[0] == "choom":
        how = ("Re-run with `choom -n 1000 -p $$;` prepended (this shell and its children become the first OOM victims), "
               "or wrap it: `choom -n 1000 -- prlimit --data=3221225472 -- <command>`.")
    else:
        how = f"Re-run wrapped as `{' '.join(wrap)} <command>`."
    reason = (
        "Bench/fuzz/perf/stress-looking runs must raise their OOM-victim rank first. The container's memory cgroup is shared "
        "by every Claude session, and the OOM killer has killed a Claude process before. " + how +
        " If this is a false positive, wrapping the same way passes."
    )
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # python3 -I 는 스크립트 디렉터리를 path 에 넣지 않는다
    import harness_nonce
    reason = f'<harness-hook name="heavy-proc-guard" level="action"{harness_nonce.attr(data.get("session_id"))}>\n{reason}\n</harness-hook>'
    json.dump({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": reason,
    }}, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
