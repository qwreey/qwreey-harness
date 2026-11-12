#!/usr/bin/env python3
"""q 상시 규약 주입. 사용: python3 -I ambient.py <SessionStart|SubagentStart>  (stdin: 훅 JSON)

context/ambient.md(영어, 사용자가 확정한 문구 그대로)를 `<plugin name="q">` 로 감싸 additionalContext 로 낸다.
- SessionStart: 메인 세션에 startup·resume·clear·compact 마다 실린다(hooks.json 의 matcher).
- SubagentStart: 서브에이전트에 실린다(.claude/audit/32 실험 2: general-purpose·커스텀(omitClaudeMd 여부 무관)·Explore 모두 실림).
  fork 는 부모 문맥(SessionStart 주입 포함)을 물려받으므로 건너뛴다(중복 방지).
- UserPromptSubmit: SessionStart 가 안 돈 세션(플러그인을 세션 중간에 켠 경우)의 보충. (세션, compact 회차) 표지가 없으면
  한 번 싣고 표지를 둔다. SessionStart 도 같은 표지를 두므로 겹치지 않는다. 회차는 compact_epoch.py(q 자기 것,
  $TMPDIR/claude-q-epoch/<sid>)를 읽기만 하고, 올리는 쪽은 PreCompact 의 hook.py 다. PreCompact 가 SessionStart(compact) 보다
  먼저라 두 훅 사이에 경합이 없다.
- 한계: 플러그인을 세션 중간에 끄면 이미 실린 맥락은 못 지운다. 플러그인 자신의 훅이 멈추므로 이 쪽에서 알아챌 수단이 없다(만들지 않음).
- 파일이 없거나 읽기 실패는 fail-open(아무것도 내지 않음). 끄기: HARNESS_Q_AMBIENT=off(환경 변수 또는 harness.env).
세션 기록(hook.py)과 따로 둔 이유: 그쪽 SessionStart 는 판단·분리 워커 흐름이라 섞이면 서로의 실패가 번진다.
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import compact_epoch  # noqa: E402
FILE = os.path.join(os.path.dirname(HERE), "context", "ambient.md")
SKIP_AGENTS = {"fork"}
NS = "claude-q-ambient"
EVENTS = ("SessionStart", "SubagentStart", "UserPromptSubmit")


def _sid(s) -> str:
    return re.sub(r"[^\w-]", "", str(s or "nosession"))


def _epoch(sid) -> int:
    return compact_epoch.epoch("q", sid)


def _marker(sid) -> str:
    return os.path.join(tempfile.gettempdir(), NS, _sid(sid) + ".json")


def _read_marker(sid) -> dict:
    try:
        return json.load(open(_marker(sid)))
    except Exception:
        return {}


def _write_marker(sid) -> None:
    try:
        os.makedirs(os.path.join(tempfile.gettempdir(), NS), exist_ok=True)
        json.dump({"epoch": _epoch(sid)}, open(_marker(sid), "w"))
    except OSError:
        pass


def injected(sid) -> bool:
    return _read_marker(sid).get("epoch") == _epoch(sid)


def build(event: str, data: dict, text: str) -> str:
    """주입할 JSON 문자열. 내지 않으면 ""."""
    if event not in EVENTS or not text.strip():
        return ""
    if event == "SubagentStart" and str(data.get("agent_type") or "") in SKIP_AGENTS:
        return ""
    if event == "UserPromptSubmit" and (data.get("agent_id") or injected(data.get("session_id"))):
        return ""
    if event in ("SessionStart", "UserPromptSubmit"):
        _write_marker(data.get("session_id"))
    ctx = '<plugin name="q">\n' + text.strip("\n") + "\n</plugin>"
    return json.dumps({"hookSpecificOutput": {"hookEventName": event, "additionalContext": ctx}}, ensure_ascii=False)


def main() -> int:
    try:
        import wslib
        if wslib.setting("HARNESS_Q_AMBIENT").strip().lower() == "off":
            return 0
    except Exception:
        if os.environ.get("HARNESS_Q_AMBIENT", "").strip().lower() == "off":
            return 0
    try:
        data = json.load(sys.stdin)
        if not isinstance(data, dict):
            data = {}
    except Exception:
        data = {}
    try:
        with open(FILE, encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return 0
    out = build(sys.argv[1] if len(sys.argv) > 1 else "", data, text)
    if out:
        print(out)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
