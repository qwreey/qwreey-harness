"""flush: 지난 오프셋부터 트랜스크립트를 줄여 구간마다 요약하고, 대조하고, 외부 저장소 기록에 절로 덧붙인다.

훅이 분리 프로세스로 부르는 길과 backfill 이 같은 함수를 쓴다(같은 이름 규칙, 같은 상태 파일).
"""
from __future__ import annotations

import contextlib
import os
import time
from datetime import datetime
from pathlib import Path

from . import config, extract as ex, messages, summarize, verify
from .store import Store, flocked


def _local(ts: str) -> datetime | None:
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone()
    except (ValueError, AttributeError):
        return None


def section_head(entries: list[ex.Entry], trigger: str) -> str:
    a, b = _local(entries[0].ts), _local(entries[-1].ts)
    if a and b:
        when = f"{a:%Y-%m-%d %H:%M}–{b:%H:%M}" if a.date() == b.date() else f"{a:%Y-%m-%d %H:%M} – {b:%Y-%m-%d %H:%M}"
    else:
        when = datetime.now().strftime("%Y-%m-%d %H:%M")
    return f"## {when} · {trigger}"


@contextlib.contextmanager
def machine_slot(wait_s: float):
    """기계 전체 동시 요약 상한(SESSION_LOG_MAX_PARALLEL). 못 잡으면 기다린다."""
    n = max(1, int(config.num("SESSION_LOG_MAX_PARALLEL")))
    base = Path(os.environ.get("XDG_RUNTIME_DIR") or "/tmp") / f"session-log-{os.getuid()}"
    deadline = time.time() + wait_s
    while True:
        for i in range(n):
            cm = flocked(base / f"slot-{i}.lock", blocking=False)
            got = cm.__enter__()
            if got:
                try:
                    yield True
                finally:
                    cm.__exit__(None, None, None)
                return
            cm.__exit__(None, None, None)
        if time.time() >= deadline:
            yield False
            return
        time.sleep(2)


def flush(store: Store, sid: str, transcript: str, trigger: str, force: bool = False, model: str | None = None,
          budget_left: float | None = None, until_byte: int | None = None, start_at: tuple[int, int] | None = None,
          notify: bool = True, max_rounds: int = 4) -> dict:
    """결과: {sections, rids, cost_usd, flagged, error?, locked?, budget_stop?}"""
    model = model or config.get("SESSION_LOG_MODEL")
    res = {"sections": 0, "rids": [], "cost_usd": 0.0, "flagged": 0, "calls": 0, "chars": 0, "wall_s": 0.0}
    if not os.path.isfile(transcript):
        return dict(res, error="transcript missing")
    store.ensure()
    pend = store.state / f"{sid}.pending"
    with flocked(store.state / f"{sid}.lock", blocking=False) as got:
        if not got:
            pend.touch()
            return dict(res, locked=True)
        with machine_slot(1800) as slot:
            if not slot:
                pend.touch()
                return dict(res, error="no slot")
            for _ in range(max_rounds):
                with contextlib.suppress(FileNotFoundError):
                    pend.unlink()
                r = _one_round(store, sid, transcript, trigger, force, model, budget_left, until_byte, start_at, res)
                start_at = None
                if r or not pend.exists():
                    break
    if notify and res["sections"]:
        store.push_notice({"kind": "saved", "session_id": sid, "rids": res["rids"], "sections": res["sections"],
                           "flagged": res["flagged"], "trigger": trigger})
    return res


