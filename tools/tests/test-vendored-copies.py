"""플러그인에 복사해 둔 파일이 원본과 바이트 단위로 같은지 본다. 실행: python3 -I tools/tests/test-vendored-copies.py

플러그인은 서로의 파일을 import 하지 않으므로(각자 따로 설치된다) 공용 코드는 복사한다. 복사본마다 머리(처음 10줄)에
`@copy-of: <원본 경로>` 를 적고, 여기서 원본과의 동일성을 한 곳에서 검사한다. 자기 경로를 적은 파일이 원본이다
(바이트가 같으므로 원본도 같은 표시를 갖는다). 표시는 glob 으로 찾으므로 목록에 안 올려도 빠지지 않는다.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKS = ROOT / "packs"
SCAN = (ROOT / "plugins", PACKS)
SUFFIX = {".py", ".sh", ".luau", ".lua", ".ts", ".js", ".mjs", ".rs", ".toml"}
MARK = re.compile(r"@copy-of:\s*(\S+)")
# 사본이 있어야 하는 곳(없으면 실패): 지워지거나 옮겨진 사본을 알아채려고 둔다. 키는 원본 경로.
EXPECTED = {
    "plugins/q/scripts/compact_epoch.py": ["plugins/qwreey-advisor/hooks/compact_epoch.py", "plugins/qwreey-conventions/hooks/compact_epoch.py", "plugins/qwreey-sessions/scripts/compact_epoch.py", "plugins/qwreey-workspace/scripts/compact_epoch.py"],
    "plugins/qwreey-conventions/hooks/memory_signals.py": ["plugins/q/skills/doctor/scripts/memory_signals.py"],
}

# PreCompact 에서 요약기에게 다시 실릴 블록을 빼라고 하는 문장. 정본과 사본(따로 설치되는 플러그인, 다른 저장소의 Rust).
OMIT_SOURCE = "plugins/q/scripts/ambient.py"
OMIT_COPIES = [
    "plugins/qwreey-advisor/hooks/ambient.py",
    "plugins/qwreey-operator/hooks/ambient.py",
    "plugins/qwreey-workspace/scripts/ambient.py",
    "../coderag/crates/coderag-core/src/rules/ledger.rs",
]
OMIT_LINE = re.compile(r'OMIT_LINE(?::\s*&str)?\s*=\s*"([^"]*)"')


def file_marks():
    """{표시한 파일 경로(저장소 기준): 원본 경로}. 머리 10줄 안의 `#이름` 없는 표시만 파일 사본 표시로 본다."""
    out = {}
    for base in SCAN:
        for p in base.rglob("*"):
            if p.suffix not in SUFFIX or "__pycache__" in p.parts or not p.is_file():
                continue
            head = "\n".join(p.read_bytes()[:2000].decode("utf-8", "replace").split("\n")[:10])
            m = MARK.search(head)
            if m and "#" not in m.group(1):
                out[p.relative_to(ROOT).as_posix()] = m.group(1)
    return out


class VendoredCopies(unittest.TestCase):
    def test_copies_match_source(self):
        marks = file_marks()
        sources = {t for t in marks.values()}
        for src in sources:
            self.assertEqual(marks.get(src), src, f"{src}: 원본 자신의 머리에 `@copy-of: {src}` 가 없다")
            want = (ROOT / src).read_bytes()
            for rel, target in marks.items():
                if target == src and rel != src:
                    self.assertEqual((ROOT / rel).read_bytes(), want, f"{rel} 이 원본 {src} 와 다르다. 원본을 고치고 복사한다")
        for src, copies in EXPECTED.items():
            for rel in copies:
                self.assertEqual(marks.get(rel), src, f"{rel} 사본이 없거나 `@copy-of: {src}` 표시가 없다")

    def test_omit_line_copies_match(self):
        # 한 문장 상수는 reuse-check 의 값 사본 검사(문자열 묶음)가 풀지 못하므로 여기서 비교한다.
        # 형제 저장소 coderag 의 Rust 사본은 그 저장소가 옆에 있을 때만 본다.
        want = OMIT_LINE.search((ROOT / OMIT_SOURCE).read_text(encoding="utf-8"))
        self.assertIsNotNone(want, f"{OMIT_SOURCE}: OMIT_LINE 정의가 없다")
        for rel in OMIT_COPIES:
            path = ROOT / rel
            if rel.startswith("../") and not path.exists():
                continue
            got = OMIT_LINE.search(path.read_text(encoding="utf-8"))
            self.assertIsNotNone(got, f"{rel}: OMIT_LINE 정의가 없다")
            self.assertEqual(got.group(1), want.group(1), f"{rel}: OMIT_LINE 이 {OMIT_SOURCE} 와 다르다")

    def test_packs_carry_no_rule_injector(self):
        # 팩 rule 은 coderag 플러그인이 넣는다. 팩이 자기 훅을 또 싣으면 같은 rule 이 두 번 실린다.
        for hooks in PACKS.glob("*/hooks"):
            self.assertFalse((hooks / "rules_inject.py").exists(), f"{hooks.relative_to(ROOT)}/rules_inject.py: 이중 주입이 된다")


if __name__ == "__main__":
    unittest.main()
