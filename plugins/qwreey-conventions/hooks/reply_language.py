#!/usr/bin/env python3
"""답변 언어 이탈 감지: 사용자 언어로 답해야 하는데 영어가 섞여 나가면 알리고 다시 쓰게 한다. 메인 대화만(agent_id 가 있으면 건너뜀).

왜: 한글 프롬프트 1,264턴 중 35턴(2.8%)이 영어로 답했고 긴 도구 실행 뒤에 많으며 한번 넘어가면 이어진다(audit/33 A).
  비율이 이봉이라 "목표 문자 비율 < 0.25 이면서 라틴 글자 20자 이상"이 깨끗한 문턱이다.
이벤트
  UserPromptSubmit : 언어를 알 수 없으면 (세션당 한 번) info 알림: 요청에 먼저 답하고, 답 끝에서 어느 언어로 답할지 물어 `set` 으로 저장하게 한다.
                     첫 요청을 질문으로 막지 않으려고 action 이 아니다.
  Stop             : 마지막 답변(last_assistant_message)이 이탈이면 decision=block 으로 다시 쓰게 한다. stop_hook_active 면 통과(루프 방지).
                     block 직전에만 트랜스크립트 끝에서 마지막 실제 사용자 프롬프트를 읽어, 코드·붙여 넣은 글·URL·경로를 뗀 뒤
                     목표 문자 체계 글자가 3개 미만이면(사용자가 영어로만 썼다) 이탈이 아니라 사용자 언어를 따른 것이므로 통과한다. 답변은 트랜스크립트에 아직 없다(audit/34 L2).
                     사용자가 이번 턴에 다른 언어를 명시한 경우는 코드가 못 가리므로 사유 문구가 "그대로 두라"고 한다.
  PostToolBatch    : (a) 트랜스크립트를 저장된 오프셋부터 읽어 도구 호출 사이의 assistant 텍스트가 이탈이면 info 알림(쿨다운. 사용자에게 언급하지 않는 알림이라 warn 이 아니다),
                     (b) prompt_id 별 도구 호출 수가 10, 이후 15마다 info 한 줄. 기록은 한 걸음 늦으므로 완결된 줄만 소비한다(L2).
언어 출처(좁은 쪽이 이김): 프로젝트 .claude/settings.local.json > .claude/settings.json > 사용자 <config>/settings.json 의 `language`,
  없으면 ${CLAUDE_PLUGIN_DATA}/language.json. 둘 다 없으면 위 질문 알림이 `set` 으로 저장하게 한다.
  `python3 -I reply_language.py set <language> [--data <dir>]`: 저장소. Bash 에는 CLAUDE_PLUGIN_DATA 가 없어서(L4) 알림이 경로를 적어 준다.
로그: ${CLAUDE_PLUGIN_DATA}/drift.jsonl 에 감지와 조치마다 한 줄(ts, session, kind, ratio, length. 본문 없음).
끄기: HARNESS_REPLY_LANGUAGE=off (환경 변수 또는 harness.env)
"""
import json
import os
import re
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import conv_env  # noqa: E402

NS = "claude-conventions-lang"
MIN_LATIN = 20
THRESHOLD = 0.25
FIRST_REMINDER, EVERY = 10, 15
INTERIM_COOLDOWN_CALLS = 5
FIRST_READ_BYTES = 200_000

