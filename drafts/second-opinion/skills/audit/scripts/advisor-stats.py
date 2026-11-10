#!/usr/bin/env python3
"""advisor-stats — 세션 트랜스크립트(jsonl)에서 advisor 호출을 집계한다. 읽기 전용, 표준 라이브러리만.

무엇을 세나 (Claude Code 2.1.316 트랜스크립트에서 실측한 스키마, audit/18 §1.3):
  - attachment.type == "advisor_tool"  → 켜고 끈 이력 {available, model, toolChange: add|remove}
  - assistant content 의 server_tool_use(name="advisor", input={}) → 호출 1건 (id = srvtoolu_…)
  - assistant content 의 advisor_tool_result.content.type
        advisor_result            → 평문 조언(text). Opus 4.8 등 일부 advisor 만
        advisor_redacted_result   → 암호화(encrypted_content). Opus 5/5.5·Fable·Sonnet 5.5 advisor. 본문을 읽을 수 없다
        advisor_tool_result_error → 실패(error_code)
  - message.usage.iterations[] 중 type == "advisor_message" → advisor 토큰(model, input/output/cache_*)
    top-level usage 에는 advisor 토큰이 합산되지 않는다(공식 API 문서).
  - 같은 assistant 메시지가 content 블록마다 레코드로 쪼개져 usage 가 반복 기록된다 → message.id 로 중복 제거.
  - api-request-blob / api-request-shape 레코드는 요청 사본이므로 세지 않는다.

조언 본문이 암호화돼 있으면 "유용했나"는 자동으로 알 수 없다. 대신
  (1) 호출 직후 메인이 한 일(다음 사람 메시지 전까지의 도구 호출, 첫 텍스트 앞부분)을 보여 주고
  (2) --ledger 로 사람이 적은 판정(useful|partial|noise|harmful)을 합친다.

사용:
  advisor-stats.py <session.jsonl>...            # 세션 파일(같은 이름 폴더의 subagents/*.jsonl 도 자동 포함)
  advisor-stats.py --session <uuid>              # ~/.claude/projects/*/<uuid>.jsonl
  advisor-stats.py --all                         # ~/.claude/projects 전체(advisor 흔적이 있는 파일만 파싱)
  옵션: --json, --ledger FILE.tsv (srvtoolu_id<TAB>verdict<TAB>note), --subagent-costs, --no-subagents
비용은 API 정가 환산(아래 PRICES)이다. 구독 플랜에서는 달러가 아니라 사용량 한도로 차감된다.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import statistics
import sys
from pathlib import Path

# $/MTok. claude-api 스킬 표(2026-10-06 캐시) 기준. cache write 는 표준 배수(5m 1.25x, 1h 2x) 가정.
# 표에 없는 모델은 None → 비용 칸을 비운다(추측하지 않는다).
PRICES = {
    "claude-opus-5-5": {"in": 4.0, "out": 20.0, "cr": 0.20},
    "claude-opus-5": {"in": 5.0, "out": 25.0, "cr": 0.50},
    "claude-sonnet-5-5": {"in": 2.0, "out": 10.0, "cr": 0.20},
    "claude-sonnet-5": {"in": 2.0, "out": 10.0, "cr": 0.20},
    "claude-fable-5-1": {"in": 10.0, "out": 50.0, "cr": 0.25},
    "claude-haiku-5-5": {"in": 0.10, "out": 0.50, "cr": 0.01},
}
VERDICTS = ("useful", "partial", "noise", "harmful")


def price(model: str | None):
    if not model:
        return None
    for k in sorted(PRICES, key=len, reverse=True):  # claude-opus-5-5 가 claude-opus-5 보다 먼저
        if model.startswith(k):
            return PRICES[k]
    return None


def cost(model, inp=0, out=0, cr=0, cw5=0, cw1h=0):
    p = price(model)
    if p is None:
        return None
    return (inp * p["in"] + out * p["out"] + cr * p["cr"] + cw5 * p["in"] * 1.25 + cw1h * p["in"] * 2.0) / 1e6


def projects_dir() -> Path:
    base = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude")
    return Path(base) / "projects"


def expand_inputs(args) -> list[Path]:
    files: list[Path] = []
    if args.all:
        files = [Path(p) for p in glob.glob(str(projects_dir() / "**" / "*.jsonl"), recursive=True)]
    if args.session:
        files += [Path(p) for p in glob.glob(str(projects_dir() / "*" / f"{args.session}.jsonl"))]
    files += [Path(p) for p in args.paths]
    out: list[Path] = []
    for f in files:
        out.append(f)
        sub = f.with_suffix("") / "subagents"
        if not args.all and not args.no_subagents and sub.is_dir():
            out += sorted(sub.glob("*.jsonl"))
    seen, uniq = set(), []
    for f in out:
        if f not in seen:
            seen.add(f); uniq.append(f)
    return uniq


def has_advisor(path: Path) -> bool:
    """파싱 전에 바이트로 거른다(수백 MB 트랜스크립트 대비)."""
    try:
        with open(path, "rb") as g:
            for chunk in iter(lambda: g.read(1 << 22), b""):
                if b"advisor_tool_result" in chunk or b'"advisor_tool"' in chunk:
                    return True
    except OSError:
        return False
    return False


def text_head(content, n=240) -> str:
    if isinstance(content, list):
        for b in content:
            if isinstance(b, dict) and b.get("type") == "text" and b.get("text", "").strip():
                return " ".join(b["text"].split())[:n]
    return ""


def is_human(o: dict) -> bool:
    """다음 '사람' 메시지인가(도구 결과·하위 보고·리마인더 제외). session-log extract.classify 와 같은 기준의 축약판."""
    if o.get("type") == "attachment":
        a = o.get("attachment") or {}
        return a.get("type") == "queued_command" and (a.get("origin") or {}).get("kind") == "human"
    if o.get("type") != "user" or o.get("isMeta") or o.get("isCompactSummary"):
        return False
    og = o.get("origin") or {}
    if isinstance(og, dict) and og.get("kind") not in (None, "human"):
        return False
    c = (o.get("message") or {}).get("content")
    if isinstance(c, str):
        return not c.lstrip().startswith(("<", "Caveat:", "This session is being continued"))
    return False


def scan(path: Path) -> dict:
    calls: dict[str, dict] = {}
    order: list[str] = []
    toggles: list[dict] = []
    usage_by_msg: dict[str, list[dict]] = {}
    msg_of_call: dict[str, str] = {}
    open_calls: list[str] = []  # 결과 뒤 '다음 사람 메시지'까지 활동을 모으는 중인 호출
    is_sub = path.parent.name == "subagents"
    with open(path, encoding="utf-8", errors="replace") as g:
        for ln, line in enumerate(g, 1):
            try:
                o = json.loads(line)
            except ValueError:
                continue
            t = o.get("type")
            if t in ("api-request", "api-request-blob", "api-request-shape"):
                continue
            if open_calls and is_human(o):
                open_calls.clear()
            if t == "attachment":
                a = o.get("attachment") or {}
                if a.get("type") == "advisor_tool":
                    toggles.append({"line": ln, "ts": o.get("timestamp"), "available": a.get("available"),
                                    "model": a.get("model"), "change": a.get("toolChange")})
                continue
            if t != "assistant":
                continue
            m = o.get("message") or {}
            content = m.get("content") if isinstance(m.get("content"), list) else []
            mid = m.get("id") or o.get("requestId") or f"L{ln}"
            it = (m.get("usage") or {}).get("iterations") or []
            adv_iters = [x for x in it if isinstance(x, dict) and x.get("type") == "advisor_message"]
            if adv_iters and mid not in usage_by_msg:
                first = next((x for x in it if x.get("type") == "message"), {})
                ctx = sum(first.get(k, 0) or 0 for k in ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"))
                usage_by_msg[mid] = [dict(x, _main_ctx=ctx) for x in adv_iters]
            for b in content:
                if not isinstance(b, dict):
                    continue
                bt = b.get("type")
                if bt == "server_tool_use" and b.get("name") == "advisor":
                    cid = b.get("id") or f"L{ln}"
                    if cid not in calls:
                        calls[cid] = {"id": cid, "file": str(path), "subagent": is_sub, "line": ln, "ts": o.get("timestamp"),
                                      "main_model": m.get("model"), "advisor_model_field": o.get("advisorModel"),
                                      "result": None, "error_code": None, "after_tools": {}, "after_text": ""}
                        order.append(cid)
                        msg_of_call[cid] = mid
                elif bt == "advisor_tool_result":
                    cid = b.get("tool_use_id")
                    c = b.get("content") or {}
                    if cid in calls and calls[cid]["result"] is None:
                        calls[cid]["result"] = c.get("type")
                        calls[cid]["error_code"] = c.get("error_code")
                        if c.get("type") == "advisor_result":
                            calls[cid]["advice_text"] = (c.get("text") or "")[:2000]
                        calls[cid]["_result_line"] = ln
                        open_calls.append(cid)
                elif bt == "tool_use" and open_calls:
                    for cid in open_calls:
                        d = calls[cid]["after_tools"]
                        d[b.get("name")] = d.get(b.get("name"), 0) + 1
            if open_calls:
                h = text_head(content)
                for cid in open_calls:
                    if h and not calls[cid]["after_text"] and ln > calls[cid].get("_result_line", 0):
                        calls[cid]["after_text"] = h
    # 토큰 배정: 한 메시지에 advisor 호출이 여럿이면 iterations 순서대로 짝짓는다.
    by_msg: dict[str, list[str]] = {}
    for cid in order:
        by_msg.setdefault(msg_of_call[cid], []).append(cid)
    for mid, cids in by_msg.items():
        its = usage_by_msg.get(mid, [])
        for i, cid in enumerate(cids):
            x = its[i] if i < len(its) else None
            c = calls[cid]
            if x is None:  # usage.iterations 에 advisor_message 가 없다(구버전 서브에이전트 기록 등) → 토큰 미기록
                c.update({"advisor_model": None, "adv_in": None, "adv_out": None, "main_ctx": None, "usd": None})
                continue
            cc = x.get("cache_creation") or {}
            c.update({"advisor_model": x.get("model"), "adv_in": x.get("input_tokens", 0) or 0,
                      "adv_out": x.get("output_tokens", 0) or 0, "adv_cache_read": x.get("cache_read_input_tokens", 0) or 0,
                      "adv_cache_write": x.get("cache_creation_input_tokens", 0) or 0, "main_ctx": x.get("_main_ctx", 0)})
            c["usd"] = cost(c["advisor_model"], c["adv_in"], c["adv_out"], c["adv_cache_read"],
                            cc.get("ephemeral_5m_input_tokens", 0) or 0, cc.get("ephemeral_1h_input_tokens", 0) or 0)
            c.pop("_result_line", None)
    return {"file": str(path), "calls": [calls[c] for c in order], "toggles": toggles}


def subagent_costs(files: list[Path]) -> list[dict]:
    """비교용: 서브에이전트 트랜스크립트 하나당 총비용(API 정가 환산). advisor 반복 호출 비용과 견주는 데 쓴다."""
    rows = []
    for f in files:
        if f.parent.name != "subagents":
            continue
        seen, tot, model, agent_type = set(), 0.0, None, None
        meta = f.with_suffix(".meta.json")
        if meta.is_file():
            try:
                agent_type = json.loads(meta.read_text()).get("agentType")
            except (OSError, ValueError):
                pass
        unknown = False
        with open(f, encoding="utf-8", errors="replace") as g:
            for line in g:
                if '"assistant"' not in line:
                    continue
                try:
                    o = json.loads(line)
                except ValueError:
                    continue
                if o.get("type") != "assistant":
                    continue
                m = o.get("message") or {}
                mid = m.get("id")
                if not mid or mid in seen:
                    continue
                seen.add(mid)
                u = m.get("usage") or {}
                model = m.get("model") or model
                cc = u.get("cache_creation") or {}
                c = cost(model, u.get("input_tokens", 0) or 0, u.get("output_tokens", 0) or 0,
                         u.get("cache_read_input_tokens", 0) or 0, cc.get("ephemeral_5m_input_tokens", 0) or 0,
                         cc.get("ephemeral_1h_input_tokens", 0) or 0)
                if c is None:
                    unknown = True
                else:
                    tot += c
                for x in u.get("iterations") or []:  # 서브에이전트가 물려받은 advisor 비용도 더한다
                    if isinstance(x, dict) and x.get("type") == "advisor_message":
                        ac = cost(x.get("model"), x.get("input_tokens", 0) or 0, x.get("output_tokens", 0) or 0,
                                  x.get("cache_read_input_tokens", 0) or 0)
                        tot += ac or 0
        rows.append({"file": f.name, "agent_type": agent_type, "model": model, "turns": len(seen),
                     "usd": None if unknown and tot == 0 else round(tot, 3)})
    return rows


def fmt(n) -> str:
    return "?" if n is None else f"{n:,}"


def load_ledger(path: str | None) -> dict:
    out = {}
    if not path:
        return out
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) >= 2 and parts[1] in VERDICTS:
            out[parts[0]] = {"verdict": parts[1], "note": parts[2] if len(parts) > 2 else ""}
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--session")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--no-subagents", action="store_true")
    ap.add_argument("--ledger")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--subagent-costs", action="store_true")
    args = ap.parse_args()
    files = expand_inputs(args)
    if not files:
        ap.error("입력 트랜스크립트가 없다")
    ledger = load_ledger(args.ledger)
    results = [scan(f) for f in files if has_advisor(f)]
    calls = [c for r in results for c in r["calls"]]
    for c in calls:
        if c["id"] in ledger:
            c.update(ledger[c["id"]])
    summary = {
        "files_scanned": len(files), "files_with_advisor": len(results),
        "calls": len(calls), "subagent_calls": sum(1 for c in calls if c["subagent"]),
        "results": {}, "adv_input_tokens": sum(c.get("adv_in") or 0 for c in calls),
        "adv_output_tokens": sum(c.get("adv_out") or 0 for c in calls),
        "calls_without_usage": sum(1 for c in calls if c.get("adv_in") is None),
        "usd_api_equiv": round(sum(c.get("usd") or 0 for c in calls), 3),
        "verdicts": {},
    }
    for c in calls:
        summary["results"][c["result"] or "none"] = summary["results"].get(c["result"] or "none", 0) + 1
        if c.get("verdict"):
            summary["verdicts"][c["verdict"]] = summary["verdicts"].get(c["verdict"], 0) + 1
    sub = subagent_costs(files) if args.subagent_costs else []
    if args.json:
        json.dump({"summary": summary, "calls": calls, "toggles": {r["file"]: r["toggles"] for r in results},
                   "subagent_costs": sub}, sys.stdout, ensure_ascii=False, indent=1)
        print()
        return 0
    s = summary
    print(f"파일 {s['files_scanned']}개 중 advisor 흔적 {s['files_with_advisor']}개 · 호출 {s['calls']}건(서브에이전트 {s['subagent_calls']}건)")
    print(f"결과: {s['results']} (none = 결과 블록 없음, 중단 추정) · 토큰 미기록 {s['calls_without_usage']}건 · advisor 입력 {s['adv_input_tokens']:,} / 출력 {s['adv_output_tokens']:,} 토큰 · API 환산 ${s['usd_api_equiv']}")
    if s["verdicts"]:
        print(f"사람 판정: {s['verdicts']}")
    for r in results:
        for tg in r["toggles"]:
            print(f"  토글 {Path(r['file']).name[:12]} L{tg['line']} {tg['ts']} {tg['change']} {tg['model']} available={tg['available']}")
    print()
    print("| 시각 | 위치 | main→advisor | 메인 맥락 | adv 입력/출력 | $ | 결과 | 직후 도구 | 직후 첫 텍스트 | 판정 |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for c in calls:
        where = ("sub:" if c["subagent"] else "") + Path(c["file"]).stem[:14]
        tools = ",".join(f"{k}×{v}" for k, v in sorted(c["after_tools"].items(), key=lambda x: -x[1])[:4])
        usd = f"{c['usd']:.2f}" if c.get("usd") is not None else "?"
        res = c["result"] + (f"({c['error_code']})" if c.get("error_code") else "") if c["result"] else "none"
        print(f"| {(c['ts'] or '')[:16]} | {where} | {c['main_model']}→{c.get('advisor_model')} | {fmt(c.get('main_ctx'))} | "
              f"{fmt(c.get('adv_in'))}/{fmt(c.get('adv_out'))} | {usd} | {res} | {tools} | {c['after_text'][:80]} | {c.get('verdict', '')} |")
    if sub:
        vals = [r["usd"] for r in sub if r["usd"] is not None]
        print()
        if vals:
            vals.sort()
            print(f"서브에이전트 {len(sub)}개 비용(API 환산): 중앙 ${statistics.median(vals):.2f} · p90 ${vals[int(len(vals) * 0.9)]:.2f} · 최대 ${vals[-1]:.2f}")
        by_model: dict = {}
        for r in sub:
            if r["usd"] is not None:
                by_model.setdefault(r["model"], []).append(r["usd"])
        for k, v in by_model.items():
            print(f"  {k}: {len(v)}개, 중앙 ${statistics.median(v):.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
