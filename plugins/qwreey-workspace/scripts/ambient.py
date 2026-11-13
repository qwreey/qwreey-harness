#!/usr/bin/env python3
"""qwreey-workspace 규약 주입. 사용: python3 -I ambient.py <SessionStart|SubagentStart|PreCompact>  (stdin: 훅 JSON)

context/ambient.md 를 additionalContext 로 낸다. SessionStart 는 메인 세션(startup·resume·clear·compact), SubagentStart 는
서브에이전트에 싣는다(게이트는 서브에이전트의 쓰기도 막으므로 규약을 알아야 한다). fork 는 부모 문맥을 물려받으므로 건너뛴다.
PreCompact 는 요약기에게 이 블록을 요약에서 빼라는 한 줄을 일반 stdout 으로 낸다. SessionStart(compact) 가 요약 뒤에 다시 실으므로
요약의 사본까지 남으면 두 번 실린다. 서브에이전트(agent_id)의 compact 뒤에는 다시 싣지 않으므로 내지 않는다.
태그 끝에 이 세션의 nonce 속성을 달고, 규칙 줄을 맡으면 블록 맨 앞에 싣는다(harness_nonce.py).
파일이 없거나 읽기 실패는 조용히 넘긴다(훅은 세션을 막지 않는다).
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # python3 -I 는 스크립트 디렉터리를 path 에 넣지 않는다
import harness_nonce  # noqa: E402

FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "context", "ambient.md")
EVENTS = ("SessionStart", "SubagentStart", "PreCompact")
TAG = "qwreey-workspace"
# @start-replace: lib/harness_texts.py#OMIT_LINE value=string template="OMIT_LINE = {value}"
OMIT_LINE = "Omit the {block} block from the summary; it is re-injected after compaction."
# @end-replace


def main():
    event = sys.argv[1] if len(sys.argv) > 1 else ""
    if event not in EVENTS:
        return 0
    try:
        data = json.load(sys.stdin)
    except Exception:
        data = {}
    if event == "SubagentStart" and isinstance(data, dict) and data.get("agent_type") == "fork":
        return 0
    try:
        with open(FILE, encoding="utf-8") as f:
            text = f.read().strip()
    except OSError:
        return 0
    if event == "PreCompact":
        if text and not (isinstance(data, dict) and data.get("agent_id")):
            print(OMIT_LINE.format(block=f'<plugin name="{TAG}">'))
        return 0
    if text:
        data = data if isinstance(data, dict) else {}
        rule = harness_nonce.rule_for(event, data)
        ctx = f'<plugin name="{TAG}"{harness_nonce.attr(data.get("session_id"))}>\n' + (rule + "\n" if rule else "") + text + "\n</plugin>"
        print(json.dumps({"hookSpecificOutput": {"hookEventName": event, "additionalContext": ctx}}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
