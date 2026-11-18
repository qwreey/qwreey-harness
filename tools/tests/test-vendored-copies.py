"""플러그인과 coderag 에 둔 사본이 lib/ 정본과 같은지 본다. 실행: python3 -I tools/tests/test-vendored-copies.py

플러그인은 서로의 파일을 import 하지 않으므로(각자 따로 설치된다) 공용 코드와 문구는 lib/ 에 정본을 두고 복사한다.
같은지는 tools/sync-copies.py --check 가 표시(파일 사본, 영역 사본)를 따라 본다. 여기 목록은 사본이 있어야 하는 곳이다:
표시째 지워지거나 옮겨진 사본은 --check 가 알아채지 못한다.
"""
import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKS = ROOT / "packs"
sys.path.insert(0, str(ROOT / "lib"))
import copy_regions  # noqa: E402

# 키는 정본 경로(저장소 기준), 값은 파일 사본.
EXPECTED = {
    "lib/compact_epoch.py": ["plugins/q/scripts/compact_epoch.py", "plugins/qwreey-advisor/hooks/compact_epoch.py", "plugins/qwreey-conventions/hooks/compact_epoch.py", "plugins/qwreey-operator/hooks/compact_epoch.py", "plugins/qwreey-sessions/scripts/compact_epoch.py", "plugins/qwreey-workspace/scripts/compact_epoch.py"],
    "lib/memory_signals.py": ["plugins/qwreey-conventions/hooks/memory_signals.py", "plugins/q/skills/doctor/scripts/memory_signals.py"],
    "lib/harness_nonce.py": ["plugins/q/scripts/harness_nonce.py", "plugins/qwreey-advisor/hooks/harness_nonce.py", "plugins/qwreey-conventions/hooks/harness_nonce.py", "plugins/qwreey-operator/hooks/harness_nonce.py", "plugins/qwreey-proc-guard/hooks/harness_nonce.py", "plugins/qwreey-reply-language/hooks/harness_nonce.py", "plugins/qwreey-sessions/scripts/harness_nonce.py", "plugins/qwreey-workspace/scripts/harness_nonce.py"],
    "lib/copy_regions.py": ["plugins/qwreey-conventions/hooks/copy_regions.py"],
    "lib/file_lock.py": ["plugins/q/scripts/file_lock.py", "plugins/qwreey-sessions/scripts/sllib/file_lock.py"],
    "home/.claude/lib/harness_env.py": ["plugins/q/scripts/harness_env.py", "plugins/q/skills/doctor/scripts/harness_env.py", "plugins/qwreey-advisor/hooks/harness_env.py", "plugins/qwreey-conventions/hooks/harness_env.py", "plugins/qwreey-delegate/skills/delegate/scripts/harness_env.py", "plugins/qwreey-operator/hooks/harness_env.py", "plugins/qwreey-proc-guard/hooks/harness_env.py", "plugins/qwreey-reply-language/hooks/harness_env.py", "plugins/qwreey-sessions/scripts/harness_env.py", "plugins/qwreey-workspace/scripts/harness_env.py"],
    "lib/known_repos.py": ["plugins/qwreey-conventions/hooks/known_repos.py", "plugins/qwreey-workspace/scripts/known_repos.py"],
    "lib/ambient.py": ["plugins/q/scripts/ambient.py", "plugins/qwreey-advisor/hooks/ambient.py", "plugins/qwreey-operator/hooks/ambient.py", "plugins/qwreey-workspace/scripts/ambient.py"],
}
# 키는 정본 영역(<경로>#<이름>), 값은 그 영역의 사본을 둔 파일. ../ 로 시작하는 형제 저장소는 옆에 있을 때만 본다.
REGIONS = {
    "lib/harness_texts.py#OMIT_LINE": ["lib/ambient.py", "../coderag/crates/coderag-core/src/rules/ledger.rs"],
    "lib/harness_texts.py#NONCE_RULE": ["lib/harness_nonce.py", "../coderag/crates/coderag-core/src/hooktag.rs"],
    "lib/harness_texts.py#STOP_ERROR": ["plugins/qwreey-advisor/hooks/second-opinion-nudge.py", "plugins/qwreey-operator/hooks/subagent-bg-tasks.py"],
}
# 표시 없이 바이트째 같아야 하는 사본. 데이터 파일이라 머리에 표시 줄을 넣으면 출처 기록의 md5 가 어긋난다.
# 정본을 고친 뒤 사본 자리에 그대로 복사한다(sync-copies 가 다루지 않는다).
UNMARKED = {
    "packs/luau-kb/typedefs/globalTypes.d.luau": ["plugins/luau-lsp/definitions/globalTypes.d.luau"],
}


class VendoredCopies(unittest.TestCase):
    def test_copies_match_canon(self):
        p = subprocess.run([sys.executable, "-I", str(ROOT / "tools" / "sync-copies.py"), "--check"], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)

    def test_expected_file_copies_exist(self):
        for src, copies in EXPECTED.items():
            self.assertEqual(copy_regions.file_copy_target((ROOT / src).read_text(encoding="utf-8")), src, f"{src}: 정본 머리에 자기 경로 표시가 없다")
            for rel in copies:
                path = ROOT / rel
                self.assertTrue(path.is_file(), f"{rel} 사본이 없다")
                self.assertEqual(copy_regions.file_copy_target(path.read_text(encoding="utf-8")), src, f"{rel}: 머리에 `@copy-of: {src}` 표시가 없다")

    def test_unmarked_copies_match(self):
        for src, copies in UNMARKED.items():
            want = (ROOT / src).read_bytes()
            for rel in copies:
                self.assertTrue((ROOT / rel).read_bytes() == want, f"{rel} 가 {src} 와 다르다: cp {src} {rel}")

    def test_expected_region_copies_exist(self):
        for key, files in REGIONS.items():
            src, name = key.rsplit("#", 1)
            for rel in files:
                path = ROOT / rel
                if rel.startswith("../") and not path.parent.exists():
                    continue
                regions, errors = copy_regions.parse_regions(path.read_text(encoding="utf-8"))
                self.assertEqual(errors, [], rel)
                prefix = os.path.relpath(ROOT, copy_regions.repo_root(str(path))) if rel.startswith("../") else ""
                want = os.path.normpath(os.path.join(prefix, src))
                self.assertTrue(any(r["name"] == name and os.path.normpath(r["path"]) == want for r in regions), f"{rel}: {key} 영역 사본이 없다")

    def test_packs_carry_no_rule_injector(self):
        # 팩 rule 은 coderag 플러그인이 넣는다. 팩이 자기 훅을 또 싣으면 같은 rule 이 두 번 실린다.
        for hooks in PACKS.glob("*/hooks"):
            self.assertFalse((hooks / "rules_inject.py").exists(), f"{hooks.relative_to(ROOT)}/rules_inject.py: 이중 주입이 된다")


if __name__ == "__main__":
    unittest.main()
