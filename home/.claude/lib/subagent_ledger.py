"""서브에이전트 슬롯·비용 원장 (session_id 단위). 표준 라이브러리만.

쓰는 곳: hooks/subagent-slots.py(기록), statusline/harness-status.py(읽기), skills/away·back(이 파일의 CLI).
설계: audit/21-cost-disclosure.md. 훅 메시지는 HOOK-MESSAGES.md 규약을 따른다.

상태 파일: $TMPDIR/claude-subagent-slots/<sid>.json (+ .lock). compact 회차로 나누지 않는다(실행 중 수는 compact 와 무관).
알림 dedup 만 키에 회차를 넣는다(lib/compact_epoch.py).

실측(2026-11-10, claude 2.1.316, audit/21 §1):
- PreToolUse(Agent) tool_input: description, prompt, subagent_type, model(별칭), run_in_background, isolation.
- 백그라운드: PostToolUse(Agent) 가 먼저 status=async_launched·agentId 로 오고, 그 다음 SubagentStart. 끝날 때 SubagentStop.
- 포그라운드: SubagentStart → SubagentStop → PostToolUse(status=completed).
- Workflow tool_input 은 {script}. 워크플로 안의 에이전트도 SubagentStart/Stop(agent_type=workflow-subagent)을 낸다.
- SubagentStop·Stop 의 background_tasks 는 실행 중인 백그라운드 작업 목록(id = agent_id)이다. 복구에 쓴다.
- 트랜스크립트 usage 는 같은 message.id 의 줄마다 같다 → id 당 한 번 센다. 이렇게 낸 값이 -p 의 total_cost_usd 와 일치했다.
"""
import fcntl
import glob
import importlib.util
import json
import os
import re
import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path

HOME = Path(__file__).resolve().parent.parent
NS = "claude-subagent-slots"

# 공식 가격(USD / MTok): https://platform.claude.com/docs/en/about-claude/pricing (2026-11-10 열람)
# (모델 id 정규식, 입력, 5분 캐시 쓰기, 1시간 캐시 쓰기, 캐시 읽기, 출력). 위에서부터 첫 일치.
PRICES = [
    (r"fable-5-2|mythos-5-2", 8, 10, 16, 0.20, 40),
    (r"fable-5-1|mythos-5-1", 10, 12.5, 20, 0.25, 50),
    (r"fable-5|mythos", 10, 12.5, 20, 1.0, 50),
    (r"opus-5-5", 4, 5, 8, 0.20, 20),
    (r"opus-4-1|opus-4-2025", 15, 18.75, 30, 1.5, 75),
    (r"opus", 5, 6.25, 10, 0.5, 25),
    (r"sonnet-5-5", 2, 2.5, 4, 0.10, 10),
    (r"sonnet-5", 2, 2.5, 4, 0.20, 10),
    (r"sonnet", 3, 3.75, 6, 0.30, 15),
    (r"haiku-5-5", 0.10, 0.125, 0.20, 0.01, 0.50),  # 프롬프트 10만 초과는 아래 HAIKU55_LONG
    (r"haiku", 1, 1.25, 2, 0.10, 5),
]
HAIKU55_LONG = (0.50, 0.625, 1.0, 0.05, 2.50)
FAST_MULT = 2.0  # fast mode 표: Opus 5.5 $8/$40 = 기본의 2배 (Fable 5.2, Opus 5 도 2배)
GEO_US_MULT = 1.1  # inference_geo=us

ORDER = ("fable", "opus", "sonnet", "haiku")  # 비싼 순
BIG = ("fable", "opus")  # "opus 이상"

