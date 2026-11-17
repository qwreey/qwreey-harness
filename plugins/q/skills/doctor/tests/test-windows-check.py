#!/usr/bin/env python3
"""doctor 의 Windows 전제 검사(scan.check_windows: WIN-PYTHON3, WIN-GITBASH). 실행: python3 -I test-windows-check.py  (exit 0 = 통과)

Linux 에서 shutil.which 를 바꿔 끼워 세 경우(없음, 앱 실행 별칭, 정상)의 판정만 본다. 실제 Windows 동작은 HUMAN_TODO 의 첫 실행 확인 몫이다.
"""
import importlib.util
import os
import shutil
import sys
import unittest

SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
sys.argv = ["scan.py"]
spec = importlib.util.spec_from_file_location("scan", os.path.join(SCRIPTS, "scan.py"))
scan = importlib.util.module_from_spec(spec)
sys.modules["scan"] = scan  # scan 이 하위 모듈에 자기를 sys.modules 로 넘긴다
spec.loader.exec_module(scan)


class WindowsCheck(unittest.TestCase):
    def run_with(self, which):
        real = shutil.which
        shutil.which = lambda c, *a, **kw: which.get(c)
        saved = os.environ.pop("CLAUDE_CODE_GIT_BASH_PATH", None)
        try:
            scan.findings.clear()
            scan.check_windows()
            return [(f["sev"], f["code"]) for f in scan.findings]
        finally:
            shutil.which = real
            if saved is not None:
                os.environ["CLAUDE_CODE_GIT_BASH_PATH"] = saved

    def test_missing(self):
        self.assertEqual(self.run_with({}), [("오류", "WIN-PYTHON3"), ("경고", "WIN-GITBASH")])

    def test_store_alias_stub(self):
        got = self.run_with({"python3": "C:/Users/u/AppData/Local/Microsoft/WindowsApps/python3.exe", "bash": sys.executable})
        self.assertEqual(got, [("경고", "WIN-PYTHON3")])

    def test_ok(self):
        self.assertEqual(self.run_with({"python3": sys.executable, "bash": sys.executable}), [])


if __name__ == "__main__":
    unittest.main()
