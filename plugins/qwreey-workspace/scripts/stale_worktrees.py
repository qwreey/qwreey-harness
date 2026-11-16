#!/usr/bin/env python3
"""오래 손대지 않은 worktree 알림. 사용: python3 -I stale_worktrees.py  (stdin: SessionStart 훅 JSON)

메인 세션의 SessionStart(startup, resume, clear. compact 는 hooks.json matcher 에서 뺀다)에 현재 저장소의 worktree 를 보고,
오래 손대지 않았고 잠기지 않았고 살아 있는 세션이 없는 것이 있으면 info 한 줄을 낸다. 정리할 수 있는지 확인해 보라는 권고일 뿐이고
지우는 명령은 내지 않는다. 이 훅은 git 과 파일 시스템을 읽기만 한다(git status 도 GIT_OPTIONAL_LOCKS=0 으로 index 를 쓰지 않게).

- 대상: `git worktree list --porcelain` 의 첫 항목(주 worktree)과 이 세션이 있는 worktree 를 뺀 전부(.claude/worktrees/*, 형제 폴더).
- 마지막으로 손댄 때: HEAD 커밋 시각, 관리 폴더(<common>/worktrees/<name>)의 index, HEAD, logs/HEAD mtime, worktree 루트 폴더 mtime 중
  가장 늦은 것. 파일 하나하나는 보지 않는다(큰 트리에서 비싸다). 그래서 커밋도 add 도 없이 파일만 고친 경우는 놓칠 수 있다.
- 잠금: porcelain 의 locked. 사라진 폴더: porcelain 의 prunable 이거나 폴더가 없음. 잠기지 않은 prunable 은 나이와 무관하게 센다
  (폴더가 이미 없어 잃을 작업이 없고, 등록만 남은 것이다).
- 살아 있는 세션: Linux /proc 에서 comm 이 claude, agy, codex 인 프로세스의 cwd 가 worktree 안이면 뺀다. /proc 이 없거나 cwd 를 읽을
  권한이 없으면(다른 uid 로 도는 위임) 모르는 채로 둔다.
- 커밋 안 한 변경: 알림에 보일 worktree(최대 SHOW 개)만, index 가 STATUS_MAX_INDEX 바이트 이하일 때, 추적 파일만(-uno) 1.5초 안에서 본다.
  그 밖은 확인하지 않고 표시도 하지 않는다.
- 문턱: HARNESS_WORKSPACE_STALE_WORKTREE_DAYS(일, 기본은 harness_env DEFAULTS). off, 0, 빈 값이면 끈다. 저장소 층도 정할 수 있다.
- 세션마다 한 번: $TMPDIR/claude-workspace-worktrees/<sid> 를 O_EXCL 로 만든 쪽만 낸다(resume 해도 다시 내지 않는다).
- HARNESS_WORKSPACE 가 비면 아무것도 하지 않는다(플러그인 규칙). 어떤 실패든 출력 없이 exit 0.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # python3 -I 는 스크립트 디렉터리를 path 에 넣지 않는다
import harness_nonce  # noqa: E402
import wslib  # noqa: E402

KEY = "HARNESS_WORKSPACE_STALE_WORKTREE_DAYS"
NS = "claude-workspace-worktrees"
AGENTS = {"claude", "agy", "codex"}
SHOW = 3  # 알림에 이름을 적는 worktree 수. 나머지는 개수만
GIT_TIMEOUT = 3.0
BUDGET = 6.0  # 훅 전체 시간(hooks.json timeout 10초 안)
STATUS_TIMEOUT = 1.5
STATUS_MAX_INDEX = 2 * 1024 * 1024  # index 2MB 는 대략 파일 2만 개. 넘으면 status 를 부르지 않는다
DAY = 86400.0


def git(args, cwd, timeout=GIT_TIMEOUT):
    env = dict(os.environ, GIT_OPTIONAL_LOCKS="0", LC_ALL="C")
    env.pop("GIT_DIR", None)
    env.pop("GIT_WORK_TREE", None)
    p = subprocess.run(["git", "-C", cwd] + args, capture_output=True, text=True, timeout=timeout, env=env,
                       stdin=subprocess.DEVNULL)
    if p.returncode != 0:
        raise RuntimeError(p.stderr.strip())
    return p.stdout


def parse_porcelain(text):
    """[{path, head, branch, locked, prunable, bare}] 순서대로. 첫 항목이 주 worktree."""
    out, cur = [], None
    for line in text.splitlines():
        if line.startswith("worktree "):
            cur = {"path": os.path.normpath(line[9:]), "head": "", "branch": "", "locked": False, "prunable": False, "bare": False}
            out.append(cur)
        elif cur is None:
            continue
        elif line.startswith("HEAD "):
            cur["head"] = line[5:].strip()
        elif line.startswith("branch "):
            b = line[7:].strip()
            cur["branch"] = b[len("refs/heads/"):] if b.startswith("refs/heads/") else b
        elif line == "detached":
            cur["branch"] = ""
        elif line == "bare":
            cur["bare"] = True
        elif line == "locked" or line.startswith("locked "):
            cur["locked"] = True
        elif line == "prunable" or line.startswith("prunable "):
            cur["prunable"] = True
    return out


def admin_dirs(common):
    """{worktree 경로(normpath): 관리 폴더}. <common>/worktrees/<name>/gitdir 은 '<worktree>/.git' 을 가리킨다."""
    out = {}
    base = os.path.join(common, "worktrees")
    try:
        names = os.listdir(base)
    except OSError:
        return out
    for n in names:
        d = os.path.join(base, n)
        try:
            with open(os.path.join(d, "gitdir"), encoding="utf-8") as f:
                g = f.read().strip()
        except OSError:
            continue
        if not os.path.isabs(g):
            g = os.path.join(d, g)
        out[os.path.normpath(os.path.dirname(g))] = d
    return out


def mtime(p):
    try:
        return os.stat(p).st_mtime
    except OSError:
        return 0.0


def commit_times(shas, cwd):
    """{sha: 커밋 시각}. 실패하면 빈 dict(그러면 mtime 만 본다)."""
    shas = sorted({s for s in shas if re.fullmatch(r"[0-9a-f]{7,64}", s)})
    if not shas:
        return {}
    try:
        text = git(["log", "--no-walk=unsorted", "--ignore-missing", "--format=%H %ct"] + shas, cwd)
    except Exception:
        return {}
    out = {}
    for line in text.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1].isdigit():
            out[parts[0]] = float(parts[1])
    return out


def live_cwds(proc="/proc"):
    """comm 이 claude, agy, codex 인 프로세스의 cwd(normpath) 목록. /proc 이 없으면 []."""
    out = []
    try:
        pids = [p for p in os.listdir(proc) if p.isdigit()]
    except OSError:
        return out
    for pid in pids:
        try:
            with open(os.path.join(proc, pid, "comm"), encoding="utf-8", errors="replace") as f:
                if f.read().strip() not in AGENTS:
                    continue
            out.append(os.path.normpath(os.readlink(os.path.join(proc, pid, "cwd"))))
        except OSError:
            continue
    return out


def threshold_days(vals):
    raw = wslib.setting(KEY, vals).strip().lower()
    if raw in ("", "off", "no", "false"):
        return None
    try:
        d = float(raw)
    except ValueError:
        return None
    return d if d > 0 else None


def claim_once(sid):
    """이 세션에서 처음이면 True. 표지를 못 만들면(쓰기 실패) 내지 않는다."""
    d = os.path.join(tempfile.gettempdir(), NS)
    try:
        os.makedirs(d, exist_ok=True)
        os.close(os.open(os.path.join(d, re.sub(r"[^\w-]", "", str(sid or "nosession"))), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600))
        return True
    except OSError:
        return False


def scan(project, now, days, proc="/proc", deadline=None):
    """(오래된 것 [dict], 잠기지 않은 prunable [dict], 주 worktree 경로). 오래된 것은 오래된 순. 실패는 예외."""
    deadline = deadline or (time.monotonic() + BUDGET)
    wts = parse_porcelain(git(["worktree", "list", "--porcelain"], project))
    if len(wts) < 2:
        return [], [], ""
    common = git(["rev-parse", "--path-format=absolute", "--git-common-dir"], project).strip()
    admins = admin_dirs(common)
    here = os.path.normpath(project)
    others = [w for w in wts[1:] if not w["bare"] and not wslib.inside(here, w["path"])]
    if not others:
        return [], [], ""
    ct = commit_times([w["head"] for w in others], project)
    lives = live_cwds(proc)
    stale, gone = [], []
    for w in others:
        if w["locked"] or any(wslib.inside(c, w["path"]) for c in lives):
            continue
        adm = admins.get(w["path"], "")
        touched = [ct.get(w["head"], 0.0), mtime(w["path"])]
        if adm:
            touched += [mtime(os.path.join(adm, f)) for f in ("index", "HEAD", os.path.join("logs", "HEAD"))]
        w["age"] = (now - max(touched)) / DAY if max(touched) > 0 else None
        w["admin"] = adm
        if w["prunable"] or not os.path.isdir(w["path"]):
            gone.append(w)
        elif w["age"] is not None and w["age"] >= days:
            stale.append(w)
    stale.sort(key=lambda w: -w["age"])
    for w in stale[:SHOW]:
        w["dirty"] = dirty(w, deadline)
    return stale, gone, wts[0]["path"]


def dirty(w, deadline):
    """추적 파일에 커밋 안 한 변경이 있으면 True, 없으면 False, 보지 않았으면 None."""
    left = deadline - time.monotonic()
    idx = os.path.join(w.get("admin") or "", "index")
    if left < 0.3 or not w.get("admin") or not os.path.isfile(idx) or os.path.getsize(idx) > STATUS_MAX_INDEX:
        return None
    try:
        return bool(git(["status", "--porcelain", "--untracked-files=no", "--ignore-submodules"], w["path"],
                        timeout=min(STATUS_TIMEOUT, left)).strip())
    except Exception:
        return None


def show_path(p, main):
    return os.path.relpath(p, main) if wslib.inside(p, main) else p


def describe(w, main):
    bits = ["branch %s" % w["branch"] if w["branch"] else "detached HEAD"]
    if w.get("age") is not None:
        bits.append("%d days" % int(w["age"]))
    if w.get("dirty"):
        bits.append("uncommitted changes")
    return "`%s` (%s)" % (show_path(w["path"], main), ", ".join(bits))


def message(stale, gone, days, main):
    parts = []
    if stale:
        names = ", ".join(describe(w, main) for w in stale[:SHOW])
        more = " and %d more" % (len(stale) - SHOW) if len(stale) > SHOW else ""
        parts.append("This repo has %d worktree%s untouched for %s+ days (not locked, no live claude/agy/codex session inside): %s%s."
                     % (len(stale), "" if len(stale) == 1 else "s", ("%g" % days), names, more))
    if gone:
        names = ", ".join("`%s` (%s)" % (show_path(w["path"], main), "branch " + w["branch"] if w["branch"] else "detached HEAD")
                          for w in gone[:SHOW])
        more = " and %d more" % (len(gone) - SHOW) if len(gone) > SHOW else ""
        parts.append("Registered but its directory is gone (prunable): %s%s." % (names, more))
    parts.append("They may be finished work. If cleanup fits the moment, check each one with the qwreey-workspace:workspace skill's "
                 "worktree-lock and live-session steps and ask the user before removing any. Nothing to do if the user keeps them "
                 "or they are unrelated to the current work.")
    return " ".join(parts)


def main():
    data = json.load(sys.stdin)
    if not isinstance(data, dict) or data.get("agent_id"):
        return
    if (data.get("hook_event_name") or "SessionStart") != "SessionStart" or data.get("source") == "compact":
        return
    cwd = data.get("cwd") or ""
    vals = wslib.load_env(cwd)
    if not wslib.workspace(vals):
        return
    days = threshold_days(vals)
    if days is None:
        return
    project = os.path.normpath(os.environ.get("CLAUDE_PROJECT_DIR") or cwd or "")
    if not project or not os.path.isdir(project):
        return
    if not claim_once(data.get("session_id")):
        return
    stale, gone, main_path = scan(project, time.time(), days)
    if not stale and not gone:
        return
    sid = data.get("session_id")
    body = message(stale, gone, days, main_path)
    rule = harness_nonce.rule_for("SessionStart", data)
    text = '<harness-hook name="stale-worktrees" level="info"%s>\n%s%s\n</harness-hook>' % (
        harness_nonce.attr(sid), rule + "\n" if rule else "", body)
    json.dump({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": text}}, sys.stdout)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
