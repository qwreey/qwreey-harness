"""harness.env 키의 주인 시험. 실행: python3 -I tools/tests/test-harness-env-owners.py  (모델 호출 없음)

로더(home/.claude/lib/harness_env.py)는 여러 플러그인이 읽는 키만 정하고, 한 플러그인만 읽는 키는 그 플러그인이 읽는 곳 옆에
`*DEFAULTS`(dict)와 `*USER_ONLY`(frozenset) 로 정해 load_layers(defaults=, user_only=) 로 넘긴다. 여기서 보는 것:
- 같은 키를 두 곳(플러그인 둘, 또는 플러그인과 로더)이 정하면 기본값과 사용자 전용 여부가 같다.
- 키를 나누기 전 로더가 막던 키(MAIN_USER_ONLY)는 지금도 막힌다: 로더 USER_ONLY 와 플러그인 선언만으로(LEGACY_USER_ONLY 를 지워도) 덮는다.
- plugins/, packs/, lib/ 에서 load_layers 를 부르는 파일은 모두 ENTRIES 나 LAYERS_ALLOW 에 있다.
- 플러그인 코드는 설치된 ~/.claude/lib/harness_env.py 를 읽지 않는다(옛 판은 플러그인의 user_only 를 모른다).
- 저장소 층을 막지 않는 옛 로더를 임시 CLAUDE_CONFIG_DIR/lib 에 두어도 각 플러그인의 사용자 전용 키는 저장소 층이 바꾸지 못한다.
- 거꾸로 installed() 로 설치본을 읽는 옛 플러그인에 새 로더를 설치해도 MAIN_USER_ONLY 는 저장소 층이 바꾸지 못한다(LEGACY_USER_ONLY).
"""
import ast
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CANON = ROOT / "home" / ".claude" / "lib" / "harness_env.py"
SCAN_DIRS = ("plugins", "packs", "lib", "home")
# harness.env 키는 이름공간이 있다(HARNESS_..., SESSION_LOG_...). 키가 모두 이 꼴인 dict 만 선언으로 본다:
# 접두를 뗀 키를 쓰는 표(statusline 의 DEFAULTS)나 소문자 설정 표는 harness.env 키가 아니다.
ENV_KEY = re.compile(r"^[A-Z][A-Z0-9]*(_[A-Z0-9]+)+$")
DEFAULTS_NAME = re.compile(r"(^|_)DEFAULTS$")
USER_ONLY_NAME = re.compile(r"(^|_)USER_ONLY$")
# 설치된 로더를 읽는 코드의 흔적. statusline 처럼 home/ 에서 함께 설치되는 스크립트만 읽어도 된다.
READS_INSTALLED = re.compile(r"\.installed\(|[\"']lib[\"']\s*/\s*[\"']harness_env\.py|lib/harness_env\.py[\"']")

# 키를 나누기 전(main) 로더의 USER_ONLY 전부. 고정한 기대값이라 로더나 플러그인에서 키가 빠지면 아래 시험이 잡는다.
MAIN_USER_ONLY = frozenset({
    "HARNESS_WORKSPACE", "HARNESS_DOCTOR_ROOT", "HARNESS_TOOL_INSTALLS", "HARNESS_HEAVY_WRAP", "HARNESS_DELEGATE_REGISTRY",
    "HARNESS_AGENT_PUSH", "HARNESS_CODERAG", "HARNESS_LUAU_KB", "HARNESS_ROBLOX_DOCS_CACHE", "HARNESS_WORKSPACE_GATE",
    "SESSION_LOG_HOME", "SESSION_LOG_CLAUDE",
    "HARNESS_DELEGATE_AGY_BIN", "HARNESS_DELEGATE_CODEX_BIN", "HARNESS_DELEGATE_AGY_HOME", "HARNESS_DELEGATE_CODEX_HOME",
    "HARNESS_DELEGATE_AGY_WORKTREE", "HARNESS_DELEGATE_AGY_UNISOLATED", "HARNESS_DELEGATE_CODEX_SANDBOX", "HARNESS_DELEGATE_KEEP_ENV",
    "HARNESS_DELEGATE_STATE", "HARNESS_DELEGATE_MAX_CONCURRENT", "HARNESS_DELEGATE_RUNS_DAYS",
})
# 로더를 부르는 곳이 없는 키: packs/luau-kb/tools/roblox_docs.py 가 사용자 harness.env 만 자기 파서로 읽어 저장소 층이 애초에 없다.
# HARNESS_DELEGATE_REGISTRY 는 읽는 곳이 없다(위임은 uid 대역 HARNESS_DELEGATE_UIDS 를 쓴다). 옛 플러그인을 위해 LEGACY_USER_ONLY 가 막는다.
NO_LOADER_CALLER = frozenset({"HARNESS_ROBLOX_DOCS_CACHE", "HARNESS_DELEGATE_REGISTRY"})

