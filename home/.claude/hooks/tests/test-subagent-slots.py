#!/usr/bin/env python3
"""subagent-slots 훅·원장·statusline 회귀. 실행: python3 -I test-subagent-slots.py (exit 0 = 통과)

슬롯 계산, 예산 소진(USD·에이전트 수), 팬아웃 dedup(묶음·compact 회차), 카운터 복구, /away·/back, statusline, 비용 계산.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

H = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOME = os.path.dirname(H)
LEDGER = os.path.join(HOME, "lib", "subagent_ledger.py")
T = tempfile.mkdtemp(prefix="slots-")
PROJ = os.path.join(T, "proj")
os.makedirs(os.path.join(PROJ, ".claude"))
BASE_ENV = {k: v for k, v in os.environ.items() if not k.startswith(("HARNESS_SUBAGENT", "HARNESS_FANOUT", "HARNESS_AWAY", "HARNESS_SLOTS"))}
ENV = dict(BASE_ENV, TMPDIR=T, CLAUDE_PROJECT_DIR=PROJ)
res = []


def check(name, ok):
    res.append((name, bool(ok)))


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
sys.path.insert(0, os.path.join(HOME, "lib"))
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
check("attended: 4th concurrent -> warn", 'level="warn"' in ctx(outs[3][0]) and "Large fan-out" in ctx(outs[3][0]))
check("attended: never denies", not any(denied(o) for o, _ in outs))
check("attended: 5th in same burst -> silent (dedup)", ctx(outs[4][0]) == "")
for _, aid in outs:
    s.stop_agent(aid)
check("attended: running back to 0 after stops", s.state()["running"] == {})
o1, a1 = s.launch("opus")
o2, a2 = s.launch("opus")
check("attended: 1 opus silent, 2nd opus -> warn (new burst)", ctx(o1) == "" and "opus-or-above: 2" in ctx(o2))
subprocess.run([sys.executable, "-I", os.path.join(H, "rearm-on-compact.py")], input=json.dumps({"session_id": "att", "source": "compact"}), text=True, env=ENV)
o3, a3 = s.launch("opus")
check("attended: compact epoch re-arms the warn in the same burst", "Large fan-out" in ctx(o3))
_, ow = s.pre(tool="Workflow")
check("attended: Workflow -> warn, not denied", "Workflow requested" in ctx(ow) and not denied(ow))

# ---- 저장소 설정이 문턱을 덮어쓴다 ----
open(os.path.join(PROJ, ".claude", "harness.env"), "w").write("HARNESS_FANOUT_WARN_CONCURRENT=2\nHARNESS_HEAVY_WRAP=evil\n")
r = S("repo")
ra, _ = r.launch()
rb, _ = r.launch()
check("repo .claude/harness.env lowers the concurrent threshold", ctx(ra) == "" and "Large fan-out" in ctx(rb))
check("repo env only overrides slot keys", L.config(PROJ).get("HARNESS_HEAVY_WRAP") != "evil")
os.remove(os.path.join(PROJ, ".claude", "harness.env"))

# ---- away: 슬롯 2 로 줄 세우기 ----
w = S("away")
out = cli("away", "away", "100", "2")
check("/away prints confirmation", "away 모드 켬" in out and "슬롯 2" in out)
wa, ida = w.launch()
wb, idb = w.launch()
wc, idc = w.launch()
check("away: first two allowed", not denied(wa) and not denied(wb))
check("away: third denied with queue reason, level=action", denied(wc) and reason(wc).startswith('<harness-hook name="subagent-slots" level="action">\nqueue: wait for a running agent to finish, then spawn the next'))
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
check("budget over: 0 running -> allowed with reconsider warn", not denied(wf1) and 'level="warn"' in ctx(wf1) and "sonnet" in ctx(wf1))
w.stop_agent(idf)
wg, idg = w.launch()
check("budget over: reconsider warn only once", not denied(wg) and ctx(wg) == "")
check("budget over: never stops the session (deny is per call)", all(not denied(x) for x in (wf1, wg)))

# ---- statusline ----
sl = subprocess.run([sys.executable, "-I", os.path.join(HOME, "statusline", "harness-status.py")],
                    input=json.dumps({"session_id": "away", "model": {"display_name": "Opus"}, "context_window": {"used_percentage": 34.4},
                                      "cost": {"total_cost_usd": 12.4}}), capture_output=True, text=True, env=ENV).stdout.strip()
check("statusline: model, ctx, cost, agents, away OVER", sl.startswith("Opus ctx 34% · $12.40 · agents 1 (sonnet 1)") and "AWAY OVER $120.00/$100 slots 1" in sl)
t0 = time.time()
for _ in range(5):
    subprocess.run([sys.executable, "-I", os.path.join(HOME, "statusline", "harness-status.py")], input="{}", capture_output=True, text=True, env=ENV)
check("statusline: fast (<150ms per run)", (time.time() - t0) / 5 < 0.15)
check("statusline: survives empty input", subprocess.run([sys.executable, "-I", os.path.join(HOME, "statusline", "harness-status.py")], input="", capture_output=True, text=True, env=ENV).returncode == 0)

# ---- /back ----
out = cli("back", "away")
check("/back: summary with spend, queued, over-budget", "away 모드 끔" in out and "$120.00" in out and "줄 세운" in out and "예산 초과: 예" in out)
check("/back: away off afterwards", (w.state().get("away") or None) is None)
wz, _ = w.launch()
check("after /back: attended again (no deny)", not denied(wz))

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

# ---- 끄기·잘못된 입력 ----
check("off switch -> no output", hook({"session_id": "off", "hook_event_name": "PreToolUse", "tool_name": "Agent", "tool_input": {}},
                                      dict(ENV, HARNESS_SUBAGENT_SLOTS="off")) is None)
bad = subprocess.run([sys.executable, "-I", os.path.join(H, "subagent-slots.py")], input="{no", capture_output=True, text=True, env=ENV)
check("bad stdin -> exit 0, silent", bad.returncode == 0 and not bad.stdout)
check("other tools ignored", hook({"session_id": "x", "hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {}}) is None)

for name, ok in res:
    print(("PASS " if ok else "FAIL ") + name)
fails = [r for r in res if not r[1]]
print(f"{len(res) - len(fails)}/{len(res)}")
shutil.rmtree(T, ignore_errors=True)
sys.exit(1 if fails else 0)
