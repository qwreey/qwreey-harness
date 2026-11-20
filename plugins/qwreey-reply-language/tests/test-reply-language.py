#!/usr/bin/env python3
"""reply_language 훅 회귀. 실행: python3 -I test-reply-language.py  (exit 0 = 통과)

문턱 판정, 언어 출처 순서, set 명령, 물어보기(세션당 한 번), Stop block 과 stop_hook_active 통과, PostToolBatch 의 중간 텍스트 감지
(마지막 줄이 덜 써진 경우 포함)와 도구 호출 카운터, 로그에 본문이 없음을 본다. 상태는 TMPDIR 로 격리한다.
"""
import json
import os
import random
import re
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOKS = os.path.join(ROOT, "hooks")
HOOK = os.path.join(HOOKS, "reply_language.py")
# HOOK_TEST_BIN=<바이너리> 면 훅 실행(set 빼고)을 python 스크립트 대신 `<바이너리> hook reply-language` 로 돌린다
# (Rust 판, crates/qwreey-reply-language). 바이너리는 플러그인 폴더를 CLAUDE_PLUGIN_ROOT 로 안다.
BIN = os.environ.get("HOOK_TEST_BIN")
CMD = [BIN, "hook", "reply-language"] if BIN else [sys.executable, "-I", HOOK]
T = tempfile.mkdtemp(prefix="reply-lang-")
# nonce 는 고정 salt 로(실제 ~/.local/share 의 salt 를 쓰지 않게)
open(os.path.join(T, "salt"), "w").write("00" * 32)
os.environ["QWREEY_HARNESS_SALT_FILE"] = os.path.join(T, "salt")
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
    if BIN:
        e["CLAUDE_PLUGIN_ROOT"] = ROOT
    e.update(extra or {})
    return e


def hook(event, session, extra=None, agent=None, e=None, **fields):
    p = {"hook_event_name": event, "session_id": session, "cwd": PROJ}
    p.update(fields)
    if agent:
        p["agent_id"] = agent
    r = subprocess.run(CMD, input=json.dumps(p), capture_output=True, text=True, env=e or env(extra))
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
        self.assertFalse(rl.is_drift(mixed, "hangul")[0])  # 코드, 경로, URL 은 뗀다
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
        # CLAUDE_PLUGIN_DATA 가 없는 Bash: <config>/plugins/data/qwreey-reply-language-* 를 찾는다
        d2 = os.path.join(CFG, "plugins", "data", "qwreey-reply-language-market")
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
        self.assertIn('level="info"', c)  # 첫 요청을 막지 않는다
        self.assertIn("Answer the user's request first", c)
        self.assertIn("at the end of that reply", c)
        self.assertNotIn("Before answering", c)
        self.assertIn(HOOK, c)
        self.assertIn(DATA, c)
        self.assertNotIn("/config", c)  # /config 가 language 를 노출하는지 문서로 확인하지 못했다
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
        self.assertIn("explicitly asked in this turn", out["reason"])
        self.assertIn("output only the rewritten reply", out["reason"].replace("Otherwise o", "o"))
        self.assertNotIn("the rewrite is all the user should see", out["reason"])
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

    def test_off_through_option_and_repo_layer(self):
        # /config 옵션(settings.json pluginConfigs)과 저장소 harness.env 층도 끈다. 환경 변수가 둘 다 이긴다.
        opt = {"language": "Korean", "pluginConfigs": {"qwreey-reply-language@m": {"options": {"harness_reply_language": False}}}}
        write_json(os.path.join(CFG, "settings.json"), opt)
        self.assertIsNone(stop(fresh(), EN))
        self.assertEqual(stop(fresh(), EN, e=env({"HARNESS_REPLY_LANGUAGE": "on"}))["decision"], "block")
        set_language("user", "Korean")
        repo_env = os.path.join(PROJ, ".claude", "harness.env")
        with open(repo_env, "w", encoding="utf-8") as f:
            f.write("HARNESS_REPLY_LANGUAGE=off\n")
        try:
            self.assertIsNone(stop(fresh(), EN))
        finally:
            os.remove(repo_env)
        self.assertEqual(stop(fresh(), EN)["decision"], "block")


