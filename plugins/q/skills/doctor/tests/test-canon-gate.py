#!/usr/bin/env python3
"""doctor 의 정본 검사 문(scan.find_doctor_root). 실행: python3 -I test-canon-gate.py  (exit 0 = 통과, 모델 호출 없음)

정본 검사(정본 훅 사본 DRIFT-HOOK, MANIFEST 링크 LINK-TARGET, 정본 home/.claude 대조)는 하네스 저장소를 알 때만 돈다:
지금 프로젝트($CLAUDE_PROJECT_DIR, 없으면 cwd)가 하네스 저장소(home/MANIFEST 와 .claude-plugin/marketplace.json)이거나
그 아래 폴더일 때, 또는 환경 변수 HARNESS_DOCTOR_ROOT 가 있을 때. 스크립트가 이 저장소 안에 있어도(설치본 아닌 클론) 짐작하지 않고,
사용자 harness.env 에 남은 옛 HARNESS_DOCTOR_ROOT 도 읽지 않는다. 가짜 하네스 저장소를 임시 폴더에 만들어 scan.py 를 하위 프로세스로 돌린다.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCAN = Path(__file__).resolve().parent.parent / "scripts" / "scan.py"
GUARD = "print('guard')\n"


class CanonGate(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = Path(self.tmp.name)
        self.cfg, self.harness, self.target, self.plain = t / "cfg", t / "harness", t / "target", t / "plain"
        for d in (self.cfg, self.target, self.plain):
            d.mkdir()
        (self.harness / "home" / ".claude").mkdir(parents=True)
        (self.harness / "home" / "MANIFEST").write_text("harness.env\nlink skills/kb ${HARNESS_DOCTOR_ROOT}/no-such-dir\n", encoding="utf-8")
        (self.harness / ".claude-plugin").mkdir()
        (self.harness / ".claude-plugin" / "marketplace.json").write_text("{}", encoding="utf-8")
        hooks = self.harness / "plugins" / "qwreey-proc-guard" / "hooks"
        hooks.mkdir(parents=True)
        (hooks / "heavy-proc-guard.py").write_text(GUARD, encoding="utf-8")
        (self.target / "heavy-proc-guard.py").write_text(GUARD, encoding="utf-8")
        # 옛 설정: 사용자 harness.env 의 HARNESS_DOCTOR_ROOT 는 이제 문을 열지 않는다
        (self.cfg / "harness.env").write_text("HARNESS_DOCTOR_ROOT=%s\n" % self.harness, encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def scan(self, *args, project, env=None):
        base = {k: v for k, v in os.environ.items()
                if k not in ("HARNESS_DOCTOR_ROOT", "HARNESS_ENV", "CLAUDE_PROJECT_DIR") and not k.startswith("HARNESS_")}
        base.update(CLAUDE_CONFIG_DIR=str(self.cfg), CLAUDE_PROJECT_DIR=str(project), **(env or {}))
        p = subprocess.run([sys.executable, "-I", str(SCAN), *args], capture_output=True, text=True, env=base, cwd=str(project),
                           timeout=120, stdin=subprocess.DEVNULL)
        self.assertIn(p.returncode, (0, 1, 2), p.stderr)
        return p.stdout

    def codes(self, *args, project, env=None):
        out = self.scan(*args, "--json", project=project, env=env)
        return {f["code"] for f in json.loads(out)["findings"]}

    def test_outside_harness_repo_skips_canon_checks(self):
        self.assertNotIn("DRIFT-HOOK", self.codes(str(self.target), "--only", "6", project=self.plain))
        self.assertNotIn("LINK-TARGET", self.codes("--user", "--only", "3", project=self.plain))
        env = self.scan("--env", project=self.plain)
        self.assertIn("DOCTOR_ROOT=(없음", env)
        self.assertNotIn("WORKSPACE=", env)

    def test_inside_harness_repo_runs_canon_checks(self):
        self.assertIn("DRIFT-HOOK", self.codes(str(self.target), "--only", "6", project=self.harness))
        self.assertIn("LINK-TARGET", self.codes("--user", "--only", "3", project=self.harness))
        self.assertIn("DOCTOR_ROOT=%s" % self.harness.resolve(), self.scan("--env", project=self.harness))

    def test_subfolder_of_harness_repo_counts(self):
        sub = self.harness / "plugins" / "qwreey-proc-guard"
        self.assertIn("DRIFT-HOOK", self.codes(str(self.target), "--only", "6", project=sub))

    def test_walk_stops_at_the_project_git_root(self):
        inner = self.harness / "nested"
        (inner / ".git").mkdir(parents=True)
        self.assertNotIn("DRIFT-HOOK", self.codes(str(self.target), "--only", "6", project=inner))

    def test_env_var_override(self):
        got = self.codes(str(self.target), "--only", "6", project=self.plain, env={"HARNESS_DOCTOR_ROOT": str(self.harness)})
        self.assertIn("DRIFT-HOOK", got)


if __name__ == "__main__":
    unittest.main()
