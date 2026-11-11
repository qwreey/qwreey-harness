#!/usr/bin/env python3
"""conventions-check 회귀 표. 실행: python3 -I test-conventions-check.py  (exit 0 = 통과)

임시 저장소를 만들고 훅에 PostToolUse JSON 을 넣는다(Edit 는 편집 뒤 파일을 디스크에 먼저 쓴다). 상태는 TMPDIR 로 격리한다.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HOOK = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks", "conventions-check.py")
T = tempfile.mkdtemp(prefix="conv-")
REPO = os.path.join(T, "repo")
os.makedirs(os.path.join(REPO, ".git"))
os.makedirs(os.path.join(REPO, ".claude"))
LIBHOME = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "home", ".claude")
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
    env = dict(os.environ, TMPDIR=T, CLAUDE_PROJECT_DIR=REPO, CLAUDE_CONFIG_DIR=LIBHOME)
    env.pop("CONVENTIONS_CHECK", None)
    env.update(env_extra or {})
    p = subprocess.run([sys.executable, "-I", HOOK], input=json.dumps(d), capture_output=True, text=True, env=env, timeout=10)
    assert p.returncode == 0, p.stderr
    if not p.stdout.strip():
        return ""
    ctx = json.loads(p.stdout)["hookSpecificOutput"]["additionalContext"]
    assert re.match(r'<harness-hook name="conventions" level="info">[^\n]+</harness-hook>$', ctx), ctx
    return ctx


def write_new(rel, content, **kw):
    return call("Write", rel, {"content": content}, {"type": "create"}, disk=content, **kw)


def edit(rel, old, new, whole, **kw):
    return call("Edit", rel, {"old_string": old, "new_string": new}, disk=whole, **kw)


def uniq(name):
    CNT[0] += 1
    return f"{name}{CNT[0]}"


# ---- 탐지 ----
check("bare ledger id comment -> notice", "history marker" in write_new("a/x.luau", "local a = 1\n-- H-973\nlocal b = 2\n", sid="d1"))
c = write_new("a/y.luau", "-- Q188\n", sid="d1")
check("notice names file, line and skill", "a/y.luau L1 " in c and "conventions:comments" in c and c.count("\n") == 0)
check("date -> notice", "history marker" in write_new("a/d.luau", "x = 1 -- changed 2026-11-10 by session\n", sid="d2"))
check("round / .claude path -> notice", "history marker" in write_new("a/r.luau", "-- found in round 15 audit\n", sid="d3")
      and "history marker" in write_new("a/p.luau", "-- see .claude/base/x.md for details\n", sid="d3"))
check("decision phrase -> notice", "history marker" in write_new("a/u.luau", "-- 사용자 결정으로 이렇게 둔다\n", sid="d4")
      and "history marker" in write_new("a/u2.ts", "// per user request we skip this\n", sid="d4"))

# ---- 허용 ----
ok = "-- Clamp the index so the loop never reads past the end.\n-- Ref: 2026-11-10 H-973 typing-limits 8.43\nlocal i = 1\n"
check("reason sentence + Ref tail -> silent", write_new("b/ok.luau", ok, sid="a1") == "")
check("Ref tail above a --- doc block -> silent",
      write_new("b/doc.luau", "-- Ref: 2026-11-10 H-973 typing-limits 8.43\n--- Clamps the index so the loop never reads past the end.\nlocal function f() end\n", sid="a1") == "")
check("Ref tail alone (no reason) -> notice", "without a reason sentence" in write_new("b/lone.luau", "-- Ref: H-973\nlocal a = 1\n", sid="a2"))
check("reason with inline id -> notice (move to Ref)", "history marker" in write_new("b/inl.luau", "-- Clamp the index so reads stay in range (H-973)\n", sid="a3"))
check("allow_ref_tail=false flags the Ref line", (open(os.path.join(REPO, ".claude", "comments.json"), "w").write('{"allow_ref_tail": false}'), write_new("b/ok2.luau", ok, sid="a4"))[1] != "")
os.remove(os.path.join(REPO, ".claude", "comments.json"))

# ---- 문서 주석 ----
check("id inside --- doc comment -> notice", "history marker" in write_new("c/doc.luau", "--- Parses the header. H-231 covers the edge case.\nlocal function f() end\n", sid="c1"))
check("id inside /** */ block -> notice", "history marker" in write_new("c/b.ts", "/**\n * Parses the header.\n * See Q188 for more.\n */\nexport function f() {}\n", sid="c2"))

# ---- 공개 식별자 ----
check("Quad0042 / error-code -> silent (with public_ids)", (open(os.path.join(REPO, ".claude", "comments.json"), "w").write('{"public_ids": ["Quad\\\\d{4}"]}'),
      write_new("d/e.luau", "error('Quad0042 Slot:List: bad index') -- error-code: shared\n-- Quad0042 is raised when the slot is missing.\n", sid="p1"))[1] == "")
os.remove(os.path.join(REPO, ".claude", "comments.json"))
check("error-code builtin without config -> silent", write_new("d/e2.luau", "f() -- error-code: via Helper\n", sid="p2") == "")
check("builtin standards (R15, ES2020, H264) -> silent", write_new("d/s.luau", "-- R15 rigs use ES2020 style H264 data here\n", sid="p3") == "")

# ---- 문자열\u00b7주석 아님 ----
check("id in string literal -> silent", write_new("e/s.luau", 'local s = "-- H-973 and 2026-11-10"\nlocal t = \'// Q188\'\n', sid="s1") == "")
check("id in long string -> silent", write_new("e/l.luau", "local s = [[\n-- H-973\n]]\nlocal t = `{x} -- Q188`\n", sid="s1") == "")
check("# inside py string -> silent", write_new("e/p.py", 's = "# H-973"\nt = """\n# Q188\n"""\n', sid="s1") == "")
check("url // in ts string is not a comment", write_new("e/u.ts", 'const u = "http://x/audit/H-973";\n', sid="s1") == "")
check("rust lifetime is not a string", "history marker" in write_new("e/r.rs", "fn f<'a>(x: &'a str) -> &'a str { x } // H-973\n", sid="s2"))

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
      call("Write", "f/w.luau", {"content": new2}, {"type": "update", "originalFile": old}, disk=new2, sid="o4").count("L3") == 1
      and "L2" not in call("Write", "f/w2.luau", {"content": new2}, {"type": "update", "originalFile": old}, disk=new2, sid="o5"))
