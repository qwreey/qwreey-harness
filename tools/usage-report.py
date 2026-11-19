#!/usr/bin/env python3
"""하네스 훅의 비용과 쓰임을 Claude Code 세션 트랜스크립트에서 잰다. 읽기만 한다. 표준 라이브러리만 쓴다.

  python3 -I tools/usage-report.py                         지난 7일(파일 mtime 과 줄 timestamp) 보고서를 Markdown 으로
  python3 -I tools/usage-report.py --since 2026-11-12      그날 0시(로컬)부터. --until 은 그날 끝까지 넣는다
  python3 -I tools/usage-report.py --project harness       프로젝트 키에 이 글자가 든 것만
  python3 -I tools/usage-report.py --json                  같은 숫자를 JSON 으로
  python3 -I tools/usage-report.py --time-hooks [--runs 5]      도구 호출마다 도는 훅을 임시 샌드박스에서 돌려 시간을 잰다(usage_bench.py)

트랜스크립트는 ${CLAUDE_CONFIG_DIR:-~/.claude}/projects 아래(--projects-dir 로 바꾼다). 키가 PROBE_PREFIXES 로 시작하는 시험 실행은
--include-probes 없이는 뺀다. 보고서에는 이름, 횟수, 크기, 시간만 싣고 메시지 내용, 도구 입력의 경로, 명령 글은 싣지 않는다.
읽는 줄의 꼴과 세는 규칙은 usage_scan.py 머리에 있다.

트랜스크립트로 못 보는 것: 아무것도 찍지 않은 훅의 실행(Stop 만 stop_hook_summary 에 남는다). 그 시간은 --time-hooks 로 본다.
"""
import argparse
import json
import os
import sys
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))  # python3 -I 는 스크립트 폴더를 path 에 넣지 않는다
import usage_scan as us  # noqa: E402

CODERAG_PLUGIN = ROOT.parent / "coderag" / "harness" / "claude"
TOP_CONTRIBUTORS = 8


# ---- 입력 ----

def hook_roots():
    """훅 이름을 플러그인에 잇고 --time-hooks 가 돌릴 플러그인 폴더: plugins/*, packs/*, 있으면 옆 저장소 coderag 의 harness/claude."""
    roots = sorted(p for p in (ROOT / "plugins").iterdir() if p.is_dir())
    roots += sorted(p for p in (ROOT / "packs").iterdir() if p.is_dir())
    if (CODERAG_PLUGIN / "hooks" / "hooks.json").is_file():
        roots.append(CODERAG_PLUGIN)
    return roots


def window(since, until):
    """--since, --until(로컬 날짜, until 은 그날 끝까지)을 (시작 epoch, 시작 ISO, 끝 ISO) 로. 줄 timestamp 는 UTC ISO 문자열이다."""
    now = datetime.now().astimezone()
    start = datetime.strptime(since, "%Y-%m-%d").astimezone() if since else now - timedelta(days=7)
    end = datetime.strptime(until, "%Y-%m-%d").astimezone() + timedelta(days=1) if until else now
    iso = lambda dt: dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    return start.timestamp(), iso(start), iso(end), start, end


def transcripts(projects, include_probes, project_filter, since_epoch):
    """창에 들 수 있는 트랜스크립트: (경로, 프로젝트 키, 세션 id, 서브에이전트 meta 경로 또는 None). 그리고 뺀 시험 키 수."""
    found, probes = [], 0
    for key in sorted(os.listdir(projects)) if projects.is_dir() else []:
        base = projects / key
        if key.startswith(us.PROBE_PREFIXES) and not include_probes:
            probes += 1
            continue
        if project_filter and project_filter not in key or not base.is_dir():
            continue
        for path in sorted(base.glob("*.jsonl")):
            found.append((path, key, path.stem, None))
        for path in sorted(base.glob("*/subagents/**/agent-*.jsonl")):
            found.append((path, key, path.relative_to(base).parts[0], path.with_name(path.stem + ".meta.json")))

    # 파일이 읽는 사이에 지워질 수 있다(worktree 정리 등)
    kept = []
    for item in found:
        try:
            if item[0].stat().st_mtime >= since_epoch:
                kept.append(item)
        except OSError:
            pass
    return kept, probes


