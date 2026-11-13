#!/usr/bin/env python3
"""qwreey-operator 규약 주입. SessionStart(startup·resume·clear·compact)에서 context/ambient.md 를 additionalContext 로 낸다.

플러그인이 켜져 있을 때만 위임 규약이 실리게 하려는 것이다. SessionStart 는 메인 세션에만 불리므로 서브에이전트에는 안 실린다.
파일이 없거나 읽기 실패는 조용히 넘긴다(훅은 세션을 막지 않는다).
"""
import json
import os
import sys

FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "context", "ambient.md")


def main():
    try:
        with open(FILE, encoding="utf-8") as f:
            text = f.read().strip()
    except OSError:
        return 0
    if text:
        ctx = '<plugin name="qwreey-operator">\n' + text + "\n</plugin>"
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": ctx}}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
