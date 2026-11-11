#!/usr/bin/env python3
"""comment-hygiene 회귀 표. 실행: python3 -I test-comment-hygiene.py  (exit 0 = 통과)

임시 저장소를 만들고 훅에 PostToolUse JSON 을 넣는다(Edit 는 편집 뒤 파일을 디스크에 먼저 쓴다). 상태는 TMPDIR 로 격리한다.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HOOK = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "comment-hygiene.py")
T = tempfile.mkdtemp(prefix="commhyg-")
REPO = os.path.join(T, "repo")
os.makedirs(os.path.join(REPO, ".git"))
os.makedirs(os.path.join(REPO, ".claude"))
res = []
CNT = [0]


def check(name, ok):
    res.append((name, bool(ok)))


def call(tool, rel, ti, resp=None, sid="s1", agent=None, disk=None, env_extra=None):
    path = os.path.join(REPO, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if disk is not None:
        open(path, "w").write(disk)
    d = {"session_id": sid, "cwd": REPO, "hook_event_name": "PostToolUse", "tool_name": tool,
         "tool_input": dict(ti, file_path=path), "tool_response": resp or {}}
    if agent:
        d["agent_id"] = agent
    env = dict(os.environ, TMPDIR=T, CLAUDE_PROJECT_DIR=REPO)
    env.pop("COMMENT_HYGIENE", None)
    env.update(env_extra or {})
    p = subprocess.run([sys.executable, "-I", HOOK], input=json.dumps(d), capture_output=True, text=True, env=env, timeout=10)
    assert p.returncode == 0, p.stderr
    if not p.stdout.strip():
        return ""
    ctx = json.loads(p.stdout)["hookSpecificOutput"]["additionalContext"]
    assert re.match(r'<harness-hook name="comment-hygiene" level="info">\n', ctx) and ctx.endswith("\n</harness-hook>"), ctx
    return ctx


def write_new(rel, content, **kw):
    return call("Write", rel, {"content": content}, {"type": "create"}, disk=content, **kw)


def edit(rel, old, new, whole, **kw):
    return call("Edit", rel, {"old_string": old, "new_string": new}, disk=whole, **kw)


def uniq(name):
    CNT[0] += 1
    return f"{name}{CNT[0]}"


# ---- 탐지 ----
check("bare ledger id comment -> notice", "ledger id" in write_new("a/x.luau", "local a = 1\n-- H-973\nlocal b = 2\n", sid="d1"))
c = write_new("a/y.luau", "-- Q188\n", sid="d1")
check("notice names file, line and rules path", "a/y.luau" in c and "L1" in c and "~/.claude/rules/comments.md" in c)
check("date -> notice", "date" in write_new("a/d.luau", "x = 1 -- changed 2026-11-10 by session\n", sid="d2"))
check("round / .claude path -> notice", "round" in write_new("a/r.luau", "-- found in round 15 audit\n", sid="d3")
      and "work-history path" in write_new("a/p.luau", "-- see .claude/base/x.md for details\n", sid="d3"))
check("decision phrase -> notice", "decision phrase" in write_new("a/u.luau", "-- 사용자 결정으로 이렇게 둔다\n", sid="d4")
      and "decision phrase" in write_new("a/u2.ts", "// per user request we skip this\n", sid="d4"))

# ---- 허용 ----
ok = "-- Clamp the index so the loop never reads past the end.\n-- Ref: 2026-11-10 H-973 typing-limits 8.43\nlocal i = 1\n"
check("reason sentence + Ref tail -> silent", write_new("b/ok.luau", ok, sid="a1") == "")
check("Ref tail above a --- doc block -> silent",
      write_new("b/doc.luau", "-- Ref: 2026-11-10 H-973 typing-limits 8.43\n--- Clamps the index so the loop never reads past the end.\nlocal function f() end\n", sid="a1") == "")
check("Ref tail alone (no reason) -> notice", "without a reason" in write_new("b/lone.luau", "-- Ref: H-973\nlocal a = 1\n", sid="a2"))
check("reason with inline id -> notice (move to Ref)", "ledger id" in write_new("b/inl.luau", "-- Clamp the index so reads stay in range (H-973)\n", sid="a3"))
check("allow_ref_tail=false flags the Ref line", (open(os.path.join(REPO, ".claude", "comments.json"), "w").write('{"allow_ref_tail": false}'), write_new("b/ok2.luau", ok, sid="a4"))[1] != "")
os.remove(os.path.join(REPO, ".claude", "comments.json"))

# ---- 문서 주석 ----
check("id inside --- doc comment -> notice", "ledger id" in write_new("c/doc.luau", "--- Parses the header. H-231 covers the edge case.\nlocal function f() end\n", sid="c1"))
check("id inside /** */ block -> notice", "ledger id" in write_new("c/b.ts", "/**\n * Parses the header.\n * See Q188 for more.\n */\nexport function f() {}\n", sid="c2"))

# ---- 공개 식별자 ----
check("Quad0042 / error-code -> silent (with public_ids)", (open(os.path.join(REPO, ".claude", "comments.json"), "w").write('{"public_ids": ["Quad\\\\d{4}"]}'),
      write_new("d/e.luau", "error('Quad0042 Slot:List: bad index') -- error-code: shared\n-- Quad0042 is raised when the slot is missing.\n", sid="p1"))[1] == "")
os.remove(os.path.join(REPO, ".claude", "comments.json"))
check("error-code builtin without config -> silent", write_new("d/e2.luau", "f() -- error-code: via Helper\n", sid="p2") == "")
check("builtin standards (R15, ES2020, H264) -> silent", write_new("d/s.luau", "-- R15 rigs use ES2020 style H264 data here\n", sid="p3") == "")

# ---- 문자열·주석 아님 ----
check("id in string literal -> silent", write_new("e/s.luau", 'local s = "-- H-973 and 2026-11-10"\nlocal t = \'// Q188\'\n', sid="s1") == "")
check("id in long string -> silent", write_new("e/l.luau", "local s = [[\n-- H-973\n]]\nlocal t = `{x} -- Q188`\n", sid="s1") == "")
check("# inside py string -> silent", write_new("e/p.py", 's = "# H-973"\nt = """\n# Q188\n"""\n', sid="s1") == "")
check("url // in ts string is not a comment", write_new("e/u.ts", 'const u = "http://x/audit/H-973";\n', sid="s1") == "")
check("rust lifetime is not a string", "ledger id" in write_new("e/r.rs", "fn f<'a>(x: &'a str) -> &'a str { x } // H-973\n", sid="s2"))

