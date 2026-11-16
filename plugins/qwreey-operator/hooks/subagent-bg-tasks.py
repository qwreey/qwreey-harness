#!/usr/bin/env python3
"""subagent-bg-tasks: 서브에이전트가 자기 백그라운드 작업(셸, 자식 에이전트)을 돌려 둔 채 끝내려 하면 한 번 알린다(warn).

등록: SubagentStop. 메시지 규약: home/.claude/HOOK-MESSAGES.md("Stop·SubagentStop 에서 이어 가게 하는 출력").
- 입력의 background_tasks 는 세션 전체의 작업이라 메인의 셸도 들어 있고 주인을 밝히는 필드가 없다(실측은 docs/how-it-works.md).
  그래서 서브에이전트 트랜스크립트(agent_transcript_path)의 tool_result 글에 id 가 나온 작업만 그 서브에이전트의 것으로 본다
  (Bash 백그라운드 결과는 "Command running in background with ID: <id>" 꼴이다). 트랜스크립트를 못 읽으면 누구 것인지 모르니
  알리지 않는다. 그 가운데 status 가 running 이고 type 이 monitor 가 아닌 것을 센다. monitor 는 끝나기를 기다리는 작업이 아니라서
  뺀다(q 의 stale_work.py 와 같다).
- 내는 것: hookSpecificOutput.additionalContext. 메인에게는 가지 않고 그 서브에이전트에게 새 턴으로 들어가, 작업을 거두거나
  TaskStop 으로 멈춘 뒤 최종 보고를 다시 내게 한다. 메인은 그 에이전트의 마지막 답을 받으므로 다시 낸 보고가 전달된다.
- 통과(아무것도 내지 않음): stop_hook_active, 남은 작업 없음, 빈 답이나 오류, 한도 알림으로 끝난 턴, agent_id 없음, 이미 알린
  서브에이전트, 끄기 스위치, 어떤 실패든(fail-open, exit 0). 마지막 답이 질문이어도 알린다: 서브에이전트의 질문은 보고에 실려
  호출한 쪽에 가고, 다시 쓰는 보고에도 남는다.
- 한 번: (session_id, agent_id, compact 회차) 상태 파일을 O_EXCL 로 만든 쪽만 낸다(compact_epoch.state_path).
- 끄기: HARNESS_OPERATOR_SUBAGENT_BG=off. 환경 변수가 이기고, 없으면 harness.env 층(사용자 < 저장소 < 저장소 local).
"""
import json
import os
import re
import sys

PLUGIN = "qwreey-operator"
NAMESPACE = "claude-qwreey-operator-subagent-bg"
# harness.env 키(tools/tests/test-harness-env-owners.py 가 읽는다). 저장소 층이 꺼도 되는 스위치라 사용자 전용이 아니다.
OPERATOR_SUBAGENT_DEFAULTS = {"HARNESS_OPERATOR_SUBAGENT_BG": "on"}
OFF_VALUES = ("off", "0", "no")
DESC_MAX = 80  # 작업 설명은 한 줄로 자른다: 설명은 서브에이전트가 쓴 글이라 길이 제한이 없다
# @start-replace: lib/harness_texts.py#STOP_ERROR value=string template="STOP_ERROR = re.compile({value}, re.I)"
STOP_ERROR = re.compile("^\\s*(API Error|Prompt is too long|Context limit|Request timed out|Credit balance)", re.I)
# @end-replace

BODY = (
    "You are about to finish while background work you started is still running:\n{tasks}\n"
    "Collect their results, or stop them with TaskStop, unless your brief says to leave them running. "
    "Then give your final report again in full: your caller receives only your last message."
)


def here():
    d = os.path.dirname(os.path.abspath(__file__))
    if d not in sys.path:
        sys.path.insert(0, d)  # python3 -I 는 스크립트 디렉터리를 path 에 넣지 않는다


def is_off(cwd):
    name = "HARNESS_OPERATOR_SUBAGENT_BG"
    if name in os.environ:
        return os.environ[name].strip().lower() in OFF_VALUES
    here()
    import harness_env
    vals = harness_env.load_layers(harness_env.project_dir(cwd), defaults=OPERATOR_SUBAGENT_DEFAULTS)
    return str(vals.get(name, "")).strip().lower() in OFF_VALUES


def running_tasks(data):
    bg = data.get("background_tasks")
    if not isinstance(bg, list):
        return []
    me = data.get("agent_id")
    return [t for t in bg if isinstance(t, dict) and t.get("status") == "running" and t.get("type") != "monitor"
            and isinstance(t.get("id"), str) and t.get("id") and t.get("id") != me]


def tool_result_text(path):
    """서브에이전트 트랜스크립트의 tool_result 글을 모두 이은 것. 읽지 못하면 None."""
    if not isinstance(path, str) or not path:
        return None
    parts = []
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                if '"tool_result"' not in line:
                    continue  # 대부분의 줄은 파싱하지 않고 넘긴다
                try:
                    content = (json.loads(line).get("message") or {}).get("content")
                except ValueError:
                    continue
                for block in content if isinstance(content, list) else []:
                    if isinstance(block, dict) and block.get("type") == "tool_result":
                        inner = block.get("content")
                        parts.append(inner if isinstance(inner, str) else json.dumps(inner, ensure_ascii=False))
    except OSError:
        return None
    return "\n".join(parts)


def own_tasks(data, tasks):
    """tasks 가운데 이 서브에이전트가 띄운 것: 자기 tool_result 에 id 가 나온 작업."""
    text = tool_result_text(data.get("agent_transcript_path"))
    if not text:
        return []
    return [t for t in tasks if re.search(r"(?<![\w-])%s(?![\w-])" % re.escape(t["id"]), text)]


def one_line(value):
    s = " ".join(str(value or "").split())
    return s if len(s) <= DESC_MAX else s[: DESC_MAX - 3] + "..."


def task_line(t):
    desc = one_line(t.get("description") or t.get("name") or t.get("agent_type"))
    return "- %s %s: %s" % (one_line(t.get("type") or "task"), one_line(t.get("id")), json.dumps(desc, ensure_ascii=False))


def claim(sid, aid):
    """이 서브에이전트에게 처음이면 True. 상태 파일을 O_EXCL 로 만들어 병렬로 불려도 한 번만 낸다."""
    here()
    import compact_epoch
    path = compact_epoch.state_path(PLUGIN, NAMESPACE, sid, aid)
    try:
        os.close(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600))
    except FileExistsError:
        return False
    return True


def handle(data):
    if data.get("hook_event_name") != "SubagentStop" or data.get("stop_hook_active"):
        return ""
    sid, aid = data.get("session_id"), data.get("agent_id")
    if not sid or not aid:
        return ""
    msg = data.get("last_assistant_message")
    if isinstance(msg, str) and (not msg.strip() or STOP_ERROR.match(msg)):
        return ""
    tasks = running_tasks(data)
    if tasks:
        tasks = own_tasks(data, tasks)
    if not tasks or is_off(data.get("cwd")) or not claim(sid, aid):
        return ""
    here()
    import harness_nonce
    text = '<harness-hook name="subagent-bg-tasks" level="warn"%s>\n%s\n</harness-hook>' % (
        harness_nonce.attr(sid), BODY.format(tasks="\n".join(task_line(t) for t in tasks)))
    return json.dumps({"hookSpecificOutput": {"hookEventName": "SubagentStop", "additionalContext": text}}, ensure_ascii=False)


def main():
    try:
        data = json.load(sys.stdin)
        out = handle(data) if isinstance(data, dict) else ""
    except Exception:
        return 0
    if out:
        print(out)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
