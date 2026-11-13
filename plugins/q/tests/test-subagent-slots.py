#!/usr/bin/env python3
"""subagent-slots 훅·원장·statusline 회귀. 실행: python3 -I test-subagent-slots.py (exit 0 = 통과)

슬롯 계산, 예산 소진(USD·에이전트 수), 팬아웃 dedup(묶음·compact 회차), 카운터 복구, /q:away·/q:back, statusline, 비용 계산.
"""
import json
import re
import os
import shutil
import subprocess
import sys
import tempfile
import time

Q = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
H = os.path.join(Q, "scripts")
HOME = os.path.join(os.path.dirname(os.path.dirname(Q)), "home", ".claude")  # 정본 사용자 설정(statusline, harness.env)
LEDGER = os.path.join(H, "subagent_ledger.py")
T = tempfile.mkdtemp(prefix="slots-")
# 사용자 설정 디렉터리 흉내: 설치된 q(이 저장소의 사본)를 가리키는 installed_plugins.json + 정본 harness.env·lib
CFG = os.path.join(T, "cfg")
os.makedirs(os.path.join(CFG, "plugins"))
os.symlink(os.path.join(HOME, "lib"), os.path.join(CFG, "lib"))
os.symlink(os.path.join(HOME, "harness.env"), os.path.join(CFG, "harness.env"))
json.dump({"version": 2, "plugins": {"q@claude-doctor-market": [{"scope": "user", "installPath": Q, "lastUpdated": "2026-01-01T00:00:00Z"}]}},
          open(os.path.join(CFG, "plugins", "installed_plugins.json"), "w"))
PROJ = os.path.join(T, "proj")
os.makedirs(os.path.join(PROJ, ".claude"))
BASE_ENV = {k: v for k, v in os.environ.items() if not k.startswith(("HARNESS_SUBAGENT", "HARNESS_FANOUT", "HARNESS_AWAY", "HARNESS_SLOTS"))}
ENV = dict(BASE_ENV, TMPDIR=T, CLAUDE_CONFIG_DIR=CFG, CLAUDE_PROJECT_DIR=PROJ, NO_COLOR="1",  # statusline 문자열 비교는 색 없이
           HARNESS_STATUSLINE_STYLE="plain",  # 스크립트 옆(정본) harness.env 의 개인 스타일에 휘둘리지 않게
           QWREEY_HARNESS_SALT_FILE=os.path.join(T, "salt"))  # nonce 는 고정 salt 로
open(os.path.join(T, "salt"), "w").write("00" * 32)
NONCE_RX = r' nonce="[0-9a-f]{12}"'
res = []


def check(name, ok, detail=None):
    res.append((name, bool(ok)))
    if not ok and detail is not None:
        print("  detail:", repr(detail))


def transcript(sid):
    p = os.path.join(T, "tx", sid + ".jsonl")
    os.makedirs(os.path.join(T, "tx", sid, "subagents"), exist_ok=True)
    if not os.path.exists(p):
        open(p, "w").close()
    return p


def usage_line(mid, model, inp=0, out=0, cr=0, w5=0, w1=0):
    u = {"input_tokens": inp, "output_tokens": out, "cache_read_input_tokens": cr, "cache_creation_input_tokens": w5 + w1,
         "cache_creation": {"ephemeral_5m_input_tokens": w5, "ephemeral_1h_input_tokens": w1}}
    return json.dumps({"type": "assistant", "message": {"id": mid, "model": model, "usage": u}}) + "\n"


def hook(data, env=None):
    p = subprocess.run([sys.executable, "-I", os.path.join(H, "subagent-slots.py")], input=json.dumps(data),
                       capture_output=True, text=True, env=env or ENV, timeout=15)
    assert p.returncode == 0, p.stderr
    return json.loads(p.stdout) if p.stdout.strip() else None


def cli(*args, env=None):
    p = subprocess.run([sys.executable, "-I", LEDGER, *args], capture_output=True, text=True, env=env or ENV, timeout=15)
    return p.stdout


def ctx(out):
    return ((out or {}).get("hookSpecificOutput") or {}).get("additionalContext") or ""


def denied(out):
    return ((out or {}).get("hookSpecificOutput") or {}).get("permissionDecision") == "deny"


def reason(out):
    return ((out or {}).get("hookSpecificOutput") or {}).get("permissionDecisionReason") or ""


class S:
    """한 세션의 이벤트를 흉내 낸다."""
    def __init__(self, sid, env=None):
        self.sid, self.env, self.tp, self.n = sid, env, transcript(sid), 0

    def base(self, **kw):
        return dict(session_id=self.sid, transcript_path=self.tp, cwd=PROJ, **kw)

    def pre(self, model="sonnet", bg=True, tool="Agent", typ="general-purpose"):
        self.n += 1
        tid = f"toolu_{self.sid}_{self.n}"
        ti = {"script": "x"} if tool == "Workflow" else {"description": "d", "prompt": "p", "subagent_type": typ, "model": model, "run_in_background": bg}
        return tid, hook(self.base(hook_event_name="PreToolUse", tool_name=tool, tool_use_id=tid, tool_input=ti), self.env)

    def launch(self, model="sonnet"):
        """백그라운드 Agent 한 개의 정상 흐름: Pre → Post(async_launched) → SubagentStart. (out, agent_id)"""
        tid, out = self.pre(model)
        if denied(out):
            return out, None
        aid = "a" + tid[-12:].replace("_", "")
        hook(self.base(hook_event_name="PostToolUse", tool_name="Agent", tool_use_id=tid, tool_input={},
                       tool_response={"status": "async_launched", "agentId": aid, "resolvedModel": f"claude-{model}-5-5"}), self.env)
        hook(self.base(hook_event_name="SubagentStart", agent_id=aid, agent_type="general-purpose"), self.env)
        return out, aid

    def stop_agent(self, aid, usage_lines=(), bg_left=None):
        p = os.path.join(T, "tx", self.sid, "subagents", f"agent-{aid}.jsonl")
        with open(p, "a") as f:
            f.writelines(usage_lines)
        d = self.base(hook_event_name="SubagentStop", agent_id=aid, agent_type="general-purpose", agent_transcript_path=p)
        if bg_left is not None:
            d["background_tasks"] = [{"id": x, "type": "subagent", "status": "running"} for x in bg_left]
        return hook(d, self.env)

    def state(self):
        return json.load(open(os.path.join(T, "claude-subagent-slots", self.sid + ".json")))


