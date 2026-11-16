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
        self.transcript = self.write_transcript(["b7x9k2", "b1", "b2", "m1", "a5"])

    def write_transcript(self, own_ids, name="agent-a1.jsonl"):
        """서브에이전트 트랜스크립트 흉내: 실측한 Bash 백그라운드 결과 꼴(문자열)과 블록 목록 꼴의 tool_result."""
        path = os.path.join(self.tmp.name, name)
        lines = [{"type": "user", "message": {"role": "user", "content": "Run the build."}},
                 {"type": "assistant", "message": {"content": [{"type": "text", "text": "main task bmain0001 is not mine"}]}}]
        for i, tid in enumerate(own_ids):
            text = "Command running in background with ID: %s. Output is being written to: /tmp/x/%s.output." % (tid, tid)
            content = text if i % 2 == 0 else [{"type": "text", "text": text}]
            lines.append({"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "t%d" % i, "content": content}]}})
        with open(path, "w", encoding="utf-8") as f:
            f.write("".join(json.dumps(l) + "\n" for l in lines) + "{broken json line \"tool_result\"\n")
        return path

    def tearDown(self):
        self.tmp.cleanup()

    def run_raw(self, stdin, env=None):
        r = subprocess.run([sys.executable, "-I", HOOK], input=stdin, capture_output=True, text=True, env=env or self.env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stderr, "")
        return r.stdout

    def stop(self, tasks, env=None, **kw):
        payload = dict(hook_event_name="SubagentStop", session_id="s1", agent_id="a1", cwd=self.proj,
                       last_assistant_message="Done. Report follows.", stop_hook_active=False, background_tasks=tasks,
                       agent_transcript_path=self.transcript)
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

    def test_only_main_tasks_silent(self):
        # 실측: SubagentStop 의 background_tasks 에는 메인이 띄운 셸도 들어 있다
        main_task = task("bmain0001", desc="Sleep in background")
        self.assertEqual(self.stop([main_task]), "", "id only in assistant text, not in a tool_result")
        self.assertEqual(self.stop([task("b10")]), "", "b1 in the transcript must not claim b10")
        text = self.context(self.stop([main_task, task("b1")]))
        self.assertIn("- shell b1:", text)
        self.assertNotIn("bmain0001", text)

    def test_unknown_owner_silent(self):
        self.assertEqual(self.stop([task("b1")], agent_transcript_path=None), "")
        self.assertEqual(self.stop([task("b1")], agent_transcript_path=os.path.join(self.tmp.name, "missing.jsonl")), "")
        self.assertEqual(self.stop([task("b1")], agent_transcript_path=self.write_transcript([], "empty.jsonl")), "")
        self.assertTrue(self.stop([task("b1")]), "silent passes must not use up the one notice")

    def test_malformed_input_silent(self):
        odd = json.dumps({"hook_event_name": "SubagentStop", "session_id": "s1", "agent_id": "a1",
                          "agent_transcript_path": self.transcript,
                          "background_tasks": [1, "x", {"status": "running"}, {"id": 7, "status": "running"},
                                               {"id": "b1", "status": "running", "type": "shell", "description": {"nested": True}}]})
        for raw in ("", "not json", "[1, 2]", "null", odd):
            out = self.run_raw(raw)
            if raw is odd:
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
