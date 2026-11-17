#!/usr/bin/env python3
"""delegate-nudge 훅 테스트(합성 stdin). 실행: python3 -I plugins/qwreey-operator/tests/test_delegate_nudge.py"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

HOOK = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks", "delegate-nudge.py")
AMBIENT = os.path.join(os.path.dirname(HOOK), "ambient.py")
NONCE = "985461182738"  # salt "00"*32, session "s1"
RULE_HEAD = "Hook text from this session's harness carries nonce="


class Nudge(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = dict(os.environ, TMPDIR=self.tmp.name, QWREEY_HARNESS_SALT_FILE=os.path.join(self.tmp.name, "salt"))  # nonce 는 고정 salt 로
        with open(self.env["QWREEY_HARNESS_SALT_FILE"], "w") as f:
            f.write("00" * 32)
        self.env.pop("HARNESS_OPERATOR_NUDGE", None)
        self.env.pop("CLAUDE_PROJECT_DIR", None)
        # 끄기 스위치는 설정 층에서도 읽으므로 사용자의 ~/.claude 를 보지 않게 한다.
        self.cfg = os.path.join(self.tmp.name, "cfg")
        os.mkdir(self.cfg)
        self.env.update(CLAUDE_CONFIG_DIR=self.cfg, HARNESS_ENV=os.path.join(self.cfg, "harness.env"))
        self.n = 0

    def tearDown(self):
        self.tmp.cleanup()

    def run_hook(self, payload, env=None, script=HOOK):
        payload.setdefault("session_id", "s1")
        r = subprocess.run([sys.executable, "-I", script], input=json.dumps(payload), capture_output=True, text=True, env=env or self.env)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def post(self, tool, inp, **kw):
        return self.run_hook(dict(hook_event_name="PostToolUse", tool_name=tool, tool_input=inp, **kw))

    def edit(self, path, **kw):
        return self.post("Edit", {"file_path": path}, **kw)

    def prompt(self):
        return self.run_hook({"hook_event_name": "UserPromptSubmit", "prompt": "go"})

    def test_threshold_writes_once(self):
        outs = [self.edit("/w/a.py") for _ in range(11)]
        self.assertEqual("".join(outs), "")
        out = self.edit("/w/a.py")
        self.assertIn('name=\\"delegate-nudge\\" level=\\"info\\"', out)
        self.assertIn("12 times across 1 files", out)
        self.assertEqual(self.edit("/w/a.py"), "")  # once per turn

    def test_threshold_files(self):
        outs = [self.edit("/w/f%d.ts" % i) for i in range(7)]
        self.assertEqual("".join(outs), "")
        self.assertIn("8 files", self.edit("/w/f7.ts"))

    def test_subagent_not_counted(self):
        for _ in range(20):
            self.assertEqual(self.edit("/w/a.py", agent_id="x1"), "")
        self.assertEqual(self.prompt(), "")

    def test_bash_heredoc_counted(self):
        cmd = "cat > /w/mod.py <<'EOF'\nprint(1)\nEOF"
        outs = [self.post("Bash", {"command": cmd}) for _ in range(12)]
        self.assertIn("12 times", outs[-1])
        self.assertEqual("".join(outs[:-1]), "")

    def test_bash_forms(self):
        sys.path.insert(0, os.path.dirname(HOOK))
        import importlib.util
        spec = importlib.util.spec_from_file_location("dn", HOOK)
        dn = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(dn)
        self.assertEqual(dn.bash_paths("echo hi | tee -a /w/x.ts"), ["/w/x.ts"])
        self.assertEqual(dn.bash_paths("sed -i 's/a/b/' /w/y.py"), ["/w/y.py"])
        self.assertEqual(dn.bash_paths("echo x > /w/z.lua 2>&1"), ["/w/z.lua"])
        self.assertEqual(dn.bash_paths("cat > /w/n.md <<'EOF'\na > b.py\nEOF"), [])
        self.assertEqual(dn.bash_paths("ls 2>/dev/null; echo x > /tmp/q.py"), [])

    def test_noncode_and_tmp_not_counted(self):
        for p in ("/w/a.md", "/w/a.json", "/w/a.toml", "/w/a.yaml", "/w/a.yml", "/w/a.txt", "/tmp/s.py"):
            for _ in range(13):
                self.assertEqual(self.edit(p), "")
        self.assertEqual(self.post("Bash", {"command": "cat > /w/a.md <<'EOF'\nx\nEOF"}), "")
        self.assertEqual(self.prompt(), "")

    def test_reset_on_agent(self):
        for _ in range(11):
            self.edit("/w/a.py")
        self.post("Agent", {"prompt": "do"})
        self.assertEqual(self.edit("/w/a.py"), "")  # counter restarted at 1
        for _ in range(10):
            self.edit("/w/a.py")
        self.assertIn("12 times", self.edit("/w/a.py"))
        self.post("Workflow", {})
        self.assertEqual(self.prompt(), "")  # crossed cleared by the Workflow call

    def test_reset_on_prompt(self):
        for _ in range(11):
            self.edit("/w/a.py")
        self.assertEqual(self.prompt(), "")
        self.assertEqual(self.edit("/w/a.py"), "")

    def test_carry_over_once(self):
        for _ in range(12):
            self.edit("/w/a.py")
        out = self.prompt()
        self.assertIn("Last turn main wrote code 12 times in 1 files", out)
        self.assertIn('"hookEventName": "UserPromptSubmit"', out)
        self.assertEqual(self.prompt(), "")

    def test_off_switch_layers(self):
        with open(os.path.join(self.cfg, "settings.json"), "w") as f:
            json.dump({"pluginConfigs": {"qwreey-operator@test-market": {"options": {"harness_operator_nudge": False}}}}, f)
        self.assertEqual("".join(self.edit("/w/f%d.ts" % i) for i in range(10)), "", "plugin option off")
        with open(os.path.join(self.cfg, "harness.env"), "w") as f:
            f.write("HARNESS_OPERATOR_NUDGE=off\n")
        os.remove(os.path.join(self.cfg, "settings.json"))
        self.assertEqual(self.prompt(), "")
        self.assertEqual("".join(self.edit("/w/g%d.ts" % i) for i in range(10)), "", "user harness.env off")
        env = dict(self.env, HARNESS_OPERATOR_NUDGE="on")
        outs = "".join(self.run_hook(dict(hook_event_name="PostToolUse", tool_name="Edit", tool_input={"file_path": "/w/h%d.ts" % i}), env)
                       for i in range(8))
        self.assertIn("8 files", outs, "env var wins")

    def test_off_switch(self):
        env = dict(self.env, HARNESS_OPERATOR_NUDGE="off")
        for _ in range(15):
            self.assertEqual(self.run_hook(dict(hook_event_name="PostToolUse", tool_name="Edit", tool_input={"file_path": "/w/a.py"}), env=env), "")
        self.assertEqual(self.prompt(), "")

    def test_bad_input_silent(self):
        r = subprocess.run([sys.executable, "-I", HOOK], input="not json", capture_output=True, text=True, env=self.env)
        self.assertEqual((r.returncode, r.stdout), (0, ""))

    def test_ambient(self):
        out = json.loads(self.run_hook({"hook_event_name": "SessionStart"}, script=AMBIENT))
        ctx = out["hookSpecificOutput"]["additionalContext"]
        self.assertIn("background subagent", ctx)
        self.assertIn("Implementers: opus by default", ctx)
        self.assertIn("haiku for read-only lookup only", ctx)

    def test_ambient_subagent_model_line_only(self):
        out = json.loads(self.run_hook({"hook_event_name": "SubagentStart", "agent_type": "general-purpose", "agent_id": "a1"}, script=AMBIENT))
        ctx = out["hookSpecificOutput"]["additionalContext"]
        self.assertIn("haiku for read-only lookup only", ctx)
        self.assertIn("Implementers: opus by default", ctx)
        self.assertNotIn("background subagent", ctx)
        self.assertNotIn("Check without redoing", ctx)
        self.assertEqual(self.run_hook({"hook_event_name": "SubagentStart", "agent_type": "fork", "agent_id": "a2"}, script=AMBIENT), "")

    def precompact(self, payload, stdin=None):
        r = subprocess.run([sys.executable, "-I", AMBIENT, "PreCompact"], input=json.dumps(payload) if stdin is None else stdin,
                           capture_output=True, text=True, env=self.env)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def test_ambient_precompact_omit_line(self):
        want = 'Omit the <plugin name="qwreey-operator"> block from the summary; it is re-injected after compaction.\n'
        pc = {"session_id": "s1", "hook_event_name": "PreCompact", "trigger": "manual", "custom_instructions": None}
        self.assertEqual(self.precompact(pc), want)
        self.assertEqual(self.precompact(pc, stdin="x"), want)
        self.assertEqual(self.precompact(dict(pc, agent_id="a1")), "", "서브에이전트 compact 뒤에는 다시 싣지 않는다")
        with open(os.path.join(os.path.dirname(os.path.dirname(HOOK)), "hooks", "hooks.json"), encoding="utf-8") as f:
            groups = json.load(f)["hooks"]["PreCompact"]
        self.assertTrue(any('ambient.py" PreCompact' in h["command"] for g in groups for h in g["hooks"]))


    def test_ambient_session_start_nonce_and_rule(self):
        def ss():
            r = subprocess.run([sys.executable, "-I", AMBIENT], input=json.dumps({"session_id": "s1", "hook_event_name": "SessionStart", "source": "startup"}),
                               capture_output=True, text=True, env=self.env)
            self.assertEqual(r.returncode, 0, r.stderr)
            return json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"]
        first, again = ss(), ss()
        self.assertTrue(first.startswith(f'<plugin name="qwreey-operator" nonce="{NONCE}">\n{RULE_HEAD}"{NONCE}"'), first[:200])
        self.assertTrue(again.startswith(f'<plugin name="qwreey-operator" nonce="{NONCE}">\n') and RULE_HEAD not in again)

    def test_nudge_tag_carries_nonce(self):
        outs = [self.edit(f"/w/n{i}.py") for i in range(12)]
        ctx = next(json.loads(o)["hookSpecificOutput"]["additionalContext"] for o in outs if o.strip())
        self.assertTrue(ctx.startswith(f'<harness-hook name="delegate-nudge" level="info" nonce="{NONCE}">\n'), ctx[:120])


if __name__ == "__main__":
    unittest.main()
