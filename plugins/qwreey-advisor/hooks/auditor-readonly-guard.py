#!/usr/bin/env python3
"""auditor-readonly-guard — 감사 서브에이전트용 PreToolUse 훅 (읽기 전용 강제의 두 번째 줄).

배치: ~/.claude/hooks/auditor-readonly-guard.py (chmod +x)
등록: 각 감사 에이전트 frontmatter 의 hooks.PreToolUse (matcher "Bash|Write|Edit|MultiEdit|NotebookEdit|mcp__.*")

첫 번째 줄은 frontmatter 의 disallowedTools(Edit, NotebookEdit)다. 이 훅은 다음을 막는다.
  - Write: 스크래치(/tmp/claude-audit/<run>/) 밖이면 거부. 에이전트가 음성 대조군과 프로브 파일을 쓸 곳은 스크래치 하나다.
  - Edit/MultiEdit/NotebookEdit: 스크래치 밖이면 거부. memory 필드가 이 도구들을 자동으로 켜도 막힌다.
  - Bash:
      - 쓰기 명령(rm, mv, cp, tee, sed -i ...)의 경로 인자가 스크래치 밖이면 거부
      - 리다이렉션(>, >>) 대상이 스크래치나 /dev/null 이 아니면 거부
      - 작업 트리, 인덱스, ref 를 바꾸는 git 하위 명령은 거부
      - 패키지 설치, 네트워크 명령은 거부
  - mcp__roblox-studio__* : 전부 거부(Studio 는 여러 세션이 같이 쓰고, execute_luau 등은 상태를 바꾼다).

스크래치는 SCRATCH_BASE(/tmp/claude-audit/) 아래 실행별 폴더(<run>/, 리뷰어 호출마다 track-reviewer.py 가 만들어 prompt 끝에 알린다)다.
가드는 자기 transcript 를 볼 수 없어서 리뷰어의 run 폴더를 알지 못한다. 그래서 SCRATCH_BASE 아래 경로(SCRATCH_BASE/<아무 이름>/...)를 허용하고
SCRATCH_BASE 자체(rm -rf /tmp/claude-audit 등)와 그 밖은 거부한다. 목적은 저장소를 못 쓰게 막는 것이지 리뷰어끼리 격리하는 것이 아니다
(프로브가 겹칠 위험은 run 마다 다른 uuid 폴더로 이미 없다).

한계(휴리스틱): `bash ./scripts/x.sh`, `python3 -c`, `luau probe.luau` 안에서 일어나는 쓰기는 못 본다.
그래서 /audit 스킬이 실행 전후의 `git status` 해시를 비교한다(세 번째 줄).

종료 코드 2 = 차단(stderr 가 에이전트에게 사유로 전달됨), 0 = 통과.
"""
from __future__ import annotations

import json
import os
import re
import shlex
import sys

SCRATCH_BASE = os.environ.get("CLAUDE_AUDIT_SCRATCH", "/tmp/claude-audit")
SCRATCH = SCRATCH_BASE

WRITE_CMDS = {
    "rm", "rmdir", "mv", "cp", "ln", "chmod", "chown", "chgrp", "touch", "truncate",
    "dd", "install", "mkdir", "tee", "shred", "unlink", "rsync",
}
DENY_CMDS = {
    # 네트워크(WebFetch 를 쓴다), 패키지, 툴체인 변경, 권한 상승
    "curl", "wget", "scp", "ssh", "sudo", "su", "setpriv", "nc",
    "npm", "pnpm", "yarn", "pip", "pip3", "cargo", "pesde", "wally", "rokit", "aftman",
    "rojo",  # rojo serve/build 는 Studio, 파일을 건드린다
    "studio-sync",
}
MISE_DENY_SUB = {"install", "use", "trust", "upgrade", "uninstall", "prune", "settings", "self-update", "set", "unuse"}
GIT_READ_SUB = {
    "status", "diff", "log", "show", "blame", "ls-files", "ls-tree", "rev-parse", "rev-list",
    "grep", "cat-file", "shortlog", "describe", "merge-base", "name-rev", "for-each-ref",
    "show-ref", "whatchanged", "range-diff", "annotate", "count-objects", "check-ignore", "version",
}
GIT_OPTS_WITH_ARG = {"-C", "-c", "--git-dir", "--work-tree", "--namespace"}
INPLACE = re.compile(r"(^|\s)-[a-zA-Z]*i(\s|$|[.=])|--in-place")
REDIR = re.compile(r"(?<![0-9&<])(?:[0-9]?)(>>?|&>>?)\s*([^\s;&|<>]+)")


def deny(msg: str) -> None:
    print(f"auditor-readonly-guard: {msg}. 감사자는 읽기 전용이다. 프로브는 {SCRATCH}/<run>/ 안에서만 만든다.", file=sys.stderr)
    sys.exit(2)


def in_scratch(path: str, cwd: str) -> bool:
    if not path:
        return False
    p = os.path.normpath(os.path.join(cwd, os.path.expanduser(path)))
    rel = os.path.relpath(p, os.path.normpath(SCRATCH))
    return rel != "." and rel != ".." and not rel.startswith(".." + os.sep) and not os.path.isabs(rel)


