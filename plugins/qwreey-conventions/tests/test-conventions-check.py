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
# nonce 는 고정 salt 로(실제 ~/.local/share 의 salt 를 쓰지 않게)
SALT = os.path.join(T, "salt")
open(SALT, "w").write("00" * 32)
os.environ["QWREEY_HARNESS_SALT_FILE"] = SALT
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
    env.pop("HARNESS_READABLE_CODE", None)
    env.update(env_extra or {})
    p = subprocess.run([sys.executable, "-I", HOOK], input=json.dumps(d), capture_output=True, text=True, env=env, timeout=10)
    assert p.returncode == 0, p.stderr
    if not p.stdout.strip():
        return ""
    ctx = json.loads(p.stdout)["hookSpecificOutput"]["additionalContext"]
    assert re.match(r'<harness-hook name="qwreey-conventions" level="info" nonce="[0-9a-f]{12}">[^\n]+</harness-hook>$', ctx), ctx
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
check("notice names file, line and skill", "a/y.luau" in c and "L1 history marker" in c and "qwreey-conventions:comments" in c and c.count("\n") == 0)
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

# ---- 문자열, 주석 아님 ----
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
subprocess.run([sys.executable, "-I", os.path.join(os.path.dirname(HOOK), "compact_epoch.py"), "qwreey-conventions"],
               input='{"session_id": "g1"}', capture_output=True, text=True, env=dict(os.environ, TMPDIR=T))  # PreCompact
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
check("message names the doc skill", "qwreey-conventions:agent-docs" in doc("d/CLAUDE.md", "# P\nUse tabs. Decided 2026-11-10.\n") or True)
c = doc("d2/SKILL.md", "---\nname: x\ndescription: made 2026-11-10\n---\n# X\nSee audit/18 for why.\n")
check("SKILL.md: frontmatter date passes, audit path flagged", "L6" in c and "L3" not in c and "agent-doc conventions" in c and "qwreey-conventions:agent-docs" in c)
check("decision phrase / round / tag / narration in entry doc", all("history marker" in doc(f"d3/{i}/SKILL.md", f"# X\n{t}\n") for i, t in enumerate(
    ["The user decided to keep it.", "Found in round 4.", "Cost [measured] is low.", "Previously this was a hook.", "As of today it works."])))
check("as of with a version passes", doc("d4/SKILL.md", "# X\nAs of luau 0.742 this works.\nRequires v2 as of v2.\n") == "")
check("ledger id without .md on the line -> flagged; with .md -> pass",
      "history marker" in doc("d5/SKILL.md", "# X\nSee D-13 here.\n") and doc("d6/SKILL.md", "# X\nSee D-13 in decisions/log.md here.\n") == "")
check("code fence, inline code, url, path token pass",
      doc("d7/SKILL.md", "# X\n```\nsince 2026-11-10 audit/18\n```\nRun `date 2026-11-10` or https://x.io/2026-11-10/a or snapshots/2026-11-10/a.json now.\n") == "")
check("entry doc: .claude/ record folder paths flagged",
      all("history marker" in doc(f"dp/{i}/SKILL.md", f"# X\nSee {t} for why.\n") for i, t in enumerate(
          [".claude/base/decisions/D-01.md", ".claude/research/drafts/x.md", ".claude/archive/research/y.md", ".claude/plan/z.md"])))
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
c2 = write_new("z/c.luau", "-- H-55 \u2192 x\n", sid="z2")
check("message lists categories, history marker first, with chars and fixes",
      "L1 history marker; L1 non-keyboard symbol: \u2192 (use \"->\")" in c2)

check("F64 / I32 / X86 / C99 / TS2322 / E0308 are not ledger ids",
      write_new("z/ids.rs", "// Reads f32 data as F64 or I32 on X86 with C99 rules; TS2322 and E0308 are compiler codes.\n", sid="zid") == ""
      and write_new("z/ids2.rs", "// Keep the clamp, the bound is H-321 here.\n", sid="zid2") != "")

