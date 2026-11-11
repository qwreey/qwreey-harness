#!/usr/bin/env python3
"""ambient 훅 회귀. 실행: python3 -I test-ambient.py (exit 0 = 통과). 모델 호출 없음."""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
HOOK = os.path.join(os.path.dirname(HERE), "hooks", "ambient.py")
T = tempfile.mkdtemp(prefix="adv-ambient-")
ENV = {k: v for k, v in os.environ.items() if not k.startswith("HARNESS_")}
ENV["TMPDIR"] = T
ok = fail = 0


def run(event, extra=None, env=None, stdin=None):
    d = {"session_id": "s1", "hook_event_name": event}
    d.update(extra or {})
    p = subprocess.run([sys.executable, "-I", HOOK, event], input=json.dumps(d) if stdin is None else stdin,
                       capture_output=True, text=True, env=env or ENV, timeout=30)
    assert p.returncode == 0, p.stderr
    return json.loads(p.stdout) if p.stdout.strip() else None


def check(name, cond):
    global ok, fail
    if cond:
        ok += 1
    else:
        fail += 1
        print("FAIL", name)


def bump():
    d = os.path.join(T, "claude-qwreey-advisor-epoch")
    os.makedirs(d, exist_ok=True)
    f = os.path.join(d, "s1")
    n = int(open(f).read()) if os.path.exists(f) else 0
    with open(f, "w") as fh:
        fh.write(str(n + 1))


o = run("SessionStart", {"source": "startup"})
ctx = o["hookSpecificOutput"]["additionalContext"]
check("format", ctx.startswith('<plugin name="qwreey-advisor">\n') and ctx.endswith("</plugin>") and "call them yourself" in ctx)
check("ss marks", run("UserPromptSubmit") is None)
T2 = tempfile.mkdtemp(prefix="adv-ambient-")
ENV["TMPDIR"] = T2
T = T2
check("ups injects without SessionStart", run("UserPromptSubmit") is not None)
check("ups second no", run("UserPromptSubmit") is None)
bump()
check("ups after compact", run("UserPromptSubmit") is not None)
check("ups again no", run("UserPromptSubmit") is None)
check("off", run("SessionStart", env=dict(ENV, HARNESS_QWREEY_ADVISOR_AMBIENT="off")) is None)
check("bad stdin", run("SessionStart", stdin="x") is not None)
check("subagent ups", run("UserPromptSubmit", {"agent_id": "a"}) is None)
print(f"ok={ok} fail={fail}")
sys.exit(1 if fail else 0)