# ---- 비용 계산: probe(2026-11-10) 의 sonnet-5-5 서브에이전트 1개 = $0.043544 ----
sys.path.insert(0, H)
import subagent_ledger as L  # noqa: E402

check("price: sonnet 5.5 cache write 5m/1h + read + out", abs(L.usage_usd("claude-sonnet-5-5", {
    "input_tokens": 3, "output_tokens": 100, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 17000,
    "cache_creation": {"ephemeral_5m_input_tokens": 17000, "ephemeral_1h_input_tokens": 0}}) - (3 * 2 + 17000 * 2.5 + 100 * 10) / 1e6) < 1e-9)
check("price: opus 5.5 is 2x sonnet 5.5 for the same usage",
      abs(L.usage_usd("claude-opus-5-5", {"input_tokens": 1000, "output_tokens": 1000}) - 2 * L.usage_usd("claude-sonnet-5-5", {"input_tokens": 1000, "output_tokens": 1000})) < 1e-12)
check("price: fast mode doubles", abs(L.usage_usd("claude-opus-5-5", {"output_tokens": 1000, "speed": "fast"}) - 0.04) < 1e-12)
check("price: unknown model -> 0", L.usage_usd("gpt-x", {"output_tokens": 1000}) == 0)
dup = os.path.join(T, "dup.jsonl")
open(dup, "w").write(usage_line("m1", "claude-sonnet-5-5", out=1000) * 3 + usage_line("m2", "claude-sonnet-5-5", out=1000))
by, off, recent, last = L.scan(dup)
check("scan: same message.id counted once", abs(by["claude-sonnet-5-5"]["usd"] - 0.02) < 1e-12)
open(dup, "a").write(usage_line("m2", "claude-sonnet-5-5", out=1000) + usage_line("m3", "claude-sonnet-5-5", out=1000))
by2, _, _, _ = L.scan(dup, off, recent)
check("scan: incremental offset + id carried across calls", abs(by2["claude-sonnet-5-5"]["usd"] - 0.01) < 1e-12)
check("away args: $15 2", L.parse_away_args(["$15", "2"], L.CFG_DEFAULTS) == (15.0, None, 2))
check("away args: 8a 3", L.parse_away_args(["8a", "3"], L.CFG_DEFAULTS) == (None, 8, 3))
check("away args: defaults", L.parse_away_args([], L.CFG_DEFAULTS) == (20.0, None, 2))

# ---- attended: 팬아웃 warn 은 문턱에서 한 번, 묶음이 끝나면 다시 ----
s = S("att")
outs = [s.launch("sonnet") for _ in range(5)]
check("attended: 3 sonnet -> silent", all(ctx(o) == "" for o, _ in outs[:3]))
check("attended: 4th concurrent -> warn", 'level="warn"' in ctx(outs[3][0]) and "Several subagents at once" in ctx(outs[3][0]))
check("attended: never denies", not any(denied(o) for o, _ in outs))
check("attended: 5th in same burst -> silent (dedup)", ctx(outs[4][0]) == "")
for _, aid in outs:
    s.stop_agent(aid)
check("attended: running back to 0 after stops", s.state()["running"] == {})
o1, a1 = s.launch("opus")
o2, a2 = s.launch("opus")
check("attended: 1 opus silent, 2nd opus -> warn (new burst)", ctx(o1) == "" and "opus-or-above: 2" in ctx(o2))
subprocess.run([sys.executable, "-I", os.path.join(H, "compact_epoch.py"), "q"], input=json.dumps({"session_id": "att", "source": "compact"}), text=True, env=ENV)
o3, a3 = s.launch("opus")
check("attended: compact epoch re-arms the warn in the same burst", "Several subagents at once" in ctx(o3))
_, ow = s.pre(tool="Workflow")
check("attended: Workflow -> warn, not denied", "Workflow requested" in ctx(ow) and not denied(ow))

# ---- 저장소 설정이 문턱을 덮어쓴다 ----
open(os.path.join(PROJ, ".claude", "harness.env"), "w").write("HARNESS_FANOUT_WARN_CONCURRENT=2\nHARNESS_HEAVY_WRAP=evil\n")
r = S("repo")
ra, _ = r.launch()
rb, _ = r.launch()
check("repo .claude/harness.env lowers the concurrent threshold", ctx(ra) == "" and "Several subagents at once" in ctx(rb))
check("repo env only overrides slot keys", L.config(PROJ).get("HARNESS_HEAVY_WRAP") != "evil")
os.remove(os.path.join(PROJ, ".claude", "harness.env"))

