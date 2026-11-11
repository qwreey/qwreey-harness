"""compact 회차 모듈 테스트(사본 동일성은 tools/tests/test-vendored-copies.py). 실행: python3 -I tests/test_compact_epoch.py  (모델 호출 없음)"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CANON = ROOT / "scripts" / "compact_epoch.py"


class CompactEpoch(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = dict(os.environ, TMPDIR=self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def py(self, code):
        p = subprocess.run([sys.executable, "-I", "-c", f"import sys; sys.path.insert(0, {str(CANON.parent)!r})\nimport compact_epoch as ce\n{code}"],
                           capture_output=True, text=True, env=self.env, timeout=30)
        self.assertEqual(p.returncode, 0, p.stderr)
        return p.stdout.strip()

    def test_bump_per_plugin_namespace(self):
        self.assertEqual(self.py("print(ce.epoch('a','s'), ce.bump('a','s'), ce.bump('a','s'), ce.epoch('a','s'), ce.epoch('b','s'))"), "0 1 2 2 0")
        self.assertTrue((Path(self.tmp.name) / "claude-a-epoch" / "s").exists())

    def test_state_path_keys(self):
        out = self.py("print(ce.state_path('a','ns','s').rsplit('/',1)[1], ce.state_path('a','ns','s','x1').rsplit('/',1)[1]); ce.bump('a','s'); print(ce.state_path('a','ns','s').rsplit('/',1)[1])")
        self.assertEqual(out.splitlines(), ["s.c0.json s.c0.ax1.json", "s.c1.json"])

    def test_cli_bumps_main_only(self):
        def cli(payload):
            p = subprocess.run([sys.executable, "-I", str(CANON), "a"], input=payload, capture_output=True, text=True, env=self.env, timeout=30)
            self.assertEqual((p.returncode, p.stdout), (0, ""))
        cli(json.dumps({"session_id": "s", "trigger": "auto"}))
        cli(json.dumps({"session_id": "s", "agent_id": "ag"}))  # 서브에이전트는 올리지 않는다
        cli("not json")
        cli(json.dumps({}))
        self.assertEqual((Path(self.tmp.name) / "claude-a-epoch" / "s").read_text(), "1")


if __name__ == "__main__":
    unittest.main()