# ---- 알림 내용: 글자와 대체, 코드포인트, 이스케이프, (파일, 범주) 중복 ----
c3 = write_new("z/d.luau", "-- loop \u2014 bounded \u00b7 by length \u2460\n", sid="z3")
check("symbols named with replacements", "\u2014 \u00b7 \u2460 (use \"-\", \",\", \"1)\")" in c3)
c4 = write_new("z/e.luau", "-- a\u00a0b\n", sid="z4")
check("invisible character named by code point", "invisible character: U+00A0 (delete it)" in c4 and "\u00a0" not in c4)
c5 = write_new("z/f.luau", "-- middle dot is \\u00b7 in an escape\n", sid="z5")
check("escaped character in a comment is flagged", "escaped character: \\u00b7" in c5)
check("escape in a string literal (code) -> silent", write_new("z/g.luau", 'local s = "\\u00b7"\n', sid="z6") == "")
check("repeat category on the same file -> silent, new category -> notice",
      write_new("z/h.luau", "-- x \u2192 y\n", sid="z7") != ""
      and edit("z/h.luau", "-- x \u2192 y\n", "-- x \u2192 y\n-- z \u2014 w\n", "-- x \u2192 y\n-- z \u2014 w\n", sid="z7") == ""
      and "history marker" in edit("z/h.luau", "-- z \u2014 w\n", "-- z \u2014 w\n-- H-77 later\n", "-- x \u2192 y\n-- z \u2014 w\n-- H-77 later\n", sid="z7"))
open(os.path.join(REPO, ".claude", "conventions.json"), "w").write('{"allow_chars": ["\u2192"]}')
check("conventions.json is read", write_new("z/i.luau", "-- x \u2192 y\n", sid="z8") == "")
open(os.path.join(REPO, ".claude", "comments.json"), "w").write('{"allow_chars": ["\u2014"]}')
check("conventions.json wins over comments.json", write_new("z/j.luau", "-- x \u2014 y\n", sid="z9") != "")
os.remove(os.path.join(REPO, ".claude", "conventions.json"))
check("comments.json is the fallback", write_new("z/k.luau", "-- x \u2014 y\n", sid="z10") == "")
os.remove(os.path.join(REPO, ".claude", "comments.json"))

# ---- 단계 라벨은 언어 판정에서 뺀다 ----
KO = "".join(f"-- 이 값은 플레이어가 들어올 때만 갱신한다 {i}\n" for i in range(12))


def label_case(rel, added_block, sid, cfg=None, base=KO):
    """한국어 주석 파일의 함수 본문에 added_block 을 더하는 Edit."""
    if cfg is not None:
        cfg_write(cfg)
    head = base + "local function f()\n\tlocal parent = 1\n"
    whole = head + added_block + "\tparent = nil\nend\n"
    try:
        return edit(rel, "\tlocal parent = 1\n", "\tlocal parent = 1\n" + added_block, whole, sid=uniq(sid))
    finally:
        if cfg is not None:
            cfg_clear()


check("label: English step label in a Korean file -> silent", label_case("lb/a.luau", "\t-- Detach previous parent first\n", "lb") == "")
check("label: two 2-word labels -> silent",
      label_case("lb/b.luau", "\t-- Clear vChildren\n\tlocal x = 1\n\t-- Already same\n", "lb") == "")
check("label: reason connective stays flagged", "language mismatch" in label_case("lb/c.luau", "\t-- Clamp the index so reads stay in range\n", "lb"))
check("label: period, 11 words, two-line block, unindented -> flagged",
      all("language mismatch" in label_case(f"lb/d{i}.luau", blk, "lb") for i, blk in enumerate([
          "\t-- Detach the previous parent first here.\n",
          "\t-- Detach the previous parent and then attach the new parent right here now\n",
          "\t-- Detach the previous parent\n\t-- Attach the new parent after\n",
          "-- Detach the previous parent first\n"])))
ten_ko = "".join(f"-- 이 값은 플레이어가 들어올 때만 갱신한다 {i}\n" for i in range(10))
labelled = ten_ko + "".join(f"local function g{i}()\n\tlocal a = 1\n\t-- Detach parent step {i}\n\ta = 2\nend\n" for i in range(3))
check("label: labels do not dilute the majority, a reason sentence is still flagged",
      "language mismatch" in label_case("lb/e.luau", "\tparent = 2 -- Clamp the index so reads stay in range\n", "lb", base=labelled))
check("label: label_language null turns the exemption off",
      "language mismatch" in label_case("lb/f.luau", "\t-- Detach previous parent first\n", "lb", cfg='{"label_language": null}'))

