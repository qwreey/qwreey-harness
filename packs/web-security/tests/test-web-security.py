#!/usr/bin/env python3
"""web-security 플러그인 회귀. 실행: timeout 120 python3 -I test-web-security.py </dev/null  (exit 0 = 통과)

팩은 훅을 싣지 않는다. rule 주입은 coderag 바이너리(`coderag hook post-tool --pack web-security`)로 시험한다: web-security rule 만 맞는 파일에 한 번 실리는지,
출력에 플러그인 이름이 나오는지, 팩에 hooks/hooks.json 이 없는지 본다. 바이너리가 없으면 그 시험은 건너뛴다. 상태는 임시 CODERAG_HOME·CODERAG_CACHE 로 격리한다.
"""
import json
import os
import subprocess
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CODERAG = os.environ.get("CODERAG_BIN") or "/code/Projects/coderag/bin/coderag"
HAVE_BIN = os.access(CODERAG, os.X_OK)
T = tempfile.mkdtemp(prefix="web-security-")
HOME = os.path.join(T, "home")
CACHE = os.path.join(T, "cache")
PROJ = os.path.join(T, "proj")
for d in (HOME, CACHE, PROJ):
    os.makedirs(d)
with open(os.path.join(HOME, "coderag.toml"), "w", encoding="utf-8") as f:
    f.write('[[packs]]\nname = "web-security"\npath = "%s"\n' % ROOT)
_n = [0]


def run(tool, path, session, env=None):
    payload = {"hook_event_name": "PostToolUse", "tool_name": tool, "tool_input": {"file_path": path}, "session_id": session, "cwd": PROJ}
    e = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": T, "CODERAG_HOME": HOME, "CODERAG_CACHE": CACHE, "CLAUDE_PROJECT_DIR": PROJ}
    e.update(env or {})
    r = subprocess.run([CODERAG, "hook", "post-tool", "--pack", "web-security"], input=json.dumps(payload), capture_output=True, text=True, env=e, timeout=30)
    return json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"] if r.stdout.strip() else None


def fresh():
    _n[0] += 1
    return "ws%d" % _n[0]


@unittest.skipUnless(HAVE_BIN, "coderag 바이너리가 없다($CODERAG_BIN 또는 /code/Projects/coderag/bin/coderag)")
class Inject(unittest.TestCase):
    def test_ts_gets_only_web_security(self):
        c = run("Read", PROJ + "/a.ts", fresh())
        self.assertIn('<rule plugin="web-security" name="web-security">', c)
        self.assertNotIn('name="comments"', c)
        self.assertNotIn('name="code-structure"', c)
        self.assertIn("Path-scoped rules from the web-security plugin", c)

    def test_injected_once_per_session(self):
        s = fresh()
        self.assertIsNotNone(run("Read", PROJ + "/a.ts", s))
        self.assertIsNone(run("Read", PROJ + "/a.ts", s))
        self.assertIsNone(run("Read", PROJ + "/b.tsx", s))

    def test_other_files_silent(self):
        for f in ("a.py", "a.md", "a.luau"):
            self.assertIsNone(run("Read", PROJ + "/" + f, fresh()), f)

    def test_all_globs(self):
        for ext in ("ts", "tsx", "js", "jsx", "mjs", "cjs", "astro"):
            self.assertIsNotNone(run("Read", PROJ + "/a." + ext, fresh()), ext)

    def test_edit_adds_check_sentence_once(self):
        s = fresh()
        c = run("Write", PROJ + "/new.ts", s)
        self.assertIn("Check what you just wrote against these rules", c)
        self.assertIsNone(run("Edit", PROJ + "/new2.ts", s))

    def test_skip_dir_and_outside_read(self):
        self.assertIsNone(run("Read", PROJ + "/node_modules/x/a.ts", fresh()))
        self.assertIsNone(run("Read", T + "/sibling/a.ts", fresh()))
        self.assertIsNotNone(run("Edit", T + "/sibling/a.ts", fresh()))

    def test_env_off(self):
        self.assertIsNone(run("Read", PROJ + "/a.ts", fresh(), env={"CODERAG_RULES": "off"}))


class NoHooks(unittest.TestCase):
    def test_pack_has_no_hooks_json(self):
        # rule 은 coderag 플러그인이 넣는다. 팩이 훅을 싣으면 같은 rule 이 두 번 실린다.
        self.assertFalse(os.path.exists(os.path.join(ROOT, "hooks", "hooks.json")))
        self.assertFalse(os.path.exists(os.path.join(ROOT, "hooks", "rules_inject.py")))


@unittest.skipUnless(HAVE_BIN, "coderag 바이너리가 없다")
class Widened(unittest.TestCase):
    def test_server_and_infra_globs(self):
        for f in ("a.go", "Caddyfile", "x/y/Caddyfile", "site.caddy", "nginx.conf", "nginx-app.conf", "a.nginx", "Dockerfile", "a.Dockerfile",
                  "compose.yaml", "compose.prod.yml", "docker-compose.yml", "docker-compose.override.yaml", "run.sh", "d/e/run.sh"):
            self.assertIsNotNone(run("Read", PROJ + "/" + f, fresh()), f)

    def test_luau_still_silent(self):
        self.assertIsNone(run("Read", PROJ + "/a.luau", fresh()))


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
