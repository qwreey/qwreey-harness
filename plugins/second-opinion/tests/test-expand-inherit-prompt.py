#!/usr/bin/env python3
"""expand-inherit-prompt 회귀. 실행: python3 -I test-expand-inherit-prompt.py (exit 0 = 통과)"""
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOK = os.path.join(ROOT, "hooks", "expand-inherit-prompt.py")
TPL = open(os.path.join(ROOT, "skills", "inherit-advisor", "templates", "fork-prompt.md"), encoding="utf-8").read().rstrip("\n")
REQ = open(os.path.join(ROOT, "skills", "inherit-advisor", "templates", "fork-prompt-reqs.md"), encoding="utf-8").read().strip()
TAG = "[second-opinion:inherit] Review only. Do not continue the work, edit files, or commit."
fails = 0


def run(tool_input, root=ROOT):
    env = dict(os.environ, CLAUDE_PLUGIN_ROOT=root)
    r = subprocess.run([sys.executable, "-I", HOOK], input=json.dumps({"tool_name": "Agent", "tool_input": tool_input}),
                       capture_output=True, text=True, env=env)
    out = json.loads(r.stdout)["hookSpecificOutput"] if r.stdout.strip() else None
    return r.returncode, out


def check(name, ok):
    global fails
    print(("ok   " if ok else "FAIL ") + name)
    fails += not ok


rc, o = run({"subagent_type": "fork", "description": "d", "prompt": TAG + "\nnext: 커밋한다"})
check("fork 표지는 템플릿으로 펼쳐진다", rc == 0 and o and o["updatedInput"]["prompt"] == TPL.replace("<다음 단계 한 줄>", "커밋한다"))
check("permissionDecision allow 와 나머지 입력 보존", o and o["permissionDecision"] == "allow" and o["updatedInput"]["description"] == "d" and o["updatedInput"]["subagent_type"] == "fork")
check("요구 대조 줄이 없다(옵션 없음)", o and REQ not in o["updatedInput"]["prompt"])

rc, o = run({"subagent_type": "fork", "prompt": TAG + "\nnext: x\noptions: reqs"})
lines = o["updatedInput"]["prompt"].split("\n") if o else []
i = next((k for k, l in enumerate(lines) if l.startswith("요청:")), -1)
check("options: reqs 는 요청: 줄 바로 뒤에 들어간다", i >= 0 and lines[i + 1] == REQ)

for name, ti in [
    ("fork 가 아니면 통과", {"subagent_type": "second-opinion:reviewer", "prompt": TAG + "\nnext: x"}),
    ("표지가 아니면 통과", {"subagent_type": "fork", "prompt": "그냥 요청"}),
    ("next 가 없으면 통과", {"subagent_type": "fork", "prompt": TAG}),
    ("prompt 가 문자열이 아니면 통과", {"subagent_type": "fork", "prompt": None}),
]:
    rc, o = run(ti)
    check(name, rc == 0 and o is None)

rc, o = run({"subagent_type": "fork", "prompt": TAG + "\nnext: x"}, root="/nonexistent")
check("템플릿이 없으면 통과", rc == 0 and o is None)
r = subprocess.run([sys.executable, "-I", HOOK], input="not json", capture_output=True, text=True)
check("깨진 입력은 통과", r.returncode == 0 and not r.stdout.strip())
sys.exit(1 if fails else 0)