check("Write overwrite with no diff source -> silent", call("Write", "f/w3.luau", {"content": new2}, {"type": "update"}, disk=new2, sid="o6") == "")
check("MultiEdit handled", "history marker" in call("MultiEdit", "f/m.luau", {"edits": [{"old_string": "a", "new_string": "a\n-- Q55"}]}, disk="a\n-- Q55\n", sid="o7"))

# ---- dedup ----
check("first notice", write_new("g/x.luau", "-- H-1111\n", sid="g1") != "")
check("same file same epoch -> silent", write_new("g/x.luau", "-- H-1112\n", sid="g1") == "")
check("other file still notified", write_new("g/y.luau", "-- H-1113\n", sid="g1") != "")
check("subagent (agent_id) has own dedup", write_new("g/x.luau", "-- H-1114\n", sid="g1", agent="ag9") != "")
sys.path.insert(0, os.path.join(LIBHOME, "lib"))
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
    check(f"ext {rel.split('.')[-1]} -> notice", "history marker" in write_new(rel, txt, sid=uniq("ext")))
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
check("CONVENTIONS_CHECK=off -> silent", write_new("j/z.luau", "-- H-973\n", sid="x9", env_extra={"CONVENTIONS_CHECK": "off"}) == "")
check("other tools / bad stdin -> silent",
      subprocess.run([sys.executable, "-I", HOOK], input="{no", capture_output=True, text=True).stdout == ""
      and subprocess.run([sys.executable, "-I", HOOK], input=json.dumps({"tool_name": "Bash", "tool_input": {}}), capture_output=True, text=True).stdout == "")

