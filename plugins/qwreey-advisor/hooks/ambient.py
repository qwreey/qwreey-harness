#!/usr/bin/env python3
"""qwreey-advisor 상시 규약 주입. 사용: python3 -I ambient.py <SessionStart|UserPromptSubmit>  (stdin: 훅 JSON)

context/ambient.md 를 `<plugin name="qwreey-advisor">` 로 감싸 additionalContext 로 낸다. 이 플러그인이 켜져 있을 때만
"qwreey-advisor 스킬을 스스로 부른다" 는 지시가 실리게 하려는 것이다(꺼진 스킬을 가리키면 틀린 지시).
- SessionStart(startup·resume·clear·compact): 메인 세션에만. 서브에이전트에는 안 싣는다.
- UserPromptSubmit: SessionStart 가 안 돈 세션(플러그인을 세션 중간에 켠 경우)의 보충. (세션, compact 회차) 표지가 없을 때 한 번.
  회차는 compact_epoch.py(이 플러그인 자기 것, $TMPDIR/claude-qwreey-advisor-epoch/<sid>)를 읽기만 한다. 올리는 쪽은 PreCompact 의
  같은 모듈이라 SessionStart(compact) 보다 먼저 끝난다(경합 없음).
- 한계: 플러그인을 세션 중간에 끄면 이미 실린 맥락은 못 지운다. 플러그인 자신의 훅이 멈추므로 알아챌 수단이 없다(만들지 않음).
- 파일이 없거나 읽기 실패는 fail-open. 끄기: HARNESS_QWREEY_ADVISOR_AMBIENT=off.
"""
import json
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import compact_epoch  # noqa: E402

FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "context", "ambient.md")
NS = "claude-qwreey-advisor-ambient"


def _sid(s):
    return re.sub(r"[^\w-]", "", str(s or "nosession"))


def _epoch(sid):
    return compact_epoch.epoch("qwreey-advisor", sid)


def _marker(sid):
    return os.path.join(tempfile.gettempdir(), NS, _sid(sid) + ".json")


def injected(sid):
    try:
        return json.load(open(_marker(sid)))["epoch"] == _epoch(sid)
    except Exception:
        return False


def mark(sid):
    try:
        os.makedirs(os.path.join(tempfile.gettempdir(), NS), exist_ok=True)
        json.dump({"epoch": _epoch(sid)}, open(_marker(sid), "w"))
    except OSError:
        pass


def build(event, data, text):
    if event not in ("SessionStart", "UserPromptSubmit") or not text.strip():
        return ""
    sid = data.get("session_id")
    if event == "UserPromptSubmit" and (data.get("agent_id") or injected(sid)):
        return ""
    mark(sid)
    ctx = '<plugin name="qwreey-advisor">\n' + text.strip("\n") + "\n</plugin>"
    return json.dumps({"hookSpecificOutput": {"hookEventName": event, "additionalContext": ctx}}, ensure_ascii=False)


def main():
    if os.environ.get("HARNESS_QWREEY_ADVISOR_AMBIENT", "").strip().lower() == "off":
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