def segments(cmd: str) -> list[str]:
    # 대충 나누기: ; && || | 줄바꿈. 따옴표 안의 구분자는 shlex 실패 시 그대로 남는다(보수적으로 다룸).
    return [s for s in re.split(r"\|\||&&|[;|\n]", cmd) if s.strip()]


HEREDOC = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1[^\n]*\n(.*?)\n\s*\2\s*(?=\n|$)", re.S)
QUOTED = re.compile(r"'[^']*'|\"(?:[^\"\\]|\\.)*\"")


def strip_bodies(cmd: str) -> str:
    # heredoc 본문(예: 프로브 Luau 코드의 `a > b`)과 따옴표 안 문자열은 리다이렉션, 명령으로 보지 않는다.
    # heredoc 을 먼저 지운다 - `<<'EOF'` 의 따옴표가 QUOTED 에 먼저 먹히면 본문을 못 찾는다.
    cmd = HEREDOC.sub(lambda m: m.group(0).split("\n", 1)[0], cmd)
    return QUOTED.sub("''", cmd)


def check_bash(cmd: str, cwd: str) -> None:
    raw = cmd
    cmd = strip_bodies(cmd)
    # 1) 리다이렉션
    for m in REDIR.finditer(cmd):
        target = m.group(2)
        if target.startswith("&") or target in ("/dev/null", "/dev/stderr", "/dev/stdout"):
            continue
        if not in_scratch(target, cwd):
            deny(f"리다이렉션 대상 {target!r} 이 스크래치 밖")
    # 2) 명령별 (따옴표는 shlex 가 다뤄야 하므로 heredoc 만 지운 원문을 쓴다)
    body_stripped = HEREDOC.sub(lambda m: m.group(0).split("\n", 1)[0], raw)
    for seg in segments(body_stripped):
        try:
            argv = shlex.split(seg, comments=True)
        except ValueError:
            argv = seg.split()
        # env VAR=x, choom ..., prlimit ..., timeout N, nice 같은 래퍼를 벗긴다
        while argv:
            a0 = os.path.basename(argv[0])
            if "=" in argv[0] and not argv[0].startswith("-"):
                argv = argv[1:]
            elif a0 in ("env", "nice", "nohup", "time", "command", "exec"):
                argv = argv[1:]
            elif a0 == "timeout":
                argv = [x for x in argv[1:] if not x.startswith("-")][1:]
            elif a0 in ("choom", "prlimit"):
                argv = argv[argv.index("--") + 1:] if "--" in argv else []
            elif a0 == "mise" and len(argv) > 1 and argv[1] == "exec":
                argv = argv[argv.index("--") + 1:] if "--" in argv else []
            else:
                break
        if not argv:
            continue
        a0 = os.path.basename(argv[0])
        args = argv[1:]
        if a0 in DENY_CMDS:
            deny(f"`{a0}` 는 감사자에게 허용되지 않음")
        if a0 == "mise" and args and args[0] in MISE_DENY_SUB:
            deny(f"`mise {args[0]}` 는 툴체인을 바꾼다")
        if a0 in WRITE_CMDS:
            paths = [x for x in args if not x.startswith("-")]
            if a0 in ("cp", "install", "rsync", "ln") and paths:
                paths = paths[-1:]  # 원본은 읽기만 한다 - 대상만 본다
            if not paths or not all(in_scratch(p, cwd) for p in paths):
                deny(f"`{a0}` 의 경로가 스크래치 밖")
        if a0 in ("sed", "perl", "ruby") and INPLACE.search(" ".join(args)):
            deny(f"`{a0} -i` (제자리 수정)")
        if a0 == "git":
            i = 0
            while i < len(args) and args[i].startswith("-"):
                i += 2 if args[i] in GIT_OPTS_WITH_ARG else 1
            sub = args[i] if i < len(args) else ""
            rest = args[i + 1:]
            if sub == "branch" and all(r in ("-a", "-r", "-v", "-vv", "--list", "--show-current") for r in rest):
                continue
            if sub == "stash" and rest[:1] in (["list"], ["show"]):
                continue
            if sub == "worktree" and rest[:1] == ["list"]:
                continue
            if sub == "config" and any(r in ("--get", "--list", "-l", "--get-all", "--get-regexp") for r in rest):
                continue
            if sub not in GIT_READ_SUB:
                deny(f"`git {sub}` 는 작업 트리·인덱스·ref 를 바꿀 수 있다 (HEAD 내용은 `git show HEAD:<경로>` 로 읽는다)")


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)  # 입력을 못 읽으면 막지 않는다(훅 자체 고장으로 감사가 멈추지 않게)
    tool = data.get("tool_name", "")
    ti = data.get("tool_input", {}) or {}
    cwd = data.get("cwd") or os.getcwd()
    if tool.startswith("mcp__roblox-studio"):
        deny("Roblox Studio MCP 는 감사자에게 허용되지 않음 — 'Studio 실측 필요'로 보고할 것")
    if tool in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
        path = ti.get("file_path") or ti.get("notebook_path") or ""
        if not in_scratch(path, cwd):
            deny(f"{tool} 대상 {path!r} 이 스크래치 밖")
        sys.exit(0)
    if tool == "Bash":
        check_bash(ti.get("command", ""), cwd)
    sys.exit(0)


if __name__ == "__main__":
    main()
