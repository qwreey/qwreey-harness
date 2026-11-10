#!/usr/bin/env python3
"""서브에이전트 고지·슬롯 훅. 한 파일이 이벤트 이름으로 나눠 처리한다.

등록(settings.json): PreToolUse(Agent|Workflow), PostToolUse(Agent), SubagentStart, SubagentStop, Stop.
설계: audit/21-cost-disclosure.md. 원장: lib/subagent_ledger.py. 메시지 규약: HOOK-MESSAGES.md.

- attended(기본): 막지 않는다. 큰 팬아웃(동시 N 개 이상, opus 이상 M 개 이상, Workflow)이면 warn 으로
  "사용자에게 규모를 고지하라"를 낸다. 팬아웃 한 묶음(실행 중 0 에서 시작해 다시 0 이 될 때까지)마다·compact 회차마다 한 번.
- away(사용자가 /away 로 선언): 실행 중 수가 슬롯 이상이면 deny(사유 "queue: …", level=action). 세션은 멈추지 않는다.
  예산을 넘기면(1단계) 슬롯을 HARNESS_AWAY_OVER_SLOTS(기본 1)로 줄여 직렬화하고, 메인에 재고 리마인더를 한 번 준다.
  예산의 2배를 넘으면(2단계) 새 Agent·Workflow 를 모두 deny(`halt: …`, level=action): 진척 파일에 상태를 적고 사용자를 기다리라는 지시.
  메인을 강제로 끊지는 않는다. 예산 단위는 USD·에이전트 수·한도 %(statusline 이 쓴 <sid>.limits.json 을 읽는다).
- 세는 법: PreToolUse 에서 예약(+1) → PostToolUse(async_launched)·SubagentStart 에서 실행 중으로 → SubagentStop 에서 −1.
  어긋남 복구: lib/subagent_ledger.live() (background_tasks, meta.json, 트랜스크립트 mtime, 예약 TTL). 수동: /away reset.
끄기: HARNESS_SUBAGENT_SLOTS=off. 실패해도 아무것도 막지 않는다(예외는 삼킨다).
"""
import importlib.util
import json
import os
import re
import sys
import time
from pathlib import Path

HOME = Path(__file__).resolve().parent.parent
BUILTIN = {"general-purpose", "fork", "Explore", "Plan", "claude", "statusline-setup", "claude-code-guide"}


