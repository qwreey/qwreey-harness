#!/usr/bin/env python3
"""readonly-for-reviewers 회귀. 실행: python3 -I test-readonly-for-reviewers.py (exit 0 = 통과)
이 플러그인의 검토 에이전트일 때만 읽기 전용 가드가 걸리고, 그 밖의 세션·에이전트는 통과하는지 본다."""
import json
import os
import subprocess
import sys
import tempfile

T = tempfile.mkdtemp(prefix="ro-reviewers-")
os.environ["QWREEY_HARNESS_SALT_FILE"] = os.path.join(T, "salt")  # nonce 는 고정 salt 로
open(os.environ["QWREEY_HARNESS_SALT_FILE"], "w").write("00" * 32)
HOOK = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks", "readonly-for-reviewers.py")
# HOOK_TEST_BIN=<바이너리> 면 python 스크립트 대신 `<바이너리> hook readonly-for-reviewers` 를 하위 프로세스로 돌린다(Rust 판, crates/qwreey-advisor)
BIN = os.environ.get("HOOK_TEST_BIN")
CMD = [BIN, "hook", "readonly-for-reviewers"] if BIN else [sys.executable, "-I", HOOK]
CASES = [
    # (기대 종료 코드, agent_type, 도구, 입력)
    (2, "qwreey-advisor:reviewer", "Bash", {"command": "rm -rf src"}),
    (0, "qwreey-advisor-context", "Bash", {"command": "git commit -am x"}),
    (0, "qwreey-advisor:reviewer", "Bash", {"command": "git diff HEAD~1 -- src"}),
    (0, "qwreey-advisor:reviewer", "Write", {"file_path": "/tmp/claude-audit/S1/probe.luau"}),
    (0, "qwreey-advisor:reviewer", "Write", {"file_path": "/tmp/claude-audit/0b1f2c3d-aaaa-bbbb-cccc-123456789012/probe.luau"}),  # run 폴더
    (0, "qwreey-advisor:reviewer", "Write", {"file_path": "/tmp/claude-audit/S2/probe.luau"}),  # 가드는 run 을 모르므로 다른 run 도 허용
    (2, "qwreey-advisor:reviewer", "Write", {"file_path": "/tmp/claude-audit"}),
    (2, "qwreey-advisor:reviewer", "Write", {"file_path": "/tmp/claude-audit/../x.luau"}),
    (2, "qwreey-advisor:reviewer", "Write", {"file_path": "/tmp/claude-audit/S1/../../x.luau"}),
    (2, "qwreey-advisor:reviewer", "Write", {"file_path": "/tmp/other/probe.luau"}),
    (0, "qwreey-advisor:reviewer", "Bash", {"command": "mkdir -p /tmp/claude-audit/S1 && echo x > /tmp/claude-audit/S1/a"}),
    (2, "qwreey-advisor:reviewer", "Bash", {"command": "rm -rf /tmp/claude-audit"}),
    (0, None, "Bash", {"command": "rm -rf build"}),
    (0, "general-purpose", "Write", {"file_path": "/code/Projects/x/a.md"}),
    (0, "reviewer", "Bash", {"command": "rm -rf build"}),  # 다른 플러그인, 사용자의 같은 이름은 건드리지 않는다
]
fail = 0
for case in CASES:
    want, agent, tool, ti = case[:4]
    d = {"tool_name": tool, "tool_input": ti, "cwd": "/code/Projects/x", "session_id": "S1"}
    if len(case) > 4:
        d["agent_id"] = case[4]
    if agent:
        d["agent_type"] = agent
    rc = subprocess.run(CMD, input=json.dumps(d), capture_output=True, text=True).returncode
    if rc != want:
        fail += 1
        print(f"FAIL: {agent} {tool} {ti} {d.get('agent_id')} → {rc}, 기대 {want}")
rc = subprocess.run(CMD, input="not json", capture_output=True, text=True).returncode
if rc != 0:
    fail += 1
    print("FAIL: 깨진 입력은 통과해야 한다")
err = subprocess.run(CMD, capture_output=True, text=True, input=json.dumps(
    {"tool_name": "Bash", "tool_input": {"command": "rm -rf src"}, "cwd": "/code/Projects/x", "session_id": "S1", "agent_type": "qwreey-advisor:reviewer"})).stderr
if not err.startswith('<harness-hook name="auditor-readonly-guard" level="action" nonce="1c2df154ed44">\n'):
    fail += 1
    print("FAIL: 거절 사유 태그에 세션 nonce", err[:120])
print(f"{len(CASES) + 2 - fail}/{len(CASES) + 2}")
sys.exit(1 if fail else 0)
