#!/usr/bin/env python3
"""render-transcript — 세션 트랜스크립트를 '사용자 메시지, 메인 응답, 주입(서브에이전트 보고·훅), 도구 호출 요약' 텍스트로 옮긴다.

쓰는 곳: second-opinion:context 의 '다른 프레임' 경로(ask-other-frame.py 가 other-frame 에이전트 본문에 대화 사본을 줄 때).
기본 경로(Agent fork)는 이 스크립트가 필요 없다. fork 는 대화를 그대로 물려받는다.

audit/18 §11 실험에서 쓴 렌더러를 옮겼다. 그 실험에서 317k 토큰 맥락이 약 132k 토큰(270KB)으로 줄었다.
줄어든 것은 거의 도구 결과다(앞부분만 남긴다). 사용자 메시지, 메인 응답, 서브에이전트 보고는 자르지 않는다(사용자 메시지만 기본 6000자).

트랜스크립트 찾기 (user-asks.py 와 같은 규칙):
  1. --transcript PATH
  2. --session UUID 또는 환경 변수 CLAUDE_CODE_SESSION_ID → $CLAUDE_CONFIG_DIR(기본 ~/.claude)/projects/*/<UUID>.jsonl
범위: 기본은 마지막 compact 경계부터 끝까지(메인 모델이 지금 보고 있는 범위와 같다). --all 이면 처음부터.

출력: stdout. 각 블록 머리에 [L줄 종류] 를 붙여 리뷰어가 원문 위치를 댈 수 있게 한다.
사용:
  render-transcript.py [--transcript P | --session UUID] [--all | --from-line N] [--res 300] [--inp 300] [--user 6000] > /tmp/x.txt
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
from pathlib import Path


def find_transcript(a) -> Path | None:
    if a.transcript:
        return Path(a.transcript)
    sid = a.session or os.environ.get("CLAUDE_CODE_SESSION_ID")
    if not sid or not re.fullmatch(r"[0-9a-fA-F-]{8,}", sid):
        return None
    base = Path(os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude")) / "projects"
    hits = glob.glob(str(base / "*" / f"{sid}.jsonl"))
    return Path(hits[0]) if hits else None


def clip(s, n):
    s = s if isinstance(s, str) else json.dumps(s, ensure_ascii=False)
    return s if len(s) <= n else s[:n] + f" …[+{len(s) - n}자 생략]"


def strip_sr(s):
    # 긴 system-reminder(환경 안내 등)는 빼고, 짧은 것(훅 한 줄 등)은 남긴다
    return re.sub(r"<system-reminder>.*?</system-reminder>",
                  lambda m: "" if len(m.group(0)) > 400 else m.group(0), s, flags=re.S).strip()


def tinp(a, name, i):
    if name == "Bash":
        return clip(i.get("command", ""), a.inp)
    if name == "Read":
        return i.get("file_path", "") + (f" (offset {i.get('offset')})" if i.get("offset") else "")
    if name == "Write":
        return f"{i.get('file_path')} ({len(i.get('content', ''))}자)"
    if name == "Edit":
        return f"{i.get('file_path')} : {clip(i.get('old_string', ''), 80)!r} → {clip(i.get('new_string', ''), 120)!r}"
    if name == "Agent":
        return f"[{i.get('subagent_type', '')}/{i.get('model', '')}] {i.get('description', '')} :: {clip(i.get('prompt', ''), a.inp * 2)}"
    return clip(i, a.inp)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--transcript")
    ap.add_argument("--session")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--from-line", type=int, default=0)
    ap.add_argument("--res", type=int, default=300, help="도구 결과 자르기(자)")
    ap.add_argument("--inp", type=int, default=300, help="도구 입력 자르기(자)")
    ap.add_argument("--user", type=int, default=6000, help="사용자·주입 메시지 자르기(자)")
    a = ap.parse_args()
    p = find_transcript(a)
    if not p or not p.exists():
        print("render-transcript: 트랜스크립트를 찾지 못했다(--transcript 또는 --session)", file=sys.stderr)
        return 2
    lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
    start = a.from_line
    if not a.all and not start:
        for n, l in enumerate(lines, 1):
            if '"compact_boundary"' in l:
                start = n
    out = []
    for n, l in enumerate(lines, 1):
        if n < start:
            continue
        try:
            d = json.loads(l)
        except ValueError:
            continue
        t = d.get("type")
        if t == "system" and d.get("subtype") == "compact_boundary":
            out.append(f"\n=== (L{n}) 여기서 compact 됨. 아래 첫 사용자 메시지는 compact 요약이다 ===\n")
            continue
        if t not in ("user", "assistant") or d.get("isSidechain"):
            continue
        c = d["message"]["content"]
        if isinstance(c, str):
            c = [{"type": "text", "text": c}]
        for b in c:
            bt = b.get("type")
            if t == "user" and bt == "text":
                s = strip_sr(b["text"])
                if not s:
                    continue
                lim = 60000 if d.get("isCompactSummary") else a.user
                tag = "사용자(compact 요약)" if d.get("isCompactSummary") else ("주입" if d.get("isMeta") else "사용자")
                out.append(f"\n[L{n} {tag}]\n{clip(s, lim)}")
            elif t == "user" and bt == "tool_result":
                cc = b.get("content")
                if isinstance(cc, list):
                    cc = "\n".join(x.get("text", "") for x in cc if isinstance(x, dict))
                out.append(f"  ← {'오류 ' if b.get('is_error') else ''}결과: {clip(strip_sr(cc or ''), a.res)}")
            elif t == "assistant" and bt == "text":
                out.append(f"\n[L{n} 메인]\n{b['text'].strip()}")
            elif t == "assistant" and bt == "tool_use":
                out.append(f"  → {b['name']}: {tinp(a, b['name'], b.get('input') or {})}")
            elif t == "assistant" and bt == "server_tool_use":
                out.append(f"  → (서버 도구) {b.get('name')}")
    print("\n".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
