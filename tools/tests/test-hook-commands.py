"""플러그인·팩 hooks.json 의 command 훅이 모두 같은 꼴로 파이썬을 부르는지 본다. 실행: python3 -I tools/tests/test-hook-commands.py

꼴: python3 -I -X utf8 "${CLAUDE_PLUGIN_ROOT}/<플러그인 안 경로>.py" [인자...]
- python3: Linux·macOS 의 sh, Windows 의 Git Bash 와 PowerShell 모두에서 한 줄로 돈다(런처 파일을 두면 PowerShell 에서 깨진다).
- -I: 사용자 site 와 PYTHON* 환경 변수를 무시한다. 그래서 PYTHONUTF8 이 먹지 않는다.
- -X utf8: Windows 의 코드 페이지(한국어 cp949)가 아니라 UTF-8 로 파일을 읽고 stdout 에 쓴다. Linux 의 UTF-8·C 로캘에서는 바뀌는 것이 없다.
- 경로는 따옴표로 감싼다(공백 든 Windows 사용자 폴더).
"""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FORM = re.compile(r'^python3 -I -X utf8 "\$\{CLAUDE_PLUGIN_ROOT\}/([^"]+\.py)"(?: [\w.-]+)*$')
SKIP = {"qwreey-desk"}  # 파이썬 훅이 없다(모드 엔진)


def commands():
    for f in sorted(list(ROOT.glob("plugins/*/hooks/hooks.json")) + list(ROOT.glob("packs/*/hooks/hooks.json"))):
        if f.parent.parent.name in SKIP:
            continue
        for groups in json.loads(f.read_text(encoding="utf-8"))["hooks"].values():
            for g in groups:
                for h in g["hooks"]:
                    if h.get("type") == "command":
                        yield f, h["command"]


class HookCommands(unittest.TestCase):
    def test_form(self):
        seen = 0
        for f, cmd in commands():
            seen += 1
            with self.subTest(file=str(f.relative_to(ROOT)), command=cmd):
                m = FORM.match(cmd)
                self.assertIsNotNone(m, "hooks.json 의 command 는 python3 -I -X utf8 \"${CLAUDE_PLUGIN_ROOT}/...py\" [인자] 꼴이어야 한다")
                self.assertTrue((f.parent.parent / m.group(1)).is_file(), m.group(1))
        self.assertGreater(seen, 0)


if __name__ == "__main__":
    unittest.main()
