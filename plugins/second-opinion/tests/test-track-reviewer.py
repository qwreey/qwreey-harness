#!/usr/bin/env python3
"""track-reviewer·nudge(SubagentStop)·review-ledger --caller 회귀. 실행: python3 -I test-track-reviewer.py (exit 0 = 통과)
같은 세션에서 메인과 일꾼이 리뷰어를 띄울 때 스크래치가 갈리고, 메인이 부른 리뷰어만 '최근 검토'로 기록되는지 본다."""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
HOOKS = os.path.join(os.path.dirname(HERE), "hooks")
LEDGER = os.path.join(os.path.dirname(HERE), "skills", "fresh-advisor", "scripts", "review-ledger.py")
T = tempfile.mkdtemp(prefix="so-track-")
ENV = {k: v for k, v in os.environ.items() if not k.startswith("HARNESS_") and k != "CLAUDE_CONFIG_DIR"}
ENV.update(TMPDIR=os.path.join(T, "tmp"), HOME=os.path.join(T, "home"), CLAUDE_AUDIT_SCRATCH=os.path.join(T, "audit"),
           XDG_STATE_HOME=os.path.join(T, "state"))
os.makedirs(ENV["TMPDIR"])
os.makedirs(ENV["HOME"])
ok = fail = 0
R = "second-opinion:reviewer"


def check(name, cond):
    global ok, fail
    if cond:
        ok += 1
    else:
        fail += 1
        print("FAIL:", name)


def hook(name, data):
    p = subprocess.run([sys.executable, "-I", os.path.join(HOOKS, name)], input=json.dumps(data), capture_output=True, text=True, env=ENV, timeout=20)
    assert p.returncode == 0, p.stderr
    return p.stdout.strip()


def pre(sid, agent_id=None, st=R):
    d = {"hook_event_name": "PreToolUse", "session_id": sid, "tool_name": "Agent", "tool_input": {"subagent_type": st}}
    if agent_id:
        d["agent_id"] = agent_id
    return hook("track-reviewer.py", d)


def start(sid, aid, agent_type=R):
    return hook("track-reviewer.py", {"hook_event_name": "SubagentStart", "session_id": sid, "agent_id": aid, "agent_type": agent_type})


def stop(sid, aid):
    hook("second-opinion-nudge.py", {"hook_event_name": "SubagentStop", "session_id": sid, "agent_id": aid, "agent_type": R, "cwd": T})


last = lambda sid: os.path.exists(os.path.join(ENV["TMPDIR"], "claude-second-opinion", sid + ".last-review"))

# SubagentStart 주입
out = start("S1", "aA")
ctx = json.loads(out)["hookSpecificOutput"]
scratch = os.path.join(ENV["CLAUDE_AUDIT_SCRATCH"], "S1", "aA")
check("SubagentStart: additionalContext 에 스크래치 경로", ctx["hookEventName"] == "SubagentStart" and f"Your scratch directory is {scratch}/" in ctx["additionalContext"])
check("SubagentStart: 폴더 생성", os.path.isdir(scratch))
check("다른 에이전트 종류는 주입 없음", start("S1", "aB", "general-purpose") == "" and not os.path.exists(os.path.join(ENV["CLAUDE_AUDIT_SCRATCH"], "S1", "aB")))
check("이상한 agent_id 는 폴더를 만들지 않음", start("S1", "../x") == "")

# 일꾼이 띄운 리뷰어: 최근 검토로 세지 않는다
pre("S2", agent_id="worker1")
start("S2", "rW")
stop("S2", "rW")
check("일꾼이 부른 리뷰어 종료 → last-review 기록 안 함", not last("S2"))
# 메인이 띄운 리뷰어
pre("S3")
start("S3", "rM")
stop("S3", "rM")
check("메인이 부른 리뷰어 종료 → last-review 기록", last("S3"))
# 섞임: 일꾼이 띄우고 메인이 띄운 뒤 순서대로 시작
pre("S4", agent_id="worker1")
pre("S4")
start("S4", "r1")
start("S4", "r2")
stop("S4", "r1")
check("일꾼 것이 먼저 끝나도 메인 기록은 없음", not last("S4"))
stop("S4", "r2")
check("그다음 메인 것이 끝나면 기록", last("S4"))
# 리뷰어 아닌 호출은 대기열에 안 들어간다
pre("S5", st="general-purpose")
pre("S5")
start("S5", "rX")
stop("S5", "rX")
check("리뷰어 아닌 Agent 호출은 대기열에 안 섞임", last("S5"))
# 짝을 모르면 main 으로 친다(옛 동작 유지)
start("S6", "rY")
stop("S6", "rY")
check("호출자를 모르면 기록(옛 동작)", last("S6"))
# agent_type 이 다르면 기록 안 함
hook("second-opinion-nudge.py", {"hook_event_name": "SubagentStop", "session_id": "S7", "agent_id": "z", "agent_type": "general-purpose", "cwd": T})
check("리뷰어가 아닌 종료는 기록 안 함", not last("S7"))

# ledger --caller
def led(*a):
    return subprocess.run([sys.executable, "-I", LEDGER, *a], capture_output=True, text=True, env=ENV)

base = ["add", "--kind", "done", "--reviewer", "opus-sub", "--verdict", "진행"]
check("ledger add --caller subagent", led(*base, "--caller", "subagent").returncode == 0)
check("ledger add --caller 잘못된 값 거부", led(*base, "--caller", "x").returncode != 0)
check("ledger add --caller 없이도 동작", led(*base).returncode == 0)
recs = [json.loads(l) for l in open(os.path.join(ENV["XDG_STATE_HOME"], "claude-second-opinion", "ledger.jsonl"))]
check("ledger 기록에 caller", recs[0]["caller"] == "subagent" and recs[1]["caller"] == "")
with open(os.path.join(ENV["XDG_STATE_HOME"], "claude-second-opinion", "ledger.jsonl"), "a") as f:  # caller 없는 옛 기록
    f.write(json.dumps({"ts": "2025", "repo": "r", "kind": "done", "reviewer": "opus-sub", "verdict": "진행"}) + "\n")
s = led("stats")
check("stats 가 옛 기록도 읽음", s.returncode == 0 and "3건" in s.stdout and "caller / subagent" in s.stdout)

shutil.rmtree(T, ignore_errors=True)
print(f"{ok}/{ok + fail}")
sys.exit(1 if fail else 0)