# 플러그인마다 harness.env 를 읽는 입구:
# (이름, 스크립트 디렉터리, out 을 만드는 코드, 사용자 전용 키를 선언한 파일 또는 None, load_layers 를 부르는 파일).
ENTRIES = [
    ("qwreey-workspace", "plugins/qwreey-workspace/scripts", "import wslib; out = wslib.load_env(PROJ)",
     "plugins/qwreey-workspace/scripts/wslib.py", "plugins/qwreey-workspace/scripts/wslib.py"),
    ("qwreey-delegate", "plugins/qwreey-delegate/skills/delegate/scripts", "import delegate; out = delegate.config(PROJ)",
     "plugins/qwreey-delegate/skills/delegate/scripts/delegate.py", "plugins/qwreey-delegate/skills/delegate/scripts/delegate.py"),
    ("qwreey-proc-guard", "plugins/qwreey-proc-guard/hooks", "out = load('heavy-proc-guard.py').load_env(PROJ)", None,
     "plugins/qwreey-proc-guard/hooks/heavy-proc-guard.py"),
    ("qwreey-proc-guard resource-guard", "plugins/qwreey-proc-guard/hooks", "out = load('resource-guard.py').load_env(PROJ)",
     "plugins/qwreey-proc-guard/hooks/resource-guard.py", "plugins/qwreey-proc-guard/hooks/resource-guard.py"),
    ("qwreey-conventions structure-reminder", "plugins/qwreey-conventions/hooks", "out = load('structure-reminder.py').harness_env()",
     "plugins/qwreey-conventions/hooks/structure-reminder.py", "plugins/qwreey-conventions/hooks/structure-reminder.py"),
    ("qwreey-conventions conv_env", "plugins/qwreey-conventions/hooks", "import conv_env; out = conv_env._layers()",
     "plugins/qwreey-conventions/hooks/conv_env.py",
     "plugins/qwreey-conventions/hooks/conv_env.py"),
    ("qwreey-reply-language", "plugins/qwreey-reply-language/hooks", "import reply_env; out = reply_env._layers()",
     "plugins/qwreey-reply-language/hooks/reply_env.py", "plugins/qwreey-reply-language/hooks/reply_env.py"),
    ("qwreey-sessions", "plugins/qwreey-sessions/scripts", "from sllib import config; out = config.load()",
     "plugins/qwreey-sessions/scripts/sllib/config.py", "plugins/qwreey-sessions/scripts/sllib/config.py"),
    ("q doctor", "plugins/q/skills/doctor/scripts", "import scan; out = scan.ENV", "plugins/q/skills/doctor/scripts/scan.py",
     "plugins/q/skills/doctor/scripts/scan.py"),
    ("q subagent_ledger", "plugins/q/scripts", "import subagent_ledger; out = subagent_ledger.config(PROJ)", None,
     "plugins/q/scripts/subagent_ledger.py"),
    ("qwreey-workspace known_repos", "plugins/qwreey-workspace/scripts", "import known_repos; out = known_repos.options()",
     "plugins/qwreey-workspace/scripts/known_repos.py", "plugins/qwreey-workspace/scripts/known_repos.py"),
    ("qwreey-conventions known_repos", "plugins/qwreey-conventions/hooks", "import known_repos; out = known_repos.options()",
     "plugins/qwreey-conventions/hooks/known_repos.py", "plugins/qwreey-conventions/hooks/known_repos.py"),
]
# ENTRIES 가 사본을 시험하는 lib/ 정본. 정본 옆에는 harness_env 사본이 없어 그 자리에서 돌릴 수 없다.
CANON_OF_ENTRIES = frozenset({"lib/known_repos.py"})
# ENTRIES 밖에서 load_layers 를 부르는 곳. 저장소 층이 정해도 되는 키(끄기 스위치, 검토 문턱)만 읽어 user_only 를 넘기지 않는다.
# 새 호출자는 여기나 ENTRIES 에 넣어야 시험이 통과한다: 사용자 전용 키를 읽는다면 ENTRIES 에 넣고 user_only 를 넘긴다.
LAYERS_ALLOW = frozenset({
    "lib/ambient.py", "plugins/q/scripts/ambient.py", "plugins/qwreey-advisor/hooks/ambient.py",
    "plugins/qwreey-operator/hooks/ambient.py", "plugins/qwreey-workspace/scripts/ambient.py",
    "plugins/qwreey-advisor/hooks/second-opinion-nudge.py", "plugins/qwreey-operator/hooks/subagent-bg-tasks.py",
    "plugins/qwreey-operator/hooks/delegate-nudge.py",
    "plugins/q/scripts/drift.py", "plugins/q/scripts/stale_work.py",
})

