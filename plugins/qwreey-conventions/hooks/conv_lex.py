"""conventions-check 와 reuse-check 가 함께 쓰는 간이 렉서: 확장자별 계열, 줄마다 주석 조각과 코드 유무. 표준 라이브러리만 쓴다."""
import re

# 확장자 -> 렉서 계열
FAMILY = {".luau": "lua", ".lua": "lua", ".ts": "c", ".tsx": "c", ".js": "c", ".jsx": "c", ".mjs": "c", ".rs": "rust", ".go": "c", ".kt": "c",
          ".astro": "astro", ".py": "py", ".sh": "py", ".html": "html", ".htm": "html"}


def lex(text, fam, keep_code=False):
    """줄마다 {"c": [주석 조각 문자열...], "s": [조각의 (시작, 끝) 열 위치...], "code": 코드나 문자열이 있는가} 를 돌려준다.
    주석은 줄 전체나 일부일 수 있다. 조각은 여닫는 표식을 뺀 본문이고, s 는 고치는 도구(scripts/conventions-scan.py)가 주석 안만 바꾸려고 쓴다.
    keep_code 면 줄마다 "k"(주석을 지우고 문자열을 `""` 하나로 줄인 코드 글)와 "in"(여러 줄 주석이나 문자열 안에서 시작하는 줄인가)도 넣는다.
    함수 범위를 키워드와 괄호로 찾는 hooks/layout_metrics.py 가 쓴다."""
    lines = text.split("\n")
    out = []
    state = None  # None | ("block", close) | ("str", close)
    for s in lines:
        row = {"c": [], "s": [], "code": False}
        code = [] if keep_code else None
        if keep_code:
            row["in"] = state is not None
        pos, n = 0, len(s)

        while pos < n:
            # Inside a block comment
            if state and state[0] == "block":
                j = s.find(state[1], pos)
                if j < 0:
                    row["c"].append(s[pos:])
                    row["s"].append((pos, n))
                    pos = n
                else:
                    row["c"].append(s[pos:j])
                    row["s"].append((pos, j))
                    pos = j + len(state[1])
                    state = None
                continue

            # Inside a multi-line string
            if state and state[0] == "str":
                row["code"] = True
                j = find_close(s, pos, state[1])
                if j < 0:
                    pos = n
                else:
                    pos = j + len(state[1])
                    state = None
                continue

            # Whitespace and plain code
            ch = s[pos]
            r = None if ch in " \t\r" else open_comment_or_string(s, pos, fam)
            if r is None:
                row["code"] = row["code"] or ch not in " \t\r"
                if code is not None:
                    code.append(" " if ch in " \t\r" else ch)
                pos += 1
                continue

            # A comment or string opens here
            kind, a, b = r  # kind: line|block|str|strline, a: 닫는 표식(또는 None), b: 여는 표식 길이
            if code is not None and kind in ("str", "strline"):
                code.append('""')

            # What it opened decides the rest of the line
            if kind == "line":
                row["c"].append(s[pos + b:])
                row["s"].append((pos + b, n))
                pos = n
            elif kind == "block":
                state = ("block", a)
                pos += b
            elif kind == "str":  # 여러 줄 문자열
                row["code"] = True
                state = ("str", a)
                pos += b
            else:  # 한 줄 문자열: 같은 줄 안에서 닫힌다(안 닫히면 줄 끝까지)
                row["code"] = True
                j = pos + b
                while j < n and s[j] != a:
                    j += 2 if s[j] == "\\" else 1
                pos = min(j + 1, n)

        if code is not None:
            row["k"] = "".join(code)
        out.append(row)
    return out


def find_close(s, pos, close):
    j = pos
    while True:
        k = s.find(close, j)
        if k < 0:
            return -1
        if close in ("`", '"""', "'''") and k > 0 and s[k - 1] == "\\":
            j = k + 1
            continue
        return k


def open_comment_or_string(s, pos, fam):
    """pos 에서 주석, 문자열이 시작하면 (kind, 닫는 표식, 여는 표식 길이). 아니면 None."""
    ch = s[pos]
    if fam == "lua":
        if s.startswith("--", pos):
            m = re.match(r"--\[(=*)\[", s[pos:])
            if m:
                return ("block", "]" + m.group(1) + "]", m.end())
            return ("line", None, 2)
        m = re.match(r"\[(=*)\[", s[pos:])
        if m:
            return ("str", "]" + m.group(1) + "]", m.end())
        if ch in "\"'":
            return ("strline", ch, 1)
        if ch == "`":
            return ("str", "`", 1)
        return None
    if fam == "py":
        if ch == "#":
            return ("line", None, 1)
        for q in ('"""', "'''"):
            if s.startswith(q, pos):
                return ("str", q, 3)
        if ch in "\"'":
            return ("strline", ch, 1)
        return None
    if fam == "html":
        if s.startswith("<!--", pos):
            return ("block", "-->", 4)
        return None  # 마크업의 아포스트로피가 문자열 상태를 오염시키지 않게 문자열은 보지 않는다
    # c 계열(c, rust, astro)
    if fam == "astro" and s.startswith("<!--", pos):
        return ("block", "-->", 4)
    if s.startswith("//", pos):
        return ("line", None, 2)
    if s.startswith("/*", pos):
        return ("block", "*/", 2)
    if ch == '"':
        return ("strline", ch, 1)
    if ch == "'":
        if fam == "rust":  # 수명 'a 와 문자 리터럴 'x' 구분: 문자 리터럴 꼴만 문자열로 본다
            m = re.match(r"'(?:\\.[^']{0,8}|[^'\\])'", s[pos:])
            return ("strline", ch, 1) if m else None
        if fam == "astro":  # 마크업 속 "don't" 를 문자열로 오인하지 않게 짝이 같은 줄에 있을 때만
            return ("strline", ch, 1) if s.find("'", pos + 1) > 0 else None
        return ("strline", ch, 1)
    if ch == "`" and fam != "rust":
        return ("str", "`", 1)
    return None


def comment_body(seg):
    """주석 조각에서 표식 장식을 걷어 낸 본문."""
    return re.sub(r"^[\s\-/#*!]+", "", seg).rstrip(" \t*/-")
