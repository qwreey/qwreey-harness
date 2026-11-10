"""요약 항목의 숫자·커밋 해시·사용자 인용을 원문 트랜스크립트 줄과 기계로 대조한다.

원문 = 그 구간(줄 범위)에 있는 JSONL 줄의 본문(message.content, attachment.prompt, content)의 모든 문자열.
메타데이터(id·서명·timestamp)의 숫자가 우연히 맞는 것을 막으려고 본문만 본다. 파일 전체를 메모리에 올리지 않는다.

판정(목록 줄 `- …` 마다)
- QUOTE_BAD    사용자 지시 절의 인용이 구간 원문 어디에도 없다 → 항목을 뺀다(dropped).
- QUOTE_OFF    인용은 구간에 있지만 짚은 줄에는 없다 → `⚠근거 줄 다름`
- NUM_MISSING  숫자·해시가 구간 원문 어디에도 없다 → `⚠원문 불일치`
- CITE_OFF     숫자·해시가 짚은 줄엔 없고 구간의 다른 줄에 있다 → `⚠근거 줄 다름`
- CITE_BAD     근거 줄 번호가 구간 밖이다 → `⚠근거 줄 없음`
"""
from __future__ import annotations

import json
import re

MARK_MISMATCH = "⚠원문 불일치"
MARK_CITE_OFF = "⚠근거 줄 다름"
MARK_CITE_BAD = "⚠근거 줄 없음"


def _strings(o, acc):
    if isinstance(o, str):
        acc.append(o)
    elif isinstance(o, dict):
        for v in o.values():
            _strings(v, acc)
    elif isinstance(o, list):
        for v in o:
            _strings(v, acc)
    return acc


def norm(s: str) -> str:
    return " ".join(s.replace(" ", " ").split())


def body_of(raw: bytes) -> str:
    try:
        o = json.loads(raw)
        if not isinstance(o, dict):
            return norm(raw.decode("utf-8", "replace"))
        body = [(o.get("message") or {}).get("content"), (o.get("attachment") or {}).get("prompt"), o.get("content")]
        return norm("\n".join(_strings(body, [])))
    except ValueError:
        return norm(raw.decode("utf-8", "replace"))


def load_range(path: str, start_byte: int, end_byte: int, start_line: int) -> dict[int, str]:
    """[start_byte, end_byte) 의 줄 → {줄 번호: 본문}. start_line 은 start_byte 앞의 줄 수."""
    out: dict[int, str] = {}
    with open(path, "rb") as f:
        f.seek(start_byte)
        pos, n = start_byte, start_line
        for raw in f:
            if pos >= end_byte:
                break
            n += 1
            pos += len(raw)
            out[n] = body_of(raw)
    return out


NUM_RX = re.compile(r"(?<![\w.\-])(\d[\d,]*(?:\.\d+)?)(?![\d.,]?\d)(?![A-Za-z_]*\d)")
HASH_RX = re.compile(r"`([0-9a-f]{7,40})`")
CITE_RX = re.compile(r"\bL(\d+)\b")
CITE_GROUP_RX = re.compile(r"\((?:L\d+[–\-~]?(?:L?\d+)?(?:,\s*)?)+\)")
QUOTE_RX = re.compile(r"\"([^\"]{4,})\"|“([^”]{4,})”")


def numbers(text: str) -> list[str]:
    t = CITE_GROUP_RX.sub(" ", text)
    t = CITE_RX.sub(" ", t)
    out = []
    for m in NUM_RX.finditer(t):
        v = m.group(1).replace(",", "")
        if len(v) == 1:
            continue  # 한 자리 숫자는 잡음(목록 번호 등)이 많다
        out.append(v)
    out += HASH_RX.findall(text)
    return out


def contains(hay: str, needle: str) -> bool:
    return needle in hay or needle.replace(",", "") in hay.replace(",", "")


def check_section(text: str, src: dict[int, str]) -> tuple[str, dict]:
    """요약 본문(### 절들)을 대조해 표시를 달고 뺄 항목을 뺀다. (새 본문, 개수)."""
    whole = "\n".join(src.values())
    counts = {"items": 0, "numbers": 0, "quotes": 0, "num_missing": 0, "quote_bad": 0, "cite_off": 0, "cite_bad": 0, "dropped": 0}
    out, section = [], ""
    for ln in text.split("\n"):
        if ln.startswith("### "):
            section = ln[4:].strip()
        if not ln.startswith("- ") or ln.strip() == "- 없음":
            out.append(ln)
            continue
        counts["items"] += 1
        cites = [int(x) for x in CITE_RX.findall(ln)]
        marks: list[str] = []
        if any(c not in src for c in cites):
            counts["cite_bad"] += 1
            marks.append(MARK_CITE_BAD)
        cited = " ".join(src.get(c, "") for c in cites)
        drop = False
        is_directive = section.startswith("사용자 지시")
        if is_directive:
            for m in QUOTE_RX.finditer(ln):
                q = norm(m.group(1) or m.group(2)).rstrip("…").rstrip(".").strip()
                if not q:
                    continue
                counts["quotes"] += 1
                if contains(cited, q):
                    continue
                if contains(whole, q):
                    counts["cite_off"] += 1
                    marks.append(MARK_CITE_OFF)
                else:
                    counts["quote_bad"] += 1
                    drop = True
        body = QUOTE_RX.sub(" ", ln) if is_directive else ln
        for v in numbers(body):
            counts["numbers"] += 1
            if contains(cited, v):
                continue
            if contains(whole, v):
                counts["cite_off"] += 1
                marks.append(MARK_CITE_OFF)
            else:
                counts["num_missing"] += 1
                marks.append(MARK_MISMATCH)
        if drop:
            counts["dropped"] += 1
            continue
        if marks:
            ln = ln.rstrip() + " " + " ".join(dict.fromkeys(marks))
        out.append(ln)
    # 항목을 모두 뺀 절에는 "- 없음" 을 남긴다
    fixed, i = [], 0
    while i < len(out):
        fixed.append(out[i])
        if out[i].startswith("### "):
            j = i + 1
            while j < len(out) and not out[j].startswith("### ") and not out[j].strip():
                j += 1
            if j >= len(out) or out[j].startswith("### "):
                fixed.append("- 없음")
        i += 1
    return "\n".join(fixed), counts


def flagged(counts: dict) -> int:
    return counts.get("num_missing", 0) + counts.get("quote_bad", 0) + counts.get("cite_bad", 0)
