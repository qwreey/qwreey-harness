#!/usr/bin/env python3
"""readonly-for-reviewers — 이 플러그인의 검토 에이전트에게만 읽기 전용 가드를 건다.

플러그인 에이전트는 frontmatter 의 hooks 를 무시한다(code.claude.com plugins/components "Ignored fields").
그래서 PreToolUse 를 플러그인 hooks.json 에 걸고, 입력의 agent_type 이 이 플러그인의 검토자일 때만
auditor-readonly-guard.py(같은 폴더)에 넘긴다. 그 밖의 세션·에이전트는 그대로 통과한다.
  - agent_type 은 서브에이전트 안이거나 세션이 --agent 로 시작했을 때 들어온다(플러그인 에이전트는 "<플러그인>:<이름>").
  - ask-other-frame.py 는 --agent second-opinion-context 로 띄우므로 그 이름도 받는다.
"""
import os
import subprocess
import sys
import json

REVIEWERS = {"second-opinion:reviewer", "second-opinion:other-frame", "second-opinion-reviewer", "second-opinion-context"}

raw = sys.stdin.read()
try:
    agent = (json.loads(raw) or {}).get("agent_type") or ""
except ValueError:
    sys.exit(0)
if agent not in REVIEWERS:
    sys.exit(0)
guard = os.path.join(os.path.dirname(os.path.abspath(__file__)), "auditor-readonly-guard.py")
r = subprocess.run([sys.executable, "-I", guard], input=raw, text=True, capture_output=True)
sys.stdout.write(r.stdout)
sys.stderr.write(r.stderr)
sys.exit(r.returncode)
