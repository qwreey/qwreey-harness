"""home/.claude/lib/harness_env.py 의 층 읽기 테스트. 실행: python3 -I tools/tests/test-harness-env.py  (모델 호출 없음)

층: DEFAULTS < 사용자 harness.env < 플러그인 옵션(settings.json pluginConfigs) < 저장소 .claude/harness.env < 저장소 .claude/harness.local.env < 환경 변수.
"""
import importlib.util
import json
import os
import shutil
import signal
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CANON = ROOT / "home" / ".claude" / "lib" / "harness_env.py"


def load_canon(path=CANON, name="harness_env_under_test"):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


he = load_canon()


def within(seconds, fn):
    """fn() 의 값. seconds 안에 끝나지 않으면(FIFO 에서 멈춤) 멈추지 않고 실패한다."""
    def timed_out(signum, frame):
        raise AssertionError("did not return within %d s (blocked on a FIFO?)" % seconds)
    old = signal.signal(signal.SIGALRM, timed_out)
    signal.alarm(seconds)
    try:
        return fn()
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)


class Layers(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="harness-env-"))
        self.cfg = self.tmp / "cfg"
        self.proj = self.tmp / "proj"
        self.cfg.mkdir()
        (self.proj / ".claude").mkdir(parents=True)
        self.saved = dict(os.environ)
        for k in list(os.environ):
            if k.startswith(("HARNESS_", "DEMO_")) or k in ("CLAUDE_PROJECT_DIR", "CLAUDE_CONFIG_DIR"):
                del os.environ[k]
        os.environ["CLAUDE_CONFIG_DIR"] = str(self.cfg)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.saved)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write(self, rel, text):
        p = self.tmp / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return p

    def user(self, text):
        return self.write("cfg/harness.env", text)

    def repo(self, text):
        return self.write("proj/.claude/harness.env", text)

    def local(self, text):
        return self.write("proj/.claude/harness.local.env", text)

    def test_each_layer_overrides_the_one_below(self):
        self.assertEqual(he.load_layers(self.proj)["HARNESS_TOOLKITS"], "", "기본값")
        self.user("HARNESS_TOOLKITS=user\nDEMO_A=user\nDEMO_B=user\n")
        self.assertEqual(he.load_layers(self.proj)["HARNESS_TOOLKITS"], "user")
        self.repo("HARNESS_TOOLKITS=repo\nDEMO_A=repo\n")
        v = he.load_layers(self.proj)
        self.assertEqual((v["HARNESS_TOOLKITS"], v["DEMO_A"], v["DEMO_B"]), ("repo", "repo", "user"), "키마다 합친다")
        self.local("HARNESS_TOOLKITS=local\n")
        v = he.load_layers(self.proj)
        self.assertEqual((v["HARNESS_TOOLKITS"], v["DEMO_A"], v["DEMO_B"]), ("local", "repo", "user"), "local 이 저장소를 이긴다")
        os.environ["HARNESS_TOOLKITS"] = "env"
        os.environ["DEMO_B"] = "env"
        v = he.load_layers(self.proj)
        self.assertEqual((v["HARNESS_TOOLKITS"], v["DEMO_B"]), ("env", "env"), "환경 변수가 모두를 이긴다")

    def test_local_without_repo_file(self):
        self.user("DEMO_A=user\n")
        self.local("DEMO_A=local\n")
        self.assertEqual(he.load_layers(self.proj)["DEMO_A"], "local")

    def test_empty_value_in_higher_layer_wins(self):
        self.user("DEMO_A=off\n")
        self.local("DEMO_A=\n")
        self.assertEqual(he.load_layers(self.proj)["DEMO_A"], "")

    def test_missing_files(self):
        v = he.load_layers(self.proj)
        self.assertEqual((v["_file"], v["_files"]), ("", ""))
        self.assertEqual(v["HARNESS_HEAVY_WRAP"], "auto")
        v = he.load_layers(self.tmp / "nowhere")
        self.assertEqual(v["_files"], "")

    def test_fifo_layers_are_skipped(self):
        """FIFO 인 harness.env(사용자, 저장소)는 열지 않고 그 층이 없는 것으로 본다. 다른 층은 그대로 읽는다."""
        os.mkfifo(self.cfg / "harness.env")
        os.mkfifo(self.proj / ".claude" / "harness.env")
        local = self.local("DEMO_X=local\n")
        v = within(5, lambda: he.load_layers(self.proj))
        self.assertEqual((v["_file"], v["_files"], v.get("DEMO_X")), ("", str(local), "local"))

        # is_file 로 고른 뒤 FIFO 로 바뀐 층 파일도 열지 않는다
        self.assertFalse(within(5, lambda: he._read({}, self.cfg / "harness.env")))

    def test_files_listed_low_to_high(self):
        u, r, l = self.user("A=1\n"), self.repo("A=2\n"), self.local("A=3\n")
        v = he.load_layers(self.proj)
        self.assertEqual(v["_file"], str(u))
        self.assertEqual(v["_files"].split(" "), [str(u), str(r), str(l)])

    def test_project_from_environment_or_cwd(self):
        self.repo("DEMO_A=repo\n")
        self.assertNotIn("DEMO_A", he.load_layers(), "저장소를 모르면 저장소 층이 없다")
        self.assertNotIn("DEMO_A", he.load_layers(""), "빈 값은 저장소 층 없음")
        self.assertEqual(he.load_layers(he.project_dir(str(self.proj)))["DEMO_A"], "repo", "CLAUDE_PROJECT_DIR 이 없으면 cwd")
        other = self.tmp / "other"
        (other / ".claude").mkdir(parents=True)
        os.environ["CLAUDE_PROJECT_DIR"] = str(self.proj)
        self.assertEqual(he.load_layers()["DEMO_A"], "repo")
        self.assertEqual(he.project_dir(str(other)), self.proj, "CLAUDE_PROJECT_DIR 이 cwd 를 이긴다")

    def test_harness_env_replaces_only_the_user_layer(self):
        self.user("DEMO_A=user\nDEMO_B=user\n")
        alt = self.write("alt.env", "DEMO_A=alt\n")
        self.repo("DEMO_C=repo\n")
        os.environ["HARNESS_ENV"] = str(alt)
        v = he.load_layers(self.proj)
        self.assertEqual((v.get("DEMO_A"), v.get("DEMO_B"), v.get("DEMO_C")), ("alt", None, "repo"))
        self.assertEqual(v["_file"], str(alt))
        os.environ["HARNESS_ENV"] = str(self.tmp / "missing.env")
        self.assertEqual(he.load_layers(self.proj)["DEMO_A"], "user", "없는 HARNESS_ENV 는 기본 위치로 물러난다")

    def test_repo_layers_cannot_set_user_only_keys(self):
        self.user("HARNESS_HEAVY_WRAP=choom -n 1000 --\nHARNESS_WORKSPACE=/ws\n")
        self.repo("HARNESS_HEAVY_WRAP=evil\nHARNESS_FANOUT_WARN_CONCURRENT=2\n")
        self.local("HARNESS_WORKSPACE=/elsewhere\nHARNESS_CODERAG=/evil\n")
        v = he.load_layers(self.proj)
        self.assertEqual((v["HARNESS_HEAVY_WRAP"], v["HARNESS_WORKSPACE"]), ("choom -n 1000 --", "/ws"))
        self.assertEqual(v["HARNESS_CODERAG"], "coderag", "저장소 층의 /evil 이 아니라 기본값")
        self.assertEqual(v["HARNESS_FANOUT_WARN_CONCURRENT"], "2", "다른 키는 덮는다")

    def test_blocked_repo_values_do_not_leak_through_references(self):
        # 막힌 줄은 같은 파일의 $NAME 에도 들어가지 않는다. $NAME 은 아래 층(사용자, 기본값, 환경 변수)의 값을 본다.
        self.user("HARNESS_HEAVY_WRAP=nice -n 5\n")
        self.repo("HARNESS_HEAVY_WRAP=evil\nDEMO_LEAK=$HARNESS_HEAVY_WRAP\nHARNESS_CODERAG=/evil\nDEMO_CR=${HARNESS_CODERAG}\n"
                  "DEMO_GATE=off\nDEMO_G=$DEMO_GATE\nHARNESS_WORKSPACE=/evil\nDEMO_WS=$HARNESS_WORKSPACE\n")
        os.environ["HARNESS_WORKSPACE"] = "/env-ws"
        v = he.load_layers(self.proj, user_only={"DEMO_GATE"})
        self.assertEqual((v["DEMO_LEAK"], v["DEMO_CR"], v["DEMO_G"], v["DEMO_WS"]), ("nice -n 5", "coderag", "", "/env-ws"))
        self.assertEqual(he.load_layers(self.proj)["DEMO_G"], "off", "막지 않은 키는 같은 파일에서 그대로 쓴다")

    def test_caller_user_only_keys(self):
        # 한 플러그인만 읽는 사용자 전용 키는 그 플러그인이 user_only 로 넘긴다. 넘기지 않은 호출은 막지 않는다.
        self.user("DEMO_GATE=on\n")
        self.repo("DEMO_GATE=off\nDEMO_FREE=repo\n")
        self.local("DEMO_NEW=evil\n")
        v = he.load_layers(self.proj, user_only={"DEMO_GATE", "DEMO_NEW"})
        self.assertEqual((v["DEMO_GATE"], v["DEMO_FREE"]), ("on", "repo"))
        self.assertNotIn("DEMO_NEW", v)
        self.assertEqual(he.load_layers(self.proj)["DEMO_GATE"], "off")
        self.assertNotIn("DEMO_GATE", he.USER_ONLY, "호출자 키가 모듈 표에 새지 않는다")

    def test_caller_defaults(self):
        v = he.load_layers(self.proj, defaults={"DEMO_HOME": "~/x", "HARNESS_TOOLKITS": "luau"})
        self.assertEqual(v["DEMO_HOME"], os.path.expanduser("~/x"), "호출자 기본값의 ~ 도 푼다")
        self.assertEqual(v["HARNESS_TOOLKITS"], "luau", "호출자 기본값이 모듈 기본값을 이긴다")
        self.user("DEMO_HOME=/u\n")
        self.assertEqual(he.load_layers(self.proj, defaults={"DEMO_HOME": "~/x"})["DEMO_HOME"], "/u")
        os.environ["DEMO_HOME"] = "/env"
        self.assertEqual(he.load_layers(self.proj, defaults={"DEMO_HOME": "~/x"})["DEMO_HOME"], "/env")

    def test_references_see_lower_layers(self):
        self.user("HARNESS_WORKSPACE=/ws\n")
        self.local("DEMO_A=${HARNESS_WORKSPACE}/x\n")
        self.assertEqual(he.load_layers(self.proj)["DEMO_A"], "/ws/x")

    def test_project_inside_config_parent_is_read_once(self):
        # 저장소가 ~ 이면 ~/.claude/harness.env 가 사용자 층이자 저장소 층이다. 사용자 층으로 한 번만 읽는다.
        os.environ["CLAUDE_CONFIG_DIR"] = str(self.tmp / ".claude")
        f = self.write(".claude/harness.env", "HARNESS_WORKSPACE=/ws\n")
        v = he.load_layers(self.tmp)
        self.assertEqual((v["_files"], v["HARNESS_WORKSPACE"]), (str(f), "/ws"))

    def test_load_reads_only_the_user_layer(self):
        self.user("DEMO_A=user\n")
        self.repo("DEMO_A=repo\n")
        os.environ["CLAUDE_PROJECT_DIR"] = str(self.proj)
        v = he.load([self.cfg / "harness.env"])
        self.assertEqual((v["DEMO_A"], v["_file"]), ("user", str(self.cfg / "harness.env")))

    def test_retired_location_keys(self):
        # 옛 위치 키는 기본값이 없지만 저장소 층은 여전히 막고, 환경 변수는 지금처럼 결과에 들어온다.
        self.assertNotIn("HARNESS_WORKSPACE", he.DEFAULTS)
        self.assertNotIn("HARNESS_DOCTOR_ROOT", he.DEFAULTS)
        self.assertNotIn("HARNESS_WORKSPACE", he.USER_ONLY)
        self.assertNotIn("HARNESS_WORKSPACE", he.load_layers(self.proj), "설정이 없으면 키도 없다(호출자는 .get 으로 읽는다)")
        self.repo("HARNESS_WORKSPACE=/evil\nHARNESS_DOCTOR_ROOT=/evil\n")
        self.assertNotIn("HARNESS_DOCTOR_ROOT", he.load_layers(self.proj), "저장소 층은 옛 위치 키를 정하지 못한다")
        os.environ["HARNESS_DOCTOR_ROOT"] = "/env"
        self.assertEqual(he.load_layers(self.proj)["HARNESS_DOCTOR_ROOT"], "/env")


