#!/usr/bin/env python3
"""PostToolUse(Write|Edit|MultiEdit) 알림: 이번에 추가한 줄이 주석, 모델용 문서 관례를 벗어난 것 같으면 한 줄로 알린다.

막지 않는다(decision 없음). additionalContext(level=info) 한 줄만 주입하고, 고치는 법은 스킬(qwreey-conventions:comments, qwreey-conventions:agent-docs)이 가진다.

남은 기존 주석 보고: 같은 PostToolUse 에서 이번에 추가하지 않은 줄의 문제를 범주별(이력, 기호, 이스케이프, 보이지 않는 문자) 줄 수로 세어
  $TMPDIR/claude-conventions/<session_id>.left.<main|agent_id>.json 에 조용히 쌓는다(파일마다 마지막 편집 기준). Stop 에서 모든 호출한 쪽 기록을 합쳐
  사용자에게 한 줄을 systemMessage 로 보인다(내용이 바뀐 때만). reuse-check 가 따로 쓰는 <session_id>.reuse.<main|agent_id>.json(전부터 있던 같은 목록 수, 원본과 다른 사본 수)도 합쳐 보인다. 고치지 않는다. 모델 턴을 늘리지 않으려고 Stop 의 additionalContext 나 decision 은 쓰지 않는다.

보는 것: 이번에 추가된 줄만. Edit/MultiEdit 는 new_string 에서 old_string 에 없던 줄, Write 는 새 파일이면 전체, 덮어쓰기면
  tool_response.originalFile 과의 차이(없으면 structuredPatch 의 + 줄, 둘 다 없으면 보지 않는다. 옛 줄을 새로 오인하지 않으려고).

코드 파일(주석 줄만; 파일 전체를 확장자별 간이 렉서로 읽어 문자열 리터럴 안의 `--`, `//`, `#` 는 주석이 아니다)
  - history marker: 원장 번호, 날짜, 라운드, 작업 이력 경로, 결정 문구. `Ref:` 꼬리는 같은 주석 덩어리에 이유 문장이 있으면 통과
  - non-keyboard symbol: 사람이 키보드로 치지 않는 문자(기호, 가운뎃점, 곡선 따옴표, 전각, 이모지). ASCII 와 모든 문자 체계의 글자(한글, 키릴, 악센트 라틴 등)와 숫자는 통과
  - escaped character: 주석 안의 유니코드 이스케이프(백슬래시 u 와 16진수 넷 등). 금지 문자를 이스케이프로 적어 검사를 피한 것으로 본다
  - invisible character: 보이지 않는 문자, 방향 제어 문자. 주석이 아니라 추가된 줄 전체에서 본다
  - language mismatch: 파일 주석의 90% 이상이 한 문자 체계(기존 10줄 이상)인데 추가된 줄이 다른 체계 단어를 3개 이상 쓴다.
    새 파일은 저장소 comment_language, 없으면 같은 폴더 형제 파일의 다수, 그것도 없으면 검사하지 않는다. 지시자 줄(--!strict, eslint-disable 등)은 뺀다
모델용 문서(CLAUDE.md, SKILL.md, agents/*.md, .claude/rules/*.md, skills/**/*.md; 추가된 줄만, frontmatter, 코드 펜스, 인라인 코드, URL, 경로 토큰 안은 통과)
  - 입구 문서: 날짜, audit/session/handoff 경로와 .claude/ 아래 기록 폴더 경로, 라운드, 결정 문구, 실측 표지, 변경 서술, 같은 줄에 .md 경로가 없는 원장 id
  - skills/**/references/*.md: 결정 문구, 라운드, audit/N 근거, 실측 표지, 정정 배너만(날짜, id, "previously" 는 통과)
  - `status:` 줄은 통과
제외: 확장자 표 밖, 생성 파일(머리 6줄 표시), 픽스처, testdata, node_modules 등, 설정의 exclude.

저장소 설정: <프로젝트>/.claude/conventions.json (없으면 예전 이름 .claude/comments.json)
  {"allow_ref_tail": true, "comment_language": "en", "allow_chars": ["emoji", "x"], "public_ids": ["Quad\\\\d{4}"],
   "exclude": ["docs/**", "*.md"], "patterns": {"ledger": "<정규식>", "date": null}, "min_reason_words": 3}
  allow_chars: "emoji" 는 이모지를 끄고, 그 밖의 항목은 허용할 글자들이다. public_ids: 줄에서 먼저 지우고 검사하는 공개 식별자 정규식.
  patterns: 이름별로 덮어쓰기, null 이면 끈다.
끄기: 환경 변수 CONVENTIONS_CHECK=off
알림 중복: (session_id, 호출한 쪽, 파일, 범주)마다 한 번(이미 알린 범주는 다시 알리지 않고, 새 범주는 알린다). compact 회차도 구분한다(compact_epoch.py, PreCompact 훅이 올린다).
상태 파일: $TMPDIR/claude-conventions/<session_id>.c<회차>[.a<agent_id>].json
"""
import fnmatch
import json
import os
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import compact_epoch  # noqa: E402
from conv_edit import GEN_MARK, MAX_BYTES, SKIP_PARTS, SKIP_SUFFIX, collect, project_root  # noqa: E402
from conv_lex import FAMILY, comment_body, lex  # noqa: E402

