"""플러그인·팩 hooks.json 의 command 훅이 모두 정해진 두 꼴 중 하나인지 본다. 실행: python3 -I tools/tests/test-hook-commands.py

파이썬 꼴(args 없음): python3 -I -X utf8 "${CLAUDE_PLUGIN_ROOT}/<플러그인 안 경로>.py" [인자...]
- python3: Linux·macOS 의 sh, Windows 의 Git Bash 와 PowerShell 모두에서 한 줄로 돈다(런처 파일을 두면 PowerShell 에서 깨진다).
- -I: 사용자 site 와 PYTHON* 환경 변수를 무시한다. 그래서 PYTHONUTF8 이 먹지 않는다.
- -X utf8: Windows 의 코드 페이지(한국어 cp949)가 아니라 UTF-8 로 파일을 읽고 stdout 에 쓴다. Linux 의 UTF-8·C 로캘에서는 바뀌는 것이 없다.
- 경로는 따옴표로 감싼다(공백 든 Windows 사용자 폴더).
- 스크립트 파일이 있어야 한다.

실행 꼴(args 있음, Rust 바이너리): "command": "${CLAUDE_PLUGIN_ROOT}/native/<바이너리>", "args": ["hook", "<이벤트>", ...]
- args 가 있으면 Claude Code 는 셸 없이 command 를 실행 파일로 바로 띄우고 args 를 argv 로 준다. ${CLAUDE_PLUGIN_ROOT} 는 글자로 바뀌므로
  공백 든 경로도 따옴표가 필요 없고, 따옴표를 달면 그대로 경로에 들어가 깨진다.
- args 는 셸 글자 없는 낱말만(따옴표, 공백, $ 가 들어가면 셸 꼴을 잘못 옮긴 것).
- native/ 의 바이너리는 빌드 산출물이라 git 에 없다. 그래서 파일이 있는지는 보지 않는다.
"""
import json
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # python3 -I 는 스크립트 디렉터리를 path 에 넣지 않는다
from hook_sandbox import PYTHON_HOOK as FORM, ROOT  # noqa: E402

EXEC_COMMAND = re.compile(r'^\$\{CLAUDE_PLUGIN_ROOT\}/native/[\w.-]+$')
EXEC_ARG = re.compile(r'^[\w.-]+$')
SKIP = {"qwreey-desk"}  # 파이썬 훅이 없다(모드 엔진)


def commands():
    for f in sorted(list(ROOT.glob("plugins/*/hooks/hooks.json")) + list(ROOT.glob("packs/*/hooks/hooks.json"))):
        if f.parent.parent.name in SKIP:
            continue
        for groups in json.loads(f.read_text(encoding="utf-8"))["hooks"].values():
            for g in groups:
                for h in g["hooks"]:
                    if h.get("type") == "command":
                        yield f, h


class HookCommands(unittest.TestCase):
    def test_form(self):
        seen = 0
        for f, hook in commands():
            seen += 1
            cmd = hook["command"]
            with self.subTest(file=str(f.relative_to(ROOT)), command=cmd, args=hook.get("args")):
                if "args" in hook:
                    self.check_exec(cmd, hook["args"])
                    continue
                m = FORM.match(cmd)
                self.assertIsNotNone(m, "hooks.json 의 command 는 python3 -I -X utf8 \"${CLAUDE_PLUGIN_ROOT}/...py\" [인자] 꼴이어야 한다")
                self.assertTrue((f.parent.parent / m.group(1)).is_file(), m.group(1))
        self.assertGreater(seen, 0)

    def check_exec(self, cmd, args):
        self.assertRegex(cmd, EXEC_COMMAND, "args 가 있는 command 는 \"${CLAUDE_PLUGIN_ROOT}/native/<바이너리>\" 꼴이어야 한다")
        self.assertIsInstance(args, list)
        for arg in args:
            self.assertRegex(arg if isinstance(arg, str) else repr(arg), EXEC_ARG, "args 는 셸 글자 없는 낱말이어야 한다")

    def test_exec_form_examples(self):
        """실행 꼴 판정이 받을 것과 거를 것. 아직 hooks.json 에 실행 꼴이 없어도 규칙이 살아 있게 한다."""
        good = ["${CLAUDE_PLUGIN_ROOT}/native/proc-guard", "${CLAUDE_PLUGIN_ROOT}/native/proc-guard.exe"]
        bad = ['"${CLAUDE_PLUGIN_ROOT}/native/proc-guard"', "${CLAUDE_PLUGIN_ROOT}/bin/proc-guard", "proc-guard",
               "${CLAUDE_PLUGIN_ROOT}/native/sub/proc-guard", "${CLAUDE_PLUGIN_ROOT}/native/proc guard"]
        for cmd in good:
            self.assertRegex(cmd, EXEC_COMMAND)
        for cmd in bad:
            self.assertNotRegex(cmd, EXEC_COMMAND)
        for arg in ("hook", "pre-tool-use", "PreToolUse", "v1.2"):
            self.assertRegex(arg, EXEC_ARG)
        for arg in ("", "a b", '"x"', "$X", "a;b"):
            self.assertNotRegex(arg, EXEC_ARG)


if __name__ == "__main__":
    unittest.main()
