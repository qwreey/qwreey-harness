"""플러그인 userConfig 시험. 실행: python3 -I tools/tests/test-plugin-userconfig.py  (모델 호출 없음)

plugins/*/.claude-plugin/plugin.json 과 packs/*/.claude-plugin/plugin.json 의 userConfig 항목마다 본다:
- 키는 소문자 식별자이고, 그 대문자(harness_reply_language 는 HARNESS_REPLY_LANGUAGE)가 그 플러그인 코드에 있다.
  harness_env 사본은 옵션 키의 대문자를 환경 변수 이름으로 읽으므로, 코드에 없는 키는 대화상자에만 있고 아무도 읽지 않는다.
- type, title, description 이 있다(claude plugin validate 가 요구한다). type 은 Claude Code 가 받는 다섯 가지 가운데 하나다.
- default 는 코드 기본값과 같다: 그 플러그인 코드의 최상위 *DEFAULTS 리터럴(로더 사본의 DEFAULTS 포함)에 있으면 그 값, 없으면 빈 값.
  /config 에 보이는 기본값과 옵션을 건드리지 않았을 때 도는 값이 어긋나지 않게 한다(설정하지 않은 옵션은 settings.json 에 없다).
- claude 가 PATH 에 있으면 모든 플러그인(userConfig 가 없어도)에 claude plugin validate 가 exit 0.
"""
import ast
import concurrent.futures
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
TYPES = {"string", "number", "boolean", "directory", "file"}  # claude plugin validate 2.1.316 이 받는 값
KEY = re.compile(r"^[a-z][a-z0-9_]*$")
ENV_KEY = re.compile(r"^[A-Z][A-Z0-9]*(_[A-Z0-9]+)+$")
DEFAULTS_NAME = re.compile(r"(^|_)DEFAULTS$")
# 코드로 보지 않는 곳: 시험, 문서, 매니페스트. 문서에만 적힌 키는 읽는 코드가 아니다.
SKIP_PARTS = {"tests", "docs", ".claude-plugin", "__pycache__", "node_modules"}
CODE_SUFFIXES = {".py", ".sh", ".js", ".mjs", ".ts", ".tsx", ".json", ".luau", ".lua", ".ps1"}


def plugin_dirs():
    return sorted(p.parent.parent for p in list((ROOT / "plugins").glob("*/.claude-plugin/plugin.json"))
                  + list((ROOT / "packs").glob("*/.claude-plugin/plugin.json")))


def code_files(plugin):
    for p in sorted(plugin.rglob("*")):
        rel = p.relative_to(plugin)
        if p.is_file() and p.suffix in CODE_SUFFIXES and not (set(rel.parts) & SKIP_PARTS):
            yield p


def code_defaults(plugin):
    """{환경 변수 이름: 기본값 문자열}: 플러그인 .py 파일 최상위의 *DEFAULTS dict 가운데 키가 모두 환경 변수 꼴인 것."""
    out = {}
    for p in code_files(plugin):
        if p.suffix != ".py":
            continue
        try:
            tree = ast.parse(p.read_text(encoding="utf-8"), str(p))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for n in tree.body:
            if not (isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name)):
                continue
            if not (DEFAULTS_NAME.search(n.targets[0].id) and isinstance(n.value, ast.Dict)):
                continue
            try:
                d = ast.literal_eval(n.value)
            except ValueError:
                continue
            if d and all(isinstance(k, str) and ENV_KEY.match(k) for k in d):
                out.update({k: str(v) for k, v in d.items()})
    # lib/ambient.py 는 플러그인마다 같은 사본이라 스위치 이름을 context/ambient.json 에서 받고, 기본값 on 을 넘긴다.
    try:
        sw = json.loads((plugin / "context" / "ambient.json").read_text(encoding="utf-8")).get("off_switch")
    except (OSError, ValueError, AttributeError):
        sw = None
    if isinstance(sw, str) and ENV_KEY.match(sw):
        out.setdefault(sw, "on")
    return out


def as_env(v):
    """userConfig default 를 코드가 받는 문자열로(harness_env.option_value 와 같은 변환, ~ 는 풀지 않고 비교한다)."""
    if isinstance(v, bool):
        return "on" if v else "off"
    if isinstance(v, (int, float)):
        return str(int(v)) if isinstance(v, float) and v.is_integer() else str(v)
    if isinstance(v, list):
        return ";".join(as_env(x) for x in v)
    return "" if v is None else str(v)


