#!/usr/bin/env python3
"""second-opinion-nudge — 정해진 시점에 '독립 검토를 받을 때'라고 알린다. 막지 않는다(ExitPlanMode 선택 기능 제외).

advisor 는 언제 불릴지 모델이 정해서 예측이 안 됐다(.claude/scopes/plugins/qwreey-advisor/audit/18). 이 훅은 잴 수 있는 시점만 맡는다.
  1. PostToolUseFailure   같은 실패 서명이 이번 회차에 2번째 → stuck 검토 권고 (서명마다 한 번)
  2. PreToolUse(Bash)     `git commit` 이고 커밋될 diff 가 등급 임계 이상, 최근 검토 없음 → done 검토 권고
     같은 명령이 `git add <경로>|-A|.|-u` 나 `git commit -a|<경로>` 로 스테이징하면 그 범위까지 잰다(commit_scope.py).
  3. Stop                 (기본 꺼짐, HARNESS_REVIEW_STOP=1) 커밋 안 된 diff 가 임계 이상, 최근 검토 없음 → done 검토 권고
     Stop 의 additionalContext 는 턴을 이어 가게 하므로 HOOK-MESSAGES.md 의 Stop 규칙을 따른다: stop_hook_active, 빈 답,
     오류·한도 알림, 사용자에게 묻는 질문으로 끝난 답이면 내지 않는다(stop_passes).
  4. PreToolUse(ExitPlanMode) (기본 꺼짐, HARNESS_REVIEW_PLAN=deny|warn) high 등급에서 계획 검토 요구
  5. SubagentStop(모든 에이전트)  검토(qwreey-advisor:reviewer, inherit-advisor fork)면 메인이 부른 것만 최근 검토 시각을 기록하고
     ledger 에 자동 행을 남긴다(review_record.py). 검토가 아니면 보고에 권고·질문이 있는지 기록한다(handback_notice.py).
  6. UserPromptSubmit, PostToolBatch (메인)  5 에서 권고·질문이 있던 보고가 메인에 들어오면 info 한 줄(에이전트마다 한 번)
'접근 확정 전'은 잴 수 없어서 메인 판단(CLAUDE.md, 스킬)에 맡긴다. 이 저장소들에서 ExitPlanMode 사용은 0회였다(.claude/scopes/plugins/qwreey-advisor/audit/18 §1.4).

설치: qwreey-advisor 플러그인의 hooks/hooks.json 이 등록한다. 설정은 harness.env 층(늘 옆의 harness_env.py
사본): 사용자 $CLAUDE_CONFIG_DIR/harness.env < 저장소 .claude/harness.env < 저장소 .claude/harness.local.env < 환경 변수.
파일이 하나도 없으면 내장 기본값으로 돈다(등급 mid, 상태는 $TMPDIR).

규칙
  - 서브에이전트 안(agent_id 있음)에서는 SubagentStop 기록 말고는 아무것도 하지 않는다. 일꾼이 리뷰어를 또 띄우는 연쇄를 막는다($589 사고, .claude/audit/10 §2.2).
  - 등급: harness.env HARNESS_REVIEW_TIERS="quad=high stl-luau=high …" (저장소 이름 = git common dir 의 부모 이름). 없으면 HARNESS_REVIEW_DEFAULT(기본 mid).
    off 등급은 아무것도 하지 않는다.
  - 임계: HARNESS_REVIEW_LINES="high=40 mid=200 low=0" (추가+삭제 줄. 0 = 끔)
  - 최근 검토: HARNESS_REVIEW_FRESH_MIN(기본 90분) 안에 메인이 부른 검토가 끝났으면 2·3 을 건너뛴다.
  - 같은 diff(내용 해시)로는 회차당 한 번만, done 알림 뒤 FRESH_MIN 동안은 쉰다(사양해도 커밋마다 조르지 않게). dedup 단위는 session_id + compact 회차(compact_epoch.py).
  - 6 은 HARNESS_REVIEW_HANDBACK=off 로 끈다.
  - 출력 규약: HOOK-MESSAGES.md (<harness-hook name="qwreey-advisor" level="warn|info">, 영어).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import commit_scope  # noqa: E402
import compact_epoch  # noqa: E402
import handback_notice  # noqa: E402
import harness_nonce  # noqa: E402
import review_record  # noqa: E402

NS = review_record.NS
MODEL = {"high": "opus", "mid": "sonnet", "low": "sonnet"}
BENIGN = re.compile(r"^\s*(grep|rg|egrep|fgrep|test|\[|diff|cmp|pgrep|pidof|which|command)\b")
COMMIT = re.compile(r"\bgit\b(\s+-C\s+\S+)?\s+commit\b")
STOP_ERROR = re.compile(r"^\s*(API Error|Prompt is too long|Context limit|Request timed out|Credit balance)", re.I)
QUESTION_TAIL = 5  # 질문 뒤에 선택지 목록이 붙는 답을 위해 끝에서 몇 줄까지 본다


def env_vals(cwd=None) -> dict:
    """harness.env 층(옆의 harness_env.py 사본): 사용자 < 저장소 < 저장소 local < 환경 변수."""
    try:
        import harness_env
        vals = harness_env.load_layers(harness_env.project_dir(cwd))
    except Exception:
        vals = {}
    for k in ("HARNESS_REVIEW_TIERS", "HARNESS_REVIEW_DEFAULT", "HARNESS_REVIEW_LINES", "HARNESS_REVIEW_FRESH_MIN",
              "HARNESS_REVIEW_STOP", "HARNESS_REVIEW_PLAN", "HARNESS_REVIEW_HANDBACK"):
        if k in os.environ:
            vals[k] = os.environ[k]
    return vals


def kv(s: str) -> dict:
    return dict(p.split("=", 1) for p in (s or "").split() if "=" in p)


def git(cwd, *args) -> str:
    try:
        return subprocess.run(["git", "-C", cwd, *args], capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.SubprocessError):
        return ""


def repo_of(cwd: str) -> str | None:
    common = git(cwd, "rev-parse", "--path-format=absolute", "--git-common-dir").strip()
    return Path(common).parent.name if common else None  # worktree 안에서도 본 저장소 이름


def tier_of(cwd: str, vals: dict) -> tuple[str | None, str]:
    repo = repo_of(cwd)
    if not repo:
        return None, "off"
    return repo, kv(vals.get("HARNESS_REVIEW_TIERS", "")).get(repo, vals.get("HARNESS_REVIEW_DEFAULT") or "mid")


def limit_of(tier: str, vals: dict) -> int:
    lines = {**{"high": "40", "mid": "200", "low": "0"}, **kv(vals.get("HARNESS_REVIEW_LINES", ""))}
    return int(lines.get(tier, "0") or 0)


def diff_stat(cwd: str, *args) -> tuple[int, str]:
    out = git(cwd, "diff", "--numstat", *args)
    n = 0
    for line in out.splitlines():
        a, d, *_ = line.split("\t") + ["", ""]
        n += (int(a) if a.isdigit() else 0) + (int(d) if d.isdigit() else 0)
    return n, hashlib.sha1(git(cwd, "diff", *args).encode()).hexdigest()[:16]


def state_file(sid: str) -> str:
    return compact_epoch.state_path("qwreey-advisor", NS, sid)


def read_json(p: str) -> dict:
    try:
        return json.load(open(p))
    except (OSError, ValueError):
        return {}


SID = ""  # main() 이 채운다. wrap() 이 nonce 를 달 때 쓴다


def wrap(body: str, level: str = "warn") -> str:
    return f'<harness-hook name="qwreey-advisor" level="{level}"{harness_nonce.attr(SID)}>\n{body}\n</harness-hook>'


def emit(event: str, text: str, **extra) -> None:
    out = {"hookSpecificOutput": {"hookEventName": event, "additionalContext": text, **extra}}
    print(json.dumps(out))


def fresh_review(sid: str, vals: dict) -> bool:
    t = review_record.last_review_time(sid)
    return bool(t) and time.time() - t < float(vals.get("HARNESS_REVIEW_FRESH_MIN") or 90) * 60


def stop_passes(msg) -> bool:
    """Stop 에서 이어 가게 하면 안 되는 턴: 빈 답, 오류·한도 알림, 사용자에게 묻는 질문으로 끝난 답."""
    msg = str(msg or "").strip()
    if not msg or STOP_ERROR.match(msg):
        return True
    tail = [l.strip().rstrip("*_`) ") for l in msg.splitlines() if l.strip()][-QUESTION_TAIL:]
    return any(l.endswith(("?", "\uff1f")) for l in tail)


def cooling(st: dict, vals: dict) -> bool:
    """done 알림 뒤 FRESH_MIN 동안은 다시 알리지 않는다(메인이 검토를 사양해도 커밋마다 조르지 않게)."""
    return time.time() - st.get("last_nudge", 0) < float(vals.get("HARNESS_REVIEW_FRESH_MIN") or 90) * 60


def done_advice(repo, tier, n, where) -> str:
    return (f"{where}: {n} changed lines in `{repo}` (review tier: {tier}) and no qwreey-advisor review has finished in this session recently "
            f"(only qwreey-advisor reviewers and inherit-advisor forks are tracked; other reviews are not).\n"
            f"Before declaring this done, consider the `qwreey-advisor:fresh-advisor` skill with kind=done "
            f"(Agent subagent_type=qwreey-advisor:reviewer, model={MODEL.get(tier, 'sonnet')}) and handle its findings as the skill says. "
            f"Skip it if the change is mechanical or docs only, was already reviewed, or the user said so, and say so in one line.")


def commit_size(cmd: str, cwd: str) -> tuple[str, int, str] | None:
    """(커밋 디렉터리, 줄 수, 해시). dry-run 이면 None."""
    pl = commit_scope.plan(cmd, cwd)
    if pl and pl["commit"]["dry"]:
        return None
    if pl and pl["stages"]:
        got = commit_scope.measure(pl)
        if got:
            return pl["dir"], got[0], got[1]
    if pl:  # 같은 명령에 스테이징이 없음: 지금 index(-a 면 HEAD 대비 작업 트리)가 커밋된다
        gcwd, all_ = pl["dir"], pl["commit"]["all"]
    else:  # 명령을 읽지 못함: 예전 방식
        m = re.search(r"\bgit\s+-C\s+(\S+)", cmd)
        gcwd = os.path.join(cwd, m.group(1).strip("'\"")) if m else cwd
        all_ = bool(re.search(r"\scommit\b.*\s(-a|--all|-\w*a\w*)\b", cmd))
    n, h = diff_stat(gcwd, "HEAD") if all_ else diff_stat(gcwd, "--cached")
    return gcwd, n, h


def handback(ev: str, data: dict, sid: str) -> int:
    """메인의 UserPromptSubmit·PostToolBatch: 권고·질문이 든 서브에이전트 보고에 info 한 줄."""
    if ev == "PostToolBatch":
        if not handback_notice.has_state(sid):
            return 0
        labels = handback_notice.on_batch(data, review_record.last_review_time(sid))
    else:
        prompt = str(data.get("prompt") or "")
        if "<task-notification>" not in prompt and "[Subagent hand-back]" not in prompt:
            return 0
        labels = handback_notice.on_prompt(data, review_record.last_review_time(sid))
    if not labels:
        return 0
    cwd = data.get("cwd") or os.getcwd()
    vals = env_vals(cwd)
    if (vals.get("HARNESS_REVIEW_HANDBACK") or "").lower() == "off":
        return 0
    repo, tier = tier_of(cwd, vals)
    if repo and tier == "off":
        return 0
    emit(ev, wrap(handback_notice.message(labels), "info"))
    return 0


def main() -> int:
    global SID
    try:
        data = json.load(sys.stdin)
    except ValueError:
        return 0
    ev = data.get("hook_event_name") or ""
    sid = SID = data.get("session_id") or ""
    if ev == "SubagentStop":
        info = review_record.on_stop(data)
        try:
            handback_notice.on_stop(data, info["meta"], info["review"], review_record.nested(info["meta"]))
        except OSError:
            pass
        return 0
    if data.get("agent_id"):  # 서브에이전트 안: 아무것도 하지 않는다
        return 0
    if ev in ("UserPromptSubmit", "PostToolBatch"):
        return handback(ev, data, sid)
    cwd = data.get("cwd") or os.getcwd()
    vals = env_vals(cwd)

    repo, tier = tier_of(cwd, vals)
    if tier == "off" or not repo:
        return 0
    limit = limit_of(tier, vals)
    sp = state_file(sid)
    st = read_json(sp)

    def save():
        json.dump(st, open(sp, "w"))

    if ev == "PostToolUseFailure":
        if data.get("is_interrupt"):
            return 0
        ti = data.get("tool_input") or {}
        if data.get("tool_name") == "Bash" and BENIGN.match(str(ti.get("command", ""))):
            return 0
        err = str(data.get("error") or "")
        first = next((l for l in err.splitlines() if l.strip() and not l.startswith("Exit code")), err[:80])
        sig = f"{data.get('tool_name')}|{re.sub(r'[0-9]+', '#', first.strip())[:160]}"
        cnt = st.setdefault("fail", {})
        cnt[sig] = cnt.get(sig, 0) + 1
        save()
        if cnt[sig] == 2:
            emit(ev, wrap(
                f"The same failure happened twice this session: `{sig[:200]}`.\n"
                f"Before a third attempt, consider the `qwreey-advisor:fresh-advisor` skill with kind=stuck "
                f"(model={MODEL.get(tier, 'sonnet')}): give it the command, the error, and your current hypothesis. "
                f"If the next step is already dictated by the error (typo, missing file), fix it and say so in one line."))
        return 0

    if ev == "PreToolUse" and data.get("tool_name") == "Bash":
        cmd = str((data.get("tool_input") or {}).get("command", ""))
        if not COMMIT.search(cmd) or fresh_review(sid, vals):
            return 0
        got = commit_size(cmd, cwd)
        if not got:
            return 0
        gcwd, n, h = got
        if os.path.normpath(gcwd) != os.path.normpath(cwd):  # 다른 저장소에 커밋: 그 저장소의 등급으로
            repo, tier = tier_of(gcwd, vals)
            if tier == "off" or not repo:
                return 0
            limit = limit_of(tier, vals)
        if limit <= 0 or n < limit or h in st.setdefault("nudged", []) or cooling(st, vals):
            return 0
        st["nudged"].append(h)
        st["last_nudge"] = time.time()
        save()
        emit(ev, wrap(done_advice(repo, tier, n, "About to commit")))
        return 0

    if ev == "Stop":
        if (vals.get("HARNESS_REVIEW_STOP") != "1" or data.get("stop_hook_active") or stop_passes(data.get("last_assistant_message"))
                or limit <= 0 or fresh_review(sid, vals)):
            return 0
        n, h = diff_stat(cwd, "HEAD")
        if n < limit or h in st.setdefault("nudged", []) or cooling(st, vals):
            return 0
        st["nudged"].append(h)
        st["last_nudge"] = time.time()
        save()
        emit(ev, wrap(done_advice(repo, tier, n, "Turn ending with uncommitted changes")))
        return 0

    if ev == "PreToolUse" and data.get("tool_name") == "ExitPlanMode":
        mode = vals.get("HARNESS_REVIEW_PLAN") or ""
        plan = str((data.get("tool_input") or {}).get("plan", ""))
        if tier != "high" or mode not in ("deny", "warn") or re.search(r"qwreey-advisor:\s*(reviewed|skip)", plan):
            return 0
        if mode == "deny":
            msg = ("This plan is for a high-tier repo. Get a kind=plan review first (`qwreey-advisor:fresh-advisor` skill, model=opus), "
                   "add the line `qwreey-advisor: reviewed` (or `qwreey-advisor: skip` with a reason) to the plan, then exit plan mode again.")
            print(json.dumps({"hookSpecificOutput": {"hookEventName": ev, "permissionDecision": "deny",
                                                     "permissionDecisionReason": wrap(msg, "action")}}))
        else:
            emit(ev, wrap("This plan is for a high-tier repo. Consider a kind=plan review (`qwreey-advisor:fresh-advisor` skill, model=opus) "
                          "and add `qwreey-advisor: reviewed` to the plan; if it is small or already reviewed, add `qwreey-advisor: skip <reason>`."))
        return 0
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # 훅 오류로 작업을 막지 않는다
        print(f"second-opinion-nudge: {e}", file=sys.stderr)
        sys.exit(0)
