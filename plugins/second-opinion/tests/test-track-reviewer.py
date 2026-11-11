#!/usr/bin/env python3
"""track-reviewer·nudge(SubagentStop)·review-ledger --caller 회귀. 실행: python3 -I test-track-reviewer.py (exit 0 = 통과)
리뷰어 호출에 run 줄이 붙고, SubagentStop 이 transcript 의 그 줄로 호출자를 읽어 메인이 부른 리뷰어만 '최근 검토'로 기록하는지 본다."""
import json
import os
import re
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


def pre(sid, agent_id=None, st=R, prompt="Review the diff."):
    d = {"hook_event_name": "PreToolUse", "session_id": sid, "tool_name": "Agent", "tool_input": {"subagent_type": st, "prompt": prompt, "description": "x"}}
    if agent_id:
        d["agent_id"] = agent_id
    return hook("track-reviewer.py", d)


def transcript(name, first_content):
    p = os.path.join(T, name + ".jsonl")
    with open(p, "w") as f:
        f.write(json.dumps({"type": "user", "message": {"role": "user", "content": first_content}}) + "\n")
        f.write(json.dumps({"type": "assistant", "message": {"role": "assistant", "content": "ok"}}) + "\n")
    return p


def stop(sid, tpath):
    hook("second-opinion-nudge.py", {"hook_event_name": "SubagentStop", "session_id": sid, "agent_id": "r", "agent_type": R,
                                     "agent_transcript_path": tpath, "cwd": T})


last = lambda sid: os.path.exists(os.path.join(ENV["TMPDIR"], "claude-second-opinion", sid + ".last-review"))
LINE = re.compile(r"\n\n\[second-opinion run: ([0-9a-f-]{36}) caller=(main|subagent) scratch=(\S+)\]$")

# PreToolUse 주입: 메인
up = json.loads(pre("S1"))["hookSpecificOutput"]
m = LINE.search(up["updatedInput"]["prompt"])
check("주입: allow + updatedInput", up["hookEventName"] == "PreToolUse" and up["permissionDecision"] == "allow")
check("주입: 원래 prompt 유지, 끝에 run 줄(main)", m and up["updatedInput"]["prompt"].startswith("Review the diff.") and m.group(2) == "main")
check("주입: 다른 입력 필드 보존", up["updatedInput"]["subagent_type"] == R and up["updatedInput"]["description"] == "x")
check("주입: 스크래치 폴더 생성", m and m.group(3) == os.path.join(ENV["CLAUDE_AUDIT_SCRATCH"], m.group(1)) + "/" and os.path.isdir(m.group(3)))
# 일꾼
up2 = json.loads(pre("S1", agent_id="worker1"))["hookSpecificOutput"]
m2 = LINE.search(up2["updatedInput"]["prompt"])
check("주입: 일꾼이 부르면 caller=subagent", m2 and m2.group(2) == "subagent")
check("주입: 호출마다 다른 id", m and m2 and m.group(1) != m2.group(1))
# 리뷰어 아님, prompt 이미 줄이 있음
check("리뷰어 아닌 호출은 주입 없음", pre("S1", st="general-purpose") == "")
check("이미 run 줄이 있으면 다시 안 붙임", pre("S1", prompt=up["updatedInput"]["prompt"]) == "")

# SubagentStop: transcript 첫 user 메시지에서 caller
stop("S2", transcript("sub", up2["updatedInput"]["prompt"]))
check("transcript 에 caller=subagent → last-review 기록 안 함", not last("S2"))
stop("S3", transcript("main", up["updatedInput"]["prompt"]))
check("transcript 에 caller=main → 기록", last("S3"))
stop("S4", transcript("blocks", [{"type": "text", "text": up2["updatedInput"]["prompt"]}]))
check("content 가 블록 배열이어도 읽음(subagent)", not last("S4"))
stop("S5", transcript("noline", "Review the diff."))
check("줄이 없으면 main 으로 침(옛 동작)", last("S5"))
stop("S6", os.path.join(T, "missing.jsonl"))
check("transcript 가 없으면 main", last("S6"))
hook("second-opinion-nudge.py", {"hook_event_name": "SubagentStop", "session_id": "S7", "agent_id": "z", "agent_type": "general-purpose", "cwd": T})
check("리뷰어가 아닌 종료는 기록 안 함", not last("S7"))
# 브리프 안에 인용된 옛 줄보다 마지막 줄이 이긴다
quoted = "[second-opinion run: " + "0" * 8 + "-0000-0000-0000-" + "0" * 12 + " caller=main scratch=/x/]\n" + up2["updatedInput"]["prompt"]
stop("S8", transcript("quoted", quoted))
check("여러 줄이면 마지막 줄 기준", not last("S8"))

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
