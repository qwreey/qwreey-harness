"""tools/tests/hook-parity.py 와 hook_sandbox 의 run_argv 를 본다. 실행: python3 -I tools/tests/test-hook-parity.py  (모델 호출 없음)

- 같은 python 을 실행 형식으로 부르면(identity) 모든 입력이 같다고 한다.
- 양쪽 모두 CLAUDE_PLUGIN_ROOT, CLAUDE_PLUGIN_DATA, CLAUDE_PROJECT_DIR 을 받고, 사례가 정한 값은 그대로다.
- 다른 출력을 내는 대역은 어긋남과 읽을 수 있는 diff 를, 없는 바이너리는 띄우지 못함(exit 127)을 알린다.
- 가짜 트랜스크립트에서 PreToolUse, PostToolUse, PostToolUseFailure 입력을 만들고 같은 호출 id 는 한 번만 쓴다. transcript_path 는 없는 파일이다.
"""
import contextlib
import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))  # python3 -I 는 스크립트 디렉터리를 path 에 넣지 않는다
from hook_sandbox import ROOT, Sandbox  # noqa: E402

_spec = importlib.util.spec_from_file_location("hook_parity", HERE / "hook-parity.py")
parity = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(parity)

GUARD = "plugins/qwreey-proc-guard/hooks/self-match-guard.py"
STUB = "import sys; sys.stdin.read(); print('{\"hookSpecificOutput\": {\"hookEventName\": \"PreToolUse\", \"additionalContext\": \"stub line\\\\nsecond\"}}')"


