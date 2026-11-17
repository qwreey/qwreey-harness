#!/usr/bin/env python3
"""doctor 항목 7 도메인 팩 검사(pack_checks.py) 회귀. 실행: python3 -I test_pack_checks.py  (exit 0 = 통과)

임시 저장소와 임시 user home 만 읽는다(실제 ~/.claude 와 PATH 는 읽지 않는다). 끝에서 scan.py 를 CLAUDE_CONFIG_DIR 로 한 번 돌려 연결을 본다.
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


def listing(repo, *names):
    (repo / "coderag.toml").write_text("".join(f'[[packs]]\nname = "{n}"\n' for n in names), encoding="utf-8")


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
        self.bin = Path(self.tmp.name) / "coderag"
        self.bin.write_text("#!/bin/sh\n")
        self.bin.chmod(0o755)
        self.crhome = Path(self.tmp.name) / "crhome"
        self.crhome.mkdir()
        (self.crhome / "coderag.toml").write_text(
            "".join(f'[[packs]]\nname = "{n}"\npath = "/packs/{n}"\n' for n in ("web-security", "luau-kb")), encoding="utf-8")
        self.got = []
        self.addCleanup(self.tmp.cleanup)

    def run_check(self, active, coderag_bin=True):
        pc.run(lambda item, sev, code, where, msg, ref=None: self.got.append((sev, code, msg)), self.repo, active, self.home,
               str(self.bin) if coderag_bin else str(self.bin) + ".none", self.crhome)
        return [c for _, c, _ in self.got]

    def test_listed_pack_without_registration(self):
        (self.crhome / "coderag.toml").write_text("", encoding="utf-8")
        listing(self.repo, "web-security")
        settings(self.repo / ".claude" / "settings.json", {KEY: True})
        self.assertEqual(self.run_check(WEB), ["PACK-UNREGISTERED"])
        self.assertIn('name = "web-security"', self.got[0][2])
        self.got.clear()
        (self.repo / "coderag.toml").write_text('[[packs]]\nname = "web-security"\npath = "/x"\n', encoding="utf-8")
        self.assertEqual(self.run_check(WEB), [], "프로젝트 항목의 path 로도 된다")

    def test_missing_with_exact_lines(self):
        self.assertEqual(self.run_check(WEB), ["PACK-MISSING"])
        self.assertIn('`[[packs]]`', self.got[0][2])
        self.assertIn('`name = "web-security"`', self.got[0][2])
        self.assertIn("coderag adapt --harness claude", self.got[0][2])
        self.assertEqual(self.got[0][0], "경고")

    def test_pack_from_unknown_market_is_not_missing(self):
        (self.home / "plugins" / "known_marketplaces.json").write_text(json.dumps({"other-market": {}}))
        self.assertNotIn("PACK-MISSING", self.run_check({"luau": ["x/.luaurc"]}))

    def test_listed_and_enabled_is_clean(self):
        listing(self.repo, "web-security")
        settings(self.repo / ".claude" / "settings.json", {KEY: True})
        self.assertEqual(self.run_check(WEB), [])

    def test_local_settings_count(self):
        listing(self.repo, "web-security")
        settings(self.repo / ".claude" / "settings.local.json", {KEY: True})
        self.assertEqual(self.run_check(WEB), [])

    def test_project_false_without_listing_is_deliberate(self):
        settings(self.repo / ".claude" / "settings.json", {KEY: False})
        self.assertEqual(self.run_check(WEB), [])

    def test_listed_but_not_enabled_drifts(self):
        listing(self.repo, "web-security")
        self.assertEqual(self.run_check(WEB), ["PACK-DRIFT"])
        self.assertIn("coderag adapt", self.got[0][2])

    def test_listed_but_false_conflicts(self):
        listing(self.repo, "web-security")
        settings(self.repo / ".claude" / "settings.json", {KEY: False})
        self.assertEqual(self.run_check(WEB), ["PACK-DRIFT"])
        self.assertIn("덮어쓰지 않", self.got[0][2])

    def test_enabled_but_not_listed_drifts(self):
        settings(self.repo / ".claude" / "settings.json", {KEY: True})
        self.assertEqual(self.run_check(WEB), ["PACK-DRIFT"])
        self.assertIn("rule 이 주입되지 않는다", self.got[0][2])

    def test_unused_when_toolkit_absent(self):
        settings(self.repo / ".claude" / "settings.json", {KEY: True})
        self.assertEqual(self.run_check({}), ["PACK-UNUSED", "PACK-DRIFT"])

    def test_unused_when_only_listed(self):
        listing(self.repo, "web-security")
        self.assertEqual(self.run_check({}), ["PACK-UNUSED", "PACK-DRIFT"])

    def test_user_level_enabled(self):
        settings(self.home / "settings.json", {KEY: True})
        self.assertEqual(self.run_check(WEB), ["PACK-MISSING", "PACK-USER-LEVEL"])
        self.got.clear()
        self.assertEqual(self.run_check({}), ["PACK-UNUSED", "PACK-USER-LEVEL"])

    def test_project_false_overrides_user_true(self):
        settings(self.home / "settings.json", {KEY: True})
        settings(self.repo / ".claude" / "settings.json", {KEY: False})
        self.assertEqual(self.run_check({}), ["PACK-USER-LEVEL"])

    def test_luau_pack(self):
        self.assertEqual(self.run_check(LUAU), ["PACK-MISSING"])
        self.assertIn('name = "luau-kb"', self.got[0][2])
        self.got.clear()
        listing(self.repo, "luau-kb")
        settings(self.repo / ".claude" / "settings.json", {"luau-kb@claude-doctor-market": True})
        self.assertEqual(self.run_check(LUAU), [])

    def test_broken_json_and_toml_are_ignored(self):
        p = self.repo / ".claude" / "settings.json"
        p.parent.mkdir()
        p.write_text("{nope", encoding="utf-8")
        (self.repo / "coderag.toml").write_text("[[packs", encoding="utf-8")
        self.assertEqual(self.run_check(WEB), ["PACK-MISSING"])

    def test_no_coderag_warns_once(self):
        listing(self.repo, "web-security", "luau-kb")
        settings(self.repo / ".claude" / "settings.json", {KEY: True, "luau-kb@claude-doctor-market": True})
        self.assertEqual(self.run_check({"web": ["x"], "luau": ["y"]}, coderag_bin=False), ["PACK-NO-CODERAG"])

    def test_coderag_plugin_without_binary_warns_without_packs(self):
        settings(self.home / "settings.json", {"coderag@coderag-market": True})
        self.assertEqual(self.run_check({}, coderag_bin=False), ["SET-CODERAG-BINARY"])
        self.got.clear()
        self.assertEqual(self.run_check({}), [])
        self.got.clear()
        listing(self.repo, "web-security")
        settings(self.repo / ".claude" / "settings.json", {KEY: True})
        self.assertEqual(self.run_check(WEB, coderag_bin=False), ["PACK-NO-CODERAG"], "팩이 켜져 있으면 한 번만")

    def test_no_coderag_silent_without_packs(self):
        self.assertEqual(self.run_check({}, coderag_bin=False), [])

    def test_non_executable_coderag_warns(self):
        self.bin.chmod(0o644)
        listing(self.repo, "web-security")
        settings(self.repo / ".claude" / "settings.json", {KEY: True})
        self.assertEqual(self.run_check(WEB), ["PACK-NO-CODERAG"])

    def test_scan_wiring(self):
        (self.repo / "package.json").write_text(json.dumps({"dependencies": {"react": "1"}}), encoding="utf-8")
        env = {**os.environ, "CLAUDE_CONFIG_DIR": str(self.home)}
        out = subprocess.run([sys.executable, "-I", str(DOCTOR / "scan.py"), str(self.repo), "--json", "--only", "7"],
                             capture_output=True, text=True, env=env, timeout=100, stdin=subprocess.DEVNULL)
        codes = [f["code"] for f in json.loads(out.stdout)["findings"]]
        self.assertIn("PACK-MISSING", codes, out.stdout + out.stderr)


if __name__ == "__main__":
    unittest.main()