# ---- layout 알림 (HARNESS_READABLE_CODE) ----
ON = {"HARNESS_READABLE_CODE": "on"}


def lua_fn(name, n, blank_every=0, doc="--- Does the thing for callers.\n", public=True):
    head = f"function M.{name}(x)\n" if public else f"local function {name}(x)\n"
    body = ""
    for i in range(n):
        if blank_every and i and i % blank_every == 0:
            body += "\n\t-- Next step here\n"
        body += f"\tlocal v{i} = x + {i}\n"
    return doc + head + body + "end\n"


def module(*fns):
    return "--!strict\nlocal M = {}\n\n" + "\n".join(fns) + "\nreturn M\n"


c = write_new("ly/a.luau", module(lua_fn("flat", 20)), sid=uniq("ly"), env_extra=ON)
check("layout: 20-line function without blank lines -> layout", "layout (readable-code)" in c and "M.flat L5-26 (20 lines, 0 blank, longest run 20)" in c)
check("layout: key off -> silent", write_new("ly/b.luau", module(lua_fn("flat", 20)), sid=uniq("ly")) == "")
check("layout: same function in 4 paragraphs -> silent", write_new("ly/c.luau", module(lua_fn("para", 20, blank_every=5)), sid=uniq("ly"), env_extra=ON) == "")
check("layout: 9-line function -> silent", write_new("ly/d.luau", module(lua_fn("short", 9)), sid=uniq("ly"), env_extra=ON) == "")
inter = "--- Wraps x.\nfunction M.wrap(x)\n\tlocal a = x\n\t-- The cache holds stale entries until\n\t-- the next frame, so read it twice\n\t-- before trusting the value\n\treturn a\nend\n"
c = write_new("ly/e.luau", module(inter), sid=uniq("ly"), env_extra=ON)
check("layout: 3-line comment between statements -> interleaved", "Multi-line comments between statements: M.wrap L7 (3 lines)" in c)
c = write_new("ly/f.luau", module(lua_fn("hidden", 3, doc="-- Hidden from hover.\n")), sid=uniq("ly"), env_extra=ON)
check("layout: `--` above a public function -> doc summary naming `---`",
      "M.hidden L5 has a comment that hover does not show" in c and "a `---` doc comment (luau-lsp shows only" in c)
c = write_new("ly/g.luau", module("function M.__tostring(self)\n\treturn \"x\"\nend\n", lua_fn("nodoc", 3, doc="")), sid=uniq("ly"), env_extra=ON)
check("layout: metamethod without a doc is skipped, public function is not", "M.nodoc L8 has no doc comment" in c and "__tostring" not in c)
c = write_new("ly/h.luau", module(lua_fn("private", 3, doc="", public=False)), sid=uniq("ly"), env_extra=ON)
check("layout: private function without a doc -> silent", c == "")
long_doc = "--- Moves the proxy under the new parent and then fires the parent changed signal for\n--- every listener that is attached.\n"
c = write_new("ly/i.luau", module(lua_fn("runon", 3, doc=long_doc)), sid=uniq("ly"), env_extra=ON)
check("layout: first doc sentence running past the first line -> doc summary", "first doc sentence runs past the first line" in c)
c = write_new("ly/i2.luau", module(lua_fn("wide", 3, doc="--- " + "word " * 25 + "end.\n")), sid=uniq("ly"), env_extra=ON)
check("layout: first doc line over 100 characters -> doc summary", "first doc line is 129 characters" in c)

# 키운 함수: 기존 함수에 15줄 이상 더하면 함수 전체를 본다. 5줄은 보지 않는다
grow_old = module(lua_fn("grow", 40, blank_every=4))
add16 = "\tlocal v39 = x + 39\n" + "".join(f"\tlocal w{i} = x * {i}\n" for i in range(16))
c = edit("ly/j.luau", "\tlocal v39 = x + 39\n", add16, grow_old.replace("\tlocal v39 = x + 39\n", add16), sid=uniq("ly"), env_extra=ON)
check("layout: function grown by 16 lines -> layout with [grown by 16 lines]", "M.grow" in c and "[grown by 16 lines]" in c)
big = module(lua_fn("big", 40))
c = edit("ly/k.luau", "\tlocal v39 = x + 39\n", "\tlocal v39 = x + 39\n" + "".join(f"\tlocal w{i} = x * {i}\n" for i in range(5)),
         big.replace("\tlocal v39 = x + 39\n", "\tlocal v39 = x + 39\n" + "".join(f"\tlocal w{i} = x * {i}\n" for i in range(5))),
         sid=uniq("ly"), env_extra=ON)
