#!/usr/bin/env python3
"""플러그인에 복사해 둔 파일이 정본과 바이트 단위로 같은지 본다. 실행: python3 -I tools/tests/test-vendored-copies.py

플러그인은 서로의 파일을 import 하지 않으므로(각자 따로 설치된다) 공용 코드는 복사한다. 복사본마다 머리 주석에 정본을 적고,
여기서 정본과의 동일성을 한 곳에서 검사한다. 새 사본은 glob 으로 찾으므로 목록에 안 올려도 빠지지 않는다.
"""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLUGINS = ROOT / "plugins"
# 파일 이름 -> 정본 경로(저장소 루트 기준)
CANON = {
    "compact_epoch.py": "plugins/q/scripts/compact_epoch.py",
    "memory_signals.py": "plugins/qwreey-conventions/hooks/memory_signals.py",
    "rules_inject.py": "plugins/qwreey-conventions/hooks/rules_inject.py",
    "conv_env.py": "plugins/qwreey-conventions/hooks/conv_env.py",
}
# 사본이 있어야 하는 곳(없으면 실패): 지워지거나 옮겨진 사본을 알아채려고 둔다
EXPECTED = {
    "compact_epoch.py": ["plugins/qwreey-advisor/hooks", "plugins/qwreey-conventions/hooks", "plugins/web-security/hooks"],
    "memory_signals.py": ["plugins/q/skills/doctor/scripts"],
    "rules_inject.py": ["plugins/web-security/hooks"],
    "conv_env.py": ["plugins/web-security/hooks"],
}


class VendoredCopies(unittest.TestCase):
    def test_copies_match_canon(self):
        for name, canon in CANON.items():
            want = (ROOT / canon).read_bytes()
            head = want[:700].decode("utf-8", "replace")
            self.assertTrue("정본" in head or "Canonical" in head, f"{canon}: 머리 주석에 정본 표시가 없다")
            copies = [p for p in PLUGINS.rglob(name) if p != ROOT / canon and "__pycache__" not in p.parts]
            for rel in EXPECTED[name]:
                self.assertIn(ROOT / rel / name, copies, f"{rel}/{name} 사본이 없다")
            for c in copies:
                self.assertEqual(c.read_bytes(), want, f"{c.relative_to(ROOT)} 이 정본 {canon} 과 다르다. 정본을 고치고 복사한다")


if __name__ == "__main__":
    unittest.main()