# 문자 체계: 이름 -> 목표 글자 정규식. 라틴 문자 언어는 여기에 없고 감지하지 않는다.
SCRIPTS = {
    "hangul": re.compile(r"[ᄀ-ᇿ㄰-㆏가-힣]"),
    "japanese": re.compile(r"[぀-ヿㇰ-ㇿ㐀-䶿一-鿿]"),
    "han": re.compile(r"[㐀-䶿一-鿿]"),
    "cyrillic": re.compile(r"[Ѐ-ӿ]"),
    "arabic": re.compile(r"[؀-ۿݐ-ݿ]"),
    "hebrew": re.compile(r"[֐-׿]"),
    "thai": re.compile(r"[฀-๿]"),
    "greek": re.compile(r"[Ͱ-Ͽ]"),
    "devanagari": re.compile(r"[ऀ-ॿ]"),
}
LANG_SCRIPT = [  # (이름이나 코드 조각, 문자 체계). 앞에서부터 처음 맞는 것
    (("korean", "한국어", "한글", "hangul"), "hangul"), (("ko",), "hangul"),
    (("japanese", "日本語", "日本", "にほんご"), "japanese"), (("ja", "jp"), "japanese"),
    (("chinese", "中文", "汉语", "漢語", "mandarin", "cantonese"), "han"), (("zh",), "han"),
    (("russian", "русский", "ukrainian", "українська", "bulgarian", "serbian", "belarusian"), "cyrillic"), (("ru", "uk", "bg", "sr", "be"), "cyrillic"),
    (("arabic", "العربية", "persian", "farsi", "urdu"), "arabic"), (("ar", "fa", "ur"), "arabic"),
    (("hebrew", "עברית"), "hebrew"), (("he",), "hebrew"),
    (("thai", "ไทย"), "thai"), (("th",), "thai"),
    (("greek", "ελληνικά"), "greek"), (("el",), "greek"),
    (("hindi", "हिन्दी", "marathi", "nepali"), "devanagari"), (("hi", "mr", "ne"), "devanagari"),
]
FENCE = re.compile(r"```.*?(?:```|\Z)|~~~.*?(?:~~~|\Z)", re.S)
INLINE = re.compile(r"`[^`\n]*`")
URL = re.compile(r"\b[a-z][a-z0-9+.-]*://\S+|\bwww\.\S+", re.I)
PATHLIKE = re.compile(r"(?<![\w])(?:[~.]{0,2}/)?[\w@.-]+(?:/[\w@.-]+)+/?|[\w-]+\.(?:[a-z]{1,5})\b", re.I)
LATIN = re.compile(r"[A-Za-z]")
NO_RESPONSE = "No response requested."
PROMPT_TAIL_BYTES = 1_000_000  # 마지막 사용자 프롬프트를 찾으려고 트랜스크립트 끝에서 읽는 상한
PROMPT_MIN_TARGET = 3
PASTED = re.compile(r"<(pasted_content|pasted_text|paste)[^>]*>.*?(?:</\1>|\Z)", re.S | re.I)


def script_for(language):
    """language 설정값(자유 문자열)에서 문자 체계 이름을 찾는다. 라틴 문자 언어나 모르는 값은 None."""
    low = str(language or "").strip().lower()
    if not low:
        return None
    words = set(re.findall(r"[^\W\d_]+(?:-[^\W\d_]+)?", low))
    for keys, script in LANG_SCRIPT:
        for k in keys:
            short_code = len(k) <= 3 and k.isascii()
            if (short_code and any(w.split("-")[0] == k for w in words)) or (not short_code and k in low):
                return script
    return None


def strip_text(text):
    for rx in (FENCE, INLINE, URL, PATHLIKE):
        text = rx.sub(" ", text)
    return text


def drift_ratio(text, script):
    """(목표 문자 비율, 라틴 글자 수). 코드, URL, 경로를 뗀 뒤 센다."""
    t = strip_text(text or "")
    target = len(SCRIPTS[script].findall(t))
    latin = len(LATIN.findall(t))
    return (target / (target + latin) if target + latin else 1.0), latin


def is_drift(text, script):
    if not text or text.strip() == NO_RESPONSE:
        return False, 1.0, 0
    ratio, latin = drift_ratio(text, script)
    return (latin >= MIN_LATIN and ratio < THRESHOLD), ratio, latin


# ---- 언어 출처 ----

def project_root(data):
    return os.environ.get("CLAUDE_PROJECT_DIR") or data.get("cwd") or os.getcwd()


def data_dir():
    d = os.environ.get("CLAUDE_PLUGIN_DATA")
    if d:
        return d
    base = os.path.join(conv_env.config_dir(), "plugins", "data")
    try:
        hits = sorted(n for n in os.listdir(base) if n.startswith("qwreey-conventions"))
    except OSError:
        return None
    return os.path.join(base, hits[0]) if hits else None


def settings_language(root):
    for p in (os.path.join(root, ".claude", "settings.local.json"), os.path.join(root, ".claude", "settings.json"),
              os.path.join(conv_env.config_dir(), "settings.json")):
        try:
            with open(p, encoding="utf-8") as f:
                v = json.load(f).get("language")
        except Exception:
            continue
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def stored_language(ddir=None):
    ddir = ddir or data_dir()
    if not ddir:
        return None
    try:
        with open(os.path.join(ddir, "language.json"), encoding="utf-8") as f:
            v = json.load(f).get("language")
    except Exception:
        return None
    return v.strip() if isinstance(v, str) and v.strip() else None


def resolve_language(data):
    return settings_language(project_root(data)) or stored_language()


# ---- 상태·로그 ----

def _sid(v):
    return re.sub(r"[^\w-]", "", str(v or "nosession"))