def user_line(text, tool_result=False):
    content = [{"type": "tool_result", "tool_use_id": "x", "content": text}] if tool_result else text
    return json.dumps({"type": "user", "message": {"role": "user", "content": content}}, ensure_ascii=False) + "\n"


class StopUserLanguage(Base):
    """사용자가 목표 문자 체계가 아닌 글로 썼으면 영어 답은 이탈이 아니다."""

    def setUp(self):
        super().setUp()
        set_language("user", "Korean")
        self.tp = os.path.join(T, "stop%d.jsonl" % _n[0])
        _n[0] += 1

    def transcript(self, *lines):
        with open(self.tp, "w", encoding="utf-8") as f:
            f.write("".join(lines))

    def test_english_prompt_passes(self):
        self.transcript(user_line("Please add a retry to the fetch function"), line("working"), user_line("big tool output " * 50, tool_result=True))
        self.assertIsNone(stop(fresh(), EN, transcript_path=self.tp))
        self.assertEqual([r["kind"] for r in log_lines()], ["stop_user_other_script"])

    def test_korean_prompt_still_blocks(self):
        self.transcript(user_line("fetch 함수에 재시도를 추가해 줘"), line("ok"))
        self.assertEqual(stop(fresh(), EN, transcript_path=self.tp)["decision"], "block")

    def test_latest_prompt_wins(self):
        self.transcript(user_line("Please add a retry to the fetch function"), line("x"), user_line("이제 테스트도 추가해 줘"))
        self.assertEqual(stop(fresh(), EN, transcript_path=self.tp)["decision"], "block")

    def test_missing_transcript_or_prompt_falls_back_to_block(self):
        self.assertEqual(stop(fresh(), EN, transcript_path=os.path.join(T, "nope.jsonl"))["decision"], "block")
        self.transcript(line("only assistant"))
        self.assertEqual(stop(fresh(), EN, transcript_path=self.tp)["decision"], "block")

    def test_pasted_english_after_korean_instruction_blocks(self):
        self.transcript(user_line("이 로그를 보고 원인을 찾아 줘\n" + "ERROR connection refused while reading the socket " * 20))
        self.assertEqual(stop(fresh(), EN, transcript_path=self.tp)["decision"], "block")

    def test_pasted_english_first_then_korean_question_blocks(self):
        log = "ERROR connection refused while reading the socket at server.js line 12 in module net\n" * 5
        for body in ("<pasted_content>\n" + log + "</pasted_content>\n이게 왜 나는 거야?", "```\n" + log + "```\n이게 왜 나는 거야?", log + "\n이게 왜 나는 거야?"):
            self.transcript(user_line(body))
            self.assertEqual(stop(fresh(), EN, transcript_path=self.tp)["decision"], "block", body[:20])

    def test_pure_english_prompt_with_paste_skips(self):
        self.transcript(user_line("Why does this fail?\n```\n로그 한글 포함 라인\n```\n<pasted_content>한글 한글 한글</pasted_content>"))
        self.assertIsNone(stop(fresh(), EN, transcript_path=self.tp))


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
        self.assertIn('level="info"', c)
        self.assertNotIn('level="warn"', c)
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


def strip_by_regex(text):
    """strip_text 이전 꼴: 정규식 네 개를 글 전체에 sub 한다(결과의 기준)."""
    for rx in (rl.FENCE, rl.INLINE, rl.URL, rl.PATHLIKE):
        text = rx.sub(" ", text)
    return text


# 긴 줄의 시작 자리마다 줄 끝까지 다시 훑던 글(정규식만으로는 python 3 초 넘게, Rust 판 10 초 넘게 들었다)
SLOW_BEFORE = {
    "x-dot": "x." * 20000,
    "name-dash": "a-" * 20000,
    "scheme-like": "http" * 10000,
    "files-then-path": "see foo.rs and " * 5000 + " a/b",
    "file-chain": "x.foo" * 8000,
}


