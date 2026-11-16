"""harness.env 키의 주인 시험. 실행: python3 -I tools/tests/test-harness-env-owners.py  (모델 호출 없음)

로더(home/.claude/lib/harness_env.py)는 여러 플러그인이 읽는 키만 정하고, 한 플러그인만 읽는 키는 그 플러그인이 읽는 곳 옆에
`*DEFAULTS`(dict)와 `*USER_ONLY`(frozenset) 로 정해 load_layers(defaults=, user_only=) 로 넘긴다. 여기서 보는 것:
- 같은 키를 두 곳(플러그인 둘, 또는 플러그인과 로더)이 정하면 기본값과 사용자 전용 여부가 같다.
- 플러그인 코드는 설치된 ~/.claude/lib/harness_env.py 를 읽지 않는다(옛 판은 플러그인의 user_only 를 모른다).
- 저장소 층을 막지 않는 옛 로더를 임시 CLAUDE_CONFIG_DIR/lib 에 두어도 각 플러그인의 사용자 전용 키는 저장소 층이 바꾸지 못한다.
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

# 플러그인마다 harness.env 를 읽는 입구: (이름, 스크립트 디렉터리, out 을 만드는 코드, 사용자 전용 키를 선언한 파일 또는 None).
ENTRIES = [
    ("qwreey-workspace", "plugins/qwreey-workspace/scripts", "import wslib; out = wslib.load_env(PROJ)",
     "plugins/qwreey-workspace/scripts/wslib.py"),
    ("qwreey-delegate", "plugins/qwreey-delegate/skills/delegate/scripts", "import delegate; out = delegate.config(PROJ)",
     "plugins/qwreey-delegate/skills/delegate/scripts/delegate.py"),
    ("qwreey-proc-guard", "plugins/qwreey-proc-guard/hooks", "out = load('heavy-proc-guard.py').load_env(PROJ)", None),
    ("qwreey-conventions structure-reminder", "plugins/qwreey-conventions/hooks", "out = load('structure-reminder.py').harness_env()",
     "plugins/qwreey-conventions/hooks/structure-reminder.py"),
    ("qwreey-conventions conv_env", "plugins/qwreey-conventions/hooks", "import conv_env; out = conv_env._layers()", None),
    ("qwreey-sessions", "plugins/qwreey-sessions/scripts", "from sllib import config; out = config.load()",
     "plugins/qwreey-sessions/scripts/sllib/config.py"),
    ("q doctor", "plugins/q/skills/doctor/scripts", "import scan; out = scan.ENV", "plugins/q/skills/doctor/scripts/scan.py"),
    ("q subagent_ledger", "plugins/q/scripts", "import subagent_ledger; out = subagent_ledger.config(PROJ)", None),
]

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


def literal_set(node):
    if isinstance(node, ast.Call) and getattr(node.func, "id", "") in ("frozenset", "set") and len(node.args) == 1:
        node = node.args[0]
    return set(ast.literal_eval(node))


def declarations(path):
    """(defaults {키: 값}, user_only {키}) : 이 파일 최상위의 harness.env 키 선언."""
    tree = ast.parse(path.read_text(encoding="utf-8"), str(path))
    defaults, user_only = {}, set()
    for node in tree.body:
        if not (isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)):
            continue
        name = node.targets[0].id
        if DEFAULTS_NAME.search(name) and isinstance(node.value, ast.Dict):
            keys = [k.value if isinstance(k, ast.Constant) else None for k in node.value.keys]
            if keys and all(isinstance(k, str) and ENV_KEY.match(k) for k in keys):
                defaults.update(ast.literal_eval(node.value))
        elif USER_ONLY_NAME.search(name):
            keys = literal_set(node.value)
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

    def test_loader_keeps_only_shared_keys(self):
        # 로더 키는 여러 플러그인이 읽는 것만. 한 플러그인의 키가 다시 로더로 모이지 않게 플러그인 선언과 겹치지 않는지 본다.
        d, u = self.decl["home/.claude/lib/harness_env.py"]
        for rel, (pd, pu) in self.decl.items():
            if rel.startswith("plugins/"):
                self.assertFalse((set(pd) | pu) & (set(d) | u), f"{rel}: 로더 키를 다시 정한다")


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
        (self.cfg / "lib" / "harness_env.py").write_text(CANON.read_text(encoding="utf-8") + "\nUSER_ONLY = frozenset()\n", encoding="utf-8")
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
        for name, here, code, decl_file in ENTRIES:
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


if __name__ == "__main__":
    unittest.main()