# ---- away: 슬롯 2 로 줄 세우기 ----
w = S("away")
out = cli("away", "away", "100", "2")
check("/q:away prints confirmation", "away 모드 켬" in out and "슬롯 2" in out)
wa, ida = w.launch()
wb, idb = w.launch()
wc, idc = w.launch()
check("away: first two allowed", not denied(wa) and not denied(wb))
check("away: third denied with queue reason, level=action", denied(wc) and re.match('<harness-hook name="subagent-slots" level="action"' + NONCE_RX + '>\nqueue: wait for a running agent to finish, then spawn the next', reason(wc)))
check("away: no fan-out warn in away mode", ctx(wa) == "" and ctx(wb) == "")
w.stop_agent(ida)
wd, idd = w.launch()
check("away: after one finishes the next spawns", not denied(wd))
check("away: queued count recorded", w.state()["away"]["queued"] == 1)
_, wf = w.pre(tool="Workflow")
check("away: Workflow while agents run -> queued (idle policy)", denied(wf) and "queue:" in reason(wf))

# ---- 예산 소진(USD): 직렬화 + 재고 리마인더 한 번 ----
big = [usage_line(f"x{i}", "claude-opus-5-5", out=1_000_000) for i in range(6)]  # $20 x 6 = $120 > $100
w.stop_agent(idb, big)
st = w.state()
check("budget: subagent spend accounted from its transcript", abs(L.total_usd(st) - 120) < 1e-6)
we, ide = w.launch()  # running: idd 하나, 초과 → 슬롯 1 → 거절
check("budget over: serialized to 1 slot (1 running -> queued)", denied(we) and "budget" in reason(we))
w.stop_agent(idd)
wf1, idf = w.launch()
check("budget over: 0 running -> allowed with reconsider warn", not denied(wf1) and 'level="warn"' in ctx(wf1) and "SendMessage" in ctx(wf1))
w.stop_agent(idf)
wg, idg = w.launch()
check("budget over: reconsider warn only once", not denied(wg) and ctx(wg) == "")
check("budget over: never stops the session (deny is per call)", all(not denied(x) for x in (wf1, wg)))

# ---- statusline ----
sl = subprocess.run([sys.executable, "-I", os.path.join(HOME, "statusline", "harness-status.py")],
                    input=json.dumps({"session_id": "away", "model": {"display_name": "Opus"}, "context_window": {"used_percentage": 34.4},
                                      "cost": {"total_cost_usd": 12.4}}), capture_output=True, text=True, env=ENV).stdout.strip()
check("statusline: model, ctx, cost, agents, away OVER", sl.startswith("Opus ctx 34% · $12.40 · agents 1 (sonnet 1)") and "AWAY OVER $120.00/$100 slots 1" in sl, sl)
t0 = time.time()
for _ in range(5):
    subprocess.run([sys.executable, "-I", os.path.join(HOME, "statusline", "harness-status.py")], input="{}", capture_output=True, text=True, env=ENV)
check("statusline: fast (<150ms per run)", (time.time() - t0) / 5 < 0.15)
check("statusline: survives empty input", subprocess.run([sys.executable, "-I", os.path.join(HOME, "statusline", "harness-status.py")], input="", capture_output=True, text=True, env=ENV).returncode == 0)

# ---- /q:back ----
out = cli("back", "away")
check("/q:back: summary with spend, queued, over-budget", "away 모드 끔" in out and "$120.00" in out and "줄 세운" in out and "예산 초과: 예" in out)
check("/q:back: away off afterwards", (w.state().get("away") or None) is None)
wz, _ = w.launch()
check("after /q:back: attended again (no deny)", not denied(wz))

# ---- 에이전트 수 예산 ----
g = S("agents")
cli("away", "agents", "2a", "3")
ga, _ = g.launch()
gb, _ = g.launch()
gc, _ = g.launch()
check("agent budget 2a: third spawn sees budget used -> serialized to 1 slot", not denied(ga) and not denied(gb) and denied(gc) and "agent budget" in reason(gc))

# ---- 카운터 복구 ----
c = S("recover")
_, x1 = c.launch()
_, x2 = c.launch()
_, x3 = c.launch()
st_path = os.path.join(T, "claude-subagent-slots", "recover.json")
st = json.load(open(st_path))
for k in st["running"]:
    st["running"][k]["t"] -= 60  # grace(10초) 밖으로
json.dump(st, open(st_path, "w"))
hook(c.base(hook_event_name="Stop", background_tasks=[{"id": x1, "type": "subagent", "status": "running"}]))
check("recover: Stop background_tasks drops bg agents that are gone (missed SubagentStop)", list(c.state()["running"]) == [x1])
meta = os.path.join(T, "tx", "recover", "subagents", f"agent-{x1}.meta.json")
json.dump({"toolUseId": "t", "finished": True}, open(meta, "w"))
hook(c.base(hook_event_name="Stop"))
check("recover: meta.json finished drops the entry", c.state()["running"] == {})
_, x4 = c.launch()
st = json.load(open(st_path))
st["running"][x4]["t"] -= 31 * 60
json.dump(st, open(st_path, "w"))
hook(c.base(hook_event_name="Stop"))
check("recover: stale entry (no transcript activity for 30 min) dropped", c.state()["running"] == {})
tid, _ = c.pre()  # 예약만 하고 시작이 오지 않음(다른 훅이 막음 등)
st = json.load(open(st_path))
st["reserved"][tid]["t"] -= 120
json.dump(st, open(st_path, "w"))
hook(c.base(hook_event_name="Stop"))
check("recover: reservation without start expires", c.state()["reserved"] == {})
c.launch()
c.launch()
out = cli("reset", "recover")
check("recover: manual reset clears counters", "비웠다" in out and c.state()["running"] == {} and c.state()["reserved"] == {})
check("recover: log records why", any(e["k"] == "recovered" and e.get("why") == "not-in-background_tasks" for e in c.state()["log"]))

