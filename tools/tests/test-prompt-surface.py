"""모델이 보는 글(prompt surface)이 커밋한 스냅숏과 같은지, 크기가 늘지 않았는지 본다. 실행: python3 -I tools/tests/test-prompt-surface.py

글은 tools/regen-prompt-surface.py 의 collect() 가 모은다(훅은 하위 프로세스로, 고정 salt). 스냅숏은 tools/tests/prompt-surface/*.txt,
크기는 sizes.json. 일부러 바꾼 문구면 다시 만든다(tools/tests/README.md). 크기는 래칫이다: 줄면 통과하고 sizes.json 을 낮추라고 알리고,
늘거나 새 항목이면 실패한다(`--allow-growth` 로 올리고 커밋 메시지에 이유를 적는다).
"""
import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("regen_prompt_surface", ROOT / "tools" / "regen-prompt-surface.py")
regen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(regen)


class PromptSurface(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.items = regen.collect()
        cls.saved = regen.snapshot_files()
        cls.sizes = regen.load_sizes()

    def test_snapshot_matches(self):
        lines = regen.diff(self.saved, self.items)
        if lines:
            self.fail("prompt surface differs from the snapshot. If the change is meant, run `%s` and commit the result.\n%s"
                      % (regen.REGEN, "\n".join(lines)))

    def test_size_ratchet(self):
        old = self.sizes.get("items", {})
        grew = [(k, old.get(k, 0), len(v)) for k, v in self.items.items() if k not in old or len(v) > old[k]]
        gone = sorted(set(old) - set(self.items))
        shrank = [(k, old[k], len(v)) for k, v in self.items.items() if k in old and len(v) < old[k]]
        if shrank or gone:
            print("\nprompt surface shrank; lower sizes.json with `%s`:" % regen.REGEN, file=sys.stderr)
            for k, a, b in shrank:
                print("  %s: %d -> %d" % (k, a, b), file=sys.stderr)
            for k in gone:
                print("  %s: removed" % k, file=sys.stderr)
        if grew:
            self.fail("items grew past sizes.json (new items count from 0). Shrink them, or run `%s --allow-growth` and give the "
                      "reason in the commit message:\n%s" % (regen.REGEN, "\n".join("  %s: %d -> %d" % g for g in grew)))

    def test_totals_consistent(self):
        self.assertEqual(self.sizes.get("totals"), regen.totals(self.sizes.get("items", {})),
                         "sizes.json totals do not match its items; run `%s`" % regen.REGEN)

    def test_hook_output_budget(self):
        over = [(k, len(v)) for k, v in self.items.items() if regen.is_hook_output(k) and len(v) >= regen.HOOK_BUDGET]
        self.assertEqual(over, [], "a single hook output must stay under %d chars" % regen.HOOK_BUDGET)

    def test_report_session_start_total(self):
        t = regen.totals({k: len(v) for k, v in self.items.items()})
        print("\nsession start: %(session_start)d chars (hooks %(session_start_hooks)d, skill/agent/tool listings %(session_start_listings)d); "
              "subagent start hooks %(subagent_start_hooks)d; enabled packs add %(packs_listings)d" % t, file=sys.stderr)
        self.assertGreater(t["session_start_hooks"], 0)


if __name__ == "__main__":
    unittest.main()