# ---- 기존 줄 ----
old = "local a = 1\n-- H-973 legacy\nlocal b = 2\n"
new = "local a = 1\n-- H-973 legacy\nlocal b = 3\n"
check("existing comment line (in old_string) -> silent", edit("f/x.luau", old, new, new, sid="o1") == "")
new2 = "local a = 1\n-- H-973 legacy\n-- Q99 new one\nlocal b = 2\n"
c = edit("f/y.luau", old, new2, new2, sid="o2")
check("only the added line reported", "L3" in c and "L2" not in c)
whole = "x = 1\n" * 30 + "-- H-973 old\ny = 2\n-- Q188 new\n"
c = edit("f/z.luau", "y = 2\n", "y = 2\n-- Q188 new\n", whole, sid="o3")
check("line number is the file line", "L33" in c)
check("Write overwrite: diff vs originalFile only",
      call("Write", "f/w.luau", {"content": new2}, {"type": "update", "originalFile": old}, disk=new2, sid="o4").count("L") >= 1
      and "L2" not in call("Write", "f/w2.luau", {"content": new2}, {"type": "update", "originalFile": old}, disk=new2, sid="o5"))
check("Write overwrite with no diff source -> silent", call("Write", "f/w3.luau", {"content": new2}, {"type": "update"}, disk=new2, sid="o6") == "")
check("MultiEdit handled", "ledger id" in call("MultiEdit", "f/m.luau", {"edits": [{"old_string": "a", "new_string": "a\n-- Q55"}]}, disk="a\n-- Q55\n", sid="o7"))

# ---- dedup ----
check("first notice", write_new("g/x.luau", "-- H-1111\n", sid="g1") != "")
check("same file same epoch -> silent", write_new("g/x.luau", "-- H-1112\n", sid="g1") == "")
check("other file still notified", write_new("g/y.luau", "-- H-1113\n", sid="g1") != "")
check("subagent (agent_id) has own dedup", write_new("g/x.luau", "-- H-1114\n", sid="g1", agent="ag9") != "")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HOOK)), "lib"))
os.environ["TMPDIR"] = T
import tempfile as _tf
_tf.tempdir = T
import compact_epoch
compact_epoch.bump("g1")
check("compact epoch bump -> notified again", write_new("g/x.luau", "-- H-1115\n", sid="g1") != "")

# ---- 확장자 ----
for rel, txt in [("h/a.ts", "// H-973 x\n"), ("h/a.go", "// H-973\n"), ("h/a.rs", "// H-973\n"), ("h/a.py", "# H-973\nx = 1\n"),
                 ("h/a.kt", "/* Q188 */\n"), ("h/a.astro", "---\nconst a = 1;\n---\n<!-- H-973 -->\n<p>don't</p>\n"),
                 ("h/a.html", "<!-- Q188 -->\n"), ("h/a.lua", "--[[ H-973 ]]\n"), ("h/a.mjs", "// Q188\n")]:
    check(f"ext {rel.split('.')[-1]} -> notice", "ledger id" in write_new(rel, txt, sid=uniq("ext")))