# ---- 포그라운드 흐름: Start → Stop → Post(completed) ----
f = S("fg")
tid, _ = f.pre(bg=False)
hook(f.base(hook_event_name="SubagentStart", agent_id="afg1", agent_type="general-purpose"))
check("foreground: SubagentStart consumes the reservation", f.state()["reserved"] == {} and "afg1" in f.state()["running"])
f.stop_agent("afg1", [usage_line("f1", "claude-sonnet-5-5", out=1000)])
hook(f.base(hook_event_name="PostToolUse", tool_name="Agent", tool_use_id=tid, tool_input={},
            tool_response={"status": "completed", "agentId": "afg1", "resolvedModel": "claude-sonnet-5-5"}))
check("foreground: cost counted once across SubagentStop + PostToolUse", abs(L.total_usd(f.state()) - 0.01) < 1e-9)
hook(f.base(hook_event_name="SubagentStart", agent_id="wf1", agent_type="workflow-subagent"))
check("workflow-subagent counted as running", "wf1" in f.state()["running"])

# ---- SubagentStop 뒤에 늦게 쓰인 마지막 응답도 센다(sweep) ----
lag = S("lag")
_, la = lag.launch()
lag.stop_agent(la, [usage_line("l1", "claude-sonnet-5-5", out=1000)])
with open(os.path.join(T, "tx", "lag", "subagents", f"agent-{la}.jsonl"), "a") as fh:
    fh.write(usage_line("l2", "claude-sonnet-5-5", out=1000))
hook(lag.base(hook_event_name="Stop"))
hook(lag.base(hook_event_name="Stop"))
check("late transcript lines after SubagentStop are swept in once", abs(L.total_usd(lag.state()) - 0.02) < 1e-9)

# ---- 메인 트랜스크립트는 끝에서 시작해 이어서 센다 ----
m = S("main")
open(m.tp, "w").write(usage_line("old", "claude-opus-5-5", out=1_000_000))  # 훅이 보기 전 사용량은 소급하지 않는다
m.pre()
open(m.tp, "a").write(usage_line("new", "claude-opus-5-5", out=1000))
hook(m.base(hook_event_name="Stop"))
check("main: no backfill, then incremental", abs(L.total_usd(m.state()) - 0.02) < 1e-9)
check("main: inherit model learned from transcript tail", m.state()["main"].get("model") == "claude-opus-5-5")
_, oi = m.pre(model="")
check("inherit spawn counted as opus", m.state()["reserved"][f"toolu_main_{m.n}"]["fam"] == "opus")
sub_tp = os.path.join(T, "tx", "main", "subagents", "agent-z.jsonl")
hook(dict(session_id="main", transcript_path=sub_tp, cwd=PROJ, agent_id="z", hook_event_name="PreToolUse", tool_name="Agent",
          tool_use_id="nested", tool_input={"model": "sonnet"}))
check("nested spawn inside a subagent does not move the main offset", m.state()["main"]["off"] == os.path.getsize(m.tp))

# ---- 한도 % 예산 + 2단계 (사용자 결정 2026-11-10, .claude/audit/21 §5) ----
SL = os.path.join(HOME, "statusline", "harness-status.py")


def sline(sid, rl=None, env=None):
    d = {"session_id": sid, "model": {"display_name": "Opus"}}
    if rl is not None:
        d["rate_limits"] = rl
    return subprocess.run([sys.executable, "-I", SL], input=json.dumps(d), capture_output=True, text=True, env=env or ENV).stdout.strip()


def rl(p5=None, pw=None, r5=1_000_000, rw=9_000_000):
    o = {}
    if p5 is not None:
        o["five_hour"] = {"used_percentage": p5, "resets_at": r5}
    if pw is not None:
        o["seven_day"] = {"used_percentage": pw, "resets_at": rw}
    return o


def lim_file(sid):
    return os.path.join(T, "claude-subagent-slots", sid + ".limits.json")


