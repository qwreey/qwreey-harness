#!/usr/bin/env python3
"""doctor 항목 7 도메인 팩 검사(pack_checks.py) 회귀. 실행: python3 -I test_pack_checks.py  (exit 0 = 통과)

임시 저장소와 임시 user home 만 읽는다(실제 ~/.claude 는 읽지 않는다). 끝에서 scan.py 를 CLAUDE_CONFIG_DIR 로 한 번 돌려 연결을 본다.
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

DOCTOR = Path(__file__).resolve().parents[1] / "skills" / "doctor" / "scripts"
spec = importlib.util.spec_from_file_location("pack_checks", DOCTOR / "pack_checks.py")
pc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pc)
WEB = {"web": ["web/package.json: react"]}
LUAU = {"luau": ["*.luau 3개"]}
KEY = "web-security@claude-doctor-market"


def settings(path, plugins):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"enabledPlugins": plugins}), encoding="utf-8")


class Packs(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name) / "repo"
        self.home = Path(self.tmp.name) / "home"
        self.repo.mkdir()
        self.home.mkdir()
        (self.home / "plugins").mkdir()
        (self.home / "plugins" / "known_marketplaces.json").write_text(json.dumps({"claude-doctor-market": {}}))
        self.got = []
        self.addCleanup(self.tmp.cleanup)

    def run_check(self, active):
        pc.run(lambda item, sev, code, where, msg, ref=None: self.got.append((sev, code, msg)), self.repo, active, self.home)
        return [c for _, c, _ in self.got]

    def test_missing_with_exact_line(self):
        self.assertEqual(self.run_check(WEB), ["PACK-MISSING"])
        self.assertIn(f'`"{KEY}": true`', self.got[0][2])
        self.assertEqual(self.got[0][0], "경고")

    def test_pack_from_unknown_market_is_not_missing(self):
        (self.home / "plugins" / "known_marketplaces.json").write_text(json.dumps({"other-market": {}}))
        self.assertNotIn("PACK-MISSING", self.run_check({"luau": ["x/.luaurc"]}))

    def test_enabled_in_project_is_clean(self):
        settings(self.repo / ".claude" / "settings.json", {KEY: True})
        self.assertEqual(self.run_check(WEB), [])

    def test_local_settings_count_and_override(self):
        settings(self.repo / ".claude" / "settings.local.json", {KEY: True})
        self.assertEqual(self.run_check(WEB), [])

    def test_project_false_is_deliberate(self):
        settings(self.repo / ".claude" / "settings.json", {KEY: False})
        self.assertEqual(self.run_check(WEB), [])

    def test_unused_when_toolkit_absent(self):
        settings(self.repo / ".claude" / "settings.json", {KEY: True})
        self.assertEqual(self.run_check({}), ["PACK-UNUSED"])

    def test_user_level_enabled(self):
        settings(self.home / "settings.json", {KEY: True})
        self.assertEqual(self.run_check(WEB), ["PACK-USER-LEVEL"])
        self.got.clear()
        self.assertEqual(self.run_check({}), ["PACK-UNUSED", "PACK-USER-LEVEL"])

    def test_project_false_overrides_user_true(self):
        settings(self.home / "settings.json", {KEY: True})
        settings(self.repo / ".claude" / "settings.json", {KEY: False})
        self.assertEqual(self.run_check({}), ["PACK-USER-LEVEL"])

    def test_luau_pack_market(self):
        self.assertEqual(self.run_check(LUAU), ["PACK-MISSING"])
        self.assertIn("luau-kb@claude-doctor-market", self.got[0][2])
        self.got.clear()
        settings(self.repo / ".claude" / "settings.json", {"luau-kb@claude-doctor-market": True})
        self.assertEqual(self.run_check(LUAU), [])

    def test_broken_json_is_ignored(self):
        p = self.repo / ".claude" / "settings.json"
        p.parent.mkdir()
        p.write_text("{nope", encoding="utf-8")
        self.assertEqual(self.run_check(WEB), ["PACK-MISSING"])

    def test_scan_wiring(self):
        (self.repo / "package.json").write_text(json.dumps({"dependencies": {"react": "1"}}), encoding="utf-8")
        env = {**os.environ, "CLAUDE_CONFIG_DIR": str(self.home), "HARNESS_WORKSPACE": self.tmp.name}
        out = subprocess.run([sys.executable, "-I", str(DOCTOR / "scan.py"), str(self.repo), "--json", "--only", "7"],
                             capture_output=True, text=True, env=env, timeout=100, stdin=subprocess.DEVNULL)
        codes = [f["code"] for f in json.loads(out.stdout)["findings"]]
        self.assertIn("PACK-MISSING", codes, out.stdout + out.stderr)


if __name__ == "__main__":
    unittest.main()