def agent_record(meta_path):
    """서브에이전트 기록 칸. meta.json 의 agentType, model(요청), requestShape, spawnDepth 를 이름으로만 옮긴다."""
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        meta = {}
    return {"active": False, "type": us.safe(meta.get("agentType")), "requested": us.safe(meta.get("model") or "unset"),
            "shape": us.safe(meta.get("requestShape") or "?") + (" fork" if meta.get("isFork") else ""),
            "depth": meta.get("spawnDepth") if isinstance(meta.get("spawnDepth"), int) else None,
            "model": None, "start_chars": 0, "start_voices": Counter(), "output_tokens": 0}


def scan(args):
    """창 안 트랜스크립트를 모두 읽은 Scan 과 뺀 시험 키 수."""
    since_epoch, since_iso, until_iso, _, _ = window(args.since, args.until)
    files, probes = transcripts(Path(args.projects_dir), args.include_probes, args.project, since_epoch)
    s = us.Scan(us.Labeler(us.load_hook_entries(hook_roots())), since_iso, until_iso)
    for path, key, sid, meta in files:
        if meta is None:
            session = s.sessions.setdefault((key, sid), {"active": False, "project": key, "startup_chars": 0,
                                                         "startup_voices": Counter()})
            s.read_file(path, key, session=session)
        else:
            agent = agent_record(meta)
            s.agents.append(agent)
            s.read_file(path, key, agent=agent)
    return s, probes


# ---- 집계 ----

def stats(values):
    """{n, p50, max} 꼴. 값이 없으면 n 만 0."""
    return {"n": len(values), "p50": us.pct(values, 0.5), "max": max(values) if values else None}