class PluginOptions(unittest.TestCase):
    """플러그인 옵션 층: 사본 위치에서 찾은 plugin.json 의 userConfig 키만 settings.json pluginConfigs 에서 읽는다."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="harness-env-opt-"))
        self.cfg = self.tmp / "cfg"
        self.proj = self.tmp / "proj"
        self.cfg.mkdir()
        (self.proj / ".claude").mkdir(parents=True)
        self.saved = dict(os.environ)
        for k in list(os.environ):
            if k.startswith(("HARNESS_", "DEMO_")) or k in ("CLAUDE_PROJECT_DIR", "CLAUDE_CONFIG_DIR", "HOME"):
                del os.environ[k]
        os.environ["CLAUDE_CONFIG_DIR"] = str(self.cfg)
        os.environ["HOME"] = str(self.tmp / "home")
        self.mod = self.plugin("demo", {"demo_mode": {}, "demo_flag": {}, "demo_n": {}, "demo_paths": {}, "harness_toolkits": {}})

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.saved)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def plugin(self, name, user_config, sub="hooks", depth=None):
        """가짜 플러그인 폴더에 로더 사본을 두고 그 사본을 읽는다. sub 는 사본이 놓일 플러그인 안 경로."""
        root = self.tmp / "plugins" / name
        (root / ".claude-plugin").mkdir(parents=True, exist_ok=True)
        manifest = {"name": name, "version": "0.1.0", "description": "x"}
        if user_config is not None:
            manifest["userConfig"] = {k: dict({"type": "string", "title": k, "description": k}, **v) for k, v in user_config.items()}
        (root / ".claude-plugin" / "plugin.json").write_text(json.dumps(manifest), encoding="utf-8")
        (root / sub).mkdir(parents=True, exist_ok=True)
        shutil.copy(CANON, root / sub / "harness_env.py")
        return load_canon(root / sub / "harness_env.py", "harness_env_" + name + "_" + sub.replace("/", "_"))

    def settings(self, configs, enabled=None):
        data = {"pluginConfigs": {pid: {"options": opts} for pid, opts in configs.items()}}
        if enabled is not None:
            data["enabledPlugins"] = enabled
        (self.cfg / "settings.json").write_text(json.dumps(data), encoding="utf-8")

    def test_layer_order(self):
        # DEFAULTS < 사용자 harness.env < 플러그인 옵션 < 저장소 < 저장소 local < 환경 변수
        m = self.mod
        self.assertEqual(m.load_layers(self.proj, defaults={"DEMO_MODE": "base"})["DEMO_MODE"], "base")
        (self.cfg / "harness.env").write_text("DEMO_MODE=user\nDEMO_FLAG=user\n", encoding="utf-8")
        self.assertEqual(m.load_layers(self.proj)["DEMO_MODE"], "user")
        self.settings({"demo@mkt": {"demo_mode": "option"}})
        v = m.load_layers(self.proj)
        self.assertEqual((v["DEMO_MODE"], v["DEMO_FLAG"], v["_options"]), ("option", "user", "demo@mkt"), "옵션이 사용자 harness.env 를 이긴다")
        (self.proj / ".claude" / "harness.env").write_text("DEMO_MODE=repo\n", encoding="utf-8")
        self.assertEqual(m.load_layers(self.proj)["DEMO_MODE"], "repo", "저장소 층이 옵션을 이긴다")
        (self.proj / ".claude" / "harness.local.env").write_text("DEMO_MODE=local\n", encoding="utf-8")
        self.assertEqual(m.load_layers(self.proj)["DEMO_MODE"], "local")
        os.environ["DEMO_MODE"] = "env"
        self.assertEqual(m.load_layers(self.proj)["DEMO_MODE"], "env", "환경 변수가 모두를 이긴다")
        del os.environ["DEMO_MODE"]
        (self.proj / ".claude" / "harness.env").unlink()
        (self.proj / ".claude" / "harness.local.env").unlink()
        os.environ["DEMO_MODE"] = "env"
        self.assertEqual(m.load_layers(self.proj)["DEMO_MODE"], "env", "저장소 층이 없어도 환경 변수가 옵션을 이긴다")

    def test_repo_layers_cannot_override_user_only_options(self):
        m = self.mod
        self.settings({"demo@mkt": {"demo_mode": "option", "harness_toolkits": "luau"}})
        (self.proj / ".claude" / "harness.env").write_text("DEMO_MODE=repo\nHARNESS_TOOLKITS=web\n", encoding="utf-8")
        v = m.load_layers(self.proj, user_only={"DEMO_MODE"})
        self.assertEqual((v["DEMO_MODE"], v["HARNESS_TOOLKITS"]), ("option", "web"))

    def test_references_in_repo_layer_see_options(self):
        self.settings({"demo@mkt": {"demo_mode": "option"}})
        (self.proj / ".claude" / "harness.env").write_text("DEMO_X=${DEMO_MODE}/x\n", encoding="utf-8")
        self.assertEqual(self.mod.load_layers(self.proj)["DEMO_X"], "option/x")

    def test_value_conversion(self):
        self.settings({"demo@mkt": {"demo_flag": True, "demo_mode": False, "demo_n": 3, "demo_paths": ["~/a", "b"]}})
        v = self.mod.load_layers(self.proj)
        home = str(self.tmp / "home")
        self.assertEqual((v["DEMO_FLAG"], v["DEMO_MODE"], v["DEMO_N"], v["DEMO_PATHS"]), ("on", "off", "3", home + "/a;b"))
        self.settings({"demo@mkt": {"demo_n": 2.5, "demo_paths": "~/a;~/b;c", "demo_mode": None, "demo_flag": {"x": 1}}})
        v = self.mod.load_layers(self.proj)
        self.assertEqual((v["DEMO_N"], v["DEMO_PATHS"]), ("2.5", home + "/a;" + home + "/b;c"))
        self.assertNotIn("DEMO_MODE", v, "null 은 설정하지 않은 것과 같다")
        self.assertNotIn("DEMO_FLAG", v, "객체 값은 쓰지 않는다")
        self.assertEqual(he.option_value(4.0), "4")
        self.assertEqual(he.option_value("$HOME/x"), "$HOME/x", "$NAME 은 풀지 않는다")

    def test_undeclared_keys_are_ignored(self):
        self.settings({"demo@mkt": {"demo_mode": "ok", "demo_left_over": "x", "HARNESS_HEAVY_WRAP": "evil", "harness_heavy_wrap": "evil"}})
        v = self.mod.load_layers(self.proj)
        self.assertEqual(v["DEMO_MODE"], "ok")
        self.assertNotIn("DEMO_LEFT_OVER", v)
        self.assertEqual(v["HARNESS_HEAVY_WRAP"], "auto", "선언하지 않은 키는 다른 플러그인 키라도 읽지 않는다")

    def test_name_lookup(self):
        # 사본이 플러그인 안 깊은 곳(skills/<이름>/scripts)에 있어도 위로 올라가 plugin.json 을 찾는다.
        deep = self.plugin("deep", {"demo_mode": {}}, sub="skills/deep/scripts")
        self.assertEqual(deep.plugin_manifest(), ("deep", frozenset({"DEMO_MODE"})))
        self.settings({"deep@mkt": {"demo_mode": "deep"}, "demo@mkt": {"demo_mode": "demo"}})
        self.assertEqual(deep.load_layers(self.proj)["DEMO_MODE"], "deep", "자기 이름의 옵션만 읽는다")
        self.assertEqual(self.mod.load_layers(self.proj)["DEMO_MODE"], "demo")
        # 5단계보다 깊으면 찾지 않는다.
        far = self.plugin("far", {"demo_mode": {}}, sub="a/b/c/d/e")
        self.assertIsNone(far.plugin_manifest())
        self.assertNotIn("DEMO_MODE", far.load_layers(self.proj))
        # plugin.json 이 없는 곳(~/.claude/lib 설치본)은 이 층이 없다.
        (self.tmp / "lib").mkdir()
        shutil.copy(CANON, self.tmp / "lib" / "harness_env.py")
        bare = load_canon(self.tmp / "lib" / "harness_env.py", "harness_env_bare")
        self.assertIsNone(bare.plugin_manifest())
        self.assertEqual(bare.load_layers(self.proj)["_options"], "")

    def test_plugin_without_user_config(self):
        none = self.plugin("plain", None)
        self.assertEqual(none.plugin_manifest(), ("plain", frozenset()))
        self.settings({"plain@mkt": {"demo_mode": "x"}})
        v = none.load_layers(self.proj)
        self.assertEqual((v.get("DEMO_MODE"), v["_options"]), (None, ""))

    def test_missing_or_broken_settings(self):
        self.assertEqual(self.mod.load_layers(self.proj)["_options"], "", "settings.json 이 없어도 돈다")
        (self.cfg / "settings.json").write_text("{not json", encoding="utf-8")
        self.assertEqual(self.mod.load_layers(self.proj)["_options"], "")
        (self.cfg / "settings.json").write_text('{"pluginConfigs": {"demo@mkt": "x"}}', encoding="utf-8")
        self.assertEqual(self.mod.load_layers(self.proj)["_options"], "")
        (self.cfg / "settings.json").write_text('{"pluginConfigs": {"demo@mkt": {"options": ["x"]}}}', encoding="utf-8")
        self.assertNotIn("DEMO_MODE", self.mod.load_layers(self.proj))

    def test_fifo_settings_is_unreadable(self):
        """FIFO 인 settings.json 은 쓰는 쪽을 기다리지 않고 없는 것처럼 본다(예전에는 open 에서 멈췄다)."""
        os.mkfifo(self.cfg / "settings.json")
        v = within(5, lambda: self.mod.load_layers(self.proj))
        self.assertEqual((v["_options"], v.get("DEMO_MODE")), ("", None))

    def test_several_marketplaces(self):
        self.settings({"demo@a": {"demo_mode": "a"}, "demo@b": {"demo_mode": "b"}, "demox@c": {"demo_mode": "c"}})
        self.assertEqual(self.mod.load_layers(self.proj)["DEMO_MODE"], "a", "켠 것이 없으면 id 이름순 첫째")
        self.settings({"demo@a": {"demo_mode": "a"}, "demo@b": {"demo_mode": "b"}}, enabled={"demo@a": False, "demo@b": True})
        v = self.mod.load_layers(self.proj)
        self.assertEqual((v["DEMO_MODE"], v["_options"]), ("b", "demo@b"), "enabledPlugins 에서 켠 것")
        self.settings({"demo@old": {"demo_mode": "old"}}, enabled={"demo@old": False, "demo@new": True})
        v = self.mod.load_layers(self.proj)
        self.assertEqual(("DEMO_MODE" in v, v["_options"]), (False, ""), "켠 사본이 설정 전이면 꺼진 옛 사본의 값을 쓰지 않는다")

    def test_settings_change_is_seen_in_one_process(self):
        self.settings({"demo@mkt": {"demo_mode": "one"}})
        self.assertEqual(self.mod.load_layers(self.proj)["DEMO_MODE"], "one")
        self.settings({"demo@mkt": {"demo_mode": "second"}})
        self.assertEqual(self.mod.load_layers(self.proj)["DEMO_MODE"], "second", "크기가 바뀌면 다시 읽는다")

    def test_other_plugin_options_for_shared_modules(self):
        # 공용 모듈(known_repos)은 다른 플러그인의 옵션을 키를 넘겨 읽는다. 자기 플러그인 옵션이 겹치면 이긴다.
        self.settings({"other@mkt": {"demo_mode": "other", "demo_extra": "x"}, "demo@mkt": {"demo_flag": True}})
        v = self.mod.load_layers(self.proj, options={"other": {"DEMO_MODE", "DEMO_EXTRA"}})
        self.assertEqual((v["DEMO_MODE"], v["DEMO_EXTRA"], v["DEMO_FLAG"]), ("other", "x", "on"))
        self.assertEqual(v["_options"].split(), ["other@mkt", "demo@mkt"])
        self.settings({"other@mkt": {"demo_mode": "other"}, "demo@mkt": {"demo_mode": "own"}})
        self.assertEqual(self.mod.load_layers(self.proj, options={"other": {"DEMO_MODE"}})["DEMO_MODE"], "own")


if __name__ == "__main__":
    unittest.main()