RUNNER = """
import importlib.util, json, sys
sys.path.insert(0, {here!r})
def load(name):
    spec = importlib.util.spec_from_file_location("entry_under_test", {here!r} + "/" + name)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m
PROJ = {proj!r}
{code}
print(json.dumps({{k: v for k, v in out.items() if isinstance(v, str)}}))
"""


def literal_set(node, where="?"):
    if isinstance(node, ast.Call) and getattr(node.func, "id", "") in ("frozenset", "set") and not node.keywords:
        if not node.args:
            return set()
        if len(node.args) == 1:
            node = node.args[0]
    try:
        return set(ast.literal_eval(node))
    except (ValueError, TypeError, SyntaxError):
        raise AssertionError(f"{where}: 사용자 전용 키 선언은 리터럴(frozenset({{...}}), {{...}}, frozenset())이어야 시험이 읽는다")


def top_assigns(path):
    """이 파일 최상위의 `이름 = 값` 들: [(이름, 값 노드)]."""
    tree = ast.parse(path.read_text(encoding="utf-8"), str(path))
    return [(n.targets[0].id, n.value) for n in tree.body
            if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name)]


def legacy_user_only():
    """로더의 LEGACY_USER_ONLY: 옛 플러그인을 위한 막음이라 로더 자기 키 선언으로 세지 않는다."""
    found = [v for name, v in top_assigns(CANON) if name == "LEGACY_USER_ONLY"]
    return literal_set(found[0], str(CANON)) if found else set()


def declarations(path):
    """(defaults {키: 값}, user_only {키}) : 이 파일 최상위의 harness.env 키 선언."""
    defaults, user_only = {}, set()
    for name, value in top_assigns(path):
        if name == "LEGACY_USER_ONLY":
            continue
        if DEFAULTS_NAME.search(name) and isinstance(value, ast.Dict):
            keys = [k.value if isinstance(k, ast.Constant) else None for k in value.keys]
            if keys and all(isinstance(k, str) and ENV_KEY.match(k) for k in keys):
                defaults.update(ast.literal_eval(value))
        elif USER_ONLY_NAME.search(name):
            keys = literal_set(value, f"{path}:{name}")
            if keys and all(isinstance(k, str) and ENV_KEY.match(k) for k in keys):
                user_only |= keys
    return defaults, user_only


def source_files():
    for d in SCAN_DIRS:
        for p in sorted((ROOT / d).rglob("*.py")):
            rel = p.relative_to(ROOT)
            if "tests" in rel.parts or "__pycache__" in rel.parts:
                continue
            yield rel, p


def all_declarations():
    """{저장소 기준 경로: (defaults, user_only)}. 로더 사본은 정본 하나로 센다."""
    out = {}
    for rel, p in source_files():
        if p.name == "harness_env.py" and p != CANON:
            continue
        d, u = declarations(p)
        if d or u:
            out[str(rel)] = (d, u)
    return out


