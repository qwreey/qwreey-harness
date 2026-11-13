"""q 상시 규약 주입 단위 테스트. 실행: python3 -I tests/test_ambient.py  (모델 호출 없음)"""
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
TEXT = (ROOT / "context" / "ambient.md").read_text(encoding="utf-8")


class T(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="q-ambient-")
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("HARNESS_")}
        self.env.update(TMPDIR=self.tmp, HOME=self.tmp, CLAUDE_CONFIG_DIR=os.path.join(self.tmp, "cfg"))
        self.sid = "sess-1"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_hook(self, event, extra=None, env=None, script=SCRIPT, stdin=None):
        data = {"session_id": self.sid, "hook_event_name": event}
        data.update(extra or {})
        p = subprocess.run([sys.executable, "-I", str(script), event], input=json.dumps(data) if stdin is None else stdin,
                           capture_output=True, text=True, env=env or self.env, timeout=30)
        self.assertEqual(p.returncode, 0, p.stderr)
        return json.loads(p.stdout) if p.stdout.strip() else None

    def bump(self):
        d = os.path.join(self.tmp, "claude-q-epoch")
        os.makedirs(d, exist_ok=True)
        f = os.path.join(d, self.sid)
        n = int(Path(f).read_text()) if os.path.exists(f) else 0
        Path(f).write_text(str(n + 1))

    def test_format(self):
        for ev in ("SessionStart", "SubagentStart"):
            o = self.run_hook(ev, {"agent_type": "general-purpose", "source": "startup"})
            h = o["hookSpecificOutput"]
            self.assertEqual(h["hookEventName"], ev)
            self.assertTrue(h["additionalContext"].startswith('<plugin name="q">\n## Hook messages'))
            self.assertTrue(h["additionalContext"].endswith("</plugin>"))
            self.assertIn(TEXT.strip(), h["additionalContext"])
            self.assertLess(len(h["additionalContext"]), 10000)

    def test_fork_skipped(self):
        self.assertIsNone(self.run_hook("SubagentStart", {"agent_type": "fork"}))
        self.assertIsNotNone(self.run_hook("SubagentStart", {"agent_type": "Explore"}))

    def test_off_switch(self):
        env = dict(self.env, HARNESS_Q_AMBIENT="off")
        for ev in ("SessionStart", "SubagentStart", "UserPromptSubmit"):
            self.assertIsNone(self.run_hook(ev, env=env))

    def test_off_switch_in_harness_env(self):
        cfg = Path(self.tmp) / "cfg"
        (cfg / "lib").mkdir(parents=True)
        shutil.copy(ROOT.parent.parent / "home" / ".claude" / "lib" / "harness_env.py", cfg / "lib")
        (cfg / "harness.env").write_text("HARNESS_Q_AMBIENT=off\n")
        self.assertIsNone(self.run_hook("SessionStart"))

    def test_fail_open_missing_file(self):
        d = Path(self.tmp) / "plug"
        (d / "scripts").mkdir(parents=True)
        shutil.copy(SCRIPT, d / "scripts" / "ambient.py")
        shutil.copy(ROOT / "scripts" / "compact_epoch.py", d / "scripts" / "compact_epoch.py")
        for ev in ("SessionStart", "SubagentStart", "UserPromptSubmit"):
            self.assertIsNone(self.run_hook(ev, script=d / "scripts" / "ambient.py"))

    def test_fail_open_bad_stdin(self):
        self.assertIsNotNone(self.run_hook("SessionStart", stdin="not json"))
        self.assertIsNone(self.run_hook("Bogus"))

    def test_ups_without_session_start(self):
        self.assertIsNotNone(self.run_hook("UserPromptSubmit"))
        self.assertIsNone(self.run_hook("UserPromptSubmit"))
        self.bump()  # 플러그인이 꺼진 사이 compact(SessionStart 안 돎) 뒤 다시 켜짐
        self.assertIsNotNone(self.run_hook("UserPromptSubmit"))
        self.assertIsNone(self.run_hook("UserPromptSubmit"))

    def test_session_start_sets_marker(self):
        self.assertIsNotNone(self.run_hook("SessionStart", {"source": "startup"}))
        self.assertIsNone(self.run_hook("UserPromptSubmit"))

    def test_compact_then_ups_no_double(self):
        self.run_hook("SessionStart", {"source": "startup"})
        # PreCompact 가 회차를 올린 뒤 SessionStart(compact) 가 싣고 표지를 새 회차로 둔다
        self.bump()
        self.assertIsNotNone(self.run_hook("SessionStart", {"source": "compact"}))
        self.assertIsNone(self.run_hook("UserPromptSubmit"))
        # SessionStart 가 안 돈 채 compact 가 지나면 보충이 다시 싣는다
        self.bump()
        self.assertIsNotNone(self.run_hook("UserPromptSubmit"))
        self.assertIsNone(self.run_hook("UserPromptSubmit"))

    def test_ups_skips_subagent(self):
        self.assertIsNone(self.run_hook("UserPromptSubmit", {"agent_id": "a1"}))

    def run_precompact(self, extra=None, env=None, script=SCRIPT, stdin=None):
        data = {"session_id": self.sid, "hook_event_name": "PreCompact", "trigger": "manual", "custom_instructions": None}
        data.update(extra or {})
        p = subprocess.run([sys.executable, "-I", str(script), "PreCompact"], input=json.dumps(data) if stdin is None else stdin,
                           capture_output=True, text=True, env=env or self.env, timeout=30)
        self.assertEqual(p.returncode, 0, p.stderr)
        return p.stdout

    def test_precompact_omit_line(self):
        want = 'Omit the <plugin name="q"> block from the summary; it is re-injected after compaction.\n'
        self.assertEqual(self.run_precompact(), want)
        self.assertEqual(self.run_precompact({"trigger": "auto"}), want)
        self.assertEqual(self.run_precompact(stdin="not json"), want)
        self.assertEqual(self.run_precompact({"agent_id": "a1"}), "", "서브에이전트 compact 뒤에는 다시 싣지 않는다")
        self.assertEqual(self.run_precompact(env=dict(self.env, HARNESS_Q_AMBIENT="off")), "")
        hooks = json.loads((ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8"))["hooks"]["PreCompact"]
        self.assertTrue(any('ambient.py" PreCompact' in h["command"] for g in hooks for h in g["hooks"]))

    def test_precompact_off_in_harness_env_and_missing_file(self):
        cfg = Path(self.tmp) / "cfg"
        (cfg / "lib").mkdir(parents=True)
        shutil.copy(ROOT.parent.parent / "home" / ".claude" / "lib" / "harness_env.py", cfg / "lib")
        (cfg / "harness.env").write_text("HARNESS_Q_AMBIENT=off\n")
        self.assertEqual(self.run_precompact(), "")
        (cfg / "harness.env").unlink()
        d = Path(self.tmp) / "plug"
        (d / "scripts").mkdir(parents=True)
        shutil.copy(SCRIPT, d / "scripts" / "ambient.py")
        shutil.copy(ROOT / "scripts" / "compact_epoch.py", d / "scripts" / "compact_epoch.py")
        self.assertEqual(self.run_precompact(script=d / "scripts" / "ambient.py"), "", "블록이 없으면 뺄 것도 없다")


if __name__ == "__main__":
    unittest.main()
