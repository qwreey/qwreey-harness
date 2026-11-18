"""qwreey-delegate 드라이버의 설정 층과 USER_ONLY 방어 시험. 실행: python3 -I tools/tests/test-delegate-config.py

- 저장소 층(.claude/harness.env, harness.local.env)은 실행 파일·인증 위치·격리 게이트·동시 실행 한도·uid 대역을 바꾸지 못하고
  모델과 setup 줄은 바꾼다. setup 줄은 드라이버 환경으로 $NAME 을 풀지 않는다.
- 드라이버는 늘 자기 옆 harness_env.py 사본을 쓴다. 설치된 ~/.claude/lib/harness_env.py 가 드라이버 키를 모르는 옛 판이어도 같다.
- 비밀 점검 경로와 상태 폴더는 고정 /code 가 아니라 HOME 과 설정 디렉터리에서 나온다.
모델 호출 없음, 다른 uid 로 실행 없음.
"""
import importlib.util
import json
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from delegate_fixture import CANON_HE, SCRIPTS, Fixture  # noqa: E402

sys.path.insert(0, str(SCRIPTS))
import delegate  # noqa: E402
import delegate_agents as agents  # noqa: E402
import delegate_isolation as iso  # noqa: E402
import delegate_workspace as ws  # noqa: E402

# 위임 드라이버 설계 문서 설정 표의 USER_ONLY 열(예, 아니오). 드라이버의 ENV_USER_ONLY 와 공용 USER_ONLY 를 합쳐 맞춰 본다.
USER_ONLY_YES = {
    "HARNESS_DELEGATE_UIDS", "HARNESS_TOOL_INSTALLS", "HARNESS_HEAVY_WRAP", "HARNESS_DELEGATE_AGY_BIN",
    "HARNESS_DELEGATE_CODEX_BIN", "HARNESS_DELEGATE_AGY_HOME", "HARNESS_DELEGATE_CODEX_HOME",
    "HARNESS_DELEGATE_AGY_WORKTREE", "HARNESS_DELEGATE_AGY_UNISOLATED", "HARNESS_DELEGATE_CODEX_SANDBOX", "HARNESS_DELEGATE_KEEP_ENV",
    "HARNESS_DELEGATE_STATE", "HARNESS_DELEGATE_MAX_CONCURRENT", "HARNESS_DELEGATE_RUNS_DAYS",
}
USER_ONLY_NO = {"HARNESS_DELEGATE_AGY_MODEL", "HARNESS_DELEGATE_CODEX_MODEL", "HARNESS_DELEGATE_SECRET_GLOBS",
                "HARNESS_DELEGATE_SETUP"}


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


canon = load(CANON_HE, "harness_env_canon")


class Env(unittest.TestCase):
    def setUp(self):
        self.f = Fixture()
        self.saved = dict(os.environ)
        os.environ.clear()
        os.environ.update(self.f.env())

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.saved)
        self.f.cleanup()

    def repo_layer(self, text, local=False):
        p = self.f.repo / ".claude" / ("harness.local.env" if local else "harness.env")
        p.parent.mkdir(exist_ok=True)
        p.write_text(text)

    def install(self, text):
        lib = self.f.cfg / "lib"
        lib.mkdir(exist_ok=True)
        (lib / "harness_env.py").write_text(text)


