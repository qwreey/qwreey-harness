#!/usr/bin/env python3
"""qwreey-conventions 검사를 파일 전체(모든 줄)에 돌리고, 판단이 필요 없는 문자만 주석과 모델용 문서 본문 안에서 기계적으로 고친다.

쓰는 법(저장소 안에서, 모델을 부르지 않는다):
  python3 -I conventions-scan.py scan [경로...] [--json] [--category C ...] [--summary] [--top N] [--root DIR]
  python3 -I conventions-scan.py scan --fix [--dry-run] ...      (= fix [경로...] [--dry-run])
  python3 -I conventions-scan.py layout [경로...] [--json] [--summary] [--root DIR]
layout: 함수마다 읽기 모양 지표(hooks/layout_metrics.py)와 훅의 layout 알림 범주를 모든 함수에 대해 낸다. 고치지 않는다.
  HARNESS_READABLE_CODE 와 무관하게 돈다. Bash 로 고친 파일처럼 훅이 못 본 편집을 확인하고, 쓰기 실측의 채점에도 쓴다.
경로를 안 주면 저장소 루트 전체. git 저장소면 git ls-files(추적 + 무시되지 않은 새 파일)만 본다.
출력: 찾은 것마다 `경로:줄: 범주: 내용`, 끝에 범주별, 파일별 수. --json 은 기계용 한 덩어리.
종료 코드: 0 = 남은 문제 없음, 1 = 남은 문제 있음(scan 은 찾은 것, fix 는 고친 뒤 남은 것), 2 = 사용법 오류.

검사는 훅(hooks/conventions-check.py)의 함수를 그대로 불러 쓴다: 같은 확장자 표, 제외(SKIP_PARTS, 생성 파일 표시, 설정의
exclude), .claude/conventions.json. 다른 점은 "추가한 줄"이 아니라 모든 줄을 보는 것과, 주석 언어 기준이 파일 전체 다수라는 것.

고치는 범주: non-keyboard symbol(코드 파일 주석 안), invisible character(코드 파일 주석 안, 모델용 문서 본문).
  모델용 문서의 기호는 훅이 검사하지 않으므로 고치지도 않는다. 코드 줄, 문자열, 문서의 코드 펜스, frontmatter, 인라인 코드,
  URL, 경로 토큰 안의 것은 그대로 두고 "needs judgment" 로 남긴다. 이력, Ref 꼬리, 이스케이프, 언어, 이모지, 상자 그림,
  표에 없는 기호도 판단이 필요해 남긴다. 사본(@copy-of 파일, 정본이 아닌 @start-replace 영역)은 고치지 않고 알린다:
  정본을 고치고 tools/sync-copies.py --apply 로 옮겨야 사본 검사가 깨지지 않는다.
대체 규칙(SYMBOL_FIX 표의 일부와 문맥 규칙):
  - em dash, en dash, horizontal bar, minus: 앞뒤 공백을 하나로 모아 " - ". 숫자 사이에 붙은 en dash, minus 는 "-"(범위, 음수).
    조각 맨 앞이면 앞 공백을 그대로 두고 "- ".
  - middle dot: 조각 맨 앞(목록 표지)이면 "-", 나머지는 앞 공백을 지우고 ", "(나열: "manual, auto", "0.734, 0.742").
    "/" 는 쓰지 않는다: 곱 n*m 으로 쓴 가운뎃점을 나눗셈으로 바꾸게 된다. 곱셈이었다면 diff 검토에서 고친다.
  - 따옴표로 바로 감싼 글자("x" 꼴)는 그 글자 자체를 가리키므로 고치지 않는다. 주석 안의 인라인 코드와 URL 도 그대로 둔다.
  - bullet "-", ellipsis "...", 화살표 -> <- <-> =>, >= <= !=, multiplication "x", 곡선 따옴표는 곧은 따옴표,
    section sign 은 지우고 뒤 공백도 지운다, 동그라미 숫자는 "1)"(뒤에 글자가 붙으면 공백 하나), 전각 문자는 NFKC 의 ASCII,
    전각 공백은 공백.
  - 보이지 않는 문자: NBSP 는 공백, 나머지(zero-width, 방향 제어, soft hyphen, word joiner, 파일 맨 앞이 아닌 BOM)는 지운다.
    이모지 옆 ZWJ 는 이모지 일부라 남긴다.
고친 뒤 확인(토큰 가드): 코드 파일은 원본과 결과를 같은 렉서로 다시 읽어 주석 밖 글자(코드, 문자열, 주석 여닫는 표식)와
  줄마다 주석 조각 수가 같아야 한다. 문서는 frontmatter, 코드 펜스 줄과 본문 줄의 보호 토큰(인라인 코드, URL, 경로)이 같아야 한다.
  다르면 그 파일은 쓰지 않고(이미 썼으면 원본 바이트로 되돌리고) rejected 로 보고한다.
"""
import argparse
import difflib
import importlib.util
import json
import os
import subprocess
import sys
import unicodedata
from collections import Counter
from pathlib import Path

