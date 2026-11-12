#!/usr/bin/env python3
"""luau-kb 의 rules 주입 훅 회귀. 실행: timeout 120 python3 -I tools/tests/test-rules-inject.py </dev/null  (exit 0 = 통과)

hooks/ 의 rules_inject.py·conv_env.py·compact_epoch.py 는 claude-doctor 정본의 바이트 같은 사본이다. 여기서는 .luau Read 가 luau-core 를 한 번 넣는지,
다른 경로는 안 넣는지, 사본이 정본과 같은지(claude-doctor 가 있을 때만)를 본다. 상태는 TMPDIR 로 격리한다.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DOCTOR = os.environ.get("CLAUDE_DOCTOR_ROOT", "/code/Projects/claude-doctor")
T = tempfile.mkdtemp(prefix="luau-kb-")
CFG = os.path.join(T, "cfg")
PROJ = os.path.join(T, "proj")
os.makedirs(CFG)
os.makedirs(PROJ)
_n = [0]


def run(tool, path, session):
    payload = {"hook_event_name": "PostToolUse", "tool_name": tool, "tool_input": {"file_path": path}, "session_id": session, "cwd": PROJ}
    e = dict(os.environ, TMPDIR=T, CLAUDE_CONFIG_DIR=CFG, CLAUDE_PROJECT_DIR=PROJ)
    e.pop("HARNESS_CONVENTIONS_RULES", None)
    r = subprocess.run([sys.executable, "-I", os.path.join(ROOT, "hooks", "rules_inject.py")], input=json.dumps(payload),
                       capture_output=True, text=True, env=e)
    return json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"] if r.stdout.strip() else None


def fresh():
    _n[0] += 1
    return "lk%d" % _n[0]


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
        self.assertIn("Check what you just wrote against these rules", c)


class Layout(unittest.TestCase):
    def test_hooks_json(self):
        with open(os.path.join(ROOT, "hooks", "hooks.json"), encoding="utf-8") as f:
            hooks = json.load(f)["hooks"]
        self.assertEqual(sorted(hooks), ["PostToolUse", "PreCompact"])
        self.assertEqual(hooks["PreCompact"][0]["matcher"], "manual|auto")
        self.assertTrue(hooks["PreCompact"][0]["hooks"][0]["command"].rstrip().endswith('compact_epoch.py" luau-kb'))

    def test_plugin_name(self):
        with open(os.path.join(ROOT, ".claude-plugin", "plugin.json"), encoding="utf-8") as f:
            self.assertEqual(json.load(f)["name"], "luau-kb")


@unittest.skipUnless(os.path.isdir(DOCTOR), "claude-doctor 가 없다")
class Copies(unittest.TestCase):
    def test_byte_identical_to_canon(self):
        canon = {
            "rules_inject.py": "plugins/qwreey-conventions/hooks/rules_inject.py",
            "conv_env.py": "plugins/qwreey-conventions/hooks/conv_env.py",
            "compact_epoch.py": "plugins/q/scripts/compact_epoch.py",
        }
        for name, rel in canon.items():
            with open(os.path.join(ROOT, "hooks", name), "rb") as a, open(os.path.join(DOCTOR, rel), "rb") as b:
                self.assertEqual(a.read(), b.read(), "%s 이 정본 %s 과 다르다. 정본을 고치고 복사한다" % (name, rel))


if __name__ == "__main__":
    unittest.main()