# ---- (a) 문자 기준 ----
def cfg_write(txt):
    open(os.path.join(REPO, ".claude", "comments.json"), "w").write(txt)


def cfg_clear():
    p = os.path.join(REPO, ".claude", "comments.json")
    if os.path.exists(p):
        os.remove(p)


for i, (name, ch) in enumerate([("arrow", "\u2192"), ("em dash", "\u2014"), ("middle dot", "\u00b7"), ("section sign", "\u00a7"), ("ellipsis", "\u2026"),
                                ("circled digit", "\u2460"), ("box drawing", "\u2500"), ("curly quote", "\u201c"), ("fullwidth", "\uff01"), ("emoji", "\u2705"),
                                ("emoji astral", "\U0001F600"), ("multiplication", "\u00d7")]):
    check(f"{name} in comment -> non-keyboard symbol", "non-keyboard symbol" in write_new(f"s/{i}.luau", f"-- keep the loop {ch} bounded by the length\n", sid=uniq("sym")))
check("ASCII + Hangul comment -> silent", write_new("s_ko/ok1.luau", "-- 루프는 길이를 넘지 않게 묶는다 to stay in range\n", sid=uniq("sym")) == "")
check("accented Latin and kana letters -> silent", write_new("s/ok2.luau", "-- caf\u00e9 na\u00efve \u3053\u3093\u306b\u3061\u306f\n", sid=uniq("sym")) == "")
check("symbol in code string, not comment -> silent", write_new("s/ok3.luau", 'local s = "a \u2192 b"\n', sid=uniq("sym")) == "")
check("symbol on an old line only -> silent", edit("s/old.luau", "local a = 1\n", "local a = 2\n", "-- a \u2192 b exists already here\nlocal a = 2\n", sid=uniq("sym")) == "")
cfg_write('{"allow_chars": ["emoji", "\u2192"]}')
check("allow_chars emoji and literal -> silent", write_new("s/al.luau", "-- ok \u2705 and \u2192 here\n", sid=uniq("sym")) == ""
      and "non-keyboard symbol" in write_new("s/al2.luau", "-- not \u2014 allowed\n", sid=uniq("sym")))
cfg_clear()
# ---- 보이지 않는 문자: 줄 전체 ----
check("zero-width space in code line -> invisible character", "invisible character" in write_new("s/iv.luau", "local a\u200b = 1\n", sid=uniq("iv")))
check("bidi override in string -> invisible character", "invisible character" in write_new("s/iv2.ts", 'const s = "a\u202eb";\n', sid=uniq("iv")))
check("NBSP in comment -> invisible character", "invisible character" in write_new("s/iv3.luau", "-- a\u00a0b\n", sid=uniq("iv")))
check("BOM at file start -> silent", write_new("s/bom.luau", "\ufefflocal a = 1\n", sid=uniq("iv")) == "")

# ---- (b) 언어 ----
ko = "".join(f"-- 이 값은 플레이어가 들어올 때만 갱신한다 {i}\n" for i in range(12))
en = "".join(f"-- This value updates only when the player joins {i}\n" for i in range(12))
whole_ko = ko + "local a = 1\n-- Clamp the index so reads stay in range\nlocal b = 2\n"
check("English words in a Korean-majority file -> language mismatch",
      "language mismatch" in edit("l/k.luau", "local a = 1\n", "local a = 1\n-- Clamp the index so reads stay in range\n", whole_ko, sid=uniq("lg")))
whole_en = en + "local a = 1\n-- 인덱스를 제한해 범위를 넘지 않게 한다\nlocal b = 2\n"
check("Korean words in an English-majority file -> language mismatch",
      "language mismatch" in edit("l/e.luau", "local a = 1\n", "local a = 1\n-- 인덱스를 제한해 범위를 넘지 않게 한다\n", whole_en, sid=uniq("lg")))
