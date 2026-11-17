#!/usr/bin/env python3
"""PostToolUse(Write|Edit|MultiEdit) 알림: 이번에 추가한 줄이 주석, 모델용 문서 관례를 벗어난 것 같으면 한 줄로 알린다.

막지 않는다(decision 없음). additionalContext(level=info) 한 줄만 주입한다. 주석 알림과 모델용 문서 알림 모두 줄 번호와 고치는 법(대체 문자,
옮길 곳, 써야 할 꼴)을 함께 줘서 알림만 보고 고칠 수 있다. 스킬을 열라고 하지 않는다.
Bash 로 바꾼 파일은 bash_writes.py 가 이 파일의 file_notice 로 같은 검사, 같은 중복 거르기를 한다.

남은 기존 주석 보고: 같은 PostToolUse 에서 이번에 추가하지 않은 줄의 문제를 범주별(이력, 기호, 이스케이프, 보이지 않는 문자) 줄 수로 세어
  $TMPDIR/claude-conventions/<session_id>.left.<main|agent_id>.json 에 조용히 쌓는다(파일마다 마지막 편집 기준). Stop 에서 모든 호출한 쪽 기록을 합쳐
  사용자에게 한 줄을 systemMessage 로 보인다(내용이 바뀐 때만). reuse-check 가 따로 쓰는 <session_id>.reuse.<main|agent_id>.json(전부터 있던 같은 목록 수, 원본과 다른 사본 수)도 합쳐 보인다. 고치지 않는다. 모델 턴을 늘리지 않으려고 Stop 의 additionalContext 나 decision 은 쓰지 않는다.

보는 것: 이번에 추가된 줄만. Edit/MultiEdit 는 new_string 에서 old_string 에 없던 줄, Write 는 새 파일이면 전체, 덮어쓰기면
  tool_response.originalFile 과의 차이(없으면 structuredPatch 의 + 줄, 둘 다 없으면 보지 않는다. 옛 줄을 새로 오인하지 않으려고).

코드 파일(주석 줄만; 파일 전체를 확장자별 간이 렉서로 읽어 문자열 리터럴 안의 `--`, `//`, `#` 는 주석이 아니다)
  - history marker: 원장 번호, 날짜, 라운드, 작업 이력 경로, 결정 문구, 변경 서술(절 머리의 Previously 와 It/This/We/They used to,
    예전에는, 절 머리의 이전에는, 기존에는 ...했다). `Ref:` 꼬리는 같은 주석 덩어리에 이유 문장이 있으면 통과
  - non-keyboard symbol: 사람이 키보드로 치지 않는 문자(기호, 가운뎃점, 곡선 따옴표, 전각, 이모지). ASCII 와 모든 문자 체계의 글자(한글, 키릴, 악센트 라틴 등)와 숫자는 통과
  - escaped character: 주석 안의 유니코드 이스케이프(백슬래시 u 와 16진수 넷 등). 금지 문자를 이스케이프로 적어 검사를 피한 것으로 본다
  - invisible character: 보이지 않는 문자, 방향 제어 문자. 주석이 아니라 추가된 줄 전체에서 본다
  - language mismatch: 파일 주석의 90% 이상이 한 문자 체계(기존 10줄 이상)인데 추가된 줄이 다른 체계 단어를 3개 이상 쓴다.
    새 파일은 저장소 comment_language, 없으면 같은 폴더 형제 파일의 다수, 그것도 없으면 검사하지 않는다. 지시자 줄(--!strict, eslint-disable 등)은 뺀다.
    단계 라벨(본문 안 들여쓴 한 줄 주석, 위는 주석 줄이 아니고 아래는 코드, label_language 글자만 2-10낱말, 72자 이하, 마침표와 이유 접속어 없음)은
    언어 판정과 다수 계산에서 뺀다. 한국어 주석 파일에 영어 라벨을 쓰는 것이 readable-code 규약이라서다(키와 무관하게 늘)
  - layout (HARNESS_READABLE_CODE=on 일 때만, hooks/layout_metrics.py): 이번 편집이 새로 쓰거나(함수 줄의 절반 이상) 15줄 이상 키운 함수의
    빈 줄 없는 긴 본문(layout), 문장 사이에 끼운 여러 줄 주석(interleaved comment), 호출하는 쪽이 못 보는 문서 주석(doc summary: 공개 함수에
    호버 꼴 문서가 없음, 첫 줄이 길거나 첫 문장이 첫 줄에서 안 끝남. 메타메서드 제외). (파일, 범주, 함수)마다 한 번이고, doc summary 를 알린 함수는
    다음 편집 뒤 한 번 더 본다
모델용 문서(CLAUDE.md, SKILL.md, agents/*.md, .claude/rules/*.md, skills/**/*.md; 추가된 줄만, frontmatter, 코드 펜스, 인라인 코드, URL, 경로 토큰 안은 통과)
  - 입구 문서: 날짜, audit/session/handoff 경로와 .claude/ 아래 기록 폴더 경로, 라운드, 결정 문구, 실측 표지, 변경 서술, 같은 줄에 .md 경로가 없는 원장 id
  - skills/**/references/*.md: 결정 문구, 라운드, audit/N 근거, 실측 표지, 정정 배너만(날짜, id, "previously" 는 통과)
  - `status:` 줄은 통과
  - 꼴(conv_docs.doc_shape): SKILL.md 의 description(영어, 언제 쓰는지, 3인칭, 한국어 계기는 끝; disable-model-invocation 은 제외),
    한국어가 대부분인 줄(이미 한국어로 쓴 문서는 제외), 입구 문서에서 원장 id 옆 .md 경로가 플러그인(밖이면 저장소) 안의 있는 파일이 아님
제외: 확장자 표 밖, 생성 파일(머리 6줄 표시), 픽스처, testdata, node_modules 등, 설정의 exclude.

저장소 설정: <프로젝트>/.claude/conventions.json (없으면 예전 이름 .claude/comments.json)
  {"allow_ref_tail": true, "comment_language": "en", "allow_chars": ["emoji", "x"], "public_ids": ["Quad\\\\d{4}"],
   "exclude": ["docs/**", "*.md"], "patterns": {"ledger": "<정규식>", "date": null}, "min_reason_words": 3,
   "label_language": "en", "layout": {"min_lines": 15, "max_run": 20, "doc_first_max": 100, "grow": 15}}
  label_language: 단계 라벨의 언어(기본 en), null 이면 라벨 예외를 끈다. layout: layout 알림 기준(layout_metrics.DEFAULT_LAYOUT).
  allow_chars: "emoji" 는 이모지를 끄고, 그 밖의 항목은 허용할 글자들이다. public_ids: 줄에서 먼저 지우고 검사하는 공개 식별자 정규식.
  patterns: 이름별로 덮어쓰기, null 이면 끈다.
끄기: 환경 변수 CONVENTIONS_CHECK=off. layout 알림은 harness.env 층의 HARNESS_READABLE_CODE=on 일 때만 켜진다(conv_env.py).
알림 중복: (session_id, 호출한 쪽, 파일, 범주)마다 한 번(이미 알린 범주는 다시 알리지 않고, 새 범주는 알린다). compact 회차도 구분한다(compact_epoch.py, PreCompact 훅이 올린다).
상태 파일: $TMPDIR/claude-conventions/<session_id>.c<회차>[.a<agent_id>].json
"""
import contextlib
import fnmatch
import json
import os
import re
import sys
import time
import unicodedata
from collections import Counter
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import compact_epoch  # noqa: E402
import harness_nonce  # noqa: E402
from conv_edit import GEN_MARK, MAX_BYTES, SKIP_PARTS, SKIP_SUFFIX, collect, project_root  # noqa: E402
from conv_docs import DOC_HINT, INLINE_CODE, PATH_TOKEN, URL, doc_check, doc_class, doc_lines, doc_shape  # noqa: E402,F401 (scan 이 cc. 로 쓴다)
from conv_lex import FAMILY, comment_body, lex  # noqa: E402
import layout_metrics  # noqa: E402
import conv_leftovers  # noqa: E402
from conv_leftovers import LEFT_LABEL, LEFT_MAX_FILES, NS, _latest, left_dir, left_path, leftover_message, report_leftovers  # noqa: E402,F401

