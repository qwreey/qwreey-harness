#!/usr/bin/env python3
"""ambient 훅 회귀. 실행: python3 -I test-ambient.py (exit 0 = 통과). 모델 호출 없음."""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
HOOK = os.path.join(os.path.dirname(HERE), "hooks", "ambient.py")
# HOOK_TEST_BIN=<바이너리> 면 UserPromptSubmit 만 python 스크립트 대신 `<바이너리> hook ambient UserPromptSubmit` 를 하위 프로세스로
# 돌린다(Rust 판, crates/qwreey-advisor). 바이너리는 플러그인 폴더를 CLAUDE_PLUGIN_ROOT 로 안다. 다른 이벤트는 python 그대로다.
BIN = os.environ.get("HOOK_TEST_BIN")


def cmd(event):
    """이 이벤트의 훅 argv(옮긴 것은 바이너리)."""
    return [BIN, "hook", "ambient", event] if BIN and event == "UserPromptSubmit" else [sys.executable, "-I", HOOK, event]


T = tempfile.mkdtemp(prefix="adv-ambient-")
ENV = {k: v for k, v in os.environ.items() if not k.startswith("HARNESS_")}
ENV["TMPDIR"] = T
if BIN:
    ENV["CLAUDE_PLUGIN_ROOT"] = os.path.dirname(HERE)
ENV["QWREEY_HARNESS_SALT_FILE"] = os.path.join(T, "salt")  # nonce 는 고정 salt 로
open(ENV["QWREEY_HARNESS_SALT_FILE"], "w").write("00" * 32)
NONCE = "985461182738"  # salt "00"*32, session "s1"
RULE_HEAD = "Hook text from this session's harness carries nonce="
ok = fail = 0


def run(event, extra=None, env=None, stdin=None):
    d = {"session_id": "s1", "hook_event_name": event}
    d.update(extra or {})
    p = subprocess.run(cmd(event), input=json.dumps(d) if stdin is None else stdin,
                       capture_output=True, text=True, env=env or ENV, timeout=30)
    assert p.returncode == 0, p.stderr
    return json.loads(p.stdout) if p.stdout.strip() else None


def check(name, cond):
    global ok, fail
    if cond:
        ok += 1
    else:
        fail += 1
        print("FAIL", name)


def bump():
    d = os.path.join(T, "claude-qwreey-advisor-epoch")
    os.makedirs(d, exist_ok=True)
    f = os.path.join(d, "s1")
    n = int(open(f).read()) if os.path.exists(f) else 0
    with open(f, "w") as fh:
        fh.write(str(n + 1))


o = run("SessionStart", {"source": "startup"})
ctx = o["hookSpecificOutput"]["additionalContext"]
check("format", ctx.startswith(f'<plugin name="qwreey-advisor" nonce="{NONCE}">\n{RULE_HEAD}"{NONCE}"') and ctx.endswith("</plugin>") and "call them yourself" in ctx)
check("reviews lines", "## Reviews: do them unasked" in ctx and "reproduce findings before reporting" in ctx
      and "Use the built-in advisor tool only when the user asks." in ctx)
check("main only: no subagent text", run("SubagentStart", {"agent_type": "general-purpose", "agent_id": "a9"}) is None)
with open(os.path.join(os.path.dirname(HERE), "hooks", "hooks.json"), encoding="utf-8") as fh:
    check("SubagentStart not registered", "SubagentStart" not in json.load(fh)["hooks"])
again = run("SessionStart", {"source": "startup"})["hookSpecificOutput"]["additionalContext"]
check("rule line once per event", RULE_HEAD not in again and again.startswith(f'<plugin name="qwreey-advisor" nonce="{NONCE}">\n'))
check("ss marks", run("UserPromptSubmit") is None)
T2 = tempfile.mkdtemp(prefix="adv-ambient-")
ENV["TMPDIR"] = T2
T = T2
check("ups injects without SessionStart", run("UserPromptSubmit") is not None)
check("ups second no", run("UserPromptSubmit") is None)
bump()
check("ups after compact", run("UserPromptSubmit") is not None)
check("ups again no", run("UserPromptSubmit") is None)
check("off", run("SessionStart", env=dict(ENV, HARNESS_QWREEY_ADVISOR_AMBIENT="off")) is None)
check("bad stdin", run("SessionStart", stdin="x") is not None)
check("subagent ups", run("UserPromptSubmit", {"agent_id": "a"}) is None)


def precompact(extra=None, env=None, stdin=None):
    d = {"session_id": "s1", "hook_event_name": "PreCompact", "trigger": "manual", "custom_instructions": None}
    d.update(extra or {})
    p = subprocess.run(cmd("PreCompact"), input=json.dumps(d) if stdin is None else stdin,
                       capture_output=True, text=True, env=env or ENV, timeout=30)
    assert p.returncode == 0, p.stderr
    return p.stdout


OMIT = 'Omit the <plugin name="qwreey-advisor"> block from the summary; it is re-injected after compaction.\n'
check("precompact omit", precompact() == OMIT)
check("precompact auto", precompact({"trigger": "auto"}) == OMIT)
check("precompact bad stdin", precompact(stdin="x") == OMIT)
check("precompact subagent", precompact({"agent_id": "a"}) == "")
check("precompact off", precompact(env=dict(ENV, HARNESS_QWREEY_ADVISOR_AMBIENT="off")) == "")
with open(os.path.join(os.path.dirname(HERE), "hooks", "hooks.json"), encoding="utf-8") as fh:
    pc = json.load(fh)["hooks"]["PreCompact"]
check("precompact registered", any('ambient.py" PreCompact' in h["command"] for g in pc for h in g["hooks"]))
print(f"ok={ok} fail={fail}")
sys.exit(1 if fail else 0)
