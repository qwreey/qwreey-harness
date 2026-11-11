#!/usr/bin/env python3
"""track-reviewer — 리뷰어(second-opinion:reviewer)마다 스크래치 폴더를 주고, 누가 불렀는지(main / subagent)를 짝짓는다.

같은 session_id 아래에서 메인과 일꾼 서브에이전트가 동시에 리뷰어를 띄울 수 있다. 훅 입력에는 부모를 알려 주는 필드가 없다
(SubagentStart/Stop 은 agent_id·agent_type 과 세션 공통 필드뿐이고 transcript_path 는 항상 메인 것, agent_transcript_path 는 평평한 subagents/ 폴더).
그래서 두 이벤트를 이어 붙인다.
  - PreToolUse(Agent|Task, subagent_type=second-opinion:reviewer)  호출자(입력에 agent_id 가 있으면 subagent, 없으면 main)를 세션별 대기열에 넣는다.
  - SubagentStart(^second-opinion:reviewer$)  대기열 맨 앞을 꺼내 agent_id → 호출자로 기록하고,
    /tmp/claude-audit/<session_id>/<agent_id>/ 를 만들어 additionalContext 로 알려 준다.
한계: 같은 세션에서 둘 이상이 거의 동시에 띄우면 대기열 순서와 시작 순서가 어긋나 호출자가 뒤바뀔 수 있다.
      거부된 호출이 남긴 항목은 120초 뒤 버린다. 짝을 못 찾으면 호출자를 알 수 없음("unknown")으로 두고, nudge 는 이를 main 으로 친다.
상태: $TMPDIR/claude-second-opinion/<session_id>.callers.json
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import time

REVIEWER = "second-opinion:reviewer"
SAFE_ID = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
SCRATCH_BASE = os.environ.get("CLAUDE_AUDIT_SCRATCH", "/tmp/claude-audit")
TTL = 120


def state_path(sid: str) -> str:
    d = os.path.join(tempfile.gettempdir(), "claude-second-opinion")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, re.sub(r"[^\w-]", "", sid or "nosession") + ".callers.json")


def load(sid: str) -> dict:
    try:
        st = json.load(open(state_path(sid)))
    except (OSError, ValueError):
        st = {}
    st.setdefault("queue", [])
    st.setdefault("map", {})
    return st


def save(sid: str, st: dict) -> None:
    p = state_path(sid)
    tmp = p + f".{os.getpid()}"
    json.dump(st, open(tmp, "w"))
    os.replace(tmp, p)


def main() -> int:
    data = json.load(sys.stdin)
    sid = data.get("session_id") or ""
    ev = data.get("hook_event_name") or ""
    if ev == "PreToolUse":
        ti = data.get("tool_input") or {}
        if ti.get("subagent_type") != REVIEWER:
            return 0
        st = load(sid)
        now = time.time()
        st["queue"] = [q for q in st["queue"] if now - q["t"] < TTL]
        st["queue"].append({"caller": "subagent" if data.get("agent_id") else "main", "t": now})
        save(sid, st)
        return 0
    if ev == "SubagentStart" and data.get("agent_type") == REVIEWER:
        aid = data.get("agent_id") or ""
        if not SAFE_ID.match(aid):
            return 0
        st = load(sid)
        now = time.time()
        st["queue"] = [q for q in st["queue"] if now - q["t"] < TTL]
        st["map"][aid] = st["queue"].pop(0)["caller"] if st["queue"] else "unknown"
        save(sid, st)
        base = os.path.join(SCRATCH_BASE, sid) if SAFE_ID.match(sid) else SCRATCH_BASE
        scratch = os.path.join(base, aid)
        os.makedirs(scratch, exist_ok=True)
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "SubagentStart",
            "additionalContext": f"Your scratch directory is {scratch}/ (already created). Write probe files only there; writes elsewhere are blocked."}}))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # 훅 오류로 작업을 막지 않는다
        print(f"track-reviewer: {e}", file=sys.stderr)
        sys.exit(0)