def summarize(s, probes, seconds, args):
    """Scan 을 보고서용 dict 로. Markdown 과 --json 이 같은 dict 를 쓴다."""
    _, _, _, start, end = window(args.since, args.until)
    sessions = [x for x in s.sessions.values() if x["active"]]
    agents = [a for a in s.agents if a["active"]]

    # 목소리마다 플러그인 이름 고르기
    def owner(voice):
        if voice.startswith("plugin "):
            return voice[len("plugin "):]
        best = s.voices[voice]["owners"].most_common(1)
        return best[0][0] if best else s.labeler.plugin_of_name(voice) or "?"

    voices = [{"hook": v, "plugin": owner(v), "spoke": x["spoke"], "levels": dict(x["levels"]), "denies": x["denies"],
               "chars": sum(x["chars"]), "chars_p50": us.pct(x["chars"], 0.5), "chars_max": max(x["chars"]),
               "tokens": round(x["tokens"]), "events": dict(x["events"])}
              for v, x in s.voices.items()]
    runs = [{"hook": label, "event": event, "runs": sum(x["sources"].values()), "timed": len(x["durations"]),
             "p50_ms": us.pct(x["durations"], 0.5), "p95_ms": us.pct(x["durations"], 0.95),
             "max_ms": max(x["durations"]) if x["durations"] else None, "errors": x["errors"], "sources": dict(x["sources"])}
            for (label, event), x in s.runs.items()]

    # 상시 주입: 세션 시작(startup), 서브에이전트 시작, 사용자 입력마다
    startups = [x["startup_chars"] for x in sessions if x["startup_chars"]]
    sub_starts = [a["start_chars"] for a in agents if a["start_chars"]]
    startup_voices, sub_voices = Counter(), Counter()
    for x in sessions:
        startup_voices.update(x["startup_voices"])
    for a in agents:
        sub_voices.update(a["start_voices"])
    top = [{"hook": v, "plugin": owner(v), "session_start_avg": round(startup_voices[v] / len(startups)) if startups else 0,
            "subagent_start_avg": round(sub_voices[v] / len(sub_starts)) if sub_starts else 0}
           for v in set(startup_voices) | set(sub_voices)]
    top.sort(key=lambda t: -(t["session_start_avg"] + t["subagent_start_avg"]))

    # 토큰: message.id 마다 한 번
    per_project, per_model = {}, {}
    for project, model, owner_rec, counts in s.usage.values():
        for table, key in ((per_project, project), (per_model, model)):
            row = table.setdefault(key, dict.fromkeys([k for k, _ in us.USAGE_FIELDS], 0))
            for k, n in counts.items():
                row[k] += n
        if "output_tokens" in owner_rec:
            owner_rec["output_tokens"] += counts["output"]
    sub_rows = Counter()
    sub_tokens = Counter()
    for a in agents:
        key = (a["type"], a["requested"], a["model"] or "?", a["shape"])
        sub_rows[key] += 1
        sub_tokens[key] += a["output_tokens"]

    return {
        "window": {"since": start.isoformat(timespec="minutes"), "until": end.isoformat(timespec="minutes"),
                   "project_filter": args.project, "probe_keys_excluded": probes},
        "read": {"files": s.files, "bytes": s.bytes, "seconds": round(seconds, 2)},
        "sessions": len(sessions), "subagents_total": len(agents),
        "projects": sorted({x["project"] for x in sessions} | {p for p, _, _, _ in s.usage.values()}),
        "hooks_spoke": sorted(voices, key=lambda v: -v["chars"]),
        "hook_runs": sorted(runs, key=lambda r: (r["event"], -(r["p50_ms"] or 0))),
        "denies": [{"hook": h, "tool": t, "kind": k, "count": n} for (h, t, k), n in s.denies.most_common()],
        "user_messages": [{"hook": h, "count": len(c), "chars": sum(c)} for h, c in sorted(s.user_messages.items())],
        "always_on": {"session_startup": stats(startups), "session_later": {k: stats(v) for k, v in s.later_starts.items()},
                      "subagent_start": stats(sub_starts), "user_prompt": stats(s.prompt_chars), "top": top[:TOP_CONTRIBUTORS]},
        "subagents": [{"type": k[0], "requested_model": k[1], "model": k[2], "shape": k[3], "count": n,
                       "output_tokens": sub_tokens[k]} for k, n in sub_rows.most_common()],
        "tokens_by_project": [{"project": k, **v} for k, v in sorted(per_project.items())],
        "tokens_by_model": [{"model": k, **v} for k, v in sorted(per_model.items())],
    }


# ---- 출력 ----

def num(v):
    """표 칸 숫자. None 은 "-", 큰 수는 천 단위 쉼표."""
    if v is None:
        return "-"
    return "{:,}".format(round(v)) if isinstance(v, (int, float)) else str(v)


def table(head, rows):
    """Markdown 표 줄들. 줄이 없으면 "(none)" 한 줄."""
    if not rows:
        return ["(none)"]
    lines = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    return lines + ["| " + " | ".join(num(c) for c in row) + " |" for row in rows]


