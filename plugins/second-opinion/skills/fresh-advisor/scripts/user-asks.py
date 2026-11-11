#!/usr/bin/env python3
"""user-asks — 메인 세션 트랜스크립트에서 '사용자가 실제로 요구한 것'만 뽑아 리뷰어에게 준다. 읽기 전용, 표준 라이브러리만.

왜: 리뷰어(새 컨텍스트 서브에이전트)는 메인의 요약에 기대면 메인 관점에 끌려간다. 사용자 원문은 리뷰어가 직접 본다.
    메인이 넘기는 것은 목표·제약 몇 줄과 '검증할 주장'뿐이다(skills/fresh-advisor/SKILL.md).

트랜스크립트 찾기 (순서):
  1. --transcript PATH
  2. --session UUID 또는 환경 변수 CLAUDE_CODE_SESSION_ID
     서브에이전트의 Bash 에도 부모 세션의 CLAUDE_CODE_SESSION_ID 가 들어 있다(문서에 없는 동작이므로 없으면 --transcript 를 쓴다).
     → $CLAUDE_CONFIG_DIR(기본 ~/.claude)/projects/*/<UUID>.jsonl

무엇을 '사용자 발언'으로 치나 (plugins/q/scripts/sllib/extract.py classify 와 같은 기준을 옮김):
  - type=user, content 가 문자열, origin.kind 가 human 이거나 없음, isMeta/isCompactSummary 아님,
    '<command-…>', '<local-command…>', '<system-reminder>', '<task-notification>' 로 시작하지 않음
  - attachment.type=queued_command 이고 origin.kind=human  (작업 중에 끼워 넣은 지시. compact 에서 잘 사라진다)
  - AskUserQuestion 의 답(tool_result)
  - 제외: origin.kind=peer(서브에이전트 보고, 다른 세션 메시지), tool_result, compact 요약, 슬래시 명령 출력
  - 슬래시 명령은 '/이름 인자' 한 줄로만 남긴다(사용자 의도 신호라서)

출력: 마크다운. 각 항목 머리에 [L줄 MM-DD HH:MM] 를 붙여 리뷰어가 원문을 다시 찾을 수 있게 한다.
옵션:
  --since-compact   마지막 compact 경계 뒤만(기본: 전체. 전체가 기본인 이유: compact 전 지시가 가장 잘 잊힌다)
  --last N          마지막 N 개만
  --claims K        메인이 사용자에게 보낸 마지막 K 개 응답 텍스트를 '검증할 주장' 절로 따로 붙인다(근거가 아님을 표시)
  --max-chars C     항목당 자르기(기본 2000)
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
from pathlib import Path

REMINDERISH = ("<system-reminder>", "<local-command", "<task-notification>", "Caveat:", "<agent-message")


def find_transcript(args) -> Path | None:
    if args.transcript:
        return Path(args.transcript)
    sid = args.session or os.environ.get("CLAUDE_CODE_SESSION_ID")
    if not sid or not re.fullmatch(r"[0-9a-fA-F-]{8,}", sid):
        return None
    base = Path(os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude")) / "projects"
    hits = glob.glob(str(base / "*" / f"{sid}.jsonl"))
    return Path(hits[0]) if hits else None


def ts(o: dict) -> str:
    t = o.get("timestamp") or ""
    return f"{t[5:10]} {t[11:16]}" if len(t) >= 16 else ""


def clip(s: str, n: int) -> str:
    s = s.strip()
    return s if len(s) <= n else s[:n] + f" …(+{len(s) - n}자)"


def slash(c: str) -> str | None:
    m = re.search(r"<command-name>([^<]+)</command-name>", c)
    if not m:
        return None
    a = re.search(r"<command-args>([\s\S]*?)</command-args>", c)
    return f"{m.group(1).strip()} {a.group(1).strip() if a else ''}".strip()


def main() -> int:
    ap = argparse.ArgumentParser(description="세션 트랜스크립트에서 사용자 요구만 추출")
    ap.add_argument("--transcript")
    ap.add_argument("--session")
    ap.add_argument("--since-compact", action="store_true")
    ap.add_argument("--last", type=int, default=0)
    ap.add_argument("--claims", type=int, default=0)
    ap.add_argument("--max-chars", type=int, default=2000)
    args = ap.parse_args()
    path = find_transcript(args)
    if not path or not path.is_file():
        print("트랜스크립트를 찾지 못했다. --transcript 나 --session 을 준다(CLAUDE_CODE_SESSION_ID 없음).", file=sys.stderr)
        return 2

    asks: list[str] = []
    claims: list[str] = []
    ask_tool_ids: set[str] = set()
    with open(path, encoding="utf-8", errors="replace") as g:
        for ln, line in enumerate(g, 1):
            try:
                o = json.loads(line)
            except ValueError:
                continue
            t = o.get("type")
            if t == "system" and o.get("subtype") == "compact_boundary" and args.since_compact:
                asks.clear(); claims.clear()
                continue
            if t == "attachment":
                a = o.get("attachment") or {}
                og = a.get("origin") or {}
                if a.get("type") == "queued_command" and isinstance(og, dict) and og.get("kind") == "human" \
                        and isinstance(a.get("prompt"), str):
                    asks.append(f"- [L{ln} {ts(o)} 작업 중 추가] {clip(a['prompt'], args.max_chars)}")
                continue
            if t == "assistant" and not o.get("isSidechain"):
                content = (o.get("message") or {}).get("content")
                if isinstance(content, list):
                    for b in content:
                        if isinstance(b, dict) and b.get("type") == "tool_use" and b.get("name") == "AskUserQuestion":
                            ask_tool_ids.add(b.get("id"))
                        elif isinstance(b, dict) and b.get("type") == "text" and b.get("text", "").strip() and args.claims:
                            claims.append(f"- [L{ln} {ts(o)}] {clip(b['text'], args.max_chars)}")
                continue
            if t != "user" or o.get("isSidechain") or o.get("isCompactSummary"):
                continue
            og = o.get("origin") or {}
            kind = og.get("kind") if isinstance(og, dict) else None
            c = (o.get("message") or {}).get("content")
            if isinstance(c, str):
                cmd = slash(c)
                if cmd:
                    asks.append(f"- [L{ln} {ts(o)} 명령] `{clip(cmd, 300)}`")
                    continue
                if o.get("isMeta") or kind not in (None, "human") or c.lstrip().startswith(REMINDERISH) \
                        or c.startswith("This session is being continued"):
                    continue
                asks.append(f"- [L{ln} {ts(o)}] {clip(c, args.max_chars)}")
            elif isinstance(c, list):
                for b in c:
                    if not isinstance(b, dict):
                        continue
                    if b.get("type") == "tool_result" and b.get("tool_use_id") in ask_tool_ids:
                        body = b.get("content")
                        if isinstance(body, list):
                            body = " ".join(x.get("text", "") for x in body if isinstance(x, dict))
                        asks.append(f"- [L{ln} {ts(o)} 질문에 대한 답] {clip(str(body), args.max_chars)}")
                    elif b.get("type") == "text" and kind in (None, "human") and not o.get("isMeta") \
                            and not b.get("text", "").lstrip().startswith(REMINDERISH):
                        asks.append(f"- [L{ln} {ts(o)}] {clip(b['text'], args.max_chars)}")

    if args.last:
        asks = asks[-args.last:]
    print(f"# 사용자 요구 원문 ({path.name}, {len(asks)}개)\n")
    print("아래는 사용자가 직접 쓴 말이다. 메인의 해석이 아니라 이것을 기준으로 대조한다. 오래된 지시가 나중 지시로 뒤집혔을 수 있으니 시간순으로 읽는다.\n")
    print("\n".join(asks) if asks else "(없음)")
    if args.claims:
        print(f"\n# 메인이 사용자에게 한 말 (마지막 {args.claims}개) — 검증할 주장이지 근거가 아니다\n")
        print("\n".join(claims[-args.claims:]) if claims else "(없음)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