NAME = "qwreey-conventions"
NS = "claude-conventions"  # 상태 경로는 이름 변경 전과 같게 둔다
HOME = Path(os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude"))

PATTERNS = {
    "ledger": r"\b[A-Z]{1,2}-?\d{2,4}\b",
    "date": r"\b20\d\d-\d\d-\d\d\b",
    "round": r"\bround\s*\d+\b|라운드\s*\d+|감사\s*\d+\s*차",
    "path": r"\.claude/|(?<![\w-])session/|(?<![\w-])audit/",
    "decision": r"사용자\s*(?:결정|지시|요청|합의|말)|\bper (?:the )?user\b|\bas (?:the user )?(?:discussed|decided|agreed)\b|\bthe user (?:decided|asked|wanted|requested)\b",
}
# 내장 공개 식별자, 표준 번호: 줄에서 먼저 지운 뒤 검사한다. 저장소 public_ids 는 여기에 더한다.
BUILTIN_PUBLIC = [r"error-code:\s*\S+", r"\bR(?:6|15)\b", r"\bES\d{4}\b", r"\bH26[45]\b", r"\bUTF-?\d+\b", r"\bSHA-?\d+\b", r"\bP\d{2,3}\b(?=\s*(?:p|fps|hz))",
                  r"\b[A-Z]{1,2}\d{2,4}(?=px|pt|ms|hz|fps|kb|mb|gb)",
                  # 번호 모양이지만 원장이 아닌 것: 정수 폭(F64, I32), 아키텍처(X86), C 표준(C99), 컴파일러 오류 코드(TS2322, E0308)
                  r"\b[FIUS](?:8|16|32|64|128)\b", r"\bX86\b", r"\bC(?:89|90|99|11|17|23)\b", r"\bTS\d{4}\b", r"\bE0\d{3}\b"]
# 주석 안의 유니코드 이스케이프(\\uXXXX, \\u{...}, \\UXXXXXXXX): 금지 문자를 이스케이프로 적어 검사를 피한 것
ESCAPE = re.compile(r"\\u[0-9A-Fa-f]{4}|\\u\{[0-9A-Fa-f]+\}|\\U[0-9A-Fa-f]{8}")
# 알림 범주 순서(알림 문장에서 앞일수록 먼저 고친다)
CATEGORY_ORDER = ("history marker", "Ref tail without a reason sentence", "non-keyboard symbol", "escaped character",
                  "invisible character", "language mismatch")
# 흔한 기호의 대체. 키가 없으면 ASCII 나 평범한 단어로 풀어 쓴다.
SYMBOL_FIX = {"\u2014": "-", "\u2013": "-", "\u2015": "-", "\u2212": "-", "\u00b7": ",", "\u2022": "-", "\u2026": "...",
              "\u2192": "->", "\u2190": "<-", "\u2194": "<->", "\u21d2": "=>", "\u00a7": "(omit)", "\u00d7": "x",
              "\u2265": ">=", "\u2264": "<=", "\u2260": "!=", "\u201c": '"', "\u201d": '"', "\u2018": "'", "\u2019": "'",
              "\u2713": "ok", "\u2714": "ok", "\u2717": "FAIL", "\u2718": "FAIL", "\u26a0": "NOTE:"}
REF_LINE = re.compile(r"^\s*Ref\s*:", re.I)
WORD = re.compile(r"[A-Za-z\u00c0-\u024f]{2,}|[가-힣]{2,}")
DEFAULTS = {"allow_ref_tail": True, "public_ids": [], "exclude": [], "patterns": {}, "min_reason_words": 3,
            "comment_language": None, "allow_chars": []}

# 모델용 문서 패턴. 날짜, round, 결정 문구는 위 PATTERNS 와 설정 덮어쓰기를 공유한다.
DOC_PATTERNS = {
    "decision": r"사용자\s*(?:결정|합의)|\bper (?:the )?user\b|\bas (?:the user )?(?:discussed|decided|agreed)\b|\bthe user decided\b|사용자\s*20\d\d",
    "path": r"(?<![\w-])(?:audit|session|handoff)/|\.claude/(?:plan|base|research|audit|handoff|archive)/",
    "ref_path": r"(?<![\w-])audit/\d+",
    "tag": r"\[(?:실측|측정|추정|추론|measured|estimated?|inferred)[^\]]*\]",
    "narration": r"\b(?:previously|recently)\b|\bas of\b(?!\s+(?:v?\d|luau|version))|현재 기준|지난\s?(?:주|번)|요즘|사실 정정|\bfact fix\b",
    "banner": r"사실 정정|\bfact fix\b|정정\s*:|\bcorrection\s*:",
    "ledger": r"\b[A-Z]{1,2}-\d{2,4}\b",
}
DOC_ENTRY = ("date", "path", "round", "decision", "tag", "narration", "ledger")
DOC_REFERENCE = ("decision", "round", "ref_path", "tag", "banner")
DOC_STATUS = re.compile(r"^\s*(?:[-*>]\s*)?\**status\**\s*:", re.I)
INLINE_CODE = re.compile(r"`[^`]*`")
URL = re.compile(r"https?://\S+")
PATH_TOKEN = re.compile(r"\S*/\S*|\S+\.\w{1,5}\b")
HAS_MD_PATH = re.compile(r"\S+\.md\b")

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


def sibling_majority(path, fam_ext):
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
            cnt += comment_stats(lex(Path(p).read_text(encoding="utf-8"), fam))
        except (OSError, UnicodeDecodeError):
            continue
    return majority(cnt)


def expected_script(rows, added, cfg, path, ext):
    """이 파일 주석이 따를 문자 체계. 파일 다수 -> 저장소 comment_language -> 형제 파일 다수 -> None(검사 안 함)."""
    own = majority(comment_stats(rows, skip=added))
    if own:
        return own
    lang = cfg.get("comment_language")
    if isinstance(lang, str) and lang.lower()[:2] in LANG_SCRIPT:
        return LANG_SCRIPT[lang.lower()[:2]]
    return sibling_majority(path, ext)


def language_lines(rows, added, expected):
    """추가된 줄 중 다른 문자 체계가 우세한 줄들의 단어가 LANG_MIN_WORDS 개 이상이면 그 줄 번호(1 기반)."""
    hits, words = [], 0
    for i in sorted(added):
        if i >= len(rows) or not rows[i]["c"] or any(DIRECTIVE.match(c) for c in rows[i]["c"]):
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


def doc_class(rel):
    """모델용 문서면 "entry" 나 "reference", 아니면 None."""
    parts = Path(rel).parts
    name = parts[-1]
    if not name.endswith(".md"):
        return None
    if "skills" in parts[:-1]:
        after = parts[parts.index("skills") + 1:-1]
        return "reference" if "references" in after else "entry"
    if name in ("CLAUDE.md", "SKILL.md") or (len(parts) > 1 and parts[-2] == "agents"):
        return "entry"
    if ".claude" in parts[:-1] and "rules" in parts[:-1]:
        return "entry"
    return None


def doc_lines(text):
    """(줄 번호 0 기반, 검사할 줄) 쌍. frontmatter 와 코드 펜스 안은 뺀다."""
    out, fence, front = [], None, False
    for idx, line in enumerate(text.split("\n")):
        if idx == 0 and line.strip() == "---":
            front = True
            continue
        if front:
            front = line.strip() != "---"
            continue
        m = re.match(r"^\s*(`{3,}|~{3,})", line)
        if m:
            if fence is None:
                fence = m.group(1)[0]
            elif m.group(1)[0] == fence:
                fence = None
            continue
        if fence is None:
            out.append((idx, line))
    return out


def doc_check(text, added, rel, cfg, pats, pub):
    """모델용 문서에서 추가된 줄의 이력 표지. [(줄 번호(1 기반), 범주)]."""
    cls = doc_class(rel)
    if not cls:
        return []
    names = DOC_ENTRY if cls == "entry" else DOC_REFERENCE
    rx = {}
    for k in names:
        if k in ("date", "round", "decision"):
            if k == "decision" and k in pats:
                rx[k] = re.compile(DOC_PATTERNS[k], re.I)
            elif k in pats:
                rx[k] = pats[k]
        else:
            rx[k] = re.compile(DOC_PATTERNS[k], re.I if k in ("narration", "banner", "tag") else 0)
    out = []
    for idx, line in doc_lines(text):
        if idx not in added or DOC_STATUS.match(line):
            continue
        s = URL.sub(" ", INLINE_CODE.sub(" ", line))
        for p in pub:
            s = p.sub(" ", s)
        bare = PATH_TOKEN.sub(" ", s)  # 경로, 파일명 속 날짜나 id 는 이력이 아니다
        hit = False
        for k, r in rx.items():
            if k in ("path", "ref_path"):
                hit = hit or bool(r.search(s))
            elif k == "ledger":
                hit = hit or (bool(r.search(bare)) and not HAS_MD_PATH.search(s))
            else:
                hit = hit or bool(r.search(bare if k == "date" else s))
        if hit:
            out.append((idx + 1, "history marker"))
    return out


def state_file(sid, agent_id):
    return compact_epoch.state_path("qwreey-conventions", NS, sid, agent_id)


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


def line_list(lines):
    nums = sorted(set(lines))
    shown = ", ".join(f"L{n}" for n in nums[:5])
    return shown + (f" (+{len(nums) - 5} more)" if len(nums) > 5 else "")


# ---------- 남은 기존 주석 보고 ----------
# 편집할 때마다 "이번에 추가하지 않은 줄"의 문제를 범주별로 세어 (세션, 호출한 쪽)별 파일에 조용히 쌓고,
# 메인 에이전트의 Stop 에서 사용자에게 한 줄(systemMessage)로 보여 준다. 모델 턴을 늘리지 않고 고치지도 않는다.
LEFT_LABEL = {"history marker": "이력", "Ref tail without a reason sentence": "이력", "non-keyboard symbol": "기호",
              "escaped character": "이스케이프", "invisible character": "보이지 않는 문자"}
LEFT_MAX_FILES = 5


def left_dir():
    import tempfile
    d = os.path.join(tempfile.gettempdir(), NS)
    os.makedirs(d, exist_ok=True)
    return d


def left_path(sid, agent_id, d=None):
    who = re.sub(r"[^\w-]", "", str(agent_id)) if agent_id else "main"
    return os.path.join(d or left_dir(), re.sub(r"[^\w-]", "", str(sid or "nosession")) + ".left." + who + ".json")


def record_leftovers(data, path, rel, kind, text, added, rows, cfg, pats, pub):
    """이번 편집에서 추가하지 않은 줄의 문제를 범주별 줄 수로 세어 쌓는다. 같은 파일은 마지막 편집 기준으로 덮어쓴다."""
    try:
        old = set(range(text.count("\n") + 1)) - added
        probs = check_lines(rows, old, pats, pub, cfg) if kind == "comment" else doc_check(text, old, rel, cfg, pats, pub)
        probs += [(ln, "invisible character") for ln in invisible_lines(text, old)]
        cnt = Counter()
        for ln, cat in set(probs):
            cnt[LEFT_LABEL.get(cat, cat)] += 1
        fp = left_path(data.get("session_id"), data.get("agent_id"))
        try:
            rec = json.load(open(fp))
        except Exception:
            rec = {}
        key = os.path.abspath(path)
        if cnt:
            import time
            rec[key] = {"rel": rel, "n": dict(cnt), "t": time.time()}
        elif key in rec:
            del rec[key]
        else:
            return
        json.dump(rec, open(fp, "w"), ensure_ascii=False)
    except Exception:
        pass


def _latest(pattern):
    """같은 파일의 여러 호출한 쪽 기록 중 가장 최근 것. {절대 경로: 기록}."""
    import glob
    best = {}
    for fp in glob.glob(pattern):
        try:
            for k, v in json.load(open(fp)).items():
                if k not in best or v["t"] > best[k]["t"]:
                    best[k] = v
        except Exception:
            continue
    return best


def leftover_message(sid, d=None):
    """세션의 모든 호출한 쪽 기록을 합쳐 사용자용 글. 첫 줄은 전부터 있던 문제(주석, 같은 목록), 둘째 줄은 원본과 달라진 사본. 없으면 None.
    같은 목록과 사본 기록은 reuse-check 가 따로 쓴다(두 훅이 한 파일을 동시에 고쳐 쓰지 않게)."""
    base = os.path.join(d or left_dir(), re.sub(r"[^\w-]", "", str(sid or "nosession")))
    left, reuse = _latest(base + ".left.*.json"), _latest(base + ".reuse.*.json")
    rows, diff = {}, []
    for k, v in left.items():
        if v["n"] and os.path.exists(k):
            rows[k] = (v["rel"], dict(v["n"]))
    for k, v in reuse.items():
        if not os.path.exists(k):
            continue
        if v.get("dup"):
            rows.setdefault(k, (v["rel"], {}))[1]["같은 목록이 두 곳"] = v["dup"]
        if v.get("differ"):
            diff.append((v["rel"], v["differ"]))
    order = ["이력", "기호", "이스케이프", "보이지 않는 문자", "같은 목록이 두 곳"]
    items = sorted(rows.values())
    lines = []
    if items:
        shown = ", ".join(f"{rel}(" + ", ".join(f"{c} {n[c]}" for c in order if c in n) + ")" for rel, n in items[:LEFT_MAX_FILES])
        more = f" 외 {len(items) - LEFT_MAX_FILES}개" if len(items) > LEFT_MAX_FILES else ""
        lines.append(f'손댄 파일에 전부터 있던 문제: {shown}{more}. 고치려면 "기존 문제도 정리해줘" 라고 하시면 됩니다.')
    if diff:
        shown = ", ".join(f"{rel} {n}" for rel, n in sorted(diff)[:LEFT_MAX_FILES])
        more = f" 외 {len(diff) - LEFT_MAX_FILES}개" if len(diff) > LEFT_MAX_FILES else ""
        lines.append(f"사본이 원본과 다름: {shown}{more}. 동작이 달라질 수 있습니다.")
    return "\n".join(lines) or None


def report_leftovers(data):
    """Stop: 내용이 바뀌었을 때만 한 번 사용자에게 보인다(턴을 늘리지 않으려고 additionalContext 가 아니라 systemMessage)."""
    msg = leftover_message(data.get("session_id"))
    if not msg:
        return 0
    mark = os.path.join(left_dir(), re.sub(r"[^\w-]", "", str(data.get("session_id") or "nosession")) + ".reported.json")
    try:
        if json.load(open(mark)).get("msg") == msg:
            return 0
    except Exception:
        pass
    try:
        json.dump({"msg": msg}, open(mark, "w"), ensure_ascii=False)
    except OSError:
        pass
    json.dump({"systemMessage": msg}, sys.stdout, ensure_ascii=False)
    return 0


def main():
    if os.environ.get("CONVENTIONS_CHECK", "").lower() == "off":
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
    ti = data.get("tool_input") or {}
    path = ti.get("file_path") or ""
    ext = os.path.splitext(path)[1].lower()
    fam = FAMILY.get(ext)
    if not path:
        return 0
    resp = data.get("tool_response") if isinstance(data.get("tool_response"), dict) else {}
    root = project_root(path, data)
    cfg = load_cfg(root)
    rel = os.path.relpath(path, root)
    kind = "comment" if fam else ("doc" if doc_class(rel) else None)
    if not kind or excluded(path, rel, cfg):
        return 0
    try:
        text = Path(path).read_text(encoding="utf-8") if os.path.getsize(path) <= MAX_BYTES else None
    except (OSError, UnicodeDecodeError):
        text = None
    got = collect(tool, ti, resp, text)
    if not got:
        return 0
    text, added = got
    if kind == "comment" and any(GEN_MARK.search(l) for l in text.split("\n", 6)[:6]):
        return 0
    pats, pub = compile_patterns(cfg)
    rows = lex(text, fam) if kind == "comment" else None
    record_leftovers(data, path, rel, kind, text, added, rows, cfg, pats, pub)
    if not added:
        return 0
    if kind == "comment":
        problems = check_lines(rows, added, pats, pub, cfg)
        exp = expected_script(rows, added, cfg, path, ext)
        if exp:
            problems += [(ln, "language mismatch") for ln in language_lines(rows, added, exp)]
    else:
        problems = doc_check(text, added, rel, cfg, pats, pub)
    problems += [(ln, "invisible character") for ln in invisible_lines(text, added)]
    if not problems:
        return 0

    state_path = state_file(data.get("session_id"), data.get("agent_id"))
    try:
        state = json.load(open(state_path))
    except Exception:
        state = {}
    key = os.path.abspath(path)
    # 알림 단위는 (파일, 범주): 이미 알린 범주는 다시 알리지 않고, 새 범주만 알린다
    seen = state.setdefault("files", {}).get(key)
    seen = seen if isinstance(seen, list) else []
    fresh = [(ln, c) for ln, c in problems if c not in seen]
    if not fresh:
        return 0
    state["files"][key] = seen + [c for c in dict.fromkeys(c for _, c in fresh)]
    try:
        json.dump(state, open(state_path, "w"))
    except OSError:
        pass

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
        else:
            det = ""
        parts.append(f"{line_list(lns)} {cat}" + (f": {det}" if det else ""))
    what, skill = ("comment", "comments") if kind == "comment" else ("agent-doc", "agent-docs")
    msg = (f'<harness-hook name="{NAME}" level="info">{rel} may not follow the {what} conventions. {"; ".join(parts)}. '
           f'Load the {NAME}:{skill} skill and fix the lines you added.</harness-hook>')
    json.dump({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": msg}}, sys.stdout, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
