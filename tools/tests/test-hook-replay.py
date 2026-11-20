"""훅 판정 재생 묶음. 실행: python3 -I tools/tests/test-hook-replay.py  (모델 호출 없음)

tools/tests/hook-replay/cases/*.json 하나가 사례 하나다. 사례마다 새 샌드박스(tools/tests/hook_sandbox.py)를 만들고 파일과 준비 명령을
놓은 뒤 단계를 차례로 돌린다. 사례를 더하려면 JSON 파일 하나를 더한다. 형식(문자열 안의 {repo} 등은 hook_sandbox 의 자리 표시):

  {"description": "무엇을 지키는지 한 줄",
   "files": {"<저장소 기준 경로 또는 {자리}/경로>": 글 | [JSONL 줄] | {"repeat": 글, "times": N} | {"text"|"jsonl": ..., "mtime_ago": 초}},
   "setup": ["<저장소에서 돌릴 bash 명령>", ...],
   "env": {"<사례 전체 환경 변수>": "값"},
   "steps": [
     {"hook": "<이 저장소 기준 스크립트 경로>", "argv": [...], "payload": {...}, "env": {...},
      "expect": {"exit": 0, "empty": true|false, "decision": "deny"|null, "tags": ["<name>/<level>", "plugin:<name>"],
                 "no_tags": ["<name>"], "contains": [...], "not_contains": [...], "max_chars": N}},
     {"sh": "<저장소에서 돌릴 bash 명령>"},
     {"write": {"<경로>": 글, ...}}]}

payload 에 session_id 가 없으면 "s1", cwd 가 없으면 "{repo}" 를 넣는다. 태그는 그 세션의 고정 salt nonce 를 달아야 맞은 것으로 본다.
contains 와 not_contains 는 출력에서 모델(과 systemMessage)에게 가는 글을 기계 경로를 지운 꼴(<sandbox>, <root>)로 본다.
"""
import json
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # python3 -I 는 스크립트 디렉터리를 path 에 넣지 않는다
from hook_sandbox import ROOT, Sandbox, SetupFailed, nonce, replay  # noqa: E402

CASES = Path(__file__).resolve().parent / "hook-replay" / "cases"
CASE_KEYS = {"description", "files", "setup", "env", "steps"}
STEP_KEYS = {"hook", "argv", "payload", "env", "expect", "sh", "write", "note"}
EXPECT_KEYS = {"exit", "empty", "decision", "tags", "no_tags", "contains", "not_contains", "max_chars"}


def tag_present(text, spec, sid):
    """spec 은 "<name>/<level>"(harness-hook) 또는 "plugin:<name>". 그 세션의 nonce 를 단 태그가 있나."""
    n = re.escape(nonce(sid))
    if spec.startswith("plugin:"):
        return re.search(r'<plugin name="%s" nonce="%s">' % (re.escape(spec[7:]), n), text) is not None
    name, level = spec.split("/")
    return re.search(r'<harness-hook name="%s" level="%s" nonce="%s">' % (re.escape(name), re.escape(level), n), text) is not None


def check(result, expect, sid, sb):
    """어긋난 점의 목록(빈 목록이면 통과)."""
    text = sb.normalize(result.text())
    raw = result.text()
    bad = []
    if result.rc != expect.get("exit", 0):
        bad.append("exit %d, expected %d (stderr: %s)" % (result.rc, expect.get("exit", 0), result.stderr[-400:]))
    if "empty" in expect and (not result.stdout.strip()) != expect["empty"]:
        bad.append("output is %s" % ("empty" if not result.stdout.strip() else "not empty"))
    if "decision" in expect and result.decision() != expect["decision"]:
        bad.append("decision %r, expected %r" % (result.decision(), expect["decision"]))
    for spec in expect.get("tags", []):
        if not tag_present(raw, spec, sid):
            bad.append("missing tag %s with nonce %s" % (spec, nonce(sid)))
    for name in expect.get("no_tags", []):
        if re.search(r'<(?:harness-hook|plugin) name="%s"' % re.escape(name), raw):
            bad.append("unexpected tag %s" % name)
    for s in expect.get("contains", []):
        if sb.subst(s) not in text and sb.subst(s) not in raw:
            bad.append("missing phrase %r" % s)
    for s in expect.get("not_contains", []):
        if sb.subst(s) in text or sb.subst(s) in raw:
            bad.append("unexpected phrase %r" % s)
    if "max_chars" in expect and len(raw) > expect["max_chars"]:
        bad.append("%d chars, over %d" % (len(raw), expect["max_chars"]))
    return bad


def run_case(path):
    """사례 하나를 돌리고 어긋난 점을 [문장] 으로 돌려준다."""
    case = json.loads(path.read_text(encoding="utf-8"))
    errors = ["unknown case key %s" % k for k in set(case) - CASE_KEYS]
    if not case.get("description") or not case.get("steps"):
        errors.append("a case needs description and steps")
    with Sandbox(prefix="hook-replay-") as sb:
        try:
            for i, step, payload, env in replay(case, sb):
                where = "step %d" % i
                errors += ["%s: unknown key %s" % (where, k) for k in set(step) - STEP_KEYS]
                errors += ["%s: unknown expect key %s" % (where, k) for k in set(step.get("expect") or {}) - EXPECT_KEYS]
                if payload is None:
                    continue
                if not (ROOT / step["hook"]).is_file():
                    errors.append("%s: no hook script %s" % (where, step["hook"]))
                    continue
                result = sb.run(step["hook"], payload, argv=step.get("argv") or (), env=env)
                for msg in check(result, step.get("expect") or {}, payload["session_id"], sb):
                    errors.append("%s (%s): %s\n    output: %s" % (where, step["hook"].rsplit("/", 1)[-1], msg,
                                                                   sb.normalize(result.text())[:600].replace("\n", "\n    ")))
        except SetupFailed as e:
            return errors + [str(e)]
    return errors


class HookReplay(unittest.TestCase):
    def test_cases(self):
        paths = sorted(CASES.glob("*.json"))
        self.assertGreater(len(paths), 0, "no cases in %s" % CASES)
        for path in paths:
            with self.subTest(case=path.name):
                errors = run_case(path)
                self.assertEqual(errors, [], "%s:\n%s" % (path.name, "\n".join(errors)))


if __name__ == "__main__":
    unittest.main()
