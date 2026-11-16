#!/usr/bin/env python3
"""subagent-bg-tasks 훅 테스트(합성 stdin, 모델 호출 없음). 실행: python3 -I plugins/qwreey-operator/tests/test_subagent_bg_tasks.py"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

HOOK = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks", "subagent-bg-tasks.py")
NONCE = "985461182738"  # salt "00"*32, session "s1"


def task(tid, type_="shell", status="running", desc="sleep 600"):
    return {"id": tid, "type": type_, "status": status, "description": desc}


class SubagentBgTasks(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.proj = os.path.join(self.tmp.name, "proj")
        self.cfg = os.path.join(self.tmp.name, "cfg")
        os.makedirs(os.path.join(self.proj, ".claude"))
        os.makedirs(self.cfg)
        salt = os.path.join(self.tmp.name, "salt")
        with open(salt, "w") as f:
            f.write("00" * 32)
        self.env = {k: v for k, v in os.environ.items() if not k.startswith(("HARNESS_", "CLAUDE_"))}
        # 사용자, 저장소 harness.env 층을 이 임시 폴더로 돌려 실제 설정을 읽지 않는다
        self.env.update(TMPDIR=self.tmp.name, QWREEY_HARNESS_SALT_FILE=salt, CLAUDE_CONFIG_DIR=self.cfg,
                        CLAUDE_PROJECT_DIR=self.proj, HOME=self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def run_raw(self, stdin, env=None):
        r = subprocess.run([sys.executable, "-I", HOOK], input=stdin, capture_output=True, text=True, env=env or self.env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stderr, "")
        return r.stdout

    def stop(self, tasks, env=None, **kw):
        payload = dict(hook_event_name="SubagentStop", session_id="s1", agent_id="a1", cwd=self.proj,
                       last_assistant_message="Done. Report follows.", stop_hook_active=False, background_tasks=tasks)
        payload.update(kw)
        return self.run_raw(json.dumps(payload), env)

    def context(self, out):
        hso = json.loads(out)["hookSpecificOutput"]
        self.assertEqual(hso["hookEventName"], "SubagentStop")
        return hso["additionalContext"]

    def test_running_shell_notifies_once(self):
        out = self.stop([task("b7x9k2", desc="until ! pgrep -f build; do sleep 5; done")])
        text = self.context(out)
        self.assertTrue(text.startswith('<harness-hook name="subagent-bg-tasks" level="warn" nonce="%s">' % NONCE), text)
        self.assertIn('- shell b7x9k2: "until ! pgrep -f build; do sleep 5; done"', text)
        self.assertIn("TaskStop", text)
        self.assertIn("unless your brief says to leave them running", text)
        self.assertIn("final report again", text)
        self.assertEqual(self.stop([task("b7x9k2")]), "", "second SubagentStop of the same agent")

    def test_other_agent_is_separate(self):
        self.assertTrue(self.stop([task("b1")]))
        self.assertTrue(self.stop([task("b2")], agent_id="a2"))

    def test_stop_hook_active_silent(self):
        self.assertEqual(self.stop([task("b1")], stop_hook_active=True), "")
        self.assertTrue(self.stop([task("b1")]), "a passed stop_hook_active call must not use up the one notice")

    def test_finished_tasks_silent(self):
        tasks = [task("b1", status="completed"), task("b2", status="failed"), task("a9", "subagent", "killed")]
        self.assertEqual(self.stop(tasks), "")
        self.assertEqual(self.stop([]), "")
        self.assertEqual(self.stop(None), "")

    def test_monitor_only_silent(self):
        self.assertEqual(self.stop([task("m1", "monitor", desc="watch log")]), "")

    def test_lists_each_running_task_and_skips_others(self):
        tasks = [task("b1"), task("m1", "monitor"), task("b2", status="completed"),
                 task("a5", "subagent", desc="explore auth"), task("a1", "subagent", desc="self")]
        text = self.context(self.stop(tasks))
        self.assertIn('- shell b1: "sleep 600"', text)
        self.assertIn('- subagent a5: "explore auth"', text)
        for gone in ("m1", "b2", "a1:"):
            self.assertNotIn(gone, text)

    def test_long_description_is_one_short_line(self):
        text = self.context(self.stop([task("b1", desc="x" * 200 + "\nsecond line")]))
        line = [l for l in text.splitlines() if l.startswith("- shell b1")][0]
        self.assertLess(len(line), 110)
        self.assertTrue(line.endswith('..."'))

    def test_error_or_empty_turn_silent(self):
        self.assertEqual(self.stop([task("b1")], last_assistant_message="API Error: 529 overloaded"), "")
        self.assertEqual(self.stop([task("b1")], last_assistant_message="Prompt is too long"), "")
        self.assertEqual(self.stop([task("b1")], last_assistant_message="  "), "")

    def test_question_still_notifies(self):
        self.assertTrue(self.stop([task("b1")], last_assistant_message="Open question: keep the old path?"))

    def test_main_stop_and_missing_ids_silent(self):
        self.assertEqual(self.stop([task("b1")], hook_event_name="Stop"), "")
        self.assertEqual(self.stop([task("b1")], agent_id=None), "")
        self.assertEqual(self.stop([task("b1")], session_id=None), "")

    def test_malformed_input_silent(self):
        for raw in ("", "not json", "[1, 2]", "null", '{"hook_event_name": "SubagentStop", "session_id": "s1", "agent_id": "a1", '
                    '"background_tasks": [1, "x", {"status": "running"}, {"id": "b1", "status": "running", "type": "shell", '
                    '"description": {"nested": true}}]}'):
            out = self.run_raw(raw)
            if raw.startswith('{"hook'):
                self.assertIn("- shell b1:", self.context(out), "a bad description is printed, not fatal")
            else:
                self.assertEqual(out, "", raw)

    def test_off_switch_env(self):
        for v in ("off", "0", "no", "OFF"):
            self.assertEqual(self.stop([task("b1")], env=dict(self.env, HARNESS_OPERATOR_SUBAGENT_BG=v)), "")
        self.assertTrue(self.stop([task("b1")], env=dict(self.env, HARNESS_OPERATOR_SUBAGENT_BG="on")))

    def test_off_switch_harness_env_layers(self):
        with open(os.path.join(self.proj, ".claude", "harness.env"), "w") as f:
            f.write("HARNESS_OPERATOR_SUBAGENT_BG=off\n")
        self.assertEqual(self.stop([task("b1")]), "", "repo harness.env turns it off")
        self.assertTrue(self.stop([task("b1")], env=dict(self.env, HARNESS_OPERATOR_SUBAGENT_BG="on")), "env var wins")

    def test_off_switch_user_layer(self):
        with open(os.path.join(self.cfg, "harness.env"), "w") as f:
            f.write("HARNESS_OPERATOR_SUBAGENT_BG=off\n")
        self.assertEqual(self.stop([task("b1")]), "")

    def test_unwritable_state_fails_open(self):
        blocker = os.path.join(self.tmp.name, "claude-qwreey-operator-subagent-bg")
        with open(blocker, "w") as f:
            f.write("a file where the state directory should be")
        self.assertEqual(self.stop([task("b1")]), "")


if __name__ == "__main__":
    unittest.main()
