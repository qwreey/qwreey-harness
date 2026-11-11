#!/usr/bin/env python3
"""heavy-proc-guard 회귀. 실행: python3 -I tests/test-heavy-proc-guard.py  (exit 0 = 통과)

harness.env 를 임시 CLAUDE_CONFIG_DIR 로 격리해 래퍼를 고정한다. 하네스 lib 가 없어도(기본값 auto) 도는지도 본다.
"""
import json
import os
import subprocess
import sys
import tempfile

HOOK = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks", "heavy-proc-guard.py")
T = tempfile.mkdtemp(prefix="procguard-")
ok = fail = 0


def check(name, cond):
    global ok, fail
    if cond:
        ok += 1
    else:
        fail += 1
        print("FAIL", name)


def run(cmd, wrap="choom -n 1000 --", raw=None):
    cfg = os.path.join(T, "cfg")
    os.makedirs(os.path.join(cfg, "lib"), exist_ok=True)
    if wrap is not None:
        src = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "home", ".claude", "lib", "harness_env.py")
        with open(src) as s, open(os.path.join(cfg, "lib", "harness_env.py"), "w") as d:
            d.write(s.read())
        with open(os.path.join(cfg, "harness.env"), "w") as f:
            f.write(f"HARNESS_HEAVY_WRAP={wrap}\n")
    env = {k: v for k, v in os.environ.items() if not k.startswith("HARNESS_")}
    env["CLAUDE_CONFIG_DIR"] = cfg if wrap is not None else os.path.join(T, "nocfg")
    p = subprocess.run([sys.executable, "-I", HOOK], input=raw if raw is not None else json.dumps({"tool_input": {"command": cmd}}),
                       capture_output=True, text=True, env=env, timeout=10)
    assert p.returncode == 0, p.stderr
    return json.loads(p.stdout) if p.stdout.strip() else None


def denied(o):
    return ((o or {}).get("hookSpecificOutput") or {}).get("permissionDecision") == "deny"


check("bench via bash denied", denied(run("bash run-bench.sh")))
check("deny message is an action hook message", run("python3 fuzz.py")["hookSpecificOutput"]["permissionDecisionReason"].startswith('<harness-hook name="heavy-proc-guard" level="action">'))
check("wrapped passes", run("choom -n 1000 -- bash run-bench.sh") is None)
check("git commit mentioning bench passes", run("git commit -m 'add bench'") is None)
check("no heavy keyword passes", run("python3 build.py") is None)
check("heavy word but no executor passes", run("echo bench") is None)
check("empty wrapper disables the guard", run("bash run-bench.sh", wrap="") is None)
check("bad stdin is silent", run("", raw="{no") is None)
check("no harness lib: defaults, no crash", run("ls", wrap=None) is None)
print(f"{ok}/{ok + fail}")
sys.exit(1 if fail else 0)