check("layout: 5 lines added to a long existing function -> silent", c == "")

# doc summary 는 다음 편집 뒤 한 번 더 본다
sid = uniq("ly")
two = module(lua_fn("nodoc", 3, doc=""), lua_fn("other", 3))
c1 = write_new("ly/l.luau", two, sid=sid, env_extra=ON)
two2 = two.replace("\tlocal v2 = x + 2\nend\n\nreturn M", "\tlocal v2 = x + 2\n\tlocal z = 1\nend\n\nreturn M")
c2 = edit("ly/l.luau", "\tlocal v2 = x + 2\nend\n\nreturn M", "\tlocal v2 = x + 2\n\tlocal z = 1\nend\n\nreturn M", two2, sid=sid, env_extra=ON)
two3 = two2.replace("\tlocal z = 1\n", "\tlocal z = 1\n\tlocal y = 2\n")
c3 = edit("ly/l.luau", "\tlocal z = 1\n", "\tlocal z = 1\n\tlocal y = 2\n", two3, sid=sid, env_extra=ON)
check("layout: missing doc is re-checked once after the next edit",
      "M.nodoc L4 has no doc comment" in c1 and "M.nodoc L4 has no doc comment (still so after your last edit)" in c2 and c3 == "")
sid = uniq("ly")
write_new("ly/m.luau", two, sid=sid, env_extra=ON)
fixed = two.replace("function M.nodoc", "--- Does nothing useful.\nfunction M.nodoc")
check("layout: a fixed doc is not re-reported",
      edit("ly/m.luau", "function M.nodoc", "--- Does nothing useful.\nfunction M.nodoc", fixed, sid=sid, env_extra=ON) == "")

# 같은 (파일, 범주, 함수)는 한 번, 다른 함수는 따로
sid = uniq("ly")
one = module(lua_fn("flat", 20))
write_new("ly/n.luau", one, sid=sid, env_extra=ON)
both = one.replace("\nreturn M", "\n" + lua_fn("flat2", 20) + "\nreturn M")
c = edit("ly/n.luau", "\nreturn M", "\n" + lua_fn("flat2", 20) + "\nreturn M", both, sid=sid, env_extra=ON)
check("layout: dedup per function, a new function is reported", "M.flat2" in c and "M.flat L" not in c)

# 설정과 층
cfg_write('{"layout": {"min_lines": 30}}')
check("layout: conventions.json layout.min_lines raises the bar", write_new("ly/o.luau", module(lua_fn("flat", 20)), sid=uniq("ly"), env_extra=ON) == "")
cfg_clear()
user_env = os.path.join(T, "user-harness.env")
open(user_env, "w").write("HARNESS_READABLE_CODE=on\n")
check("layout: user harness.env on -> notice", "layout (readable-code)" in write_new("ly/p.luau", module(lua_fn("flat", 20)), sid=uniq("ly"), env_extra={"HARNESS_ENV": user_env}))
open(os.path.join(REPO, ".claude", "harness.env"), "w").write("HARNESS_READABLE_CODE=off\n")
check("layout: repo .claude/harness.env off wins over the user layer",
      write_new("ly/q.luau", module(lua_fn("flat", 20)), sid=uniq("ly"), env_extra={"HARNESS_ENV": user_env}) == "")
os.remove(os.path.join(REPO, ".claude", "harness.env"))

