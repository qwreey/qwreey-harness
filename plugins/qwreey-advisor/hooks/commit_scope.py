"""commit_scope: 한 Bash 명령 안의 `git add ...` 와 `git commit ...` 을 읽어, 커밋될 변경의 줄 수를 PreToolUse 시점에 잰다.

PreToolUse 는 명령이 돌기 전이라 `git add x && git commit` 꼴에서는 index 가 아직 비어 있다. 그래서 같은 명령이 스테이징할
경로를 읽어 `git diff HEAD -- <경로>` 와 그 아래 추적 안 된 파일(.gitignore 존중)의 줄 수로 대신 잰다.
읽을 수 없는 명령(따옴표 오류, `$VAR`, 명령 치환이 든 경로, `add -p` 같은 대화형, `--pathspec-from-file`)은 None 을 돌려주고,
호출자는 예전처럼 `--cached`(커밋에 -a 면 `HEAD`)로 잰다.
git 호출은 rev-parse 1회와 diff, ls-files 최대 3회다.
"""
from __future__ import annotations

import hashlib
import os
import re
import shlex
import subprocess

SEPARATORS = {"&&", "||", ";", "|", "&", "\n", ";;", "|&"}
REDIRECT = re.compile(r"^[<>&]*[<>][<>&]*$")
COMMIT_VALUE_SHORT = set("mFCct")  # 값을 받는 commit 짧은 옵션
COMMIT_VALUE_LONG = {"--message", "--file", "--reuse-message", "--reedit-message", "--fixup", "--squash", "--author",
                     "--date", "--template", "--cleanup", "--trailer"}
ADD_INTERACTIVE = {"-p", "--patch", "-i", "--interactive", "-e", "--edit"}
ALL = ":/"  # 저장소 전체 pathspec
MAX_FILE_BYTES = 2 * 1024 * 1024


def tokens(cmd: str) -> list[str] | None:
    lex = shlex.shlex(cmd, posix=True, punctuation_chars=";&|<>\n")
    lex.whitespace = " \t\r"
    lex.whitespace_split = True
    try:
        out = []
        for t in lex:
            if t in ("<<", "<<-", "<<<"):  # heredoc 본문은 명령이 아니다. 그 앞까지만 본다
                break
            out.append(t)
        return out
    except ValueError:
        return None


def segments(toks: list[str]) -> list[list[str]]:
    segs, cur = [], []
    i = 0
    while i < len(toks):
        t = toks[i]
        if t in SEPARATORS:
            if cur:
                segs.append(cur)
            cur = []
        elif REDIRECT.match(t):
            if cur and cur[-1].isdigit():  # `2>&1` 의 fd
                cur.pop()
            i += 1  # 리다이렉트 대상
        else:
            cur.append(t)
        i += 1
    if cur:
        segs.append(cur)
    return segs


def git_sub(seg: list[str]) -> tuple[str | None, str, list[str]]:
    """(-C 경로, 하위 명령, 인자). git 명령이 아니면 하위 명령이 빈 값."""
    if not seg or os.path.basename(seg[0]) != "git":
        return None, "", []
    i, cdir = 1, None
    while i < len(seg):
        t = seg[i]
        if t == "-C" and i + 1 < len(seg):
            cdir = seg[i + 1] if cdir is None else os.path.join(cdir, seg[i + 1])
            i += 2
        elif t == "-c" and i + 1 < len(seg):
            i += 2
        elif t.startswith("-"):
            i += 1
        else:
            return cdir, t, seg[i + 1:]
    return cdir, "", []


def dynamic(t: str) -> bool:
    return "$" in t or "`" in t


def parse_commit(args: list[str]) -> dict | None:
    flags, paths, i, after_dd = set(), [], 0, False
    while i < len(args):
        t = args[i]
        if after_dd:
            paths.append(t)
        elif t == "--":
            after_dd = True
        elif t.startswith("--"):
            name = t.split("=", 1)[0]
            flags.add(name)
            if name in COMMIT_VALUE_LONG and "=" not in t:
                i += 1
        elif t.startswith("-") and len(t) > 1:
            for j, ch in enumerate(t[1:]):
                flags.add("-" + ch)
                if ch in COMMIT_VALUE_SHORT:
                    if j == len(t) - 2:  # 값이 다음 토큰
                        i += 1
                    break
        else:
            paths.append(t)
        i += 1
    if any(dynamic(p) for p in paths):
        return None
    return {"all": bool(flags & {"-a", "--all"}), "include": bool(flags & {"-i", "--include"}),
            "dry": "--dry-run" in flags, "paths": paths}


