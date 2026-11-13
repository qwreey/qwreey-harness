#!/usr/bin/env python3
"""bash-bypass-reminder 회귀. 실행: timeout 120 python3 -I test-bash-bypass-reminder.py  (exit 0 = 통과)

level(쓰기 신호가 있으면 warn, 읽기만 하는 인터프리터 명령은 info)과, 규칙 안내가 설치된 플러그인의 rules/(폴더 마켓은 마켓 정의의 폴더)와 프로젝트가 목록에 적은 팩의 rules/ 를 보는지 본다.
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
# nonce 는 고정 salt 로(실제 ~/.local/share 의 salt 를 쓰지 않게)
open(os.path.join(T, "salt"), "w").write("00" * 32)
os.environ["QWREEY_HARNESS_SALT_FILE"] = os.path.join(T, "salt")
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

    def test_directory_market_beats_stale_install_path_and_packs_need_listing(self):
        """폴더 마켓은 installPath 가 옛 캐시여도 마켓 정의의 폴더를 본다. coderag.toml 을 실은 팩은 프로젝트 목록에 있을 때만 나온다."""
        mkt = os.path.join(T, "mkt")
        for rel, body in (("plugins/tool/rules/tool.md", '---\npaths: ["**/*.ts"]\n---\n# t\n'),
                          ("packs/sec/rules/sec.md", '---\npaths: ["**/*.ts"]\n---\n# s\n'), ("packs/sec/coderag.toml", "[pack]\nname = \"sec\"\n")):
            os.makedirs(os.path.dirname(os.path.join(mkt, rel)), exist_ok=True)
            with open(os.path.join(mkt, rel), "w", encoding="utf-8") as f:
                f.write(body)
        os.makedirs(os.path.join(mkt, ".claude-plugin"), exist_ok=True)
        with open(os.path.join(mkt, ".claude-plugin", "marketplace.json"), "w", encoding="utf-8") as f:
            json.dump({"name": "m", "plugins": [{"name": "tool", "source": "./plugins/tool"}, {"name": "sec", "source": "./packs/sec"}]}, f)
        os.makedirs(os.path.join(CFG, "plugins"), exist_ok=True)
        stale = os.path.join(T, "cache", "stale")
        with open(os.path.join(CFG, "plugins", "installed_plugins.json"), "w", encoding="utf-8") as f:
            json.dump({"plugins": {"tool@m": [{"installPath": stale}], "sec@m": [{"installPath": stale}]}}, f)
        with open(os.path.join(CFG, "plugins", "known_marketplaces.json"), "w", encoding="utf-8") as f:
            json.dump({"m": {"source": {"source": "directory", "path": mkt}, "installLocation": mkt}}, f)
        home = os.path.join(T, "crhome")
        os.makedirs(home, exist_ok=True)
        with open(os.path.join(home, "coderag.toml"), "w", encoding="utf-8") as f:
            f.write('[[packs]]\nname = "sec"\npath = "%s"\n' % os.path.join(mkt, "packs", "sec"))
        env = {"CODERAG_HOME": home}
        try:
            c = run("cat src/a.ts | python3 -c 'import sys'", env)
            self.assertIn(os.path.join(mkt, "plugins", "tool", "rules", "tool.md"), c)
            self.assertNotIn(stale, c)
            self.assertNotIn("sec (sec rule:", c, "목록에 없는 팩은 알리지 않는다")
            with open(os.path.join(PROJ, "coderag.toml"), "w", encoding="utf-8") as f:
                f.write('[[packs]]\nname = "sec"\n')
            self.assertIn(os.path.join(mkt, "packs", "sec", "rules", "sec.md"), run("cat src/b.ts | python3 -c 'import sys'", env))
        finally:
            for f in (os.path.join(CFG, "plugins", "installed_plugins.json"), os.path.join(CFG, "plugins", "known_marketplaces.json"),
                      os.path.join(PROJ, "coderag.toml")):
                if os.path.exists(f):
                    os.remove(f)

    def test_own_rules_still_listed(self):
        self.assertIn("code-structure (qwreey-conventions rule:", run("python3 -c \"print(open('src/a.py').read())\""))

    def test_brace_glob_rule_matches_py(self):
        """comments rule 의 paths 는 중괄호 패턴이다. rules_inject 의 glob 해석을 같이 쓰므로 .py 가 맞는다."""
        c = run("python3 -c \"print(open('src/a.py').read())\"")
        self.assertIn("comments (qwreey-conventions rule:", c)
        self.assertNotIn("comments (qwreey-conventions rule:", run("python3 -c \"print(open('src/a.md').read())\""))


if __name__ == "__main__":
    unittest.main()
