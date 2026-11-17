"""플러그인 옵션(/plugin configure, /config) 이 훅과 CLI 에 닿는지. 실행: python3 -I tests/test_config_options.py  (모델 호출 없음)

옵션은 <설정 디렉터리>/settings.json 의 pluginConfigs["qwreey-sessions@<마켓>"].options 에 저장된다. 훅과 Bash 로 부르는
session-log CLI 가 같은 값을 보려면 둘 다 scripts/harness_env.py 사본의 settings.json 층으로 읽어야 한다
(CLAUDE_PLUGIN_OPTION_* 는 Bash 로 부르는 스크립트에 들어가지 않는다). 그래서 따로 띄운 프로세스로 본다.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[1]
SCRIPTS = PLUGIN / "scripts"

PRINT_CONFIG = """
import json, sys
sys.path.insert(0, {scripts!r})
from sllib import config
v = config.load()
print(json.dumps({{"vals": v, "disabled": config.disabled(), "anchors_off": config.anchors_off(),
                  "read_gate_off": config.read_gate_off(), "home": str(config.home())}}))
"""


class PluginOptions(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = Path(self.tmp.name)
        self.cfg, self.home, self.proj = t / "cfg", t / "home", t / "proj"
        for d in (self.cfg, self.home, self.proj):
            d.mkdir()
        subprocess.run(["git", "init", "-q", str(self.proj)], check=True)
        self.env = {k: v for k, v in os.environ.items()
                    if not k.startswith(("SESSION_LOG", "HARNESS_", "CLAUDE_", "XDG_"))}
        self.env.update(HOME=str(self.home), CLAUDE_CONFIG_DIR=str(self.cfg), CLAUDE_PROJECT_DIR=str(self.proj),
                        TMPDIR=self.tmp.name, CLAUDE_CODE_ENTRYPOINT="cli")

    def tearDown(self):
        self.tmp.cleanup()

    def options(self, **opts):
        data = {"enabledPlugins": {"qwreey-sessions@test-market": True},
                "pluginConfigs": {"qwreey-sessions@test-market": {"options": opts}}}
        (self.cfg / "settings.json").write_text(json.dumps(data), encoding="utf-8")

    def config(self):
        p = subprocess.run([sys.executable, "-I", "-c", PRINT_CONFIG.format(scripts=str(SCRIPTS))], env=self.env,
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(p.returncode, 0, p.stderr)
        return json.loads(p.stdout)

    def test_defaults_without_options(self):
        got = self.config()
        self.assertEqual(got["vals"]["SESSION_LOG_MODEL"], "haiku")
        self.assertFalse(got["disabled"] or got["anchors_off"] or got["read_gate_off"])
        self.assertEqual(got["home"], str(self.home / ".local" / "share" / "session-log"))

    def test_options_reach_the_config(self):
        store = self.proj.parent / "store"
        self.options(session_log=False, session_log_model="sonnet", session_log_home=str(store),
                     session_log_compact_anchors=False, session_log_read_gate=False,
                     session_log_cooldown_min=1)  # userConfig 에 없는 키는 읽지 않는다
        got = self.config()
        self.assertTrue(got["disabled"])
        self.assertTrue(got["anchors_off"])
        self.assertTrue(got["read_gate_off"])
        self.assertEqual(got["vals"]["SESSION_LOG_MODEL"], "sonnet")
        self.assertEqual(got["home"], str(store))
        self.assertEqual(got["vals"]["SESSION_LOG_COOLDOWN_MIN"], "20")

    def test_session_log_switch_and_legacy_key(self):
        """SESSION_LOG 는 옵션, 저장소 층, 환경 변수에서 끈다. 옛 SESSION_LOG_DISABLE 은 harness.env 와 환경 변수에서만 끈다."""
        # Options: new switch read, legacy key ignored
        self.options(session_log=True)
        self.assertFalse(self.config()["disabled"])
        self.options(session_log_disable=True)  # 옵션에서 뺀 옛 키: userConfig 에 없으니 읽지 않는다
        self.assertFalse(self.config()["disabled"])

        # Legacy key in the user harness.env
        (self.cfg / "harness.env").write_text("SESSION_LOG_DISABLE=1\n", encoding="utf-8")
        self.assertTrue(self.config()["disabled"])
        (self.cfg / "harness.env").unlink()

        # Repo layer turns it off
        (self.proj / ".claude").mkdir()
        (self.proj / ".claude" / "harness.env").write_text("SESSION_LOG=off\n", encoding="utf-8")
        self.assertTrue(self.config()["disabled"])
        (self.proj / ".claude" / "harness.env").unlink()

        # Environment values
        for v in ("off", "0", "false"):
            self.env["SESSION_LOG"] = v
            self.assertTrue(self.config()["disabled"], v)
        self.env["SESSION_LOG"] = "on"
        self.env["SESSION_LOG_DISABLE"] = "yes"
        self.assertTrue(self.config()["disabled"])

    def test_environment_beats_options(self):
        self.options(session_log_model="sonnet")
        self.env["SESSION_LOG_MODEL"] = "opus"
        self.assertEqual(self.config()["vals"]["SESSION_LOG_MODEL"], "opus")

    def test_cli_sees_the_store_option(self):
        store = self.proj.parent / "store"
        self.options(session_log_home=str(store))
        p = subprocess.run([str(PLUGIN / "bin" / "session-log"), "status"], env=self.env, cwd=self.proj,
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn(f"store:   {store}/", p.stdout)


if __name__ == "__main__":
    unittest.main()
