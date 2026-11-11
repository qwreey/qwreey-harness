"""저장소 루트와 외부 저장소 키.

- 루트: 시작 디렉터리에서 위로 올라가며 `.git` 을 찾는다. `.git` 이 파일(worktree)이면 gitdir 의 `commondir` 를 따라
  본 체크아웃으로 올린다. 그래서 worktree 에서 시작한 세션도 본 체크아웃과 같은 키를 쓴다. subprocess 없이 판정한다(훅 빠른 길).
- 키: 루트 절대 경로의 영숫자 아닌 글자를 `-` 로 바꾼 것(Claude Code 의 ~/.claude/projects 키와 같은 꼴).
"""
from __future__ import annotations

import os
import re
from pathlib import Path


def _read(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def project_root(start: str | os.PathLike) -> Path:
    start_p = Path(start).resolve()
    d = start_p
    while True:
        g = d / ".git"
        if g.is_dir():
            return d
        if g.is_file():
            txt = _read(g)
            if txt.startswith("gitdir:"):
                gitdir = Path(txt[7:].strip())
                if not gitdir.is_absolute():
                    gitdir = (d / gitdir).resolve()
                cd = _read(gitdir / "commondir")
                if cd:  # worktree → 본 저장소의 .git
                    common = Path(cd) if os.path.isabs(cd) else (gitdir / cd).resolve()
                    return common.parent if common.name == ".git" else common
            return d  # 서브모듈 등: .git 파일이 있는 곳
        if d.parent == d:
            return start_p  # git 저장소가 아니면 시작 디렉터리 그대로
        d = d.parent


def project_key(root: str | os.PathLike) -> str:
    return re.sub(r"[^A-Za-z0-9]", "-", str(Path(root)))


def short_home(p: str | os.PathLike) -> str:
    s, h = str(p), os.path.expanduser("~")
    return "~" + s[len(h):] if h != "/" and (s == h or s.startswith(h + "/")) else s


def find_transcript(session_id: str) -> Path | None:
    from . import config
    base = config.claude_config_dir() / "projects"
    for p in base.glob(f"*/{session_id}.jsonl"):
        return p
    return None


def latest_transcript_for(root: Path) -> Path | None:
    """이 저장소(또는 그 worktree)에서 시작한 세션 중 가장 최근에 갱신된 메인 트랜스크립트."""
    from . import config
    base = config.claude_config_dir() / "projects"
    key = project_key(root)
    best = None
    for d in base.glob(key + "*"):
        if not (d.name == key or d.name.startswith(key + "--")):
            continue
        for f in d.glob("*.jsonl"):
            m = f.stat().st_mtime
            if best is None or m > best[0]:
                best = (m, f)
    return best[1] if best else None