CFG_DEFAULTS = {
    "HARNESS_SUBAGENT_SLOTS": "on",  # off 면 훅이 아무것도 하지 않는다
    "HARNESS_FANOUT_WARN_CONCURRENT": "4",  # attended: 이 호출로 동시 실행이 N 개 이상이면 warn
    "HARNESS_FANOUT_WARN_BIG": "2",  # attended: opus 이상이 동시에 N 개 이상이면 warn
    "HARNESS_FANOUT_WARN_WORKFLOW": "on",  # attended: Workflow 호출마다 warn
    "HARNESS_AWAY_BUDGET_USD": "20",  # /away 에 예산을 안 주면
    "HARNESS_AWAY_SLOTS": "2",  # /away 에 슬롯을 안 주면
    "HARNESS_AWAY_OVER_SLOTS": "1",  # 예산을 넘긴 뒤 슬롯(직렬화)
    "HARNESS_AWAY_WORKFLOW": "idle",  # away 중 Workflow: idle(실행 중 0 일 때만) | deny | allow
    "HARNESS_SLOTS_STALE_MIN": "30",  # 트랜스크립트가 이만큼 조용한 실행 중 항목은 죽은 것으로 본다
    "HARNESS_SLOTS_RESERVE_SEC": "90",  # PreToolUse 예약이 SubagentStart 없이 이만큼 지나면 버린다
}
CFG_PREFIXES = ("HARNESS_SUBAGENT_", "HARNESS_FANOUT_", "HARNESS_AWAY_", "HARNESS_SLOTS_")


