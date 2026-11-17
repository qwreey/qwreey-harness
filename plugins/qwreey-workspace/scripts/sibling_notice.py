#!/usr/bin/env python3
"""형제 저장소 내부 경로 알림. 사용: python3 -I sibling_notice.py  (stdin: PostToolUse 훅 JSON, Write|Edit|MultiEdit)

이 세션 저장소의 기록(`.claude/` 아래)에 쓴 글에 이 기기의 다른 저장소(형제) 안 경로가 있으면 info 한 줄을 낸다.
그 내부를 이 저장소가 정말 필요로 하는지(의존), 그 저장소가 이 저장소만큼 공개인지(remote, LICENSE) 확인하고, 모르면 사용자에게
묻게 하는 알림이다. 비공개 목록 같은 설정은 없다. 판단은 모델이 한다.

- 기록: 기록 뿌리(이 세션 저장소, 또는 그 안 `.claude/worktrees/<이름>` worktree)의 `.claude/` 아래 파일.
  `.claude/worktrees/` 자체와 설정, 규약 폴더(rules, skills, agents, commands, hooks, settings*.json, harness*.env)는 뺀다.
- 형제 저장소: map.py 와 같은 known_repos 목록(세션 기록의 cwd, 옵션으로 더하고 뺀 것). 이 세션 저장소(worktree 는 본 저장소로)는 뺀다.
  `<형제>` 는 저장소 폴더 이름이다. 이름이 같은 저장소가 여럿이면 이 저장소와 같은 폴더에 있는 것, 없으면 경로순 첫째로 본다.
- 경로 꼴: 형제 뿌리 아래 절대 경로, `../<형제>/<경로>`, `<형제>/<경로>`. 마지막 꼴은 그 경로가 형제 안에 실제로 있고
  이 저장소 안(저장소 뿌리, `.claude/`, 쓴 파일의 폴더)에는 없을 때만 센다(저장소 이름만 지나가거나 우연히 같은 낱말은 잡지 않는다).
- 쓴 글만 본다: Write 의 content, Edit 의 new_string, MultiEdit 의 edits[].new_string.
- 한 번: (쓴 파일, 형제)마다 (세션, agent_id, compact 회차)에 한 번.
- 끄기: HARNESS_WORKSPACE_SIBLING_NOTICE=off(옵션 harness_workspace_sibling_notice, 환경 변수, harness.env 의 사용자, 저장소 층).
  다른 저장소를 하나도 모르면 낼 것이 없다.
- 어떤 실패든 출력 없이 exit 0.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # python3 -I 는 스크립트 디렉터리를 path 에 넣지 않는다
import compact_epoch  # noqa: E402
import harness_nonce  # noqa: E402
import known_repos  # noqa: E402
import wslib  # noqa: E402

KEY = "HARNESS_WORKSPACE_SIBLING_NOTICE"
NS = "claude-workspace-sibling"
TOOLS = {"Write", "Edit", "MultiEdit"}
# 기록이 아닌 `.claude/` 첫 단계: worktree 사본, 모델용 규약과 설정
SKIP_TOP = {"worktrees", "rules", "skills", "agents", "commands", "hooks"}
SKIP_FILE = re.compile(r"^(?:settings(?:\.local)?\.json|harness(?:\.local)?\.env)$")
# 경로 꼬리에 올 수 있는 글자. 줄 번호(`:12`), 앵커(`#x`), 문장 부호는 뺀다
REST = r"[^\s`'\"<>()\[\]{}|,;:#*!?]+"
EXAMPLE_MAX = 80


def records_rel(path: str, project: str) -> str | None:
    """path 가 기록이면 기록 뿌리의 `.claude/` 기준 상대 경로, 아니면 None. 둘 다 normpath."""
    if not wslib.inside(path, project) or path == project:
        return None
    parts = Path(os.path.relpath(path, project)).parts
    if len(parts) > 3 and parts[0] == ".claude" and parts[1] == "worktrees":
        parts = parts[3:]  # 이 저장소의 worktree 도 같은 저장소의 기록이다
    if len(parts) < 2 or parts[0] != ".claude" or parts[1] in SKIP_TOP:
        return None
    if len(parts) == 2 and SKIP_FILE.match(parts[1]):
        return None
    return "/".join(parts[1:])


def siblings(project: str, repos: list[str]) -> dict[str, str]:
    """{형제 이름(폴더 이름): 저장소 루트}. 이 세션 저장소와 이름이 같은 저장소는 뺀다(`../<이름>` 이 어느 쪽인지 모른다).
    이름이 겹치면 이 저장소와 같은 폴더에 있는 것, 없으면 경로순 첫째."""
    own = known_repos.repo_root(project) or project
    mine, parent = os.path.normcase(own), os.path.normcase(os.path.dirname(own))
    out: dict[str, str] = {}
    for r in sorted(repos):
        n = os.path.basename(r)
        if not n or os.path.normcase(r) == mine or n == os.path.basename(own):
            continue
        if n not in out or (os.path.normcase(os.path.dirname(r)) == parent and os.path.normcase(os.path.dirname(out[n])) != parent):
            out[n] = r
    return out


def written_text(tool: str, ti: dict) -> str:
    if tool == "Write":
        return str(ti.get("content") or "")
    if tool == "Edit":
        return str(ti.get("new_string") or "")
    edits = ti.get("edits") if isinstance(ti.get("edits"), list) else []
    return "\n".join(str(e.get("new_string") or "") for e in edits if isinstance(e, dict))


def _sep_re(path: str) -> str:
    """경로를 정규식으로. 구분자는 `/` 와 `\\` 둘 다 받는다(Windows 기록)."""
    return r"[\\/]".join(re.escape(p) for p in re.split(r"[\\/]", path.rstrip("\\/")))


def _clean(rest: str) -> str:
    return rest.replace("\\", "/").rstrip("./")


def _abs_prefixes(root: str) -> list[str]:
    """root 를 가리키는 절대 경로 꼴의 정규식: 그대로, 홈 아래면 `~/` 꼴도."""
    out = [_sep_re(root)]
    home = os.path.expanduser("~")
    if wslib.inside(root, home) and root != home:
        out.append(r"~[\\/]" + _sep_re(os.path.relpath(root, home)))
    return out


def find_hits(text: str, sibs: dict[str, str], local_dirs: list[str]) -> dict[str, list[tuple[str, str]]]:
    """{형제 이름: [(형제 안 상대 경로, 글에 적힌 꼴)]}. sibs 는 siblings() 의 {이름: 루트}. 상대 경로가 같으면 한 번만 센다."""
    if not sibs or not text:
        return {}
    flags = re.IGNORECASE if os.name == "nt" else 0
    by_name = {(n.lower() if flags else n): n for n in sibs}
    alt = "|".join(re.escape(n) for n in sorted(sibs, key=len, reverse=True))
    # 절대 경로 꼴은 저장소마다 뿌리가 달라 저장소마다 식 하나(이름이 정해져 있다). 상대 꼴은 이름을 그룹 1 로 꺼낸다.
    forms = [(re.compile(r"(?<![\w.-])(?:%s)[\\/](%s)" % ("|".join(_abs_prefixes(root)), REST), flags), name, False)
             for name, root in sibs.items()]
    forms += [
        (re.compile(r"(?<![\w.-])(?:\.\.[\\/])+(%s)[\\/](%s)" % (alt, REST), flags), None, False),
        (re.compile(r"(?<![\w.\-/\\~$])(%s)/(%s)" % (alt, REST), flags), None, True),
    ]
    found: dict[str, dict[str, tuple[int, str]]] = {}
    for rx, fixed, must_exist in forms:
        for m in rx.finditer(text):
            if fixed:
                name, rel = fixed, _clean(m.group(1))
            else:
                g = m.group(1)
                name, rel = by_name.get(g.lower() if flags else g, g), _clean(m.group(2))
            if not rel or rel.startswith("../") or rel == "..":
                continue
            if must_exist and not exists_only_there(sibs[name], name, rel, local_dirs):
                continue
            seen = found.setdefault(name, {})
            if rel not in seen or m.start() < seen[rel][0]:
                seen[rel] = (m.start(), m.group(0).rstrip(".,"))
    # 글에 나온 순서로: 알림의 예는 처음 나온 경로다
    return {n: [(rel, shown) for rel, (_, shown) in sorted(r.items(), key=lambda kv: kv[1][0])] for n, r in found.items()}


def exists_only_there(root: str, name: str, rel: str, local_dirs: list[str]) -> bool:
    """`<name>/<rel>` 이 형제(root) 안에 있고, 이 저장소 쪽(local_dirs 기준)에는 없으면 True."""
    p = os.path.normpath(os.path.join(root, rel))
    if not wslib.inside(p.replace("\\", "/"), root.replace("\\", "/")) or not os.path.lexists(p):
        return False
    return not any(os.path.lexists(os.path.join(d, name, rel)) for d in local_dirs)


def read_seen(p: str) -> set:
    try:
        with open(p, encoding="utf-8") as f:
            return set(json.load(f).get("seen") or [])
    except (OSError, ValueError, AttributeError):
        return set()


def write_seen(p: str, seen: set) -> None:
    try:
        tmp = "%s.%d.tmp" % (p, os.getpid())
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"seen": sorted(seen)}, f)
        os.replace(tmp, p)
    except OSError:
        pass


def _example(s: str) -> str:
    return s if len(s) <= EXAMPLE_MAX else s[:EXAMPLE_MAX - 3] + "..."


def message(hits: list[tuple[str, list[tuple[str, str]]]]) -> str:
    if len(hits) == 1:
        name, rels = hits[0]
        n = len(rels)
        return ("This record names %d internal path%s of sibling repo `%s` (e.g. `%s`). Check that this repo needs %s and that "
                "`%s` is at least as public as this repo (remote, LICENSE); if unsure, ask the user, else keep only the conclusion."
                % (n, "" if n == 1 else "s", name, _example(rels[0][1]), "it" if n == 1 else "them", name))
    parts = ", ".join("`%s` (%d, e.g. `%s`)" % (name, len(rels), _example(rels[0][1])) for name, rels in hits)
    return ("This record names internal paths of sibling repos %s. Check that this repo needs them and that each is at least as "
            "public as this repo (remote, LICENSE); if unsure, ask the user, else keep only the conclusion." % parts)


def run(data: dict) -> str:
    """알림 글, 낼 것이 없으면 ""."""
    tool = data.get("tool_name") or ""
    ti = data.get("tool_input") if isinstance(data.get("tool_input"), dict) else {}
    if tool not in TOOLS:
        return ""
    fp = str(ti.get("file_path") or "")
    text = written_text(tool, ti)
    if not fp or not text or ".claude" not in fp:
        return ""
    cwd = data.get("cwd") or ""
    project = os.path.normpath(os.environ.get("CLAUDE_PROJECT_DIR") or cwd or "")
    if not project or project == os.path.dirname(project):
        return ""
    path = wslib.norm(fp, cwd or project)
    if records_rel(path, project) is None:
        return ""
    if wslib.is_off(KEY, wslib.load_env(cwd)):
        return ""
    sibs = siblings(project, known_repos.repos())
    local_dirs = [project, os.path.join(project, ".claude"), os.path.dirname(path)]
    found = find_hits(text, sibs, local_dirs)
    if not found:
        return ""
    sid = data.get("session_id")
    sp = compact_epoch.state_path("qwreey-workspace", NS, sid, data.get("agent_id"))
    seen = read_seen(sp)
    fresh = [(n, found[n]) for n in sorted(found) if "%s\t%s" % (path, n) not in seen]
    if not fresh:
        return ""
    write_seen(sp, seen | {"%s\t%s" % (path, n) for n, _ in fresh})
    return '<harness-hook name="sibling-internals" level="info"%s>\n%s\n</harness-hook>' % (harness_nonce.attr(sid), message(fresh))


def main() -> int:
    try:
        data = json.load(sys.stdin)
        if isinstance(data, dict):
            text = run(data)
            if text:
                json.dump({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": text}}, sys.stdout)
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
