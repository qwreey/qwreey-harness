"""모든 hooks.json 훅을 Windows 흉내(simwin.py)로 한 번씩 돌려 죽지 않는지 본다. 실행: python3 -I tools/tests/test-hooks-simwin.py

훅마다 그 이벤트의 최소 입력을 주고 exit 0 과 stderr 에 Traceback 이 없음을 본다. 판정 내용은 test-hook-replay.py 몫이다
(그 묶음도 HOOK_SANDBOX_SIMWIN=1 로 흉내 낼 수 있다). simwin.py 가 못 보는 것은 그 파일 머리에 있다.
"""
import json
import os
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # python3 -I 는 스크립트 디렉터리를 path 에 넣지 않는다
from hook_sandbox import ROOT, Sandbox  # noqa: E402

FORM = re.compile(r'"\$\{CLAUDE_PLUGIN_ROOT\}/([^"]+)"((?: [\w.-]+)*)$')
SKIP = {"qwreey-desk"}


def payload(event, matcher, sb):
    tool = (matcher or "Bash").split("|")[0]
    if tool in ("", "*", ".*"):
        tool = "Bash"
    base = {"hook_event_name": event, "session_id": "simwin", "cwd": str(sb.repo), "transcript_path": str(sb.tmp / "t.jsonl")}
    tool_input = {"Bash": {"command": "ls"}, "Read": {"file_path": str(sb.repo / "a.py")}, "Grep": {"pattern": "x"},
                  "Glob": {"pattern": "*"}, "Skill": {"skill": "x"}, "Agent": {"description": "d", "prompt": "p"},
                  "Task": {"description": "d", "prompt": "p"}}.get(tool, {"file_path": str(sb.repo / "a.py"), "content": "x = 1\n"})
    extra = {
        "SessionStart": {"source": matcher.split("|")[0] if matcher else "startup"},
        "SubagentStart": {"agent_id": "a1", "agent_type": "general-purpose"},
        "SubagentStop": {"agent_id": "a1", "agent_type": "general-purpose", "stop_hook_active": False},
        "Stop": {"stop_hook_active": False},
        "UserPromptSubmit": {"prompt": "hello"},
        "UserPromptExpansion": {"prompt": "/x"},
        "PreToolUse": {"tool_name": tool, "tool_input": tool_input, "tool_use_id": "t1"},
        "PostToolUse": {"tool_name": tool, "tool_input": tool_input, "tool_response": {}, "tool_use_id": "t1"},
        "PostToolUseFailure": {"tool_name": tool, "tool_input": tool_input, "error": "x", "tool_use_id": "t1"},
        "PreCompact": {"trigger": "manual", "custom_instructions": ""},
        "PostCompact": {"trigger": "manual", "compact_summary": "s"},
        "SessionEnd": {"reason": "other"},
    }.get(event, {})
    return {**base, **extra}


def hooks():
    for f in sorted(ROOT.glob("plugins/*/hooks/hooks.json")):
        if f.parent.parent.name in SKIP:
            continue
        for event, groups in json.loads(f.read_text(encoding="utf-8"))["hooks"].items():
            for g in groups:
                for h in g["hooks"]:
                    m = FORM.search(h.get("command", ""))
                    if m:
                        yield f.parent.parent, event, g.get("matcher", ""), m.group(1), m.group(2).split()


class HooksSimWin(unittest.TestCase):
    def test_every_hook_survives(self):
        os.environ["HOOK_SANDBOX_SIMWIN"] = "1"
        n = 0
        with Sandbox(prefix="hooks-simwin-") as sb:
            sb.write("a.py", "x = 1\n")
            (sb.tmp / "t.jsonl").write_text("", encoding="utf-8")
            for plugin, event, matcher, script, argv in hooks():
                n += 1
                with self.subTest(plugin=plugin.name, event=event, script=script):
                    r = sb.run(plugin / script, payload(event, matcher, sb), argv,
                               env={"CLAUDE_PLUGIN_ROOT": str(plugin)})
                    self.assertNotIn("Traceback", r.stderr, r.stderr[-1500:])
                    self.assertIn(r.rc, (0, 2), r.stderr[-800:])
        self.assertGreater(n, 50)


if __name__ == "__main__":
    unittest.main()
