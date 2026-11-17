#!/usr/bin/env python3
"""workspace 스킬의 지도: 이 기기에서 일한 저장소(known_repos)마다 한 줄. 사용: python3 -I map.py [현재 저장소 경로]

저장소는 Claude Code 세션 기록의 cwd 로 모으고 qwreey-workspace 옵션(harness_workspace_extra, harness_workspace_exclude)으로 더하고 뺀다.
각 저장소의 CLAUDE.md, AGENTS.md, README.md 순으로 첫 번째로 있는 파일에서 제목도 빈 줄도 아닌 첫 줄을 120자까지 쓴다.
`*-kb` 를 맨 위에, 현재 저장소에는 표시를 붙인다. 이름이 같은 저장소가 여럿일 수 있어 경로도 적는다(홈 아래는 `~/`).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
import known_repos  # noqa: E402
import wslib  # noqa: E402

DOCS = ("CLAUDE.md", "AGENTS.md", "README.md")
MAXLEN = 120
# 지도는 스킬을 실을 때마다 맥락에 들어간다. 저장소가 아주 많은 기기에서도 몇 천 자 안에 머물게 자른다(`*-kb` 가 앞이라 잘리지 않는다).
MAX_ROWS = 60
NONE_FOUND = ("No other repos known yet. Repos are found from this machine's Claude Code sessions; the user can add more "
              "with the qwreey-workspace option harness_workspace_extra (/config, or /plugin configure qwreey-workspace).")


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


def build(repos: list[str], current: str) -> str:
    cur = os.path.normcase(known_repos.repo_root(current) or "") if current else ""
    if not [r for r in repos if os.path.normcase(r) != cur]:
        return NONE_FOUND
    repos = sorted(repos, key=lambda r: (not os.path.basename(r).endswith("-kb"), os.path.basename(r).lower(), r))
    rows = []
    for r in repos[:MAX_ROWS]:
        mark = " (this session's repo)" if os.path.normcase(r) == cur else ""
        d = describe(Path(r))
        head = f"- {os.path.basename(r)} `{wslib.shown(r)}`{mark}"
        rows.append(f"{head}: {d}" if d else head)
    if len(repos) > MAX_ROWS:
        rows.append(f"- ... and {len(repos) - MAX_ROWS} more")
    return f"Repos on this machine ({len(repos)}; `*-kb` first):\n" + "\n".join(rows)


def main() -> int:
    cur = sys.argv[1] if len(sys.argv) > 1 else (os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
    print(build(known_repos.repos(), cur))
    return 0


if __name__ == "__main__":
    sys.exit(main())