class Declarations(unittest.TestCase):
    def setUp(self):
        self.decl = all_declarations()

    def test_scanner_finds_the_owners(self):
        for rel in ["home/.claude/lib/harness_env.py"] + [e[3] for e in ENTRIES if e[3]] + [
                "plugins/qwreey-proc-guard/hooks/heavy-proc-guard.py", "plugins/q/scripts/subagent_ledger.py"]:
            self.assertIn(rel, self.decl, f"{rel}: 선언을 찾지 못했다(이름이 *DEFAULTS, *USER_ONLY 인 최상위 리터럴이어야 한다)")

    def test_shared_keys_agree(self):
        seen = {}
        for rel, (d, u) in self.decl.items():
            for k in set(d) | u:
                seen.setdefault(k, []).append((rel, d.get(k), k in u))
        for k, sites in seen.items():
            if len(sites) < 2:
                continue
            self.assertEqual(len({s[2] for s in sites}), 1, f"{k}: 사용자 전용 여부가 다르다: {sites}")
            self.assertLessEqual(len({s[1] for s in sites if s[1] is not None}), 1, f"{k}: 기본값이 다르다: {sites}")

    def test_plugin_redeclares_loader_keys_identically(self):
        # 플러그인이 로더 키를 다시 적을 수는 있지만 값과 사용자 전용 여부가 로더와 같아야 한다(옛 로더 사본을 쓰는 곳의 기본값이 어긋나지 않게).
        # LEGACY_USER_ONLY 는 로더 선언으로 세지 않으므로 그 키를 플러그인이 사용자 전용으로 정하는 것은 겹침이 아니다.
        d, u = self.decl["home/.claude/lib/harness_env.py"]
        for rel, (pd, pu) in self.decl.items():
            if not rel.startswith("plugins/"):
                continue
            for k in (set(pd) | pu) & (set(d) | u):
                self.assertEqual(k in pu, k in u, f"{rel}: {k} 의 사용자 전용 여부가 로더와 다르다")
                if k in pd:
                    self.assertIn(k, d, f"{rel}: 로더에 기본값이 없는 {k} 에 기본값을 정한다")
                    self.assertEqual(pd[k], d[k], f"{rel}: {k} 의 기본값이 로더와 다르다")

    def test_main_user_only_still_blocked(self):
        loader_u = self.decl["home/.claude/lib/harness_env.py"][1]
        plugins_u = set().union(*(u for rel, (_, u) in self.decl.items() if rel.startswith("plugins/")))
        legacy = legacy_user_only()
        self.assertFalse(MAIN_USER_ONLY - (loader_u | legacy | plugins_u), "옛 로더가 막던 키가 이제 막히지 않는다")
        self.assertEqual(legacy, MAIN_USER_ONLY - loader_u, "LEGACY_USER_ONLY 는 옛 로더 USER_ONLY 에서 지금 로더 USER_ONLY 를 뺀 것이다")
        # LEGACY_USER_ONLY 를 지워도 막히도록 각 키는 지금 로더나 그 키를 읽는 플러그인이 사용자 전용으로 정해야 한다.
        missing = MAIN_USER_ONLY - NO_LOADER_CALLER - (loader_u | plugins_u)
        self.assertFalse(missing, f"{sorted(missing)}: 로더도 플러그인도 사용자 전용으로 정하지 않는다(LEGACY_USER_ONLY 에만 기댄다)")


def load_layers_callers():
    """plugins/, packs/, lib/ 에서 load_layers(...) 를 부르는 시험 밖 파일(저장소 기준 경로)."""
    out = set()
    for rel, p in source_files():
        if rel.parts[0] not in ("plugins", "packs", "lib"):
            continue
        tree = ast.parse(p.read_text(encoding="utf-8"), str(p))
        for n in ast.walk(tree):
            if isinstance(n, ast.Call) and (getattr(n.func, "attr", None) == "load_layers" or getattr(n.func, "id", None) == "load_layers"):
                out.add(str(rel))
                break
    return out


class Callers(unittest.TestCase):
    def test_every_caller_is_listed(self):
        callers = load_layers_callers()
        self.assertIn("plugins/qwreey-sessions/scripts/sllib/config.py", callers, "호출 찾기가 동작하지 않는다")
        listed = {e[4] for e in ENTRIES} | LAYERS_ALLOW | CANON_OF_ENTRIES
        self.assertFalse(callers - listed, f"{sorted(callers - listed)}: load_layers 를 부르지만 ENTRIES 에도 LAYERS_ALLOW 에도 없다")
        self.assertFalse(listed - callers, f"{sorted(listed - callers)}: 목록에 있지만 load_layers 를 부르지 않는다")


