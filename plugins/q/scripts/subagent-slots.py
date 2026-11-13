#!/usr/bin/env python3
"""서브에이전트 고지·슬롯 훅. 한 파일이 이벤트 이름으로 나눠 처리한다.

등록(q 플러그인 hooks/hooks.json): PreToolUse(Agent|Workflow), PostToolUse(모든 도구), SubagentStart, SubagentStop, Stop.
설계: .claude/audit/21-cost-disclosure.md. 원장: subagent_ledger.py(같은 디렉터리). 메시지 규약: HOOK-MESSAGES.md.

- attended(기본): 막지 않는다. 큰 팬아웃(동시 N 개 이상, opus 이상 M 개 이상, Workflow)이면 warn 으로
  "사용자에게 규모를 고지하라"를 낸다. 팬아웃 한 묶음(실행 중 0 에서 시작해 다시 0 이 될 때까지)마다·compact 회차마다 한 번.
- away(사용자가 /q:away 로 선언): 실행 중 수가 슬롯 이상이면 deny(사유 "queue: …", level=action). 세션은 멈추지 않는다.
  예산을 넘기면(1단계) 슬롯을 HARNESS_AWAY_OVER_SLOTS(기본 1)로 줄여 직렬화하고, 메인에 재고 리마인더를 한 번 준다.
  예산의 2배를 넘으면(2단계) 새 Agent·Workflow 를 모두 deny(`halt: …`, level=action): 진척 파일에 상태를 적고 사용자를 기다리라는 지시.
  메인을 강제로 끊지는 않는다. 메인이 서브에이전트 없이 혼자 일해도 PostToolUse(모든 도구)에서 같은 안내(1단계 warn, 2단계 action)를 한 번 받는다(main_notice).
  평소(away 아님)에는 상태 파일을 열어 away.on 만 보고 즉시 끝난다(원장 모듈을 적재하지 않는다).
  예산 단위는 USD·에이전트 수·한도 %(statusline 이 쓴 <sid>.limits.json 을 읽는다).
- 세는 법: PreToolUse 에서 예약(+1) → PostToolUse(async_launched)·SubagentStart 에서 실행 중으로 → SubagentStop 에서 −1.
  어긋남 복구: subagent_ledger.live() (background_tasks, meta.json, 트랜스크립트 mtime, 예약 TTL). 수동: /q:away reset.
끄기: HARNESS_SUBAGENT_SLOTS=off. 실패해도 아무것도 막지 않는다(예외는 삼킨다).
"""
import os
import sys

MAIN_EVAL_SEC = 15  # away 중 메인 단독 안내: 트랜스크립트 증분 읽기 간격
# json·re·importlib·pathlib·time 은 느려서(실측 합 약 15 ms) 모든 도구의 PostToolUse 가 지나가는 길에서는 적재하지 않는다. 필요한 길에서 _late() 가 적재한다.
json = re = importlib = time = Path = HOME = None


def _late():
    global json, re, importlib, time, Path, HOME
    import json as _j
    import re as _r
    json, re = _j, _r
    import importlib.util  # noqa: F401  (global importlib 에 묶인다)
    import time as _t
    from pathlib import Path as _P
    time, Path = _t, _P
    HOME = _P(os.environ.get("CLAUDE_CONFIG_DIR") or _P.home() / ".claude")  # 사용자 정의 에이전트(agents/) 위치


BUILTIN = {"general-purpose", "fork", "Explore", "Plan", "claude", "statusline-setup", "claude-code-guide"}


def load_ledger():
    spec = importlib.util.spec_from_file_location("subagent_ledger", Path(__file__).resolve().with_name("subagent_ledger.py"))
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
                            f"queue: wait for a running agent to finish, then spawn the next. Away mode is on (the user declared /q:away): "
                            f"{n} subagents running ({fams_text(L, items)}), slot limit {limit}.{why} This call did not run; the session is not stopped. "
                            f"Do not retry until a completion notification arrives; meanwhile do non-agent work or end the turn. "
                            f"Before respawning, check whether a smaller model (sonnet) or a smaller pass would do."))
        if over and st["notes"].get(f"over:{who}") != f"{ep}:{away.get('since')}":
            st["notes"][f"over:{who}"] = f"{ep}:{away.get('since')}"
            out = context(tag("warn",
                              f"Away budget reached ({over}). Subagents are now serialized ({limit} at a time); nothing is stopped. "
                              f"Before each further spawn, consider: can an agent you already have be resumed (SendMessage) instead of a new one; "
                              f"can a lighter model do it where a mistake is cheap; is the remaining work worth the spend. "
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
                              f"Several subagents at once: with this call {after} run ({mix}; opus-or-above: {big}). Not blocked. "
                              f"If you have not yet, tell the user in one line: how many, which models, why, and the expected size. "
                              f"Independent parts in parallel are fine. If several of them cover the same code or question, consider one "
                              f"agent working in small steps instead, reviewed between steps and resumed with SendMessage: it keeps what "
                              f"it has read (its cache lasts about an hour) and corrects itself from concrete counter-evidence."))
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


