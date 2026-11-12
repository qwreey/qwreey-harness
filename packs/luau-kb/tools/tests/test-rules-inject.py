#!/usr/bin/env python3
"""luau-kb 의 rule 주입 회귀. 실행: timeout 120 python3 -I tools/tests/test-rules-inject.py </dev/null  (exit 0 = 통과)

팩은 훅을 싣지 않는다. rule 주입은 coderag 바이너리(`coderag hook post-tool --pack luau-kb`)로 시험한다: .luau Read 가 luau-core 를 한 번 넣는지,
다른 경로는 안 넣는지, 팩에 hooks/hooks.json 이 없는지 본다. 바이너리가 없으면 그 시험은 건너뛴다. 상태는 임시 CODERAG_HOME·CODERAG_CACHE 로 격리한다.
"""
import json
import os
import subprocess
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CODERAG = os.environ.get("CODERAG_BIN") or "/code/Projects/coderag/bin/coderag"
HAVE_BIN = os.access(CODERAG, os.X_OK)
T = tempfile.mkdtemp(prefix="luau-kb-")
HOME = os.path.join(T, "home")
CACHE = os.path.join(T, "cache")
PROJ = os.path.join(T, "proj")
for d in (HOME, CACHE, PROJ):
    os.makedirs(d)
with open(os.path.join(HOME, "coderag.toml"), "w", encoding="utf-8") as f:
    f.write('[[packs]]\nname = "luau-kb"\npath = "%s"\n' % ROOT)
_n = [0]


def run(tool, path, session):
    payload = {"hook_event_name": "PostToolUse", "tool_name": tool, "tool_input": {"file_path": path}, "session_id": session, "cwd": PROJ}
    e = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": T, "CODERAG_HOME": HOME, "CODERAG_CACHE": CACHE, "CLAUDE_PROJECT_DIR": PROJ}
    r = subprocess.run([CODERAG, "hook", "post-tool", "--pack", "luau-kb"], input=json.dumps(payload), capture_output=True, text=True, env=e, timeout=30)
    return json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"] if r.stdout.strip() else None


def fresh():
    _n[0] += 1
    return "lk%d" % _n[0]


@unittest.skipUnless(HAVE_BIN, "coderag 바이너리가 없다($CODERAG_BIN 또는 /code/Projects/coderag/bin/coderag)")
class Inject(unittest.TestCase):
    def test_luau_read_injects_core_once(self):
        s = fresh()
        c = run("Read", PROJ + "/a.luau", s)
        self.assertIn('<rule plugin="luau-kb" name="luau-core">', c)
        self.assertIn("Luau core rules", c)
        self.assertIsNone(run("Read", PROJ + "/b.luau", s))

    def test_non_matching_path_silent(self):
        for f in ("a.py", "a.md", "a.ts", "luau"):
            self.assertIsNone(run("Read", PROJ + "/" + f, fresh()), f)

    def test_write_adds_check_sentence(self):
        c = run("Write", PROJ + "/new.luau", fresh())
        self.assertIn("Check what you wrote against them", c)


class Layout(unittest.TestCase):
    def test_pack_has_no_hooks_json(self):
        # rule 은 coderag 플러그인이 넣는다. 팩이 훅을 싣으면 같은 rule 이 두 번 실린다.
        self.assertFalse(os.path.exists(os.path.join(ROOT, "hooks", "hooks.json")))
        self.assertFalse(os.path.exists(os.path.join(ROOT, "hooks", "rules_inject.py")))

    def test_plugin_name(self):
        with open(os.path.join(ROOT, ".claude-plugin", "plugin.json"), encoding="utf-8") as f:
            self.assertEqual(json.load(f)["name"], "luau-kb")


if __name__ == "__main__":
    unittest.main()