class Keys(unittest.TestCase):
    def test_user_only_matches_design_table(self):
        user_only = delegate.ENV_USER_ONLY | (canon.USER_ONLY & set(delegate.SHARED_KEYS))
        self.assertEqual(user_only, USER_ONLY_YES)
        self.assertFalse(USER_ONLY_NO & (delegate.ENV_USER_ONLY | canon.USER_ONLY), "더하기만 되거나 격리와 무관한 키는 저장소가 정해도 된다")
        self.assertEqual(set(delegate.KEYS), USER_ONLY_YES | USER_ONLY_NO, "드라이버가 읽는 키 = 설계 표의 키")

    def test_shared_keys_come_from_the_loader(self):
        for k in delegate.SHARED_KEYS:
            self.assertIn(k, canon.DEFAULTS, k)
            self.assertNotIn(k, delegate.ENV_DEFAULTS, f"{k}: 공용 키는 로더가 정한다")

    def test_driver_defaults(self):
        d = delegate.ENV_DEFAULTS
        self.assertEqual(d["HARNESS_DELEGATE_MAX_CONCURRENT"], "1")
        self.assertEqual(d["HARNESS_DELEGATE_AGY_WORKTREE"], "uid")
        self.assertEqual(d["HARNESS_DELEGATE_AGY_HOME"], "~/.gemini")
        self.assertEqual(d["HARNESS_DELEGATE_AGY_UNISOLATED"], "", "격리 없는 agy 는 기본으로 꺼짐")
        self.assertEqual(canon.DEFAULTS["HARNESS_DELEGATE_UIDS"], "61000-61015")
        self.assertEqual(ws.parse_uid_range(canon.DEFAULTS["HARNESS_DELEGATE_UIDS"]), (61000, 61015))


class Layers(Env):
    def test_repo_layers_cannot_open_user_only_keys(self):
        self.repo_layer("HARNESS_DELEGATE_AGY_BIN=/evil/agy\nHARNESS_DELEGATE_CODEX_SANDBOX=danger-full-access\n"
                        "HARNESS_DELEGATE_AGY_MODEL=repo-model\nHARNESS_DELEGATE_SECRET_GLOBS=*.secret\n")
        self.repo_layer("HARNESS_DELEGATE_MAX_CONCURRENT=99\nHARNESS_DELEGATE_KEEP_ENV=1\nHARNESS_DELEGATE_AGY_UNISOLATED=allow\n"
                        "HARNESS_DELEGATE_AGY_HOME=/evil\nHARNESS_DELEGATE_UIDS=0-0\n", local=True)
        ctx = delegate.Ctx()
        cfg = ctx.layers(str(self.f.repo))
        self.assertEqual(cfg["HARNESS_DELEGATE_AGY_BIN"], str(self.f.bin / "agy"))
        self.assertEqual(cfg["HARNESS_DELEGATE_CODEX_SANDBOX"], "")
        self.assertEqual(cfg["HARNESS_DELEGATE_MAX_CONCURRENT"], "1")
        self.assertEqual(cfg["HARNESS_DELEGATE_KEEP_ENV"], "")
        self.assertEqual(cfg["HARNESS_DELEGATE_AGY_UNISOLATED"], "")
        self.assertEqual(cfg["HARNESS_DELEGATE_AGY_HOME"], str(self.f.home / ".gemini"))
        self.assertEqual(cfg["HARNESS_DELEGATE_UIDS"], f"{self.f.first_uid}-{self.f.last_uid}")
        self.assertEqual(ctx.uid_range(), (self.f.first_uid, self.f.last_uid))
        self.assertEqual((cfg["HARNESS_DELEGATE_AGY_MODEL"], cfg["HARNESS_DELEGATE_SECRET_GLOBS"]), ("repo-model", "*.secret"))

    def test_environment_and_user_layer_win(self):
        os.environ["HARNESS_DELEGATE_MAX_CONCURRENT"] = "3"
        self.repo_layer("HARNESS_DELEGATE_CODEX_MODEL=repo\n")
        os.environ["HARNESS_DELEGATE_CODEX_MODEL"] = "env"
        cfg = delegate.Ctx().layers(str(self.f.repo))
        self.assertEqual((cfg["HARNESS_DELEGATE_MAX_CONCURRENT"], cfg["HARNESS_DELEGATE_CODEX_MODEL"]), ("3", "env"))

    def test_uid_range_is_read_without_repo_layers(self):
        # 대역은 저장소를 찾기 전에 사용자 층으로 읽는다. 저장소 층이 USER_ONLY 를 무시하는 판이어도 닿지 않게.
        self.repo_layer("HARNESS_DELEGATE_UIDS=0-0\n")
        os.chdir(self.f.repo)
        try:
            self.assertEqual(delegate.Ctx().uid_range(), (self.f.first_uid, self.f.last_uid))
        finally:
            os.chdir(self.f.tmp)

    def test_setup_line_from_repo_layers_unexpanded(self):
        self.assertEqual(delegate.setup_line(str(self.f.repo)), "")
        self.repo_layer("HARNESS_DELEGATE_SETUP=echo $HOME > a\n")
        self.assertEqual(delegate.setup_line(str(self.f.repo)), "echo $HOME > a", "드라이버 환경으로 풀지 않는다")
        self.repo_layer("HARNESS_DELEGATE_SETUP='make deps'  # 주석\n", local=True)
        self.assertEqual(delegate.setup_line(str(self.f.repo)), "make deps", "harness.local.env 가 이긴다")
        self.assertEqual(delegate.Ctx().layers(str(self.f.repo))["HARNESS_DELEGATE_SETUP"], "make deps")
        os.environ["HARNESS_DELEGATE_SETUP"] = "from env"
        self.assertEqual(delegate.setup_line(str(self.f.repo)), "from env", "환경 변수가 이긴다")

    def test_run_end_to_end_uses_user_bin_and_repo_model(self):
        self.repo_layer("HARNESS_DELEGATE_AGY_BIN=/evil/agy\nHARNESS_DELEGATE_AGY_MODEL=repo-model\n")
        p = self.f.drive("run", "agy", "t1", self.f.prompt, "--mode", "empty")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("model: repo-model", (self.f.out("t1") / "meta.txt").read_text())


