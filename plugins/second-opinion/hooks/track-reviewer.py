#!/usr/bin/env python3
"""track-reviewer — 리뷰어(second-opinion:reviewer) 호출마다 실행 id 와 스크래치 폴더를 주고, 호출자(main / subagent)를 prompt 에 새긴다.

같은 session_id 아래에서 메인과 일꾼 서브에이전트가 동시에 리뷰어를 띄울 수 있다. 훅 입력에는 부모를 알려 주는 필드가 없어서
(SubagentStart/Stop 은 agent_id·agent_type 과 세션 공통 필드뿐) 호출 시점에 호출자를 prompt 에 적어 넣는다.
PreToolUse(Agent|Task, subagent_type=second-opinion:reviewer):
  - uuid4 를 만들고, 호출자(입력에 agent_id 가 있으면 subagent, 없으면 main)를 정하고,
    /tmp/claude-audit/<uuid>/ 를 만든 뒤 updatedInput 으로 prompt 끝에 한 줄을 붙인다.
      [second-opinion run: <uuid> caller=<main|subagent> scratch=/tmp/claude-audit/<uuid>/]
SubagentStop 쪽(second-opinion-nudge.py)은 리뷰어 transcript 의 첫 user 메시지에서 이 줄을 읽어 호출자를 안다(parse_run_line).
이 줄은 한 호출에 한 번만 붙는다(이미 있으면 그대로 둔다). 상태 파일은 없다.
"""
from __future__ import annotations

import json
import os
import re
import sys
import uuid

REVIEWER = "second-opinion:reviewer"
SCRATCH_BASE = os.environ.get("CLAUDE_AUDIT_SCRATCH", "/tmp/claude-audit")
RUN_LINE = re.compile(r"\[second-opinion run: ([0-9a-f-]{36}) caller=(main|subagent) scratch=[^\]\n]*\]")


def parse_run_line(text: str):
    """(run_id, caller) 마지막 일치. 없으면 None."""
    found = RUN_LINE.findall(text or "")
    return found[-1] if found else None


def main() -> int:
    data = json.load(sys.stdin)
    ti = data.get("tool_input") or {}
    if ti.get("subagent_type") != REVIEWER or not isinstance(ti.get("prompt"), str):
        return 0
    if parse_run_line(ti["prompt"]):
        return 0
    run = str(uuid.uuid4())
    caller = "subagent" if data.get("agent_id") else "main"
    scratch = os.path.join(SCRATCH_BASE, run)
    os.makedirs(scratch, exist_ok=True)
    updated = dict(ti)
    updated["prompt"] = ti["prompt"].rstrip("\n") + f"\n\n[second-opinion run: {run} caller={caller} scratch={scratch}/]"
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse", "permissionDecision": "allow",
        "permissionDecisionReason": "second-opinion: 리뷰어 실행 id 와 스크래치를 prompt 끝에 붙임",
        "updatedInput": updated}}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # 훅 오류로 작업을 막지 않는다
        print(f"track-reviewer: {e}", file=sys.stderr)
        sys.exit(0)