A = {"five_hour": {"p": 20.0, "r": 1000}, "seven_day": {"p": 50.0, "r": 9000}, "t": time.time()}
P = lambda *a: L.parse_away(list(a), L.CFG_DEFAULTS, A)
check("parse: 30% -> pct, both windows", P("30%")["unit"] == "pct" and P("30%")["budget_pct"] == 30 and P("30%")["pct_win"] is None)
check("parse: 30%w -> seven_day, 30%5h -> five_hour", P("30%w")["pct_win"] == "seven_day" and P("30%5h")["pct_win"] == "five_hour")
check("parse: $5 usd, 6a agents, 2nd number = slots", P("$5")["budget_usd"] == 5 and P("6a")["budget_agents"] == 6 and P("$5", "3")["slots"] == 3 and P("30%", "3")["slots"] == 3)
check("parse: no args + limit data -> pct default 30", P()["unit"] == "pct" and P()["budget_pct"] == 30)
check("parse: no args + no limit data -> usd + plan-unknown", L.parse_away([], L.CFG_DEFAULTS, None)["unit"] == "usd" and L.parse_away([], L.CFG_DEFAULTS, None)["note"] == "plan-unknown")
check("parse: HARNESS_AWAY_PLAN=usd keeps usd even with limit data", L.parse_away([], dict(L.CFG_DEFAULTS, HARNESS_AWAY_PLAN="usd"), A)["unit"] == "usd")
check("parse: 30% without limit data falls back to usd (no-limits)", L.parse_away(["30%"], L.CFG_DEFAULTS, None)["note"] == "no-limits")
check("parse: explicit window missing -> other window (window-missing)", L.parse_away(["30%5h"], L.CFG_DEFAULTS, {"seven_day": A["seven_day"], "t": 1})["note"] == "window-missing")
for bad in (["0%"], ["abc"], ["5%x"]):
    try:
        L.parse_away(bad, L.CFG_DEFAULTS, A)
        check(f"parse: {bad} rejected", False)
    except ValueError:
        check(f"parse: {bad} rejected", True)

# statusline 이 한도 값을 파일에 적고, 줄에도 보인다
sline("pc", rl(20, 50))
check("statusline writes limits file from rate_limits", json.load(open(lim_file("pc")))["five_hour"]["p"] == 20)
check("statusline shows limits", "limit 5h 20% wk 50%" in sline("pc", rl(20, 50)))
sline("pc", {})
check("statusline: no rate_limits keeps the previous file", json.load(open(lim_file("pc")))["seven_day"]["p"] == 50)

# % 계산: /q:away 시점부터의 증가분, 가장 빡빡한 창이 먼저
pc = S("pc")
out = cli("away", "pc", "30%", "2")
check("/q:away 30%: pct budget on, both windows tracked", "한도 30%p" in out and "5h/week" in out and pc.state()["away"]["unit"] == "pct")
sline("pc", rl(40, 60))  # 5h +20, week +10
pa, ida = pc.launch()
pb, idb = pc.launch()
check("pct: +20%p of 30 -> not over (2 slots)", not denied(pa) and not denied(pb) and ctx(pa) == "")
check("pct statusline: AWAY +20/30% 5h", "AWAY +20/30% 5h slots 2" in sline("pc", rl(40, 60)))
sline("pc", rl(52, 65))  # 5h +32
pd = pc.pre()[1]
check("pct: 5h +32%p >= 30 -> over, 2 running -> queued with limit reason", denied(pd) and "5h limit +32%p" in reason(pd))
check("pct: level 1 stamp recorded", pc.state()["away"]["over_at"] and not pc.state()["away"]["over2_at"])
check("pct statusline: OVER", "AWAY OVER +32/30% 5h" in sline("pc", rl(52, 65)))
sline("pc", rl(81, 65))  # 5h +61 >= 60
pe = pc.pre()[1]
check("pct: +61%p >= 2x -> stage 2 halt", denied(pe) and re.match('<harness-hook name="subagent-slots" level="action"' + NONCE_RX + '>\nhalt:', reason(pe)))
check("pct statusline: HALT", "AWAY HALT" in sline("pc", rl(81, 65)))
_, wfl = pc.pre(tool="Workflow")
check("stage 2: Workflow also denied", denied(wfl) and "halt:" in reason(wfl))
check("stage 2: full instruction once, short afterwards", "progress file" in reason(pe) and "progress file" in reason(wfl) and len(reason(wfl)) < len(reason(pe)))
subprocess.run([sys.executable, "-I", os.path.join(H, "compact_epoch.py"), "q"], input=json.dumps({"session_id": "pc", "source": "compact"}), text=True, env=ENV)
pf = pc.pre()[1]
check("stage 2: full instruction again after compact (dedup per epoch)", "wait for the user" in reason(pf) and len(reason(pf)) > 300)
check("stage 2: denied calls reserve nothing and count as queued", pc.state()["reserved"] == {} and pc.state()["away"]["queued"] >= 4)
out = cli("back", "pc")
check("/q:back: stage 2 reached with time and pct growth", "2단계(새 서브에이전트 중단) 도달: 예" in out and "5h +" in out and "예산 초과: 예" in out)

# 남은 여유가 N 보다 작으면 한도 100% 가 문턱
cli("away", "room", "30%w")
sline("room", rl(10, 90))
r_ = S("room")
cli("away", "room", "30%w", "1")
sline("room", rl(10, 99))
ra = r_.pre()[1]
check("pct: week at 90% base, N=30 -> threshold is the remaining 10%p (not over at +9)", not denied(ra))
sline("room", rl(10, 100))
rb, _ = r_.launch()
rc = r_.pre()[1]
check("pct: reaching 100% of the window -> stage 2", denied(rc) and "halt:" in reason(rc))

