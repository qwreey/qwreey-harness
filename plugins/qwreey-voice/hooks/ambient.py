#!/usr/bin/env python3
"""플러그인 상시 규약(ambient) 주입. 사용: python3 -I ambient.py [이벤트]  (stdin: 훅 JSON. 이벤트를 안 주면 hook_event_name)
@copy-of: lib/ambient.py
플러그인 사본(목록은 tools/tests/test-vendored-copies.py 의 EXPECTED)은 바이트가 같아야 한다. 고칠 때는 lib/ambient.py 만 고치고
python3 -I tools/sync-copies.py --apply 로 옮긴다. 플러그인마다 다른 것은 플러그인 루트의 context/(이 스크립트 디렉터리의 형제)에 둔다:
- context/ambient.json: 설정. 없거나 읽지 못하면 아무것도 내지 않는다.
    plugin      태그 이름(<plugin name="...">), 표지 이름공간(claude-<plugin>-ambient). 필수.
    events      켤 이벤트: SessionStart, SubagentStart, UserPromptSubmit, PreCompact 중에서.
    off_switch  끄기 스위치 이름(값이 off 면 끈다, 기본 on). 환경 변수가 이기고, 없으면 harness.env 층과 플러그인 옵션
                (옆의 harness_env.py 사본; userConfig 에 소문자 키를 boolean 으로 두면 대화상자에서 끈다). 없으면 스위치 없음.
    epoch       compact 회차 이름공간(compact_epoch.py). 기본은 plugin. UserPromptSubmit 보충만 쓴다.
- context/ambient.md: 메인 세션 글. context/subagent.md: 서브에이전트 글(없으면 ambient.md). 파일이 비면 블록이 없다.
  글 안의 HTML 주석(<!-- ... -->)은 사람용 메모라 싣지 않는다.

이벤트(hooks.json 에 등록하고 events 에도 넣어야 돈다):
- SessionStart: 메인 세션에 startup, resume, clear, compact 마다(hooks.json 의 matcher).
- SubagentStart: 서브에이전트에. fork 는 부모 문맥(SessionStart 주입 포함)을 물려받으므로 건너뛴다.
- UserPromptSubmit: SessionStart 가 안 돈 세션(플러그인을 세션 중간에 켠 경우)의 보충. (세션, compact 회차) 표지가 없으면
  한 번 싣고 표지를 둔다. SessionStart 도 같은 표지를 두므로 겹치지 않는다. 회차는 읽기만 하고, 올리는 쪽은 PreCompact 에 따로
  등록한 compact_epoch.py 다. PreCompact 가 SessionStart(compact) 보다 먼저라 경합이 없다. 서브에이전트(agent_id)는 건너뛴다.
- PreCompact: 요약기에게 이 블록을 요약에서 빼라는 한 줄(OMIT_LINE)을 일반 stdout 으로 낸다. SessionStart(compact) 가 요약 뒤에
  다시 실으므로, 요약이 풀어 쓴 사본까지 남으면 같은 규약이 두 번 실린다. 서브에이전트의 compact 뒤에는 SessionStart 가 다시
  싣지 않으므로 내지 않는다. SessionStart 가 꺼졌거나 메인 글이 비면 다시 실릴 블록이 없으니 내지 않는다.
태그 끝에 이 세션의 nonce 속성을 달고, SessionStart, SubagentStart 에서 규칙 줄을 맡으면 블록 맨 앞에 싣는다(harness_nonce.py).
한계: 플러그인을 세션 중간에 끄면 이미 실린 맥락은 못 지운다. 플러그인 자신의 훅이 멈추므로 알아챌 수단이 없다.
어떤 실패든 아무것도 내지 않고 exit 0(훅은 세션을 막지 않는다).
"""
import json
import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)  # python3 -I 는 스크립트 디렉터리를 path 에 넣지 않는다
CONTEXT = os.path.join(os.path.dirname(HERE), "context")
EVENTS = ("SessionStart", "SubagentStart", "UserPromptSubmit", "PreCompact")
SKIP_AGENTS = {"fork"}
# 글 파일의 메모: 사람이 남기는 줄이라 모델에게 싣지 않는다
NOTE_LINES = re.compile(r"^[ \t]*<!--(?:(?!-->).)*-->[ \t]*\n", re.M | re.S)
NOTE_INLINE = re.compile(r"[ \t]*<!--(?:(?!-->).)*-->", re.S)
# @start-replace: lib/harness_texts.py#OMIT_LINE value=string template="OMIT_LINE = {value}"
OMIT_LINE = "Omit the {block} block from the summary; it is re-injected after compaction."
# @end-replace


