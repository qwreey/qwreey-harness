"""서브에이전트 슬롯·비용 원장 (session_id 단위). 표준 라이브러리만.

쓰는 곳: scripts/subagent-slots.py(기록), statusline/harness-status.py(읽기), skills/q:away·back(이 파일의 CLI). statusline 은 설치된 q 의 사본을 찾아 읽는다.
설계: .claude/audit/21-cost-disclosure.md. 훅 메시지는 HOOK-MESSAGES.md 규약을 따른다.

상태 파일: $TMPDIR/claude-subagent-slots/<sid>.json (+ .lock). compact 회차로 나누지 않는다(실행 중 수는 compact 와 무관).
알림 dedup 만 키에 회차를 넣는다(compact_epoch.py, q 자기 회차).

실측(2026-11-10, claude 2.1.316, .claude/audit/21 §1):
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

HOME = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")  # 사용자 설정 위치(harness.env, lib/harness_env.py, projects/)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import compact_epoch  # noqa: E402
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
    "HARNESS_AWAY_BUDGET_USD": "20",  # /q:away 에 예산을 안 주면
    "HARNESS_AWAY_SLOTS": "2",  # /q:away 에 슬롯을 안 주면
    "HARNESS_AWAY_OVER_SLOTS": "1",  # 예산을 넘긴 뒤 슬롯(직렬화)
    "HARNESS_AWAY_BUDGET_PCT": "30",  # 구독제: /q:away 에 예산을 안 주면 그 창의 몇 %p 를 더 쓸 때까지
    "HARNESS_AWAY_PLAN": "auto",  # auto(statusline 이 한도 값을 보내면 pct, 아니면 usd) | usd | pct
    "HARNESS_AWAY_STAGE2_MULT": "2",  # 2단계 = 예산의 이 배수(새 서브에이전트·Workflow 거절)
    "HARNESS_AWAY_LIMITS_STALE_MIN": "10",  # statusline 이 한도 값을 이만큼 못 갱신하면 오래된 것으로 보고 USD 가드로
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
    return compact_epoch.epoch("q", sid)


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


# ---------- 한도 % (statusline 입력의 rate_limits → 세션별 파일) ----------
WINDOWS = {"5h": "five_hour", "w": "seven_day"}
WLABEL = {"five_hour": "5h", "seven_day": "week"}


def limits_path(sid):
    return os.path.join(state_dir(), _sid(sid) + ".limits.json")


def write_limits(sid, rate_limits, now=None):
    """statusline 이 호출한다. 훅은 statusline 입력을 못 받으므로 이 파일로 넘긴다. 값이 없으면 쓰지 않는다(이전 값 유지)."""
    out = {}
    for w in WINDOWS.values():
        e = (rate_limits or {}).get(w)
        if isinstance(e, dict) and isinstance(e.get("used_percentage"), (int, float)):
            out[w] = {"p": float(e["used_percentage"]), "r": e.get("resets_at") if isinstance(e.get("resets_at"), (int, float)) else None}
    if not out:
        return False
    out["t"] = now or time.time()
    p = limits_path(sid)
    tmp = f"{p}.{os.getpid()}.tmp"
    with open(tmp, "w") as f:
        json.dump(out, f)
    os.replace(tmp, p)
    return True


def read_limits(sid):
    try:
        d = json.load(open(limits_path(sid)))
        return d if isinstance(d, dict) and "t" in d else None
    except Exception:
        return None


# ---------- away ----------
def parse_away(args, cfg, lim=None):
    """`[예산] [슬롯]` → dict(unit, budget_usd, budget_agents, budget_pct, pct_win, slots, note).
    예산: 15 | $15 | 15usd → USD, 8a → 에이전트 수, 30% → 한도 %p(가장 빡빡한 창), 30%w | 30%5h → 창 지정.
    슬롯: 2 | 2s | slots=2. 예산을 안 주면 HARNESS_AWAY_PLAN(auto 는 lim 이 있으면 pct)."""
    r = dict(unit=None, budget_usd=None, budget_agents=None, budget_pct=None, pct_win=None, note=None,
             slots=num(cfg, "HARNESS_AWAY_SLOTS", int))
    pos = 0
    for a in args:
        a = a.strip().lower()
        if not a:
            continue
        m = re.fullmatch(r"(?:slots?=)?(\d+)s(?:lots?)?|slots?=(\d+)", a)
        if m:
            r["slots"] = int(m.group(1) or m.group(2))
            continue
        m = re.fullmatch(r"(\d+(?:\.\d+)?)\s*%\s*(w|week|weekly|7d|5h|5hr|h)?", a)
        if m and pos == 0:
            if float(m.group(1)) <= 0:
                raise ValueError("한도 %는 0 보다 커야 한다")
            r["unit"], r["budget_pct"], pos = "pct", float(m.group(1)), 1
            if m.group(2):
                r["pct_win"] = WINDOWS["w" if m.group(2) in ("w", "week", "weekly", "7d") else "5h"]
            continue
        m = re.fullmatch(r"(\d+)\s*a(?:gents?)?", a)
        if m and pos == 0:
            r["unit"], r["budget_agents"], pos = "agents", int(m.group(1)), 1
            continue
        m = re.fullmatch(r"\$?(\d+(?:\.\d+)?)(?:usd|\$)?", a)
        if m:
            if pos == 0:
                r["unit"], r["budget_usd"], pos = "usd", float(m.group(1)), 1
            else:
                r["slots"] = int(float(m.group(1)))
            continue
        raise ValueError(f"알 수 없는 인자: {a}")
    plan = str(cfg.get("HARNESS_AWAY_PLAN", "auto")).strip().lower()
    if r["unit"] is None:
        pct_ok = plan == "pct" or (plan == "auto" and bool(lim and any(w in lim for w in WINDOWS.values())))
        if pct_ok:
            r["unit"], r["budget_pct"] = "pct", num(cfg, "HARNESS_AWAY_BUDGET_PCT")
        else:
            r["unit"], r["budget_usd"] = "usd", num(cfg, "HARNESS_AWAY_BUDGET_USD")
            if plan == "auto":
                r["note"] = "plan-unknown"
    if r["unit"] == "pct":
        have = [w for w in WINDOWS.values() if lim and w in lim]
        want = [r["pct_win"]] if r["pct_win"] else have
        use = [w for w in want if w in have] or have
        if not use:  # 한도 값을 아직 못 받음(비구독, -p, 첫 응답 전)
            r["unit"], r["budget_usd"], r["budget_pct"] = "usd", num(cfg, "HARNESS_AWAY_BUDGET_USD"), None
            r["note"] = "no-limits"
        elif r["pct_win"] and r["pct_win"] not in use:
            r["note"] = "window-missing"
            r["pct_win"] = None
    r["slots"] = max(1, r["slots"])
    return r


def parse_away_args(args, cfg):
    """(budget_usd, budget_agents, slots) — 구버전 호환(% 는 USD 로 바뀌지 않으므로 budget_usd=None)."""
    r = parse_away(args, cfg)
    return r["budget_usd"], r["budget_agents"], r["slots"]


def pct_init(r, lim, now):
    """/q:away 시점의 기준점. 창마다 시작값·리셋 시각·문턱(남은 여유가 N 보다 작으면 거기까지)을 적는다."""
    wins = [r["pct_win"]] if r["pct_win"] else [w for w in WINDOWS.values() if w in lim]
    out = {}
    for w in wins:
        p = lim[w]["p"]
        room = max(0.0, 100.0 - p)
        out[w] = {"start": p, "last": p, "acc": 0.0, "r": lim[w].get("r"), "room": room}
    return out


def away_eval(st, lim=None, now=None, persist=True, cfg=None):
    """away 예산 판정 → dict(level 0|1|2, why, spent, spawned, pct(창별 증가분 %p), stale).
    level 1 = 예산 도달, level 2 = 예산 x STAGE2_MULT. 기준은 /q:away 이후 증가분.
    persist=True 면 창 상태(리셋 넘김 포함)를 st 에 갱신한다. 훅만 True(잠금 안), statusline 은 False."""
    now = now or time.time()
    cfg = cfg or CFG_DEFAULTS
    a = st.get("away") or {}
    if not persist:
        import copy
        a = copy.deepcopy(a)
    mult = num(cfg, "HARNESS_AWAY_STAGE2_MULT")
    spent = total_usd(st) - a.get("base_usd", 0.0)
    spawned = st.get("spawned", 0) - a.get("base_spawned", 0)
    res = dict(level=0, why=None, spent=spent, spawned=spawned, pct={}, stale=False)

    def mark(level, why):
        if level > res["level"]:
            res["level"], res["why"] = level, why

    if a.get("budget_usd") is not None:
        b = a["budget_usd"]
        if spent >= b * mult:
            mark(2, f"${b * mult:g} (x{mult:g} budget) reached (${spent:.2f})")
        if spent >= b:
            mark(1, f"budget ${b:g} used (${spent:.2f})")
    elif a.get("budget_agents") is not None:
        b = a["budget_agents"]
        if spawned >= b * mult:
            mark(2, f"{b * mult:g} agents (x{mult:g} budget) reached ({spawned} spawned)")
        if spawned >= b:
            mark(1, f"agent budget {b} used ({spawned} spawned)")
    elif a.get("budget_pct") is not None:
        n = a["budget_pct"]
        stale_sec = num(cfg, "HARNESS_AWAY_LIMITS_STALE_MIN") * 60
        fresh = bool(lim) and now - lim.get("t", 0) <= stale_sec
        res["stale"] = not fresh
        pw = a.get("pct") or {}
        for w, s in pw.items():
            cur = lim.get(w) if fresh else None
            if cur:
                if cur.get("r") and s.get("r") and cur["r"] > s["r"] + 60:  # 창이 리셋됐다: 리셋 전 증가분을 쌓고 새로 센다
                    s["acc"] += max(0.0, s["last"] - s["start"])
                    s["start"], s["room"] = 0.0, 100.0
                    s["r"] = cur["r"]
                s["last"] = cur["p"]
                if s.get("r") is None:
                    s["r"] = cur.get("r")
            d = s["acc"] + max(0.0, s["last"] - s["start"])
            res["pct"][w] = d
            t1, t2 = min(n, s["room"]), min(n * mult, s["room"])  # 남은 여유가 N 보다 작으면 한도 100% 가 문턱
            lbl = WLABEL[w]
            if d >= t2:
                mark(2, f"{lbl} limit +{d:.0f}%p since away (stage-2 threshold {t2:g}%p)")
            if d >= t1:
                mark(1, f"{lbl} limit +{d:.0f}%p since away (budget {t1:g}%p)")
        if not fresh:  # 값이 오래됐다: 마지막으로 본 증가분은 그대로 두고, 모자란 부분은 USD 가드로 메운다
            fb = num(cfg, "HARNESS_AWAY_BUDGET_USD")
            if spent >= fb * mult:
                mark(2, f"limit data stale; USD guard ${fb * mult:g} reached (${spent:.2f})")
            if spent >= fb:
                mark(1, f"limit data stale; USD guard ${fb:g} used (${spent:.2f})")
    return res


def away_status(st, now=None, lim=None, cfg=None):
    """(spent_usd, spawned, over 문자열 또는 None) — away 이후 기준. 상태는 고치지 않는다."""
    e = away_eval(st, lim, now, persist=False, cfg=cfg)
    return e["spent"], e["spawned"], e["why"]


def find_transcript(sid):
    cfgdir = os.environ.get("CLAUDE_CONFIG_DIR") or str(HOME)
    hits = glob.glob(os.path.join(cfgdir, "projects", "*", _sid(sid) + ".jsonl"))
    return max(hits, key=os.path.getmtime) if hits else None


def fmt_spend(bucket):
    items = sorted(bucket.items(), key=lambda kv: -kv[1]["usd"])
    tok = lambda n: f"{n / 1e6:.1f}M" if n >= 1e6 else f"{n / 1e3:.0f}k"
    return ", ".join(f"{m.replace('claude-', '')} ${e['usd']:.2f} ({tok(e['tok'])} tok)" for m, e in items) or "없음"


def away_check(st, cfg, lim, now=None):
    """away 중이면 판정하고(창 상태 갱신 포함) 1·2단계 도달 시각을 처음 한 번만 적는다. 훅·/q:back 이 부른다."""
    a = st.get("away")
    if not (a and a.get("on")):
        return None
    now = now or time.time()
    e = away_eval(st, lim, now, True, cfg)
    if e["level"] >= 1 and not a.get("over_at"):
        a["over_at"] = now
        log(st, "over-budget", why=e["why"])
    if e["level"] >= 2 and not a.get("over2_at"):
        a["over2_at"] = now
        log(st, "stage2", why=e["why"])
    return e


def budget_text(a, cfg):
    mult = num(cfg, "HARNESS_AWAY_STAGE2_MULT")
    if a.get("budget_usd") is not None:
        return f"${a['budget_usd']:g} (API 목록가 환산, {mult:g}배인 ${a['budget_usd'] * mult:g} 에서 새 서브에이전트 중단)"
    if a.get("budget_agents") is not None:
        return f"에이전트 {a['budget_agents']}개 ({mult:g}배인 {a['budget_agents'] * mult:g}개에서 중단)"
    wl = "/".join(WLABEL[w] for w in (a.get("pct") or {})) or "?"
    return f"한도 {a['budget_pct']:g}%p ({wl} 창 기준, {mult:g}배인 {a['budget_pct'] * mult:g}%p 에서 새 서브에이전트 중단)"


def cmd_away(sid, args):
    cfg = config(os.environ.get("CLAUDE_PROJECT_DIR"))
    lim = read_limits(sid)
    try:
        r = parse_away(args, cfg, lim)
    except ValueError as e:
        print(f"/q:away: {e}. 형식: /q:away [예산: $5 | 30% | 30%w | 30%5h | 6a] [슬롯: 2]")
        return 2
    now = time.time()
    with session(sid) as st:
        account_main(st, st.get("tp") or find_transcript(sid))
        sweep(st)
        st["away"] = {"on": True, "since": now, "unit": r["unit"], "budget_usd": r["budget_usd"], "budget_agents": r["budget_agents"],
                      "budget_pct": r["budget_pct"], "pct": pct_init(r, lim, now) if r["unit"] == "pct" else {},
                      "slots": r["slots"], "over_slots": num(cfg, "HARNESS_AWAY_OVER_SLOTS", int),
                      "base_usd": total_usd(st), "base_spawned": st.get("spawned", 0), "queued": 0, "over_at": None, "over2_at": None}
        log(st, "away-on", unit=r["unit"], budget_usd=r["budget_usd"], budget_agents=r["budget_agents"], budget_pct=r["budget_pct"], slots=r["slots"])
        n = len(live(st, cfg))
        a = st["away"]
    print(f"away 모드 켬: 예산 {budget_text(a, cfg)}, 동시 슬롯 {r['slots']}.")
    print(f"예산을 넘기면(1단계) 슬롯 {num(cfg, 'HARNESS_AWAY_OVER_SLOTS', int)}개로 직렬화하고, {num(cfg, 'HARNESS_AWAY_STAGE2_MULT'):g}배를 넘기면(2단계) 새 서브에이전트·Workflow 를 거절하고 메인에게 상태를 적고 기다리라고 한다.")
    note = r.get("note")
    if note == "no-limits":
        print("[no-limits] 한도 % 값을 아직 받지 못해(statusline 미설정, 비구독, 또는 첫 응답 전) USD 예산으로 켰다.")
    elif note == "window-missing":
        print("[window-missing] 지정한 창의 값이 없어 있는 창으로 켰다(요금제에 없는 창일 수 있다).")
    elif note == "plan-unknown":
        print("[plan-unknown] 요금제를 알 수 없어 USD 기본값으로 켰다.")
    print(f"지금 실행 중인 서브에이전트: {n}개. 돌아오면 /q:back 으로 요약을 본다.")
    return 0


def summary(st, cfg, now=None, lim=None):
    now = now or time.time()
    a = st.get("away") or {}
    e = away_check(st, cfg, lim, now) or away_eval(st, lim, now, False, cfg)
    spent, spawned = e["spent"], e["spawned"]
    items = live(st, cfg, now)
    mins = (now - a.get("since", now)) / 60
    hm = lambda t: time.strftime("%H:%M", time.localtime(t))
    lines = [f"자리 비운 시간: {mins:.0f}분",
             f"예산: {budget_text(a, cfg)}",
             f"쓴 비용(API 목록가 환산): ${spent:.2f}"]
    if a.get("budget_pct") is not None:
        lines.append("한도 증가분(자리 비운 뒤): " + (", ".join(f"{WLABEL[w]} +{d:.0f}%p" for w, d in e["pct"].items()) or "없음")
                     + (" (한도 값이 오래돼 USD 가드로 보강)" if e["stale"] else ""))
    lines += [f"띄운 서브에이전트: {spawned}개" + (f" / 예산 {a['budget_agents']}개" if a.get("budget_agents") is not None else "")
              + f", 줄 세운(거절 후 대기) 횟수: {a.get('queued', 0)}",
              f"예산 초과: {'예 ' + hm(a['over_at']) + ' (1단계) — ' + str(e['why']) if a.get('over_at') else '아니오'}",
              f"2단계(새 서브에이전트 중단) 도달: {'예 ' + hm(a['over2_at']) if a.get('over2_at') else '아니오'}",
              f"지금 실행 중: {len(items)}개 {by_family(items) or ''}",
              f"세션 누적(훅이 본 뒤): 메인 {fmt_spend(st['spent']['main'])} / 서브 {fmt_spend(st['spent']['sub'])}"]
    since = a.get("since", 0)
    ev = [x for x in st["log"] if x.get("t", 0) >= since and x["k"] in ("queued", "over-budget", "stage2", "recovered")]
    if ev:
        lines.append("사건: " + ", ".join(f"{hm(x['t'])} {x['k']}" for x in ev[-8:]))
    return lines


def cmd_back(sid):
    cfg = config(os.environ.get("CLAUDE_PROJECT_DIR"))
    lim = read_limits(sid)
    with session(sid) as st:
        account_main(st, st.get("tp") or find_transcript(sid))
        sweep(st)
        if not (st.get("away") or {}).get("on"):
            print("away 모드가 아니다. 세션 누적(훅이 본 뒤): 메인 " + fmt_spend(st["spent"]["main"]) + " / 서브 " + fmt_spend(st["spent"]["sub"]))
            return 0
        lines = summary(st, cfg, lim=lim)
        st["away"]["on"] = False
        st["last_away"] = st.pop("away")
        st["away"] = None
        log(st, "away-off")
    print("away 모드 끔. 요약:")
    print("\n".join("- " + x for x in lines))
    return 0


def cmd_status(sid):
    cfg = config(os.environ.get("CLAUDE_PROJECT_DIR"))
    lim = read_limits(sid)
    with session(sid) as st:
        account_main(st, st.get("tp") or find_transcript(sid))
        sweep(st)
        if (st.get("away") or {}).get("on"):
            print("away 모드 켜짐:")
            print("\n".join("- " + x for x in summary(st, cfg, lim=lim)))
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