# 창 리셋을 넘을 때: 리셋 전 증가분을 쌓고 새로 센다
sline("rs", rl(20, 50, r5=1000))
cli("away", "rs", "30%5h", "2")
rs = S("rs")
sline("rs", rl(45, 50, r5=1000))  # +25
rs.launch()
sline("rs", rl(3, 51, r5=19000))  # 리셋 → 25 + 3 = 28
ro = rs.pre()[1]
check("reset: 25 before + 3 after = 28 < 30 -> not over", not denied(ro) and rs.state()["away"]["pct"]["five_hour"]["acc"] == 25)
sline("rs", rl(6, 51, r5=19000))  # 31
rs.launch()  # 슬롯 1 개 남음 -> 2 번째
rp = rs.pre()[1]
check("reset: 25 + 6 = 31 >= 30 -> over (queued at 2 running)", denied(rp) and "5h limit +31%p" in reason(rp))
sline("rs", rl(7, 51, r5=19030))  # 30초 어긋난 resets_at 은 리셋이 아니다
check("reset: tiny resets_at jitter (<60s) is not a reset", rs.pre() and rs.state()["away"]["pct"]["five_hour"]["acc"] == 25)

# 값이 오래됐을 때: 마지막 증가분은 유지, USD 가드로 보강
sline("st", rl(20, 50))
cli("away", "st", "30%", "2")
stl = S("st")
d_ = json.load(open(lim_file("st")))
d_["t"] -= 15 * 60
json.dump(d_, open(lim_file("st"), "w"))
envg = dict(ENV, HARNESS_AWAY_BUDGET_USD="10")
stl.env = envg
_, sa = stl.launch()
stl.stop_agent(sa, [usage_line("s1", "claude-opus-5-5", out=750_000)])  # $15
sb = stl.pre()[1]
check("stale: no fresh limit data, USD $15 >= guard $10 -> level 1 reminder", ctx(sb).count("limit data stale") == 1 and "stale" in ctx(sb))
check("stale statusline shows (stale)", "(stale)" in sline("st", None, envg))
sline("st", rl(25, 50))  # 다시 신선
check("stale: fresh value again -> pct evaluated (+5, level 0), no guard", L.away_eval(json.load(open(os.path.join(T, "claude-subagent-slots", "st.json"))), json.load(open(lim_file("st"))), time.time(), False, envg)["level"] == 0)

# USD 2단계 + 에이전트 수 2단계 + Workflow allow 정책
os.environ.pop("HARNESS_AWAY_WORKFLOW", None)
envw = dict(ENV, HARNESS_AWAY_WORKFLOW="allow")
u = S("usd2", envw)
cli("away", "usd2", "$10", "2", env=envw)
_, ua = u.launch()
u.stop_agent(ua, [usage_line("u1", "claude-opus-5-5", out=600_000)])  # $12: 1 단계
u1, ub = u.launch()
check("usd2: $12 of $10 -> level 1 (allowed when idle, with reconsider warn)", not denied(u1) and "Away budget reached" in ctx(u1))
u.stop_agent(ub, [usage_line("u2", "claude-opus-5-5", out=500_000)])  # 누적 $22 >= $20
n_sp = u.state()["spawned"]
u2 = u.pre()[1]
_, uw = u.pre(tool="Workflow")
check("usd2: $22 >= 2x$10 -> Agent denied (halt)", denied(u2) and "halt:" in reason(u2))
check("usd2: Workflow denied even with HARNESS_AWAY_WORKFLOW=allow", denied(uw))
check("usd2: denied calls are not counted as spawned", u.state()["spawned"] == n_sp)
check("usd2: stage-2 time recorded and logged", u.state()["away"]["over2_at"] and any(e["k"] == "stage2" for e in u.state()["log"]))
check("usd2 statusline: HALT $22.00/$10", "AWAY HALT $22.00/$10" in sline("usd2", None, envw))
out = cli("back", "usd2", env=envw)
check("/q:back (usd): stage 2 line", "2단계(새 서브에이전트 중단) 도달: 예" in out)
g2 = S("ag2")
cli("away", "ag2", "1a", "3")
_, g2a = g2.launch()
g2.stop_agent(g2a)
g2b = g2.pre()[1]  # 1 개 띄운 뒤라 1 단계(비어 있으니 허용)
g2c = g2.pre()[1]  # 예약 1 + 띄운 2 -> 2 >= 2x1
check("agents 1a: level 1 allowed when idle, then 2 spawned -> stage 2", denied(g2c) and "halt:" in reason(g2c))
check("stage 2 never fires in attended mode", not denied(S("att2").pre()[1]))

# ---- 서브에이전트 안의 중첩 호출은 메인의 "회차당 한 번" 알림을 쓰지 않는다 ----
envn = dict(ENV, HARNESS_FANOUT_WARN_CONCURRENT="2")
nn = S("nest", envn)
nn.launch()
sub_pre = hook(dict(nn.base(hook_event_name="PreToolUse", tool_name="Agent", tool_use_id="nest-sub", agent_id="zz", agent_type="general-purpose",
                            tool_input={"model": "sonnet", "run_in_background": True})), envn)
check("nested (agent_id) call gets the fan-out warn", "Several subagents at once" in ctx(sub_pre))
_, main_pre = nn.pre()
check("main still gets its own fan-out warn after the subagent consumed one", "Several subagents at once" in ctx(main_pre))
_, main_pre2 = nn.pre()
check("main dedup within the burst is unchanged (silent)", ctx(main_pre2) == "")

# ---- away 중 메인 단독 작업: 모든 도구의 PostToolUse 에서 1·2단계 안내 ----
def post_read(sx, agent=None, env=None):
    d = sx.base(hook_event_name="PostToolUse", tool_name="Read", tool_use_id=f"r{time.time()}", tool_input={"file_path": "/x"}, tool_response={})
    if agent:
        d["agent_id"] = agent
    return hook(d, env or sx.env)