def parse_add(args: list[str]) -> dict | None:
    flags, paths, after_dd = set(), [], False
    for t in args:
        if after_dd:
            paths.append(t)
        elif t == "--":
            after_dd = True
        elif t.startswith("--"):
            flags.add(t.split("=", 1)[0])
        elif t.startswith("-") and len(t) > 1:
            flags |= {"-" + ch for ch in t[1:]}
        else:
            paths.append(t)
    if flags & ADD_INTERACTIVE or "--pathspec-from-file" in flags or any(dynamic(p) for p in paths):
        return None
    return {"dry": bool(flags & {"-n", "--dry-run"}), "all": bool(flags & {"-A", "--all"}),
            "update": bool(flags & {"-u", "--update"}), "paths": paths}


def plan(cmd: str, cwd: str) -> dict | None:
    """커밋 디렉터리와 같은 명령의 스테이징 범위. 같은 명령에 스테이징이 없으면 {"stages": False}. 읽을 수 없으면 None."""
    toks = tokens(cmd)
    if toks is None:
        return None
    here, adds = cwd, []
    for seg in segments(toks):
        if seg[0] in ("cd", "pushd"):
            if len(seg) > 2 or (len(seg) == 2 and dynamic(seg[1])):
                return None
            here = os.path.normpath(os.path.join(here, os.path.expanduser(seg[1] if len(seg) == 2 else "~")))
            continue
        cdir, sub, args = git_sub(seg)
        gdir = os.path.normpath(os.path.join(here, cdir)) if cdir else here
        if sub in ("add", "stage"):
            a = parse_add(args)
            if a is None:
                return None
            if not a["dry"]:
                adds.append((gdir, a))
        elif sub == "commit":
            c = parse_commit(args)
            if c is None:
                return None
            return {"dir": gdir, "commit": c, "adds": adds,
                    "stages": bool(adds or c["paths"])}
    return None


def git(cwd: str, *args: str) -> tuple[int, str]:
    try:
        p = subprocess.run(["git", "-C", cwd, *args], capture_output=True, text=True, timeout=5)
        return p.returncode, p.stdout
    except (OSError, subprocess.SubprocessError):
        return 1, ""


def numstat(out: str) -> dict[str, int]:
    files = {}
    for line in out.splitlines():
        a, d, *rest = line.split("\t") + ["", ""]
        files[rest[0] if rest else ""] = (int(a) if a.isdigit() else 0) + (int(d) if d.isdigit() else 0)
    return files


def count_lines(path: str) -> int:
    try:
        with open(path, "rb") as f:
            data = f.read(MAX_FILE_BYTES)
    except OSError:
        return 0
    if not data or b"\0" in data[:8192]:  # 바이너리는 numstat 처럼 0
        return 0
    return data.count(b"\n") + (0 if data.endswith(b"\n") else 1)


def specs_of(top: str, base: str, paths: list[str]) -> list[str]:
    """명령의 경로를 저장소 루트 기준 pathspec 으로. 저장소 밖이면 버린다."""
    out = []
    for p in paths:
        ap = os.path.normpath(os.path.join(base, os.path.expanduser(p)))
        rel = os.path.relpath(ap, top)
        if rel == ".":
            out.append(ALL)
        elif not rel.startswith(".."):
            out.append(":/" + rel)
    return out


def measure(pl: dict) -> tuple[int, str] | None:
    """plan 이 스테이징하는 범위까지 더한 커밋 크기 (추가+삭제 줄, 내용 해시). 저장소를 못 찾으면 None."""
    gdir = pl["dir"]
    rc, out = git(gdir, "rev-parse", "--show-toplevel")
    top = out.strip()
    if rc or not top:
        return None
    c = pl["commit"]
    tracked, untracked = set(), set()
    for adir, a in pl["adds"]:
        specs = specs_of(top, adir, a["paths"]) if a["paths"] else [ALL]
        tracked |= set(specs)
        if not a["update"]:
            untracked |= set(specs)
    files: dict[str, int] = {}
    if c["paths"] and not c["include"]:  # `git commit <경로>` 는 그 경로만 커밋한다
        only = specs_of(top, gdir, c["paths"])
        if not only:
            return None
        files.update(numstat(git(top, "diff", "HEAD", "--numstat", "--", *only)[1]))
        untracked = set(only) if untracked else set()
    else:
        tracked |= set(specs_of(top, gdir, c["paths"]))
        if c["all"] or ALL in tracked:
            files.update(numstat(git(top, "diff", "HEAD", "--numstat")[1]))
        else:
            files.update(numstat(git(top, "diff", "--cached", "--numstat")[1]))
            if tracked:
                files.update(numstat(git(top, "diff", "HEAD", "--numstat", "--", *sorted(tracked))[1]))
    if untracked:
        names = git(top, "ls-files", "--others", "--exclude-standard", "-z", "--", *sorted(untracked))[1]
        for name in filter(None, names.split("\0")):
            files["?" + name] = count_lines(os.path.join(top, name))
    n = sum(files.values())
    h = hashlib.sha1("\n".join(f"{k}\t{v}" for k, v in sorted(files.items())).encode()).hexdigest()[:16]
    return n, h