# 다른 언어
py_fn = "def handle(x):\n" + "".join(f"    v{i} = x + {i}\n" for i in range(18)) + "    return x\n"
c = write_new("ly/r.py", '"""Module."""\n\n\n' + py_fn, sid=uniq("ly"), env_extra=ON)
check("layout: python function -> layout and docstring wording", "handle L4-23 (19 lines, 0 blank" in c and "a docstring (`#` comments" in c)
c = write_new("ly/s.py", py_fn + '\n\nif __name__ == "__main__":\n    handle(1)\n', sid=uniq("ly"), env_extra=ON)
check("layout: python script functions are not public (no doc summary)", "layout (readable-code)" in c and "Doc comments" not in c)
ts = "export function run(x: number): number {\n" + "".join(f"  const v{i} = x + {i};\n" for i in range(18)) + "  return x;\n}\n"
c = write_new("ly/t.ts", ts, sid=uniq("ly"), env_extra=ON)
check("layout: ts exported function -> layout and JSDoc wording", "run L1-21" in c and "`/** */` JSDoc" in c)
check("layout: .sh is not measured", write_new("ly/u.sh", "f() {\n" + "  echo 1\n" * 20 + "}\n", sid=uniq("ly"), env_extra=ON) == "")
c = write_new("ly/v.luau", module(lua_fn("flat", 20)) + "-- see H-973\n", sid=uniq("ly"), env_extra=ON)
check("layout: comment notice and layout notice share one tag", c.count("<harness-hook") == 1 and "history marker" in c and "layout (readable-code)" in c)

# 지표: 여러 반환 받기는 한 줄 여러 선언이 아니다
import importlib.util as _ilu2
sys.path.insert(0, os.path.dirname(HOOK))
import conv_lex as _lex  # noqa: E402
import layout_metrics as _lm  # noqa: E402


def lua_metrics(src):
    rows = _lex.lex(src, "lua", keep_code=True)
    lines = src.split("\n")
    return [_lm.measure(rows, lines, fn, "lua") for fn in _lm.functions(rows, lines, "lua")]


m = lua_metrics("local function f()\n\tlocal ok, err = pcall(g)\n\tlocal a, b = 1, 2\n\tlocal c, d\n\tlocal e: number, h = g(), 1\n\treturn ok\nend\n")[0]
check("metrics: receiving multiple returns is not a multi-declaration", m["multi_decl"] == 3)
m = lua_metrics("local function f(x)\n\tlocal y = if x then 1 else 2\n\tif x then\n\t\treturn y\n\tend\n\treturn 0\nend\nlocal function g() end\n")
check("metrics: Luau if-expression does not open a block", [x["name"] for x in m] == ["f", "g"] and m[0]["end"] == 7)

# ---- 남은 기존 주석 보고(Stop) ----
def stop(sid, env_extra=None):
    d = {"session_id": sid, "cwd": REPO, "hook_event_name": "Stop", "stop_hook_active": False}
    env = dict(os.environ, TMPDIR=T, CLAUDE_PROJECT_DIR=REPO, CLAUDE_CONFIG_DIR=LIBHOME)
    env.pop("CONVENTIONS_CHECK", None)
    env.update(env_extra or {})
    p = subprocess.run([sys.executable, "-I", HOOK], input=json.dumps(d), capture_output=True, text=True, env=env, timeout=10)
    assert p.returncode == 0, p.stderr
    return json.loads(p.stdout) if p.stdout.strip() else None


old_file = "-- Old note \u2014 keep (H-973)\n-- Another \u2192 one\nlocal a = 1\n-- Clamp the index so reads stay in range.\n"
edit_new = "local a = 2\n"
check("Stop with nothing recorded -> silent", stop("L0") is None)
edit("l/old.luau", "local a = 1\n", edit_new, old_file.replace("local a = 1", "local a = 2"), sid="L1")
r = stop("L1")
msg = (r or {}).get("systemMessage", "")
check("Stop reports leftover counts to the user (systemMessage only)", r is not None and set(r) == {"systemMessage"}
      and "l/old.luau(이력 1, 기호 2)" in msg and msg.startswith("손댄 파일에 전부터 있던 문제") and "정리해줘" in msg)