def force_eval(sx):  # 15초 간격 제한을 건너뛴다
    sp = os.path.join(T, "claude-subagent-slots", sx.sid + ".json")
    st_ = json.load(open(sp))
    st_["main_eval"] = 0
    json.dump(st_, open(sp, "w"))


check("main-solo: fast path file name == ledger state_path", os.path.basename(L.state_path("m1")) == "m1.json" and os.path.basename(os.path.dirname(L.state_path("m1"))) == "claude-subagent-slots")
m = S("m1")
check("main-solo: no state file -> silent", post_read(m) is None)
open(m.tp, "a").write(usage_line("mm1", "claude-opus-5-5", out=300_000))  # $7.5
check("main-solo: attended (no away) -> silent even with spend", post_read(m) is None)
cli("away", "m1", "$10", "2")
check("main-solo: away on, below budget -> silent", post_read(m) is None)
open(m.tp, "a").write(usage_line("mm2", "claude-opus-5-5", out=600_000))  # +$12 -> over $10
force_eval(m)
o1 = post_read(m)
check("main-solo: stage 1 -> one warn, PostToolUse event", 'level="warn"' in ctx(o1) and o1["hookSpecificOutput"]["hookEventName"] == "PostToolUse" and "Away budget reached" in ctx(o1))
check("main-solo: stage 1 only once per epoch", post_read(m) is None)
check("main-solo: stage 1 notice is not a deny", not denied(o1))
open(m.tp, "a").write(usage_line("mm3", "claude-opus-5-5", out=500_000))  # +$10 -> $22 >= 20
force_eval(m)
o2 = post_read(m)
check("main-solo: stage 2 -> action 'halt:' with progress-file instruction", 'level="action"' in ctx(o2) and "halt:" in ctx(o2) and "progress file" in ctx(o2))
check("main-solo: stage 2 only once per epoch", post_read(m) is None)
check("main-solo: nothing is stopped (no decision field)", "permissionDecision" not in json.dumps(o2) and "decision" not in o2)
check("main-solo: subagent (agent_id) call gets nothing", post_read(m, agent="zz") is None)
subprocess.run([sys.executable, "-I", os.path.join(H, "compact_epoch.py"), "q"], input=json.dumps({"session_id": "m1", "source": "compact"}), text=True, env=ENV)
check("main-solo: new compact epoch -> stage 2 again", "halt:" in ctx(post_read(m)))
m2 = S("m2")
open(m2.tp, "a").write(usage_line("mx1", "claude-opus-5-5", out=900_000))  # $22.5 before away
cli("away", "m2", "$10", "2")
check("main-solo: spend before /q:away is not counted", post_read(m2) is None)
open(m2.tp, "a").write(usage_line("mx2", "claude-opus-5-5", out=1_100_000))  # +$22 after away
force_eval(m2)
check("main-solo: stage 2 from the main's own spend", "halt:" in ctx(post_read(m2)))
_, d2 = m2.pre()
check("main-solo: later Agent deny is the short form (notice already given)", denied(d2) and "still in effect" in reason(d2))
a = S("m3")
_, aid3 = a.launch()
check("main-solo: Agent PostToolUse still tracks the running agent", aid3 in a.state()["running"])
check("main-solo: off switch -> silent", post_read(m2, env=dict(ENV, HARNESS_SUBAGENT_SLOTS="off")) is None)


def timeit(sx, n=20, **kw):
    t0 = time.perf_counter()
    for _ in range(n):
        post_read(sx, **kw)
    return (time.perf_counter() - t0) / n * 1000


base_ms = timeit(S("lat-none"))
t0 = time.perf_counter()
for _ in range(20):
    subprocess.run([sys.executable, "-I", "-c", "pass"], capture_output=True)
py_ms = (time.perf_counter() - t0) / 20 * 1000
cli("away", "lat-away", "$100")
away_ms = timeit(S("lat-away"))
print(f"latency per PostToolUse call: not-away {base_ms:.1f} ms, away {away_ms:.1f} ms (bare python -I startup {py_ms:.1f} ms)")
check("main-solo: not-away path costs < 10 ms over bare python startup", base_ms - py_ms < 10)

# ---- 끄기·잘못된 입력 ----
check("off switch -> no output", hook({"session_id": "off", "hook_event_name": "PreToolUse", "tool_name": "Agent", "tool_input": {}},
                                      dict(ENV, HARNESS_SUBAGENT_SLOTS="off")) is None)
