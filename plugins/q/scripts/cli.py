#!/usr/bin/env python3
"""session-log CLI.

  session-log pending [--json]                  받아 가지 않은 기록 목록(~토큰, 요약 한 줄)
  session-log show <rid> [--section N]          기록 보기
  session-log import [rid…] [--to DIR] [--force]  대기 기록(rid 생략 시 전부)을 보관 폴더로 그대로 복사하고 imported 로 표시. 머리말 두 줄만 붙는다
  session-log home [PATH | --archive-only | --unset]  저장소 보관 폴더 보기·저장(.claude/session-log.json, 커밋해 공유)
  session-log dismiss <rid…> [--reason TEXT]    고르지 않은 기록을 dismissed 로
  session-log flush [--session SID] [--transcript P] [--trigger T] [--force] [--wait]   지금 요약(수동 /q:checkpoint)
  session-log status                            저장소 위치·세션별 상태·최근 오류
  session-log brief precompact|handover [--session SID]   주입 문자열 미리 보기
  session-log backfill --plan plan.json [--budget USD] [--dry-run]   남은 트랜스크립트 소급 요약
  session-log verify <record.md> <transcript>   기록을 원문과 다시 대조(표시는 바꾸지 않음)
공통: --project DIR (기본: $CLAUDE_PROJECT_DIR, 없으면 현재 디렉터리. worktree 면 본 체크아웃)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from sllib import brief, config, extract as ex, records_home, summarize, verify, worker  # noqa: E402
from sllib.paths import find_transcript, latest_transcript_for, project_root, short_home  # noqa: E402
from sllib.store import Store, fmt_tokens, token_estimate  # noqa: E402


def store_for(a) -> Store:
    start = a.project or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    return Store(project_root(start))


def session_and_transcript(a, store: Store) -> tuple[str, str]:
    tp = a.transcript or ""
    sid = a.session or (Path(tp).stem if tp else "") or os.environ.get("CLAUDE_CODE_SESSION_ID") or ""
    if not tp and sid:
        p = find_transcript(sid)
        tp = str(p) if p else ""
    if not tp:
        p = latest_transcript_for(store.root)
        tp = str(p) if p else ""
    if tp and not sid:
        sid = Path(tp).stem
    return sid, tp


def cmd_pending(a):
    st = store_for(a)
    rows = st.pending()
    if a.json:
        print(json.dumps(rows, ensure_ascii=False, indent=1)); return
    if not rows:
        print(f"pending 없음 ({short_home(st.dir)})"); return
    print(f"# {short_home(st.records)} — pending {len(rows)}개")
    for e in rows:
        p = st.record_path(e["rid"])
        try:
            tok = fmt_tokens(token_estimate(p.read_text(encoding="utf-8")))
        except OSError:
            tok = "?"
        extra = f" (imported {e.get('imported_sections', 0)}절 → 새 절 있음)" if e.get("status") == "imported" else ""
        v = e.get("verify") or {}
        flag = v.get("num_missing", 0) + v.get("quote_bad", 0) + v.get("cite_bad", 0)
        print(f"{e['rid']}  {tok}  {e.get('sections', 0)}절  {e.get('created', '')[:10]}{extra}"
              + (f"  ⚠{flag}" if flag else "") + f"\n    {e.get('description', '')}")


def cmd_show(a):
    st = store_for(a)
    p = st.record_path(a.rid)
    if not p.exists():
        sys.exit(f"없음: {a.rid}")
    text = p.read_text(encoding="utf-8")
    if a.section is None:
        sys.stdout.write(text); return
    secs = text.split("\n## ")
    if not (1 <= a.section < len(secs)):
        sys.exit(f"절 번호 범위: 1–{len(secs) - 1}")
    sys.stdout.write("## " + secs[a.section] + ("\n" if not secs[a.section].endswith("\n") else ""))


def cmd_import(a):
    """대기 중인 기록을 보관 폴더로 그대로 복사하고 imported 로 표시한다. 고르거나 고쳐 쓰지 않는다."""
    st = store_for(a)
    idx = st.index()
    if a.to:
        to = a.to
    elif records_home.archive_only(st.root):
        sys.exit("이 저장소는 기록을 저장소 밖에만 둔다(archive_only). 가져가려면 --to DIR 을 주거나 `session-log home <경로>` 로 바꾼다.")
    else:
        # 위치를 모르는 채 기본 폴더에 복사하면 사용자가 원치 않은 파일이 저장소에 남는다. 묻고 정하게 한다
        to = records_home.home_rel(st.root)
        if not to:
            sys.exit("records home is not set, so nothing was copied. Ask the user where records go "
                     "(`docs/sessions/`, `.claude/sessions/`, an existing history dir, or `--archive-only` to keep them outside the repo), "
                     "save the answer with `session-log home <path>`, then run `session-log import` again. "
                     "To copy once without saving a home, pass `--to DIR`.")
    to_dir = (st.root / to) if not os.path.isabs(to) else Path(to)
    rids = a.rid or [e["rid"] for e in st.pending()]
    if not rids:
        print("pending 없음"); return
    now = datetime.now().isoformat(timespec="seconds")
    n = 0
    for rid in rids:
        if rid not in idx:
            print(f"없음: {rid}", file=sys.stderr); continue
        dst = to_dir / f"{rid}.md"
        try:
            rel = str(dst.relative_to(st.root))
        except ValueError:
            rel = str(dst)
        # 새 절이 붙어 다시 pending 이 된 기록은 같은 파일의 늘어난 판이라 덮어쓴다
        if dst.exists() and idx[rid].get("imported_to") != rel and not a.force:
            print(f"이미 있음(--force 로 덮어씀): {dst}", file=sys.stderr); continue
        to_dir.mkdir(parents=True, exist_ok=True)
        text = st.record_path(rid).read_text(encoding="utf-8")
        dst.write_text(records_home.with_header(text, rid), encoding="utf-8")
        st.mark(rid, status="imported", imported_to=rel, imported_at=now,
                imported_sections=idx[rid].get("sections", 0), imported_commit="")
        print(f"imported {rid} → {dst}")
        n += 1
    if n:
        print(f"{n}개 복사. 다음 커밋에 {to}/ 를 넣는다(플러그인은 git 을 건드리지 않는다).")


def cmd_home(a):
    st = store_for(a)
    if a.path or a.archive_only or a.unset:
        try:
            d = records_home.save(st.root, home=a.path, archive=a.archive_only, unset=a.unset)
        except ValueError as e:
            sys.exit(str(e))
        print(f"saved {records_home.FILE}: {json.dumps(d, ensure_ascii=False) if d else '(unset)'}\n"
              "이 파일을 커밋하면 동료도 같은 위치를 쓴다.")
        return
    if records_home.archive_only(st.root):
        print("archive_only: 기록은 저장소 밖에만 둔다(pending 알림 꺼짐)")
    else:
        h = records_home.home_rel(st.root)
        print(f"records home: {h + '/' if h else '(미설정; import 는 --to 가 없으면 거절한다)'}")


def cmd_dismiss(a):
    st = store_for(a)
    for rid in a.rid:
        try:
            st.mark(rid, status="dismissed", dismissed_at=datetime.now().isoformat(timespec="seconds"), reason=a.reason or "")
            print(f"dismissed {rid}")
        except KeyError:
            print(f"없음: {rid}", file=sys.stderr)


def cmd_flush(a):
    st = store_for(a)
    sid, tp = session_and_transcript(a, st)
    if not tp:
        sys.exit("트랜스크립트를 찾지 못했다(--transcript)")
    t0 = time.time()
    r = worker.flush(st, sid, tp, a.trigger, force=a.force)
    r["wall_s"] = round(time.time() - t0, 1)
    if a.wait or sys.stdout.isatty():
        r["records"] = [short_home(st.record_path(x)) for x in r.get("rids", [])]
        print(json.dumps(r, ensure_ascii=False))


def cmd_status(a):
    st = store_for(a)
    print(f"project: {st.root}\nstore:   {short_home(st.dir)}  (exists: {st.exists()})")
    if not st.exists():
        return
    idx = st.index()
    by = {}
    for e in idx.values():
        by[e.get("status", "pending")] = by.get(e.get("status", "pending"), 0) + 1
    print(f"records: {len(idx)} {by}  pending: {len(st.pending())}")
    for rid, e in sorted(idx.items()):
        if e.get("status") == "imported":
            c = st.resolve_commit(e)
            if c and not e.get("imported_commit"):
                st.mark(rid, imported_commit=c)
            print(f"  imported {rid} → {e.get('imported_to')} (commit {c or 'not yet'})")
    for p in sorted(st.state.glob("*.json")):
        if p.name.endswith(".hook.json"):
            continue
        w = json.loads(p.read_text())
        lr = datetime.fromtimestamp(w.get("last_run", 0)).isoformat(timespec="minutes") if w.get("last_run") else "-"
        print(f"  {p.stem[:8]} offset {w.get('offset', 0)} line {w.get('line', 0)} sections {w.get('sections', 0)}"
              f" cost ${w.get('cost_usd', 0):.3f} last_run {lr} failures {w.get('failures', 0)}")
    el = st.state / "errors.log"
    if el.exists():
        tail = el.read_text(encoding="utf-8").splitlines()[-5:]
        if tail:
            print("errors (last 5):\n  " + "\n  ".join(tail))


def cmd_brief(a):
    st = store_for(a)
    sid, tp = session_and_transcript(a, st)
    if a.kind == "precompact":
        print(brief.precompact(st, sid, tp))
    else:
        print(brief.handover(st, sid, a.source, tp))
        print(brief.pending_line(st, "session_start")[1])


def window_offsets(path: str, t_from: str | None, t_to: str | None) -> tuple[tuple[int, int] | None, int | None]:
    """ISO 시각 창 → (시작 (바이트, 앞 줄 수), 끝 바이트). 창이 없으면 None."""
    import json as _j
    start, end = None, None
    pos, n = 0, 0
    with open(path, "rb") as f:
        for raw in f:
            ts = ""
            if b'"timestamp"' in raw[:4000] or b'"timestamp"' in raw:
                try:
                    ts = _j.loads(raw).get("timestamp") or ""
                except (ValueError, AttributeError):
                    ts = ""
            if ts:
                if t_from and start is None and ts >= t_from:
                    start = (pos, n)
                if t_to and end is None and ts >= t_to:
                    end = pos
                    break
            pos += len(raw); n += 1
    return start, end


def cmd_backfill(a):
    plan = json.load(open(a.plan, encoding="utf-8"))
    budget = a.budget
    spent = 0.0
    log = []
    for item in plan:
        tp = item["transcript"]
        root = project_root(item.get("project") or ex.first_cwd(tp) or os.path.dirname(tp))
        st = Store(root)
        sid = Path(tp).stem
        start, end = window_offsets(tp, item.get("from"), item.get("to")) if (item.get("from") or item.get("to")) else (None, None)
        if item.get("from") and start is None:
            log.append({"sid": sid[:8], "skip": "window empty"}); continue
        e = ex.extract(tp, start[0] if start else 0, start[1] if start else 0, to_byte=end)
        est = sum(summarize.estimate_cost(len("\n".join(x.text for x in ch)), a.model or config.get("SESSION_LOG_MODEL"))
                  for ch in ex.chunks(e.entries, int(config.num("SESSION_LOG_CHUNK_CHARS"))))
        row = {"sid": sid[:8], "project": root.name, "chars": e.chars, "chunks": len(ex.chunks(e.entries, int(config.num("SESSION_LOG_CHUNK_CHARS")))),
               "est_usd": round(est, 3)}
        if a.dry_run:
            log.append(row); print(json.dumps(row, ensure_ascii=False)); continue
        t0 = time.time()
        r = worker.flush(st, sid, tp, "backfill", force=True, model=a.model, budget_left=budget - spent,
                         until_byte=end, start_at=start, notify=True)
        spent += r.get("cost_usd", 0.0)
        row.update({k: r.get(k) for k in ("sections", "rids", "flagged", "calls", "error", "budget_stop", "locked")},
                   cost_usd=round(r.get("cost_usd", 0.0), 4), wall_s=round(time.time() - t0, 1), spent=round(spent, 4))
        if end is not None or start is not None:
            row["window"] = [item.get("from"), item.get("to")]
        log.append(row)
        print(json.dumps(row, ensure_ascii=False), flush=True)
        if r.get("budget_stop"):
            print(json.dumps({"stop": "budget", "spent": round(spent, 4)}), flush=True)
            break
    tot = {"total_usd": round(spent, 4), "items": len(log)}
    if a.dry_run:
        tot["est_usd"] = round(sum(x.get("est_usd", 0) for x in log), 3)
    print(json.dumps(tot))


def cmd_verify(a):
    text = open(a.record, encoding="utf-8").read()
    total = {}
    for sec in text.split("\n## ")[1:]:
        import re
        m = re.search(r"note: L(\d+)–L(\d+)", sec)
        if not m:
            continue
        lo, hi = int(m.group(1)), int(m.group(2))
        src = {}
        with open(a.transcript, "rb") as f:
            for i, raw in enumerate(f, 1):
                if i > hi:
                    break
                if i >= lo:
                    src[i] = verify.body_of(raw)
        body = sec.split("\n", 2)[-1]
        clean = re.sub(r" ⚠\S+( ⚠\S+)*$", "", body, flags=re.M)
        _, c = verify.check_section(clean, src)
        for k, v in c.items():
            total[k] = total.get(k, 0) + v
    print(json.dumps(total, ensure_ascii=False))


def main():
    ap = argparse.ArgumentParser(prog="session-log", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project")
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("pending"); p.add_argument("--json", action="store_true"); p.set_defaults(f=cmd_pending)
    p = sp.add_parser("show"); p.add_argument("rid"); p.add_argument("--section", type=int); p.set_defaults(f=cmd_show)
    p = sp.add_parser("import"); p.add_argument("rid", nargs="*"); p.add_argument("--to", help="보관 폴더(기본: 설정된 records home)")
    p.add_argument("--force", action="store_true"); p.set_defaults(f=cmd_import)
    p = sp.add_parser("home"); p.add_argument("path", nargs="?"); p.add_argument("--archive-only", action="store_true")
    p.add_argument("--unset", action="store_true"); p.set_defaults(f=cmd_home)
    p = sp.add_parser("dismiss"); p.add_argument("rid", nargs="+"); p.add_argument("--reason"); p.set_defaults(f=cmd_dismiss)
    p = sp.add_parser("flush")
    for o in ("--session", "--transcript"):
        p.add_argument(o)
    p.add_argument("--trigger", default="checkpoint"); p.add_argument("--force", action="store_true")
    p.add_argument("--wait", action="store_true"); p.set_defaults(f=cmd_flush)
    p = sp.add_parser("status"); p.set_defaults(f=cmd_status)
    p = sp.add_parser("brief"); p.add_argument("kind", choices=["precompact", "handover"])
    p.add_argument("--session"); p.add_argument("--transcript"); p.add_argument("--source", default="resume"); p.set_defaults(f=cmd_brief)
    p = sp.add_parser("backfill"); p.add_argument("--plan", required=True); p.add_argument("--budget", type=float, default=4.0)
    p.add_argument("--model"); p.add_argument("--dry-run", action="store_true"); p.set_defaults(f=cmd_backfill)
    p = sp.add_parser("verify"); p.add_argument("record"); p.add_argument("transcript"); p.set_defaults(f=cmd_verify)
    for name, sub in sp.choices.items():
        if name != "verify" and not any(x.dest == "project" for x in sub._actions):
            sub.add_argument("--project", default=argparse.SUPPRESS)
    a = ap.parse_args()
    if not hasattr(a, "project"):
        a.project = None
    a.f(a)


if __name__ == "__main__":
    main()
