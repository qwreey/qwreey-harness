#!/usr/bin/env python3
"""H1(문자열 묶음 중복) 초안 검사를 저장소 전체에 돌려 묶음(cluster)과 걸린 시간을 보인다. 읽기만 한다.

실행: python3 -I sets_probe.py <저장소> [--raw] [--mirror]
  --raw     걸러내기(낱말 모양, argv, 정의 쪽, 경로) 없이 coderag .claude/audit/47-coderag-code-quality litsets.py 와 같은 기준으로 센다
  --mirror  타입 합집합과 런타임 목록이 짝인 경우(SAME/DIFF)만 보인다
훅 초안과 다른 점: 주석 제거가 줄 단위 간이판이라 블록 주석(--[[ ]], /* */) 안의 묶음을 못 거른다. 훅은 conventions-check 의 렉서를 쓴다.
"""
import itertools
import os
import re
import sys
import time

EXT = {".rs": "rust", ".py": "py", ".luau": "lua", ".lua": "lua", ".ts": "c", ".tsx": "c", ".js": "c", ".mjs": "c"}
SKIP = {"target", "node_modules", ".git", "Packages", "luau_packages", "roblox_packages", "lune_packages", "vendor", "dist",
        "build", "__pycache__", ".venv", "fixtures", "testdata", "worktrees", "archive", "raw", "refs", "stories", "gallery", "examples"}
TEST = re.compile(r"(^|/)(tests?|specs?|__tests__)(/|$)|\.(spec|test|story)\.|_test\.|(^|/)test[-_]|tests\.rs$", re.I)
STR = r'"[^"\\\n]*"|\'[^\'\\\n]*\''
GROUP = re.compile(r"[\[\{\(]((?:\s*(?:" + STR + r")\s*[,;]?)+)\s*[\]\}\)]|((?:(?:" + STR + r")\s*(?:\||\bor\b)\s*)+(?:" + STR + r"))", re.S)
WORD = re.compile(r"^(?=.*[A-Za-z])[\w.\-/ ]{2,}$")
# 정의 줄: 이름 붙은 바인딩, const/static/let/local/type. 정의가 아닌 쪽끼리(if x in (...) 두 번)는 알리지 않는다
DEF = re.compile(r"^\s*(?:pub(?:\([\w:]+\))?\s+)?(?:export\s+)?(?:const|static|let|local|type)\s+\w+"
                 r"|^\s*[A-Za-z_]\w*\s*(?::[^=]+)?=\s*(?:table\.freeze\(|frozenset\(|set\()?[\[\{\(]|^\s*[A-Za-z_]\w*\s*:\s*&?\[")
TYPE = re.compile(r"^\s*(?:export\s+)?type\s+\w+|^\s*\w+\s*:\s*[\"']")
COMMENT = {"py": ("#",), "rust": ("//", "*", "/*"), "c": ("//", "*", "/*"), "lua": ("--",)}


def groups_of(path, rel, fam):
    try:
        src = open(path, encoding="utf-8").read()
    except (OSError, UnicodeDecodeError):
        return []
    if fam == "rust" and "#[cfg(test)]" in src:
        src = src[:src.find("#[cfg(test)]")]
    lines = ["" if l.lstrip().startswith(COMMENT[fam]) else l for l in src.split("\n")]
    src = "\n".join(lines)
    out = []
    for m in GROUP.finditer(src):
        s = frozenset(x[1:-1] for x in re.findall(STR, m.group(0)) if len(x) > 2)
        if len(s) >= 3:
            ln = src.count("\n", 0, m.start()) + 1
            out.append({"rel": rel, "ln": ln, "set": s, "lines": lines})
    return out


def scan(root):
    out = []
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if d not in SKIP and not d.startswith(".")]
        for f in fn:
            fam = EXT.get(os.path.splitext(f)[1])
            p = os.path.join(dp, f)
            rel = os.path.relpath(p, root)
            if fam and not TEST.search(rel) and not f.endswith(".min.js") and os.path.getsize(p) <= 1_000_000:
                out += groups_of(p, rel, fam)
    return out


def is_def(g):
    """묶음이 시작하는 줄이나 그 위 3줄 안(여러 줄 리터럴)에 정의 머리가 있나."""
    L = g["lines"]
    for k in range(g["ln"] - 1, max(-1, g["ln"] - 5), -1):
        if DEF.match(L[k]):
            return True
        if k < g["ln"] - 1 and not L[k].rstrip().endswith((",", "(", "{", "[", "=")):
            return False
    return False


def filtered(g):
    words = frozenset(x for x in g["set"] if WORD.match(x))
    if any(x.startswith("-") for x in g["set"]) and len(g["set"]) <= 8:
        return None  # argv 목록(git rev-parse --show-toplevel 류)
    return dict(g, set=words, d=is_def(g), t=bool(TYPE.match(g["lines"][g["ln"] - 1]))) if len(words) >= 3 else None


def pairs(gs, raw):
    res = []
    for a, b in itertools.combinations(gs, 2):
        same_file = a["rel"] == b["rel"]
        if same_file and abs(a["ln"] - b["ln"]) < (3 if raw else 50):
            continue
        i = a["set"] & b["set"]
        j = len(i) / len(a["set"] | b["set"])
        if not (len(i) >= 3 or (len(i) >= 2 and j >= 0.5)):
            continue
        if not raw:
            if not (a["d"] or b["d"]) or (same_file and not (a["d"] and b["d"])):
                continue
            if a["t"] != b["t"]:
                continue  # 타입 합집합과 런타임 목록의 짝(--mirror 로 따로 본다)
            if a["t"] and b["t"] and a["set"] != b["set"]:
                continue  # 타입끼리는 같을 때만(컴포넌트마다 부분집합이 다른 것은 다른 지식)
        res.append((j, a, b, i))
    return res


def clusters(ps):
    par = {}

    def find(x):
        while par.setdefault(x, x) != x:
            x = par[x]
        return x
    for _, a, b, _ in ps:
        par[find((a["rel"], a["ln"]))] = find((b["rel"], b["ln"]))
    cl = {}
    for p in ps:
        cl.setdefault(find((p[1]["rel"], p[1]["ln"])), []).append(p)
    return list(cl.values())


def main():
    root = os.path.abspath(sys.argv[1])
    raw, mirror = "--raw" in sys.argv, "--mirror" in sys.argv
    t0 = time.perf_counter()
    gs = scan(root)
    t1 = time.perf_counter()
    if not raw:
        gs = [x for x in map(filtered, gs) if x]
    if mirror:
        for a, b in itertools.combinations(gs, 2):
            if a["t"] != b["t"] and len(a["set"] & b["set"]) >= 3:
                print(("SAME" if a["set"] == b["set"] else "DIFF"), f'{a["rel"]}:{a["ln"]} ~ {b["rel"]}:{b["ln"]}',
                      "only_a=", sorted(a["set"] - b["set"])[:4], "only_b=", sorted(b["set"] - a["set"])[:4])
        return 0
    ps = pairs(gs, raw)
    t2 = time.perf_counter()
    cls = clusters(ps)
    for v in cls:
        locs = sorted({(p[1]["rel"], p[1]["ln"]) for p in v} | {(p[2]["rel"], p[2]["ln"]) for p in v})
        print(f"[{len(v)}] {sorted(v[0][3])[:5]} :: " + ", ".join(f"{r}:{n}" for r, n in locs[:5]))
    print(f"sets={len(gs)} pairs={len(ps)} clusters={len(cls)} scan_ms={1000 * (t1 - t0):.0f} pair_ms={1000 * (t2 - t1):.0f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
