#!/usr/bin/env python3
"""qwreey-workspace 규약 주입. 사용: python3 -I ambient.py <SessionStart|SubagentStart>  (stdin: 훅 JSON)

context/ambient.md 를 additionalContext 로 낸다. SessionStart 는 메인 세션(startup·resume·clear·compact), SubagentStart 는
서브에이전트에 싣는다(게이트는 서브에이전트의 쓰기도 막으므로 규약을 알아야 한다). fork 는 부모 문맥을 물려받으므로 건너뛴다.
파일이 없거나 읽기 실패는 조용히 넘긴다(훅은 세션을 막지 않는다).
"""
import json
import os
import sys

FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "context", "ambient.md")
EVENTS = ("SessionStart", "SubagentStart")


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
    if text:
        ctx = '<plugin name="qwreey-workspace">\n' + text + "\n</plugin>"
        print(json.dumps({"hookSpecificOutput": {"hookEventName": event, "additionalContext": ctx}}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