HOOKS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks")
sys.path.insert(0, HOOKS)  # python3 -I 는 스크립트 디렉터리를 path 에 넣지 않는다


def _load_check():
    # 파일 이름에 하이픈이 있어 import 문으로는 못 부른다
    spec = importlib.util.spec_from_file_location("conventions_check", os.path.join(HOOKS, "conventions-check.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


cc = _load_check()
from conv_edit import GEN_MARK, MAX_BYTES, SKIP_PARTS  # noqa: E402
from conv_lex import FAMILY, lex  # noqa: E402
import copy_regions  # noqa: E402
import layout_metrics  # noqa: E402

CATEGORIES = cc.CATEGORY_ORDER
ALIASES = {"history": "history marker", "ref": "Ref tail without a reason sentence", "symbol": "non-keyboard symbol",
           "escape": "escaped character", "invisible": "invisible character", "language": "language mismatch"}
FIXABLE = ("non-keyboard symbol", "invisible character")
DOC_FIXABLE = ("invisible character",)  # 훅이 문서의 기호는 검사하지 않는다

# 한 글자를 한 대체로 바꾸는 것. 문맥이 필요한 대시, 가운뎃점, section sign, 동그라미 숫자는 fix_segment 가 따로 다룬다.
PLAIN_FIX = {"\u2022": "-", "\u2026": "...", "\u2192": "->", "\u2190": "<-", "\u2194": "<->", "\u21d2": "=>",
             "\u2265": ">=", "\u2264": "<=", "\u2260": "!=", "\u00d7": "x",
             "\u201c": '"', "\u201d": '"', "\u2018": "'", "\u2019": "'", "\u3000": " "}
DASHES = "\u2014\u2013\u2015\u2212"
RANGE_DASHES = "\u2013\u2212"  # 숫자 사이에 붙으면 범위나 음수라 "-" 한 글자
MIDDLE_DOT = "\u00b7"
SECTION = "\u00a7"
ZWJ = "\u200d"
HSPACE = " \t"
QUOTES = "\"'`"
COMMENT_KEEP = (cc.INLINE_CODE, cc.URL)  # 주석 안: 인용한 코드와 URL 은 글자 그대로가 뜻이다
DOC_KEEP = (cc.INLINE_CODE, cc.URL, cc.PATH_TOKEN)  # 문서 본문: 훅이 검사에서 빼는 구간과 같다


# ---------- 파일 고르기 ----------

def repo_root(start):
    try:
        out = subprocess.run(["git", "-C", start, "rev-parse", "--show-toplevel"], capture_output=True, text=True, timeout=30)
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    d = os.path.abspath(start)
    while d and d != "/":
        if os.path.exists(os.path.join(d, ".git")) or os.path.isdir(os.path.join(d, ".claude")):
            return d
        d = os.path.dirname(d)
    return os.path.abspath(start)


def list_files(root, paths):
    """root 기준 상대 경로 목록. git 이면 추적 파일과 무시되지 않은 새 파일, 아니면 걷기(SKIP_PARTS 폴더는 들어가지 않는다)."""
    rels = [os.path.relpath(os.path.abspath(p), root) for p in paths] or ["."]
    try:
        out = subprocess.run(["git", "-C", root, "ls-files", "-z", "-co", "--exclude-standard", "--"] + rels,
                             capture_output=True, timeout=120)
        if out.returncode == 0:
            return sorted(set(p for p in out.stdout.decode("utf-8", "surrogateescape").split("\0") if p))
    except (OSError, subprocess.SubprocessError):
        pass
    found = []
    for r in rels:
        top = os.path.join(root, r)
        if os.path.isfile(top):
            found.append(os.path.normpath(r))
            continue
        for d, dirs, files in os.walk(top):
            dirs[:] = sorted(x for x in dirs if x not in SKIP_PARTS)
            found += [os.path.relpath(os.path.join(d, f), root) for f in files]
    return sorted(set(found))


def file_kind(rel):
    if FAMILY.get(os.path.splitext(rel)[1].lower()):
        return "comment"
    return "doc" if cc.doc_class(rel) else None


def read_text(path):
    """(텍스트, 건너뛴 이유). 줄 끝(\\r\\n)은 바꾸지 않고 그대로 둔다: 고친 파일을 바이트 그대로 되쓰려고."""
    if os.path.islink(path) or not os.path.isfile(path):
        return None, "not a regular file"
    try:
        if os.path.getsize(path) > MAX_BYTES:
            return None, "too large"
        return open(path, "rb").read().decode("utf-8"), None
    except UnicodeDecodeError:
        return None, "not UTF-8"
    except OSError:
        return None, "unreadable"


# ---------- 검사 ----------

def excerpt(text, ln, width=90):
    src = text.split("\n")
    s = src[ln - 1].strip() if 0 < ln <= len(src) else ""
    s = cc.INVISIBLE.sub(lambda m: f"<U+{ord(m.group(0)):04X}>", s)
    return s if len(s) <= width else s[:width - 3] + "..."


def detail(cat, text, ln, rows, cfg, pats, pub):
    if cat == "non-keyboard symbol":
        return cc.symbol_detail(text, [ln], cfg.get("allow_chars") or [])
    if cat == "invisible character":
        return cc.invisible_detail(text, [ln])
    if cat == "escaped character":
        return cc.escape_detail(text, [ln])
    if cat == "history marker" and rows is not None and rows[ln - 1]["c"]:
        body = " ".join(cc.comment_body(c) for c in rows[ln - 1]["c"])
        toks = list(dict.fromkeys(t for _, t in cc.scan(body, pats, pub)[0]))
        if toks:
            return ", ".join(toks[:6])
    return excerpt(text, ln)


def scan_text(text, rel, path, cfg, pats, pub):
    """[(줄 번호(1 기반), 범주)] 정렬 목록과 렉서 결과. 생성 파일이면 None."""
    kind = file_kind(rel)
    every = set(range(text.count("\n") + 1))
    if kind == "comment":
        if any(GEN_MARK.search(l) for l in text.split("\n", 6)[:6]):
            return None, None
        ext = os.path.splitext(rel)[1].lower()
        rows = lex(text, FAMILY[ext])
        probs = cc.check_lines(rows, every, pats, pub, cfg)
        labels = cc.step_labels(rows, text.split("\n"), cfg)
        exp = cc.expected_script(rows, set(), cfg, path, ext, labels)
        if exp:
            probs += [(ln, "language mismatch") for ln in cc.language_lines(rows, every, exp, labels)]
    else:
        rows = None
        probs = cc.doc_check(text, every, rel, cfg, pats, pub)
    probs += [(ln, "invisible character") for ln in cc.invisible_lines(text, every)]
    order = {c: i for i, c in enumerate(CATEGORIES)}
    return sorted(set(probs), key=lambda p: (p[0], order.get(p[1], 99))), rows


# ---------- 고치기 ----------

def _is_emoji(ch):
    return bool(ch) and any(a <= ord(ch) <= b for a, b in cc.EMOJI_RANGES)


def _sep(out, seg, i, mark, before):
    """앞뒤 공백을 모아 before + mark 로: 조각 맨 앞(앞이 공백뿐)이면 앞 공백을 그대로 두고 mark 만. 뒤에 글이 있으면 공백 하나. 다음 위치를 돌려준다."""
    stripped = "".join(out).rstrip(HSPACE)
    if stripped:
        out[:] = [stripped, before + mark]
    else:
        out.append(mark)
    j = i + 1
    while j < len(seg) and seg[j] in HSPACE:
        j += 1
    if j < len(seg):
        out.append(" ")
    return j


def fix_segment(seg, cats, allow, counts, file_start=False):
    """주석 조각이나 문서 본문 한 토막을 고친다. 판단이 필요한 글자는 그대로 둔다. counts 에 (글자, 대체) 수를 더한다."""
    literal = "".join(a for a in allow if a != "emoji")
    do_sym, do_inv = "non-keyboard symbol" in cats, "invisible character" in cats
    out, i, n = [], 0, len(seg)
    while i < n:
        ch = seg[i]
        prev, nxt = (seg[i - 1] if i else ""), (seg[i + 1] if i + 1 < n else "")
        if ord(ch) < 0x80 or ch in literal:
            out.append(ch)
            i += 1
            continue
        if cc.INVISIBLE.match(ch):
            keep = (not do_inv or (ch == "\ufeff" and file_start and i == 0)
                    or (ch == ZWJ and (_is_emoji(prev) or _is_emoji(nxt))))
            rep = ch if keep else (" " if ch == "\u00a0" else "")
            if not keep:
                counts[(ch, rep)] += 1
            out.append(rep)
            i += 1
            continue
        if not do_sym or not cc.odd_chars(ch, allow):
            out.append(ch)
            i += 1
            continue
        if prev and prev == nxt and prev in QUOTES:
            out.append(ch)  # 따옴표로 감싼 글자는 그 글자 자체를 가리킨다
            i += 1
            continue
        lead = not "".join(out).strip(HSPACE)
        if ch in DASHES:
            if ch in RANGE_DASHES and prev.isdigit() and nxt.isdigit():
                out.append("-")
                counts[(ch, "-")] += 1
                i += 1
            else:
                counts[(ch, " - ")] += 1
                i = _sep(out, seg, i, "-", " " if not lead else "")
            continue
        if ch == MIDDLE_DOT:
            # 주석의 가운뎃점은 거의 나열이다(버전 목록, 이름 묶음). "/" 는 곱 n*m 을 나눗셈으로 바꿀 수 있어 쓰지 않는다
            counts[(ch, "-" if lead else ", ")] += 1
            i = _sep(out, seg, i, "-", "") if lead else _sep(out, seg, i, ",", "")
            continue
        if ch == SECTION:
            counts[(ch, "")] += 1
            i += 1
            while i < n and seg[i] in HSPACE:
                i += 1
            continue
        name = unicodedata.name(ch, "")
        nk = unicodedata.normalize("NFKC", ch)
        if name.startswith(("CIRCLED DIGIT", "CIRCLED NUMBER")) and nk.isdigit():
            rep = nk + ")" + (" " if nxt and not nxt.isspace() and (nxt.isalnum() or nxt in "([\"'`") else "")
            counts[(ch, nk + ")")] += 1
            out.append(rep)
            i += 1
            continue
        if ch in PLAIN_FIX:
            rep = PLAIN_FIX[ch]
        elif any(a <= ord(ch) <= b for a, b in cc.FULLWIDTH_RANGES) and nk.isascii() and nk != ch:
            rep = nk
        else:
            out.append(ch)  # 이모지, 상자 그림, 표에 없는 기호: 판단이 필요하다
            i += 1
            continue
        counts[(ch, rep)] += 1
        out.append(rep)
        i += 1
    return "".join(out)


def plan_code_fix(text, fam, cats, allow, counts, skip=frozenset()):
    """코드 파일: 주석 조각 안만 고친 새 텍스트. 지시자 줄(--!strict, noqa 등)의 기호는 훅이 보지 않으므로 그대로 둔다."""
    lines = text.split("\n")
    for idx, row in enumerate(lex(text, fam)):
        if not row["s"] or idx in skip:
            continue
        line = lines[idx]
        line_cats = cats
        if any(cc.DIRECTIVE.match(c) for c in row["c"]):
            line_cats = tuple(c for c in cats if c != "non-keyboard symbol")
        for a, b in reversed(row["s"]):
            line = line[:a] + fix_unprotected(line[a:b], COMMENT_KEEP, line_cats, allow, counts, idx == 0 and a == 0) + line[b:]
        lines[idx] = line
    return "\n".join(lines)


def fix_unprotected(s, rxs, cats, allow, counts, file_start):
    """s 에서 rxs 가 잡는 구간(인라인 코드 등)은 그대로 두고 나머지 토막만 fix_segment 로 고친다."""
    out, pos = [], 0
    for a, b in protected(s, rxs) + [[len(s), len(s)]]:
        out.append(fix_segment(s[pos:a], cats, allow, counts, file_start and pos == 0))
        out.append(s[a:b])
        pos = b
    return "".join(out)


def protected(line, rxs=None):
    """고치지 않을 구간 목록(겹치면 합친다). 기본은 문서 본문 기준: 인라인 코드, URL, 경로 토큰."""
    spans = [m.span() for rx in (rxs or DOC_KEEP) for m in rx.finditer(line)]
    spans.sort()
    merged = []
    for a, b in spans:
        if merged and a <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    return merged


def plan_doc_fix(text, cats, allow, counts, skip=frozenset()):
    """모델용 문서: frontmatter, 코드 펜스 밖 줄에서 보호 구간을 뺀 곳만 고친다."""
    lines = text.split("\n")
    for idx, line in cc.doc_lines(text):
        if idx in skip:
            continue
        lines[idx] = fix_unprotected(line, DOC_KEEP, cats, allow, counts, idx == 0)
    return "\n".join(lines)


def code_projection(text, fam):
    """주석 밖 글자만 남긴 줄 목록. 주석 조각 자리는 \\0 하나로 둔다(조각 수까지 같아야 같다)."""
    lines, proj = text.split("\n"), []
    for line, row in zip(lines, lex(text, fam)):
        parts, pos = [], 0
        for a, b in row["s"]:
            parts += [line[pos:a], "\0"]
            pos = b
        parts.append(line[pos:])
        proj.append("".join(parts))
    return proj


def doc_projection(text):
    prose = dict(cc.doc_lines(text))
    out = []
    for idx, line in enumerate(text.split("\n")):
        out.append([line[a:b] for a, b in protected(line)] if idx in prose else line)
    return out


def guard_ok(old, new, kind, fam):
    if old.count("\n") != new.count("\n"):
        return False
    if kind == "comment":
        return code_projection(old, fam) == code_projection(new, fam)
    return doc_projection(old) == doc_projection(new)


def copy_lines(text, rel):
    """사본이라 고치지 않을 것: 파일 전체 사본이면 "file", 아니면 정본이 아닌 영역 사본의 줄 번호(0 기반) 집합.
    사본을 고치면 정본과 어긋나 sync-copies --check 가 깨지므로 정본을 고치고 sync-copies --apply 로 옮긴다."""
    try:
        tgt = copy_regions.file_copy_target(text)
        if tgt and os.path.normpath(tgt) != os.path.normpath(rel):
            return "file"
        regions, _ = copy_regions.parse_regions(text)
    except Exception:
        return set()
    return {i for r in regions if os.path.normpath(r["path"]) != os.path.normpath(rel) for i in range(r["start"], r["end"] + 1)}


def plan_fix(text, rel, cats, allow, skip=frozenset()):
    """(새 텍스트, 대체 수). 고칠 것이 없으면 새 텍스트가 원본과 같다."""
    counts = Counter()
    if file_kind(rel) == "comment":
        new = plan_code_fix(text, FAMILY[os.path.splitext(rel)[1].lower()], cats, allow, counts, skip)
    else:
        cats = tuple(c for c in cats if c in DOC_FIXABLE)
        new = plan_doc_fix(text, cats, allow, counts, skip) if cats else text
    return new, counts


def write_checked(path, old, new, kind, fam):
    """같은 폴더 임시 파일로 바꿔 쓰고 다시 읽어 가드를 한 번 더 본다. 어긋나면 원본 바이트로 되돌리고 False."""
    raw = old.encode("utf-8")
    mode = os.stat(path).st_mode & 0o7777
    tmp = path + ".conventions-fix.tmp"
    with open(tmp, "wb") as f:
        f.write(new.encode("utf-8"))
    os.chmod(tmp, mode)
    os.replace(tmp, path)
    try:
        back = open(path, "rb").read().decode("utf-8")
        ok = back == new and guard_ok(old, back, kind, fam)
    except (OSError, UnicodeDecodeError):
        ok = False
    if not ok:
        with open(path, "wb") as f:
            f.write(raw)
    return ok


def show_diff(rel, old, new):
    lines = list(difflib.unified_diff(old.splitlines(keepends=True), new.splitlines(keepends=True), f"a/{rel}", f"b/{rel}"))
    return "".join(cc.INVISIBLE.sub(lambda m: f"<U+{ord(m.group(0)):04X}>", l) + ("" if l.endswith("\n") else "\n") for l in lines)


# ---------- 읽기 모양 ----------

def layout_file(text, rel, limits):
    """(함수 지표 목록, 함수마다 걸린 범주 dict 목록). 지원하지 않는 확장자나 생성 파일이면 None."""
    ext = os.path.splitext(rel)[1].lower()
    lang = layout_metrics.LANG_BY_EXT.get(ext)
    if lang is None or any(GEN_MARK.search(l) for l in text.split("\n", 6)[:6]):
        return None
    rows = lex(text, FAMILY[ext], keep_code=True)
    lines = text.split("\n")
    measured = [layout_metrics.measure(rows, lines, fn, lang) for fn in layout_metrics.functions(rows, lines, lang)]
    return measured, [layout_metrics.findings(m, lang, limits) for m in measured]


def layout_line(rel, m, found):
    doc = m["doc"]
    if doc == "ok":
        doc = "ok, first line %d chars%s" % (m["doc_first_len"], "" if m["doc_sentence"] else ", sentence runs on")
    inter = ", ".join("L%d(%d)" % pair for pair in m["interleaved"]) or "0"
    return (f"{rel}:{m['start']}-{m['end']}: {m['name']}{' (public)' if m['public'] else ''}: {m['nonblank']} lines, "
            f"{m['blank']} blank, {m['paragraphs']} paragraphs, longest run {m['max_run']}, labels {m['labels']}, "
            f"interleaved {inter}, multi-decl {m['multi_decl']}, one-letter {m['one_letter']}, doc {doc}"
            + (f"  [{', '.join(found)}]" if found else ""))


def run_layout(args, out=sys.stdout):
    """layout 하위 명령. 종료 코드 0 = 걸린 함수 없음, 1 = 있음."""
    start = os.path.abspath(args.paths[0]) if args.paths else os.getcwd()
    root = os.path.abspath(args.root) if args.root else repo_root(start if os.path.isdir(start) else os.path.dirname(start))
    cfg = cc.load_cfg(root)
    limits = layout_metrics.limits(cfg.get("layout"))

    files = []
    for rel in list_files(root, args.paths):
        if os.path.splitext(rel)[1].lower() not in layout_metrics.LANG_BY_EXT or cc.excluded(os.path.join(root, rel), rel, cfg):
            continue
        text, _ = read_text(os.path.join(root, rel))
        got = layout_file(text, rel, limits) if text is not None else None
        if got:
            files.append((rel, got[0], got[1]))

    # Summary over every measured function
    fns = [(rel, m, f) for rel, ms, fs in files for m, f in zip(ms, fs)]
    long_fns = [m for _, m, _ in fns if m["nonblank"] >= limits["min_lines"]]
    public = [m for _, m, _ in fns if m["public"] and not m["metamethod"]]
    body = sum(m["nonblank"] for _, m, _ in fns)
    cats = Counter(c for _, _, f in fns for c in f)
    summary = {
        "root": root, "files": len(files), "functions": len(fns), "limits": limits,
        "long_functions": len(long_fns), "long_one_block": cats["layout"],
        "interleaved_per_100_lines": round(100 * sum(len(m["interleaved"]) for _, m, _ in fns) / body, 2) if body else 0,
        "public_with_doc": sum(1 for m in public if m["doc"] == "ok"), "public": len(public),
        "multi_decl": sum(m["multi_decl"] for _, m, _ in fns), "by_category": {c: cats[c] for c in layout_metrics.CATEGORIES if cats[c]},
    }
    status = 1 if cats else 0
    if args.json:
        json.dump({"functions": [dict(m, path=rel, findings=f) for rel, m, f in fns], "summary": summary}, out, ensure_ascii=False, indent=1)
        out.write("\n")
        return status

    w = out.write
    if not args.summary:
        for rel, m, f in fns:
            w(layout_line(rel, m, f) + "\n")
    w(f"\nroot: {root}\nfiles: {len(files)}, functions: {len(fns)}\n")
    w(f"functions with {limits['min_lines']}+ lines: {len(long_fns)}, read as one block: {cats['layout']}\n")
    w(f"interleaved multi-line comments per 100 body lines: {summary['interleaved_per_100_lines']}\n")
    w(f"public functions with a doc comment callers can see: {summary['public_with_doc']}/{len(public)}\n")
    w(f"multi-name declarations: {summary['multi_decl']}\n")
    w("findings: " + (", ".join(f"{c} {n}" for c, n in summary["by_category"].items()) or "none") + "\n")
    return status


# ---------- 실행 ----------

def run(args, out=sys.stdout):
    start = os.path.abspath(args.paths[0]) if args.paths else os.getcwd()
    root = os.path.abspath(args.root) if args.root else repo_root(start if os.path.isdir(start) else os.path.dirname(start))
    cfg = cc.load_cfg(root)
    pats, pub = cc.compile_patterns(cfg)
    allow = cfg.get("allow_chars") or []
    selected = [ALIASES.get(c, c) for c in (args.category or [])]
    bad = [c for c in selected if c not in CATEGORIES]
    if bad:
        print(f"unknown category: {', '.join(bad)} (use one of: {', '.join(CATEGORIES)} or {', '.join(ALIASES)})", file=sys.stderr)
        return 2
    selected = selected or list(CATEGORIES)
    fix_cats = tuple(c for c in FIXABLE if c in selected)
    fixing = args.fix

    findings, remaining, skipped = [], [], Counter()
    replaced, changed, rejected, copies, scanned = Counter(), [], [], [], 0
    diffs = []
    for rel in list_files(root, args.paths):
        kind = file_kind(rel)
        path = os.path.join(root, rel)
        if not kind:
            continue
        if cc.excluded(path, rel, cfg):
            skipped["excluded"] += 1
            continue
        text, why = read_text(path)
        if text is None:
            skipped[why] += 1
            continue
        probs, rows = scan_text(text, rel, path, cfg, pats, pub)
        if probs is None:
            skipped["generated"] += 1
            continue
        scanned += 1
        probs = [p for p in probs if p[1] in selected]
        mine = [{"path": rel, "line": ln, "category": cat, "detail": detail(cat, text, ln, rows, cfg, pats, pub)} for ln, cat in probs]
        findings += mine
        left = mine
        skip = copy_lines(text, rel) if fix_cats and any(p[1] in fix_cats for p in probs) else set()
        if skip == "file" or any(ln - 1 in skip for ln, cat in probs if cat in fix_cats):
            copies.append(rel)
        if fix_cats and skip != "file" and any(p[1] in fix_cats for p in probs):
            new, counts = plan_fix(text, rel, fix_cats, allow, skip)
            fam = FAMILY.get(os.path.splitext(rel)[1].lower())
            if new != text:
                if not guard_ok(text, new, kind, fam):
                    rejected.append(rel)
                else:
                    after, rows2 = scan_text(new, rel, path, cfg, pats, pub)
                    after_set = {p for p in (after or []) if p[1] in selected}
                    left = [f for f in mine if (f["line"], f["category"]) in after_set]
                    applied = True
                    if fixing and not args.dry_run:
                        applied = write_checked(path, text, new, kind, fam)
                        if not applied:
                            rejected.append(rel)
                            left = mine
                    if applied:
                        changed.append({"path": rel, "fixed": len(mine) - len(left), "replacements": sum(counts.values())})
                        replaced.update(counts)
                        if fixing and args.dry_run:
                            diffs.append({"path": rel, "diff": show_diff(rel, text, new)})
        remaining += left

    def label(k):
        ch, rep = k
        return f"U+{ord(ch):04X} {unicodedata.name(ch, '?')} -> {json.dumps(rep)}"

    by_cat = Counter(f["category"] for f in findings)
    by_file = Counter(f["path"] for f in findings)
    left_cat = Counter(f["category"] for f in remaining)
    summary = {
        "root": root, "files_scanned": scanned, "skipped": dict(skipped),
        "by_category": {c: by_cat[c] for c in CATEGORIES if by_cat[c]},
        "by_file": dict(by_file.most_common()),
        "fix": {
            "mode": ("apply" if fixing and not args.dry_run else "dry-run" if fixing else "estimate"),
            "categories": list(fix_cats),
            "files": changed, "findings_fixed": len(findings) - len(remaining),
            "replacements": {label(k): v for k, v in replaced.most_common()},
            "guard": {"files_checked": len(changed) + len(rejected), "rejected": rejected},
            "copies_left": copies,
            "needs_judgment_by_category": {c: left_cat[c] for c in CATEGORIES if left_cat[c]},
        },
    }
    status = 1 if (remaining if fixing else findings) else 0  # scan: 찾은 것, fix: 고친 뒤 남은 것
    if args.json:
        json.dump({"findings": findings, "needs_judgment": remaining, "diffs": diffs, "summary": summary},
                  out, ensure_ascii=False, indent=1)
        out.write("\n")
        return status

    w = out.write
    if fixing and args.dry_run and diffs:
        if any("<U+" in d["diff"] for d in diffs):
            w("# invisible characters are shown as <U+XXXX> in this diff\n")
        for d in diffs:
            w(d["diff"])
    if not args.summary:
        if fixing:
            w("needs judgment:\n" if remaining else "")
        for f in (remaining if fixing else findings):
            w(f"{f['path']}:{f['line']}: {f['category']}: {f['detail']}\n")
    w(f"\nroot: {root}\nfiles scanned: {scanned}" + (f" (skipped: {', '.join(f'{k} {v}' for k, v in sorted(skipped.items()))})" if skipped else "") + "\n")
    w(f"findings: {len(findings)}" + "".join(f"\n  {c}: {n}" for c, n in summary["by_category"].items()) + "\n")
    if by_file:
        top = by_file.most_common(args.top)
        w(f"files with findings: {len(by_file)} (top {len(top)})\n" + "".join(f"  {n:5d} {p}\n" for p, n in top))
    fx = summary["fix"]
    verb = {"apply": "fixed", "dry-run": "would fix", "estimate": "fixable by --fix"}[fx["mode"]]
    if fix_cats:
        w(f"{verb}: {fx['findings_fixed']} findings in {len(changed)} files, {sum(replaced.values())} character replacements\n")
        for k, v in summary["fix"]["replacements"].items():
            w(f"  {v:5d} {k}\n")
        if fixing or rejected:
            w(f"token guard: {fx['guard']['files_checked']} files checked, {len(rejected)} rejected"
              + (" (left unchanged: " + ", ".join(rejected) + ")" if rejected else "") + "\n")
        if copies:
            w(f"copies left unfixed: {', '.join(copies)} (fix the canon, then python3 -I tools/sync-copies.py --apply)\n")
        w(f"needs judgment: {len(remaining)}" + "".join(f"\n  {c}: {n}" for c, n in fx["needs_judgment_by_category"].items()) + "\n")
    return status


def parse(argv):
    ap = argparse.ArgumentParser(prog="conventions-scan.py", description="Whole-file qwreey-conventions scan and mechanical fixer (no model calls).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    lay = sub.add_parser("layout", help="per-function layout numbers and the readable-code notice categories (no fixes)")
    lay.add_argument("paths", nargs="*", help="files or folders (default: repo root)")
    lay.add_argument("--root", help="repo root (default: git toplevel of the first path or cwd)")
    lay.add_argument("--json", action="store_true", help="machine-readable output")
    lay.add_argument("--summary", action="store_true", help="print only the summary")
    for name, hlp in (("scan", "report findings on every line of the files"), ("fix", "same as scan --fix")):
        p = sub.add_parser(name, help=hlp)
        p.add_argument("paths", nargs="*", help="files or folders (default: repo root)")
        p.add_argument("--root", help="repo root (default: git toplevel of the first path or cwd)")
        p.add_argument("--json", action="store_true", help="machine-readable output")
        p.add_argument("--category", action="append", metavar="C",
                       help="limit to a category (repeatable): " + ", ".join(ALIASES) + " or the full name")
        p.add_argument("--summary", action="store_true", help="print only the summary")
        p.add_argument("--top", type=int, default=20, help="files listed in the summary (default 20)")
        p.add_argument("--dry-run", action="store_true", help="with fix: print a unified diff, write nothing")
        if name == "scan":
            p.add_argument("--fix", action="store_true", help="replace unambiguous symbols and invisible characters in comments and doc prose")
    a = ap.parse_args(argv)
    if a.cmd == "layout":
        return a
    a.fix = a.cmd == "fix" or getattr(a, "fix", False)
    if a.dry_run and not a.fix:
        ap.error("--dry-run needs --fix")
    return a


if __name__ == "__main__":
    ARGS = parse(sys.argv[1:])
    sys.exit(run_layout(ARGS) if ARGS.cmd == "layout" else run(ARGS))