def _one_round(store, sid, transcript, trigger, force, model, budget_left, until_byte, start_at, res) -> bool:
    """한 번 돈다. 더 돌 필요가 없으면(실패·예산) True."""
    st = store.wstate(sid)
    st.setdefault("session_id", sid)
    st["transcript"] = transcript
    if not st.get("started"):
        st["started"] = (_local(ex.first_timestamp(transcript)) or datetime.now()).isoformat()
    if start_at and start_at[0] > st.get("offset", 0):
        st["offset"], st["line"] = start_at
    offset, line = st.get("offset", 0), st.get("line", 0)
    try:
        if os.path.getsize(transcript) < offset:  # 트랜스크립트가 바뀌었다(드묾) → 처음부터
            offset, line = 0, 0
    except OSError:
        return True
    e = ex.extract(transcript, offset, line, to_byte=until_byte)
    min_chars = config.num("SESSION_LOG_FORCE_MIN_CHARS" if force else "SESSION_LOG_MIN_CHARS")
    if not e.entries:
        st["offset"], st["line"] = e.end_byte, e.end_line
        st["last_run"] = time.time()
        store.save_wstate(sid, st)
        return True
    if e.chars < min_chars:
        st["last_run"] = time.time()
        store.save_wstate(sid, st)
        return True
    limit = int(config.num("SESSION_LOG_CHUNK_CHARS"))
    timeout = config.num("SESSION_LOG_CALL_TIMEOUT")
    template = messages.SUMMARY_PROMPT
    chunk_start, chunk_line = offset, line
    for ch in ex.chunks(e.entries, limit):
        text = "\n".join(x.text for x in ch)
        if budget_left is not None and res["cost_usd"] + summarize.estimate_cost(len(text), model) > budget_left:
            res["budget_stop"] = True
            store.save_wstate(sid, st)
            return True
        r = summarize.call_model(template.replace("{{TRANSCRIPT}}", text), model, timeout)
        res["calls"] += 1
        res["cost_usd"] += r.get("cost_usd") or 0.0
        res["wall_s"] += r.get("wall_s") or 0.0
        res["chars"] += len(text)
        st["cost_usd"] = round(st.get("cost_usd", 0.0) + (r.get("cost_usd") or 0.0), 5)
        out = r.get("result", "") if r.get("ok") else ""
        n = st.get("sections", 0) + 1
        head = section_head(ch, trigger)
        rng = f"L{ch[0].line}–L{ch[-1].end_line}"
        if not summarize.valid(out):
            st["failures"] = st.get("failures", 0) + 1 if st.get("fail_offset") == chunk_start else 1
            st["fail_offset"] = chunk_start
            store.log_error(f"{sid[:8]} {rng} summarize failed ({st['failures']}): {r.get('error') or 'format/echo check'}")
            if st["failures"] < 3:
                st["last_run"] = time.time()
                store.save_wstate(sid, st)
                res["error"] = r.get("error") or "format"
                return True
            humans = sum(1 for x in ch if x.human)
            section = f"{head}\nid: {sid[:8]}-{n} · note: {rng}\n요약 실패 — 원문 {rng}, 사람 발언 {humans}개. 트랜스크립트에서 직접 확인한다.\n"
            desc, kws, counts = "", [], {}
        else:
            desc, kws, body = summarize.parse(out)
            src = verify.load_range(transcript, chunk_start, ch[-1].end_byte, chunk_line)
            body, counts = verify.check_section(body, src)
            res["flagged"] += verify.flagged(counts)  # quote_bad 는 뺀 항목(dropped)과 같은 것
            summ = desc.replace(" · ", ", ")
            section = f"{head}\nid: {sid[:8]}-{n} · summary: {summ} · note: {rng}\n\n{body}\n"
        rid = store.append_section(sid, st, section, desc, kws, counts, model, transcript)
        st["sections"] = n
        st["failures"], st["fail_offset"] = 0, None
        chunk_start, chunk_line = ch[-1].end_byte, ch[-1].end_line
        st["offset"], st["line"], st["rid"] = chunk_start, chunk_line, rid
        st["last_run"] = time.time()
        store.save_wstate(sid, st)
        res["sections"] += 1
        if rid not in res["rids"]:
            res["rids"].append(rid)
    # 마지막 항목 뒤의 버린 줄까지 오프셋을 옮긴다
    if e.end_byte > st.get("offset", 0):
        st["offset"], st["line"] = e.end_byte, e.end_line
        store.save_wstate(sid, st)
    return False