NAME = "qwreey-conventions"
HOME = Path(os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude"))

# 과거 시제 음절: 받침이 ㅆ 인 한글 음절(했, 였, 었, 랐, 됐 ...)에서 현재를 말하는 있, 겠을 뺀 것. 뒤에 종결이나 관형 어미가 와야 센다
PAST_SYLLABLES = "".join(c for c in (chr(0xAC00 + i * 28 + 20) for i in range(19 * 21)) if c not in "있겠")
# 절 머리: 주석 시작, 문장 부호 뒤, 여는 괄호 뒤. "the buffer it used to hold" 처럼 명사 뒤에 오는 꼴은 코드가 하는 일이다
CLAUSE_START = r"(?:^|[.;:!?]\s+|\(\s*)"
PATTERNS = {
    "ledger": r"\b[A-Z]{1,2}-?\d{2,4}\b",
    "date": r"\b20\d\d-\d\d-\d\d\b",
    "round": r"\bround\s*\d+\b|라운드\s*\d+|감사\s*\d+\s*차",
    "path": r"\.claude/|(?<![\w-])session/|(?<![\w-])audit/",
    "decision": r"사용자\s*(?:결정|지시|요청|합의|말)|\bper (?:the )?user\b|\bas (?:the user )?(?:discussed|decided|agreed)\b|\bthe user (?:decided|asked|wanted|requested)\b",
    # 변경 서술. "the previously selected item", "a key used to sign", "초기화 이전에는", "기존엔 키가 있을 수 있다" 는 코드가 하는 일을
    # 말하므로 절 머리의 "Previously"(쉼표나 낱말이 뒤따름, "Previously-seen" 은 아님)와 "It/This/We/They used to", 예전에는,
    # 절 머리의 이전에는, 기존에는 ... 과거 어미만 센다
    "narration": CLAUSE_START + r"(?:Previously(?=,|\s+\w)|(?:[Ii]t|[Tt]his|[Ww]e|[Tt]hey)\s+used\s+to\b)|예전(?:에는|엔)"
                 r"|(?:^|[.;:!?,(]\s*)이전(?:에는|엔)"
                 r"|기존(?:에는|엔)[^.\n]*?[" + PAST_SYLLABLES + r"](?:다|습니다|어요|죠|던|지만|는데)",
}
# 내장 공개 식별자, 표준 번호: 줄에서 먼저 지운 뒤 검사한다. 저장소 public_ids 는 여기에 더한다.
BUILTIN_PUBLIC = [r"error-code:\s*\S+", r"\bR(?:6|15)\b", r"\bES\d{4}\b", r"\bH26[45]\b", r"\bUTF-?\d+\b", r"\bSHA-?\d+\b", r"\bP\d{2,3}\b(?=\s*(?:p|fps|hz))",
                  r"\b[A-Z]{1,2}\d{2,4}(?=px|pt|ms|hz|fps|kb|mb|gb)",
                  # 번호 모양이지만 원장이 아닌 것: 정수 폭(F64, I32), 아키텍처(X86), C 표준(C99), 컴파일러 오류 코드(TS2322, E0308)
                  r"\b[FIUS](?:8|16|32|64|128)\b", r"\bX86\b", r"\bC(?:89|90|99|11|17|23)\b", r"\bTS\d{4}\b", r"\bE0\d{3}\b"]
# 주석 안의 유니코드 이스케이프(\\uXXXX, \\u{...}, \\UXXXXXXXX): 금지 문자를 이스케이프로 적어 검사를 피한 것
ESCAPE = re.compile(r"\\u[0-9A-Fa-f]{4}|\\u\{[0-9A-Fa-f]+\}|\\U[0-9A-Fa-f]{8}")
# 알림 범주 순서(알림 문장에서 앞일수록 먼저 고친다)
CATEGORY_ORDER = ("history marker", "Ref tail without a reason sentence", "skill description", "ledger id path", "non-keyboard symbol",
                  "escaped character", "invisible character", "language mismatch")
# 흔한 기호의 대체. 키가 없으면 ASCII 나 평범한 단어로 풀어 쓴다.
SYMBOL_FIX = {"\u2014": "-", "\u2013": "-", "\u2015": "-", "\u2212": "-", "\u00b7": ",", "\u2022": "-", "\u2026": "...",
              "\u2192": "->", "\u2190": "<-", "\u2194": "<->", "\u21d2": "=>", "\u00a7": "(omit)", "\u00d7": "x",
              "\u2265": ">=", "\u2264": "<=", "\u2260": "!=", "\u201c": '"', "\u201d": '"', "\u2018": "'", "\u2019": "'",
              "\u2713": "ok", "\u2714": "ok", "\u2717": "FAIL", "\u2718": "FAIL", "\u26a0": "NOTE:"}
REF_LINE = re.compile(r"^\s*Ref\s*:", re.I)
WORD = re.compile(r"[A-Za-z\u00c0-\u024f]{2,}|[가-힣]{2,}")
DEFAULTS = {"allow_ref_tail": True, "public_ids": [], "exclude": [], "patterns": {}, "min_reason_words": 3,
            "comment_language": None, "allow_chars": [], "label_language": "en", "layout": {}}


# 보이지 않는 문자, 방향 제어 문자(소프트 하이픈, NBSP, ZW*, 방향 표식, 임베딩, 고립, WORD JOINER, BOM)
INVISIBLE = re.compile("[\u00ad\u00a0\u061c\u180e\u200b-\u200f\u202a-\u202e\u2060-\u2069\ufeff]")
EMOJI_RANGES = ((0x1F000, 0x1FAFF), (0x2600, 0x27BF), (0x2B00, 0x2BFF), (0xFE00, 0xFE0F), (0x20E3, 0x20E3))
FULLWIDTH_RANGES = ((0x3000, 0x3000), (0xFF01, 0xFF5E), (0xFFE0, 0xFFE6))

# 지시자 줄: 도구에게 하는 말이라 언어 판정에서 뺀다
DIRECTIVE = re.compile(r"^\s*(?:!|@|-\*-|eslint|prettier|noqa|type:|pyright|pylint|mypy|selene|stylua|luau-lsp|region|endregion|nolint|lint:|coding[:=]|vim:|go:|nocheck|<reference)", re.I)
SCRIPT_WORDS = {"latin": re.compile(r"[A-Za-z\u00c0-\u024f]{3,}"), "hangul": re.compile(r"[가-힣]+"),
                "cjk": re.compile(r"[\u3040-\u30ff\u3400-\u9fff]+"), "cyrillic": re.compile(r"[\u0400-\u04ff]{2,}")}
LANG_SCRIPT = {"en": "latin", "ko": "hangul", "ja": "cjk", "zh": "cjk", "ru": "cyrillic"}
# 주석 안의 코드 조각(타입 표기, 대입, 블록)은 문장이 아니라 언어 판정에서 뺀다
CODE_LIKE = re.compile(r"::|=|[{};]|^\s*`{3}")
LANG_MIN_LINES = 10
LANG_SHARE = 0.9
LANG_MIN_WORDS = 3
# 단계 라벨: 이유 접속어가 있으면 라벨이 아니라 이유 문장이라 언어 판정에 남긴다
LABEL_REASON = re.compile(r"\b(?:because|since|so|otherwise|unless|must|never|in order to|to avoid|due to|workaround)\b", re.I)
LABEL_WORDS = {"latin": re.compile(r"[A-Za-z\u00c0-\u024f]+")}
LABEL_MAX_CHARS = 72


# ---------- 설정, 경로 ----------

def load_cfg(root):
    cfg = {k: (dict(v) if isinstance(v, dict) else list(v) if isinstance(v, list) else v) for k, v in DEFAULTS.items()}
    try:
        for name in ("conventions.json", "comments.json"):  # comments.json 은 예전 이름
            fp = os.path.join(root, ".claude", name)
            if os.path.exists(fp):
                user = json.load(open(fp))
                if isinstance(user, dict):
                    cfg.update(user)
                break
    except Exception:
        pass
    return cfg


def compile_patterns(cfg):
    pats = dict(PATTERNS)
    for k, v in (cfg.get("patterns") or {}).items():
        if v:
            pats[k] = v
        else:
            pats.pop(k, None)
    out = {}
    for k, v in pats.items():
        try:
            out[k] = re.compile(v, re.I if k in ("round", "decision") else 0)
        except re.error:
            pass
    pub = []
    for v in BUILTIN_PUBLIC + list(cfg.get("public_ids") or []):
        try:
            pub.append(re.compile(v))
        except re.error:
            pass
    return out, pub


def excluded(path, rel, cfg):
    parts = set(Path(rel).parts)
    if parts & SKIP_PARTS or path.endswith(SKIP_SUFFIX):
        return True
    for g in cfg.get("exclude") or []:
        if fnmatch.fnmatch(rel, g) or fnmatch.fnmatch(os.path.basename(rel), g) or fnmatch.fnmatch(rel, "*/" + g):
            return True
    return False


# ---------- 문자, 언어 ----------

def odd_chars(text, allow):
    """키보드로 치지 않는 문자(기호, 곡선 따옴표, 전각, 이모지)가 있으면 True. ASCII 와 자연어 글자, 숫자는 통과."""
    allow_emoji = "emoji" in allow
    literal = "".join(a for a in allow if a != "emoji")
    for ch in text:
        cp = ord(ch)
        if cp < 0x80 or ch in literal or INVISIBLE.match(ch):
            continue
        if any(a <= cp <= b for a, b in EMOJI_RANGES):
            if allow_emoji:
                continue
            return True
        if any(a <= cp <= b for a, b in FULLWIDTH_RANGES):
            return True
        cat = unicodedata.category(ch)
        if cat[0] in "LM" or cat == "Nd":
            continue
        return True
    return False


def invisible_lines(text, added):
    """추가된 줄 중 보이지 않는 문자가 있는 줄 번호(1 기반). 파일 맨 앞 BOM 은 인코딩 표지라 통과."""
    out = []
    for idx, line in enumerate(text.split("\n")):
        if idx not in added:
            continue
        if idx == 0 and line.startswith("\ufeff"):
            line = line[1:]
        if INVISIBLE.search(line):
            out.append(idx + 1)
    return out


def word_counts(seg):
    seg = INLINE_CODE.sub(" ", URL.sub(" ", seg))
    return {name: len(rx.findall(seg)) for name, rx in SCRIPT_WORDS.items()}


def line_script(counts):
    top = max(counts.values())
    if top == 0:
        return None
    best = [k for k, v in counts.items() if v == top]
    return best[0] if len(best) == 1 else None


def step_labels(rows, lines, cfg):
    """언어 판정에서 뺄 단계 라벨 줄 번호(0 기반). label_language 가 null 이면 빈 집합이다.

    라벨: 본문 안에 들여쓴 한 줄 주석, 위 줄은 주석만 있는 줄이 아니고 아래 줄은 코드, label_language 글자의 낱말 2-10개,
    72자 이하, 마침표와 이유 접속어가 없다.
    """
    lang = cfg.get("label_language", "en")
    script = LANG_SCRIPT.get(lang.lower()[:2]) if isinstance(lang, str) else None
    if not script:
        return frozenset()

    words_rx = LABEL_WORDS.get(script, SCRIPT_WORDS[script])
    out = set()
    for i in range(1, len(rows) - 1):
        # Shape: one indented comment line heading code
        r = rows[i]
        if r["code"] or len(r["c"]) != 1 or lines[i][:1] not in (" ", "\t"):
            continue
        if (rows[i - 1]["c"] and not rows[i - 1]["code"]) or not rows[i + 1]["code"]:
            continue

        # Text: a short phrase in the label language
        body = comment_body(r["c"][0])
        if not body or len(body) > LABEL_MAX_CHARS or body.endswith(".") or LABEL_REASON.search(body):
            continue
        if any(v for k, v in word_counts(body).items() if k != script):
            continue
        if layout_metrics.LABEL_WORDS_MIN <= len(words_rx.findall(body)) <= layout_metrics.LABEL_WORDS_MAX:
            out.add(i)
    return frozenset(out)


def comment_stats(rows, skip=frozenset()):
    """주석 줄(지시자 제외, skip 줄 제외)의 문자 체계 분포."""
    cnt = Counter()
    for i, r in enumerate(rows):
        if i in skip or not r["c"] or any(DIRECTIVE.match(c) for c in r["c"]):
            continue
        s = line_script(word_counts(" ".join(r["c"])))
        if s:
            cnt[s] += 1
    return cnt


def majority(cnt):
    total = sum(cnt.values())
    if total < LANG_MIN_LINES:
        return None
    script, n = cnt.most_common(1)[0]
    return script if n / total >= LANG_SHARE else None


def sibling_majority(path, fam_ext, cfg=None):
    d = os.path.dirname(path)
    cnt = Counter()
    try:
        names = sorted(n for n in os.listdir(d) if n.endswith(fam_ext))
    except OSError:
        return None
    fam = FAMILY.get(fam_ext)
    for n in [n for n in names if os.path.join(d, n) != path][:20]:
        try:
            p = os.path.join(d, n)
            if os.path.getsize(p) > 200_000:
                continue
            sib = Path(p).read_text(encoding="utf-8")
            rows = lex(sib, fam)
            cnt += comment_stats(rows, step_labels(rows, sib.split("\n"), cfg or DEFAULTS))
        except (OSError, UnicodeDecodeError):
            continue
    return majority(cnt)


def expected_script(rows, added, cfg, path, ext, labels=frozenset()):
    """이 파일 주석이 따를 문자 체계. 파일 다수 -> 저장소 comment_language -> 형제 파일 다수 -> None(검사 안 함). labels 줄은 세지 않는다."""
    own = majority(comment_stats(rows, skip=set(added) | labels))
    if own:
        return own
    lang = cfg.get("comment_language")
    if isinstance(lang, str) and lang.lower()[:2] in LANG_SCRIPT:
        return LANG_SCRIPT[lang.lower()[:2]]
    return sibling_majority(path, ext, cfg)


def language_lines(rows, added, expected, labels=frozenset()):
    """추가된 줄 중 다른 문자 체계가 우세한 줄들의 단어가 LANG_MIN_WORDS 개 이상이면 그 줄 번호(1 기반). labels 줄(단계 라벨)은 뺀다."""
    hits, words = [], 0
    for i in sorted(added):
        if i in labels or i >= len(rows) or not rows[i]["c"] or any(DIRECTIVE.match(c) for c in rows[i]["c"]):
            continue
        joined = " ".join(rows[i]["c"])
        if CODE_LIKE.search(joined):
            continue
        counts = word_counts(joined)
        other = sum(v for k, v in counts.items() if k != expected)
        if other >= 2 and other > counts.get(expected, 0):
            hits.append(i + 1)
            words += other
    return hits if words >= LANG_MIN_WORDS else []


# ---------- 검사 ----------

def scan(body, pats, pub):
    """본문에서 탐지 토큰을 (종류, 토큰) 목록으로. 공개 식별자는 먼저 지운다."""
    for p in pub:
        body = p.sub(" ", body)
    hits = []
    for kind, rx in pats.items():
        for m in rx.finditer(body):
            hits.append((kind, m.group(0).strip()))
    return hits, body


def reason_words(body, pats):
    for rx in pats.values():
        body = rx.sub(" ", body)
    return len(WORD.findall(body))


def check_lines(rows, added, pats, pub, cfg):
    """rows: lex 결과, added: 추가된 줄 번호(0 기반) 집합. [(줄 번호(1 기반), 범주)] 를 돌려준다(한 줄에 범주가 여럿일 수 있다)."""
    # 주석 덩어리: 코드 없이 주석만 있는 줄이 이어진 것. 코드와 한 줄에 있는 주석은 줄마다 따로.
    segs = [" ".join(comment_body(c) for c in r["c"]) if r["c"] else None for r in rows]
    standalone = [bool(r["c"]) and not r["code"] for r in rows]
    allow = cfg.get("allow_chars") or []
    problems = []
    i, n = 0, len(rows)
    min_words = int(cfg.get("min_reason_words", 3))
    while i < n:
        if segs[i] is None:
            i += 1
            continue
        j = i + 1
        if standalone[i]:
            while j < n and standalone[j] and segs[j] is not None:
                j += 1
        block = range(i, j)
        i = j
        if not any(k in added for k in block):
            continue
        has_reason = any(not REF_LINE.match(segs[k]) and reason_words(scan(segs[k], pats, pub)[1], pats) >= min_words
                         for k in block if segs[k])
        for k in block:
            if k not in added or not segs[k]:
                continue
            body = segs[k]
            if any(DIRECTIVE.match(c) for c in rows[k]["c"]):
                continue
            if odd_chars(body, allow):
                problems.append((k + 1, "non-keyboard symbol"))
            if ESCAPE.search(body):
                problems.append((k + 1, "escaped character"))
            if REF_LINE.match(body) and cfg.get("allow_ref_tail", True):
                if not has_reason:
                    problems.append((k + 1, "Ref tail without a reason sentence"))
                continue
            if scan(body, pats, pub)[0]:
                problems.append((k + 1, "history marker"))
    return problems


def state_file(sid, agent_id):
    return compact_epoch.state_path("qwreey-conventions", NS, sid, agent_id)


STATE_LOCK_WAIT_S = 3.0


@contextlib.contextmanager
def state_lock(path):
    """상태 파일의 읽기, 알림, 쓰기를 한 프로세스씩. 나란히 도는 Bash 와 Edit 훅이 같은 알림을 두 번 내지 않게 한다.

    fcntl 이 없거나(Windows) 잠금 파일을 못 열거나 STATE_LOCK_WAIT_S 안에 못 잡으면 잠그지 않고 간다(알림이 한 번 겹칠 뿐이다).
    """
    fd = None
    try:
        import fcntl
        fd = os.open(path + ".lock", os.O_RDWR | os.O_CREAT, 0o600)
        end = time.monotonic() + STATE_LOCK_WAIT_S
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() > end:
                    break
                time.sleep(0.01)
    except (ImportError, OSError):
        pass
    try:
        yield
    finally:
        if fd is not None:
            os.close(fd)


def load_state(path):
    """세션 상태 {"files": {경로: [알린 키]}, "doc_recheck": {경로: [함수 키]}}. 깨졌거나 꼴이 다르면 빈 상태로 시작한다."""
    try:
        state = json.load(open(path))
    except Exception:
        state = {}
    state = state if isinstance(state, dict) else {}
    for name in ("files", "doc_recheck"):
        if not isinstance(state.get(name), dict):
            state[name] = {}
    return state


def layout_step(state, key, text, rows, added, ext, cfg):
    """(다시 볼 함수 키, layout 알림). 지표 코드가 어떤 입력에서 터져도 주석 알림은 나가야 하므로 실패하면 둘 다 빈 목록이다."""
    try:
        recheck = state["doc_recheck"].get(key)
        recheck = [k for k in recheck if isinstance(k, str)] if isinstance(recheck, list) else []
        shapes = layout_metrics.edit_findings(text, rows, added, layout_metrics.LANG_BY_EXT[ext], cfg.get("layout"), recheck)
        return recheck, shapes
    except Exception:
        return [], []


def symbol_detail(text, lines, allow):
    """알림에 적을 글자와 대체. 보이지 않는 글자는 코드포인트로 적는다(모델이 눈으로 볼 수 없다)."""
    allow_emoji = "emoji" in allow
    literal = "".join(a for a in allow if a != "emoji")
    src = text.split("\n")
    odd, fixes = [], []
    for n in lines:
        for ch in src[n - 1] if 0 < n <= len(src) else "":
            if ord(ch) < 0x80 or ch in odd or ch in literal or INVISIBLE.match(ch) or not odd_chars(ch, ["emoji"] if allow_emoji else []):
                continue
            odd.append(ch)
            fix = SYMBOL_FIX.get(ch)
            if fix is None:
                name = unicodedata.name(ch, "")
                nk = unicodedata.normalize("NFKC", ch)
                if name.startswith(("CIRCLED DIGIT", "CIRCLED NUMBER", "DINGBAT")) and nk.isdigit():
                    fix = nk + ")"
                elif nk.isascii() and nk != ch:
                    fix = nk
                elif any(a <= ord(ch) <= b for a, b in EMOJI_RANGES):
                    fix = "ok, FAIL, NOTE: or plain words"
                else:
                    fix = "plain ASCII or words"
            if fix not in fixes:
                fixes.append(fix)
    shown = " ".join(odd[:6]) + (" ..." if len(odd) > 6 else "")
    return f'{shown} (use {", ".join(chr(34) + f + chr(34) for f in fixes[:6])})' if odd else ""


def invisible_detail(text, lines):
    src = text.split("\n")
    cps = []
    for n in lines:
        for ch in INVISIBLE.findall(src[n - 1]) if 0 < n <= len(src) else []:
            cp = f"U+{ord(ch):04X}"
            if cp not in cps:
                cps.append(cp)
    return " ".join(cps[:6]) + " (delete it)" if cps else ""


def escape_detail(text, lines):
    src = text.split("\n")
    found = []
    for n in lines:
        for m in ESCAPE.findall(src[n - 1]) if 0 < n <= len(src) else []:
            if m not in found:
                found.append(m)
    return " ".join(found[:4]) + " (write the character itself or reword)" if found else ""


LINE_LIST_MAX = 40  # 범주당 찍는 숫자 수 상한. 줄을 다 알려야 모델이 파일을 통째로 읽지 않고 고치지만, 알림이 길어지지는 않게


def line_list(lines):
    """줄 번호를 범위로 묶는다(L12-18, L40). 찍은 숫자가 LINE_LIST_MAX 를 넘으면 남은 줄은 "+N more" 로 센다."""
    nums = sorted(set(lines))
    runs = []
    for n in nums:
        if runs and n == runs[-1][1] + 1:
            runs[-1][1] = n
        else:
            runs.append([n, n])
    parts, used, covered = [], 0, 0
    for a, b in runs:
        cost = 1 if a == b else 2
        if used + cost > LINE_LIST_MAX:
            break
        parts.append(f"L{a}" if a == b else f"L{a}-{b}")
        used, covered = used + cost, covered + b - a + 1
    rest = len(nums) - covered
    return ", ".join(parts) + (f" (+{rest} more)" if rest else "")


def record_leftovers(data, path, rel, kind, text, added, rows, cfg, pats, pub):
    return conv_leftovers.record_leftovers(data, path, rel, kind, text, added, rows, cfg, pats, pub, check_lines, invisible_lines)



def target(path, data):
    """검사하는 파일이면 (root, cfg, rel, kind, ext), 아니면 None. kind 는 "comment"(코드 파일)나 "doc"(모델용 문서)."""
    ext = os.path.splitext(path)[1].lower()
    root = project_root(path, data)
    cfg = load_cfg(root)
    rel = os.path.relpath(path, root)
    kind = "comment" if FAMILY.get(ext) else ("doc" if doc_class(rel) else None)
    if not kind or excluded(path, rel, cfg):
        return None
    return root, cfg, rel, kind, ext


def generated(text):
    return any(GEN_MARK.search(l) for l in text.split("\n", 6)[:6])


# 범주별 고치는 법. 알림만 보고 고칠 수 있게 줄 번호와 함께 준다(스킬을 열라는 말은 실제로 따르지 않았다)
FIX_HINT = {"history marker": "keep the reason as a sentence about the code now and move dates, ids, rounds, who decided and what "
                              "it used to do to the commit message",
            "Ref tail without a reason sentence": "write the reason sentence above the Ref: line"}
SCRIPT_NAME = {"latin": "English", "hangul": "Korean", "cjk": "Japanese or Chinese", "cyrillic": "Russian"}


COMMENT_TAIL = "Fix those lines; a false match (quoted text, a needed symbol) can stay, said once in your report."
DOC_TAIL = "Fix those lines; a false match (quoted text, a needed symbol) can stay, said once in your report."


def file_notice(data, path, rel, kind, ext, cfg, text, added, state, tail=True):
    """한 파일에서 added(0 기반 줄 번호) 줄의 알림 문장. state 로 중복을 거르고 state 를 고친다.

    (문장 목록, state 가 바뀌었나) 를 돌려준다(새로 알릴 것이 없으면 빈 목록). Stop 보고용 기존 문제도 쌓는다.
    Edit/Write 경로와 Bash 경로(bash_writes.py)가 함께 쓴다. tail 이 거짓이면 끝의 대응 문장(COMMENT_TAIL, DOC_TAIL)을 빼서
    여러 파일을 한 알림에 담는 쪽이 한 번만 붙이게 한다.
    """
    pats, pub = compile_patterns(cfg)
    layout = kind == "comment" and layout_metrics.enabled(ext)
    rows = lex(text, FAMILY[ext], keep_code=layout) if kind == "comment" else None
    record_leftovers(data, path, rel, kind, text, added, rows, cfg, pats, pub)
    if not added:
        return [], False

    # Added-line checks
    exp, doc_det = None, {}
    if kind == "comment":
        problems = check_lines(rows, added, pats, pub, cfg)
        labels = step_labels(rows, text.split("\n"), cfg)
        exp = expected_script(rows, added, cfg, path, ext, labels)
        if exp:
            problems += [(ln, "language mismatch") for ln in language_lines(rows, added, exp, labels)]
    else:
        problems = doc_check(text, added, rel, cfg, pats, pub)
        shape, doc_det = doc_shape(text, added, path, rel, pub)
        problems += shape
    problems += [(ln, "invisible character") for ln in invisible_lines(text, added)]

    # Layout of the functions this edit wrote or grew
    key = os.path.abspath(path)
    recheck, shapes = layout_step(state, key, text, rows, added, ext, cfg) if layout else ([], [])
    if not problems and not shapes and not recheck:
        return [], False

    # One notice per (file, category); layout per (file, category, function)
    seen = state["files"].get(key)
    seen = seen if isinstance(seen, list) else []
    fresh = [(ln, c) for ln, c in problems if c not in seen]
    fresh_shapes = [(cat, name, desc, again) for cat, name, desc, again in shapes if again or "%s|%s" % (cat, name) not in seen]

    # Remember notices and doc rechecks
    state["files"][key] = seen + [c for c in dict.fromkeys(c for _, c in fresh)] + [
        "%s|%s" % (cat, name) for cat, name, _, again in fresh_shapes if not again]
    docs = [name for cat, name, _, again in fresh_shapes if cat == "doc summary" and not again]
    state["doc_recheck"][key] = docs
    if not state["doc_recheck"][key]:
        del state["doc_recheck"][key]
    dirty = bool(fresh or fresh_shapes or recheck)

    # Comment notice text
    allow = cfg.get("allow_chars") or []
    parts = []
    for cat in CATEGORY_ORDER:
        lns = sorted({ln for ln, c in fresh if c == cat})
        if not lns:
            continue
        if cat == "non-keyboard symbol":
            det = symbol_detail(text, lns, allow)
        elif cat == "invisible character":
            det = invisible_detail(text, lns)
        elif cat == "escaped character":
            det = escape_detail(text, lns)
        elif kind == "comment" and cat == "language mismatch" and exp in SCRIPT_NAME:
            det = f"write it in {SCRIPT_NAME[exp]} like the file's other comments"
        else:
            det = FIX_HINT.get(cat, "") if kind == "comment" else doc_det.get(cat) or DOC_HINT.get(cat, "")
        parts.append(f"{line_list(lns)} {cat}" + (f": {det}" if det else ""))

    body = []
    if parts:
        what, end = ("comment", COMMENT_TAIL) if kind == "comment" else ("agent-doc", DOC_TAIL)
        body.append(f'{rel} may not follow the {what} conventions. {"; ".join(parts)}.' + (" " + end if tail else ""))
    if fresh_shapes:
        order = {c: i for i, c in enumerate(layout_metrics.CATEGORIES)}
        items = [(cat, desc, again) for cat, _, desc, again in sorted(fresh_shapes, key=lambda x: order[x[0]])]
        body.append(f"{rel} layout (readable-code): " + layout_metrics.notice(items, layout_metrics.LANG_BY_EXT[ext]))
    return body, dirty


def save_state(path, state):
    try:
        json.dump(state, open(path, "w"))
    except OSError:
        pass


def notice_tag(data, body):
    """주석 알림과 layout 알림은 level 이 같아 한 태그에 담는다."""
    return f'<harness-hook name="{NAME}" level="info"{harness_nonce.attr(data.get("session_id"))}>{" ".join(body)}</harness-hook>'


def main():
    import conv_env  # 끄기 스위치는 harness.env 층과 /config 옵션에서도 읽는다
    if conv_env.is_off("CONVENTIONS_CHECK"):
        return 0
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0
    if data.get("hook_event_name") == "Stop":
        return report_leftovers(data)
    tool = data.get("tool_name") or ""
    if tool not in ("Write", "Edit", "MultiEdit"):
        return 0

    # Which file, and whether it is checked at all
    ti = data.get("tool_input") or {}
    path = ti.get("file_path") or ""
    if not path:
        return 0
    found = target(path, data)
    if not found:
        return 0
    root, cfg, rel, kind, ext = found

    # Text and the lines this edit added
    resp = data.get("tool_response") if isinstance(data.get("tool_response"), dict) else {}
    try:
        text = Path(path).read_text(encoding="utf-8") if os.path.getsize(path) <= MAX_BYTES else None
    except (OSError, UnicodeDecodeError):
        text = None
    got = collect(tool, ti, resp, text)
    if not got:
        return 0
    text, added = got
    if kind == "comment" and generated(text):
        return 0

    state_path = state_file(data.get("session_id"), data.get("agent_id"))
    with state_lock(state_path):
        state = load_state(state_path)
        body, dirty = file_notice(data, path, rel, kind, ext, cfg, text, added, state)
        if dirty:
            save_state(state_path, state)
    if body:
        json.dump({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": notice_tag(data, body)}},
                  sys.stdout, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
