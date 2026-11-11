#!/usr/bin/env python3
"""readonly-for-reviewers 회귀. 실행: python3 -I test-readonly-for-reviewers.py (exit 0 = 통과)
이 플러그인의 검토 에이전트일 때만 읽기 전용 가드가 걸리고, 그 밖의 세션·에이전트는 통과하는지 본다."""
import json
import os
import subprocess
import sys

HOOK = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks", "readonly-for-reviewers.py")
CASES = [
    # (기대 종료 코드, agent_type, 도구, 입력)
    (2, "second-opinion:reviewer", "Bash", {"command": "rm -rf src"}),
    (2, "second-opinion:other-frame", "Write", {"file_path": "/code/Projects/x/a.md"}),
    (2, "second-opinion-context", "Bash", {"command": "git commit -am x"}),
    (0, "second-opinion:reviewer", "Bash", {"command": "git diff HEAD~1 -- src"}),
    (0, "second-opinion:reviewer", "Write", {"file_path": "/tmp/claude-audit/S1/probe.luau"}),
    (2, "second-opinion:reviewer", "Write", {"file_path": "/tmp/claude-audit/probe.luau"}),  # 세션 폴더 밖
    (2, "second-opinion:reviewer", "Write", {"file_path": "/tmp/claude-audit/S2/probe.luau"}),  # 다른 세션의 스크래치
    (2, "second-opinion:reviewer", "Write", {"file_path": "/tmp/claude-audit/S1/../S2/p.luau"}),
    (0, "second-opinion:reviewer", "Bash", {"command": "mkdir -p /tmp/claude-audit/$CLAUDE_CODE_SESSION_ID && echo x > /tmp/claude-audit/S1/a"}),
    (0, "second-opinion:reviewer", "Bash", {"command": "mkdir -p /tmp/claude-audit/${CLAUDE_CODE_SESSION_ID}"}),
    (2, "second-opinion:reviewer", "Bash", {"command": "rm -rf /tmp/claude-audit/S2"}),
    (2, "second-opinion:reviewer", "Bash", {"command": "rm -rf /tmp/claude-audit"}),
    (0, None, "Bash", {"command": "rm -rf build"}),
    (0, "general-purpose", "Write", {"file_path": "/code/Projects/x/a.md"}),
    (0, "reviewer", "Bash", {"command": "rm -rf build"}),  # 다른 플러그인·사용자의 같은 이름은 건드리지 않는다
]
fail = 0
for want, agent, tool, ti in CASES:
    d = {"tool_name": tool, "tool_input": ti, "cwd": "/code/Projects/x", "session_id": "S1"}
    if agent:
        d["agent_type"] = agent
    rc = subprocess.run([sys.executable, "-I", HOOK], input=json.dumps(d), capture_output=True, text=True).returncode
    if rc != want:
        fail += 1
        print(f"FAIL: {agent} {tool} {ti} → {rc}, 기대 {want}")
rc = subprocess.run([sys.executable, "-I", HOOK], input="not json", capture_output=True, text=True).returncode
if rc != 0:
    fail += 1
    print("FAIL: 깨진 입력은 통과해야 한다")
print(f"{len(CASES) + 1 - fail}/{len(CASES) + 1}")
sys.exit(1 if fail else 0)