# ---------- 설정 ----------
def _load_mod(name):
    spec = importlib.util.spec_from_file_location(name, HOME / "lib" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def config(project_dir=None):
    """우선순위: 환경 변수 > 저장소 <project>/.claude/harness.env (위 접두 키만) > ~/.claude/harness.env > CFG_DEFAULTS."""
    vals = dict(CFG_DEFAULTS)
    try:
        he = _load_mod("harness_env")
        user = he.load([HOME / "harness.env"])
        vals.update({k: v for k, v in user.items() if k in vals or k.startswith(CFG_PREFIXES)})
        if project_dir:
            repo = Path(project_dir) / ".claude" / "harness.env"
            if repo.is_file():
                for k, v in he.parse(repo.read_text(encoding="utf-8"), vals).items():
                    if k.startswith(CFG_PREFIXES):
                        vals[k] = v
    except Exception:
        pass
    vals.update({k: os.environ[k] for k in list(vals) if k in os.environ})
    return vals


def num(cfg, key, kind=float):
    try:
        return kind(str(cfg.get(key, CFG_DEFAULTS.get(key, "0"))).strip())
    except ValueError:
        return kind(CFG_DEFAULTS.get(key, "0"))


def epoch(sid):
    try:
        return _load_mod("compact_epoch").epoch(sid)
    except Exception:
        return 0


# ---------- 모델·가격 ----------
def family(model):
    m = str(model or "").lower()
    for f in ORDER:
        if f in m or (f == "fable" and "mythos" in m):
            return f
    return "?"


def price_row(model, prompt_tokens=0):
    m = str(model or "").lower()
    for pat, *row in PRICES:
        if re.search(pat, m):
            if pat.startswith("haiku-5-5") and prompt_tokens > 100_000:
                return HAIKU55_LONG
            return tuple(row)
    return None


def usage_usd(model, u):
    """한 API 응답의 usage → USD (목록가). 모르는 모델은 0(호출자가 '?' 로 표시)."""
    cc = u.get("cache_creation") or {}
    w5 = cc.get("ephemeral_5m_input_tokens")
    w1 = cc.get("ephemeral_1h_input_tokens") or 0
    if w5 is None:
        w5 = (u.get("cache_creation_input_tokens") or 0) - w1
    inp, cr, out = u.get("input_tokens") or 0, u.get("cache_read_input_tokens") or 0, u.get("output_tokens") or 0
    row = price_row(model, inp + cr + w5 + w1)
    if not row:
        return 0.0
    p_in, p_w5, p_w1, p_cr, p_out = row
    usd = (inp * p_in + w5 * p_w5 + w1 * p_w1 + cr * p_cr + out * p_out) / 1e6
    if u.get("speed") == "fast":
        usd *= FAST_MULT
    if str(u.get("inference_geo") or "").lower() == "us":
        usd *= GEO_US_MULT
    return usd


def scan(path, offset=0, recent=()):
    """트랜스크립트를 offset 부터 읽어 모델별 {usd, tok} 와 새 offset, 최근 message.id, 마지막 모델을 낸다.
    완결된 줄까지만 읽는다. 같은 message.id 는 한 번만 센다(recent 로 호출 사이 경계도 막는다)."""
    out, seen, last_model = {}, list(recent), None
    try:
        with open(path, "rb") as f:
            f.seek(offset)
            data = f.read()
    except OSError:
        return out, offset, list(recent)[-50:], None
    end = data.rfind(b"\n") + 1
    for line in data[:end].splitlines():
        if b'"usage"' not in line:
            continue
        try:
            d = json.loads(line)
        except ValueError:
            continue
        msg = d.get("message") if isinstance(d.get("message"), dict) else None
        if d.get("type") != "assistant" or not msg or not isinstance(msg.get("usage"), dict):
            continue
        mid = msg.get("id") or d.get("requestId")
        if mid in seen:
            continue
        seen.append(mid)
        model = msg.get("model") or "?"
        if model.startswith("<"):  # <synthetic> 등
            continue
        last_model = model
        u = msg["usage"]
        e = out.setdefault(model, {"usd": 0.0, "tok": 0})
        e["usd"] += usage_usd(model, u)
        e["tok"] += sum(int(u.get(k) or 0) for k in ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"))
    return out, offset + end, seen[-50:], last_model


def tail_model(path, nbytes=262144):
    """큰 트랜스크립트의 끝부분에서 마지막 assistant 모델만 찾는다(처음 볼 때 inherit 판정용)."""
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as f:
            f.seek(max(0, size - nbytes))
            data = f.read()
    except OSError:
        return None
    for m in reversed(re.findall(rb'"model":"(claude-[^"]+)"', data)):
        return m.decode()
    return None


def add_spend(bucket, by_model):
    for model, e in by_model.items():
        b = bucket.setdefault(model, {"usd": 0.0, "tok": 0})
        b["usd"] += e["usd"]
        b["tok"] += e["tok"]


def total_usd(st):
    return sum(e["usd"] for k in ("main", "sub") for e in st.get("spent", {}).get(k, {}).values())


# ---------- 상태 ----------
def _sid(sid):
    return re.sub(r"[^\w-]", "", str(sid or "nosession"))


def state_dir():
    d = os.path.join(tempfile.gettempdir(), NS)
    os.makedirs(d, exist_ok=True)
    return d


def state_path(sid):
    return os.path.join(state_dir(), _sid(sid) + ".json")


def blank():
    return {"reserved": {}, "running": {}, "agents": {}, "spent": {"main": {}, "sub": {}}, "main": {},
            "away": None, "spawned": 0, "notes": {}, "burst": 0, "log": []}


def read(sid):
    try:
        st = json.load(open(state_path(sid)))
    except Exception:
        return blank()
    for k, v in blank().items():
        st.setdefault(k, v)
    return st


@contextmanager
def session(sid):
    """잠금을 잡고 상태를 읽어 넘기고, 블록이 끝나면 원자적으로 쓴다(병렬 훅 대비)."""
    p = state_path(sid)
    with open(p + ".lock", "w") as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        st = read(sid)
        yield st
        st["log"] = st["log"][-200:]
        tmp = p + ".tmp"
        with open(tmp, "w") as f:
            json.dump(st, f)
        os.replace(tmp, p)


def log(st, event, **kw):
    st["log"].append(dict(kw, t=round(time.time(), 1), k=event))


def subagent_dir(st):
    tp = st.get("tp")
    return os.path.join(os.path.splitext(tp)[0], "subagents") if tp else None


def _meta(st, agent_id):
    d = subagent_dir(st)
    if not d:
        return None
    try:
        return json.load(open(os.path.join(d, f"agent-{agent_id}.meta.json")))
    except Exception:
        return None


def live(st, cfg, now=None, background=None):
    """실행 중 + 예약 목록을 정리해서 돌려준다(복구 포함). 상태를 고친다.
    복구 근거(위에서부터): background_tasks(공식, 백그라운드만) → meta.json finished(비공식, 로컬 실측)
    → 트랜스크립트 mtime 이 STALE 분 넘게 멈춤 → 예약 TTL."""
    now = now or time.time()
    stale = num(cfg, "HARNESS_SLOTS_STALE_MIN") * 60
    ttl = num(cfg, "HARNESS_SLOTS_RESERVE_SEC")
    for k, r in list(st["reserved"].items()):
        if now - r.get("t", 0) > ttl:
            del st["reserved"][k]
            log(st, "reserve-expired", id=k)
    bg_ids = None
    if background is not None:
        bg_ids = {t.get("id") for t in background if t.get("type") == "subagent"}
    d = subagent_dir(st)
    for aid, r in list(st["running"].items()):
        why = None
        if bg_ids is not None and r.get("bg") and aid not in bg_ids:
            why = "not-in-background_tasks"
        else:
            meta = _meta(st, aid)
            if meta and meta.get("finished"):
                why = "meta-finished"
            else:
                try:
                    last = os.path.getmtime(os.path.join(d, f"agent-{aid}.jsonl")) if d else r.get("t", now)
                except OSError:
                    last = r.get("t", now)
                if now - max(last, r.get("t", 0)) > stale:
                    why = "stale"
        if why:
            del st["running"][aid]
            log(st, "recovered", id=aid, why=why)
    return [dict(r, id=k) for k, r in st["running"].items()] + [dict(r, id=k, reserved=True) for k, r in st["reserved"].items()]


def by_family(items):
    c = {}
    for r in items:
        f = r.get("fam") or "?"
        c[f] = c.get(f, 0) + 1
    return {f: c[f] for f in ORDER + ("?",) if f in c}


def account_main(st, transcript_path):
    """메인 트랜스크립트 사용량을 이어서 더한다. 처음 보면 끝에서 시작한다(긴 세션을 소급하지 않는다)."""
    if not transcript_path:
        return
    st["tp"] = transcript_path
    m = st["main"]
    if "off" not in m:
        try:
            m["off"] = os.path.getsize(transcript_path)
        except OSError:
            m["off"] = 0
        m["since"] = time.time()
        m["model"] = tail_model(transcript_path)
        return
    by, m["off"], m["recent"], last = scan(transcript_path, m["off"], m.get("recent", ()))
    add_spend(st["spent"]["main"], by)
    if last:
        m["model"] = last


def account_agent(st, agent_id, path):
    """서브에이전트 트랜스크립트를 이어서 더한다(재개된 에이전트가 다시 멈춰도 두 번 세지 않는다)."""
    if not path:
        d = subagent_dir(st)
        path = os.path.join(d, f"agent-{agent_id}.jsonl") if d else None
    if not path:
        return None
    a = st["agents"].setdefault(agent_id, {"off": 0, "usd": 0.0})
    a["path"] = path
    by, a["off"], a["recent"], last = scan(path, a["off"], a.get("recent", ()))
    add_spend(st["spent"]["sub"], by)
    a["usd"] += sum(e["usd"] for e in by.values())
    if last:
        a["model"] = last
    if len(st["agents"]) > 500:  # 오래된 것부터 정리(합계는 spent 에 남는다)
        for k in list(st["agents"])[:100]:
            del st["agents"][k]
    return a


def sweep(st, now=None, window=600):
    """SubagentStop 시점에는 마지막 응답이 아직 트랜스크립트에 없다(실측: 에이전트마다 약 7% 누락).
    최근 window 초 안에 멈춘 에이전트는 다음 훅 이벤트마다 이어서 읽는다(offset 이 있어 두 번 세지 않는다)."""
    now = now or time.time()
    for aid, a in list(st["agents"].items()):
        if a.get("stopped") and now - a["stopped"] < window and a.get("path"):
            account_agent(st, aid, a["path"])


# ---------- away ----------
def parse_away_args(args, cfg):
    """`[예산] [슬롯]`. 예산: 15 | $15 | 15usd → USD, 8a | 8agents → 에이전트 수. 슬롯: 2 | 2s | slots=2."""
    budget_usd, budget_agents, slots = num(cfg, "HARNESS_AWAY_BUDGET_USD"), None, num(cfg, "HARNESS_AWAY_SLOTS", int)
    pos = 0
    for a in args:
        a = a.strip().lower()
        if not a:
            continue
        m = re.fullmatch(r"(?:slots?=)?(\d+)s(?:lots?)?|slots?=(\d+)", a)
        if m:
            slots = int(m.group(1) or m.group(2))
            continue
        m = re.fullmatch(r"(\d+)\s*a(?:gents?)?", a)
        if m and pos == 0:
            budget_agents, budget_usd, pos = int(m.group(1)), None, 1
            continue
        m = re.fullmatch(r"\$?(\d+(?:\.\d+)?)(?:usd|\$)?", a)
        if m:
            if pos == 0:
                budget_usd, pos = float(m.group(1)), 1
            else:
                slots = int(float(m.group(1)))
            continue
        raise ValueError(f"알 수 없는 인자: {a}")
    return budget_usd, budget_agents, max(1, slots)


def away_status(st, now=None):
    """(spent_usd, spawned, over, why) — away 이후 기준."""
    a = st.get("away") or {}
    spent = total_usd(st) - a.get("base_usd", 0.0)
    spawned = st.get("spawned", 0) - a.get("base_spawned", 0)
    over = None
    if a.get("budget_usd") is not None and spent >= a["budget_usd"]:
        over = f"budget ${a['budget_usd']:g} used (${spent:.2f})"
    elif a.get("budget_agents") is not None and spawned >= a["budget_agents"]:
        over = f"agent budget {a['budget_agents']} used ({spawned} spawned)"
    return spent, spawned, over


def find_transcript(sid):
    cfgdir = os.environ.get("CLAUDE_CONFIG_DIR") or str(HOME)
    hits = glob.glob(os.path.join(cfgdir, "projects", "*", _sid(sid) + ".jsonl"))
    return max(hits, key=os.path.getmtime) if hits else None


def fmt_spend(bucket):
    items = sorted(bucket.items(), key=lambda kv: -kv[1]["usd"])
    tok = lambda n: f"{n / 1e6:.1f}M" if n >= 1e6 else f"{n / 1e3:.0f}k"
    return ", ".join(f"{m.replace('claude-', '')} ${e['usd']:.2f} ({tok(e['tok'])} tok)" for m, e in items) or "없음"


def cmd_away(sid, args):
    cfg = config(os.environ.get("CLAUDE_PROJECT_DIR"))
    try:
        budget_usd, budget_agents, slots = parse_away_args(args, cfg)
    except ValueError as e:
        print(f"/away: {e}. 형식: /away [예산: 15 | $15 | 8a] [슬롯: 2]")
        return 2
    with session(sid) as st:
        account_main(st, st.get("tp") or find_transcript(sid))
        sweep(st)
        st["away"] = {"on": True, "since": time.time(), "budget_usd": budget_usd, "budget_agents": budget_agents,
                      "slots": slots, "over_slots": num(cfg, "HARNESS_AWAY_OVER_SLOTS", int),
                      "base_usd": total_usd(st), "base_spawned": st.get("spawned", 0), "queued": 0, "over_at": None}
        log(st, "away-on", budget_usd=budget_usd, budget_agents=budget_agents, slots=slots)
        n = len(live(st, cfg))
    b = f"${budget_usd:g} (API 목록가 환산)" if budget_agents is None else f"에이전트 {budget_agents}개"
    print(f"away 모드 켬: 예산 {b}, 동시 슬롯 {slots}. 예산을 넘기면 슬롯 {num(cfg, 'HARNESS_AWAY_OVER_SLOTS', int)}개로 직렬화한다(멈추지 않음).")
    print(f"지금 실행 중인 서브에이전트: {n}개. 돌아오면 /back 으로 요약을 본다.")
    return 0


def summary(st, cfg, now=None):
    now = now or time.time()
    a = st.get("away") or {}
    spent, spawned, over = away_status(st)
    items = live(st, cfg, now)
    mins = (now - a.get("since", now)) / 60
    lines = [f"자리 비운 시간: {mins:.0f}분",
             f"쓴 비용(API 목록가 환산): ${spent:.2f}" + (f" / 예산 ${a['budget_usd']:g}" if a.get("budget_usd") is not None else ""),
             f"띄운 서브에이전트: {spawned}개" + (f" / 예산 {a['budget_agents']}개" if a.get("budget_agents") is not None else "")
             + f", 줄 세운(거절 후 대기) 횟수: {a.get('queued', 0)}",
             f"예산 초과: {'예 — ' + over if over else '아니오'}",
             f"지금 실행 중: {len(items)}개 {by_family(items) or ''}",
             f"세션 누적(훅이 본 뒤): 메인 {fmt_spend(st['spent']['main'])} / 서브 {fmt_spend(st['spent']['sub'])}"]
    since = a.get("since", 0)
    ev = [e for e in st["log"] if e.get("t", 0) >= since and e["k"] in ("queued", "over-budget", "recovered")]
    if ev:
        lines.append("사건: " + ", ".join(f"{time.strftime('%H:%M', time.localtime(e['t']))} {e['k']}" for e in ev[-8:]))
    return lines


def cmd_back(sid):
    cfg = config(os.environ.get("CLAUDE_PROJECT_DIR"))
    with session(sid) as st:
        account_main(st, st.get("tp") or find_transcript(sid))
        sweep(st)
        if not (st.get("away") or {}).get("on"):
            print("away 모드가 아니다. 세션 누적(훅이 본 뒤): 메인 " + fmt_spend(st["spent"]["main"]) + " / 서브 " + fmt_spend(st["spent"]["sub"]))
            return 0
        lines = summary(st, cfg)
        st["away"]["on"] = False
        st["last_away"] = st.pop("away")
        st["away"] = None
        log(st, "away-off")
    print("away 모드 끔. 요약:")
    print("\n".join("- " + x for x in lines))
    return 0


def cmd_status(sid):
    cfg = config(os.environ.get("CLAUDE_PROJECT_DIR"))
    with session(sid) as st:
        account_main(st, st.get("tp") or find_transcript(sid))
        sweep(st)
        if (st.get("away") or {}).get("on"):
            print("away 모드 켜짐:")
            print("\n".join("- " + x for x in summary(st, cfg)))
        else:
            items = live(st, cfg)
            print(f"away 모드 아님. 실행 중 {len(items)}개 {by_family(items) or ''}")
    return 0


def cmd_reset(sid):
    with session(sid) as st:
        n = len(st["running"]) + len(st["reserved"])
        st["running"], st["reserved"] = {}, {}
        log(st, "reset", n=n)
    print(f"슬롯 카운터를 비웠다({n}개 항목). 실제 실행 중인 에이전트는 영향이 없고, 다음 훅부터 다시 센다.")
    return 0


def main(argv):
    if len(argv) < 2:
        print("사용: subagent_ledger.py away|back|status|reset <session_id> [인자…]")
        return 2
    cmd, sid, rest = argv[0], argv[1], argv[2:]
    if not sid or sid.startswith("${"):
        print("session_id 를 받지 못했다(스킬의 ${CLAUDE_SESSION_ID} 치환 실패).")
        return 2
    if cmd == "away":
        if rest and rest[0].lower() in ("off", "back"):
            return cmd_back(sid)
        if rest and rest[0].lower() == "status":
            return cmd_status(sid)
        if rest and rest[0].lower() == "reset":
            return cmd_reset(sid)
        return cmd_away(sid, rest)
    return {"back": cmd_back, "status": cmd_status, "reset": cmd_reset}.get(cmd, lambda s: 2)(sid)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