def state_file(session_id):
    d = os.path.join(tempfile.gettempdir(), NS)
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, _sid(session_id) + ".json")


def load_state(session_id):
    try:
        with open(state_file(session_id)) as f:
            return json.load(f)
    except Exception:
        return {}


def save_state(session_id, st):
    try:
        p = state_file(session_id)
        tmp = "%s.%d.tmp" % (p, os.getpid())
        with open(tmp, "w") as f:
            json.dump(st, f)
        os.replace(tmp, p)
    except OSError:
        pass


def log(session_id, kind, ratio=None, length=None):
    d = data_dir()
    if not d:
        return
    try:
        os.makedirs(d, exist_ok=True)
        rec = {"ts": int(time.time()), "session": _sid(session_id)[:8], "kind": kind,
               "ratio": None if ratio is None else round(ratio, 3), "length": length}
        with open(os.path.join(d, "drift.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
    except OSError:
        pass


def tag(level, body):
    return '<harness-hook name="reply-language" level="%s">\n%s\n</harness-hook>' % (level, body)


# ---- 이벤트 ----

def last_user_prompt(path):
    """트랜스크립트 끝에서 가장 최근의 실제 사용자 프롬프트 텍스트. 못 찾으면 None. 도구 결과·메타·서브에이전트 항목은 건너뛴다."""
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as f:
            start = max(0, size - PROMPT_TAIL_BYTES)
            f.seek(start)
            chunk = f.read()
    except OSError:
        return None
    lines = chunk.split(b"\n")
    if start:
        lines = lines[1:]  # 잘린 첫 줄
    for raw in reversed(lines):
        try:
            j = json.loads(raw)
        except ValueError:
            continue
        if j.get("type") != "user" or j.get("isSidechain") or j.get("isMeta"):
            continue
        c = (j.get("message") or {}).get("content")
        if isinstance(c, list):
            if any(isinstance(b, dict) and b.get("type") == "tool_result" for b in c):
                continue
            c = " ".join(b.get("text") or "" for b in c if isinstance(b, dict) and b.get("type") == "text")
        if isinstance(c, str) and c.strip():
            return c
    return None


def user_wrote_other_script(path, script):
    """마지막 사용자 프롬프트에 목표 문자 체계 글이 사실상 없는가(사용자가 다른 언어로만 썼다).
    코드 블록, 붙여 넣은 블록, URL, 경로를 뗀 뒤 목표 글자가 PROMPT_MIN_TARGET 미만이면 참이다. 목표 글자가 조금이라도 있으면
    사용자가 그 언어를 쓰는 것이다(영어 로그를 붙여 넣고 한국어로 물은 경우). 영어 답을 명시한 경우는 사유 문구가 맡는다."""
    text = last_user_prompt(path) if path else None
    if not text:
        return False
    text = PASTED.sub(" ", text)
    return len(SCRIPTS[script].findall(strip_text(text))) < PROMPT_MIN_TARGET


def on_prompt(data):
    if resolve_language(data):
        return None
    sid = data.get("session_id")
    st = load_state(sid)
    if st.get("asked"):
        return None
    st["asked"] = True
    save_state(sid, st)
    log(sid, "ask_language")
    d = data_dir() or ""
    cmd = 'python3 -I "%s" set "<language>"%s' % (os.path.abspath(__file__), (' --data "%s"' % d) if d else "")
    return {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": tag(
        "info",
        "No reply language is configured, so replies cannot be checked for language drift. Answer the user's request first, as usual. "
        "Then, at the end of that reply, ask in one short question which language to reply in, and store the answer with this command: %s\n"
        "If the user's message already makes the language clear (they write in it or name it), store that instead of asking. "
        "The `language` key in a Claude Code settings.json sets it too." % cmd)}}


def on_stop(data):
    lang = resolve_language(data)
    script = script_for(lang)
    sid = data.get("session_id")
    msg = data.get("last_assistant_message") or ""
    if not lang:
        return None
    if not script:
        log(sid, "stop_latin_skip", None, len(msg))
        return None
    drifted, ratio, _latin = is_drift(msg, script)
    if not drifted:
        return None
    if data.get("stop_hook_active"):
        log(sid, "stop_still_drifted", ratio, len(msg))
        return None
    if user_wrote_other_script(data.get("transcript_path"), script):
        log(sid, "stop_user_other_script", ratio, len(msg))
        return None
    log(sid, "stop_block", ratio, len(msg))
    return {"decision": "block", "reason": tag(
        "action",
        "Your last reply is not in %s. If the user explicitly asked in this turn for that reply in another language, keep the reply "
        "and add nothing. Otherwise output only the rewritten reply, the same content in %s, with no line about rewriting, the "
        "earlier version, the language or this notice, and no apology." % (lang, lang))}