def load_ledger():
    spec = importlib.util.spec_from_file_location("subagent_ledger", HOME / "lib" / "subagent_ledger.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def tag(level, body):
    return f'<harness-hook name="subagent-slots" level="{level}">\n{body}\n</harness-hook>'


def context(text):
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": text}}


def deny(text):
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": text}}


def agent_model(name, cwd):
    """사용자 정의 에이전트 frontmatter 의 model (없으면 None)."""
    for d in (Path(cwd or ".") / ".claude" / "agents", HOME / "agents"):
        if not d.is_dir():
            continue
        for p in d.glob("*.md"):
            try:
                head = p.read_text(encoding="utf-8")[:2000]
            except OSError:
                continue
            fm = re.match(r"---\n(.*?)\n---", head, re.S)
            if not fm:
                continue
            nm = re.search(r"^name:\s*['\"]?([^'\"\n]+)", fm.group(1), re.M)
            if (nm.group(1).strip() if nm else p.stem) == name:
                mm = re.search(r"^model:\s*['\"]?([^'\"\n]+)", fm.group(1), re.M)
                return mm.group(1).strip() if mm else None
    return None


def spawn_family(L, ti, st, cwd):
    m = (ti.get("model") or "").strip()
    if not m or m == "inherit":
        typ = ti.get("subagent_type") or ""
        if typ and typ not in BUILTIN and ":" not in typ:
            m = agent_model(typ, cwd) or ""
    if not m or m == "inherit":
        m = (st.get("main") or {}).get("model") or ""
    return L.family(m)


def fams_text(L, items):
    return ", ".join(f"{f} {n}" for f, n in L.by_family(items).items()) or "unknown models"


def stage2_deny(L, st, away, ep, who, ev, kind):
    """2단계: 새 서브에이전트·Workflow 를 모두 거절한다. 전체 지시는 회차(compact)·away 선언마다 한 번, 이후는 짧게."""
    away["queued"] = away.get("queued", 0) + 1
    L.log(st, "stage2-deny", kind=kind)
    key = f"{ep}:{away.get('since')}"
    if st["notes"].get(f"stage2:{who}") != key:
        st["notes"][f"stage2:{who}"] = key
        return deny(tag("action",
                        f"halt: the away budget's stage 2 is reached ({ev['why']}); new subagents and workflows are refused until the user returns. "
                        f"This call did not run. Do not retry or work around it. Write the current state to the progress file "
                        f"(or the session notes): what is done, what is running, what is next, and what needs the user's decision. "
                        f"Then wait for the user; the session itself is not stopped, so you may finish the small step in hand but start no new large work."))
    return deny(tag("action", "halt: away budget stage 2 still in effect; no new subagents or workflows. "
                              "Keep the progress file current and wait for the user."))


def pre_agent(L, st, data, cfg, now):
    ti = data.get("tool_input") or {}
    sid = data.get("session_id")
    fam = spawn_family(L, ti, st, data.get("cwd"))
    items = L.live(st, cfg, now)
    n = len(items)
    if n == 0:
        st["burst"] = st.get("burst", 0) + 1
    ep = L.epoch(sid)
    who = data.get("agent_id") or "main"  # dedup 은 (세션, 호출한 쪽, 회차): 서브에이전트 안의 중첩 호출이 메인의 "한 번"을 쓰지 않게
    out = None
    away = st.get("away") if (st.get("away") or {}).get("on") else None
    if away:
        ev = L.away_check(st, cfg, L.read_limits(sid), now)
        over = ev["why"]
        if ev["level"] >= 2:
            return stage2_deny(L, st, away, ep, who, ev, "agent")
        limit = away.get("over_slots", 1) if over else away.get("slots", 2)
        if n >= limit:
            away["queued"] = away.get("queued", 0) + 1
            L.log(st, "queued", n=n, limit=limit, fam=fam)
            why = f" The away budget is used up ({over}), so subagents now run {limit} at a time." if over else ""
            return deny(tag("action",
                            f"queue: wait for a running agent to finish, then spawn the next. Away mode is on (the user declared /away): "
                            f"{n} subagents running ({fams_text(L, items)}), slot limit {limit}.{why} This call did not run; the session is not stopped. "
                            f"Do not retry until a completion notification arrives; meanwhile do non-agent work or end the turn. "
                            f"Before respawning, check whether a smaller model (sonnet) or a smaller pass would do."))
        if over and st["notes"].get(f"over:{who}") != f"{ep}:{away.get('since')}":
            st["notes"][f"over:{who}"] = f"{ep}:{away.get('since')}"
            out = context(tag("warn",
                              f"Away budget reached ({over}). Subagents are now serialized ({limit} at a time); nothing is stopped. "
                              f"Before each further spawn, reconsider: can sonnet do it instead of opus/fable; can the work be a small "
                              f"find -> review -> fix -> review pass instead of a fan-out; is the remaining work worth the spend. "
                              f"Mention this in your next report to the user."))
    else:
        after = n + 1
        big = sum(1 for r in items if r.get("fam") in L.BIG) + (1 if fam in L.BIG else 0)
        conc_lim = L.num(cfg, "HARNESS_FANOUT_WARN_CONCURRENT", int)
        big_lim = L.num(cfg, "HARNESS_FANOUT_WARN_BIG", int)
        key = f"{ep}:{st['burst']}"
        if (after >= conc_lim or big >= big_lim) and st["notes"].get(f"fanout:{who}") != key:
            st["notes"][f"fanout:{who}"] = key
            L.log(st, "fanout-warn", n=after, big=big)
            mix = fams_text(L, items + [{"fam": fam}])
            out = context(tag("warn",
                              f"Large fan-out: with this call {after} subagents run at once ({mix}; opus-or-above: {big}). Not blocked. "
                              f"Tell the user in one line now: how many agents, which models, why, and the expected size (files, rounds). "
                              f"Unless speed matters, prefer small sequential passes (one finder, then a reviewer, fix, review again): "
                              f"parallel agents re-read the same code, and the fixes need another review anyway. "
                              f"Match the model to the task size (sonnet for search and mechanical work)."))
    st["reserved"][data.get("tool_use_id") or f"anon-{now}"] = {
        "t": now, "fam": fam, "type": ti.get("subagent_type") or "general-purpose", "bg": bool(ti.get("run_in_background", True)), "kind": "agent"}
    st["spawned"] = st.get("spawned", 0) + 1
    L.log(st, "spawn", fam=fam, type=ti.get("subagent_type"))
    return out


def pre_workflow(L, st, data, cfg, now):
    items = L.live(st, cfg, now)
    n = len(items)
    away = st.get("away") if (st.get("away") or {}).get("on") else None
    out = None
    if away:
        ev = L.away_check(st, cfg, L.read_limits(data.get("session_id")), now)
        if ev["level"] >= 2:
            return stage2_deny(L, st, away, L.epoch(data.get("session_id")), data.get("agent_id") or "main", ev, "workflow")
        policy = str(cfg.get("HARNESS_AWAY_WORKFLOW", "idle")).strip().lower()
        if policy == "deny":
            away["queued"] = away.get("queued", 0) + 1
            L.log(st, "queued", kind="workflow")
            return deny(tag("action", "Away mode is on and workflows are disabled while away (HARNESS_AWAY_WORKFLOW=deny). "
                                      "Run the stages as sequential Agent calls instead; the session is not stopped."))
        if policy != "allow" and n > 0:
            away["queued"] = away.get("queued", 0) + 1
            L.log(st, "queued", kind="workflow", n=n)
            return deny(tag("action",
                            f"queue: wait for a running agent to finish, then spawn the next. Away mode is on: a workflow fans out beyond "
                            f"the slot limit ({away.get('slots')}), so it may start only when no subagent is running ({n} running now). "
                            f"This call did not run; the session is not stopped. Consider sequential Agent calls instead."))
        out = context(tag("warn", "Away mode: this workflow's internal concurrency is not governed by the slot limit "
                                  "(the runtime allows up to 16 agents at once by default). Keep it small (few agents, sequential stages) "
                                  "and match each stage's model to its size."))
    elif str(cfg.get("HARNESS_FANOUT_WARN_WORKFLOW", "on")).lower() not in ("off", "0", "no"):
        out = context(tag("warn",
                          "Workflow requested: a workflow spawns many subagents (up to 16 at once by default). Not blocked. "
                          "Tell the user in one line now: the phases, agent count, models, why a workflow rather than a few "
                          "sequential agents, and the expected size."))
    st["reserved"][data.get("tool_use_id") or f"anon-{now}"] = {"t": now, "fam": "?", "type": "workflow", "bg": True, "kind": "workflow"}
    L.log(st, "workflow")
    return out


def post_agent(L, st, data, cfg, now):
    tr = data.get("tool_response") if isinstance(data.get("tool_response"), dict) else {}
    r = st["reserved"].pop(data.get("tool_use_id") or "", None) or {}
    aid = tr.get("agentId")
    if not aid:
        return None
    fam = L.family(tr.get("resolvedModel")) if tr.get("resolvedModel") else r.get("fam", "?")
    if tr.get("status") == "async_launched":
        e = st["running"].setdefault(aid, {"t": now})
        e.update(fam=fam, type=tr.get("agentType") or r.get("type"), bg=True)
    elif tr.get("status") == "completed":
        st["running"].pop(aid, None)
        L.account_agent(st, aid, None)
    return None


def subagent_start(L, st, data, cfg, now):
    aid, typ = data.get("agent_id"), data.get("agent_type") or ""
    if not aid:
        return None
    if aid in st["running"]:
        st["running"][aid]["t"] = now
        return None
    r = None
    meta = L._meta(st, aid) or {}
    if meta.get("toolUseId") in st["reserved"]:
        r = st["reserved"].pop(meta["toolUseId"])
    else:
        wf = typ == "workflow-subagent"
        cands = sorted(((v["t"], k) for k, v in st["reserved"].items()
                        if (v.get("kind") == "workflow") == wf and (wf or v.get("type") == typ)), key=lambda x: x[0])
        if not cands and not wf:
            cands = sorted((v["t"], k) for k, v in st["reserved"].items() if v.get("kind") == "agent")
        if cands:
            r = st["reserved"].pop(cands[0][1])
    fam = (r or {}).get("fam") or (L.family(meta.get("model")) if meta.get("model") else "?")
    st["running"][aid] = {"t": now, "fam": fam, "type": typ, "bg": bool((r or {}).get("bg", False))}
    return None


def subagent_stop(L, st, data, cfg, now):
    aid = data.get("agent_id")
    if aid:
        r = st["running"].pop(aid, None)
        a = L.account_agent(st, aid, data.get("agent_transcript_path"))
        if a is not None:
            a["stopped"] = now
        L.log(st, "stop", id=aid, fam=(r or {}).get("fam"), usd=round((a or {}).get("usd", 0), 4))
    reconcile(L, st, data, cfg, now)
    return None


def stop(L, st, data, cfg, now):
    reconcile(L, st, data, cfg, now)
    return None


def reconcile(L, st, data, cfg, now):
    bg = data.get("background_tasks")
    if isinstance(bg, list):
        grace = {k: v for k, v in st["running"].items() if now - v.get("t", 0) < 10}  # 막 띄운 것은 목록 반영 전일 수 있다
        L.live(st, cfg, now, background=bg)
        st["running"].update(grace)
    else:
        L.live(st, cfg, now)
    L.away_check(st, cfg, L.read_limits(data.get("session_id")), now)  # 1·2단계 도달 시각을 정확히 남긴다


HANDLERS = {
    ("PreToolUse", "Agent"): pre_agent,
    ("PreToolUse", "Task"): pre_agent,
    ("PreToolUse", "Workflow"): pre_workflow,
    ("PostToolUse", "Agent"): post_agent,
    ("PostToolUse", "Task"): post_agent,
    ("SubagentStart", None): subagent_start,
    ("SubagentStop", None): subagent_stop,
    ("Stop", None): stop,
}


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0
    ev = data.get("hook_event_name")
    fn = HANDLERS.get((ev, data.get("tool_name"))) or HANDLERS.get((ev, None))
    if not fn:
        return 0
    try:
        L = load_ledger()
        cfg = L.config(os.environ.get("CLAUDE_PROJECT_DIR") or data.get("cwd"))
        if str(cfg.get("HARNESS_SUBAGENT_SLOTS", "on")).lower() in ("off", "0", "no"):
            return 0
        now = time.time()
        with L.session(data.get("session_id")) as st:
            if not data.get("agent_id") and ev in ("PreToolUse", "Stop"):
                L.account_main(st, data.get("transcript_path"))  # 서브에이전트 안의 훅은 메인 트랜스크립트 offset 을 건드리지 않는다
            out = fn(L, st, data, cfg, now)
            L.sweep(st, now)
    except Exception as e:  # 원장이 깨져도 도구 호출은 막지 않는다
        print(f"subagent-slots: {e}", file=sys.stderr)
        return 0
    if out:
        json.dump(out, sys.stdout, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