class PluginOptions(Env):
    """/plugin configure 가 settings.json 에 쓴 옵션(pluginConfigs)이 드라이버에 닿는지. 드라이버는 Bash 로 부르므로
    CLAUDE_PLUGIN_OPTION_* 가 아니라 옆 사본의 settings.json 층으로만 받는다."""

    def options(self, **opts):
        data = {"pluginConfigs": {"qwreey-delegate@test-market": {"options": opts}}}
        (self.f.cfg / "settings.json").write_text(json.dumps(data))

    def test_options_reach_the_driver(self):
        self.options(harness_delegate_agy_model="opt-model", harness_delegate_uids="63000-63003",
                     harness_delegate_state="/undeclared")
        ctx = delegate.Ctx()
        self.assertEqual(ctx.uid_range(), (63000, 63003), "옵션이 사용자 harness.env 보다 이긴다")
        self.assertEqual(ctx.cfg["HARNESS_DELEGATE_AGY_MODEL"], "opt-model")
        self.assertEqual(ctx.cfg["HARNESS_DELEGATE_STATE"], "", "userConfig 에 없는 키는 읽지 않는다")
        self.repo_layer("HARNESS_DELEGATE_AGY_MODEL=repo-model\nHARNESS_DELEGATE_UIDS=1-2\n")
        cfg = ctx.layers(str(self.f.repo))
        self.assertEqual(cfg["HARNESS_DELEGATE_AGY_MODEL"], "repo-model", "모델은 저장소 층이 이긴다")
        self.assertEqual(cfg["HARNESS_DELEGATE_UIDS"], "63000-63003", "대역은 저장소 층이 바꾸지 못한다")

    def test_no_table_option_left(self):
        manifest = json.loads((SCRIPTS.parents[2] / ".claude-plugin" / "plugin.json").read_text())
        self.assertNotIn("harness_delegate_registry", manifest["userConfig"])
        self.assertEqual(manifest["userConfig"]["harness_delegate_uids"]["default"], canon.DEFAULTS["HARNESS_DELEGATE_UIDS"])
        self.assertFalse((SCRIPTS.parent / "registry.tsv").exists(), "uid 표는 없어졌다")