class LongRuns(unittest.TestCase):
    PIECES = ["a", "x", "Z", "_", "9", "\u00e9", "\u0130", "\u0131", "\u017f", "\u212a", "\u00b2", "\u0903", "한", "\ud800",
              ".", "-", "@", "~", "/", ":", "://", "+", " ", "\n", "\x1c", "\u3000", "www", "WwW.", "rs", "html", "abcdef",
              "http", "a/b", "./", "../", "~/", ".~/", "~~/", "...", "//", "`", "!", "\u00a0", "x.", "a-", "foo.rs", "K", "s"]

    def test_scanners_match_the_regexes(self):
        """긴 줄 훑기가 URL, PATHLIKE 정규식과 같은 일치를 낸다(무작위 글 2만 개, 긴 줄 길로 가게 세 번 이은 글 포함)."""
        rng = random.Random(20261120)
        for _ in range(20000):
            text = "".join(rng.choice(self.PIECES) for _ in range(rng.randint(0, 40)))

            # path_spans takes any text, url_spans one whitespace-free run
            self.assertEqual(rl.path_spans(text), [m.span() for m in rl.PATHLIKE.finditer(text)], repr(text))
            for run in re.findall(r"\S+", text):
                self.assertEqual(rl.url_spans(run), [m.span() for m in rl.URL.finditer(run)], repr(run))

            # Repeating makes runs past LONG_RUN, so strip_text takes the scanner path
            long_text = text * 3
            self.assertEqual(rl.strip_text(long_text), strip_by_regex(long_text), repr(long_text))

    def test_class_sets_follow_python(self):
        """손으로 적은 글자 집합이 모든 코드 포인트에서 python re 의 판정과 같다."""
        az, scheme, w = re.compile(r"[a-z]", re.I), re.compile(r"[a-z0-9+.-]", re.I), re.compile("w", re.I)
        for code in range(sys.maxunicode + 1):
            c = chr(code)
            self.assertEqual(bool(az.fullmatch(c)), c in rl.ICASE_LETTERS, hex(code))
            self.assertEqual(bool(scheme.fullmatch(c)), c in rl.SCHEME_CHARS, hex(code))
            # url_spans checks "www" as w or W only
            self.assertEqual(bool(w.fullmatch(c)), c in "wW", hex(code))

    def test_strip_text_is_linear(self):
        """제곱 시간이던 글을 strip_text 가 0.5 초 안에 뗀다."""
        for name, text in SLOW_BEFORE.items():
            started = time.perf_counter()
            rl.strip_text(text)
            self.assertLess(time.perf_counter() - started, 0.5, name)


class LongRunHooks(Base):
    def setUp(self):
        super().setUp()
        set_language("user", "Korean")

    def test_stop_blocks_in_time(self):
        """제곱 시간이던 답에서 Stop 이 훅 제한(5 초) 한참 안에 block 을 낸다."""
        for name, text in SLOW_BEFORE.items():
            started = time.perf_counter()
            r = hook("Stop", fresh(), last_assistant_message=text)
            self.assertLess(time.perf_counter() - started, 2.0, name)
            # x-dot and file-chain strip down to file names only ("x.x", "x.foo"), so they leave too few Latin letters
            want = None if name in ("x-dot", "file-chain") else "block"
            self.assertEqual((r or {}).get("decision"), want, name)

    def test_batch_reads_in_time_and_saves_the_offset(self):
        """트랜스크립트의 그런 글도 PostToolBatch 가 제때 읽고 오프셋을 저장해 다음 batch 가 다시 읽지 않는다."""
        s = fresh()
        tp = os.path.join(T, "long-%s.jsonl" % s)
        with open(tp, "w", encoding="utf-8") as f:
            f.write(line(SLOW_BEFORE["files-then-path"]))

        # First batch reads the long text and notices the drift
        started = time.perf_counter()
        first = ctx(batch(s, tp))
        self.assertLess(time.perf_counter() - started, 2.0)
        self.assertIn('level="info"', first)

        # The offset moved past it: nothing new to read
        self.assertEqual(ctx(batch(s, tp)), "")
        self.assertEqual([r["kind"] for r in log_lines()], ["interim_drift"])


if __name__ == "__main__":
    unittest.main()
