#!/usr/bin/env python3
"""handback 알림 회귀. 실행: python3 -I test-handback-notice.py (exit 0 = 통과)

검토가 아닌 서브에이전트 보고에 권고·선택지·열린 질문이 있으면 메인에 info 한 줄(에이전트마다 한 번)을 내는지 본다.
SubagentStop(분류, 대기) -> UserPromptSubmit(쉬는 메인에 새 턴으로 온 보고) 또는 PostToolBatch(일하는 중에 붙은 보고) 경로를
훅 입력 JSON 으로 흉내 낸다. 입력 모양은 claude 2.1.316 의 덤프(task-notification, agent-message hand-back, meta.json)를 따른다.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
HOOKS = os.path.join(os.path.dirname(HERE), "hooks")
HOOK = os.path.join(HOOKS, "second-opinion-nudge.py")
sys.path.insert(0, HOOKS)
import handback_notice as hn  # noqa: E402

T = tempfile.mkdtemp(prefix="so-handback-")
ENV = {k: v for k, v in os.environ.items() if not k.startswith("HARNESS_") and k not in ("CLAUDE_CONFIG_DIR", "CLAUDE_PROJECT_DIR")}
ENV.update(TMPDIR=os.path.join(T, "tmp"), HOME=os.path.join(T, "home"), XDG_STATE_HOME=os.path.join(T, "state"),
           QWREEY_HARNESS_SALT_FILE=os.path.join(T, "salt"))
os.makedirs(ENV["TMPDIR"])
os.makedirs(ENV["HOME"])
open(ENV["QWREEY_HARNESS_SALT_FILE"], "w").write("00" * 32)
ok = fail = 0

DESIGN = """I wrote the design draft. Nothing is committed.

**Key design choices**
1. Command surface is unchanged.

**Open questions in the doc, each with my recommendation**
- Q1: Empty folder or secret-free copy? Recommend: empty folder.
- Q2: Refuse or downgrade? Recommend: refuse.
"""
DESIGN_KO = "설계안을 썼습니다.\n\n### 사용자 결정 3가지 (권장 포함)\n1. compact 회차를 누가 올리나.\n"
TESTS_ONLY = """Done. All 43 tests pass and `sync-copies --check` exits 0.

### Changed files
- `a.py`, `b.py`

### Design choices
- Kept the old CLI.

