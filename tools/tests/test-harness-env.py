"""home/.claude/lib/harness_env.py 의 층 읽기 테스트. 실행: python3 -I tools/tests/test-harness-env.py  (모델 호출 없음)

층: DEFAULTS < 사용자 harness.env < 저장소 .claude/harness.env < 저장소 .claude/harness.local.env < 환경 변수.
"""
import importlib.util
import os
import shutil
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
        self.local("HARNESS_WORKSPACE=/elsewhere\nHARNESS_WORKSPACE_GATE=off\nSESSION_LOG_CLAUDE=evil\n")
        v = he.load_layers(self.proj)
        self.assertEqual((v["HARNESS_HEAVY_WRAP"], v["HARNESS_WORKSPACE"]), ("choom -n 1000 --", "/ws"))
        self.assertNotIn("HARNESS_WORKSPACE_GATE", v)
        self.assertNotIn("SESSION_LOG_CLAUDE", v)
        self.assertEqual(v["HARNESS_FANOUT_WARN_CONCURRENT"], "2", "다른 키는 덮는다")

    def test_repo_layers_cannot_set_delegate_gates(self):
        # 위임 드라이버의 실행 파일, 인증 위치, 격리 게이트, 동시 실행 한도. 모델 이름과 더 거를 비밀 이름은 저장소가 정해도 된다.
        gates = {
            "HARNESS_DELEGATE_AGY_BIN": "/evil/agy", "HARNESS_DELEGATE_CODEX_BIN": "/evil/codex",
            "HARNESS_DELEGATE_AGY_HOME": "/evil", "HARNESS_DELEGATE_CODEX_HOME": "/evil",
            "HARNESS_DELEGATE_AGY_WORKTREE": "sandbox", "HARNESS_DELEGATE_AGY_UNISOLATED": "allow",
            "HARNESS_DELEGATE_CODEX_SANDBOX": "danger-full-access",
            "HARNESS_DELEGATE_KEEP_ENV": "1", "HARNESS_DELEGATE_STATE": "/evil", "HARNESS_DELEGATE_MAX_CONCURRENT": "99",
        }
        free = {"HARNESS_DELEGATE_AGY_MODEL": "m1", "HARNESS_DELEGATE_CODEX_MODEL": "m2", "HARNESS_DELEGATE_SECRET_GLOBS": "*.x"}
        self.repo("".join(f"{k}={v}\n" for k, v in list(gates.items())[:5]) + "".join(f"{k}={v}\n" for k, v in free.items()))
        self.local("".join(f"{k}={v}\n" for k, v in list(gates.items())[5:]))
        v = he.load_layers(self.proj)
        for k in gates:
            self.assertEqual(v[k], he.expand(he.DEFAULTS[k], {}), k)
        for k, want in free.items():
            self.assertEqual(v[k], want, k)

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


class Installed(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="harness-env-inst-"))
        self.saved = os.environ.get("CLAUDE_CONFIG_DIR")
        os.environ["CLAUDE_CONFIG_DIR"] = str(self.tmp / "cfg")
        (self.tmp / "cfg" / "lib").mkdir(parents=True)
        (self.tmp / "plug").mkdir()
        shutil.copy(CANON, self.tmp / "plug" / "harness_env.py")
        self.copy = load_canon(self.tmp / "plug" / "harness_env.py", "harness_env_plugin_copy")

    def tearDown(self):
        if self.saved is None:
            os.environ.pop("CLAUDE_CONFIG_DIR", None)
        else:
            os.environ["CLAUDE_CONFIG_DIR"] = self.saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_falls_back_to_own_copy(self):
        self.assertIs(self.copy.installed().load_layers, self.copy.load_layers, "설치된 lib 가 없다")
        (self.tmp / "cfg" / "lib" / "harness_env.py").write_text("def load(c=(), defaults=None):\n    return {}\n")
        self.assertIs(self.copy.installed().load_layers, self.copy.load_layers, "load_layers 가 없는 옛 판")
        (self.tmp / "cfg" / "lib" / "harness_env.py").write_text("raise RuntimeError\n")
        self.assertIs(self.copy.installed().load_layers, self.copy.load_layers, "깨진 판")

    def test_prefers_installed_canon(self):
        shutil.copy(CANON, self.tmp / "cfg" / "lib" / "harness_env.py")
        mod = self.copy.installed()
        self.assertIsNot(mod.load_layers, self.copy.load_layers)
        self.assertEqual(Path(mod.__file__), self.tmp / "cfg" / "lib" / "harness_env.py")


if __name__ == "__main__":
    unittest.main()