class InstalledModule(Env):
    def test_old_installed_module_is_not_used(self):
        # 위임 키를 모르는 옛 정본을 흉내 낸다: 저장소 층을 막지 않는다.
        self.install(CANON_HE.read_text() + "\nUSER_ONLY = frozenset()\nRETIRED_USER_ONLY = frozenset()\nLEGACY_USER_ONLY = frozenset()\n")
        self.repo_layer("HARNESS_DELEGATE_AGY_BIN=/evil/agy\nHARNESS_DELEGATE_UIDS=0-0\n")
        old = load(self.f.cfg / "lib" / "harness_env.py", "old_installed")
        self.assertEqual(old.load_layers(str(self.f.repo))["HARNESS_DELEGATE_AGY_BIN"], "/evil/agy",
                         "옛 판만으로는 저장소가 실행 파일을 바꾼다(드라이버가 자기 사본을 쓰는 이유)")
        cfg = delegate.Ctx().layers(str(self.f.repo))
        self.assertEqual(cfg["HARNESS_DELEGATE_AGY_BIN"], str(self.f.bin / "agy"))
        self.assertEqual(cfg["HARNESS_DELEGATE_UIDS"], f"{self.f.first_uid}-{self.f.last_uid}")
        p = self.f.drive("doctor")
        self.assertIn(f"INFO harness_env {SCRIPTS / 'harness_env.py'}", p.stdout)


class Paths(Env):
    def test_secret_paths_come_from_home_and_config_dir(self):
        got = iso.secret_paths(Path.home(), delegate.harness_env.config_dir())
        self.assertEqual(got, [self.f.cfg / ".credentials.json", self.f.home / ".git-credentials", self.f.home / ".ssh"])

    def test_state_dir(self):
        self.assertEqual(ws.default_state_dir(), self.f.home / ".local" / "state" / "qwreey-delegate")
        os.environ["XDG_STATE_HOME"] = str(self.f.tmp / "xdg")
        self.assertEqual(ws.default_state_dir(), self.f.tmp / "xdg" / "qwreey-delegate")

    def test_credentials_default_from_home(self):
        cfg = delegate.Ctx().layers("")
        self.assertEqual(agents.ADAPTERS["agy"].credentials(cfg), self.f.home / ".gemini")
        self.assertEqual(agents.ADAPTERS["codex"].credentials(cfg), self.f.home / ".codex" / "auth.json")
        os.environ["CODEX_HOME"] = str(self.f.tmp / "ch")
        self.assertEqual(agents.ADAPTERS["codex"].credentials(cfg), self.f.tmp / "ch" / "auth.json")

    def test_find_bin(self):
        tmp = self.f.tmp
        shims = tmp / "mise" / "shims"
        shims.mkdir(parents=True)
        for p in (shims / "agy", tmp / "inst" / "antigravity-cli" / "latest" / "agy"):
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("#!/bin/sh\n")
            p.chmod(0o755)
        os.environ["PATH"] = f"{shims}:/usr/bin:/bin"
        self.assertEqual(agents.find_bin("", "agy", str(tmp / "inst"), "antigravity-cli/latest/agy"),
                         str(tmp / "inst" / "antigravity-cli" / "latest" / "agy"), "shim 은 건너뛰고 설치 경로로")
        self.assertIsNone(agents.find_bin(str(tmp / "nope"), "agy", str(tmp / "inst"), "antigravity-cli/latest/agy"),
                          "설정한 경로가 없으면 다른 곳을 찾지 않는다")
        os.environ["PATH"] = f"{self.f.bin}:/usr/bin:/bin"
        self.assertEqual(agents.find_bin("", "agy", "", "x"), str(self.f.bin / "agy"))


if __name__ == "__main__":
    unittest.main()
