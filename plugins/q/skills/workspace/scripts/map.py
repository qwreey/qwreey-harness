#!/usr/bin/env python3
"""workspace 스킬의 지도: HARNESS_WORKSPACE 아래 `.git` 이 있는 폴더마다 한 줄. 사용: python3 -I map.py [현재 저장소 경로]

각 폴더의 CLAUDE.md, AGENTS.md, README.md 순으로 첫 번째로 있는 파일에서 제목도 빈 줄도 아닌 첫 줄을 120자까지 쓴다.
`*-kb` 를 맨 위에, 현재 저장소에는 표시를 붙인다. HARNESS_WORKSPACE 가 비면 "HARNESS_WORKSPACE not configured".
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
import wslib  # noqa: E402

DOCS = ("CLAUDE.md", "AGENTS.md", "README.md")
MAXLEN = 120


def first_line(path: Path) -> str:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    if lines and lines[0].strip() == "---":  # frontmatter
        end = next((i for i, l in enumerate(lines[1:], 1) if l.strip() == "---"), 0)
        lines = lines[end + 1:]
    for l in lines:
        s = l.strip()
        if not s or s.startswith("#") or s in ("---", "***") or s.startswith("<!--"):
            continue
        return s[:MAXLEN]
    return ""


def describe(repo: Path) -> str:
    for name in DOCS:
        f = repo / name
        if f.is_file():
            t = first_line(f)
            if t:
                return t
    return ""


def build(ws: str, current: str) -> str:
    if not ws:
        return "HARNESS_WORKSPACE not configured"
    try:
        names = sorted(n for n in os.listdir(ws) if (Path(ws) / n / ".git").exists())
    except OSError:
        return f"HARNESS_WORKSPACE not readable: {ws}"
    cur = ""
    if current:
        cur = wslib.sibling_of(os.path.normpath(current), ws, "") or ""
    names.sort(key=lambda n: (not n.endswith("-kb"), n))
    rows = []
    for n in names:
        mark = " (this session's repo)" if n == cur else ""
        d = describe(Path(ws) / n)
        rows.append(f"- {n}{mark}: {d}" if d else f"- {n}{mark}")
    return f"Workspace {ws} ({len(rows)} repos; `*-kb` first):\n" + "\n".join(rows)


def main() -> int:
    ws = wslib.workspace()
    cur = sys.argv[1] if len(sys.argv) > 1 else (os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
    print(build(ws, cur))
    return 0


if __name__ == "__main__":
    sys.exit(main())
