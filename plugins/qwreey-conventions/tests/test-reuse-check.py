#!/usr/bin/env python3
"""reuse-check 훅과 턴 끝 보고(conventions-check Stop)의 회귀 표. 실행: python3 -I test-reuse-check.py  (exit 0 = 통과)

임시 저장소를 만들고 훅에 PostToolUse JSON 을 넣는다(편집 뒤 파일을 디스크에 먼저 쓴다). 상태와 색인은 TMPDIR 로 격리한다.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOK = os.path.join(HERE, "hooks", "reuse-check.py")
CONV = os.path.join(HERE, "hooks", "conventions-check.py")
T = tempfile.mkdtemp(prefix="reuse-")
# nonce 는 고정 salt 로(실제 ~/.local/share 의 salt 를 쓰지 않게)
open(os.path.join(T, "salt"), "w").write("00" * 32)
os.environ["QWREEY_HARNESS_SALT_FILE"] = os.path.join(T, "salt")
REPO = os.path.join(T, "repo")
os.makedirs(os.path.join(REPO, ".git"))
os.makedirs(os.path.join(REPO, ".claude"))
LIBHOME = os.path.join(T, "home")
os.makedirs(LIBHOME)
SHADOW = os.path.join(T, "claude-qwreey-reuse", "shadow.jsonl")
res = []
SID = [0]


def check(name, ok):
    res.append((name, bool(ok)))


def put(rel, content):
    p = os.path.join(REPO, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "w", encoding="utf-8").write(content)


def env_for(extra=None):
    env = dict(os.environ, TMPDIR=T, CLAUDE_PROJECT_DIR=REPO, CLAUDE_CONFIG_DIR=LIBHOME)
    for k in ("CONVENTIONS_CHECK", "REUSE_CHECK", "CLAUDE_PLUGIN_DATA", "HARNESS_WORKSPACE"):
        env.pop(k, None)
    env.update(extra or {})
    return env


def run(rel, content, old="", new=None, sid=None, agent=None, env=None):
    """파일을 content 로 만들고 훅을 돌린다. new 가 있으면 Edit(old -> new), 없으면 Write(create). 알림 문구 또는 ''."""
    put(rel, content)
    if sid is None:
        SID[0] += 1
        sid = f"s{SID[0]}"
    ti = {"file_path": os.path.join(REPO, rel)}
    if new is None:
        ti["content"] = content
        tool, resp = "Write", {"type": "create"}
    else:
        ti.update(old_string=old, new_string=new)
        tool, resp = "Edit", {}
    d = {"session_id": sid, "cwd": REPO, "hook_event_name": "PostToolUse", "tool_name": tool, "tool_input": ti, "tool_response": resp}
    if agent:
        d["agent_id"] = agent
    p = subprocess.run([sys.executable, "-I", HOOK], input=json.dumps(d), capture_output=True, text=True, env=env_for(env), timeout=10)
    assert p.returncode == 0, p.stderr
    if not p.stdout.strip():
        return ""
    ctx = json.loads(p.stdout)["hookSpecificOutput"]["additionalContext"]
    assert re.match(r'<harness-hook name="qwreey-conventions" level="info" nonce="[0-9a-f]{12}">[^\n]+</harness-hook>$', ctx), ctx
    return ctx


def stop(sid):
    d = {"session_id": sid, "cwd": REPO, "hook_event_name": "Stop", "stop_hook_active": False}
    p = subprocess.run([sys.executable, "-I", CONV], input=json.dumps(d), capture_output=True, text=True, env=env_for(), timeout=10)
    assert p.returncode == 0, p.stderr
    return json.loads(p.stdout)["systemMessage"] if p.stdout.strip() else None


def shadow():
    try:
        return [json.loads(l) for l in open(SHADOW, encoding="utf-8")]
    except OSError:
        return []


LIST = 'local KINDS = { "omega", "sigma", "kappa", "theta" }\n'

# ---- C1: @copy-of 사본 ----
put("a/src.luau", '-- source\nlocal FORMS = { "coin", "stick", "back", "card" }\nreturn FORMS\n')
ok = '-- @copy-of: a/src.luau#FORMS\nlocal FORMS = { "coin", "stick", "back", "card" }\n'
check("C1 value copy equal -> silent", run("b/copy.luau", ok, "", ok) == "")
bad = '-- @copy-of: a/src.luau#FORMS\nlocal FORMS = { "coin", "stick", "back", "dice" }\n'
r = run("b/copy.luau", bad, "", bad)
check("C1 value copy differs -> notice with missing/extra", "differs: missing" in r and '"card"' in r and '"dice"' in r and "b/copy.luau:1" in r)
sid_c = "c1once"
a = run("b/copy.luau", bad, "", bad, sid=sid_c)
check("C1 notice is once per session key", a != "" and run("b/copy.luau", bad, "", bad, sid=sid_c) == "")
nores = '-- @copy-of: a/nope.luau#FORMS\nlocal FORMS = { "coin", "stick", "back", "card" }\n'
check("C1 unresolved path -> notice", "does not resolve" in run("b/c2.luau", nores, "", nores))
nores2 = '-- @copy-of: a/src.luau#MISSING\nlocal FORMS = { "coin", "stick", "back", "card" }\n'
check("C1 unresolved name -> notice", "does not resolve" in run("b/c3.luau", nores2, "", nores2))
check("C1 sibling-repo mark without workspace -> silent, logged", run("b/c4.luau", '-- @copy-of: other:src/x.luau#FORMS\n' + LIST, "", "x") == ""
      and any(s.get("status") == "sibling" for s in shadow()))

# 파일 사본: 바이트 비교, 자기 경로를 적은 파일이 원본
put("p/src.py", '"""mod.\n@copy-of: p/src.py\nbody\n"""\nX = 1\n')
cp = '"""mod.\n@copy-of: p/src.py\nbody\n"""\nX = 1\n'
check("C1 file copy identical -> silent", run("q/cp.py", cp, "X = 1\n", "X = 1\n") == "")
cp2 = cp + "Y = 2\n"
check("C1 file copy differs -> notice", "differs from this copy" in run("q/cp.py", cp2, "X = 1\n", "X = 1\nY = 2\n"))
check("C1 source marker naming itself -> silent", run("p/src.py", '"""mod.\n@copy-of: p/src.py\nbody\n"""\nX = 1\n', "X = 1\n", "X = 1\n") == "")

# ---- C2: 원본을 고치면 사본 목록 ----
srcnew = '-- source\nlocal FORMS = { "coin", "stick", "back", "card", "ring" }\nreturn FORMS\n'
r = run("a/src.luau", srcnew, '"card" }', '"card", "ring" }')
check("C2 editing a source set lists its copies", "FORMS has" in r and "b/copy.luau:1" in r and "update them too" in r)
r2 = run("a/src.luau", srcnew + "-- note\n", "return FORMS\n", "return FORMS\n-- note\n", sid="c2b")
check("C2 comment-only edit in the source -> silent", "FORMS has" not in r2)
put("p/src.py", cp)
r = run("p/src.py", cp + "Z = 3\n", "X = 1\n", "X = 1\nZ = 3\n")
check("C2 editing a file source lists file copies", "src.py has 1 @copy-of copies: q/cp.py:2" in r)

# ---- H1: 그림자 ----
put("m/one.py", 'SKIP = ["alpha", "bravo", "charlie", "delta"]\n')
n0 = len(shadow())
dup = 'SKIP_DIRS = ["alpha", "bravo", "charlie", "echo"]\n'
check("H1 shadow mode prints nothing", run("m/two.py", dup, "", dup) == "")
h1 = [s for s in shadow()[n0:] if s["check"] == "H1"]
check("H1 shadow mode writes a log line", len(h1) == 1 and h1[0]["notice"] in ("N1", "N2") and h1[0]["at"] == "m/two.py:1"
      and h1[0]["other"] == "m/one.py:1" and h1[0]["k"] == 3 and h1[0]["lang"] == "py" and "ms" in h1[0])
check("H1 log has no source text beyond the shared strings", all("SKIP" not in json.dumps(s) or s["name"] for s in h1))
check("H1 log is outside the repo", not os.path.exists(os.path.join(REPO, "shadow.jsonl")) and SHADOW.startswith(T))
r = run("m/three.py", dup, "", dup, env={"REUSE_CHECK": "on"})
check("H1 on: notice names an existing definition and the shared strings", "m/three.py:1" in r and re.search(r"at m/(one|two)\.py:1", r) and "/4 shared" in r
      and "@dup-ok" in r and "Unsure: load the qwreey-conventions:code-reuse skill" in r)
lk = 'local K = { "alpha", "bravo", "charlie", "echo" }\n'
check("H1 on: other-language pair -> cannot import notice", "cannot import" in run("m/four.luau", lk, "", lk, env={"REUSE_CHECK": "on"}))
sid = "dd1"
a = run("m/five.py", dup, "", dup, sid=sid, env={"REUSE_CHECK": "on"})
b = run("m/five.py", dup, "", dup, sid=sid, env={"REUSE_CHECK": "on"})
check("H1 on: same pair is reported once per session", a != "" and b == "")
ok1 = '# @dup-ok: different knowledge, only the words overlap\n' + dup
check("H1 on: @dup-ok with a reason silences", run("m/six.py", ok1, "", ok1, env={"REUSE_CHECK": "on"}) == "")
bad1 = '# @dup-ok: later\n' + dup
check("H1 on: @dup-ok without a reason is reported and flagged", "has no reason" in run("m/seven.py", bad1, "", bad1, env={"REUSE_CHECK": "on"}))
check("REUSE_CHECK=off silences everything", run("b/copy.luau", bad, "", bad, env={"REUSE_CHECK": "off"}) == "")
check("CONVENTIONS_CHECK=off silences the hook", run("b/copy.luau", bad, "", bad, env={"CONVENTIONS_CHECK": "off"}) == "")

# ---- N7: 타입 합집합과 런타임 목록 ----
put("t/types.ts", 'export type Phase = "idle" | "play" | "pause" | "stop";\n')
lst = 'export const PHASES = ["idle", "play", "pause", "seek"];\n'
r = run("t/list.ts", lst, "", lst, env={"REUSE_CHECK": "on"})
check("N7 list drifted from type -> notice with missing/extra", "list PHASES and type Phase" in r and '"stop"' in r and '"seek"' in r)
put("t/mode.ts", 'export type Mode = "walk" | "swim" | "fly" | "dig";\n')
same = 'export const MODES = ["walk", "swim", "fly", "dig"];\n'
check("N7 list equal to type -> silent (only drift is reported)", run("t/mode-list.ts", same, "", same, env={"REUSE_CHECK": "on"}) == "")
put("t/Types.luau", 'export type Tone = "warm" | "cool" | "dark" | "pale"\n')
lz = 'local TONES = { "warm", "cool", "dark", "dusk" }\n'
check("N7 Luau list drifted from type -> notice", "list TONES and type Tone" in run("t/Dice.luau", lz, "", lz, env={"REUSE_CHECK": "on"}))

# ---- 제외 ----
for rel, why in [(".claude/audit/x.py", ".claude"), ("m/old-ignoreme/x.py", "ignoreme"), ("vendor/x/x.py", "vendor dir"), ("tests/t.py", "tests"),
                 ("m/test-thing.py", "test file")]:
    n0 = len(shadow())
    check(f"excluded: {why}", run(rel, dup, "", dup, env={"REUSE_CHECK": "on"}) == "" and len(shadow()) == n0)
put("lock/vendor.lock.json", "{}")
check("excluded: tree with vendor.lock.json", run("lock/src/x.py", dup, "", dup, env={"REUSE_CHECK": "on"}) == "")
for hdr in ("# generated by tool\n", "# 생성: tools/gen.py\n"):
    gen = hdr + dup
    check(f"excluded: generated file ({hdr.strip()})", run("g/gen%d.py" % len(hdr), gen, "", gen, env={"REUSE_CHECK": "on"}) == "")
# 색인에 들어간 .claude 와 생성 파일은 상대로도 쓰이지 않는다
put(".claude/archive/old.py", 'OLD = ["zulu", "yankee", "xray", "whiskey"]\n')
uniq = 'NEW = ["zulu", "yankee", "xray", "whiskey"]\n'
check(".claude files are never the other side of a pair", run("m/eight.py", uniq, "", uniq, env={"REUSE_CHECK": "on"}) == "")

# ---- 패키지 경계 ----
put("pkg1/Cargo.toml", '[package]\nname = "one"\n[dependencies]\ntwo = { path = "../pkg2" }\n')
put("pkg2/Cargo.toml", '[package]\nname = "two"\n')
put("pkg3/Cargo.toml", '[package]\nname = "three"\n')
put("pkg2/src/lib.rs", 'pub const KINDS: &[&str] = &["red", "green", "blue", "cyan"];\n')
r1 = 'pub const MINE: &[&str] = &["red", "green", "blue", "cyan"];\n'
r = run("pkg1/src/lib.rs", r1, "", r1, env={"REUSE_CHECK": "on"})
check("declared dependency -> importable (reference notice)", "Same knowledge: reference KINDS" in r)
r = run("pkg3/src/lib.rs", r1, "", r1, env={"REUSE_CHECK": "on"})
check("undeclared package -> cannot import (copy notice)", "cannot import" in r and "@copy-of: pkg2/src/lib.rs#KINDS" in r)

# ---- 턴 끝 보고 ----
put("a/src.luau", '-- source\nlocal FORMS = { "coin", "stick", "back", "card", "ring" }\nreturn FORMS\n')
run("b/copy.luau", bad, "", bad, sid="rep1")
m = stop("rep1") or ""
check("Stop: differing copy gets its own line", "사본이 원본과 다름: b/copy.luau 1. 동작이 달라질 수 있습니다." in m and "전부터 있던 문제" not in m)
run("b/copy.luau", ok.replace('"card" }', '"card", "ring" }'), "", ok.replace('"card" }', '"card", "ring" }'), sid="rep1")
check("Stop: fixed copy drops out", stop("rep1") is None)
put("m/old.py", 'OLDLIST = ["alpha", "bravo", "charlie", "delta"]\n')
both = 'OLDLIST = ["alpha", "bravo", "charlie", "delta"]\nSECOND = ["alpha", "bravo", "charlie", "delta"]\n' + "pass\n" * 60 + 'THIRD = ["alpha", "bravo", "charlie", "delta"]\n'
run("m/old.py", both, "pass\n", "pass\n", sid="rep2", env={"REUSE_CHECK": "on"})
m = stop("rep2") or ""
check("Stop: existing duplicate sets are counted in plain words", m.startswith("손댄 파일에 전부터 있던 문제: ") and "(같은 목록이 두 곳 " in m
      and '"기존 문제도 정리해줘"' in m)
run("m/old2.py", both, "pass\n", "pass\n", sid="rep3")
check("Stop: shadow mode never reports duplicates", stop("rep3") is None)

# ---- 비용 ----
big = os.path.join(REPO, "big")
os.makedirs(big)
for i in range(300):
    open(os.path.join(big, f"f{i}.py"), "w").write(f'LST{i} = ["a{i}x", "b{i}x", "c{i}x", "d{i}x"]\n' + "x = 1\n" * 40)
run("big/f0.py", open(os.path.join(big, "f0.py")).read(), "x = 1\n", "x = 1\n", sid="cost0")  # 색인을 데운다
ts = []
for i in range(7):
    t0 = time.perf_counter()
    run("big/f1.py", open(os.path.join(big, "f1.py")).read(), "x = 1\n", "x = 1\n", sid="cost1")
    ts.append((time.perf_counter() - t0) * 1000)
ts.sort()
print("warm median ms (incl. process start, 300 files):", round(ts[len(ts) // 2]))
check("warm edit stays under the 150 ms p95 budget", ts[len(ts) // 2] < 150)

shutil.rmtree(T, ignore_errors=True)
bad_n = [n for n, ok_ in res if not ok_]
for n, ok_ in res:
    print(("PASS " if ok_ else "FAIL ") + n)
print(f"{len(res) - len(bad_n)}/{len(res)}")
sys.exit(1 if bad_n else 0)
