#!/usr/bin/env python3
"""second-opinion-nudge 회귀. 실행: python3 -I test-second-opinion-nudge.py (exit 0 = 통과)

임시 HOME(.claude/{lib,harness.env})과 임시 git 저장소를 만들고 플러그인의 훅(hooks/second-opinion-nudge.py)에 이벤트 JSON 을 넣어 본다.
lib 는 claude-doctor 정본(home/.claude/lib)을 복사해 쓴다. 하네스가 없는 환경(lib·harness.env 없음)도 따로 본다.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
HOOK = os.path.join(os.path.dirname(HERE), "hooks", "second-opinion-nudge.py")
DOCTOR = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
T = tempfile.mkdtemp(prefix="so-nudge-")
CH = os.path.join(T, "home", ".claude")
shutil.copytree(os.path.join(DOCTOR, "home", ".claude", "lib"), os.path.join(CH, "lib"), ignore=shutil.ignore_patterns("__pycache__"))
open(os.path.join(CH, "harness.env"), "w").write("HARNESS_REVIEW_TIERS=hi=high docs=off\nHARNESS_REVIEW_LINES=high=10 mid=50\n")
ENV = {k: v for k, v in os.environ.items() if not k.startswith("HARNESS_") and k not in ("CLAUDE_CONFIG_DIR", "CLAUDE_PROJECT_DIR")}
ENV.update(TMPDIR=os.path.join(T, "tmp"), HOME=os.path.join(T, "home"), GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t",
           GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")
os.makedirs(ENV["TMPDIR"])
ENV["QWREEY_HARNESS_SALT_FILE"] = os.path.join(T, "salt")  # nonce 는 고정 salt 로
open(ENV["QWREEY_HARNESS_SALT_FILE"], "w").write("00" * 32)
ok = fail = 0


def repo(name):
    d = os.path.join(T, name)
    os.makedirs(d)
    subprocess.run(["git", "init", "-q", d], check=True, env=ENV)
    open(os.path.join(d, "a.txt"), "w").write("x\n")
    subprocess.run(["git", "-C", d, "add", "."], check=True, env=ENV)
    subprocess.run(["git", "-C", d, "commit", "-qm", "init"], check=True, env=ENV)
    return d


def run(data, env=None):
    p = subprocess.run([sys.executable, "-I", HOOK], input=json.dumps(data), capture_output=True, text=True, env=env or ENV, timeout=20)
    assert p.returncode == 0, p.stderr
    return p.stdout.strip()


def check(name, cond):
    global ok, fail
    if cond:
        ok += 1
    else:
        fail += 1
        print("FAIL:", name)


HI, MID, DOCS = repo("hi"), repo("mid"), repo("docs")
for d, n in ((HI, 20), (MID, 20), (DOCS, 200)):
    open(os.path.join(d, "b.txt"), "w").write("y\n" * n)
    subprocess.run(["git", "-C", d, "add", "b.txt"], check=True, env=ENV)

commit = lambda d, sid="s1", **kw: run({"hook_event_name": "PreToolUse", "session_id": sid, "cwd": d, "tool_name": "Bash",
                                        "tool_input": {"command": "git commit -m 'x'"}, **kw})
out = commit(HI)
ctx = json.loads(out)["hookSpecificOutput"]["additionalContext"] if out else ""
check("high: 20줄 커밋 → 알림", ctx.startswith('<harness-hook name="qwreey-advisor" level="warn" nonce="985461182738">') and "model=opus" in ctx)
check("알림은 플러그인 이름을 쓴다", "qwreey-advisor:fresh-advisor" in ctx and "subagent_type=qwreey-advisor:reviewer" in ctx)
check("같은 diff 두 번째 → 조용", commit(HI) == "")
open(os.path.join(HI, "c.txt"), "w").write("z\n" * 30)
subprocess.run(["git", "-C", HI, "add", "c.txt"], check=True, env=ENV)
check("알림 직후 다른 diff 라도 쿨다운 동안 조용", commit(HI) == "")
check("mid: 20줄 < 50 → 조용", commit(MID) == "")
check("off 등급 → 조용", commit(DOCS) == "")
check("서브에이전트 안 → 조용", commit(HI, sid="s2", agent_id="agent-x") == "")
check("git 아닌 명령 → 조용", run({"hook_event_name": "PreToolUse", "session_id": "s3", "cwd": HI, "tool_name": "Bash",
                                    "tool_input": {"command": "git status"}}) == "")

run({"hook_event_name": "SubagentStop", "session_id": "s4", "cwd": HI, "agent_type": "qwreey-advisor:reviewer"})
check("최근 검토(qwreey-advisor:reviewer)가 있으면 → 조용", commit(HI, sid="s4") == "")
run({"hook_event_name": "SubagentStop", "session_id": "s4b", "cwd": HI, "agent_type": "general-purpose"})
check("다른 에이전트 종료는 검토로 치지 않음", commit(HI, sid="s4b") != "")

fail_ev = lambda sid, err, cmd="luau-lsp analyze src": run({"hook_event_name": "PostToolUseFailure", "session_id": sid, "cwd": MID,
                                                         "tool_name": "Bash", "tool_input": {"command": cmd}, "error": err})
check("실패 1회 → 조용", fail_ev("s5", "Exit code 1\nsrc/a.luau(12,3): TypeError: x") == "")
out = fail_ev("s5", "Exit code 1\nsrc/a.luau(14,9): TypeError: x")
check("같은 서명(숫자만 다름) 2회 → stuck 알림, mid 는 sonnet", "kind=stuck" in out and "model=sonnet" in out)
check("3회째 → 조용", fail_ev("s5", "Exit code 1\nsrc/a.luau(15,9): TypeError: x") == "")
check("grep 의 exit 1 은 무시", fail_ev("s6", "Exit code 1", "grep foo x") == "" and fail_ev("s6", "Exit code 1", "grep foo x") == "")

stop = lambda sid, env=None, **kw: run({"hook_event_name": "Stop", "session_id": sid, "cwd": HI, "stop_hook_active": False,
                                         "last_assistant_message": "Done: changed the parser.", **kw}, env)
check("Stop 기본 꺼짐", stop("s7") == "")
env_on = dict(ENV, HARNESS_REVIEW_STOP="1")
check("Stop 켜면 알림", "Turn ending" in stop("s8", env_on))
check("stop_hook_active 면 조용", stop("s9", env_on, stop_hook_active=True) == "")
check("빈 답이면 조용", stop("s9b", env_on, last_assistant_message="") == "")
check("오류·한도 알림이면 조용", stop("s9c", env_on, last_assistant_message="Prompt is too long") == "")
check("사용자에게 묻는 답이면 조용", stop("s9d", env_on, last_assistant_message="Which one do you want?\n1. A\n2. B") == "")
check("굵은 질문 끝도 질문", stop("s9e", env_on, last_assistant_message="**어느 쪽으로 할까요?**") == "")

plan = lambda sid, text, mode: run({"hook_event_name": "PreToolUse", "session_id": sid, "cwd": HI, "tool_name": "ExitPlanMode",
                                     "tool_input": {"plan": text}}, dict(ENV, HARNESS_REVIEW_PLAN=mode))
out = plan("s10", "do X", "deny")
check("plan deny → permissionDecision deny + action", '"deny"' in out and 'level=\\"action\\"' in out)
check("plan 표시 있으면 통과", plan("s10", "do X\nqwreey-advisor: reviewed", "deny") == "")

# 저장소 개인 층(.claude/harness.local.env)이 사용자 층의 등급을 덮는다. 저장소는 훅 cwd 로 안다.
LOC = repo("loc")
open(os.path.join(LOC, "b.txt"), "w").write("y\n" * 20)
subprocess.run(["git", "-C", LOC, "add", "b.txt"], check=True, env=ENV)
loc_commit = lambda sid: run({"hook_event_name": "PreToolUse", "session_id": sid, "cwd": LOC, "tool_name": "Bash",  # noqa: E731
                              "tool_input": {"command": "git commit -m x"}})
check("층: 사용자 층만이면 mid, 20줄 -> 조용", loc_commit("s12") == "")
os.makedirs(os.path.join(LOC, ".claude"))
open(os.path.join(LOC, ".claude", "harness.local.env"), "w").write("HARNESS_REVIEW_TIERS=loc=high\n")
check("층: harness.local.env 가 high 로 -> 알림(opus)", "model=opus" in loc_commit("s13"))

# 같은 명령의 git add: PreToolUse 때 index 는 비어 있으므로 명령이 스테이징할 범위로 잰다 (hi 등급 임계 10)
def fresh_repo(name):
    d = repo(name)
    open(os.path.join(d, ".gitignore"), "w").write("ign/\n")
    subprocess.run(["git", "-C", d, "add", ".gitignore"], check=True, env=ENV)
    subprocess.run(["git", "-C", d, "commit", "-qm", "ig"], check=True, env=ENV)
    return d


def bash(d, cmd, sid, env=None):
    return run({"hook_event_name": "PreToolUse", "session_id": sid, "cwd": d, "tool_name": "Bash", "tool_input": {"command": cmd}}, env)


env_hi = dict(ENV, HARNESS_REVIEW_TIERS="add1=high add2=high add3=high add4=high add5=high add6=high add7=high")
A1 = fresh_repo("add1")
open(os.path.join(A1, "a.txt"), "a").write("m\n" * 12)
check("add <tracked path> && commit → 알림(예전에는 0줄)", "12 changed lines" in bash(A1, "git add a.txt && git commit -qm x", "c1", env_hi))
A2 = fresh_repo("add2")
os.makedirs(os.path.join(A2, "sub"))
open(os.path.join(A2, "sub", "new.py"), "w").write("n\n" * 15)
os.makedirs(os.path.join(A2, "ign"))
open(os.path.join(A2, "ign", "big.txt"), "w").write("i\n" * 500)
out = bash(A2, 'git add -A && git commit -m "$(cat <<EOF\nmsg\nEOF\n)" 2>&1 | tail -3', "c2", env_hi)
check("add -A: 추적 안 된 파일 줄 수, .gitignore 는 제외", "15 changed lines" in out)
check("add <다른 경로> 만 → 그 경로만 잼(sub 밖 0줄 → 조용)", bash(A2, "git add a.txt && git commit -m x", "c3", env_hi) == "")
check("cd sub && git add . && commit → sub 의 새 파일", "15 changed lines" in bash(A2, "cd sub && git add . && git commit -m x", "c4", env_hi))
check("다른 저장소에서 git -C <repo> add && commit → 그 저장소를 잰다", "`add2`" in bash(MID, f"git -C {A2} add sub && git -C {A2} commit -m x", "c5", env_hi))
A3 = fresh_repo("add3")
open(os.path.join(A3, "a.txt"), "a").write("q\n" * 11)
check("git commit -am → HEAD 대비(예전과 같음)", "11 changed lines" in bash(A3, "git commit -am x", "c6", env_hi))
check("git commit <경로> → 그 경로", "11 changed lines" in bash(A3, "git commit -m x -- a.txt", "c7", env_hi))
check("git add -u && commit → 추적 파일", "11 changed lines" in bash(A3, "git add -u; git commit -m x", "c8", env_hi))
check("읽을 수 없는 명령(add $VAR)은 예전 방식(--cached, 0줄 → 조용)", bash(A3, "git add $F && git commit -m x", "c9", env_hi) == "")
check("add -p 는 예전 방식", bash(A3, "git add -p && git commit -m x", "c10", env_hi) == "")
check("commit --dry-run 은 조용", bash(A3, "git add a.txt && git commit --dry-run -m x", "c11", env_hi) == "")
A4 = fresh_repo("add4")
open(os.path.join(A4, "a.txt"), "a").write("s\n" * 6)
subprocess.run(["git", "-C", A4, "add", "a.txt"], check=True, env=ENV)
open(os.path.join(A4, "c.txt"), "w").write("t\n" * 6)
check("이미 스테이징된 것 + 같은 명령의 add 를 합침(6+6)", "12 changed lines" in bash(A4, "git add c.txt && git commit -m x", "c12", env_hi))

# inherit-advisor fork 가 끝났으면 최근 검토로 친다
ftp = os.path.join(T, "fork.jsonl")
with open(ftp, "w") as f:
    f.write(json.dumps({"type": "fork-context-ref"}) + "\n")
    f.write(json.dumps({"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Agent",
                                                                       "input": {"prompt": "[qwreey-advisor:inherit] Review only.\nnext: x"}}]}}) + "\n")
run({"hook_event_name": "SubagentStop", "session_id": "c13", "cwd": A1, "agent_id": "fk", "agent_type": "fork", "agent_transcript_path": ftp})
check("inherit fork 검토 뒤 → 커밋 알림 없음", bash(A1, "git add a.txt && git commit -qm x", "c13", env_hi) == "")

# 하네스 없는 환경: lib, harness.env 가 없어도 기본값(mid, 200줄)으로 돈다
bare = dict(ENV, HOME=os.path.join(T, "bare"))
os.makedirs(os.path.join(T, "bare"))
BIG = repo("big")
open(os.path.join(BIG, "d.txt"), "w").write("w\n" * 250)
subprocess.run(["git", "-C", BIG, "add", "d.txt"], check=True, env=ENV)
out = run({"hook_event_name": "PreToolUse", "session_id": "s11", "cwd": BIG, "tool_name": "Bash",
           "tool_input": {"command": "git commit -m x"}}, bare)
check("하네스 없음: mid 기본, 250줄 → 알림(sonnet)", "model=sonnet" in out)

shutil.rmtree(T, ignore_errors=True)
print(f"{ok}/{ok + fail}")
sys.exit(1 if fail else 0)
