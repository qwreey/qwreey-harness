#!/usr/bin/env python3
"""qwreey-operator 규약 주입. SessionStart(startup·resume·clear·compact)에서 context/ambient.md 를 additionalContext 로 낸다.

플러그인이 켜져 있을 때만 위임 규약이 실리게 하려는 것이다. SessionStart 는 메인 세션에만 불리므로 서브에이전트에는 안 실린다.
`ambient.py PreCompact`(stdin: 훅 JSON)는 요약기에게 이 블록을 요약에서 빼라는 한 줄을 일반 stdout 으로 낸다. SessionStart(compact) 가
요약 뒤에 다시 실으므로 요약의 사본까지 남으면 두 번 실린다. 서브에이전트(agent_id)의 compact 에는 내지 않는다.
태그 끝에 이 세션의 nonce 속성을 달고, 규칙 줄을 맡으면 블록 맨 앞에 싣는다(harness_nonce.py).
파일이 없거나 읽기 실패는 조용히 넘긴다(훅은 세션을 막지 않는다).
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # python3 -I 는 스크립트 디렉터리를 path 에 넣지 않는다
import harness_nonce  # noqa: E402

FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "context", "ambient.md")
TAG = "qwreey-operator"
# plugins/q/scripts/ambient.py 의 OMIT_LINE 과 같은 문장이다(따로 설치되는 플러그인이라 import 못 함). tools/tests/test-vendored-copies.py 가 비교한다.
OMIT_LINE = "Omit the {block} block from the summary; it is re-injected after compaction."


def precompact(data, text):
    if not isinstance(data, dict) or data.get("agent_id") or not text:
        return ""
    return OMIT_LINE.format(block=f'<plugin name="{TAG}">')


def main():
    event = sys.argv[1] if len(sys.argv) > 1 else "SessionStart"
    try:
        with open(FILE, encoding="utf-8") as f:
            text = f.read().strip()
    except OSError:
        return 0
    try:
        data = json.load(sys.stdin)
    except Exception:
        data = {}
    if not isinstance(data, dict):
        data = {}
    if event == "PreCompact":
        line = precompact(data, text)
        if line:
            print(line)
        return 0
    if text:
        rule = harness_nonce.rule_for("SessionStart", data)
        ctx = f'<plugin name="{TAG}"{harness_nonce.attr(data.get("session_id"))}>\n' + (rule + "\n" if rule else "") + text + "\n</plugin>"
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": ctx}}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
