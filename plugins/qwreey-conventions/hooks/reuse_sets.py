"""reuse-check 의 추출부: 파일에서 문자열 묶음(정의, 인라인, 타입 합집합)과 @copy-of, @dup-ok 표시를 뽑는다. 표준 라이브러리만 쓴다.

묶음 = 따옴표 문자열 3개 이상의 리터럴 목록이나 `"a" | "b"` 합집합. 원소는 글자가 있는 낱말만(구두점·연산자 묶음 제외).
렉서(conv_lex)는 묶음 후보가 있을 때만 돌려 주석 줄의 묶음을 거른다.
"""
import bisect
import re

from conv_lex import lex

STR = r'"[^"\\\n]*"|\'[^\'\\\n]*\''
GROUP = re.compile(r"[\[\{\(]((?:\s*(?:" + STR + r")\s*[,;]?)+)\s*[\]\}\)]|((?:(?:" + STR + r")\s*(?:\||\bor\b)\s*)+(?:" + STR + r"))", re.S)
WORD = re.compile(r"^(?=.*[A-Za-z])[\w.\-/ ]{2,}$")
# 정의 머리: 이름 붙은 바인딩과 const/static/let/local/type. 정의가 아닌 쪽끼리(if x in (...) 두 번)는 짝으로 보지 않는다
DEF = re.compile(r"^\s*(?:pub(?:\([\w:]+\))?\s+)?(?:export\s+)?(?:const|static|let|local|type)\s+\w+"
                 r"|^\s*[A-Za-z_]\w*\s*(?::[^=]+)?=\s*(?:table\.freeze\(|frozenset\(|set\()?[\[\{\(]|^\s*[A-Za-z_]\w*\s*:\s*&?\[")
NAME = re.compile(r"^\s*(?:pub(?:\([\w:]+\))?\s+)?(?:export\s+)?(?:(?:const|static|let|local|type)\s+(?:mut\s+)?)?([A-Za-z_]\w*)")
TYPE = re.compile(r"^\s*(?:export\s+)?type\s+\w+|^\s*\w+\s*:\s*[\"']")
COPY = re.compile(r"@copy-of:\s*(\S+)")
DUP = re.compile(r"(?:--|//|#|/\*|\{/\*)\s*@dup-ok\b:?[ \t]*([^\n]*)")
HEADER_LINES = 10
BAD_REASONS = {"", "-", "later", "todo", "fixme", "tbd", "n/a", "나중에", "추후"}
CONT = (",", "(", "{", "[", "=", "|")
FLAG_DEF, FLAG_TYPE = 1, 2


def reason_ok(text):
    t = (text or "").strip().rstrip("*/} ").strip()
    return t.lower() not in BAD_REASONS and len(t) >= 6


def _is_def(lines, ln):
    """묶음이 시작하는 줄(1 기반)이나 그 위 3줄 안의 정의 머리 줄 번호(0 기반), 없으면 None. 여러 줄 리터럴과 `| "a"` 줄을 따라 올라간다."""
    for k in range(ln - 1, max(-1, ln - 5), -1):
        if k < ln - 1 and not (lines[k].rstrip().endswith(CONT) or lines[k + 1].lstrip().startswith("|")):
            return None
        if DEF.match(lines[k]):
            return k
    return None


def extract(text, fam):
    """(묶음 목록, 표시 목록). 묶음: [줄(1 기반), 이름, 플래그(1 정의, 2 타입), 원소(정렬), 표시 대상 또는 None, @dup-ok 사유 또는 None].
    표시: [줄, 대상 경로, 이름 또는 None, "f"(파일 사본) | "v"(값 사본)]."""
    if fam == "rust" and "#[cfg(test)]" in text:
        text = text[:text.find("#[cfg(test)]")]
    lines = text.split("\n")
    cands = []
    starts = None
    for m in GROUP.finditer(text):
        els = frozenset(x[1:-1] for x in re.findall(STR, m.group(0)) if len(x) > 2)
        if len(els) < 3:
            continue
        if starts is None:
            starts = [0]
            for mm in re.finditer("\n", text):
                starts.append(mm.end())
        cands.append((bisect.bisect_right(starts, m.start()), els))
    has_mark = "@copy-of" in text
    rows = lex(text, fam) if (cands or has_mark) else None
    sets = []
    for ln, els in cands:
        if not rows[ln - 1]["code"] and rows[ln - 1]["c"]:
            continue  # 주석 줄
        words = sorted(x for x in els if WORD.match(x))
        if len(words) < 3 or (any(x.startswith("-") for x in words) and len(words) <= 8):
            continue  # 낱말 3개 미만, argv 목록
        dk = _is_def(lines, ln)
        flags = (FLAG_DEF if dk is not None else 0) | (FLAG_TYPE if TYPE.match(lines[ln - 1] if dk is None else lines[dk]) else 0)
        m = NAME.match(lines[dk]) if dk is not None else None
        dup = None
        for k in range(max(0, ln - 4), ln):
            d = DUP.search(lines[k])
            if d:
                dup = d.group(1).strip()
        sets.append([ln, m.group(1) if m else "", flags, words, None, dup])
    marks = []
    if has_mark:
        for i, s in enumerate(lines):
            m = COPY.search(s)
            if not m or not (i < HEADER_LINES or rows[i]["c"]):
                continue
            tgt = m.group(1).rstrip(".,;)*/}")
            name = None
            if "#" in tgt:
                tgt, name = tgt.split("#", 1)
            if name is None and i < HEADER_LINES:
                marks.append([i + 1, tgt, None, "f"])
                continue
            for st in sets:  # 이 표시 바로 아래 6줄 안의 첫 묶음이 사본
                if i + 1 < st[0] <= i + 7:
                    st[4] = tgt + "#" + (name or st[1])
                    marks.append([i + 1, tgt, name or st[1], "v"])
                    break
            else:
                marks.append([i + 1, tgt, name, "v"] if name else [i + 1, tgt, None, "f"])
    return sets, marks