def load_config(context=CONTEXT):
    """ambient.json 을 읽어 고친 dict, 쓸 수 없으면 None."""
    try:
        with open(os.path.join(context, "ambient.json"), encoding="utf-8") as f:
            cfg = json.load(f)
    except (OSError, ValueError):
        return None
    if not isinstance(cfg, dict) or not isinstance(cfg.get("plugin"), str) or not cfg["plugin"]:
        return None
    events = cfg.get("events")
    cfg["events"] = [e for e in events if e in EVENTS] if isinstance(events, list) else []
    cfg["epoch"] = cfg.get("epoch") or cfg["plugin"]
    return cfg


def strip_notes(text):
    """HTML 주석(<!-- ... -->)을 뺀 글. 주석만 있던 줄은 줄째 뺀다. 닫히지 않은 주석은 그대로 둔다."""
    text = NOTE_LINES.sub("", text)
    return NOTE_INLINE.sub("", text)


def read_text(name, context=CONTEXT):
    try:
        with open(os.path.join(context, name), encoding="utf-8") as f:
            return strip_notes(f.read())
    except OSError:
        return ""


def is_off(name, cwd=None):
    """끄기 스위치: 환경 변수가 이기고, 없으면 harness.env 층(harness_env.load_layers: 사용자 < 저장소 < 저장소 local)."""
    if not name:
        return False
    if name in os.environ:
        return os.environ[name].strip().lower() == "off"
    try:
        import harness_env
        vals = harness_env.load_layers(harness_env.project_dir(cwd), defaults={name: "on"})
        return str(vals.get(name, "")).strip().lower() == "off"
    except Exception:
        return False


def _sid(s):
    return re.sub(r"[^\w-]", "", str(s or "nosession"))


def _epoch(cfg, sid):
    try:
        import compact_epoch
        return compact_epoch.epoch(cfg["epoch"], sid)
    except Exception:
        return 0


def _marker(cfg, sid):
    return os.path.join(tempfile.gettempdir(), "claude-%s-ambient" % _sid(cfg["plugin"]), _sid(sid) + ".json")


def injected(cfg, sid):
    try:
        with open(_marker(cfg, sid)) as f:
            return json.load(f).get("epoch") == _epoch(cfg, sid)
    except Exception:
        return False


def mark(cfg, sid):
    try:
        path = _marker(cfg, sid)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump({"epoch": _epoch(cfg, sid)}, f)
    except OSError:
        pass


def tag(cfg):
    return '<plugin name="%s">' % cfg["plugin"]


def build(cfg, event, data, main_text, sub_text=None):
    """주입할 JSON 문자열. 내지 않으면 ""."""
    import harness_nonce
    if event not in cfg["events"] or event == "PreCompact":
        return ""
    text = (main_text if sub_text is None else sub_text) if event == "SubagentStart" else main_text
    if not text.strip():
        return ""
    sid = data.get("session_id")
    if event == "SubagentStart" and str(data.get("agent_type") or "") in SKIP_AGENTS:
        return ""
    if event == "UserPromptSubmit" and (data.get("agent_id") or injected(cfg, sid)):
        return ""
    if event in ("SessionStart", "UserPromptSubmit") and "UserPromptSubmit" in cfg["events"]:
        mark(cfg, sid)
    rule = harness_nonce.rule_for(event, data)
    ctx = '<plugin name="%s"%s>\n' % (cfg["plugin"], harness_nonce.attr(sid)) + (rule + "\n" if rule else "") + text.strip("\n") + "\n</plugin>"
    return json.dumps({"hookSpecificOutput": {"hookEventName": event, "additionalContext": ctx}}, ensure_ascii=False)


def precompact(cfg, data, main_text):
    """PreCompact 에 낼 일반 텍스트 한 줄. 내지 않으면 ""."""
    if "PreCompact" not in cfg["events"] or "SessionStart" not in cfg["events"]:
        return ""
    if data.get("agent_id") or not main_text.strip():
        return ""
    return OMIT_LINE.format(block=tag(cfg))


def main():
    cfg = load_config()
    if cfg is None:
        return 0
    try:
        data = json.load(sys.stdin)
    except Exception:
        data = {}
    if not isinstance(data, dict):
        data = {}
    if is_off(cfg.get("off_switch"), data.get("cwd")):
        return 0
    event = sys.argv[1] if len(sys.argv) > 1 else str(data.get("hook_event_name") or "")
    main_text = read_text("ambient.md")
    if event == "PreCompact":
        out = precompact(cfg, data, main_text)
    else:
        sub = read_text("subagent.md") if event == "SubagentStart" and os.path.exists(os.path.join(CONTEXT, "subagent.md")) else None
        out = build(cfg, event, data, main_text, sub)
    if out:
        print(out)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