def run_main(*argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
        rc = parity.main(list(argv))
    return rc, out.getvalue()


def tool_lines(call_id, command, result, is_error=False):
    use = {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": call_id, "name": "Bash", "input": {"command": command}}]}}
    res = {"type": "user", "toolUseResult": {"stdout": result, "stderr": "", "interrupted": False},
           "message": {"content": [{"type": "tool_result", "tool_use_id": call_id, "content": result, "is_error": is_error}]}}
    return [json.dumps(use), json.dumps(res)]


class Parity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="test-hook-parity-"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def write_map(self, name, entries):
        path = self.tmp / name
        path.write_text(json.dumps(entries), encoding="utf-8")
        return str(path)

    def test_identity_is_same(self):
        rc, out = run_main("--identity", "qwreey-proc-guard")
        self.assertEqual(rc, 0, out)
        self.assertRegex(out, r"(\d+) inputs: \1 same, 0 different")
        self.assertIn("case self-match-loop-deny.json step 1 self-match-guard.py", out)

    def test_stub_differs_with_diff(self):
        path = self.write_map("stub.json", [{"hook": GUARD, "exec": ["python3", "-I", "-c", STUB]}])
        rc, out = run_main("--map", path, "--case", "self-match-loop-deny")
        self.assertEqual(rc, 1, out)
        self.assertIn("DIFFERENT             case self-match-loop-deny.json step 1", out)
        self.assertIn("--- python", out)
        self.assertIn("+++ exec", out)
        self.assertIn("+  | stub line", out)
        self.assertIn("-hookSpecificOutput.permissionDecision: \"deny\"", out)

    def test_missing_binary_cannot_start(self):
        path = self.write_map("missing.json", [{"hook": GUARD, "argv": [], "exec": ["${CLAUDE_PLUGIN_ROOT}/native/does-not-exist", "hook", "pre-tool-use"]}])
        rc, out = run_main("--map", path, "--case", "self-match-safe-forms")
        self.assertEqual(rc, 1, out)
        self.assertIn("vs 127 (exec)", out)
        self.assertIn("cannot start <root>/plugins/qwreey-proc-guard/native/does-not-exist", out)

    def test_bad_map(self):
        path = self.write_map("bad.json", [{"hook": "tools/tests/hook_sandbox.py", "exec": ["x"]}])
        self.assertEqual(run_main("--map", path)[0], 2)
        self.assertEqual(run_main("--identity", "no-such-plugin")[0], 2)

    def test_run_argv_expands_plugin_root(self):
        with Sandbox(prefix="test-hook-parity-") as sb:
            r = sb.run_argv(["python3", "-I", "-c", "import sys; print(sys.argv[1]); print(sys.stdin.read())", "${CLAUDE_PLUGIN_ROOT}/x"],
                            {"cwd": "{repo}"}, "plugins/qwreey-proc-guard")
            self.assertEqual(r.rc, 0, r.stderr)
            first, second = r.stdout.splitlines()[:2]
            self.assertEqual(first, str(ROOT / "plugins" / "qwreey-proc-guard" / "x"))
            self.assertEqual(json.loads(second), {"cwd": str(sb.repo)})

    def test_plugin_env_on_both_sides(self):
        printer = "import os, sys; sys.stdin.read(); print(*(os.environ.get(k) for k in ('CLAUDE_PLUGIN_ROOT', 'CLAUDE_PLUGIN_DATA', 'CLAUDE_PROJECT_DIR')))"
        entry = parity.Entry(GUARD, [sys.executable, "-I", "-c", printer], argv=[])
        with Sandbox(prefix="test-hook-parity-") as sb:
            env = sb.plugin_env("plugins/qwreey-proc-guard")
            r = parity.run_side(sb, GUARD, [], {"cwd": "{repo}"}, {}, entry)
            self.assertEqual(r.stdout.split(), [env["CLAUDE_PLUGIN_ROOT"], env["CLAUDE_PLUGIN_DATA"], str(sb.repo)])
            self.assertTrue(env["CLAUDE_PLUGIN_DATA"].startswith(str(sb.cfg / "plugins" / "data" / "qwreey-proc-guard-")))
            case_value = parity.run_side(sb, GUARD, [], {}, {"CLAUDE_PLUGIN_DATA": "{sandbox}/mine"}, entry).stdout.split()[1]
            self.assertEqual(case_value, str(sb.root / "mine"))

    def test_transcript_inputs(self):
        projects = self.tmp / "projects"
        (projects / "p").mkdir(parents=True, exist_ok=True)
        older = tool_lines("toolu_a", "ls", "a\n") + tool_lines("toolu_b", "false", "Exit code 1", is_error=True)
        (projects / "p" / "old.jsonl").write_text("\n".join(older) + "\n", encoding="utf-8")
        # 이어 간 세션처럼 toolu_b 를 다시 적고, 결과가 아직 없는 새 호출 하나
        newer = older[2:3] + [json.dumps({"type": "assistant", "message": {"content": [
            {"type": "tool_use", "id": "toolu_c", "name": "Bash", "input": {"command": "sleep 1"}}]}})]
        new_file = projects / "p" / "new.jsonl"
        new_file.write_text("\n".join(newer) + "\n", encoding="utf-8")
        old_time = new_file.stat().st_mtime - 60
        os.utime(projects / "p" / "old.jsonl", (old_time, old_time))

        calls = parity.recent_calls(lambda name: name == "Bash", 3, projects)
        self.assertEqual([c["id"] for c in calls], ["toolu_c", "toolu_b", "toolu_a"])
        self.assertTrue(calls[1]["is_error"])

        rc, out = run_main("--identity", "qwreey-proc-guard", "--no-cases", "--from-transcripts", "3", "--projects", str(projects))
        self.assertEqual(rc, 0, out)
        self.assertIn("transcript PostToolUseFailure Bash toolu_b resource-guard.py", out)
        self.assertIn("transcript PostToolUse Bash toolu_a resource-guard.py", out)
        self.assertNotIn("PostToolUse Bash toolu_c", out)
        self.assertNotIn("PostToolUseFailure Bash toolu_a", out)

        with Sandbox(prefix="test-hook-parity-") as sb:
            payload = json.loads(parity.tool_payload(sb, "PostToolUseFailure", calls[1]))
            self.assertFalse(Path(payload["transcript_path"]).exists())
            self.assertEqual(payload["cwd"], str(sb.repo))
            self.assertEqual(payload["error"], "Exit code 1")


if __name__ == "__main__":
    unittest.main()
