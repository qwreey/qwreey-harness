"""방치 작업 알림: 셸 등 서브에이전트가 아닌 작업의 출력 파일 신호와 문구. 실행: python3 -I tests/test_stale_work.py  (모델 호출 없음)

서브에이전트 트랜스크립트 신호와 dedup·끄기는 test_notices.py 의 Stale 이 본다. 여기서는 Claude Code 가 쓰는
<TMPDIR>/claude-<uid>/<프로젝트 키>/<sid>/tasks/<id>.output 을 가짜로 만들어 본다. 기준 시간은 환경 변수로 0 에 가깝게 줄여 잠들지 않는다.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

STALE = Path(__file__).resolve().parent.parent / "scripts" / "stale_work.py"
SID = "s-stale-test"


def run(payload, env):
    p = subprocess.run([sys.executable, "-I", str(STALE)], input=json.dumps(payload), capture_output=True, text=True, env=env, timeout=30)
    assert p.returncode == 0, p.stderr
    return json.loads(p.stdout) if p.stdout.strip() else None


class ShellSignal(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = Path(self.tmp.name)
        (t / "tmp").mkdir()
        (t / "salt").write_text("00" * 32)
        self.env = {"PATH": os.environ["PATH"], "TMPDIR": str(t / "tmp"), "QWREEY_HARNESS_SALT_FILE": str(t / "salt"),
                    "HARNESS_Q_STALE_IDLE_MIN": "5", "HARNESS_Q_STALE_AGE_MIN": "0", "HARNESS_Q_STALE_LONG_MIN": "999"}
        # 트랜스크립트는 <projects>/<프로젝트 키>/<sid>.jsonl, 작업 출력은 <tmp>/claude-<uid>/<프로젝트 키>/<sid>/tasks/<id>.output
        key = "-code-Projects-fake"
        self.tp = t / "projects" / key / (SID + ".jsonl")
        self.tp.parent.mkdir(parents=True)
        self.tp.write_text("")
        self.tasks = t / "tmp" / ("claude-%d" % os.getuid()) / key / SID / "tasks"
        self.tasks.mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def output(self, tid, text="", age_s=0):
        p = self.tasks / (tid + ".output")
        p.write_text(text)
        if age_s:
            os.utime(p, (time.time() - age_s, time.time() - age_s))
        return p

    def stop(self, tasks, env=None):
        return run({"hook_event_name": "Stop", "session_id": SID, "transcript_path": str(self.tp), "background_tasks": tasks}, env or self.env)

    def context(self):
        out = run({"hook_event_name": "UserPromptSubmit", "session_id": SID, "prompt": "hi"}, self.env)
        return out["hookSpecificOutput"]["additionalContext"] if out else None

    SHELL = {"id": "b1tfeqtx2", "type": "shell", "status": "running", "description": "Wait for test run to finish and show output"}

    def test_quiet_shell_is_stalled_with_stop_hint(self):
        out_file = self.output("b1tfeqtx2", "", age_s=3600)  # 한 시간째 출력 없음 (pgrep -f 대기 루프)
        msg = self.stop([self.SHELL])
        self.assertIn("멈췄거나 대기 중일 수 있습니다", msg["systemMessage"])
        self.assertIn("Wait for test run", msg["systemMessage"])
        text = self.context()
        self.assertRegex(text, r'<harness-hook name="stale-work" level="warn" nonce="[0-9a-f]{12}">\n')
        self.assertIn("may be stalled or waiting", text)
        self.assertIn("TaskStop", text)
        self.assertIn("loops waiting on a condition", text)
        self.assertIn(str(out_file), text)

    def test_output_change_counts_as_progress(self):
        f = self.output("b2", "line\n", age_s=3600)
        shell = {**self.SHELL, "id": "b2"}
        # 처음 볼 때는 나이 기준이 아직이라 아무것도 내지 않고 신호만 남긴다
        self.assertIsNone(self.stop([shell], {**self.env, "HARNESS_Q_STALE_AGE_MIN": "999"}))
        with open(f, "a") as fh:
            fh.write("more\n")
        self.assertIsNone(self.stop([shell]))  # 출력이 늘었으니 진척, 멈춤 아님
        self.assertIsNone(self.context())

    def test_long_running_notice_does_not_say_stay_silent(self):
        self.output("b3", "tick\n")  # 방금 출력: 진척 있음
        env = {**self.env, "HARNESS_Q_STALE_LONG_MIN": "0"}
        msg = self.stop([{**self.SHELL, "id": "b3"}], env)
        self.assertIn("실행 중입니다(진척은 있음)", msg["systemMessage"])
        text = self.context()
        self.assertIn('level="info"', text)
        self.assertIn("still showing progress", text)
        self.assertIn("TaskStop", text)
        self.assertIn("mention it to the user in one line", text)
        self.assertNotIn("only if it matters", text)

    def test_shell_without_output_file_is_only_long(self):
        env = {**self.env, "HARNESS_Q_STALE_IDLE_MIN": "0", "HARNESS_Q_STALE_LONG_MIN": "0"}
        msg = self.stop([{**self.SHELL, "id": "nofile"}], env)
        self.assertNotIn("멈췄", msg["systemMessage"])
        text = self.context()
        self.assertIn('level="info"', text)
        self.assertNotIn("Output file", text)

    def test_unknown_type_uses_output_file_too(self):
        self.output("x9", "", age_s=3600)
        msg = self.stop([{"id": "x9", "type": "remote_thing", "status": "running", "description": "odd"}])
        self.assertIn("멈췄거나", msg["systemMessage"])
        self.assertIn("remote_thing", self.context())

    def test_monitor_still_excluded(self):
        self.output("m1", "", age_s=3600)
        self.assertIsNone(self.stop([{"id": "m1", "type": "monitor", "status": "running", "description": "watch"}]))

    def test_old_two_field_state_is_read(self):
        # 이전 버전이 남긴 상태 파일의 신호는 [크기, mtime] 두 칸이다
        f = self.output("b4", "abc", age_s=3600)
        st = Path(self.env["TMPDIR"]) / "claude-q-stale" / (SID + ".json")
        st.parent.mkdir(parents=True)
        now, sig_mtime = time.time(), os.stat(f).st_mtime
        st.write_text(json.dumps({"tasks": {"b4": {"first": now - 3600, "prog": now - 3600, "sig": [3, sig_mtime], "done": []}},
                                  "model": [], "user": []}))
        msg = self.stop([{**self.SHELL, "id": "b4"}])
        self.assertIn("멈췄거나", msg["systemMessage"])


if __name__ == "__main__":
    unittest.main()
