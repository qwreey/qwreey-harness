#!/usr/bin/env python3
"""q 상시 규약 주입. 사용: python3 -I ambient.py <SessionStart|SubagentStart|UserPromptSubmit|PreCompact>  (stdin: 훅 JSON)

context/ambient.md(영어, 사용자가 확정한 문구 그대로)를 `<plugin name="q">` 로 감싸 additionalContext 로 낸다.
태그 끝에 이 세션의 nonce 속성을 달고, SessionStart, SubagentStart 에서 규칙 줄을 맡으면 블록 맨 앞에 싣는다(harness_nonce.py).
- SessionStart: 메인 세션에 startup·resume·clear·compact 마다 실린다(hooks.json 의 matcher).
- SubagentStart: 서브에이전트에 실린다(.claude/audit/32 실험 2: general-purpose·커스텀(omitClaudeMd 여부 무관)·Explore 모두 실림).
  fork 는 부모 문맥(SessionStart 주입 포함)을 물려받으므로 건너뛴다(중복 방지).
- UserPromptSubmit: SessionStart 가 안 돈 세션(플러그인을 세션 중간에 켠 경우)의 보충. (세션, compact 회차) 표지가 없으면
  한 번 싣고 표지를 둔다. SessionStart 도 같은 표지를 두므로 겹치지 않는다. 회차는 compact_epoch.py(q 자기 것,
  $TMPDIR/claude-q-epoch/<sid>)를 읽기만 하고, 올리는 쪽은 PreCompact 의 hook.py 다. PreCompact 가 SessionStart(compact) 보다
  먼저라 두 훅 사이에 경합이 없다.
- PreCompact: 요약기에게 이 블록을 요약에서 빼라는 한 줄(OMIT_LINE)을 일반 stdout 으로 낸다. SessionStart(compact) 가 요약 뒤에
  다시 실으므로, 요약이 풀어 쓴 사본까지 남으면 같은 규약이 두 번 실린다. OMIT_LINE 은 lib/harness_texts.py 의
  사본이다(다른 플러그인도 같다). 서브에이전트(agent_id)의 compact 뒤에는 SessionStart 가 다시 싣지 않으므로 내지 않는다. 끄기 스위치가 켜졌거나
  파일이 비면 블록이 없으니 내지 않는다.
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
import harness_nonce  # noqa: E402
FILE = os.path.join(os.path.dirname(HERE), "context", "ambient.md")
SKIP_AGENTS = {"fork"}
NS = "claude-q-ambient"
EVENTS = ("SessionStart", "SubagentStart", "UserPromptSubmit")
TAG = "q"
# @start-replace: lib/harness_texts.py#OMIT_LINE value=string template="OMIT_LINE = {value}"
OMIT_LINE = "Omit the {block} block from the summary; it is re-injected after compaction."
# @end-replace


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
    rule = harness_nonce.rule_for(event, data)
    body = (rule + "\n" if rule else "") + text.strip("\n")
    ctx = f'<plugin name="{TAG}"{harness_nonce.attr(data.get("session_id"))}>\n' + body + "\n</plugin>"
    return json.dumps({"hookSpecificOutput": {"hookEventName": event, "additionalContext": ctx}}, ensure_ascii=False)


def precompact(data: dict, text: str) -> str:
    """PreCompact 에 낼 일반 텍스트 한 줄. 내지 않으면 ""."""
    if data.get("agent_id") or not text.strip():
        return ""
    return OMIT_LINE.format(block=f'<plugin name="{TAG}">')


def _off() -> bool:
    """끄기 스위치: 환경 변수가 이기고, 없으면 harness.env(하네스 lib/harness_env.py)."""
    if "HARNESS_Q_AMBIENT" in os.environ:
        return os.environ["HARNESS_Q_AMBIENT"].strip().lower() == "off"
    try:
        import importlib.util
        cd = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude")
        spec = importlib.util.spec_from_file_location("harness_env", os.path.join(cd, "lib", "harness_env.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return str(mod.load([os.path.join(cd, "harness.env")]).get("HARNESS_Q_AMBIENT", "")).strip().lower() == "off"
    except Exception:
        return False


def main() -> int:
    if _off():
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
    event = sys.argv[1] if len(sys.argv) > 1 else ""
    out = precompact(data, text) if event == "PreCompact" else build(event, data, text)
    if out:
        print(out)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
