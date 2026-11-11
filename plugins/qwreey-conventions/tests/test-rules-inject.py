#!/usr/bin/env python3
"""rules_inject 훅 회귀. 실행: python3 -I test-rules-inject.py  (exit 0 = 통과)

glob 변환(옮겨 온 rule 5개의 패턴 전부), 주입 dedup(에이전트·compact 회차·세션별), 새 파일 Write 1회 deny, 병렬 호출 이중 주입 없음,
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
        self.assertEqual(names, {"comments", "agent-docs", "code-structure", "memory", "web-security"})

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
        self.assertTrue(hit("web-security", "/r/a.astro"))
        self.assertTrue(hit("web-security", "/r/a.cjs"))
        self.assertFalse(hit("web-security", "/r/a.luau"))

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
        out = run("PostToolUse", "Read", "/x/a.py", s)
        c = ctx(out)
        self.assertIn('<rule plugin="qwreey-conventions" name="comments">', c)
        self.assertIn("Write why", c)
        self.assertNotIn("paths:", c)  # 프론트매터는 뗀다
        self.assertNotIn("name=\"web-security\"", c)
        self.assertIsNone(run("PostToolUse", "Edit", "/x/b.py", s))  # 같은 rule 은 다시 안 넣는다
        self.assertIn('name="web-security"', ctx(run("PostToolUse", "Read", "/x/c.ts", s)))  # 다른 rule 은 넣는다

    def test_no_match_is_silent(self):
        self.assertIsNone(run("PostToolUse", "Read", "/x/a.txt", fresh()))

    def test_agent_and_session_keys(self):
        s = fresh()
        self.assertTrue(run("PostToolUse", "Read", "/x/a.py", s))
        self.assertTrue(run("PostToolUse", "Read", "/x/a.py", s, agent="ag1"))
        self.assertIsNone(run("PostToolUse", "Read", "/x/a.py", s, agent="ag1"))
        self.assertTrue(run("PostToolUse", "Read", "/x/a.py", s, agent="ag2"))
        self.assertTrue(run("PostToolUse", "Read", "/x/a.py", fresh()))

    def test_compact_epoch_reinjects(self):
        s = fresh()
        self.assertTrue(run("PostToolUse", "Read", "/x/a.py", s))
        self.assertIsNone(run("PostToolUse", "Read", "/x/a.py", s))
        subprocess.run([sys.executable, "-I", os.path.join(HOOKS, "compact_epoch.py"), "qwreey-conventions"],
                       input=json.dumps({"session_id": s}), text=True, env=dict(os.environ, TMPDIR=T))
        self.assertTrue(run("PostToolUse", "Read", "/x/a.py", s))

    def test_notebook_path(self):
        payload = {"hook_event_name": "PostToolUse", "tool_name": "NotebookEdit", "tool_input": {"notebook_path": "/x/n.py"},
                   "session_id": fresh(), "cwd": PROJ}
        r = subprocess.run([sys.executable, "-I", HOOK], input=json.dumps(payload), capture_output=True, text=True,
                           env=dict(os.environ, TMPDIR=T, CLAUDE_CONFIG_DIR=CFG, CLAUDE_PROJECT_DIR=PROJ))
        self.assertIn("comments", r.stdout)


class Deny(unittest.TestCase):
    def test_new_file_write_denied_once(self):
        s = fresh()
        new = os.path.join(T, "brand_new.py")
        out = run("PreToolUse", "Write", new, s)
        self.assertEqual(out["permissionDecision"], "deny")
        reason = out["permissionDecisionReason"]
        self.assertIn("not an error", reason)
        self.assertIn("Retry the same Write call", reason)
        self.assertIn("Do not mention this notice", reason)
        self.assertIn('name="comments"', reason)
        self.assertIsNone(run("PreToolUse", "Write", new, s))  # 재시도는 통과
        self.assertIsNone(run("PostToolUse", "Write", new, s))  # 이미 넣은 rule 은 다시 안 넣는다

    def test_existing_file_pre_denies_once_for_every_edit_tool(self):
        ex = os.path.join(T, "existing.py")
        with open(ex, "w") as f:
            f.write("x = 1\n")
        for tool in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
            s = fresh()
            out = run("PreToolUse", tool, ex, s)
            self.assertEqual(out["permissionDecision"], "deny", tool)
            self.assertIn('name="comments"', out["permissionDecisionReason"])
            self.assertIn("Retry the same %s call" % tool, out["permissionDecisionReason"])
            self.assertIsNone(run("PreToolUse", tool, ex, s), tool)  # 재시도는 통과
            self.assertIsNone(run("PostToolUse", tool, ex, s), tool)  # 같은 rule 을 다시 안 넣는다

    def test_read_first_means_no_deny(self):
        s = fresh()
        ex = os.path.join(T, "readfirst.py")
        with open(ex, "w") as f:
            f.write("x = 1\n")
        self.assertTrue(run("PostToolUse", "Read", ex, s))
        self.assertIsNone(run("PreToolUse", "Edit", ex, s))

    def test_subagent_edit_without_read_is_denied_once(self):
        s = fresh()
        ex = os.path.join(T, "sub.py")
        with open(ex, "w") as f:
            f.write("x = 1\n")
        run("PostToolUse", "Read", ex, s)  # 메인이 읽음
        out = run("PreToolUse", "Edit", ex, s, agent="sub1")  # 서브에이전트는 Read 없이 편집
        self.assertEqual(out["permissionDecision"], "deny")
        self.assertIsNone(run("PreToolUse", "Edit", ex, s, agent="sub1"))

    def test_compact_then_first_edit_denied(self):
        s = fresh()
        ex = os.path.join(T, "cmp.py")
        with open(ex, "w") as f:
            f.write("x = 1\n")
        run("PostToolUse", "Read", ex, s)
        subprocess.run([sys.executable, "-I", os.path.join(HOOKS, "compact_epoch.py"), "qwreey-conventions"],
                       input=json.dumps({"session_id": s}), text=True, env=dict(os.environ, TMPDIR=T))
        self.assertEqual(run("PreToolUse", "Edit", ex, s)["permissionDecision"], "deny")

    def test_parallel_claims_inject_once(self):
        s = fresh()
        with ThreadPoolExecutor(8) as ex:
            outs = list(ex.map(lambda i: run("PostToolUse", "Read", "/x/p%d.py" % i, s), range(8)))
        self.assertEqual(sum(1 for o in outs if o), 1)


class Switches(unittest.TestCase):
    def test_env_off(self):
        self.assertIsNone(run("PostToolUse", "Read", "/x/a.py", fresh(), env={"HARNESS_CONVENTIONS_RULES": "off"}))

    def test_harness_env_off(self):
        with open(os.path.join(CFG, "harness.env"), "w") as f:
            f.write("HARNESS_CONVENTIONS_RULES=off\n")
        try:
            self.assertIsNone(run("PostToolUse", "Read", "/x/a.py", fresh()))
        finally:
            os.remove(os.path.join(CFG, "harness.env"))
        self.assertTrue(run("PostToolUse", "Read", "/x/a.py", fresh()))

    def test_rules_exclude(self):
        p = os.path.join(PROJ, ".claude", "conventions.json")
        with open(p, "w") as f:
            json.dump({"rules_exclude": ["comments"]}, f)
        try:
            self.assertNotIn('name="comments"', ctx(run("PostToolUse", "Read", "/x/a.py", fresh())))
            self.assertIn("web-security", ctx(run("PostToolUse", "Read", "/x/a.ts", fresh())))
        finally:
            os.remove(p)

    def test_bad_input_is_silent(self):
        r = subprocess.run([sys.executable, "-I", HOOK], input="not json file_path", capture_output=True, text=True)
        self.assertEqual((r.returncode, r.stdout), (0, ""))


if __name__ == "__main__":
    unittest.main()
