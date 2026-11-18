#!/usr/bin/env python3
"""doctor 의 위임 uid 대역 검사(DRIFT-UID). 실행: python3 -I test-delegate-uids.py  (exit 0 = 통과, 모델 호출 없음)

HARNESS_DELEGATE_UIDS(사용자 harness.env, qwreey-delegate 옵션) 가 잘못됐거나, 실제 계정(/etc/passwd, /etc/group)과 겹치면
알린다. 검사는 하네스 저장소를 알거나 qwreey-delegate 가 설치됐을 때만 돈다. 저장소 층은 대역을 바꾸지 못한다.
scan.py 를 하위 프로세스로 돌린다.
"""
import ast
import json
import os
import pwd
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCAN = HERE.parent / "scripts" / "scan.py"
ROOT = HERE.parents[4]
DRIVER = ROOT / "plugins" / "qwreey-delegate" / "skills" / "delegate" / "scripts" / "delegate_workspace.py"


def literal(path, name):
    """path 최상위의 `name = <리터럴>` 값."""
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    for n in tree.body:
        if isinstance(n, ast.Assign) and len(n.targets) == 1 and getattr(n.targets[0], "id", None) == name:
            return ast.literal_eval(n.value)
    raise AssertionError(f"{path}: {name} 이 없다")


def free_range(size, start=63500):
    """계정이 없는 연속 uid 대역 (첫, 끝)."""
    import grp
    uid = start
    while True:
        ids = range(uid, uid + size)
        if not any(_exists(pwd.getpwuid, u) or _exists(grp.getgrgid, u) for u in ids):
            return uid, uid + size - 1
        uid += size


def _exists(fn, uid):
    try:
        fn(uid)
        return True
    except KeyError:
        return False


class DelegateUids(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = Path(self.tmp.name)
        self.cfg, self.harness, self.target = t / "cfg", t / "harness", t / "target"
        for d in (self.cfg, self.target / ".claude"):
            d.mkdir(parents=True)
        (self.harness / "home").mkdir(parents=True)
        (self.harness / "home" / "MANIFEST").write_text("harness.env\n", encoding="utf-8")
        (self.harness / ".claude-plugin").mkdir()
        (self.harness / ".claude-plugin" / "marketplace.json").write_text("{}", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def findings(self, uids=None, gate=True, repo_layer=None, option=None):
        """DRIFT-UID 찾음의 msg 목록. uids 는 사용자 harness.env 값, option 은 qwreey-delegate 옵션 값."""
        (self.cfg / "harness.env").write_text(f"HARNESS_DELEGATE_UIDS={uids}\n" if uids is not None else "", encoding="utf-8")
        opts = {"harness_delegate_uids": option} if option is not None else {}
        data = {"pluginConfigs": {"qwreey-delegate@m": {"options": opts}}}
        (self.cfg / "settings.json").write_text(json.dumps(data), encoding="utf-8")
        line = f"HARNESS_DELEGATE_UIDS={repo_layer}\n" if repo_layer is not None else ""
        (self.target / ".claude" / "harness.env").write_text(line, encoding="utf-8")
        env = {k: v for k, v in os.environ.items() if not k.startswith("HARNESS_") and k != "CLAUDE_PROJECT_DIR"}
        env.update(CLAUDE_CONFIG_DIR=str(self.cfg), CLAUDE_PROJECT_DIR=str(self.target))
        if gate:
            env["HARNESS_DOCTOR_ROOT"] = str(self.harness)
        p = subprocess.run([sys.executable, "-I", str(SCAN), str(self.target), "--only", "6", "--json"], capture_output=True,
                           text=True, env=env, cwd=str(self.target), timeout=120, stdin=subprocess.DEVNULL)
        self.assertIn(p.returncode, (0, 1, 2), p.stderr)
        return [f["msg"] for f in json.loads(p.stdout)["findings"] if f["code"] == "DRIFT-UID"]

    def test_free_range_is_quiet(self):
        first, last = free_range(4)
        self.assertEqual(self.findings(f"{first}-{last}"), [])

    def test_invalid_or_empty_range(self):
        for bad in ("", "abc", "0-3", "5-2", "1-100000"):
            with self.subTest(bad=bad):
                msgs = self.findings(bad)
                self.assertEqual(len(msgs), 1, msgs)
                self.assertIn("잘못됐다", msgs[0])

    def test_collision_with_a_real_account(self):
        real = next(e.pw_uid for e in pwd.getpwall() if e.pw_uid > 0)
        (msg,) = self.findings(f"{real}-{real}")
        self.assertIn(f"{real}(user)", msg)
        self.assertIn("남는 uid 가 없어", msg)
        first, last = free_range(3)
        self.assertEqual(self.findings(f"{first}-{last}"), [])

    def test_option_layer_and_repo_layer(self):
        self.assertTrue(self.findings("63500-63503", option="abc"), "옵션이 사용자 harness.env 위에 온다")
        first, last = free_range(2)
        self.assertEqual(self.findings(f"{first}-{last}", repo_layer="abc"), [], "저장소 층은 대역을 바꾸지 못한다")

    def test_gate(self):
        self.assertEqual(self.findings("abc", gate=False), [], "하네스 저장소도 설치된 qwreey-delegate 도 없으면 보지 않는다")

    def test_bound_matches_the_driver(self):
        got, want = literal(SCAN.parent / "scan_settings.py", "MAX_UID_RANGE"), literal(DRIVER, "MAX_UID_RANGE")
        self.assertEqual(got, want, f"{SCAN.parent / 'scan_settings.py'} 의 MAX_UID_RANGE 를 {DRIVER} 의 값으로 고친다")


if __name__ == "__main__":
    unittest.main()