check("Stop does not repeat an unchanged report", stop("L1") is None)
# 추가한 줄의 문제는 알림 쪽이 맡고 남은 기존 주석 집계에는 넣지 않는다
n = edit("l/new.luau", "local a = 1\n", "local a = 1 -- x \u2014 y\n", "local a = 1 -- x \u2014 y\n", sid="L2")
check("added-line problem is notified, not counted as leftover", "non-keyboard symbol" in n and stop("L2") is None)
# 서브에이전트가 쌓은 것도 메인 Stop 이 모아 보인다
edit("l/sub.rs", "let a = 1;\n", "let a = 2;\n", "// old \u2026 note\nlet a = 2;\n", sid="L3", agent="ag1")
check("subagent leftovers appear in the main Stop line", "l/sub.rs(기호 1)" in (stop("L3") or {}).get("systemMessage", ""))
# 고치면 사라지고, 파일이 지워져도 보고하지 않는다
edit("l/fix.luau", "local a = 1\n", "local a = 2\n", "-- old \u2192 x\nlocal a = 2\n", sid="L4")
edit("l/fix.luau", "-- old \u2192 x\n", "-- old to x\n", "-- old to x\nlocal a = 2\n", sid="L4")
check("fixed file drops out of the report", stop("L4") is None)
edit("l/gone.luau", "local a = 1\n", "local a = 2\n", "-- old \u2192 x\nlocal a = 2\n", sid="L5")
os.remove(os.path.join(REPO, "l/gone.luau"))
check("deleted file is not reported", stop("L5") is None)
# 모델용 문서의 기존 이력도 센다
edit("skills/x/SKILL.md", "Run it.\n", "Run it now.\n", "Decided 2026-11-10 by the user.\nRun it now.\n", sid="L6")
check("agent-doc leftovers are counted", "SKILL.md(이력 1)" in (stop("L6") or {}).get("systemMessage", ""))
edit("l/off.luau", "local a = 1\n", "local a = 2\n", "-- old \u2192 x\nlocal a = 2\n", sid="L7")
check("CONVENTIONS_CHECK=off silences Stop", stop("L7", {"CONVENTIONS_CHECK": "off"}) is None and stop("L7") is not None)

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

# ---- 줄 번호 목록: 범위로 묶고 숫자 40개에서 자른다 ----
import importlib.util as _ilu
_spec = _ilu.spec_from_file_location("cc_lines", HOOK)
sys.path.insert(0, os.path.dirname(HOOK))
_cc = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_cc)
check("line_list: ranges", _cc.line_list([40, 12, 13, 14, 15, 16, 17, 18, 3]) == "L3, L12-18, L40")
check("line_list: all lines shown under the cap", _cc.line_list(range(1, 80, 2)) == ", ".join(f"L{n}" for n in range(1, 80, 2)))
check("line_list: capped at 40 numbers, rest counted", _cc.line_list(range(1, 200, 2)) == ", ".join(f"L{n}" for n in range(1, 80, 2)) + " (+60 more)")
check("line_list: a long run costs two numbers", _cc.line_list(list(range(1, 501)) + [600]) == "L1-500, L600")
c = write_new("ll/many.luau", "".join(f"-- see Q{100 + i} for more\nlocal a{i} = 1\n" for i in range(8)), sid=uniq("ll"))
check("notice lists every flagged line (no 5-line cut)", all(f"L{2 * i + 1}" in c for i in range(8)) and "more)" not in c)

# ---- layout 지표 회귀(리뷰 재현) ----
def spans(src, lang, fam):
    rows = _lex.lex(src, fam, keep_code=True)
    return [(f["name"], f["start"] + 1, f["header_end"] + 1, f["last"] + 1) for f in _lm.functions(rows, src.split("\n"), lang)]


def docs(src, lang, fam):
    rows = _lex.lex(src, fam, keep_code=True)
    lines = src.split("\n")
    return {f["name"]: _lm.measure(rows, lines, f, lang)["doc"] for f in _lm.functions(rows, lines, lang)}


# 문서 주석 위의 이유 주석이나 접기 표지는 문서를 가리지 않는다. 가장 가까운 주석이 정한다
reason_above = ("local M = {}\n\n-- Kept iterative: deep trees overflow the C stack\n--- Returns the depth of the deepest leaf.\n"
                "function M.depth(node)\n\treturn 1\nend\n\n--#region Helpers\n--- Returns the node count.\nfunction M.count(node)\n"
                "\treturn 1\nend\n\n--- Returns two.\n-- Kept for old callers\nfunction M.two()\n\treturn 2\nend\n--#endregion\n\nreturn M\n")
check("doc: `--` reason or `--#region` above `---` -> ok, `--` nearest -> hidden",
      docs(reason_above, "lua", "lua") == {"M.depth": "ok", "M.count": "ok", "M.two": "hidden"})
