"""Shared helpers for audit/45: corpus trees, search runs, output post-processing, token estimate."""
import importlib.util, json, os, re, shutil, subprocess, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
RAW = HERE / "raw"
spec = importlib.util.spec_from_file_location("m39", HERE.parent / "39-records-experiment" / "measure.py")
m39 = importlib.util.module_from_spec(spec); spec.loader.exec_module(m39)
BIN = "/code/Projects/coderag/target/release/coderag"
DOCTOR = Path("/code/Projects/claude-doctor")
COEFF = (0.4, 1.6, 1.5)
HDR = re.compile(r"^(\S+?):(\d+)-(\d+)(?:\s|$)(.*)")
LEG = re.compile(r"^@(\w+) = (/.*)$")

PACK_Q = [
 ("p1", "__index", "luau 에서 __index 메타메서드는 어떻게 동작하고 성능에 어떤 영향이 있나?", ["skills/luau-perf/references/metatables.md"]),
 ("p2", "table.freeze", "table.freeze 를 쓰면 무엇이 바뀌고 주의할 점은?", ["skills/luau-perf/references/metatables.md"]),
 ("p3", "type function 제약", "type function 안에서 할 수 없는 일(제약·한도)은 무엇인가?", ["skills/luau-types/references/type-functions-limits.md"]),
 ("p4", "debug.info", "debug.info 가 최적화 수준에 따라 어떻게 달라지나?", ["skills/luau-testing/references/optimize-levels.md", "skills/luau-style/references/errors.md"]),
 ("p5", "상한", "제네릭 타입 매개변수의 상한(bound)은 어떻게 다루나?", ["skills/luau-types/references/generics.md"]),
]

def est(text):
    a = h = o = 0
    for c in text:
        if ord(c) < 128: a += 1
        elif 0xAC00 <= ord(c) <= 0xD7A3: h += 1
        else: o += 1
    return round(COEFF[0] * a + COEFF[1] * h + COEFF[2] * o)

def run(cmd, env, cwd):
    return subprocess.run(["choom", "-n", "1000", "--", "timeout", "600"] + cmd, env=env, cwd=cwd, stdin=subprocess.DEVNULL, capture_output=True, text=True)

def split_results(out):
    """-> (preamble lines, [ [header, desc-or-None, extra lines...] ])"""
    pre, res = [], []
    for ln in out.splitlines():
        if ln.startswith(" "):
            if res: res[-1].append(ln)
        elif HDR.match(ln) and not LEG.match(ln):
            res.append([ln])
        elif ln.startswith("@") and not res:
            pre.append(ln)
        elif not res:
            pre.append(ln)
        else:
            res[-1].append(ln)
    return pre, res

def join(pre, res):
    return "\n".join(pre + [l for r in res for l in r]) + "\n"

def v_top(out, n):
    pre, res = split_results(out)
    return join(pre, [r if i < n else r[:1] for i, r in enumerate(res)])

def v_cap(out, k):
    pre, res = split_results(out)
    new = []
    for r in res:
        r = list(r)
        if len(r) > 1:
            d = r[1].strip()
            if len(d) > k: d = d[:k] + "…"
            r[1] = "  " + d
        new.append(r)
    return join(pre, new)

def v_none(out):
    return v_top(out, 0)

def result_locs(out):
    pre, res = split_results(out)
    return [r[0].split(" ")[0] for r in res]

def doc_of(loc, legend):
    """'@P/rel/path.md:1-5' -> absolute path (without line range)."""
    p = loc.rsplit(":", 1)[0]
    m = re.match(r"^@(\w+)/(.*)$", p)
    if m and m.group(1) in legend:
        return legend[m.group(1)].rstrip("/") + "/" + m.group(2)
    return p

def legend_of(out):
    return {m.group(1): m.group(2) for l in out.splitlines() if (m := LEG.match(l))}