### Open points
- The lock is held while deleting.
"""
PROBE = "Recommendation: adopt option B.\nOpen questions: Q1 should we keep A?\nDecide before Friday."


def check(name, cond):
    global ok, fail
    if cond:
        ok += 1
    else:
        fail += 1
        print("FAIL:", name)


def run(data, env=None):
    p = subprocess.run([sys.executable, "-I", HOOK], input=json.dumps(data), capture_output=True, text=True, env=env or ENV, timeout=20)
    assert p.returncode == 0, p.stderr
    return p.stdout.strip()


def ctx(out):
    return json.loads(out)["hookSpecificOutput"]["additionalContext"] if out else ""


def transcript(aid, meta, handback=None):
    p = os.path.join(T, f"agent-{aid}.jsonl")
    with open(p, "w") as f:
        f.write(json.dumps({"type": "user", "message": {"content": "task"}}) + "\n")
        if handback is not None:
            f.write(json.dumps({"type": "assistant", "message": {"content": [
                {"type": "tool_use", "name": "SubagentHandback", "input": {"message": handback}}]}}) + "\n")
    if meta is not None:
        json.dump(meta, open(p[:-6] + ".meta.json", "w"))
    return p


def sstop(sid, aid, last="", meta=None, handback=None, agent_type="general-purpose"):
    meta = {"agentType": agent_type, "description": f"Design {aid}", "spawnDepth": 1} if meta is None else meta
    run({"hook_event_name": "SubagentStop", "session_id": sid, "cwd": T, "agent_id": aid, "agent_type": agent_type,
         "agent_transcript_path": transcript(aid, meta or None, handback), "last_assistant_message": last})


def hb_prompt(aid, text):
    body = "\n".join("  " + l for l in text.splitlines())
    return (f'Another Claude session sent a message:\n<agent-message from="{aid}">\n[Subagent hand-back] The text below is the final report '
            f"of a subagent this session delegated to. The report follows:\n{body}\n</agent-message>")


def tn_prompt(aid, desc, result):
    return (f"<task-notification>\n<task-id>{aid}</task-id>\n<tool-use-id>toolu_x</tool-use-id>\n<status>completed</status>\n"
            f'<summary>Agent "{desc}" finished</summary>\n<result>{result}</result>\n</task-notification>')


def ups(sid, prompt, env=None, **kw):
    return run({"hook_event_name": "UserPromptSubmit", "session_id": sid, "cwd": T, "prompt": prompt, **kw}, env)


def batch(sid, calls=(), **kw):
    return run({"hook_event_name": "PostToolBatch", "session_id": sid, "cwd": T, "tool_calls": list(calls), **kw})


# 분류기
check("분류: 설계 보고(Open questions 굵은 줄 + Q 줄) → 냄", hn.carries_decisions(DESIGN))
check("분류: 한국어 '사용자 결정' 제목 → 냄", hn.carries_decisions(DESIGN_KO))
check("분류: 테스트 보고(Design choices, Open points) → 안 냄", not hn.carries_decisions(TESTS_ONLY))
check("분류: 한 줄짜리 권고 + 열린 질문 문구 둘 → 냄", hn.carries_decisions(PROBE))
check("분류: 코드 블록 안의 제목은 안 봄", not hn.carries_decisions("Done.\n```\n## Recommendations\n```\n"))
check("분류: 빈 글 → 안 냄", not hn.carries_decisions(""))

# 쉬는 메인: SubagentStop(hand-back 은 transcript 의 SubagentHandback 입력) -> UserPromptSubmit(hand-back)
sstop("s1", "a1", last="", handback=DESIGN)
out = ups("s1", hb_prompt("a1", DESIGN))
c = ctx(out)
check("hand-back 턴 → info 한 줄, nonce, 설명 이름", c.startswith('<harness-hook name="qwreey-advisor" level="info" nonce="')
      and '"Design a1"' in c and "qwreey-advisor:inherit-advisor" in c and "Skip this for" in c)
check("UserPromptSubmit 이벤트 이름", json.loads(out)["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit")
check("같은 에이전트 두 번째(task-notification 안내) → 조용", ups("s1", tn_prompt("a1", "Design a1", "This agent's report was delivered to you as a message from a1")) == "")
sstop("s1", "a1", last=DESIGN)
check("이어 받은 같은 에이전트가 다시 끝나도 → 조용", ups("s1", hb_prompt("a1", DESIGN)) == "" and batch("s1") == "")

# 테스트 보고는 조용, 상태 없이 prompt 만으로도 분류
sstop("s2", "a2", last=TESTS_ONLY)
check("테스트 보고 → 조용", ups("s2", hb_prompt("a2", TESTS_ONLY)) == "")
check("SubagentStop 기록이 없어도 prompt(task-notification result)로 분류", '"Plan B"' in ctx(ups("s2", tn_prompt("a3", "Plan B", DESIGN))))
check("일반 사용자 prompt → 조용", ups("s2", "please continue") == "")

# 일하는 중의 메인: PostToolBatch 가 대기 중인 것을 낸다
sstop("s3", "b1", last=DESIGN)
sstop("s3", "b2", last=DESIGN_KO)
out = batch("s3", [{"tool_name": "Bash", "tool_input": {"command": "ls"}}])
c = ctx(out)
check("PostToolBatch → 둘을 한 줄로", '"Design b1"' in c and '"Design b2"' in c and "reports from subagents" in c
      and json.loads(out)["hookSpecificOutput"]["hookEventName"] == "PostToolBatch")
check("한 번 낸 뒤 다음 묶음 → 조용", batch("s3") == "")
check("낸 뒤 그 보고의 hand-back 턴 → 조용", ups("s3", hb_prompt("b1", DESIGN)) == "")

# 이미 검토하는 중이거나 검토가 끝났으면 내지 않는다
sstop("s4", "c1", last=DESIGN)
check("같은 묶음에서 inherit-advisor fork 를 띄움 → 조용",
      batch("s4", [{"tool_name": "Agent", "tool_input": {"subagent_type": "fork", "prompt": "[qwreey-advisor:inherit] Review only.\nnext: x"}}]) == "")
sstop("s5", "c2", last=DESIGN)
rv = transcript("rv", {"agentType": "qwreey-advisor:reviewer", "description": "second opinion: plan", "spawnDepth": 1})
run({"hook_event_name": "SubagentStop", "session_id": "s5", "cwd": T, "agent_id": "rv", "agent_type": "qwreey-advisor:reviewer",
     "agent_transcript_path": rv})
check("보고 뒤에 검토가 끝났음 → 조용", ups("s5", hb_prompt("c2", DESIGN)) == "")
check("검토 자신의 보고 → 조용", ups("s5", hb_prompt("rv", DESIGN)) == "")
check("기록 없는 검토 보고(run 줄)도 조용", ups("s5", tn_prompt("zz", "second opinion: done", DESIGN + "\n[qwreey-advisor run: x]")) == "")

# 메인이 띄운 것만 대기로 둔다
sstop("s6", "d1", last=DESIGN, meta={"agentType": "general-purpose", "spawnDepth": 2, "parentAgentId": "w1"})
check("일꾼이 띄운 에이전트 → PostToolBatch 조용", batch("s6") == "")
sstop("s6", "d2", last=DESIGN, meta={})
check("meta 가 없으면 대기로 두지 않음(UserPromptSubmit 경로만)", batch("s6") == "")

# 서브에이전트 안, 끄기, off 등급
sstop("s7", "e1", last=DESIGN)
check("서브에이전트 안의 PostToolBatch → 조용", batch("s7", agent_id="w9") == "")
check("HARNESS_REVIEW_HANDBACK=off → 조용", ups("s7", hb_prompt("e1", DESIGN), env=dict(ENV, HARNESS_REVIEW_HANDBACK="off")) == "")
G = os.path.join(T, "offrepo")
subprocess.run(["git", "init", "-q", G], check=True, env=ENV)
sstop("s8", "e2", last=DESIGN)
check("off 등급 저장소 → 조용", run({"hook_event_name": "UserPromptSubmit", "session_id": "s8", "cwd": G, "prompt": hb_prompt("e2", DESIGN)},
                                  dict(ENV, HARNESS_REVIEW_TIERS="offrepo=off")) == "")
sstop("s9", "e3", last=DESIGN)
check("git 저장소가 아니어도 기본 등급으로 냄", ctx(ups("s9", hb_prompt("e3", DESIGN))) != "")

# 이어 받은 에이전트의 새 보고는 다시 본다, 토론 입장문은 내지 않는다
sstop("s10", "f1", handback=DESIGN)
check("첫 보고 → 냄", '"Design f1"' in ctx(ups("s10", hb_prompt("f1", DESIGN))))
sstop("s10", "f1", handback=DESIGN_KO)
check("이어 받아 다른 보고 → 다시 냄", '"Design f1"' in ctx(ups("s10", hb_prompt("f1", DESIGN_KO))))
sstop("s10", "f1", handback=DESIGN_KO)
check("같은 보고가 또 오면 → 조용", ups("s10", hb_prompt("f1", DESIGN_KO)) == "" and batch("s10") == "")
sstop("s11", "g1", handback=DESIGN, meta={"agentType": "general-purpose", "description": "debate: P round 1", "spawnDepth": 1})
check("토론 입장문(설명 debate:) → 조용", ups("s11", hb_prompt("g1", DESIGN)) == "" and batch("s11") == "")
check("SubagentStop 없이 온 토론 보고(task-notification 설명 토론) → 조용", ups("s11", tn_prompt("g2", "토론 Q 2라운드", DESIGN)) == "")

shutil.rmtree(T, ignore_errors=True)
print(f"{ok}/{ok + fail}")
sys.exit(1 if fail else 0)