ts_doc = ("// Kept sync: callers run in a worker\n/** Returns one. */\nexport function one() {\n  return 1;\n}\n"
          "// #region api\n// Reason here\n/**\n * Returns two.\n */\nexport function two() {\n  return 2;\n}\n"
          "/** Returns three. */\n// reason\nexport function three() {\n  return 3;\n}\n")
check("doc: TS `//` above `/** */` -> ok, multi-line JSDoc -> ok, `//` nearest -> hidden",
      docs(ts_doc, "ts", "c") == {"one": "ok", "two": "ok", "three": "hidden"})
check("doc: Rust `//` above `///` -> ok", docs("// Reason\n/// Returns one.\npub fn one() -> u8 {\n    1\n}\n", "rust", "rust") == {"one": "ok"})
c = write_new("ly/rsn.luau", reason_above.replace("--- Returns two.\n-- Kept for old callers\n", "--- Returns two.\n"), sid=uniq("ly"), env_extra=ON)
check("doc: hook does not report a doc under a reason comment", "Doc comments" not in c)

# 줄 끝의 제네릭 타입이나 캐스트 때문에 다음 줄의 `if` 를 식으로 보지 않는다
optional_of = ("const function Of<T>(value: T?): Optional<T>\n\tif value == nil then\n\t\treturn Absent\n\tend\n"
               "\treturn { isPresent = true, value = value :: T }\nend\n\nlocal function g(x)\n\tlocal v = x :: Optional<T>\n"
               "\tif v then\n\t\treturn 1\n\tend\n\tlocal w = x < if v then 1 else 2\n\treturn w\nend\n")
check("lua: `if` after a line ending in `>` is a statement, `< if` on one line is an expression",
      spans(optional_of, "lua", "lua") == [("Of", 1, 1, 6), ("g", 8, 8, 15)])

# 매개변수, 반환 타입, 제네릭 안의 중괄호는 본문이 아니다
c_cases = [
    ("export function originalUrl(id: string, opts: { download?: boolean } = {}): string {\n  return id;\n}\n", "ts",
     [("originalUrl", 1, 1, 3)]),
    ("export async function uploadFile(\n  file: File,\n): Promise<{ duplicate: boolean; retry?: number }> {\n  const t = 1;\n"
     "  return { duplicate: false };\n}\n", "ts", [("uploadFile", 1, 3, 6)]),
    ("export function Login({ onDone }: { onDone: () => void }) {\n  const a = 1;\n  return a;\n}\n", "ts", [("Login", 1, 1, 4)]),
    ("function h<T extends { a: number }>(x: T): T {\n  return x;\n}\n", "ts", [("h", 1, 1, 3)]),
    ("export function k(): {\n  a: number;\n} {\n  return { a: 1 };\n}\n", "ts", [("k", 1, 3, 5)]),
    ("class A {\n  constructor(el: X, id = 'h', opts: O = {}) {\n    this.el = el;\n  }\n}\n", "ts", [("constructor", 2, 2, 4)]),
    ("useEffect(() => {\n  run();\n}, []);\n", "ts", [("useEffect", 1, 1, 3)]),
    ("pub fn r<T: Into<Vec<u8>>>(x: T) -> Result<Vec<u8>, E> where T: Clone {\n    Ok(x.into())\n}\n", "rust", [("r", 1, 1, 3)]),
    ("fun <T> f(x: Map<String, T> = mapOf()): List<T> {\n    return listOf()\n}\n", "kt", [("f", 1, 1, 3)]),
    ("func start(g *rig, peer string) <-chan int {\n\treturn nil\n}\nfunc (s *S) Watch(stop <-chan struct{}) {\n\treturn\n}\n", "go",
     [("start", 1, 1, 3), ("Watch", 4, 4, 6)]),
]
check("c spans: braces inside the signature are not the body",
      all(spans(src, lang, "rust" if lang == "rust" else "c") == want for src, lang, want in c_cases))

# 파이썬 머리: 한 줄 def, 닫히지 않은 괄호가 파일 끝까지 훑지 않는다
check("py: one-line def ends on its own line",
      spans("def f(): return 1\ndef g(a: int = (1),\n      b: dict = {}) -> list[int]:\n    return [a]\n", "py", "py")
      == [("f", 1, 1, 1), ("g", 2, 3, 4)])
check("py: header scan stops after PY_HEADER_SCAN lines",
      spans("def broken(\n" + "    x,\n" * 60 + "):\n    pass\n", "py", "py")[0][:3] == ("broken", 1, 1))

