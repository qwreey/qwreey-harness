#!/usr/bin/env python3
"""second-opinion-nudge — 정해진 시점에 '독립 검토를 받을 때'라고 알린다. 막지 않는다(ExitPlanMode 선택 기능 제외).

advisor 는 언제 불릴지 모델이 정해서 예측이 안 됐다(audit/18). 이 훅은 잴 수 있는 시점만 맡는다.
  1. PostToolUseFailure   같은 실패 서명이 이번 회차에 2번째 → stuck 검토 권고 (서명마다 한 번)
  2. PreToolUse(Bash)     `git commit` 이고 커밋될 diff 가 등급 임계 이상, 최근 검토 없음 → done 검토 권고
  3. Stop                 (기본 꺼짐, HARNESS_REVIEW_STOP=1) 커밋 안 된 diff 가 임계 이상, 최근 검토 없음 → done 검토 권고
  4. PreToolUse(ExitPlanMode) (기본 꺼짐, HARNESS_REVIEW_PLAN=deny|warn) high 등급에서 계획 검토 요구
  5. SubagentStop(second-opinion-reviewer)  검토 완료 시각을 기록 → 2·3 이 다시 울리지 않게
'접근 확정 전'은 잴 수 없어서 메인 판단(CLAUDE.md, 스킬)에 맡긴다. 이 저장소들에서 ExitPlanMode 사용은 0회였다(audit/18 §1.4).

규칙
  - 서브에이전트 안(agent_id 있음)에서는 아무것도 하지 않는다. 일꾼이 리뷰어를 또 띄우는 연쇄를 막는다($589 사고, audit/10 §2.2).
  - 등급: harness.env HARNESS_REVIEW_TIERS="quad=high stl-luau=high …" (저장소 이름 = git common dir 의 부모 이름). 없으면 HARNESS_REVIEW_DEFAULT(기본 mid).
    off 등급은 아무것도 하지 않는다.
  - 임계: HARNESS_REVIEW_LINES="high=40 mid=200 low=0" (추가+삭제 줄. 0 = 끔)
  - 최근 검토: HARNESS_REVIEW_FRESH_MIN(기본 90분) 안에 리뷰어가 끝났으면 2·3 을 건너뛴다.
  - 같은 diff(내용 해시)로는 회차당 한 번만, done 알림 뒤 FRESH_MIN 동안은 쉰다(사양해도 커밋마다 조르지 않게). dedup 단위는 session_id + compact 회차(lib/compact_epoch.py).
  - 출력 규약: HOOK-MESSAGES.md (<harness-hook name="second-opinion" level="warn">, 영어).
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HOME = Path(__file__).resolve().parent.parent  # ~/.claude
NS = "claude-second-opinion"
REVIEWER = "second-opinion-reviewer"
MODEL = {"high": "opus", "mid": "sonnet", "low": "sonnet"}
BENIGN = re.compile(r"^\s*(grep|rg|egrep|fgrep|test|\[|diff|cmp|pgrep|pidof|which|command)\b")


def load(name):
    try:
        spec = importlib.util.spec_from_file_location(name, HOME / "lib" / f"{name}.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception:
        return None


def env_vals() -> dict:
    he = load("harness_env")
    vals = he.load([HOME / "harness.env"]) if he else {}
    for k in ("HARNESS_REVIEW_TIERS", "HARNESS_REVIEW_DEFAULT", "HARNESS_REVIEW_LINES", "HARNESS_REVIEW_FRESH_MIN",
              "HARNESS_REVIEW_STOP", "HARNESS_REVIEW_PLAN"):
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


def diff_stat(cwd: str, *args) -> tuple[int, str]:
    out = git(cwd, "diff", "--numstat", *args)
    n = 0
    for line in out.splitlines():
        a, d, *_ = line.split("\t") + ["", ""]
        n += (int(a) if a.isdigit() else 0) + (int(d) if d.isdigit() else 0)
    return n, hashlib.sha1(git(cwd, "diff", *args).encode()).hexdigest()[:16]


def state_file(sid: str) -> str:
    ce = load("compact_epoch")
    if ce:
        return ce.state_path(NS, sid)
    d = os.path.join(tempfile.gettempdir(), NS)
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, re.sub(r"[^\w-]", "", sid or "nosession") + ".json")


def last_review_path(sid: str) -> str:
    """검토 완료 시각은 compact 를 넘어 유지한다(회차와 무관)."""
    d = os.path.join(tempfile.gettempdir(), NS)
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, re.sub(r"[^\w-]", "", sid or "nosession") + ".last-review")


def read_json(p: str) -> dict:
    try:
        return json.load(open(p))
    except (OSError, ValueError):
        return {}


def wrap(body: str, level: str = "warn") -> str:
    return f'<harness-hook name="second-opinion" level="{level}">\n{body}\n</harness-hook>'


def emit(event: str, text: str, **extra) -> None:
    out = {"hookSpecificOutput": {"hookEventName": event, "additionalContext": text, **extra}}
    print(json.dumps(out))


def fresh_review(sid: str, vals: dict) -> bool:
    try:
        t = float(open(last_review_path(sid)).read().strip())
    except (OSError, ValueError):
        return False
    return time.time() - t < float(vals.get("HARNESS_REVIEW_FRESH_MIN") or 90) * 60


def cooling(st: dict, vals: dict) -> bool:
    """done 알림 뒤 FRESH_MIN 동안은 다시 알리지 않는다(메인이 검토를 사양해도 커밋마다 조르지 않게)."""
    return time.time() - st.get("last_nudge", 0) < float(vals.get("HARNESS_REVIEW_FRESH_MIN") or 90) * 60


def done_advice(repo, tier, n, where) -> str:
    return (f"{where}: {n} changed lines in `{repo}` (review tier: {tier}) and no independent review has finished in this session recently.\n"
            f"Before declaring this done, run the `second-opinion` skill with kind=done "
            f"(Agent subagent_type=second-opinion-reviewer, model={MODEL.get(tier, 'sonnet')}), then relay its report verbatim. "
            f"If a review is not worth it here (mechanical change, docs only, user said skip), say so in one line instead.")


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except ValueError:
        return 0
    if data.get("agent_id"):  # 서브에이전트 안: 아무것도 하지 않는다
        return 0
    ev = data.get("hook_event_name") or ""
    sid = data.get("session_id") or ""
    cwd = data.get("cwd") or os.getcwd()
    vals = env_vals()

    if ev == "SubagentStop":
        if data.get("agent_type") == REVIEWER:
            open(last_review_path(sid), "w").write(str(time.time()))
        return 0

    repo, tier = tier_of(cwd, vals)
    if tier == "off" or not repo:
        return 0
    lines = {**{"high": "40", "mid": "200", "low": "0"}, **kv(vals.get("HARNESS_REVIEW_LINES", ""))}
    limit = int(lines.get(tier, "0") or 0)
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
                f"Before a third attempt, consider the `second-opinion` skill with kind=stuck "
                f"(model={MODEL.get(tier, 'sonnet')}): give it the command, the error, and your current hypothesis. "
                f"If the next step is already dictated by the error (typo, missing file), fix it and say so in one line."))
        return 0

    if ev == "PreToolUse" and data.get("tool_name") == "Bash":
        cmd = str((data.get("tool_input") or {}).get("command", ""))
        if not re.search(r"\bgit\b(\s+-C\s+\S+)?\s+commit\b", cmd) or limit <= 0 or fresh_review(sid, vals):
            return 0
        m = re.search(r"\bgit\s+-C\s+(\S+)", cmd)
        gcwd = os.path.join(cwd, m.group(1).strip("'\"")) if m else cwd
        n, h = diff_stat(gcwd, "HEAD") if re.search(r"\scommit\b.*\s(-a|--all|-\w*a\w*)\b", cmd) else diff_stat(gcwd, "--cached")
        if n < limit or h in st.setdefault("nudged", []) or cooling(st, vals):
            return 0
        st["nudged"].append(h)
        st["last_nudge"] = time.time()
        save()
        emit(ev, wrap(done_advice(repo, tier, n, "About to commit")))
        return 0

    if ev == "Stop":
        if vals.get("HARNESS_REVIEW_STOP") != "1" or data.get("stop_hook_active") or limit <= 0 or fresh_review(sid, vals):
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
        if tier != "high" or mode not in ("deny", "warn") or re.search(r"second-opinion:\s*(reviewed|skip)", plan):
            return 0
        msg = ("This plan is for a high-tier repo. Get a kind=plan review first (`second-opinion` skill, model=opus), "
               "add the line `second-opinion: reviewed` (or `second-opinion: skip` with a reason) to the plan, then exit plan mode again.")
        if mode == "deny":
            print(json.dumps({"hookSpecificOutput": {"hookEventName": ev, "permissionDecision": "deny",
                                                     "permissionDecisionReason": wrap(msg, "action")}}))
        else:
            emit(ev, wrap(msg))
        return 0
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # 훅 오류로 작업을 막지 않는다
        print(f"second-opinion-nudge: {e}", file=sys.stderr)
        sys.exit(0)