def read_new_lines(path, st):
    """오프셋부터 완결된 줄(개행으로 끝남)만 읽는다. 처음에는 끝에서 FIRST_READ_BYTES 만큼만 본다. 새 오프셋을 st 에 적는다."""
    try:
        size = os.path.getsize(path)
        off = st.get("offset")
        with open(path, "rb") as f:
            skip_first = False
            if off is None or off > size:
                off = max(0, size - FIRST_READ_BYTES)
                skip_first = off > 0
            f.seek(off)
            chunk = f.read()
    except OSError:
        return []
    end = chunk.rfind(b"\n")
    if end < 0:
        st["offset"] = off
        return []
    complete = chunk[:end + 1]
    st["offset"] = off + len(complete)
    lines = complete.split(b"\n")[:-1]
    return lines[1:] if skip_first else lines


def interim_texts(lines):
    """메인 대화의 assistant text 블록들. 서브에이전트(sidechain) 항목은 뺀다."""
    out = []
    for raw in lines:
        try:
            j = json.loads(raw)
        except ValueError:
            continue
        if j.get("type") != "assistant" or j.get("isSidechain"):
            continue
        c = (j.get("message") or {}).get("content")
        if isinstance(c, list):
            out += [b.get("text") or "" for b in c if isinstance(b, dict) and b.get("type") == "text"]
        elif isinstance(c, str):
            out.append(c)
    return out


def on_batch(data):
    lang = resolve_language(data)
    script = script_for(lang)
    if not script:
        return None
    sid = data.get("session_id")
    st = load_state(sid)
    pid = data.get("prompt_id")
    if st.get("prompt_id") != pid:
        st["prompt_id"], st["count"], st["next"] = pid, 0, FIRST_REMINDER
    prev = st["count"]
    st["count"] = prev + max(1, len(data.get("tool_calls") or []))
    total = st["count"]
    out = []
    tp = data.get("transcript_path")
    if tp:
        worst, worst_len = None, None
        for text in interim_texts(read_new_lines(tp, st)):
            d, ratio, _ = is_drift(text, script)
            if d and (worst is None or ratio < worst):
                worst, worst_len = ratio, len(text)
        if worst is not None and total - st.get("last_interim", -99) >= INTERIM_COOLDOWN_CALLS:
            st["last_interim"] = total
            log(sid, "interim_drift", worst, worst_len)
            out.append(tag("info", "Text you wrote to the user between tool calls was not in %s. Write all text to the user in %s, "
                           "including short progress notes. Do not mention this notice." % (lang, lang)))
    if total >= st["next"]:
        while st["next"] <= total:
            st["next"] += EVERY
        log(sid, "long_turn_reminder", None, total)
        out.append(tag("info", "Reply to the user in %s." % lang))
    save_state(sid, st)
    if not out:
        return None
    return {"hookSpecificOutput": {"hookEventName": "PostToolBatch", "additionalContext": "\n".join(out)}}


def cmd_set(argv):
    args = [a for a in argv]
    ddir = None
    if "--data" in args:
        i = args.index("--data")
        ddir = args[i + 1] if i + 1 < len(args) else None
        del args[i:i + 2]
    lang = " ".join(args).strip()
    ddir = ddir or data_dir()
    if not lang or not ddir:
        print("usage: reply_language.py set <language> [--data <dir>]; data dir not found" if lang else "usage: reply_language.py set <language> [--data <dir>]", file=sys.stderr)
        return 2
    os.makedirs(ddir, exist_ok=True)
    with open(os.path.join(ddir, "language.json"), "w", encoding="utf-8") as f:
        json.dump({"language": lang, "set_at": int(time.time())}, f, ensure_ascii=False)
    print("reply language stored: %s (%s)" % (lang, os.path.join(ddir, "language.json")))
    return 0


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "set":
        return cmd_set(sys.argv[2:])
    try:
        if conv_env.is_off("HARNESS_REPLY_LANGUAGE"):
            return 0
        data = json.load(sys.stdin)
        if data.get("agent_id"):
            return 0
        ev = data.get("hook_event_name")
        fn = {"UserPromptSubmit": on_prompt, "Stop": on_stop, "PostToolBatch": on_batch}.get(ev)
        out = fn(data) if fn else None
        if out:
            json.dump(out, sys.stdout, ensure_ascii=False)
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
