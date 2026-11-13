"""workspace 규약 주입 단위 테스트(합성 stdin). 실행: python3 -I tests/test_ambient.py  (모델 호출 없음)"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "ambient.py"
OMIT = 'Omit the <plugin name="qwreey-workspace"> block from the summary; it is re-injected after compaction.\n'


class T(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="ws-ambient-")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_hook(self, event, extra=None, stdin=None, script=SCRIPT):
        data = {"session_id": "s1", "hook_event_name": event}
        data.update(extra or {})
        p = subprocess.run([sys.executable, "-I", str(script), event], input=json.dumps(data) if stdin is None else stdin,
                           capture_output=True, text=True, env=dict(os.environ, TMPDIR=self.tmp), timeout=30)
        self.assertEqual(p.returncode, 0, p.stderr)
        return p.stdout

    def test_session_start_block(self):
        ctx = json.loads(self.run_hook("SessionStart", {"source": "compact"}))["hookSpecificOutput"]["additionalContext"]
        self.assertTrue(ctx.startswith('<plugin name="qwreey-workspace">\n') and ctx.endswith("</plugin>"))
        self.assertEqual(self.run_hook("SubagentStart", {"agent_type": "fork"}), "")

    def test_precompact_omit_line(self):
        self.assertEqual(self.run_hook("PreCompact", {"trigger": "manual", "custom_instructions": None}), OMIT)
        self.assertEqual(self.run_hook("PreCompact", {"trigger": "auto"}), OMIT)
        self.assertEqual(self.run_hook("PreCompact", stdin="not json"), OMIT)
        self.assertEqual(self.run_hook("PreCompact", {"agent_id": "a1"}), "", "서브에이전트 compact 뒤에는 다시 싣지 않는다")
        groups = json.loads((ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8"))["hooks"]["PreCompact"]
        self.assertTrue(any('ambient.py" PreCompact' in h["command"] for g in groups for h in g["hooks"]))

    def test_precompact_quiet_without_block(self):
        d = Path(self.tmp) / "plug" / "scripts"
        d.mkdir(parents=True)
        shutil.copy(SCRIPT, d / "ambient.py")
        self.assertEqual(self.run_hook("PreCompact", script=d / "ambient.py"), "", "블록이 없으면 뺄 것도 없다")


if __name__ == "__main__":
    unittest.main()