check("py shebang / luau --!strict -> silent", write_new("h/b.py", "#!/usr/bin/env python3\n# why: x\n", sid="x1") == "" and write_new("h/b.luau", "--!strict\n", sid="x1") == "")
check(".md ignored", write_new("h/n.md", "<!-- H-973 -->\n", sid="x2") == "")
check("unknown ext ignored", write_new("h/n.json", "// H-973\n", sid="x3") == "")

# ---- 제외 ----
check("generated file (header mark) -> silent", write_new("i/gen.luau", "-- generated by tool, do not edit\n-- H-973\n", sid="x4") == "")
check("fixtures dir -> silent", write_new("i/fixtures/a.luau", "-- H-973\n", sid="x5") == "")
open(os.path.join(REPO, ".claude", "comments.json"), "w").write('{"exclude": ["docs/**", "legacy/*.luau"]}')
check("config exclude glob -> silent", write_new("docs/a/x.luau", "-- H-973\n", sid="x6") == "" and write_new("legacy/x.luau", "-- H-973\n", sid="x6") == "")
open(os.path.join(REPO, ".claude", "comments.json"), "w").write('{"patterns": {"ledger": null}}')
check("pattern null disables it", write_new("j/x.luau", "-- H-973\n", sid="x7") == "")
open(os.path.join(REPO, ".claude", "comments.json"), "w").write('{not json')
check("broken config -> defaults", write_new("j/y.luau", "-- H-973\n", sid="x8") != "")
os.remove(os.path.join(REPO, ".claude", "comments.json"))
check("COMMENT_HYGIENE=off -> silent", write_new("j/z.luau", "-- H-973\n", sid="x9", env_extra={"COMMENT_HYGIENE": "off"}) == "")
check("other tools / bad stdin -> silent",
      subprocess.run([sys.executable, "-I", HOOK], input="{no", capture_output=True, text=True).stdout == ""
      and subprocess.run([sys.executable, "-I", HOOK], input=json.dumps({"tool_name": "Bash", "tool_input": {}}), capture_output=True, text=True).stdout == "")

# ---- 오탐 표본: 이유 문장만 있는 일반 주석 ----
clean = """--!strict
-- Walk children in reverse so removals do not shift unvisited indices.
-- UTF-8 bytes above 0x7F are copied as-is; the 2 or 3 byte forms matter here.
local x = 1 -- 1-based
--- Returns the key. Throws when `n` > 10 or the slot is nil.
-- TODO: handle the empty case
-- 이 값은 렌더러가 프레임마다 다시 읽기 때문에 캐시하지 않는다.
"""
check("plain reason comments -> no false positive", write_new("k/clean.luau", clean, sid="fp1") == "")

# ---- quad 표본(읽기 전용; 없으면 건너뜀) ----
QUAD = "/code/Projects/quad"
if os.path.isdir(QUAD):
    sys.path.insert(0, os.path.dirname(HOOK))
    import importlib.util
    spec = importlib.util.spec_from_file_location("ch", HOOK)
    ch = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ch)
    cfg = ch.load_cfg(QUAD)
    cfg["public_ids"] = ["Quad\\d{4}"]
    pats, pub = ch.compile_patterns(cfg)
    flagged = total = 0
    flagged_lines = []
    for root, dirs, files in os.walk(QUAD):
        dirs[:] = [d for d in dirs if d not in (".git", "node_modules", ".claude", "Packages", "luau_packages")]
        for f in files:
            if not f.endswith(".luau"):
                continue
            p = os.path.join(root, f)
            try:
                t = open(p, encoding="utf-8").read()
            except Exception:
                continue
            rows = ch.lex(t, "lua")
            added = {i for i, r in enumerate(rows) if r["c"]}
            total += len(added)
            for ln, why in ch.check_lines(rows, added, pats, pub, cfg):
                flagged += 1
                flagged_lines.append((os.path.relpath(p, QUAD), ln, why))
    print(f"quad sample: {total} comment lines, {flagged} flagged ({100 * flagged / max(total, 1):.1f}%)")
    json.dump(flagged_lines, open(os.path.join(T, "quad-flagged.json"), "w"), ensure_ascii=False)
    check("quad scan ran", total > 0)

for name, ok in res:
    print(("PASS " if ok else "FAIL ") + name)
fails = [r for r in res if not r[1]]
print(f"{len(res) - len(fails)}/{len(res)}")
if os.environ.get("KEEP_T"):
    print(T)
else:
    shutil.rmtree(T, ignore_errors=True)
sys.exit(1 if fails else 0)
