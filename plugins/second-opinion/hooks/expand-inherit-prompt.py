#!/usr/bin/env python3
"""expand-inherit-prompt — second-opinion:inherit-advisor 의 fork 표지를 후행 프롬프트 원문으로 펼치는 PreToolUse 훅.

메인은 짧은 표지만 보낸다:
  [second-opinion:inherit] Review only. Do not continue the work, edit files, or commit.
  next: <한 줄>
  options: reqs            (선택)
subagent_type == "fork" 이고 prompt 가 표지로 시작할 때만 prompt 를 templates/fork-prompt.md 로 바꾼다.
그 밖의 호출, 템플릿 누락·형식 오류는 그대로 통과시킨다(표지 자체가 안전한 최소 지시라 fork 가 작업을 이어 하지 않는다).
updatedInput 은 permissionDecision 과 함께 보낸다(공식 문서: 없으면 auto 모드가 바뀐 호출을 거절할 수 있다. 실측은 allow 와 함께 동작).
"""
import json
import os
import sys

TAG = "[second-opinion:inherit]"
NEXT_PLACEHOLDER = "<next step in one line>"
REQ_AFTER = "Request:"
ROOT = os.environ.get("CLAUDE_PLUGIN_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TPL_DIR = os.path.join(ROOT, "skills", "inherit-advisor", "templates")


def expand(prompt: str):
    """표지를 펼친 prompt. 바꿀 수 없으면 None."""
    if not prompt.startswith(TAG):
        return None
    nxt, opts = "", set()
    for line in prompt.splitlines()[1:]:
        key, _, val = line.partition(":")
        key = key.strip().lower()
        if key == "next" and not nxt:
            nxt = val.strip()
        elif key == "options":
            opts |= {o.strip().lower() for o in val.replace(",", " ").split()}
    if not nxt:
        return None
    try:
        with open(os.path.join(TPL_DIR, "fork-prompt.md"), encoding="utf-8") as f:
            tpl = f.read().rstrip("\n")
        reqs = ""
        if "reqs" in opts:
            with open(os.path.join(TPL_DIR, "fork-prompt-reqs.md"), encoding="utf-8") as f:
                reqs = f.read().strip()
    except OSError:
        return None
    if NEXT_PLACEHOLDER not in tpl:
        return None
    out = tpl.replace(NEXT_PLACEHOLDER, nxt)
    if reqs:
        lines = out.split("\n")
        idx = next((i for i, l in enumerate(lines) if l.startswith(REQ_AFTER)), None)
        if idx is None:
            return None
        lines.insert(idx + 1, reqs)
        out = "\n".join(lines)
    return out


def main() -> int:
    try:
        data = json.load(sys.stdin)
        ti = data.get("tool_input") or {}
        if ti.get("subagent_type") != "fork" or not isinstance(ti.get("prompt"), str):
            return 0
        new = expand(ti["prompt"])
    except Exception:
        return 0
    if new is None:
        return 0
    updated = dict(ti)
    updated["prompt"] = new
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse", "permissionDecision": "allow",
        "permissionDecisionReason": "second-opinion: inherit-advisor 표지를 후행 프롬프트로 펼침",
        "updatedInput": updated}}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
