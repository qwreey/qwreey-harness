"""review_record: SubagentStop 에서 끝난 서브에이전트가 메인이 부른 검토인지 가리고, 그렇다면 최근 검토 시각과 ledger 자동 행을 남긴다.

검토로 치는 것
  - qwreey-advisor:reviewer (예전 이름 qwreey-advisor-reviewer).
  - agent_type 이 fork 이고 transcript 앞부분에 inherit-advisor 표지(`[qwreey-advisor:inherit]`, 펼친 뒤의 첫 줄
    `[second opinion: inherit]`)가 있는 것. fork transcript 는 부모 대화를 복사하지 않고(fork-context-ref 한 줄)
    둘째 줄의 Agent 호출 입력과 셋째 줄의 지시에 표지가 있다(실측, claude 2.1.316).
호출자: 서브에이전트 transcript 옆 `agent-<id>.meta.json` 의 parentAgentId(또는 spawnDepth > 1)가 있으면 subagent.
리뷰어는 track-reviewer.py 의 run 줄도 본다. 둘 다 없으면 main.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import tempfile
import time

NS = "claude-second-opinion"
RUN_LINE = re.compile(r"\[qwreey-advisor run: ([0-9a-f-]{36}) caller=(main|subagent) scratch=[^\]\n]*\]")
REVIEWERS = {"qwreey-advisor:reviewer", "qwreey-advisor-reviewer"}  # 플러그인 이름공간 + 예전 이름
FORK_MARKERS = ("[qwreey-advisor:inherit]", "[second opinion: inherit]")
HEAD_BYTES = 64 * 1024
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEDGER = os.path.join(ROOT, "skills", "fresh-advisor", "scripts", "review-ledger.py")


def last_review_path(sid: str) -> str:
    """검토 완료 시각은 compact 를 넘어 유지한다(회차와 무관)."""
    d = os.path.join(tempfile.gettempdir(), NS)
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, re.sub(r"[^\w-]", "", sid or "nosession") + ".last-review")


def last_review_time(sid: str) -> float:
    try:
        return float(open(last_review_path(sid)).read().strip())
    except (OSError, ValueError):
        return 0.0


def read_meta(tpath: str) -> dict:
    if not tpath or not tpath.endswith(".jsonl"):
        return {}
    try:
        with open(tpath[:-len(".jsonl")] + ".meta.json", encoding="utf-8") as f:
            m = json.load(f)
        return m if isinstance(m, dict) else {}
    except (OSError, ValueError):
        return {}


def nested(meta: dict) -> bool | None:
    """서브에이전트가 띄운 것이면 True, 메인이 띄운 것이면 False, meta 가 없으면 None."""
    if not meta:
        return None
    try:
        depth = int(meta.get("spawnDepth") or 1)
    except (TypeError, ValueError):
        depth = 1
    return bool(meta.get("parentAgentId")) or depth > 1


def head_text(tpath: str) -> str:
    try:
        with open(tpath or "", encoding="utf-8", errors="replace") as f:
            return f.read(HEAD_BYTES)
    except OSError:
        return ""


def run_caller(tpath: str) -> str | None:
    """리뷰어 transcript 의 첫 user 메시지에서 track-reviewer.py 가 붙인 run 줄의 호출자. 줄이 없으면 None."""
    try:
        with open(tpath or "", encoding="utf-8") as f:
            for line in f:
                rec = json.loads(line)
                if rec.get("type") != "user":
                    continue
                c = (rec.get("message") or {}).get("content")
                if isinstance(c, list):
                    c = "\n".join(x.get("text", "") for x in c if isinstance(x, dict))
                m = RUN_LINE.findall(c if isinstance(c, str) else "")
                return m[-1][1] if m else None
    except (OSError, ValueError, AttributeError):
        pass
    return None


def review_kind(data: dict, meta: dict) -> str | None:
    """'reviewer', 'fork', 또는 검토가 아니면 None."""
    at = data.get("agent_type") or ""
    if at in REVIEWERS:
        return "reviewer"
    if at == "fork":
        head = head_text(data.get("agent_transcript_path") or "")
        if any(m in head for m in FORK_MARKERS) or (meta.get("description") or "").startswith("second opinion: inherit"):
            return "fork"
    return None


def caller_of(data: dict, meta: dict, kind: str) -> str:
    if nested(meta):
        return "subagent"
    if kind == "reviewer" and run_caller(data.get("agent_transcript_path") or "") == "subagent":
        return "subagent"
    return "main"


def ledger_fields(kind: str, meta: dict) -> tuple[str, str]:
    """(ledger kind, reviewer). 리뷰어 kind 는 스킬이 정한 description `second opinion: <kind>` 에서 읽는다."""
    if kind == "fork":
        return "inherit", "fork"
    m = re.match(r"second opinion:\s*(\w+)", meta.get("description") or "")
    lk = m.group(1) if m and m.group(1) in ("plan", "stuck", "done") else "adhoc"
    model = str(meta.get("model") or "")
    rv = "opus-sub" if "opus" in model else "sonnet-sub" if "sonnet" in model else (model + "-sub" if model and model != "inherit" else "sub")
    return lk, rv


def ledger_auto(data: dict, meta: dict, kind: str, caller: str) -> None:
    try:
        spec = importlib.util.spec_from_file_location("review_ledger", LEDGER)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        lk, rv = ledger_fields(kind, meta)
        mod.auto_add(lk, rv, caller, "agent-" + str(data.get("agent_id") or ""), data.get("cwd") or os.getcwd(), data.get("session_id") or "")
    except Exception:  # ledger 를 못 써도 검토 기록(last-review)은 남긴다
        pass


def on_stop(data: dict) -> dict:
    """검토면 기록한다. 돌려주는 값: review(검토 여부), caller, meta."""
    meta = read_meta(data.get("agent_transcript_path") or "")
    kind = review_kind(data, meta)
    if not kind:
        return {"review": False, "meta": meta}
    caller = caller_of(data, meta, kind)
    if caller == "main":  # 일꾼이 띄운 검토는 메인의 검토가 아니다
        open(last_review_path(data.get("session_id") or ""), "w").write(str(time.time()))
    ledger_auto(data, meta, kind, caller)
    return {"review": True, "caller": caller, "meta": meta}