bad = subprocess.run([sys.executable, "-I", os.path.join(H, "subagent-slots.py")], input="{no", capture_output=True, text=True, env=ENV)
check("bad stdin -> exit 0, silent", bad.returncode == 0 and not bad.stdout)
check("other tools ignored", hook({"session_id": "x", "hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {}}) is None)

# ---- statusline 스타일 (ANSI 를 벗긴 텍스트로 비교) ----
import re
ANSI = re.compile(r"\x1b\[[0-9;]*m")
git_proj = os.path.join(T, "gitproj")
os.makedirs(os.path.join(git_proj, ".git"))
open(os.path.join(git_proj, ".git", "HEAD"), "w").write("ref: refs/heads/feat-x\n")
SAMPLE = {"session_id": "sty", "model": {"display_name": "Opus"}, "effort": {"level": "high"}, "context_window": {"used_percentage": 34.4},
          "workspace": {"current_dir": git_proj, "project_dir": git_proj},
          "rate_limits": {"five_hour": {"used_percentage": 92, "resets_at": time.time() + 7530}, "seven_day": {"used_percentage": 50, "resets_at": time.time() + 400000}}}


def sty(style, extra=None, inp=SAMPLE, color=False):
    e = {k: v for k, v in ENV.items() if k != "NO_COLOR"}
    if not color:
        e["NO_COLOR"] = "1"
    e.update(extra or {}, HARNESS_STATUSLINE_STYLE=style)
    return subprocess.run([sys.executable, "-I", SL], input=json.dumps(inp), capture_output=True, text=True, env=e).stdout


plain = sty("plain").strip()
check("style plain", plain == "gitproj:feat-x · Opus high ctx 34% · limit 5h 92% wk 50% reset 2h05m", plain)
check("style plain: no cost for subscribers", "$" not in plain)
nerd = sty("nerd").strip()
check("style nerd: icons + same facts", "\uf07b gitproj:feat-x" in nerd and " │ " in nerd and "34%" in nerd and "92%" in nerd)
check("style minimal", sty("minimal").strip() == "Opus 34% · 5h 92%", sty("minimal"))
check("style off: empty, limits file still written", sty("off") == "" and json.load(open(lim_file("sty")))["five_hour"]["p"] == 92)
two = sty("plain", {"HARNESS_STATUSLINE_LINES": "2"}).splitlines()
check("two lines option", len(two) == 2 and two[0].startswith("gitproj") and two[1].startswith("limit"), two)
col = sty("plain", color=True)
check("color on: ANSI present, stripped equals plain", "\x1b[" in col and ANSI.sub("", col).strip() == plain)
check("color: 92% red, 34% green", "\x1b[31mlimit 5h 92%" in col and "\x1b[32mctx 34%" in col, col)
check("NO_COLOR respected", "\x1b[" not in sty("plain"))
nosub = dict(SAMPLE); nosub.pop("rate_limits"); nosub["cost"] = {"total_cost_usd": 3.5}
check("non-subscriber shows cost", "$3.50" in sty("plain", inp=nosub))
check("narrow COLUMNS drops trailing segments", sty("plain", {"COLUMNS": "50"}).strip() == "gitproj:feat-x · Opus high ctx 34%", sty("plain", {"COLUMNS": "50"}))
open(os.path.join(PROJ, ".claude", "harness.env"), "w").write("HARNESS_STATUSLINE_STYLE=minimal\n")
repo_out = subprocess.run([sys.executable, "-I", SL], input=json.dumps(dict(SAMPLE, workspace={"current_dir": PROJ, "project_dir": PROJ})),
                          capture_output=True, text=True, env={k: v for k, v in ENV.items() if k != "HARNESS_STATUSLINE_STYLE"}).stdout.strip()
check("repo harness.env sets style (env var unset)", repo_out == "Opus 34% · 5h 92%", repo_out)
os.remove(os.path.join(PROJ, ".claude", "harness.env"))

# ---- statusline: 설치된 q 찾기 ----
def sl_out(cfg_dir):
    env = dict(ENV, CLAUDE_CONFIG_DIR=cfg_dir)
    return subprocess.run([sys.executable, "-I", SL], input=json.dumps({"session_id": "away", "model": {"display_name": "Opus"}}),
                          capture_output=True, text=True, env=env)


def registry(entries):
    d = os.path.join(T, "cfg2")
    os.makedirs(os.path.join(d, "plugins"), exist_ok=True)
    json.dump({"version": 2, "plugins": {"q@claude-doctor-market": entries}}, open(os.path.join(d, "plugins", "installed_plugins.json"), "w"))
    return d


r = sl_out(os.path.join(T, "no-such-config"))
check("statusline: q not installed -> no agents/away segment, no error", r.returncode == 0 and r.stdout.strip() == "Opus" and r.stderr == "", (r.stdout, r.stderr))
r = sl_out(registry([{"scope": "user", "installPath": os.path.join(T, "gone")}]))
check("statusline: registry points at missing install -> omitted", r.returncode == 0 and "agents" not in r.stdout, r.stdout)
r = sl_out(registry([{"scope": "user", "installPath": os.path.join(T, "gone")}, {"scope": "local", "installPath": Q}]))
check("statusline: picks the install that exists", "agents" in r.stdout, r.stdout)
fake = os.path.join(T, "fakeq", "scripts")
os.makedirs(fake)
open(os.path.join(fake, "subagent_ledger.py"), "w").write("raise RuntimeError('broken')\n")
r = sl_out(registry([{"scope": "user", "installPath": Q}, {"scope": "local", "installPath": os.path.dirname(fake)}]))
check("statusline: narrower scope wins deterministically (broken copy -> omitted, no crash)", r.returncode == 0 and "agents" not in r.stdout, r.stdout)
r = sl_out(registry([{"scope": "user", "installPath": os.path.dirname(fake), "lastUpdated": "2026-01-01"}, {"scope": "user", "installPath": Q, "lastUpdated": "2026-02-01"}]))
check("statusline: same scope -> later lastUpdated wins", "agents" in r.stdout, r.stdout)

for name, ok in res:
    print(("PASS " if ok else "FAIL ") + name)
fails = [r for r in res if not r[1]]
print(f"{len(res) - len(fails)}/{len(res)}")
shutil.rmtree(T, ignore_errors=True)
sys.exit(1 if fails else 0)