def markdown(r):
    """summarize 결과를 짧은 Markdown 보고서 줄들로."""
    w, rd, ao = r["window"], r["read"], r["always_on"]
    out = ["# Usage report", "",
           "- Window: %s .. %s%s" % (w["since"], w["until"], ", project ~ %s" % w["project_filter"] if w["project_filter"] else ""),
           "- Sessions: %d main, %d subagents, %d projects (%d probe keys excluded)"
           % (r["sessions"], r["subagents_total"], len(r["projects"]), w["probe_keys_excluded"]),
           "- Read: %d files, %.1f MB, %.1f s" % (rd["files"], rd["bytes"] / 1e6, rd["seconds"]), ""]

    out += ["## Hooks that spoke (text the model saw)", ""]
    out += table(["hook", "plugin", "spoke", "info/warn/action/-", "denies", "chars", "p50", "max", "~tokens"],
                 [[v["hook"], v["plugin"], v["spoke"], "/".join(str(v["levels"].get(k, 0)) for k in (*us.LEVELS, "-")),
                   v["denies"], v["chars"], v["chars_p50"], v["chars_max"], v["tokens"]] for v in r["hooks_spoke"]])

    out += ["", "## Hook run time", "", "Recorded only when the hook printed something, except Stop (stop summary has all). See --time-hooks.", ""]
    out += table(["hook", "event", "runs", "p50 ms", "p95 ms", "max ms", "errors"],
                 [[x["hook"], x["event"], x["runs"], x["p50_ms"], x["p95_ms"], x["max_ms"], x["errors"]] for x in r["hook_runs"]])

    out += ["", "## Denies and blocking errors", ""]
    out += table(["hook", "tool", "kind", "count"], [[d["hook"], d["tool"], d["kind"], d["count"]] for d in r["denies"]])
    out += ["", "## Shown to the user (systemMessage)", ""]
    out += table(["hook", "count", "chars"], [[m["hook"], m["count"], m["chars"]] for m in r["user_messages"]])

    out += ["", "## Always-on injection (chars)", ""]
    rows = [["SessionStart startup, per session", ao["session_startup"]],
            *[["SessionStart %s, per record" % k, v] for k, v in sorted(ao["session_later"].items())],
            ["SubagentStart, per subagent", ao["subagent_start"]], ["UserPromptSubmit, per record", ao["user_prompt"]]]
    out += table(["when", "n", "p50", "max"], [[name, st["n"], st["p50"], st["max"]] for name, st in rows])
    out += ["", "Top contributors (average chars):", ""]
    out += table(["hook", "plugin", "per session start", "per subagent start"],
                 [[t["hook"], t["plugin"], t["session_start_avg"], t["subagent_start_avg"]] for t in ao["top"]])

    out += ["", "## Subagents", ""]
    out += table(["type", "requested model", "model", "shape", "count", "output tokens"],
                 [[a["type"], a["requested_model"], a["model"], a["shape"], a["count"], a["output_tokens"]] for a in r["subagents"]])

    out += ["", "## Tokens", ""]
    head = ["input", "cache read", "cache creation", "output"]
    out += table(["project", *head], [[t["project"], *(t[k] for k, _ in us.USAGE_FIELDS)] for t in r["tokens_by_project"]])
    out += [""] + table(["model", *head], [[t["model"], *(t[k] for k, _ in us.USAGE_FIELDS)] for t in r["tokens_by_model"]])
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--since", help="YYYY-MM-DD, local midnight (default: 7 days ago)")
    ap.add_argument("--until", help="YYYY-MM-DD, inclusive (default: now)")
    ap.add_argument("--project", help="keep project keys containing this substring")
    ap.add_argument("--include-probes", action="store_true", help="keep keys starting with %s" % ", ".join(us.PROBE_PREFIXES))
    ap.add_argument("--projects-dir", default=str(Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude") / "projects"))
    ap.add_argument("--json", action="store_true", help="machine output")
    ap.add_argument("--time-hooks", action="store_true", help="time silent per-tool-call hooks in a temp sandbox instead")
    ap.add_argument("--runs", type=int, default=5, help="--time-hooks: runs per hook")
    ap.add_argument("--hook-root", action="append", help="--time-hooks: plugin folder to bench (repeatable; default: this repo's plugins)")
    args = ap.parse_args()

    # --time-hooks 는 트랜스크립트를 읽지 않는 다른 동작이다
    if args.time_hooks:
        import usage_bench
        roots = [Path(p).resolve() for p in args.hook_root] if args.hook_root else hook_roots()
        result = usage_bench.bench(roots, max(1, args.runs))
        print(json.dumps(result, indent=1) if args.json else "\n".join(usage_bench.markdown(result)))
        return 0

    started = time.monotonic()
    s, probes = scan(args)
    report = summarize(s, probes, time.monotonic() - started, args)
    print(json.dumps(report, indent=1, ensure_ascii=False) if args.json else "\n".join(markdown(report)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
