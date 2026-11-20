"""conventions-check 와 reuse-check 가 함께 쓰는 훅 입력 읽기: 프로젝트 루트, 추가한 줄 찾기, 건너뛸 경로. 표준 라이브러리만 쓴다."""
import os
import re
from collections import Counter

MAX_BYTES = 1_000_000
SKIP_PARTS = {"node_modules", ".git", "luau_packages", "roblox_packages", "lune_packages", "Packages", "vendor", "third_party",
              "build", "dist", "refs", "typedefs", "testdata", "fixtures", "__snapshots__", "snapshots", "__pycache__", ".venv", "venv", "target"}
SKIP_SUFFIX = (".d.luau", ".d.ts", ".d.mts", ".min.js", ".gen.ts", ".pb.go", "_pb2.py", "_pb2_grpc.py")
GEN_MARK = re.compile(r"generated|do not edit|@generated|손으로 고치지 않는다|만든 것:", re.I)


def project_root(path, data):
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    if env and path.startswith(env.rstrip("/") + "/"):
        return env
    d = os.path.dirname(path)
    while d and d != "/":
        if os.path.exists(os.path.join(d, ".git")) or os.path.isdir(os.path.join(d, ".claude")):
            return d
        up = os.path.dirname(d)
        if up == d:  # `//` 로 시작하는 경로는 dirname 이 `//` 에서 줄지 않는다
            break
        d = up
    return data.get("cwd") or os.path.dirname(path)


def added_set(old, new, base_line):
    """new(여러 줄 문자열)의 줄 중 old 에 없던 줄의 파일 줄 번호(0 기반)."""
    have = Counter(l.strip() for l in old.split("\n")) if old else Counter()
    res = set()
    for idx, l in enumerate(new.split("\n")):
        t = l.strip()
        if not t:
            continue
        if have[t] > 0:
            have[t] -= 1
        else:
            res.add(base_line + idx)
    return res


def patch_added(sp):
    """tool_response.structuredPatch(훈크 목록)에서 새 파일 기준 추가 줄 번호(0 기반)."""
    res = set()
    for h in sp or []:
        try:
            cur = int(h["newStart"]) - 1
            for l in h.get("lines") or []:
                if l.startswith("+"):
                    res.add(cur)
                    cur += 1
                elif l.startswith("-"):
                    continue
                else:
                    cur += 1
        except (KeyError, TypeError, ValueError):
            return None
    return res


def locate(text, new_string):
    """text 안에서 new_string 이 시작하는 줄 번호(0 기반). 없으면 None."""
    if not new_string:
        return None
    k = text.find(new_string)
    return None if k < 0 else text.count("\n", 0, k)


def collect(tool, ti, resp, text):
    """(검사할 텍스트, 추가 줄 번호 집합) 또는 None. 텍스트는 가능하면 파일 전체."""
    if tool == "Write":
        content = ti.get("content")
        if not isinstance(content, str):
            return None
        t = resp.get("type")
        orig = resp.get("originalFile")
        if t == "create":
            return content, added_set("", content, 0)
        if isinstance(orig, str):
            return content, added_set(orig, content, 0)
        sp = patch_added(resp.get("structuredPatch"))
        return (content, sp) if sp is not None else None
    edits = [ti] if tool == "Edit" else [e for e in (ti.get("edits") or []) if isinstance(e, dict)]
    if text is None:
        return None
    added = set()
    for e in edits:
        new, old = e.get("new_string"), e.get("old_string") or ""
        if not isinstance(new, str) or not new:
            continue
        base = locate(text, new)
        if base is None:
            continue
        added |= added_set(old, new, base)
    return text, added
