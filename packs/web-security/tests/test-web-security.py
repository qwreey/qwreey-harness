#!/usr/bin/env python3
"""web-security 플러그인 회귀. 실행: timeout 120 python3 -I test-web-security.py  (exit 0 = 통과)

사본 rules_inject.py 가 이름을 코드가 아니라 plugin.json 에서 읽는지(설치 경로의 상위 디렉터리는 버전이다), web-security rule 만 주입하는지,
dedup 이 qwreey-conventions 와 섞이지 않는지, hooks.json 이 PostToolUse 와 PreCompact 만 갖는지 본다. 상태는 TMPDIR 로 격리한다.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T = tempfile.mkdtemp(prefix="web-security-")
CFG = os.path.join(T, "cfg")
PROJ = os.path.join(T, "proj")
os.makedirs(CFG)
os.makedirs(PROJ)
_n = [0]


def run(event, tool, path, session, hook_dir=None, env=None):
    hook = os.path.join(hook_dir or os.path.join(ROOT, "hooks"), "rules_inject.py")
    payload = {"hook_event_name": event, "tool_name": tool, "tool_input": {"file_path": path}, "session_id": session, "cwd": PROJ}
    e = dict(os.environ, TMPDIR=T, CLAUDE_CONFIG_DIR=CFG, CLAUDE_PROJECT_DIR=PROJ)
    e.pop("HARNESS_CONVENTIONS_RULES", None)
    e.update(env or {})
    r = subprocess.run([sys.executable, "-I", hook], input=json.dumps(payload), capture_output=True, text=True, env=e)
    return json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"] if r.stdout.strip() else None


def fresh():
    _n[0] += 1
    return "ws%d" % _n[0]


class Inject(unittest.TestCase):
    def test_ts_gets_only_web_security(self):
        c = run("PostToolUse", "Read", PROJ + "/a.ts", fresh())
        self.assertIn('<rule plugin="web-security" name="web-security">', c)
        self.assertNotIn('name="comments"', c)
        self.assertNotIn('name="code-structure"', c)
        self.assertIn("Path-scoped rules from the web-security plugin", c)

    def test_other_files_silent(self):
        for f in ("a.py", "a.md", "a.luau"):
            self.assertIsNone(run("PostToolUse", "Read", PROJ + "/" + f, fresh()), f)

    def test_all_globs(self):
        for ext in ("ts", "tsx", "js", "jsx", "mjs", "cjs", "astro"):
            self.assertIsNotNone(run("PostToolUse", "Read", PROJ + "/a." + ext, fresh()), ext)

    def test_edit_adds_check_sentence_once(self):
        s = fresh()
        c = run("PostToolUse", "Write", PROJ + "/new.ts", s)
        self.assertIn("Check what you just wrote against these rules", c)
        self.assertIsNone(run("PostToolUse", "Edit", PROJ + "/new2.ts", s))

    def test_skip_dir_and_outside_read(self):
        self.assertIsNone(run("PostToolUse", "Read", PROJ + "/node_modules/x/a.ts", fresh()))
        self.assertIsNone(run("PostToolUse", "Read", T + "/sibling/a.ts", fresh()))
        self.assertIsNotNone(run("PostToolUse", "Edit", T + "/sibling/a.ts", fresh()))

    def test_state_is_separate_from_conventions_plugin(self):
        ns = os.path.join(T, "claude-web-security-rules")
        run("PostToolUse", "Read", PROJ + "/a.ts", fresh())
        self.assertTrue(os.path.isdir(ns))

    def test_env_off(self):
        self.assertIsNone(run("PostToolUse", "Read", PROJ + "/a.ts", fresh(), env={"HARNESS_CONVENTIONS_RULES": "off"}))

    def test_name_comes_from_plugin_json_not_directory(self):
        """설치본은 .../web-security/0.1.0/ 이라 위치의 마지막 이름이 버전이다. plugin.json 이 이름을 정한다."""
        dst = os.path.join(T, "cache", "web-security", "0.1.0")
        shutil.copytree(ROOT, dst, ignore=shutil.ignore_patterns("__pycache__", "tests"))
        c = run("PostToolUse", "Read", PROJ + "/a.ts", fresh(), hook_dir=os.path.join(dst, "hooks"))
        self.assertIn('plugin="web-security"', c)
        self.assertNotIn("0.1.0", c)

    def test_name_falls_back_to_directory(self):
        dst = os.path.join(T, "fallback", "my-sec")
        shutil.copytree(ROOT, dst, ignore=shutil.ignore_patterns("__pycache__", "tests", ".claude-plugin"))
        c = run("PostToolUse", "Read", PROJ + "/a.ts", fresh(), hook_dir=os.path.join(dst, "hooks"))
        self.assertIn('plugin="my-sec"', c)

    def test_compact_epoch_entry_reinjects(self):
        with open(os.path.join(ROOT, "hooks", "hooks.json"), encoding="utf-8") as f:
            hooks = json.load(f)["hooks"]
        cmd = hooks["PreCompact"][0]["hooks"][0]["command"]
        self.assertTrue(cmd.rstrip().endswith("compact_epoch.py\" web-security"), cmd)
        self.assertEqual(list(hooks), ["PreCompact", "PostToolUse"])
        s = fresh()
        self.assertIsNotNone(run("PostToolUse", "Read", PROJ + "/a.ts", s))
        self.assertIsNone(run("PostToolUse", "Read", PROJ + "/a.ts", s))
        subprocess.run([sys.executable, "-I", os.path.join(ROOT, "hooks", "compact_epoch.py"), "web-security"],
                       input=json.dumps({"session_id": s}), text=True, env=dict(os.environ, TMPDIR=T))
        self.assertIsNotNone(run("PostToolUse", "Read", PROJ + "/a.ts", s))


class Widened(unittest.TestCase):
    def test_server_and_infra_globs(self):
        for f in ("a.go", "Caddyfile", "x/y/Caddyfile", "site.caddy", "nginx.conf", "nginx-app.conf", "a.nginx", "Dockerfile", "a.Dockerfile",
                  "compose.yaml", "compose.prod.yml", "docker-compose.yml", "docker-compose.override.yaml", "run.sh", "d/e/run.sh"):
            self.assertIsNotNone(run("PostToolUse", "Read", PROJ + "/" + f, fresh()), f)

    def test_luau_still_silent(self):
        self.assertIsNone(run("PostToolUse", "Read", PROJ + "/a.luau", fresh()))


class Skill(unittest.TestCase):
    def test_hardening_skill_files(self):
        d = os.path.join(ROOT, "skills", "hardening")
        with open(os.path.join(d, "SKILL.md"), encoding="utf-8") as f:
            text = f.read()
        self.assertTrue(text.startswith("---\n"))
        fm = text.split("---\n")[1]
        self.assertIn("name: hardening\n", fm)
        self.assertIn("description: ", fm)
        for r in ("principles", "auth-gates", "client-identity", "browser-and-origin", "paths", "injection", "outbound-connections",
                  "secrets", "resource-limits", "supply-chain", "state-changes", "privileges", "verification"):
            self.assertTrue(os.path.isfile(os.path.join(d, "references", r + ".md")), r)
            self.assertIn("`" + r + ".md`", text, r)


class Layout(unittest.TestCase):
    def test_manifest_and_marketplace(self):
        with open(os.path.join(ROOT, ".claude-plugin", "plugin.json"), encoding="utf-8") as f:
            pj = json.load(f)
        self.assertEqual(pj["name"], "web-security")  # 버전은 올릴 때마다 바뀌므로 고정하지 않는다
        with open(os.path.join(os.path.dirname(os.path.dirname(ROOT)), ".claude-plugin", "marketplace.json"), encoding="utf-8") as f:
            mk = json.load(f)
        self.assertIn(("web-security", "./packs/web-security"), [(p["name"], p["source"]) for p in mk["plugins"]])


if __name__ == "__main__":
    unittest.main()