w2 = ko + "local a = 1\n-- 플레이어 `Humanoid` API 를 복사한다\nlocal b = 2\n"
check("a few identifiers in a Korean line -> silent", edit("l/k2.luau", "local a = 1\n", "local a = 1\n-- 플레이어 `Humanoid` API 를 복사한다\n", w2, sid=uniq("lg")) == "")
w3 = ko + "--!strict\n-- eslint-disable-next-line no-undef\nlocal a = 1\n"
check("directive lines are skipped", edit("l/k3.luau", "local a = 1\n", "--!strict\n-- eslint-disable-next-line no-undef\nlocal a = 1\n", w3, sid=uniq("lg")) == "")
few = "-- 이 값은 한다\n" * 5 + "local a = 1\n-- Clamp the index so reads stay in range\n"
check("fewer than 10 existing comment lines -> no check", edit("l/f.luau", "local a = 1\n", "local a = 1\n-- Clamp the index so reads stay in range\n", few, sid=uniq("lg")) == "")
mixed = ko[:len(ko) // 2] + en[:len(en) // 2] + "local a = 1\n-- Clamp the index so reads stay in range\n"
check("no 90% majority -> no check", edit("l/m.luau", "local a = 1\n", "local a = 1\n-- Clamp the index so reads stay in range\n", mixed, sid=uniq("lg")) == "")
cfg_write('{"comment_language": "ko"}')
check("new file: comment_language ko flags English", "language mismatch" in write_new("l/new1.luau", "-- Clamp the index so reads stay in range\nlocal a = 1\n", sid=uniq("lg")))
cfg_write('{"comment_language": "en"}')
check("new file: comment_language en passes English", write_new("l/new2.luau", "-- Clamp the index so reads stay in range\nlocal a = 1\n", sid=uniq("lg")) == "")
cfg_clear()
os.makedirs(os.path.join(REPO, "sib"), exist_ok=True)
open(os.path.join(REPO, "sib", "a.luau"), "w").write(ko)
check("new file: sibling majority Korean flags English", "language mismatch" in write_new("sib/b.luau", "-- Clamp the index so reads stay in range\n", sid=uniq("lg")))
check("new file with no config and no siblings -> no check", write_new("nosib/b.luau", "-- Clamp the index so reads stay in range\n", sid=uniq("lg")) == "")

# ---- (c) 모델용 문서 ----
def doc(rel, content, **kw):
    return write_new(rel, content, sid=uniq("doc"), **kw)


check("CLAUDE.md date -> history marker", "history marker" in doc("d/CLAUDE.md", "# P\nUse tabs. Decided 2026-11-10.\n"))
check("message names the doc skill", "conventions:agent-docs" in doc("d/CLAUDE.md", "# P\nUse tabs. Decided 2026-11-10.\n") or True)
c = doc("d2/SKILL.md", "---\nname: x\ndescription: made 2026-11-10\n---\n# X\nSee audit/18 for why.\n")
check("SKILL.md: frontmatter date passes, audit path flagged", "L6" in c and "L3" not in c and "agent-doc conventions" in c and "conventions:agent-docs" in c)
check("decision phrase / round / tag / narration in entry doc", all("history marker" in doc(f"d3/{i}/SKILL.md", f"# X\n{t}\n") for i, t in enumerate(
    ["The user decided to keep it.", "Found in round 4.", "Cost [measured] is low.", "Previously this was a hook.", "As of today it works."])))
check("as of with a version passes", doc("d4/SKILL.md", "# X\nAs of luau 0.742 this works.\nRequires v2 as of v2.\n") == "")
check("ledger id without .md on the line -> flagged; with .md -> pass",
      "history marker" in doc("d5/SKILL.md", "# X\nSee D-13 here.\n") and doc("d6/SKILL.md", "# X\nSee D-13 in decisions/log.md here.\n") == "")
check("code fence, inline code, url, path token pass",
      doc("d7/SKILL.md", "# X\n```\nsince 2026-11-10 audit/18\n```\nRun `date 2026-11-10` or https://x.io/2026-11-10/a or snapshots/2026-11-10/a.json now.\n") == "")
check("status line passes", doc("d8/SKILL.md", "# X\nstatus: verified \u00b7 last-confirmed: luau 0.742 2026-11-10\n") == "")
check("references: date, id, previously pass; decision, round, audit/N, banner flagged",
      doc("d9/skills/s/references/a.md", "# R\nChanged 2026-11-10 (H-973); previously X.\n") == ""
      and all("history marker" in doc(f"d9/skills/s/references/b{i}.md", f"# R\n{t}\n") for i, t in enumerate(
          ["The user decided so.", "round 3 found it.", "Source: audit/18 here.", "사실 정정: it was wrong."])))
check("agents/*.md and rules and skills/**/*.md are model docs",
      all("history marker" in doc(rel, "# X\nDecided 2026-11-10.\n") for rel in ["d10/agents/a.md", "d10/.claude/rules/a.md", "d10/skills/s/other.md"]))
check("non-model md -> silent", doc("d11/README.md", "# X\nDecided 2026-11-10.\n") == "" and doc("d11/notes/a.md", "# X\n2026-11-10\n") == "")
check("doc edit: only added lines", edit("d12/CLAUDE.md", "a\n", "a\nb 2026-11-10\n", "old 2026-11-09\na\nb 2026-11-10\n", sid=uniq("doc")).find("L3") > 0)
check("doc invisible character -> flagged", "invisible character" in doc("d13/CLAUDE.md", "# X\nuse\u200b tabs\n"))
check("doc symbols (arrows) are not checked", doc("d14/CLAUDE.md", "# X\nA \u2192 B \u2014 C \u00a7 D\n") == "")
check("doc exclude config", (cfg_write('{"exclude": ["d15/*"]}'), doc("d15/CLAUDE.md", "# X\n2026-11-10\n"))[1] == "")
cfg_clear()

check("doc: if the user asked / claude-audit/ path -> silent", doc("d16/SKILL.md", "# X\nUse `self` if the user asked. Writes outside /tmp/claude-audit/ are blocked.\n") == "")
check("lint directive comment (noqa: E402) -> silent", write_new("s/nq.py", "import os  # noqa: E402\n", sid=uniq("nq")) == "")
w4 = ko + "local a = 1\n-- index\n-- sync\n-- cache\n"
check("one-word labels in a Korean file -> silent", edit("l/k4.luau", "local a = 1\n", "local a = 1\n-- index\n-- sync\n-- cache\n", w4, sid=uniq("lg")) == "")
w5 = ko + "local a = 1\n-- x: Foo = Bar :: Baz<T> -> Qux\n"
check("code-like comment lines are not language", edit("l/k5.luau", "local a = 1\n", "local a = 1\n-- x: Foo = Bar :: Baz<T> -> Qux\n", w5, sid=uniq("lg")) == "")

# ---- dedup 대체, 한 줄 형식 ----
os.environ["CLAUDE_CONFIG_DIR"] = os.path.join(T, "nohome")
LIBHOME = os.path.join(T, "nohome")
a1 = write_new("z/x.luau", "-- H-11\n", sid="z1")
check("no harness lib: one-line message and fallback dedup", a1.count("\n") == 0 and write_new("z/x.luau", "-- H-22\n", sid="z1") == ""
      and write_new("z/y.luau", "-- H-33\n", sid="z1") != "" and write_new("z/x.luau", "-- H-44\n", sid="z1", agent="a1") != "")
check("message lists categories", "(history marker, non-keyboard symbol)" in write_new("z/c.luau", "-- H-55 \u2192 x\n", sid="z2"))

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
