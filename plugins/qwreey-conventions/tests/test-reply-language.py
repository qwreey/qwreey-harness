#!/usr/bin/env python3
"""reply_language 훅 회귀. 실행: python3 -I test-reply-language.py  (exit 0 = 통과)

문턱 판정, 언어 출처 순서, set 명령, 물어보기(세션당 한 번), Stop block 과 stop_hook_active 통과, PostToolBatch 의 중간 텍스트 감지
(마지막 줄이 덜 써진 경우 포함)와 도구 호출 카운터, 로그에 본문이 없음을 본다. 상태는 TMPDIR 로 격리한다.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOKS = os.path.join(ROOT, "hooks")
HOOK = os.path.join(HOOKS, "reply_language.py")
T = tempfile.mkdtemp(prefix="reply-lang-")
CFG = os.path.join(T, "cfg")
PROJ = os.path.join(T, "proj")
DATA = os.path.join(T, "data")
os.makedirs(CFG)
os.makedirs(os.path.join(PROJ, ".claude"))
sys.path.insert(0, HOOKS)
import reply_language as rl  # noqa: E402

KO = "파일을 읽고 함수를 추가했습니다. 테스트도 통과했고 따로 걸리는 점은 없습니다."
EN = "I read the file and added the function. The tests pass and nothing else needs attention."
_n = [0]


def fresh():
    _n[0] += 1
    return "ls%d" % _n[0]


def write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False)


def set_language(where, lang):
    paths = {"user": os.path.join(CFG, "settings.json"), "project": os.path.join(PROJ, ".claude", "settings.json"),
             "local": os.path.join(PROJ, ".claude", "settings.local.json"), "store": os.path.join(DATA, "language.json")}
    write_json(paths[where], {"language": lang})


def clear_language():
    for p in (os.path.join(CFG, "settings.json"), os.path.join(PROJ, ".claude", "settings.json"),
              os.path.join(PROJ, ".claude", "settings.local.json"), os.path.join(DATA, "language.json"),
              os.path.join(DATA, "drift.jsonl")):
        if os.path.exists(p):
            os.remove(p)


def env(extra=None):
    e = dict(os.environ, TMPDIR=T, CLAUDE_CONFIG_DIR=CFG, CLAUDE_PROJECT_DIR=PROJ, CLAUDE_PLUGIN_DATA=DATA)
    e.pop("HARNESS_REPLY_LANGUAGE", None)
    e.update(extra or {})
    return e


def hook(event, session, extra=None, agent=None, e=None, **fields):
    p = {"hook_event_name": event, "session_id": session, "cwd": PROJ}
    p.update(fields)
    if agent:
        p["agent_id"] = agent
    r = subprocess.run([sys.executable, "-I", HOOK], input=json.dumps(p), capture_output=True, text=True, env=e or env(extra))
    return json.loads(r.stdout) if r.stdout.strip() else None


def ctx(out):
    return ((out or {}).get("hookSpecificOutput") or {}).get("additionalContext", "")


def stop(session, msg, **kw):
    return hook("Stop", session, last_assistant_message=msg, stop_hook_active=kw.pop("active", False), **kw)


def log_lines():
    try:
        with open(os.path.join(DATA, "drift.jsonl"), encoding="utf-8") as f:
            return [json.loads(x) for x in f]
    except OSError:
        return []


class Base(unittest.TestCase):
    def setUp(self):
        clear_language()


class Detection(unittest.TestCase):
    def test_script_for(self):
        for lang, want in (("korean", "hangul"), ("Korean (한국어)", "hangul"), ("한국어", "hangul"), ("ko-KR", "hangul"), ("Japanese", "japanese"),
                           ("zh-CN", "han"), ("russian", "cyrillic"), ("English", None), ("Spanish", None), ("", None), (None, None)):
            self.assertEqual(rl.script_for(lang), want, lang)

    def test_threshold(self):
        self.assertFalse(rl.is_drift(KO, "hangul")[0])
        self.assertTrue(rl.is_drift(EN, "hangul")[0])
        self.assertFalse(rl.is_drift("Short English.", "hangul")[0])  # 라틴 20자 미만
        self.assertFalse(rl.is_drift("No response requested.", "hangul")[0])
        mixed = "커밋했습니다. 변경은 `src/very/long/path/file_name.luau` 와 https://example.com/a/b/c 와 " + "```\nlocal function helperThatIsLong() end\n```"
        self.assertFalse(rl.is_drift(mixed, "hangul")[0])  # 코드·경로·URL 은 뗀다
        terms = "이번 변경은 cache invalidation 과 retry policy 를 손봤고 대부분의 로직은 그대로입니다. 나머지는 그대로 두었습니다."
        self.assertFalse(rl.is_drift(terms, "hangul")[0])
        self.assertTrue(rl.is_drift("완료. " + EN * 3, "hangul")[0])

    def test_other_scripts(self):
        self.assertFalse(rl.is_drift("ファイルを読んで関数を追加しました。テストも通りました。", "japanese")[0])
        self.assertTrue(rl.is_drift(EN, "japanese")[0])
        self.assertFalse(rl.is_drift("Я прочитал файл и добавил функцию. Тесты проходят успешно.", "cyrillic")[0])


class Resolution(Base):
    def test_order_narrowest_wins(self):
        set_language("store", "english")
        os.environ["CLAUDE_CONFIG_DIR"], os.environ["CLAUDE_PROJECT_DIR"], os.environ["CLAUDE_PLUGIN_DATA"] = CFG, PROJ, DATA
        self.assertEqual(rl.resolve_language({}), "english")  # 설정이 없으면 저장소
        set_language("user", "korean")
        self.assertEqual(rl.resolve_language({}), "korean")
        set_language("project", "japanese")
        self.assertEqual(rl.resolve_language({}), "japanese")
        set_language("local", "russian")
        self.assertEqual(rl.resolve_language({}), "russian")

    def test_set_subcommand(self):
        out = subprocess.run([sys.executable, "-I", HOOK, "set", "Korean", "--data", DATA], capture_output=True, text=True, env=env())
        self.assertEqual(out.returncode, 0)
        with open(os.path.join(DATA, "language.json"), encoding="utf-8") as f:
            self.assertEqual(json.load(f)["language"], "Korean")
        # CLAUDE_PLUGIN_DATA 가 없는 Bash: <config>/plugins/data/qwreey-conventions-* 를 찾는다
        d2 = os.path.join(CFG, "plugins", "data", "qwreey-conventions-market")
        os.makedirs(d2)
        e = env()
        e.pop("CLAUDE_PLUGIN_DATA")
        subprocess.run([sys.executable, "-I", HOOK, "set", "Japanese"], capture_output=True, text=True, env=e)
        with open(os.path.join(d2, "language.json"), encoding="utf-8") as f:
            self.assertEqual(json.load(f)["language"], "Japanese")
        self.assertEqual(subprocess.run([sys.executable, "-I", HOOK, "set"], capture_output=True, text=True, env=env()).returncode, 2)


class Ask(Base):
    def test_ask_once_per_session(self):
        s = fresh()
        out = hook("UserPromptSubmit", s, prompt="hi")
        c = ctx(out)
        self.assertIn('level="action"', c)
        self.assertIn(HOOK, c)
        self.assertIn(DATA, c)
        self.assertIn("/config", c)
        self.assertIsNone(hook("UserPromptSubmit", s, prompt="again"))
        self.assertTrue(hook("UserPromptSubmit", fresh(), prompt="new session"))

    def test_no_ask_when_language_set(self):
        set_language("user", "korean")
        self.assertIsNone(hook("UserPromptSubmit", fresh(), prompt="hi"))

    def test_subagent_skipped(self):
        self.assertIsNone(hook("UserPromptSubmit", fresh(), agent="a1", prompt="hi"))


class StopBlock(Base):
    def test_block_then_pass(self):
        set_language("user", "Korean")
        s = fresh()
        out = stop(s, EN)
        self.assertEqual(out["decision"], "block")
        self.assertIn("Korean", out["reason"])
        self.assertIn("Do not mention this notice", out["reason"])
        self.assertIsNone(stop(s, EN, active=True))  # 두 번째 Stop 은 통과
        kinds = [r["kind"] for r in log_lines()]
        self.assertEqual(kinds, ["stop_block", "stop_still_drifted"])
        for r in log_lines():
            self.assertEqual(set(r), {"ts", "session", "kind", "ratio", "length"})
            self.assertNotIn("read the file", json.dumps(r))

    def test_clean_reply_and_no_language(self):
        set_language("user", "Korean")
        self.assertIsNone(stop(fresh(), KO))
        self.assertIsNone(stop(fresh(), "No response requested."))
        clear_language()
        self.assertIsNone(stop(fresh(), EN))

    def test_latin_language_only_logs(self):
        set_language("user", "English")
        self.assertIsNone(stop(fresh(), EN))
        self.assertEqual([r["kind"] for r in log_lines()], ["stop_latin_skip"])

    def test_main_only_and_off(self):
        set_language("user", "Korean")
        self.assertIsNone(stop(fresh(), EN, agent="sub1"))
        self.assertIsNone(hook("Stop", fresh(), e=env({"HARNESS_REPLY_LANGUAGE": "off"}), last_assistant_message=EN, stop_hook_active=False))


def line(text, sidechain=False, typ="assistant"):
    j = {"type": typ, "isSidechain": sidechain, "message": {"role": typ, "content": [{"type": "text", "text": text}]}}
    return json.dumps(j, ensure_ascii=False) + "\n"


def batch(session, tp, prompt="p1", n=1):
    return hook("PostToolBatch", session, prompt_id=prompt, transcript_path=tp, tool_calls=[{"tool_name": "Read"}] * n)


class Batch(Base):
    def setUp(self):
        super().setUp()
        set_language("user", "Korean")
        self.tp = os.path.join(T, "tr%d.jsonl" % _n[0])
        _n[0] += 1

    def append(self, s):
        with open(self.tp, "a", encoding="utf-8") as f:
            f.write(s)

    def test_interim_drift_partial_line_and_cooldown(self):
        s = fresh()
        self.append(line(KO))
        self.assertEqual(ctx(batch(s, self.tp)), "")
        full = line(EN)
        self.append(full[:40])  # 덜 써진 마지막 줄은 소비하지 않는다
        self.assertEqual(ctx(batch(s, self.tp)), "")
        self.append(full[40:])
        c = ctx(batch(s, self.tp))
        self.assertIn('level="warn"', c)
        self.assertIn("Korean", c)
        self.append(line(EN))
        self.assertEqual(ctx(batch(s, self.tp)), "")  # 쿨다운
        self.assertEqual([r["kind"] for r in log_lines()], ["interim_drift"])

    def test_sidechain_and_user_lines_ignored(self):
        s = fresh()
        self.append(line(EN, sidechain=True) + line(EN, typ="user"))
        self.assertEqual(ctx(batch(s, self.tp)), "")

    def test_counter_10_then_every_15(self):
        s = fresh()
        fired = []
        for i in range(1, 60):
            if "Reply to the user in Korean" in ctx(batch(s, self.tp)):
                fired.append(i)
        self.assertEqual(fired, [10, 25, 40, 55])

    def test_counter_resets_per_prompt_and_counts_batch_size(self):
        s = fresh()
        self.assertIn('level="info"', ctx(batch(s, self.tp, "pA", n=10)))
        self.assertEqual(ctx(batch(s, self.tp, "pA", n=3)), "")
        self.assertEqual(ctx(batch(s, self.tp, "pB", n=9)), "")
        self.assertTrue(ctx(batch(s, self.tp, "pB", n=1)))

    def test_missing_transcript_and_subagent(self):
        s = fresh()
        self.assertEqual(ctx(batch(s, os.path.join(T, "nope.jsonl"))), "")
        self.assertIsNone(hook("PostToolBatch", s, agent="a1", prompt_id="x", transcript_path=self.tp, tool_calls=[{}] * 20))


if __name__ == "__main__":
    unittest.main()
