#!/usr/bin/env python3
"""세션 기록의 숫자·인용·커밋 해시를 원문 트랜스크립트와 기계적으로 대조한다. (프로토타입)

사용: python3 -I verify.py <summary.md> <transcript.jsonl> [--show]

항목(목록 줄 `- …`)마다:
- 인용 "…"(사용자 지시 절): 인용한 줄(Lnnn)의 원문에 글자 그대로 있어야 한다. 없으면 QUOTE_BAD.
- 숫자·해시: 인용한 줄들의 원문에 있어야 한다.
  - 인용한 줄엔 없고 다른 줄에 있으면 CITE_OFF(근거 줄을 잘못 짚음, 내용은 원문에 있음)
  - 원문 어디에도 없으면 NUM_MISSING(지어냈거나 계산·환산한 값 → 사람이 봐야 함)
- 줄 번호가 트랜스크립트 범위를 벗어나면 CITE_BAD.
원문 = JSONL 각 줄의 본문(message.content, attachment.prompt, content)의 모든 문자열(잘라 낸 extract 가 아니라 전체).
"""
from __future__ import annotations

import json
import re
import sys

def strings(o, acc):
    if isinstance(o, str):
        acc.append(o)
    elif isinstance(o, dict):
        for v in o.values():
            strings(v, acc)
    elif isinstance(o, list):
        for v in o:
            strings(v, acc)
    return acc

def norm(s: str) -> str:
    return " ".join(s.replace(" ", " ").split())

def load(path):
    lines = {}
    with open(path, encoding="utf-8", errors="replace") as f:
        for i, raw in enumerate(f, 1):
            try:
                o = json.loads(raw)
                # 메타데이터(id·서명·타임스탬프)의 숫자가 우연히 맞는 것을 막으려고 본문만 본다.
                body = [(o.get("message") or {}).get("content"), (o.get("attachment") or {}).get("prompt"), o.get("content")]
                lines[i] = norm("\n".join(strings(body, [])))
            except Exception:
                lines[i] = norm(raw)
    return lines

NUM_RX = re.compile(r"(?<![\w.\-])(\d[\d,]*(?:\.\d+)?)(?![\d.,]?\d)(?![A-Za-z_]*\d)")
HASH_RX = re.compile(r"`([0-9a-f]{7,40})`")
CITE_RX = re.compile(r"L(\d+)")
QUOTE_RX = re.compile(r"\"([^\"]{4,})\"|“([^”]{4,})”")

def numbers(text: str):
    t = CITE_RX.sub(" ", text)
    t = re.sub(r"\(L[\d, L]+\)", " ", t)
    out = []
    for m in NUM_RX.finditer(t):
        v = m.group(1).replace(",", "")
        if len(v) == 1 and v in "0123456789":
            continue  # 한 자리 숫자는 잡음(목록 번호, "둘" 류)이 많아 뺀다
        out.append(v)
    out += HASH_RX.findall(text)
    return out

def contains(hay: str, needle: str) -> bool:
    if needle in hay:
        return True
    if needle.replace(",", "") in hay.replace(",", ""):
        return True
    return False

def main():
    summ, tr = sys.argv[1], sys.argv[2]
    show = "--show" in sys.argv
    src = load(tr)
    whole = "\n".join(src.values())
    issues = []
    n_items = n_nums = n_quotes = 0
    section = ""
    for ln in open(summ, encoding="utf-8"):
        ln = ln.rstrip("\n")
        if ln.startswith("### "):
            section = ln[4:]
        if not ln.startswith("- ") or ln.strip() == "- 없음":
            continue
        n_items += 1
        cites = [int(x) for x in CITE_RX.findall(ln)]
        bad = [c for c in cites if c not in src]
        if bad:
            issues.append(("CITE_BAD", section, ln, bad))
        cited = " ".join(src.get(c, "") for c in cites)
        # 인용
        if section.startswith("사용자 지시"):
            for m in QUOTE_RX.finditer(ln):
                q = norm(m.group(1) or m.group(2)).rstrip("…").strip()
                n_quotes += 1
                if not contains(cited, q):
                    kind = "QUOTE_CITE_OFF" if contains(whole, q) else "QUOTE_BAD"
                    issues.append((kind, section, ln, q))
        # 숫자·해시
        body = QUOTE_RX.sub(" ", ln) if section.startswith("사용자 지시") else ln
        for v in numbers(body):
            n_nums += 1
            if contains(cited, v):
                continue
            issues.append(("CITE_OFF" if contains(whole, v) else "NUM_MISSING", section, ln, v))
    kinds = {}
    for k, *_ in issues:
        kinds[k] = kinds.get(k, 0) + 1
    print(json.dumps({"file": summ.rsplit("/", 1)[-1], "items": n_items, "numbers": n_nums, "quotes": n_quotes, "issues": kinds}, ensure_ascii=False))
    if show:
        for k, sec, ln, v in issues:
            print(f"  {k:14} [{sec}] {v!s:20} | {ln[:200]}")

if __name__ == "__main__":
    main()