def quick_not_away(raw):
    """모든 도구의 PostToolUse 가 지나가는 길. json 을 적재하기 전에 원문에서 session_id 만 뽑아 상태 파일의 away.on 을 본다.
    '확실히 away 가 아님'일 때만 True(그대로 종료). 조금이라도 불확실하면 False 라 정상 경로가 판단한다.
    상태 파일 위치는 subagent_ledger.state_path 와 같은 규칙(테스트가 일치를 확인한다)."""
    if '"PostToolUse"' not in raw or '"Agent"' in raw or '"Task"' in raw:
        return False
    i = raw.find('"session_id"')
    if i < 0:
        return False
    j = raw.find('"', raw.find(":", i) + 1)
    k = raw.find('"', j + 1)
    if j < 0 or k < 0:
        return False
    sid = "".join(c for c in raw[j + 1:k] if c.isalnum() or c in "_-") or "nosession"
    tmp = os.environ.get("TMPDIR") or os.environ.get("TEMP") or os.environ.get("TMP") or "/tmp"  # tempfile.gettempdir() 와 같은 순서
    try:
        with open(os.path.join(tmp, "claude-subagent-slots", sid + ".json")) as f:
            return '"on": true' not in f.read()  # 싼 거름: away 가 켜진 상태 파일만 정상 경로로 보낸다
    except OSError:
        return True


def main_notice(L, st, data, cfg, now):
    """away 중 메인(agent_id 없음)이 서브에이전트 없이 일할 때 받는 안내. 도구 호출마다 불린다.
    트랜스크립트 읽기(account_main)는 MAIN_EVAL_SEC 초에 한 번만. 안내는 (호출한 쪽, 회차, away 선언)당 한 번이고
    pre_agent·stage2_deny 와 같은 notes 키를 써서, 이미 받았으면 거기서는 짧게/조용히 지나간다."""
    if data.get("agent_id") or not (st.get("away") or {}).get("on"):
        return None
    if now - st.get("main_eval", 0) >= MAIN_EVAL_SEC:
        st["main_eval"] = now
        L.account_main(st, data.get("transcript_path"))
    away = st["away"]
    ev = L.away_check(st, cfg, L.read_limits(data.get("session_id")), now)
    if not ev or ev["level"] < 1:
        return None
    key = f"{L.epoch(data.get('session_id'))}:{away.get('since')}"
    if ev["level"] >= 2:
        if st["notes"].get("stage2:main") == key:
            return None
        st["notes"]["stage2:main"] = key
        st["notes"]["over:main"] = key
        L.log(st, "stage2-main-notice")
        return post_context(tag("action",
                                f"halt: the away budget's stage 2 is reached ({ev['why']}). New subagents and workflows are refused until the user returns; "
                                f"you are working on your own, so nothing else is stopped. Write the current state to the progress file (or the session notes) now: "
                                f"what is done, what is running, what is next, and what needs the user's decision. Then wait for the user; "
                                f"finish the small step in hand but start no new large work."))
    if st["notes"].get("over:main") == key:
        return None
    st["notes"]["over:main"] = key
    L.log(st, "over-main-notice")
    return post_context(tag("warn",
                            f"Away budget reached ({ev['why']}). Nothing is stopped. If you spawn subagents they now run {away.get('over_slots', 1)} at a time. "
                            f"Reconsider whether the remaining work is worth the spend, prefer small steps over large new work, and mention this in your next report to the user."))


def post_context(text):
    return {"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": text}}


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


def post_tool(L, st, data, cfg, now):
    """PostToolUse(모든 도구): Agent·Task 는 먼저 원장을 갱신하고, 그다음 메인이면 away 안내를 본다."""
    if data.get("tool_name") in ("Agent", "Task"):
        post_agent(L, st, data, cfg, now)
    return main_notice(L, st, data, cfg, now)


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
    ("PostToolUse", None): post_tool,
    ("SubagentStart", None): subagent_start,
    ("SubagentStop", None): subagent_stop,
    ("Stop", None): stop,
}


def main():
    raw = sys.stdin.read()
    if quick_not_away(raw) or os.environ.get("HARNESS_SUBAGENT_SLOTS", "").lower() in ("off", "0", "no") and '"PostToolUse"' in raw:
        return 0
    _late()
    try:
        data = json.loads(raw)
    except Exception:
        return 0
    ev = data.get("hook_event_name")
    fn = HANDLERS.get((ev, data.get("tool_name"))) or HANDLERS.get((ev, None))
    if not fn:
        return 0
    if ev == "PostToolUse" and data.get("tool_name") not in ("Agent", "Task"):
        # 서브에이전트 안의 호출은 안내 대상이 아니다(메인만)
        if data.get("agent_id"):
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
