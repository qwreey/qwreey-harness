#!/usr/bin/env python3
"""bash-bypass-reminder 회귀. 실행: timeout 120 python3 -I test-bash-bypass-reminder.py  (exit 0 = 통과)

level(쓰기 신호가 있으면 warn, 읽기만 하는 인터프리터 명령은 info)과, 규칙 안내가 설치된 모든 플러그인의 rules/ 를 보는지 본다.
상태는 TMPDIR 로 격리한다.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOK = os.path.join(ROOT, "hooks", "bash-bypass-reminder.py")
T = tempfile.mkdtemp(prefix="bypass-")
CFG = os.path.join(T, "cfg")
PROJ = os.path.join(T, "proj")
os.makedirs(PROJ)
os.makedirs(CFG)
_n = [0]


def run(cmd, env=None):
    _n[0] += 1
    payload = {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": cmd}, "session_id": "b%d" % _n[0], "cwd": PROJ}
    e = dict(os.environ, TMPDIR=T, CLAUDE_CONFIG_DIR=CFG, CLAUDE_PROJECT_DIR=PROJ)
    e.update(env or {})
    r = subprocess.run([sys.executable, "-I", HOOK], input=json.dumps(payload), capture_output=True, text=True, env=e)
    return json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"] if r.stdout.strip() else ""


class Levels(unittest.TestCase):
    def test_read_only_interpreter_is_info(self):
        for cmd in ("python3 - <<'EOF'\nprint(open('a.py').read())\nEOF", "python3 -I tests/test-x.py", "node -e \"console.log(1)\" a.ts"):
            c = run(cmd)
            self.assertIn('level="info"', c, cmd)
            self.assertNotIn('level="warn"', c, cmd)

    def test_interpreter_that_writes_is_warn(self):
        c = run("python3 - <<'EOF'\nopen('a.py','w').write('x')\nEOF")
        self.assertIn('level="warn"', c)
        self.assertIn('level="warn"', run("python3 -c \"import pathlib; pathlib.Path('a.py').write_text('x')\""))

    def test_shell_writes_stay_warn(self):
        self.assertIn('level="warn"', run("sed -i 's/a/b/' src/a.py"))
        self.assertIn('level="warn"', run("echo x > src/a.py"))

    def test_rules_note_level_follows_write_signal(self):
        read = run("python3 -c \"print(open('src/a.py').read())\"")
        self.assertIn("Rules that apply to files this command touches", read)
        self.assertIn('level="info"', read)
        write = run("python3 -c \"open('src/a.py','w').write('x')\"")
        self.assertIn("Rules that apply", write)
        self.assertIn('level="warn"', write)

    def test_plain_commands_silent(self):
        self.assertEqual(run("ls -la"), "")
        self.assertEqual(run("git status"), "")


class PluginRules(unittest.TestCase):
    def test_rules_from_other_installed_plugins_are_found(self):
        inst = os.path.join(T, "cache", "web-security", "0.1.0")
        os.makedirs(os.path.join(inst, "rules"))
        with open(os.path.join(inst, "rules", "web-security.md"), "w", encoding="utf-8") as f:
            f.write('---\npaths: ["**/*.ts"]\n---\n# body\n')
        os.makedirs(os.path.join(CFG, "plugins"), exist_ok=True)
        with open(os.path.join(CFG, "plugins", "installed_plugins.json"), "w", encoding="utf-8") as f:
            json.dump({"version": 2, "plugins": {"web-security@claude-doctor-market": [{"installPath": inst}]}}, f)
        try:
            c = run("cat src/a.ts | python3 -c 'import sys'")
            self.assertIn("web-security (web-security rule:", c)
            self.assertIn(os.path.join(inst, "rules", "web-security.md"), c)
        finally:
            os.remove(os.path.join(CFG, "plugins", "installed_plugins.json"))
        self.assertNotIn("web-security (web-security rule:", run("cat src/a.ts | python3 -c 'import sys'"))

    def test_own_rules_still_listed(self):
        self.assertIn("code-structure (qwreey-conventions rule:", run("python3 -c \"print(open('src/a.py').read())\""))

    def test_brace_glob_rule_matches_py(self):
        """comments rule 의 paths 는 중괄호 패턴이다. rules_inject 의 glob 해석을 같이 쓰므로 .py 가 맞는다."""
        c = run("python3 -c \"print(open('src/a.py').read())\"")
        self.assertIn("comments (qwreey-conventions rule:", c)
        self.assertNotIn("comments (qwreey-conventions rule:", run("python3 -c \"print(open('src/a.md').read())\""))


if __name__ == "__main__":
    unittest.main()
