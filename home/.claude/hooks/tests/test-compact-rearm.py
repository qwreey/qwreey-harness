#!/usr/bin/env python3
"""compact 회차 dedup 회귀. 실행: python3 -I test-compact-rearm.py (exit 0 = 통과)

같은 (session_id, 회차) 에서는 한 번만 알리고, rearm-on-compact 가 회차를 올리면 다시 알려야 한다.
"""
import json
import re
import os
import shutil
import subprocess
import sys
import tempfile

H = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T = tempfile.mkdtemp(prefix="rearm-")
REPO = os.path.join(T, "repo")
os.makedirs(os.path.join(REPO, ".git"))
os.makedirs(os.path.join(REPO, "src"))
big = os.path.join(REPO, "src", "Big.luau")
open(big, "w").write("--!strict\n" + "local x = 1\n" * 900)
ENV = dict(os.environ, TMPDIR=T, CLAUDE_PROJECT_DIR=REPO)


def run(hook, data):
    p = subprocess.run([sys.executable, "-I", os.path.join(H, hook)], input=json.dumps(data), capture_output=True, text=True, env=ENV, timeout=10)
    assert p.returncode == 0, p.stderr
    return p.stdout.strip()


def bypass(sid):
    return run("bash-bypass-reminder.py", {"session_id": sid, "cwd": REPO, "tool_name": "Bash",
                                           "tool_input": {"command": "python3 -c 'print(1)'"}})


def struct(sid):
    return run("structure-reminder.py", {"session_id": sid, "cwd": REPO, "tool_name": "Edit",
                                         "tool_input": {"file_path": big, "old_string": "a", "new_string": "a\n"}, "tool_response": {}})


def rearm(sid, source="compact"):
    return run("rearm-on-compact.py", {"session_id": sid, "hook_event_name": "SessionStart", "source": source})


res = []
for name, fn in (("bash-bypass-reminder", bypass), ("structure-reminder", struct)):
    res.append((name + ": first call fires", bool(fn("a"))))
    res.append((name + ": same epoch is silent", fn("a") == ""))
    res.append((name + ": other session fires", bool(fn("b"))))
    rearm("a", "resume")
    res.append((name + ": SessionStart resume does not rearm", fn("a") == ""))
    rearm("a")
    res.append((name + ": new epoch fires again", bool(fn("a"))))
    res.append((name + ": then silent again", fn("a") == ""))
    res.append((name + ": other session unaffected by rearm", fn("b") == ""))
res.append(("bash-bypass-reminder interpreter note carries level=info", 'level="info">' in json.loads(bypass("lv"))["hookSpecificOutput"]["additionalContext"]))
res.append(("structure-reminder carries a level", bool(re.search(r'level="(info|warn|action)">', json.loads(struct("lv"))["hookSpecificOutput"]["additionalContext"]))))
# 성장 기준점은 session_id 단위: compact 전 +200, 회차를 올린 뒤 +150 이면 합계 +350 으로 grow 알림이 나와야 한다
grow = os.path.join(REPO, "src", "Grow.luau")


def grow_edit(sid, total, added):
    open(grow, "w").write("--!strict\n" + "local x = 1\n" * (total - 1))
    return run("structure-reminder.py", {"session_id": sid, "cwd": REPO, "tool_name": "Edit",
                                         "tool_input": {"file_path": grow, "old_string": "a", "new_string": "a" + "\n" * added}, "tool_response": {}})


g1 = grow_edit("g", 1100, 200)
res.append(("growth: +200 before compact is not a grow note", "grew" not in g1))
rearm("g")
g2 = grow_edit("g", 1250, 150)
res.append(("growth: baseline survives compact (+200 then +150 -> grow note)", "grew 900 -> 1250" in g2))
res.append(("rearm-on-compact prints nothing, bad stdin ok", run("rearm-on-compact.py", {}) == ""))
bad = subprocess.run([sys.executable, "-I", os.path.join(H, "rearm-on-compact.py")], input="{no", capture_output=True, text=True, env=ENV)
res.append(("rearm-on-compact survives bad stdin", bad.returncode == 0 and not bad.stdout))
for ok, name in [(r[1], r[0]) for r in res]:
    print(("PASS " if ok else "FAIL ") + name)
fails = [r for r in res if not r[1]]
print(f"{len(res) - len(fails)}/{len(res)}")
shutil.rmtree(T, ignore_errors=True)
sys.exit(1 if fails else 0)
