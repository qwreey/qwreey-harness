"""주입 문자열 만들기: SessionStart 인계, PreCompact 상기, pending 알림, 요약 완료 알림.

주입 경로 안전(HOOK-MESSAGES 규약, 2026-11-10): SessionStart·UserPromptSubmit 출력은 user turn 에 그대로 들어간다.
그래서 구조화된 항목만 넣는다 — 개수, 경로, 미완료 항목 제목(⚠ 없는 것), 원문 대조를 통과한 사용자 인용.
자유 텍스트 요약 본문(### 요약)은 넣지 않고 경로만 준다. `<…>` 는 무력화한다.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path

from . import config, extract as ex, messages
from .paths import short_home
from .store import Store, escape_tags, parse_sections

WARN = "⚠"
CITE_TAIL_RX = re.compile(r"\s*\((?:L\d+[^)]*)\)\s*$")


def _item_title(item: str, n: int = 110) -> str:
    s = item[2:] if item.startswith("- ") else item
    m = CITE_TAIL_RX.search(s)
    cite = m.group(0).strip() if m else ""
    s = CITE_TAIL_RX.sub("", s).strip()
    s = escape_tags(" ".join(s.split()))
    if len(s) > n:
        s = s[: n - 1] + "…"
    return f"- {s}" + (f" {cite}" if cite else "")


def _clean(items: list[str]) -> list[str]:
    return [i for i in items if i.startswith("- ") and i.strip() != "- 없음" and WARN not in i]


def fit(head: str, items: list[str], limit: int, tail: list[str] = ()) -> str:
    """머리 + 항목들을 limit 자 안에. 넘치면 항목 단위로 자르고 '(+N more)'."""
    lines = [head]
    used = len(head) + 1 + sum(len(t) + 1 for t in tail)
    for i, it in enumerate(items):
        rest = len(items) - i
        reserve = len(messages.more(rest)) + 1 if rest > 1 else 0
        if used + len(it) + 1 + reserve > limit:
            lines.append(messages.more(rest))
            break
        lines.append(it); used += len(it) + 1
    return "\n".join(lines + list(tail))


def record_sections(store: Store, sid: str) -> tuple[list[dict], Path | None]:
    rids = sorted(r for r, e in store.index().items() if e.get("session_id") == sid)
    secs: list[dict] = []
    last = None
    for rid in rids:
        p = store.record_path(rid)
        try:
            secs += parse_sections(p.read_text(encoding="utf-8"))
            last = p
        except OSError:
            pass
    return secs, last


def latest_other_session(store: Store, sid: str) -> str | None:
    best = None
    for rid, e in store.index().items():
        if e.get("session_id") == sid:
            continue
        if best is None or e.get("updated", "") > best[0]:
            best = (e.get("updated", ""), e.get("session_id"))
    return best[1] if best else None


# ---- SessionStart ----
def handover(store: Store, sid: str, source: str) -> str:
    limit = int(config.num("SESSION_LOG_HANDOVER_CHARS"))
    target = sid if source == "resume" else latest_other_session(store, sid)
    if not target:
        return ""
    secs, path = record_sections(store, target)
    if not secs:
        return ""
    last = secs[-1]
    try:
        age = (datetime.now().date() - datetime.fromisoformat(last["head"][:10]).date()).days
    except ValueError:
        age = 0
    if age > config.num("SESSION_LOG_HANDOVER_MAX_DAYS"):
        return ""
    items = [_item_title(i) for i in _clean(last["parts"].get("미해결과 다음 단계", []))]
    if not items:
        return ""
    when = last["head"].split(" · ")[0]
    head = messages.handover_head(target[:8], when, target == sid)
    tail = [f"Record: {short_home(path)}"] if path else []
    return fit(head, items, limit, tail)


def pending_line(store: Store, trigger: str) -> tuple[str, str]:
    """(level, text). 임계를 넘으면 action, 아니면 warn."""
    count, oldest, days = store.pending_summary()
    if not count:
        return "warn", ""
    strong = count >= config.num("SESSION_LOG_PENDING_STRONG_COUNT") or days >= config.num("SESSION_LOG_PENDING_STRONG_DAYS")
    return ("action" if strong else "warn"), messages.pending(count, oldest, days, trigger, strong)


# ---- 요약 완료 알림 ----
def saved_line(store: Store, notices: list[dict]) -> str:
    if not notices:
        return ""
    n = sum(x.get("sections", 0) for x in notices)
    rids = list(dict.fromkeys(r for x in notices for r in x.get("rids", [])))
    files = [short_home(store.record_path(r)) for r in rids]
    flagged = sum(x.get("flagged", 0) for x in notices)
    return messages.saved(n, files, len(store.pending()), flagged)


# ---- PreCompact ----
QUOTE_RX = re.compile(r"\"([^\"]{4,})\"|“([^”]{4,})”")


def precompact(store: Store, sid: str, transcript: str) -> str:
    limit = int(config.num("SESSION_LOG_PRECOMPACT_CHARS"))
    secs, path = record_sections(store, sid)
    lines = [messages.PRECOMPACT_HEAD]
    directives, decisions, done, open_ = [], [], [], []
    for s in secs:
        directives += _clean(s["parts"].get("사용자 지시와 정정", []))
        decisions += _clean(s["parts"].get("결정", []))
    if secs:
        done = _clean(secs[-1]["parts"].get("바뀐 파일과 커밋", []))
        open_ = _clean(secs[-1]["parts"].get("미해결과 다음 단계", []))
    # 사용자 지시: 대조를 통과한 인용 줄(⚠ 없음)만. 최근 것 우선.
    recent_user = _unsummarized_user(store, sid, transcript)
    blocks = [
        (messages.PRECOMPACT_DIRECTIVES, [_item_title(i, 200) for i in directives[::-1]], 0.35),
        (messages.PRECOMPACT_RECENT_USER, recent_user, 0.25),
        (messages.PRECOMPACT_DECISIONS, [_item_title(i) for i in decisions[::-1]], 0.15),
        (messages.PRECOMPACT_OPEN, [_item_title(i) for i in open_], 0.15),
        (messages.PRECOMPACT_DONE, [_item_title(i, 90) for i in done], 0.10),
    ]
    tail = messages.precompact_record(short_home(path) if path else None, short_home(store.records))
    budget = limit - len(lines[0]) - len(tail) - 4
    for title, items, share in blocks:
        if not items:
            continue
        lines.append(fit(title, items, int(budget * share)))
    lines.append(tail)
    return "\n".join(lines)


def _unsummarized_user(store: Store, sid: str, transcript: str, max_items: int = 12) -> list[str]:
    """요약이 아직 덮지 않은 구간의 사용자 발언 원문. 기록이 없으면 꼬리 8MB 의 마지막 compact 이후."""
    st = store.wstate(sid)
    try:
        size = os.path.getsize(transcript)
    except OSError:
        return []
    off = st.get("offset", 0)
    line = st.get("line")
    if size - off > 8 * 1024 * 1024:
        off, line = size - 8 * 1024 * 1024, None
        # 줄 경계로 맞추고 줄 번호는 모르므로 L 없이 쓴다
    try:
        e = ex.extract(transcript, off, line if line is not None else 0)
    except OSError:
        return []
    human = []
    for x in e.entries:
        if "--- compact(" in x.text:
            human = []  # 마지막 compact 이후만
            continue
        if x.human and x.human_text.strip():
            t = escape_tags(" ".join(x.human_text.split()))
            t = t if len(t) <= 300 else t[:299] + "…"
            human.append(f'- "{t}"' + (f" (L{x.line})" if line is not None else ""))
    return human[-max_items:]
