#!/usr/bin/env python3
"""review-ledger — 검토(second opinion) 결과를 한 줄씩 남기고 집계한다. 표준 라이브러리만.

왜: "도움이 되는 정도"를 감이 아니라 데이터로 조정하려고. 검토 종류·검토자·트리거별로
    발견 수와 메인이 실제로 받아들인 수를 남기면, 어떤 시점·어떤 검토자가 값을 하는지 보인다.

저장: ${XDG_STATE_HOME:-~/.local/state}/claude-second-opinion/ledger.jsonl (저장소 트리 밖. 다른 세션과 충돌하지 않게 append 만)

사용:
  review-ledger.py add --kind done --reviewer opus-sub --trigger hook:commit --verdict 고친뒤진행 \
                       --found 4 --adopted 3 --must 1 [--repo DIR] [--note "..."] [--caller main|subagent] [--ref srvtoolu_… | agent-…]
  review-ledger.py stats [--since YYYY-MM-DD] [--repo NAME]
  kind: plan | stuck | done | adhoc | inherit (옛 context|audit 도 받는다)        reviewer: opus-sub | sonnet-sub | fork | codex | agy | advisor-opus | advisor-fable
  verdict: 진행 | 고친뒤진행 | 다시생각 | 발견없음 | 실패 (미기록 은 훅의 자동 행 전용)
advisor 는 조언 본문이 암호화돼 있어 found/adopted 를 메인이 응답에서 밝힌 수로 적는다(advisor-stats.py 의 '직후 첫 텍스트' 참고).

자동 행: 메인이 부른 qwreey-advisor 리뷰어나 inherit-advisor fork 가 끝나면 훅(second-opinion-nudge.py)이 auto_add 로
verdict 미기록, auto=true, ref=agent-<id> 인 행을 남긴다. 그래서 메인이 add 를 잊어도 사용 횟수는 보인다.
나중에 add 가 같은 검토를 적으면 그 행의 supersedes 에 자동 행의 ref 를 적고(--ref 가 맞으면 그것, 아니면 같은 세션에서
검토자 계열이 같고 아직 짝이 없는 가장 최근 자동 행, AUTO_LINK_HOURS 안), stats 는 짝이 생긴 자동 행을 세지 않는다.
append 만 하므로 기존 행은 고치지 않는다.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

KINDS = ("plan", "stuck", "done", "adhoc", "inherit", "context", "audit")  # context|audit 는 옛 기록과의 호환(새로 쓰지 않는다)
CALLERS = ("main", "subagent")
VERDICTS = ("진행", "고친뒤진행", "다시생각", "발견없음", "실패")
UNRECORDED = "미기록"  # 자동 행의 판정. add 의 선택지에는 넣지 않는다
AUTO_LINK_HOURS = 6  # 자동 행과 사람이 쓴 행을 짝지을 최대 간격
TS_FORMAT = "%Y-%m-%dT%H:%M:%S%z"


def ledger_path() -> Path:
    base = os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state")
    return Path(base) / "claude-second-opinion" / "ledger.jsonl"


def repo_name(d: str) -> str:
    try:
        top = subprocess.run(["git", "-C", d, "rev-parse", "--show-toplevel"], capture_output=True, text=True, timeout=5).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        top = ""
    return Path(top or d).name


def family(reviewer: str) -> str:
    """자동 행과 사람이 쓴 행을 짝지을 때 보는 검토자 계열: fork 또는 sub(새 컨텍스트 리뷰어)."""
    return "fork" if reviewer == "fork" else "sub" if reviewer.endswith("-sub") or reviewer == "sub" else reviewer


def read_rows() -> list[dict]:
    p = ledger_path()
    if not p.is_file():
        return []
    rows = []
    for line in p.read_text(encoding="utf-8").splitlines():
        try:
            rows.append(json.loads(line))
        except ValueError:
            continue
    return rows


def append(rec: dict) -> Path:
    p = ledger_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return p


def auto_add(kind: str, reviewer: str, caller: str, ref: str, repo_dir: str, session: str) -> Path:
    """훅이 부른다: 검토가 끝났다는 것만 남긴다(판정·발견 수는 메인의 add 몫)."""
    return append({
        "ts": time.strftime(TS_FORMAT), "session": session, "repo": repo_name(repo_dir), "kind": kind, "reviewer": reviewer,
        "trigger": "", "verdict": UNRECORDED, "caller": caller, "found": 0, "adopted": 0, "must": 0, "ref": ref, "note": "",
        "auto": True,
    })


def epoch(ts: str) -> float:
    try:
        return datetime.strptime(ts, TS_FORMAT).timestamp()
    except (TypeError, ValueError):
        return 0.0


def link_target(rows: list[dict], reviewer: str, ref: str, session: str, now: float) -> str:
    """사람이 쓰는 행이 대신할 자동 행의 ref. 없으면 빈 값."""
    taken = {r.get("supersedes") for r in rows if r.get("supersedes")}
    autos = [r for r in rows if r.get("auto") and r.get("ref") and r["ref"] not in taken]
    if ref:
        hit = [r for r in autos if r["ref"] == ref]
        if hit:
            return ref
    cands = [r for r in autos if family(r.get("reviewer", "")) == family(reviewer)
             and (not session or r.get("session") == session) and 0 <= now - epoch(r.get("ts", "")) <= AUTO_LINK_HOURS * 3600]
    return cands[-1]["ref"] if cands else ""


def add(a) -> int:
    session = os.environ.get("CLAUDE_CODE_SESSION_ID", "")
    rec = {
        "ts": time.strftime(TS_FORMAT), "session": session,
        "repo": repo_name(a.repo), "kind": a.kind, "reviewer": a.reviewer, "trigger": a.trigger,
        "verdict": a.verdict, "caller": a.caller, "found": a.found, "adopted": a.adopted, "must": a.must, "ref": a.ref, "note": a.note,
    }
    target = link_target(read_rows(), a.reviewer, a.ref, session, time.time())
    if target:
        rec["supersedes"] = target
    p = append(rec)
    print(f"기록: {p}" + (f" (자동 행 {target} 를 대신함)" if target else ""))
    return 0


def stats(a) -> int:
    all_rows = read_rows()
    if not all_rows:
        print("기록 없음")
        return 0
    taken = {r.get("supersedes") for r in all_rows if r.get("supersedes")}
    rows = []
    for r in all_rows:
        if r.get("auto") and r.get("ref") in taken:
            continue
        if a.since and r.get("ts", "") < a.since:
            continue
        if a.repo and r.get("repo") != a.repo:
            continue
        rows.append(r)
    g = defaultdict(lambda: {"n": 0, "found": 0, "adopted": 0, "must": 0, "empty": 0, "unrec": 0})
    for r in rows:
        for key in ((r["kind"], r["reviewer"]), ("trigger", r.get("trigger") or "-"), ("caller", r.get("caller") or "-")):
            s = g[key]
            s["n"] += 1; s["found"] += r.get("found", 0); s["adopted"] += r.get("adopted", 0); s["must"] += r.get("must", 0)
            s["empty"] += r.get("verdict") == "발견없음"
            s["unrec"] += r.get("verdict") == UNRECORDED
    print(f"{len(rows)}건 ({ledger_path()})\n")
    print("| 묶음 | 건수 | 발견 | 채택 | 채택률 | 반드시 | 발견없음 | 미기록 |")
    print("|---|---|---|---|---|---|---|---|")
    for k, s in sorted(g.items()):
        rate = f"{s['adopted'] / s['found']:.0%}" if s["found"] else "-"
        print(f"| {' / '.join(k)} | {s['n']} | {s['found']} | {s['adopted']} | {rate} | {s['must']} | {s['empty']} | {s['unrec']} |")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    pa = sub.add_parser("add")
    pa.add_argument("--kind", choices=KINDS, required=True)
    pa.add_argument("--reviewer", required=True)
    pa.add_argument("--trigger", default="manual")
    pa.add_argument("--verdict", choices=VERDICTS, required=True)
    pa.add_argument("--found", type=int, default=0)
    pa.add_argument("--adopted", type=int, default=0)
    pa.add_argument("--must", type=int, default=0)
    pa.add_argument("--repo", default=".")
    pa.add_argument("--ref", default="")
    pa.add_argument("--caller", choices=CALLERS, default="")  # 없으면 빈 값(옛 기록과 같다)
    pa.add_argument("--note", default="")
    ps = sub.add_parser("stats")
    ps.add_argument("--since", default="")
    ps.add_argument("--repo", default="")
    a = ap.parse_args()
    return add(a) if a.cmd == "add" else stats(a)


if __name__ == "__main__":
    sys.exit(main())
