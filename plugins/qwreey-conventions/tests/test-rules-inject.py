#!/usr/bin/env python3
"""rules_inject 훅 회귀. 실행: python3 -I test-rules-inject.py  (exit 0 = 통과)

glob 변환(이 플러그인 rule 4개의 패턴 전부), 주입 dedup(에이전트·compact 회차·세션별), PreToolUse 출력 없음과 편집 뒤 대조 문장, 건너뛰는 경로, 병렬 호출 이중 주입 없음,
끄기(환경 변수, harness.env, rules_exclude)를 본다. 상태는 TMPDIR 로 격리한다.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOKS = os.path.join(ROOT, "hooks")
HOOK = os.path.join(HOOKS, "rules_inject.py")
T = tempfile.mkdtemp(prefix="rules-inject-")
CFG = os.path.join(T, "cfg")
PROJ = os.path.join(T, "proj")
X = PROJ + "/x"
os.makedirs(CFG)
os.makedirs(os.path.join(PROJ, ".claude"))
sys.path.insert(0, HOOKS)
import rules_inject as ri  # noqa: E402

_n = [0]


def run(event, tool, path, session="s1", agent=None, env=None, cwd=PROJ):
    payload = {"hook_event_name": event, "tool_name": tool, "tool_input": {"file_path": path}, "session_id": session, "cwd": cwd}
    if agent:
        payload["agent_id"] = agent
    e = dict(os.environ, TMPDIR=T, CLAUDE_CONFIG_DIR=CFG, CLAUDE_PROJECT_DIR=PROJ)
    e.pop("HARNESS_CONVENTIONS_RULES", None)
    e.update(env or {})
    r = subprocess.run([sys.executable, "-I", HOOK], input=json.dumps(payload), capture_output=True, text=True, env=e)
    return json.loads(r.stdout)["hookSpecificOutput"] if r.stdout.strip() else None


def ctx(out):
    return (out or {}).get("additionalContext", "")


def fresh():
    _n[0] += 1
    return "sess%d" % _n[0]


def rx(rule, glob_index=None):
    return dict((n, r) for n, r, _ in ri.load_rules())[rule]


def hit(rule, path, root=PROJ):
    return ri.rule_matches(rx(rule), path, root)


class Globs(unittest.TestCase):
    def test_every_rule_has_globs(self):
        names = {n for n, _, _ in ri.load_rules()}
        self.assertEqual(names, {"comments", "agent-docs", "code-structure", "code-reuse", "memory"})

    def test_comments_braces(self):
        for ext in ("luau", "py", "html", "sh", "kt", "tsx"):
            self.assertTrue(hit("comments", "/a/b/c.%s" % ext), ext)
        for ext in ("md", "txt", "json"):
            self.assertFalse(hit("comments", "/a/b/c.%s" % ext), ext)
        self.assertTrue(hit("comments", "/c.py"))  # `**/` 는 0개 디렉터리도 된다

    def test_agent_docs(self):
        for p in ("/r/CLAUDE.md", "/r/skills/x/SKILL.md", "/r/agents/a.md", "/r/.claude/rules/r.md", "/r/skills/x/references/y/z.md"):
            self.assertTrue(hit("agent-docs", p), p)
        self.assertFalse(hit("agent-docs", "/r/README.md"))

    def test_code_structure_and_web(self):
        self.assertTrue(hit("code-structure", "/r/a.luau"))
        self.assertTrue(hit("code-structure", "/r/src/a.rs"))
        self.assertTrue(hit("code-structure", "/r/a.py"))
        self.assertFalse(hit("code-structure", "/r/a.md"))

    def test_memory_absolute_path_outside_project(self):
        self.assertTrue(hit("memory", "/code/.claude/projects/-code-Projects-x/memory/user.md"))
        self.assertTrue(hit("memory", "/code/.claude/projects/-code-Projects-x/memory/MEMORY.md"))
        self.assertTrue(hit("memory", "/r/.claude/memory/a/b.txt"))
        self.assertFalse(hit("memory", "/r/notes/a.md"))

    def test_glob_regex_pieces(self):
        g = ri.glob_to_regex
        self.assertTrue(g("src/**/*.ts").match("src/a/b/c.ts"))
        self.assertTrue(g("src/**/*.ts").match("src/c.ts"))
        self.assertFalse(g("src/**/*.ts").match("lib/c.ts"))
        self.assertFalse(g("*.ts").match("a/b.ts"))
        self.assertTrue(g("a/{b,c/{d,e}}/f").match("a/c/e/f"))
        self.assertTrue(g("a?.py").match("ab.py"))
        self.assertFalse(g("a?.py").match("a/.py"))
        self.assertTrue(g("[ab].py").match("a.py"))
        self.assertTrue(g("a/**").match("a/b/c"))

    def test_relative_pattern_is_project_relative(self):
        rx_ = [ri.glob_to_regex("src/**/*.ts")]
        self.assertTrue(ri.rule_matches(rx_, os.path.join(PROJ, "src/a/b.ts"), PROJ))
        self.assertFalse(ri.rule_matches(rx_, os.path.join(PROJ, "other/src/a/b.ts"), PROJ))


class Injection(unittest.TestCase):
    def test_post_read_injects_once_and_wraps(self):
        s = fresh()
        out = run("PostToolUse", "Read", X + "/a.py", s)
        c = ctx(out)
        self.assertIn('<rule plugin="qwreey-conventions" name="comments">', c)
        self.assertIn("Write why", c)
        self.assertNotIn("paths:", c)  # 프론트매터는 뗀다
        self.assertNotIn("web-security", c)  # web-security rule 은 별도 플러그인이다
        self.assertIsNone(run("PostToolUse", "Edit", X + "/b.py", s))  # 같은 rule 은 다시 안 넣는다
        self.assertIn('name="agent-docs"', ctx(run("PostToolUse", "Read", X + "/CLAUDE.md", s)))  # 다른 rule 은 넣는다

    def test_no_match_is_silent(self):
        self.assertIsNone(run("PostToolUse", "Read", X + "/a.txt", fresh()))

    def test_agent_and_session_keys(self):
        s = fresh()
        self.assertTrue(run("PostToolUse", "Read", X + "/a.py", s))
        self.assertTrue(run("PostToolUse", "Read", X + "/a.py", s, agent="ag1"))
        self.assertIsNone(run("PostToolUse", "Read", X + "/a.py", s, agent="ag1"))
        self.assertTrue(run("PostToolUse", "Read", X + "/a.py", s, agent="ag2"))
        self.assertTrue(run("PostToolUse", "Read", X + "/a.py", fresh()))

    def test_compact_epoch_reinjects(self):
        s = fresh()
        self.assertTrue(run("PostToolUse", "Read", X + "/a.py", s))
        self.assertIsNone(run("PostToolUse", "Read", X + "/a.py", s))
        subprocess.run([sys.executable, "-I", os.path.join(HOOKS, "compact_epoch.py"), "qwreey-conventions"],
                       input=json.dumps({"session_id": s}), text=True, env=dict(os.environ, TMPDIR=T))
        self.assertTrue(run("PostToolUse", "Read", X + "/a.py", s))

    def test_notebook_path(self):
        payload = {"hook_event_name": "PostToolUse", "tool_name": "NotebookEdit", "tool_input": {"notebook_path": X + "/n.py"},
                   "session_id": fresh(), "cwd": PROJ}
        r = subprocess.run([sys.executable, "-I", HOOK], input=json.dumps(payload), capture_output=True, text=True,
                           env=dict(os.environ, TMPDIR=T, CLAUDE_CONFIG_DIR=CFG, CLAUDE_PROJECT_DIR=PROJ))
        self.assertIn("comments", r.stdout)


class AfterWrite(unittest.TestCase):
    """PreToolUse deny 는 없다. 편집·쓰기 뒤 처음이면 본문과 대조 문장을 한 번 싣는다."""

    def test_no_pretooluse_output_and_no_hook_entry(self):
        s = fresh()
        self.assertIsNone(run("PreToolUse", "Write", os.path.join(PROJ, "brand_new.py"), s))
        with open(os.path.join(HOOKS, "hooks.json"), encoding="utf-8") as f:
            hooks = json.load(f)["hooks"]
        for entry in hooks.get("PreToolUse", []):
            for h in entry["hooks"]:
                self.assertNotIn("rules_inject", h["command"])

    def test_write_injects_with_check_sentence_once(self):
        for tool in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
            s = fresh()
            c = ctx(run("PostToolUse", tool, os.path.join(PROJ, "w.py"), s))
            self.assertIn('name="comments"', c, tool)
            self.assertIn("Check what you wrote against them and fix it.", c, tool)
            self.assertIsNone(run("PostToolUse", tool, os.path.join(PROJ, "w2.py"), s), tool)

    def test_read_has_no_check_sentence(self):
        c = ctx(run("PostToolUse", "Read", PROJ + "/r.py", fresh()))
        self.assertIn('name="comments"', c)
        self.assertNotIn("Check what you wrote", c)

    def test_read_then_write_does_not_repeat(self):
        s = fresh()
        self.assertTrue(run("PostToolUse", "Read", PROJ + "/rw.py", s))
        self.assertIsNone(run("PostToolUse", "Write", PROJ + "/rw.py", s))

    def test_wrapper_text(self):
        c = ctx(run("PostToolUse", "Read", PROJ + "/wt.py", fresh()))
        self.assertIn("shown once per context", c)
        self.assertNotIn("Follow them for this file", c)
        self.assertNotIn(".claude/rules with paths", c)

    def test_subagent_write_injects_again(self):
        s = fresh()
        run("PostToolUse", "Read", PROJ + "/a.py", s)
        self.assertIn("Check what you wrote", ctx(run("PostToolUse", "Edit", PROJ + "/a.py", s, agent="sub1")))

    def test_compact_then_first_edit_injects(self):
        s = fresh()
        run("PostToolUse", "Read", PROJ + "/cmp.py", s)
        subprocess.run([sys.executable, "-I", os.path.join(HOOKS, "compact_epoch.py"), "qwreey-conventions"],
                       input=json.dumps({"session_id": s}), text=True, env=dict(os.environ, TMPDIR=T))
        self.assertIn("Check what you wrote", ctx(run("PostToolUse", "Edit", PROJ + "/cmp.py", s)))


class Cost(unittest.TestCase):
    def test_skip_dirs(self):
        for d in ("node_modules", ".git", "dist", "build", ".venv", "vendor", "__pycache__"):
            for tool in ("Read", "Edit"):
                self.assertIsNone(run("PostToolUse", tool, "%s/%s/pkg/a.py" % (PROJ, d), fresh()), (d, tool))
        self.assertTrue(run("PostToolUse", "Read", PROJ + "/builder/a.py", fresh()))

    def test_parent_dir_named_build_is_not_skipped(self):
        proj = os.path.join(T, "build", "p")
        os.makedirs(proj, exist_ok=True)
        self.assertTrue(run("PostToolUse", "Read", proj + "/a.py", fresh(), env={"CLAUDE_PROJECT_DIR": proj}, cwd=proj))

    def test_read_outside_project_skipped_but_edit_injects(self):
        outside = os.path.join(T, "sibling", "a.py")
        self.assertIsNone(run("PostToolUse", "Read", outside, fresh()))
        self.assertTrue(run("PostToolUse", "Edit", outside, fresh()))
        self.assertTrue(run("PostToolUse", "Write", outside, fresh()))

    def test_memory_read_outside_project_injects(self):
        mem = os.path.join(CFG, "projects", "-x-y", "memory", "user.md")
        self.assertIn('name="memory"', ctx(run("PostToolUse", "Read", mem, fresh())))
        notmem = os.path.join(CFG, "projects", "-x-y", "other", "user.md")
        self.assertIsNone(run("PostToolUse", "Read", notmem, fresh()))

    def test_cwd_is_root_without_project_dir(self):
        e = {"CLAUDE_PROJECT_DIR": ""}
        self.assertTrue(run("PostToolUse", "Read", PROJ + "/c.py", fresh(), env=e, cwd=PROJ))
        self.assertIsNone(run("PostToolUse", "Read", T + "/sibling/c.py", fresh(), env=e, cwd=PROJ))


class Race(unittest.TestCase):
    def test_parallel_claims_inject_once(self):
        s = fresh()
        with ThreadPoolExecutor(8) as ex:
            outs = list(ex.map(lambda i: run("PostToolUse", "Read", X + "/p%d.py" % i, s), range(8)))
        self.assertEqual(sum(1 for o in outs if o), 1)


class Switches(unittest.TestCase):
    def test_env_off(self):
        self.assertIsNone(run("PostToolUse", "Read", X + "/a.py", fresh(), env={"HARNESS_CONVENTIONS_RULES": "off"}))

    def test_harness_env_off(self):
        with open(os.path.join(CFG, "harness.env"), "w") as f:
            f.write("HARNESS_CONVENTIONS_RULES=off\n")
        try:
            self.assertIsNone(run("PostToolUse", "Read", X + "/a.py", fresh()))
        finally:
            os.remove(os.path.join(CFG, "harness.env"))
        self.assertTrue(run("PostToolUse", "Read", X + "/a.py", fresh()))

    def test_rules_exclude(self):
        p = os.path.join(PROJ, ".claude", "conventions.json")
        with open(p, "w") as f:
            json.dump({"rules_exclude": ["comments"]}, f)
        try:
            self.assertNotIn('name="comments"', ctx(run("PostToolUse", "Read", X + "/a.py", fresh())))
            self.assertIn("code-structure", ctx(run("PostToolUse", "Read", X + "/a.ts", fresh())))
        finally:
            os.remove(p)

    def test_bad_input_is_silent(self):
        r = subprocess.run([sys.executable, "-I", HOOK], input="not json file_path", capture_output=True, text=True)
        self.assertEqual((r.returncode, r.stdout), (0, ""))


if __name__ == "__main__":
    unittest.main()
