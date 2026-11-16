#!/usr/bin/env python3
"""self-match-guard 회귀. 실행: python3 -I tests/test-self-match-guard.py  (exit 0 = 통과)

훅이 판정한 자기 일치를 실제 pgrep 으로도 맞춰 본다(pgrep 이 있을 때만): `bash -c '<명령>'` 의 argv 에 명령 전체가 들어가므로
같은 패턴이 그 셸에 걸리는지가 훅의 판정과 같아야 한다.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HOOK = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks", "self-match-guard.py")
T = tempfile.mkdtemp(prefix="selfmatch-")
# nonce 는 고정 salt 로(실제 ~/.local/share 의 salt 를 쓰지 않게). salt "00"*32 + 세션 "abc" 의 nonce 는 39596342ed0e
open(os.path.join(T, "salt"), "w").write("00" * 32)
os.environ["QWREEY_HARNESS_SALT_FILE"] = os.path.join(T, "salt")
ok = fail = 0


def check(name, cond):
    global ok, fail
    if cond:
        ok += 1
    else:
        fail += 1
        print("FAIL", name)


def run(cmd, raw=None):
    p = subprocess.run([sys.executable, "-I", HOOK], capture_output=True, text=True, timeout=10,
                       input=raw if raw is not None else json.dumps({"session_id": "abc", "tool_input": {"command": cmd}}))
    assert p.returncode == 0, p.stderr
    return json.loads(p.stdout) if p.stdout.strip() else None


def denied(o):
    return ((o or {}).get("hookSpecificOutput") or {}).get("permissionDecision") == "deny"


def level(o):
    ctx = ((o or {}).get("hookSpecificOutput") or {}).get("additionalContext") or ""
    return "warn" if 'level="warn"' in ctx else "info" if 'level="info"' in ctx else None


INCIDENT = 'until ! pgrep -f "test-delegate-cli.py" >/dev/null; do sleep 2; done; cat /tmp/claude-0/x/tasks/b1.output'
o = run(INCIDENT)
check("incident command denied", denied(o))
reason = o["hookSpecificOutput"]["permissionDecisionReason"]
check("deny is an action hook message with the nonce",
      reason.startswith('<harness-hook name="self-match-guard" level="action" nonce="39596342ed0e">\n'))
for part in ("pgrep -x <process name>", '"[t]est-delegate-cli.py"', "run_in_background", "never ends"):
    check("deny reason names " + part, part in reason)

for c in ["while pgrep -f my-job; do sleep 1; done",
          "while true; do pgrep -f my-job || break; sleep 5; done",
          'while [ -n "$(pgrep -f foo.py)" ]; do sleep 1; done',
          "until [ -z \"`pgrep -f foo.py`\" ]; do sleep 1; done",
          "while pgrep -fl worker >/dev/null\ndo\n  sleep 2\ndone",
          "cd /x && until ! pgrep -af 'python3 run.py'; do sleep 3; done",
          "P=test-delegate; until ! pgrep -f \"$P\"; do sleep 2; done",
          "while sleep 1; do pkill -f my-job; done",
          "until ! pgrep -u root -f my-job; do sleep 1; done",
          "until ! pkill -0 -f my-job; do sleep 1; done",
          "until ! pgrep --full my-job; do sleep 1; done"]:
    check("loop denied: " + c.replace("\n", "\\n"), denied(run(c)))

check("pkill -f outside a loop warns", level(run("pkill -f my-server")) == "warn")
check("pkill -9 -f warns", level(run("pkill -9 -f 'node server.js'")) == "warn")
check("pgrep -f outside a loop is info", level(run("pgrep -af python3")) == "info")
check("pgrep -fl in a pipeline is info", level(run("pgrep -fl worker | wc -l")) == "info")
check("for loop is not a wait loop", level(run("for i in 1 2; do pgrep -f job; done")) == "info")
check("loop closed before the call", level(run("while false; do :; done; pgrep -f job")) == "info")

for c in ['until ! pgrep -f "[t]est-delegate-cli.py"; do sleep 2; done',
          "until ! pgrep -x luau; do sleep 2; done",
          "until ! pgrep -A -f test-delegate; do sleep 2; done",
          "until ! pgrep -vf test-delegate; do sleep 2; done",
          "pgrep python3",
          "pkill -x node",
          "until ! pgrep -f \"$JOB\"; do sleep 2; done",
          "until ! pgrep -fx test-delegate; do sleep 2; done",
          'git commit -m "until pgrep -f x; do sleep 1; done"',
          "echo 'pgrep -f x in a while loop'",
          "grep -n 'pgrep -f' SKILL.md",
          "cat > notes.md <<'EOF'\nwhile pgrep -f job; do sleep 1; done\nEOF",
          "ls"]:
    check("passes: " + c.replace("\n", "\\n"), run(c) is None)
check("bracket trick still matches when the plain text appears elsewhere",
      denied(run('python3 test-delegate.py & until ! pgrep -f "[t]est-delegate"; do sleep 2; done')))
check("bad stdin is silent", run("", raw="{no") is None)
check("no command is silent", run("", raw=json.dumps({"tool_input": {}})) is None)

# 훅의 판정을 실제 pgrep 과 맞춰 본다: bash -c '<명령>' 이 떠 있는 동안 같은 패턴이 그 셸을 찾는가.
# 명령이 하나뿐이면 bash 가 exec 로 자기를 바꾸므로 `; true` 를 붙여 셸을 남긴다
if shutil.which("pgrep") and shutil.which("bash"):
    for pat, cmd in [("zz-selfmatch-a", "sleep 2; true zz-selfmatch-a"), ("[z]z-selfmatch-b", "sleep 2; true [z]z-selfmatch-b")]:
        p = subprocess.Popen(["bash", "-c", cmd])
        try:
            subprocess.run(["sleep", "0.3"])
            real = subprocess.run(["pgrep", "-f", pat], capture_output=True).returncode == 0
        finally:
            p.kill()
            p.wait()
        hook = run("pgrep -f '%s' # %s" % (pat, cmd)) is not None
        check("hook agrees with real pgrep for " + pat, real == hook)
print(f"{ok}/{ok + fail}")
sys.exit(1 if fail else 0)