class LiteralSet(unittest.TestCase):
    def test_empty_and_bad_literals(self):
        val = lambda src: ast.parse(src).body[0].value
        self.assertEqual(literal_set(val("frozenset()")), set())
        self.assertEqual(literal_set(val("set()")), set())
        self.assertEqual(literal_set(val('frozenset({"A_B"})')), {"A_B"})
        with self.assertRaises(AssertionError):
            literal_set(val("frozenset(x)"))


class NoInstalledLoader(unittest.TestCase):
    def test_plugin_code_uses_its_own_copy(self):
        for rel, p in source_files():
            if rel.parts[0] == "home" or p.name == "harness_env.py":
                continue
            self.assertIsNone(READS_INSTALLED.search(p.read_text(encoding="utf-8")), f"{rel}: 설치된 harness_env 를 읽는다")


class OldInstalledLoader(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="harness-env-owners-"))
        self.cfg, self.proj, self.home = self.tmp / "cfg", self.tmp / "proj", self.tmp / "home"
        (self.cfg / "lib").mkdir(parents=True)
        (self.proj / ".claude").mkdir(parents=True)
        self.home.mkdir()
        decl = all_declarations()
        self.loader_user_only = decl["home/.claude/lib/harness_env.py"][1]
        self.user_only = set().union(*(u for _, u in decl.values()))
        # 저장소 층을 막지 않는 옛 로더. 플러그인이 이것을 읽으면 아래 값이 evil 이 된다.
        (self.cfg / "lib" / "harness_env.py").write_text(
            CANON.read_text(encoding="utf-8") + "\nUSER_ONLY = frozenset()\nRETIRED_USER_ONLY = frozenset()\nLEGACY_USER_ONLY = frozenset()\n", encoding="utf-8")
        (self.cfg / "harness.env").write_text("".join(f"{k}=user-{k}\n" for k in sorted(self.user_only)), encoding="utf-8")
        evil = "".join(f"{k}=evil\n" for k in sorted(self.user_only))
        (self.proj / ".claude" / "harness.env").write_text(evil, encoding="utf-8")
        (self.proj / ".claude" / "harness.local.env").write_text(evil, encoding="utf-8")
        self.env = {k: v for k, v in os.environ.items()
                    if not k.startswith(("HARNESS_", "SESSION_LOG_", "CLAUDE_")) and k not in ("HOME", "XDG_CONFIG_HOME")}
        self.env.update(HOME=str(self.home), CLAUDE_CONFIG_DIR=str(self.cfg), CLAUDE_PROJECT_DIR=str(self.proj))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_old_loader_alone_lets_the_repo_win(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("old_loader", self.cfg / "lib" / "harness_env.py")
        old = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(old)
        self.assertEqual(old.load_layers(str(self.proj))["HARNESS_WORKSPACE"], "evil", "옛 로더 흉내가 막지 않아야 시험이 뜻이 있다")

    def test_each_plugin_keeps_its_user_only_keys(self):
        for name, here, code, decl_file, _ in ENTRIES:
            with self.subTest(name):
                src = RUNNER.format(here=str(ROOT / here), proj=str(self.proj), code=code)
                p = subprocess.run([sys.executable, "-I", "-c", src], capture_output=True, text=True, env=self.env,
                                   cwd=self.proj, timeout=60)
                self.assertEqual(p.returncode, 0, p.stderr)
                out = json.loads(p.stdout.strip().splitlines()[-1])
                own = declarations(ROOT / decl_file)[1] if decl_file else set()
                self.assertTrue(own <= set(out), f"{name}: 자기 사용자 전용 키 {sorted(own - set(out))} 를 읽지 못했다")
                for k in own | (self.loader_user_only & set(out)):
                    self.assertEqual(out[k], f"user-{k}", f"{name}: 저장소 층이 {k} 를 바꿨다")


# 키를 나누기 전 플러그인의 harness_env.py 사본 가운데 설치본을 고르는 부분(installed() 는 main 판 그대로). 자기 사본으로 떨어지면
# 시험이 뜻을 잃으므로 그 load_layers 는 실패한다.
OLD_PLUGIN_COPY = """
import os
import sys
from pathlib import Path


def config_dir():
    return Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")


def load_layers(project=None, candidates=None, defaults=None):
    raise AssertionError("old plugin fell back to its own copy")


def installed():
    p = config_dir() / "lib" / "harness_env.py"
    try:
        if p.is_file() and p.resolve() != Path(__file__).resolve():
            import importlib.util
            spec = importlib.util.spec_from_file_location("_harness_env_installed", p)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            if hasattr(mod, "load_layers"):
                return mod
    except Exception:
        pass
    me = sys.modules.get(__name__)
    if getattr(me, "load_layers", None) is load_layers:
        return me
    import types
    return types.SimpleNamespace(**{k: v for k, v in globals().items() if not k.startswith("__")})
"""
# main 의 plugins/qwreey-sessions/scripts/sllib/config.py 가 층을 읽던 방식: 옆 사본의 installed() 로 고른 모듈에 user_only 없이.
OLD_PLUGIN_READER = """
import importlib.util, json, sys
spec = importlib.util.spec_from_file_location("_sl_harness_env", {copy!r})
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
he = mod.installed()
out = he.load_layers()
out["_loader"] = he.__file__
print(json.dumps({{k: v for k, v in out.items() if isinstance(v, str)}}))
"""


class NewInstalledLoaderOldPlugin(unittest.TestCase):
    """플러그인 캐시에 옛 판이 남은 채 home-sync apply 로 새 로더가 설치된 경우."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="harness-env-legacy-"))
        self.cfg, self.proj, self.home, self.plugin = (self.tmp / n for n in ("cfg", "proj", "home", "plugin"))
        for d in (self.cfg / "lib", self.proj / ".claude", self.home, self.plugin):
            d.mkdir(parents=True)
        (self.plugin / "harness_env.py").write_text(OLD_PLUGIN_COPY, encoding="utf-8")
        (self.cfg / "harness.env").write_text("".join(f"{k}=user-{k}\n" for k in sorted(MAIN_USER_ONLY)), encoding="utf-8")
        evil = "".join(f"{k}=evil\n" for k in sorted(MAIN_USER_ONLY))
        (self.proj / ".claude" / "harness.env").write_text(evil, encoding="utf-8")
        (self.proj / ".claude" / "harness.local.env").write_text(evil, encoding="utf-8")
        self.env = {k: v for k, v in os.environ.items()
                    if not k.startswith(("HARNESS_", "SESSION_LOG_", "CLAUDE_")) and k not in ("HOME", "XDG_CONFIG_HOME")}
        self.env.update(HOME=str(self.home), CLAUDE_CONFIG_DIR=str(self.cfg), CLAUDE_PROJECT_DIR=str(self.proj))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_old_plugin(self, installed_text):
        installed = self.cfg / "lib" / "harness_env.py"
        installed.write_text(installed_text, encoding="utf-8")
        src = OLD_PLUGIN_READER.format(copy=str(self.plugin / "harness_env.py"))
        p = subprocess.run([sys.executable, "-I", "-c", src], capture_output=True, text=True, env=self.env, cwd=self.proj, timeout=60)
        self.assertEqual(p.returncode, 0, p.stderr)
        out = json.loads(p.stdout.strip().splitlines()[-1])
        self.assertEqual(Path(out["_loader"]).resolve(), installed.resolve(), "옛 플러그인이 설치본을 읽지 않았다")
        return out

    def test_legacy_keys_stay_blocked(self):
        out = self.run_old_plugin(CANON.read_text(encoding="utf-8"))
        for k in sorted(MAIN_USER_ONLY):
            self.assertEqual(out.get(k), f"user-{k}", f"새 설치본을 읽는 옛 플러그인에서 저장소 층이 {k} 를 바꿨다")

    def test_without_the_guard_the_repo_wins(self):
        # 막음을 뺀 새 로더면 저장소 층이 이긴다: 위 시험이 LEGACY_USER_ONLY 를 재고 있다는 확인.
        out = self.run_old_plugin(CANON.read_text(encoding="utf-8") + "\nLEGACY_USER_ONLY = frozenset()\n")
        self.assertEqual(out["SESSION_LOG_CLAUDE"], "evil")


if __name__ == "__main__":
    unittest.main()