def problems(plugin):
    """plugin 폴더의 userConfig 문제 [문장]. userConfig 가 없으면 []."""
    try:
        manifest = json.loads((plugin / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return ["plugin.json: %s" % e]
    uc = manifest.get("userConfig")
    if uc is None:
        return []
    if not isinstance(uc, dict):
        return ["userConfig is not an object"]
    out = []
    text = None
    defaults = None
    for key, spec in uc.items():
        where = "userConfig.%s" % key
        if not KEY.match(key):
            out.append("%s: key must be lowercase letters, digits, _ (the lowercase env name)" % where)
        if not isinstance(spec, dict):
            out.append("%s: not an object" % where)
            continue
        if spec.get("type") not in TYPES:
            out.append("%s: type %r not in %s" % (where, spec.get("type"), sorted(TYPES)))
        for field in ("title", "description"):
            if not (isinstance(spec.get(field), str) and spec[field].strip()):
                out.append("%s: %s missing" % (where, field))
        env = key.upper()
        if text is None:
            text = "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in code_files(plugin))
            defaults = code_defaults(plugin)
        if not re.search(r"\b%s\b" % re.escape(env), text):
            out.append("%s: no code in the plugin reads %s" % (where, env))
        want = defaults.get(env, "")
        got = as_env(spec.get("default")) if "default" in spec else ""
        if got != want:
            src = "a *DEFAULTS entry" if env in defaults else "no *DEFAULTS entry (so empty)"
            out.append("%s: default %r differs from the code default %r (%s)" % (where, got, want, src))
    return out


def claude_bin():
    exe = shutil.which("claude")
    if not exe:
        return None
    try:
        ok = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=60).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        ok = False
    return exe if ok else None


class UserConfig(unittest.TestCase):
    def test_every_plugin(self):
        dirs = plugin_dirs()
        self.assertGreater(len(dirs), 5, "plugin.json 찾기가 동작하지 않는다")
        for d in dirs:
            with self.subTest(plugin=str(d.relative_to(ROOT))):
                self.assertEqual(problems(d), [])

    def test_claude_plugin_validate(self):
        exe = claude_bin()
        if not exe:
            self.skipTest("claude 가 PATH 에 없다")

        def run(d):
            p = subprocess.run([exe, "plugin", "validate", str(d)], capture_output=True, text=True, timeout=120)
            return d, p.returncode, p.stdout + p.stderr

        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
            for d, rc, out in pool.map(run, plugin_dirs()):
                with self.subTest(plugin=str(d.relative_to(ROOT))):
                    self.assertEqual(rc, 0, out[-2000:])


class SelfTest(unittest.TestCase):
    """가짜 플러그인으로 검사가 문제를 잡는지 본다(지금 userConfig 를 가진 플러그인이 없어도 검사가 살아 있게)."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="userconfig-"))
        self.plugin = self.tmp / "fake"
        (self.plugin / ".claude-plugin").mkdir(parents=True)
        (self.plugin / "hooks").mkdir()
        (self.plugin / "tests").mkdir()
        (self.plugin / "hooks" / "fake.py").write_text(
            'FAKE_DEFAULTS = {"HARNESS_FAKE_MODE": "warn", "HARNESS_FAKE_ON": "on", "HARNESS_FAKE_N": "3"}\n'
            'paths = env.get("HARNESS_FAKE_PATHS", "")\n', encoding="utf-8")
        # 시험과 문서에만 있는 키는 읽는 코드가 아니다.
        (self.plugin / "tests" / "t.py").write_text('X = "HARNESS_FAKE_ORPHAN"\n', encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def manifest(self, user_config):
        data = {"name": "fake", "version": "0.1.0", "description": "x"}
        if user_config is not None:
            data["userConfig"] = user_config
        (self.plugin / ".claude-plugin" / "plugin.json").write_text(json.dumps(data), encoding="utf-8")

    def ok(self, **kw):
        return dict({"type": "string", "title": "t", "description": "d"}, **kw)

    def test_no_user_config(self):
        self.manifest(None)
        self.assertEqual(problems(self.plugin), [])

    def test_good_entries(self):
        self.manifest({
            "harness_fake_mode": self.ok(default="warn", options=["warn", "off"]),
            "harness_fake_on": self.ok(type="boolean", default=True),
            "harness_fake_n": self.ok(type="number", default=3),
            "harness_fake_paths": self.ok(),
        })
        self.assertEqual(problems(self.plugin), [])

    def test_bad_entries(self):
        self.manifest({
            "HARNESS_FAKE_MODE": self.ok(default="warn"),
            "harness_fake_on": self.ok(type="boolean", default=False),
            "harness_fake_n": {"type": "number", "default": 3},
            "harness_fake_paths": self.ok(type="list", default="x"),
            "harness_fake_orphan": self.ok(),
        })
        got = "\n".join(problems(self.plugin))
        self.assertIn("userConfig.HARNESS_FAKE_MODE: key must be lowercase", got)
        self.assertIn("userConfig.harness_fake_on: default 'off' differs from the code default 'on'", got)
        self.assertIn("userConfig.harness_fake_n: title missing", got)
        self.assertIn("userConfig.harness_fake_n: description missing", got)
        self.assertIn("userConfig.harness_fake_paths: type 'list'", got)
        self.assertIn("userConfig.harness_fake_paths: default 'x' differs from the code default '' (no *DEFAULTS entry", got)
        self.assertIn("userConfig.harness_fake_orphan: no code in the plugin reads HARNESS_FAKE_ORPHAN", got)

    def test_validate_catches_missing_fields(self):
        exe = claude_bin()
        if not exe:
            self.skipTest("claude 가 PATH 에 없다")
        self.manifest({"harness_fake_mode": {"type": "string", "title": "t"}})
        p = subprocess.run([exe, "plugin", "validate", str(self.plugin)], capture_output=True, text=True, timeout=120)
        self.assertNotEqual(p.returncode, 0, "validate 가 description 없는 항목을 받았다: 이 시험의 전제가 바뀌었다")


if __name__ == "__main__":
    unittest.main()