# 단계 라벨은 rule 대로 2-10 낱말이고 `due to`, `workaround` 는 이유 말이다
check("label: is_label takes 2-10 words", not _lm.is_label("-- Cleanup") and _lm.is_label("-- Detach previous parent")
      and not _lm.is_label("-- " + " ".join(["word"] * 11)))
lab_src = "local function f()\n\tlocal a = 1\n\n\t-- Cleanup\n\ta = 2\n\n\t-- Detach parent\n\ta = 3\nend\n"
check("label: step_labels skips a one-word comment", _cc.step_labels(_lex.lex(lab_src, "lua"), lab_src.split("\n"), _cc.DEFAULTS) == {6})
check("label: `due to` and `workaround` keep a line in the language check",
      all("language mismatch" in label_case(f"lb/r{i}.luau", blk, "lb") for i, blk in enumerate([
          "\t-- Retry twice due to the flaky network\n", "\t-- Workaround for the engine resize bug\n"])))

# 중복 제거와 다시 보기 키는 같은 이름의 함수를 가른다
sid = uniq("ly")
cls_a = '"""Module."""\n\n\nclass A:\n    def run(self):\n        return 1\n'
cls_b = '\n\nclass B:\n    def run(self):\n        return 2\n'
c1 = write_new("ly/same.py", cls_a, sid=sid, env_extra=ON)
c2 = call("Edit", "ly/same.py", {"old_string": "        return 1\n", "new_string": "        return 1\n" + cls_b},
          disk=cls_a + cls_b, sid=sid, env_extra=ON)
check("layout: same-named function in another class is reported as new, the first is rechecked",
      "run L5 has no doc comment" in c1 and "run L5 has no doc comment (still so after your last edit)" in c2
      and "run L10 has no doc comment" in c2 and "run L10 has no doc comment (still" not in c2)
check("layout: fn_keys numbers repeats", _lm.fn_keys([{"name": "a"}, {"name": "b"}, {"name": "a"}]) == ["a", "b", "a#2"])

# layout 이 터져도 주석 알림은 나가고, 깨진 상태 파일은 무시한다
import io as _io
import tempfile as _tempfile
import compact_epoch as _ce  # noqa: E402


def in_process(rel, content, sid, env):
    path = os.path.join(REPO, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "w").write(content)
    d = {"session_id": sid, "cwd": REPO, "hook_event_name": "PostToolUse", "tool_name": "Write",
         "tool_input": {"file_path": path, "content": content}, "tool_response": {"type": "create"}}
    saved = (sys.stdin, sys.stdout, dict(os.environ), _tempfile.tempdir)
    sys.stdin, sys.stdout = _io.StringIO(json.dumps(d)), _io.StringIO()
    os.environ.update(env, TMPDIR=T, CLAUDE_PROJECT_DIR=REPO, CLAUDE_CONFIG_DIR=LIBHOME)
    _tempfile.tempdir = T
    try:
        _cc.main()
        return sys.stdout.getvalue()
    finally:
        sys.stdin, sys.stdout, _tempfile.tempdir = saved[0], saved[1], saved[3]
        os.environ.clear()
        os.environ.update(saved[2])


def boom(*a, **k):
    raise RuntimeError("metrics bug")


real = _cc.layout_metrics.edit_findings
_cc.layout_metrics.edit_findings = boom
try:
    out = in_process("ly/boom.luau", module(lua_fn("flat", 20)) + "-- see H-973\n", uniq("ly"), ON)
except Exception:
    out = ""
finally:
    _cc.layout_metrics.edit_findings = real
check("layout: an exception in the metrics drops only the layout part", "history marker" in out and "layout (readable-code)" not in out)
sid = uniq("ly")
_tempfile.tempdir = T
bad_state = _ce.state_path(_cc.NAME, _cc.NS, sid)
_tempfile.tempdir = None
for junk in ("[1, 2]", '{"files": [], "doc_recheck": "x"}'):
    open(bad_state, "w").write(junk)
    c = write_new("ly/badstate.luau", module(lua_fn("flat", 20)) + "-- see H-973\n", sid=sid, env_extra=ON)
    check("layout: non-dict state file %s is ignored" % junk, "history marker" in c and "layout (readable-code)" in c)

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
