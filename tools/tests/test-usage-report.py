"""tools/usage-report.py 시험. 실행: python3 -I tools/tests/test-usage-report.py  (모델 호출 없음, 표준 라이브러리만)

임시 설정 폴더의 projects/ 아래에 가짜 트랜스크립트(메인 세션, 서브에이전트와 meta.json, 시험 키)를 만들고 --json 결과의 숫자를 본다:
훅 목소리와 수준, 거부, 실행 시간(Stop 은 stop summary 에서만), systemMessage, 상시 주입, 서브에이전트, 토큰(message.id 마다 한 번),
시험 키 빼기와 --include-probes, 창 거르기, Markdown 보고서에 메시지 내용이 새지 않음. --time-hooks 는 가짜 플러그인 하나로 한 번 돌린다.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools" / "usage-report.py"
SECRET = "SECRET-CONTENT-42"
NONCE = "abcdef123456"
DAY = "2026-11-10"


def ts(hour, day=DAY):
    return "%sT%02d:00:00.000Z" % (day, hour)


def tag(name, level, body):
    return '<harness-hook name="%s" level="%s" nonce="%s">\n%s\n</harness-hook>' % (name, level, NONCE, body)


def plugin_block(name, body):
    return '<plugin name="%s" nonce="%s">\n%s\n</plugin>' % (name, NONCE, body)


def attachment(hour, **att):
    return {"type": "attachment", "timestamp": ts(hour), "attachment": att}


def success(hour, event, name, command, stdout, ms, tool_use="t1"):
    return attachment(hour, type="hook_success", hookName=name, hookEvent=event, toolUseID=tool_use, content="",
                      stdout=stdout, stderr="", exitCode=0, command=command, durationMs=ms)


def context(hour, event, items, tool_use="t1"):
    return attachment(hour, type="hook_additional_context", hookName=event, hookEvent=event, toolUseID=tool_use, content=items)


def assistant(hour, mid, model, output):
    return {"type": "assistant", "timestamp": ts(hour), "message": {
        "model": model, "id": mid, "role": "assistant", "content": [{"type": "text", "text": SECRET}],
        "usage": {"input_tokens": 3, "cache_read_input_tokens": 100, "cache_creation_input_tokens": 10, "output_tokens": output}}}


def ctx_json(event, text):
    return json.dumps({"hookSpecificOutput": {"hookEventName": event, "additionalContext": text}})


AMBIENT_Q = 'python3 -I -X utf8 "${CLAUDE_PLUGIN_ROOT}/scripts/ambient.py" SessionStart'
BYPASS = 'python3 -I -X utf8 "${CLAUDE_PLUGIN_ROOT}/hooks/bash-bypass-reminder.py"'
CONV_CHECK = 'python3 -I -X utf8 "${CLAUDE_PLUGIN_ROOT}/hooks/conventions-check.py"'
STALE = 'python3 -I -X utf8 "${CLAUDE_PLUGIN_ROOT}/scripts/stale_work.py"'
Q_START = plugin_block("q", "Rules for %s, with a quoted <harness-hook name=\"...\" level=\"info|warn|action\"> example." % SECRET)
WS_START = plugin_block("qwreey-workspace", "Workspace %s" % SECRET)
BYPASS_TEXT = tag("bash-bypass-reminder", "warn", "Bypass at /home/someone/%s" % SECRET)


def main_session_lines():
    """메인 세션 하나: 시작 주입, Bash 알림, 사용자 입력 주입, 거부, Stop, 실패 훅, 되풀이되는 assistant 줄, 창 밖 줄."""
    return [
        success(1, "SessionStart", "SessionStart:startup", AMBIENT_Q, ctx_json("SessionStart", Q_START), 50, "s0"),
        context(1, "SessionStart", [Q_START, WS_START], "s0"),
        success(2, "PreToolUse", "PreToolUse:Bash", BYPASS, ctx_json("PreToolUse", BYPASS_TEXT), 40),
        context(2, "PreToolUse", [BYPASS_TEXT]),
        context(3, "UserPromptSubmit", [tag("reply-language", "info", "Reply in Korean, %s" % SECRET)], "u1"),
        {"type": "user", "timestamp": ts(4), "message": {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "t2", "is_error": True,
             "content": "PreToolUse:Edit hook error: " + tag("workspace-gate", "action", "Blocked %s" % SECRET)},
            {"type": "tool_result", "tool_use_id": "t3", "is_error": False,
             "content": "PreToolUse:Bash hook error: printed by cat, not a deny"}]}},
        success(5, "Stop", "Stop", CONV_CHECK, json.dumps({"systemMessage": "Old problems in %s" % SECRET}), 70, "st"),
        attachment(5, type="hook_system_message", hookName="Stop", hookEvent="Stop", toolUseID="st", content="Old problems in %s" % SECRET),
        {"type": "system", "subtype": "stop_hook_summary", "timestamp": ts(5), "toolUseID": "st", "hookCount": 2,
         "hookInfos": [{"command": CONV_CHECK, "durationMs": 70}, {"command": STALE, "durationMs": 30}], "hookErrors": []},
        attachment(6, type="hook_non_blocking_error", hookName="PostToolUse:Read", hookEvent="PostToolUse", toolUseID="t4",
                   stderr=SECRET, stdout="", exitCode=1, command=STALE, durationMs=9),
        assistant(7, "msg_1", "claude-opus-x", 500),
        assistant(7, "msg_1", "claude-opus-x", 500),
        assistant(8, "msg_s", "<synthetic>", 0),
        {**context(9, "UserPromptSubmit", [tag("reply-language", "info", "old")], "u0"), "timestamp": ts(9, "2026-10-01")},
    ]


def subagent_lines():
    return [context(1, "SubagentStart", [Q_START], "a0"), assistant(2, "msg_a", "claude-sonnet-x", 200)]


def write_jsonl(path, lines):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(x) + "\n" for x in lines), encoding="utf-8")


class UsageReport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="usage-report-")).resolve()
        cls.projects = cls.tmp / "projects"
        key = cls.projects / "-code-Projects-alpha"
        write_jsonl(key / "s1.jsonl", main_session_lines())
        write_jsonl(key / "s1" / "subagents" / "agent-a1.jsonl", subagent_lines())
        (key / "s1" / "subagents" / "agent-a1.meta.json").write_text(json.dumps(
            {"agentType": "general-purpose", "model": "sonnet", "requestShape": "background", "spawnDepth": 1}), encoding="utf-8")
        write_jsonl(cls.projects / "-tmp-probe-x" / "p1.jsonl", [context(2, "PreToolUse", [BYPASS_TEXT]),
                                                                 assistant(3, "msg_p", "claude-opus-x", 7)])

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def run_tool(self, *args):
        p = subprocess.run([sys.executable, "-I", str(TOOL), "--projects-dir", str(self.projects), *args],
                           capture_output=True, text=True, timeout=120)
        self.assertEqual(p.returncode, 0, p.stderr[-2000:])
        return p.stdout

    def report(self, *args):
        return json.loads(self.run_tool("--since", DAY, "--until", DAY, "--json", *args))

    def test_hook_voices_and_levels(self):
        voices = {v["hook"]: v for v in self.report()["hooks_spoke"]}
        self.assertEqual(voices["bash-bypass-reminder"]["spoke"], 1)
        self.assertEqual(voices["bash-bypass-reminder"]["levels"], {"warn": 1})
        self.assertEqual(voices["bash-bypass-reminder"]["plugin"], "qwreey-conventions")
        self.assertEqual(voices["plugin q"]["spoke"], 2, "session start and subagent start; the quoted tag inside is not a voice")
        self.assertNotIn("...", voices)
        self.assertEqual(voices["reply-language"]["spoke"], 1, "the 2026-10-01 line is outside the window")
        self.assertEqual(voices["workspace-gate"]["denies"], 1)
        self.assertEqual(voices["workspace-gate"]["levels"], {"action": 1})
        self.assertEqual(voices["plugin q"]["chars"], 2 * len(Q_START))

    def test_denies_runs_and_messages(self):
        r = self.report()
        self.assertEqual(r["denies"], [{"hook": "workspace-gate", "tool": "Edit", "kind": "exit 2", "count": 1}])
        runs = {(x["hook"], x["event"]): x for x in r["hook_runs"]}
        self.assertEqual(runs[("qwreey-conventions:bash-bypass-reminder.py", "PreToolUse")]["p50_ms"], 40)
        self.assertEqual(runs[("qwreey-conventions:conventions-check.py", "Stop")]["runs"], 1, "Stop is timed from the summary only")
        self.assertEqual(runs[("q:stale_work.py", "Stop")]["p50_ms"], 30)
        self.assertEqual(runs[("q:stale_work.py", "PostToolUse")]["errors"], 1)
        self.assertEqual(r["user_messages"], [{"hook": "qwreey-conventions:conventions-check.py", "count": 1,
                                               "chars": len("Old problems in %s" % SECRET)}])

    def test_always_on_subagents_tokens(self):
        r = self.report()
        ao = r["always_on"]
        self.assertEqual(ao["session_startup"], {"n": 1, "p50": len(Q_START) + len(WS_START), "max": len(Q_START) + len(WS_START)})
        self.assertEqual(ao["subagent_start"]["n"], 1)
        self.assertEqual(ao["user_prompt"]["n"], 1)
        self.assertEqual(r["subagents"], [{"type": "general-purpose", "requested_model": "sonnet", "model": "claude-sonnet-x",
                                           "shape": "background", "count": 1, "output_tokens": 200}])
        self.assertEqual(r["tokens_by_project"], [{"project": "-code-Projects-alpha", "input": 6, "cache_read": 200,
                                                   "cache_creation": 20, "output": 700}], "msg_1 counted once, synthetic skipped")
        self.assertEqual((r["sessions"], r["subagents_total"]), (1, 1))

    def test_probe_keys(self):
        r = self.report()
        self.assertEqual(r["window"]["probe_keys_excluded"], 1)
        self.assertEqual(r["projects"], ["-code-Projects-alpha"])
        r = self.report("--include-probes")
        self.assertEqual(r["projects"], ["-code-Projects-alpha", "-tmp-probe-x"])
        self.assertEqual({v["hook"]: v["spoke"] for v in r["hooks_spoke"]}["bash-bypass-reminder"], 2)

    def test_window_and_project_filter(self):
        r = json.loads(self.run_tool("--since", "2026-11-12", "--json"))
        self.assertEqual((r["sessions"], r["hooks_spoke"], r["tokens_by_project"]), (0, [], []))
        r = self.report("--project", "nomatch")
        self.assertEqual(r["sessions"], 0)

    def test_markdown_has_no_content(self):
        out = self.run_tool("--since", DAY, "--until", DAY, "--include-probes")
        self.assertIn("## Hooks that spoke", out)
        self.assertIn("bash-bypass-reminder", out)
        for leak in (SECRET, "/home/someone", NONCE, "Reply in Korean", "Blocked"):
            self.assertNotIn(leak, out)


FAKE_HOOKS = {"hooks": {
    "PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": 'python3 -I -X utf8 "${CLAUDE_PLUGIN_ROOT}/hooks/quiet.py"'}]},
                   {"matcher": "Bash", "hooks": [{"type": "prompt", "prompt": "judge this"}]}],
    "PostToolUse": [{"matcher": "*", "hooks": [{"type": "command", "command": 'python3 -I -X utf8 "${CLAUDE_PLUGIN_ROOT}/hooks/loud.py" x'},
                                               {"type": "command", "command": "echo outside"}]}],
    "SessionStart": [{"hooks": [{"type": "command", "command": 'python3 -I -X utf8 "${CLAUDE_PLUGIN_ROOT}/hooks/quiet.py"'}]}],
}}
QUIET = "import json, os, sys\ndata = json.load(sys.stdin)\nassert os.environ['CLAUDE_PLUGIN_DATA'].startswith(os.environ['TMPDIR'].rsplit('/tmp', 1)[0])\n"
LOUD = "import json, sys\njson.load(sys.stdin)\nprint(json.dumps({'hookSpecificOutput': {'hookEventName': 'PostToolUse', 'additionalContext': 'hi'}}))\n"


class Bench(unittest.TestCase):
    def test_bench_smoke(self):
        tmp = Path(tempfile.mkdtemp(prefix="usage-bench-test-")).resolve()
        try:
            plugin = tmp / "fakeplug"
            (plugin / ".claude-plugin").mkdir(parents=True)
            (plugin / ".claude-plugin" / "plugin.json").write_text(json.dumps({"name": "fakeplug"}), encoding="utf-8")
            (plugin / "hooks").mkdir()
            (plugin / "hooks" / "hooks.json").write_text(json.dumps(FAKE_HOOKS), encoding="utf-8")
            (plugin / "hooks" / "quiet.py").write_text(QUIET, encoding="utf-8")
            (plugin / "hooks" / "loud.py").write_text(LOUD, encoding="utf-8")
            p = subprocess.run([sys.executable, "-I", str(TOOL), "--time-hooks", "--runs", "2", "--hook-root", str(plugin), "--json"],
                               capture_output=True, text=True, timeout=300)
            self.assertEqual(p.returncode, 0, p.stderr[-2000:])
            r = json.loads(p.stdout)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

        rows = {(h["hook"], h["event"], h["tool"]): h for h in r["hooks"]}
        self.assertEqual(sorted(rows), [("fakeplug:loud.py x", "PostToolUse", t) for t in ("Bash", "Edit", "Read")]
                         + [("fakeplug:quiet.py", "PreToolUse", "Bash")])
        self.assertEqual(rows[("fakeplug:quiet.py", "PreToolUse", "Bash")]["exit"], {"0": 2})
        self.assertEqual(rows[("fakeplug:quiet.py", "PreToolUse", "Bash")]["spoke"], 0)
        self.assertEqual(rows[("fakeplug:loud.py x", "PostToolUse", "Read")]["spoke"], 2)
        self.assertEqual(r["per_tool"]["Bash"]["PostToolUse"]["hooks"], 1)
        self.assertEqual(sorted(s["reason"] for s in r["skipped"]),
                         ["command runs outside the plugin root", "type prompt calls a model or the network"])


if __name__ == "__main__":
    unittest.main()
