"""함수 범위와 읽기 모양 지표(문단, 이어진 줄, 끼운 주석 덩어리, 문서 주석)를 언어별로 잰다. 표준 라이브러리만 쓴다.

conventions-check.py 의 layout 알림과 scripts/conventions-scan.py 의 `layout` 하위 명령이 같이 쓴다.
입력은 conv_lex.lex(text, fam, keep_code=True) 의 줄 목록이다("k" 는 주석을 지우고 문자열을 `""` 로 줄인 코드).

함수 찾기(가장 바깥 함수만; 안쪽 콜백과 지역 함수는 바깥 함수 본문에 든다):
  - Lua 계열: `function`/`do`/`then`/`repeat` 와 `end`/`until` 의 짝. Luau 의 `if` 식(`= if a then b else c`)은 `end` 가 없어 쌓지 않는다.
  - Python: `def` 줄과 들여쓰기. 클래스는 함수가 아니라서 메서드가 따로 잡힌다.
  - C 계열(ts, js, rs, go, kt): 함수 머리(`function`, `fn`, `func`, `fun`, `=> {`, ts 메서드 꼴) 뒤 첫 `{` 와 그 짝 `}`.
본문은 머리와 닫는 줄 사이, 문단은 빈 줄로 나뉜 덩어리, 끼운 주석은 바로 위와 아래가 코드인 2줄 이상 주석 덩어리다.
"""
import re

LANG_BY_EXT = {".luau": "lua", ".lua": "lua", ".py": "py", ".ts": "ts", ".tsx": "ts", ".js": "ts", ".jsx": "ts", ".mjs": "ts",
               ".rs": "rust", ".go": "go", ".kt": "kt"}

# 편집기 호버와 자동완성이 보여 주는 문서 주석의 꼴. 알림 문구가 언어마다 이 말을 쓴다
DOC_FORM = {
    "lua": "a `---` doc comment (luau-lsp shows only `---` and `--[=[ ]=]` on hover and completion, never `--`)",
    "py": "a docstring (`#` comments above the def are not shown on hover)",
    "ts": "a `/** */` JSDoc comment (`//` is not shown on hover)",
    "rust": "a `///` doc comment (`//` is not shown on hover)",
    "go": "a `//` doc comment directly above the func, starting with its name",
    "kt": "a `/** */` KDoc comment (`//` is not shown on hover)",
}
# 시험 함수가 따를 문서 꼴. 시험은 호버로 부르지 않으니, 보는 것은 무엇을 확인하는지 적은 한 줄이다
TEST_FORM = {"rust": "a one-line `///` doc comment"}
# 문서 없는 시험의 설명. notice 가 TEST_MARK 로 시험을 가려 시험용 문장을 붙인다(함수 이름에는 빈칸이 없다)
TEST_NO_DOC = "is a test with no doc comment"
TEST_HIDDEN_DOC = "is a test whose comment is not a doc comment"
TEST_MARK = " is a test "
DOC_OPEN = {"lua": re.compile(r"^\s*(?:---|--\[=+\[)"), "ts": re.compile(r"^\s*/\*\*"), "kt": re.compile(r"^\s*/\*\*"),
            "rust": re.compile(r"^\s*(?:///|/\*\*)"), "go": re.compile(r"^\s*//")}
# 편집기 접기 표지(`--#region`, `// #endregion`)는 문서도 이유도 아니라 건너뛴다
REGION = re.compile(r"^\s*(?:--|//)\s*#\s*(?:end)?region\b")
DOC_MARK = re.compile(r"^\s*(?:--\[=*\[|-{2,}|/\*\*?|\*/|\*|/{2,}|#)\s?")
DOC_TAG = re.compile(r"^(?:@|\*|-\s|\|)")
# 첫 문장이 끝난 줄: 문장 부호나 한국어 종결 어미로 끝난다
SENTENCE_END = re.compile(r"(?:[.?!:]|[다요음함됨임])[\"')\]`]*$")

LUA_TOKEN = re.compile(r"[A-Za-z_]\w*|\.\.\.?=?|[=~<>]=|//=?|[-+*/%^]=|->|::|\S")
LUA_OPENERS = {"function": "function", "if": "if", "repeat": "repeat", "do": "do"}
# 이 토큰 뒤의 `if` 는 식이라 `end` 가 없다
LUA_EXPR_BEFORE = frozenset({"=", "(", ",", "{", "[", "return", "and", "or", "not", "elseif", "if", "while", "until", "in",
                             "..", "==", "~=", "<=", ">=",
                             "+", "-", "*", "/", "//", "%", "^", "#", "+=", "-=", "*=", "/=", "//=", "%=", "^=", "..="})
# `<`, `>` 는 줄 끝에서 제네릭 타입이나 캐스트(`): Optional<T>`)를 닫는 일이 많아, 같은 줄의 `if` 앞에서만 식으로 본다
LUA_EXPR_BEFORE_SAME_LINE = frozenset({"<", ">"})
LUA_NAME = re.compile(r"function\s+([\w.:]+)\s*[(<]|([\w.:\[\]\"]+)\s*=\s*function\b")
LUA_PUBLIC = re.compile(r"^\s*function\s+[A-Za-z_]\w*(?:\.\w+)*[.:]\w+|^\s*[A-Za-z_]\w*(?:\.\w+)+\s*=\s*function\b")
METAMETHOD = re.compile(r"(?:^|[.:])__\w+$")

C_TOKEN = re.compile(r"[A-Za-z_$][\w$]*|=>|->|::|\S")
C_FN_KEYWORD = {"ts": "function", "rust": "fn", "go": "func", "kt": "fun"}
C_CONTROL = frozenset({"if", "for", "while", "switch", "catch", "with", "return", "match", "loop", "else", "do", "try", "when",
                       "typeof", "sizeof", "new", "await", "yield", "throw", "case", "super", "this", "function"})
C_METHOD = re.compile(r"^\s*(?:(?:public|private|protected|static|async|override|readonly|abstract|export|default|get|set)\s+)*"
                      r"\*?\s*([A-Za-z_$#][\w$]*)\s*(?:<[^>]*>)?\s*\(")
C_NAMES = (re.compile(r"\bfunction\s*\*?\s*([\w$]+)"), re.compile(r"\bfn\s+(\w+)"), re.compile(r"\bfunc\s*(?:\([^)]*\)\s*)?(\w+)"),
           re.compile(r"\bfun\s+(?:<[^>]*>\s*)?(?:[\w.]+\.)?(\w+)"), re.compile(r"\b(?:const|let|var)\s+([\w$]+)\s*(?::[^=]*)?="),
           re.compile(r"([\w$]+)\s*[:=]\s*(?:async\s*)?(?:function|\()"))
C_CONTINUES = ("{", "where", "->", ":", ")")
KT_PRIVATE = re.compile(r"\b(?:private|protected|internal)\b")
# 함수 머리 위의 속성이나 데코레이터 줄(`#[...]`, `@x`). 문서 주석은 그 위에 있어도 된다
ATTRIBUTE = re.compile(r"^\s*(?:#\[|@)")
# Rust 시험 속성: `#[test]`, `#[tokio::test]`, `#[tokio::test(flavor = "...")]`. `#[cfg(test)]` 는 시험이 아니다
RUST_TEST = re.compile(r"#\[\s*(?:[A-Za-z_]\w*\s*::\s*)*test\s*[\](]")

PY_DEF = re.compile(r"^\s*(?:async\s+)?def\s+(\w+)")
PY_CLASS = re.compile(r"^\s*class\s+(\w+)")
PY_MAIN = re.compile(r"^if\s+__name__\s*==")
PY_HEADER_SCAN = 50  # def 머리를 찾아 내려가는 줄 수. 닫히지 않은 괄호가 파일 끝까지 훑지 않게 막는다

# 한 선언에 이름 여럿: 오른쪽에 최상위 쉼표가 있을 때만 센다(`local ok, err = pcall(f)` 처럼 여러 반환을 받는 것은 뺀다)
LUA_MULTI = re.compile(r"^\s*local\s+[A-Za-z_]\w*(?:\s*:[^,=]+)?\s*,")
TS_MULTI = re.compile(r"^\s*(?:let|const|var)\s+[A-Za-z_$][\w$]*\s*(?::[^=,]+)?(?:=|,)")
TS_DESTRUCTURE = re.compile(r"^\s*(?:let|const|var)\s*[\[{]")
ONE_LETTER = {"lua": re.compile(r"^\s*local\s+([A-Za-z])\s*(?:[:=,]|$)"), "ts": re.compile(r"^\s*(?:let|const|var)\s+([A-Za-z])\s*[:=]")}
LABEL_WORD = re.compile(r"[A-Za-z\u00c0-\u024f\uac00-\ud7a3]+")
# 단계 라벨의 낱말 수(rules/readable-code.md 와 같은 2-10). 한 낱말은 라벨이 아니라 이름표나 메모로 본다
LABEL_WORDS_MIN, LABEL_WORDS_MAX = 2, 10

# 알림 기준. 사용자 손 코드(본문 15줄 이상)는 3/26, 에이전트 코드는 68/75 가 걸리는 선이다. 문서 첫 줄 100자는 지침(80자)보다
# 느슨하게 두어 잡음을 줄인다. grow 는 기존 함수를 키운 편집, mostly 는 함수를 거의 새로 쓴 편집의 기준이다.
# 저장소 conventions.json 의 "layout" 이 덮는다
DEFAULT_LAYOUT = {"min_lines": 15, "max_run": 20, "doc_first_max": 100, "grow": 15, "mostly": 0.5}
CATEGORIES = ("layout", "interleaved comment", "doc summary")
LIST_MAX = 8  # 알림에서 범주당 이름을 대는 함수 수. 나머지는 수만 센다


# ---------- 함수 찾기 ----------

def functions(rows, lines, lang):
    """가장 바깥 함수 목록: [{name, start, header_end, end, last, public, metamethod, test}], 줄은 0 기반.

    본문은 header_end+1 부터 end-1 까지, last 는 함수의 마지막 줄이다. lang 은 LANG_BY_EXT 의 값이다.
    """
    if lang == "lua":
        return _lua_functions(rows)
    if lang == "py":
        return _py_functions(rows, lines)
    return _c_functions(rows, lang)


def lua_blocks(rows):
    """블록을 여닫는 토큰마다 (줄, 토큰, "open" | "close"). 반복문 머리의 `do` 와 `if` 식은 뺀다."""
    pending_do = 0
    prev = ""
    prev_ln = -1

    for ln, row in enumerate(rows):
        for tok in LUA_TOKEN.findall(row["k"]):
            if tok in ("while", "for"):
                yield ln, tok, "open"
                pending_do += 1
            elif tok == "do" and pending_do:
                pending_do -= 1  # 반복문 머리의 `do` 는 새 블록을 열지 않는다
            elif tok in LUA_OPENERS and not (tok == "if" and _lua_if_expr(prev, prev_ln == ln)):
                yield ln, tok, "open"
            elif tok in ("end", "until"):
                yield ln, tok, "close"
            prev, prev_ln = tok, ln


def _lua_if_expr(prev, same_line):
    return prev in LUA_EXPR_BEFORE or same_line and prev in LUA_EXPR_BEFORE_SAME_LINE


def _lua_spans(rows):
    """가장 바깥 함수의 (머리 줄, `end` 줄) 목록."""
    stack = []
    spans = []
    for ln, tok, act in lua_blocks(rows):
        if act == "open":
            stack.append(("function" if tok == "function" else "block", ln))
        elif stack:
            kind, start = stack.pop()
            if kind == "function" and not any(k == "function" for k, _ in stack):
                spans.append((start, ln))
    return spans


def _lua_functions(rows):
    out = []
    for start, end in _lua_spans(rows):
        head = rows[start]["k"]
        m = LUA_NAME.search(head)
        name = (m.group(1) or m.group(2)) if m else "(anonymous)"
        out.append({"name": name, "start": start, "header_end": _params_end(rows, start, end), "end": end, "last": end,
                    "public": bool(LUA_PUBLIC.match(head)), "metamethod": bool(METAMETHOD.search(name)), "test": False})
    return out


def _params_end(rows, start, end):
    """머리 줄부터 매개변수 괄호가 닫히는 줄. 못 찾으면 머리 줄."""
    depth = 0
    for ln in range(start, end + 1):
        for ch in rows[ln]["k"]:
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    return ln
    return start


def _indent(line):
    text = line.expandtabs()
    return len(text) - len(text.lstrip())


def _py_functions(rows, lines):
    out = []
    ln = 0
    while ln < len(rows):
        m = None if rows[ln].get("in") else PY_DEF.match(rows[ln]["k"])
        if not m:
            ln += 1
            continue

        indent = _indent(lines[ln])
        head_end = _py_header_end(rows, ln)
        last = _py_body_end(rows, lines, head_end, indent)
        name = m.group(1)
        out.append({"name": name, "start": ln, "header_end": head_end, "end": last + 1, "last": last, "public": not name.startswith("_"),
                    "metamethod": name.startswith("__") and name.endswith("__"), "test": False, "indent": indent})
        ln = last + 1

    _py_public_scope(out, rows, lines)
    return out


def _py_header_end(rows, start):
    """`def` 머리가 끝나는 줄: 매개변수 괄호가 닫힌 뒤 괄호 깊이 0 의 첫 콜론이 있는 줄.

    한 줄 함수(`def f(): return 1`)는 머리 줄이 곧 끝이다. PY_HEADER_SCAN 줄 안에 없으면 머리 줄로 본다.
    """
    depth = 0
    opened = False
    for k in range(start, min(len(rows), start + PY_HEADER_SCAN)):
        for ch in rows[k]["k"]:
            if ch in "([{":
                depth += 1
                opened = True
            elif ch in ")]}":
                depth -= 1
            elif ch == ":" and depth <= 0 and opened:
                return k
    return start


def _py_body_end(rows, lines, head_end, indent):
    """본문의 마지막 코드 줄. 빈 줄, 주석 줄, 여러 줄 문자열 안의 줄은 들여쓰기와 무관하게 본문을 끊지 않는다."""
    last = head_end
    for k in range(head_end + 1, len(rows)):
        if rows[k].get("in") or not rows[k]["code"]:
            continue
        if _indent(lines[k]) <= indent:
            break
        last = k
    return last


def _py_public_scope(found, rows, lines):
    """모듈 맨 위 함수와 공개 클래스의 메서드만 공개로 본다. `__main__` 블록이 있는 스크립트는 남이 부르는 코드가 아니다."""
    if any(PY_MAIN.match(r["k"]) for r in rows):
        for fn in found:
            fn["public"] = False
        return

    classes = [(ln, _indent(lines[ln]), m.group(1)) for ln, r in enumerate(rows) for m in [PY_CLASS.match(r["k"])] if m]
    for fn in found:
        if fn["indent"] == 0:
            continue
        owner = [c for c in classes if c[0] < fn["start"] and c[1] < fn["indent"]]
        fn["public"] = fn["public"] and bool(owner) and owner[-1][1] == 0 and not owner[-1][2].startswith("_")


def _c_spans(rows, lang):
    """가장 바깥 함수의 (머리 줄, 여는 중괄호 줄, 닫는 중괄호 줄) 목록.

    머리 안(매개변수 괄호, 제네릭 `<>`, 반환 타입 `: {`)의 중괄호는 타입이나 기본값이라 본문이 아니다.
    본문은 머리 뒤 깊이 0 에서 처음 여는 `{` 다.
    """
    keyword = C_FN_KEYWORD[lang]
    stack = []
    spans = []
    sig = None  # 머리를 읽는 중: {"ln", "paren"(머리가 시작할 때의 괄호 깊이), "angle", "brace", "call"}
    paren = 0
    prev = ""

    def start(ln, call=False):
        return {"ln": ln, "paren": paren, "angle": 0, "brace": 0, "call": call}

    def depth():
        return paren - sig["paren"] + sig["angle"] + sig["brace"] if sig else 0

    for ln, row in enumerate(rows):
        code = row["k"].rstrip()
        method = C_METHOD.match(code) if lang == "ts" else None
        if method and method.group(1) not in C_CONTROL and not code.endswith(";") and sig is None:
            sig = start(ln, call=True)  # 메서드 머리이거나 호출(`useEffect(() => {`)

        toks = C_TOKEN.findall(code)
        for i, tok in enumerate(toks):
            if tok in ("(", ")"):
                paren += 1 if tok == "(" else -1
            elif tok == keyword:
                sig = start(ln)
            elif tok == "=>" and toks[i + 1:i + 2] == ["{"] and (sig is None or sig["call"] or depth() == 0):
                sig = start(ln)  # 화살표 함수 본문이 바로 온다. 키워드 머리의 괄호 안이면 함수 타입(`cb: () => {...}`)이다
            elif sig and tok in ("<", ">") and lang != "go":  # Go 제네릭은 `[]` 이고 `<-` 는 채널이다
                sig["angle"] = max(0, sig["angle"] + (1 if tok == "<" else -1))
            elif tok == "{" and sig and (depth() > 0 or prev == ":"):
                sig["brace"] += 1  # 머리 안의 타입이나 기본값
                stack.append((False, None, ln, True))
            elif tok == "{":
                inside = any(is_fn for is_fn, _, _, _ in stack)
                stack.append((sig is not None and not inside, sig and sig["ln"], ln, False))
                sig = None
            elif tok == "}" and stack:
                is_fn, head, brace, in_sig = stack.pop()
                if in_sig and sig:
                    sig["brace"] = max(0, sig["brace"] - 1)
                if is_fn:
                    spans.append((head, brace, ln))
            elif (depth() if sig else paren) <= 0 and (tok == ";" or tok == "=" and lang == "kt"):
                sig = None  # 몸통 없는 선언이거나 Kotlin 식 몸통
            prev = tok

        # 중괄호가 이 줄에도 다음 줄에도 없는 머리는 호출이나 시그니처다
        if sig is not None and depth() <= 0 and code and not code.endswith("{") and not _next_continues(rows, ln):
            sig = None
    return spans


def _next_continues(rows, ln):
    """다음 코드 줄이 머리를 잇는가(Allman 중괄호, Rust where 절, 반환 타입 줄)."""
    for row in rows[ln + 1:ln + 4]:
        code = row["k"].strip()
        if code:
            return code.startswith(C_CONTINUES)
    return False


def _c_functions(rows, lang):
    out = []
    for head, brace, end in _c_spans(rows, lang):
        code = rows[head]["k"]
        name = next((m.group(1) for rx in C_NAMES for m in [rx.search(code)] if m), None)
        if name is None:
            m = C_METHOD.match(code)
            name = m.group(1) if m else "(anonymous)"
        out.append({"name": name, "start": head, "header_end": brace, "end": end, "last": end, "public": _c_public(code, name, lang),
                    "metamethod": False, "test": lang == "rust" and _rust_test(rows, head)})
    return out


def _rust_test(rows, head):
    """머리 줄이나 그 바로 위 속성 줄에 시험 속성(`#[test]`, `#[tokio::test]`)이 있는가."""
    k = head
    while k >= 0 and (k == head or rows[k]["code"] and ATTRIBUTE.match(rows[k]["k"])):
        if RUST_TEST.search(rows[k]["k"]):
            return True
        k -= 1
    return False


def _c_public(code, name, lang):
    if lang == "ts":
        return bool(re.search(r"\bexport\b", code))
    if lang == "rust":
        return bool(re.search(r"\bpub\b", code))
    if lang == "go":
        return name[:1].isupper()
    return not KT_PRIVATE.search(code) and name != "(anonymous)"


# ---------- 지표 ----------

def measure(rows, lines, fn, lang):
    """한 함수의 지표 dict(줄 번호는 1 기반): 빈 줄, 문단, 최장 이어짐, 라벨, 끼운 주석, 선언, 문서 주석."""
    doc = _doc_info(rows, lines, fn, lang)
    kinds = _body_kinds(rows, fn, doc.pop("skip", frozenset()))
    nonblank = sum(1 for _, kind in kinds if kind != "blank")
    runs = _runs(kinds)
    interleaved, labels = _comment_blocks(rows, kinds)
    return {
        "name": fn["name"], "start": fn["start"] + 1, "end": fn["last"] + 1, "public": fn["public"], "metamethod": fn["metamethod"],
        "test": fn["test"], "nonblank": nonblank, "blank": len(kinds) - nonblank, "paragraphs": len(runs),
        "max_run": max(runs, default=0), "labels": labels, "interleaved": interleaved, "multi_decl": _multi_decl(rows, kinds, lang),
        "one_letter": _one_letter(rows, kinds, lang), **doc,
    }


def _body_kinds(rows, fn, skip):
    """본문 줄마다 (0 기반 줄, "blank" | "comment" | "code"). 앞뒤 빈 줄과 skip 줄(파이썬 docstring)은 뺀다."""
    out = []
    for ln in range(fn["header_end"] + 1, fn["end"]):
        if ln in skip:
            continue
        r = rows[ln]
        out.append((ln, "code" if r["code"] else "comment" if r["c"] or r.get("in") else "blank"))

    while out and out[-1][1] == "blank":
        out.pop()
    while out and out[0][1] == "blank":
        out.pop(0)
    return out


def _runs(kinds):
    """빈 줄로 나뉜 문단마다의 줄 수."""
    runs = []
    cur = 0
    for _, kind in kinds:
        if kind != "blank":
            cur += 1
        elif cur:
            runs.append(cur)
            cur = 0
    return runs + [cur] if cur else runs


def _comment_blocks(rows, kinds):
    """(끼운 여러 줄 주석 [(1 기반 시작 줄, 줄 수)], 라벨 수). 끼운 것은 바로 위와 아래가 코드인 2줄 이상 덩어리다."""
    interleaved = []
    labels = 0
    i = 0
    while i < len(kinds):
        if kinds[i][1] != "comment":
            i += 1
            continue

        j = i
        while j + 1 < len(kinds) and kinds[j + 1][1] == "comment":
            j += 1
        above = kinds[i - 1][1] if i else "blank"
        below = kinds[j + 1][1] if j + 1 < len(kinds) else "blank"
        if j > i and above == "code" and below == "code":
            interleaved.append((kinds[i][0] + 1, j - i + 1))
        if i == j and above == "blank" and below == "code" and is_label(" ".join(rows[kinds[i][0]]["c"])):
            labels += 1
        i = j + 1
    return interleaved, labels


def is_label(text):
    """본문 단계 라벨처럼 보이는 한 줄 주석인가: 낱말 2-10, 마침표로 끝나지 않고 목록 표지나 TODO 로 시작하지 않는다."""
    body = text.strip().lstrip("-/#* ").rstrip()
    words = LABEL_WORD.findall(body)
    return LABEL_WORDS_MIN <= len(words) <= LABEL_WORDS_MAX and not body.endswith(".") and not body.startswith(("TODO", "NOTE", "FIXME"))


def _top_level_comma(code):
    depth = 0
    for ch in code:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        elif ch == "," and depth == 0:
            return True
    return False


def _multi_decl(rows, kinds, lang):
    """한 줄에 이름을 여럿 선언한 수. 오른쪽이 식 하나(여러 반환 받기)면 세지 않는다."""
    rx = LUA_MULTI if lang == "lua" else TS_MULTI if lang == "ts" else None
    if rx is None:
        return 0
    n = 0
    for ln, kind in kinds:
        code = rows[ln]["k"]
        if kind != "code" or not rx.match(code):
            continue
        if lang == "lua":
            _, eq, right = code.partition("=")
            n += not eq or _top_level_comma(right)
        else:
            n += _top_level_comma(code) and not TS_DESTRUCTURE.match(code)
    return n


def _one_letter(rows, kinds, lang):
    rx = ONE_LETTER.get(lang)
    if rx is None:
        return 0
    return sum(1 for ln, kind in kinds if kind == "code" and rx.match(rows[ln]["k"]))


# ---------- 문서 주석 ----------

def _doc_info(rows, lines, fn, lang):
    """{"doc": none | ok | hidden, "doc_first", "doc_first_len", "doc_sentence"}. hidden 은 호버에 안 보이는 꼴이다.

    doc_sentence 는 첫 문장이 첫 줄에서 끝나는가. 파이썬은 docstring 줄을 "skip" 으로 함께 돌려준다.
    """
    if lang == "py":
        return _py_doc(rows, lines, fn)

    # Comment lines above the header, past decorators and region markers
    k = fn["start"] - 1
    while k >= 0 and rows[k]["code"] and ATTRIBUTE.match(rows[k]["k"]):
        k -= 1
    while k >= 0 and _comment_only(rows[k]) and REGION.match(lines[k]):
        k -= 1
    if k < 0 or not _comment_only(rows[k]):
        return {"doc": "none", "doc_first": "", "doc_first_len": 0, "doc_sentence": True}

    # 가장 가까운 주석이 정한다. 문서 주석 위의 이유 주석은 문서를 가리지 않는다
    block = _nearest_doc(rows, lines, k, lang)
    if not block:
        top = k
        while top > 0 and _comment_only(rows[top - 1]) and not REGION.match(lines[top - 1]):
            top -= 1
        first = _doc_text(lines[top])
        return {"doc": "hidden", "doc_first": first, "doc_first_len": len(first), "doc_sentence": True}
    return _summary([_doc_text(line) for line in block])


def _comment_only(row):
    return not row["code"] and bool(row["c"])


def _block_start(rows, k):
    """k 줄이 든 여러 줄 주석의 여는 줄(줄 주석이면 k)."""
    while k > 0 and rows[k].get("in") and _comment_only(rows[k - 1]):
        k -= 1
    return k


def _nearest_doc(rows, lines, k, lang):
    """k 줄에서 위로 이어진 문서 주석 꼴의 줄 목록(위에서 아래 순). k 줄이 문서 꼴이 아니면 빈 목록.

    블록 주석(`/** */`, `--[=[ ]=]`)은 그 블록 하나, 줄 주석(`---`, `///`)은 문서 꼴이 끊길 때까지다.
    """
    start = _block_start(rows, k)
    if not DOC_OPEN[lang].match(lines[start]):
        return []
    if start < k:
        return lines[start:k + 1]
    while start > 0 and _comment_only(rows[start - 1]) and not rows[start - 1].get("in") and not REGION.match(lines[start - 1]) \
            and DOC_OPEN[lang].match(lines[start - 1]):
        start -= 1
    return lines[start:k + 1]


def _doc_text(line):
    text = DOC_MARK.sub("", line.strip(), count=1).strip()
    return re.sub(r"(?:\*/|\]=*\])$", "", text).strip()


def _summary(texts):
    while texts and not texts[0]:
        texts = texts[1:]
    first = texts[0] if texts else ""
    nxt = texts[1] if len(texts) > 1 else ""
    runs_on = bool(first) and bool(nxt) and not DOC_TAG.match(nxt) and not SENTENCE_END.search(first)
    return {"doc": "ok", "doc_first": first, "doc_first_len": len(first), "doc_sentence": not runs_on}


def _py_doc(rows, lines, fn):
    k = fn["header_end"] + 1
    while k < fn["end"] and not lines[k].strip():
        k += 1
    if k >= fn["end"] or rows[k]["k"].strip() != '""':
        return {"doc": "none", "doc_first": "", "doc_first_len": 0, "doc_sentence": True, "skip": frozenset()}

    end = k + 1
    while end < fn["end"] and rows[end].get("in"):
        end += 1
    texts = [re.sub(r'^[rRbBuUfF]*("""|\'\'\'|"|\')', "", lines[k].strip())] + [line.strip() for line in lines[k + 1:end]]
    texts = [re.sub(r'("""|\'\'\')$', "", t).strip() for t in texts]
    return {**_summary(texts), "skip": frozenset(range(k, end))}


# ---------- 알림 범주 ----------

def findings(m, lang, limits):
    """measure 결과에서 알림 범주별 설명: {"layout", "interleaved comment", "doc summary"} 가운데 걸린 것.

    limits 는 min_lines, max_run, doc_first_max 를 가진다(conventions-check.py 의 DEFAULT_LAYOUT).
    """
    out = {}
    if m["nonblank"] >= limits["min_lines"] and (not m["blank"] or m["max_run"] > limits["max_run"]):
        out["layout"] = "%s L%d-%d (%d lines, %d blank, longest run %d)" % (
            m["name"], m["start"], m["end"], m["nonblank"], m["blank"], m["max_run"])
    if m["interleaved"]:
        out["interleaved comment"] = "%s %s" % (m["name"], ", ".join("L%d (%d lines)" % pair for pair in m["interleaved"]))
    doc = _doc_problem(m, limits)
    if doc:
        out["doc summary"] = "%s L%d %s" % (m["name"], m["start"], doc)
    return out


def _doc_problem(m, limits):
    if m["metamethod"]:
        return None
    if m["doc"] != "ok":
        if m["test"]:
            return TEST_NO_DOC if m["doc"] == "none" else TEST_HIDDEN_DOC
        if not m["public"]:
            return None
        return "has no doc comment" if m["doc"] == "none" else "has a comment that hover does not show"
    if m["doc_first_len"] > limits["doc_first_max"]:
        return "first doc line is %d characters" % m["doc_first_len"]
    if not m["doc_sentence"]:
        return "first doc sentence runs past the first line"
    return None


# ---------- 편집 알림 (conventions-check.py) ----------

def limits(user):
    """DEFAULT_LAYOUT 에 저장소 conventions.json 의 layout 값(숫자만)을 덮는다."""
    out = dict(DEFAULT_LAYOUT)
    if isinstance(user, dict):
        out.update({k: v for k, v in user.items() if k in out and isinstance(v, (int, float)) and not isinstance(v, bool)})
    return out


def edit_findings(text, rows, added, lang, user_limits=None, recheck=()):
    """이번 편집이 쓰거나 키운 함수의 알림: [(범주, 함수 키, 설명, 다시 본 것인가)].

    거의 새로 쓴(mostly) 함수와 grow 줄 이상 키운 함수는 모든 범주를, recheck 키의 함수는 doc summary 만 본다.
    함수 키는 이름이고, 파일에 같은 이름이 또 있으면 두 번째부터 `이름#순번`이다(fn_keys).
    """
    lines = text.split("\n")
    lim = limits(user_limits)
    out = []
    found_fns = functions(rows, lines, lang)
    for fn, key in zip(found_fns, fn_keys(found_fns)):
        span = [ln for ln in range(fn["start"], fn["last"] + 1) if lines[ln].strip()]
        new = sum(1 for ln in span if ln in added)
        wrote = bool(span) and new >= lim["mostly"] * len(span)
        grew = new >= lim["grow"]
        again = key in recheck
        if not (wrote or grew or again):
            continue

        found = findings(measure(rows, lines, fn, lang), lang, lim)
        if not (wrote or grew):
            found = {k: v for k, v in found.items() if k == "doc summary"}
        tag = " [grown by %d lines]" % new if grew and not wrote else ""
        out += [(cat, key, desc + tag, again and cat == "doc summary") for cat, desc in found.items()]
    return out


def fn_keys(fns):
    """함수마다 알림 중복 제거와 다시 보기에 쓰는 키: 이름, 같은 이름의 두 번째부터는 `이름#2`, `이름#3`."""
    seen = {}
    keys = []
    for fn in fns:
        seen[fn["name"]] = seen.get(fn["name"], 0) + 1
        keys.append(fn["name"] if seen[fn["name"]] == 1 else "%s#%d" % (fn["name"], seen[fn["name"]]))
    return keys


def notice(items, lang):
    """알림 한 줄의 layout 부분. items 는 [(범주, 설명, 다시 본 것인가)], lang 은 문서 주석 꼴을 고른다."""
    docs = [desc for cat, desc, _ in items if cat == "doc summary"]
    tests = sum(1 for desc in docs if TEST_MARK in desc)
    by = {}
    for cat, desc, again in items:
        by.setdefault(cat, []).append(desc + (" (still so after your last edit)" if again else ""))
    for cat, descs in by.items():
        if len(descs) > LIST_MAX:
            by[cat] = descs[:LIST_MAX] + ["%d more" % (len(descs) - LIST_MAX)]

    # One sentence group per category
    parts = []
    if "layout" in by:
        parts.append("Functions you wrote or grew read as one block: " + "; ".join(by["layout"]) + ". Hand-written functions of this size "
                     "have about 4 paragraphs and runs under 13 lines. If a function has steps, separate them with blank lines and short "
                     "step labels; if it is one step (a literal, one expression), leave it.")
    if "interleaved comment" in by:
        parts.append("Multi-line comments between statements: " + "; ".join(by["interleaved comment"]) + ". Move a design reason "
                     "above the declaration, apart from the doc comment, or cut it to one line at the trap.")
    if "doc summary" in by:
        text = "Doc comments: " + "; ".join(by["doc summary"]) + "."
        if tests < len(docs):
            text += (" Public functions in code others call get " + DOC_FORM[lang]
                     + " whose first sentence ends on the first line, about 80 characters.")
        if tests:
            text += (" Each test gets " + TEST_FORM.get(lang, "a one-line doc comment") + " saying the one behavior it checks; "
                     'a line that needs "and" means two tests.')
        parts.append(text)

    return " ".join(parts) + " These numbers are evidence, not a verdict; a repo's own rules win."


def enabled(ext):
    """이 확장자를 재고 HARNESS_READABLE_CODE 가 켜졌나(harness.env 층, conv_env.py)."""
    if ext not in LANG_BY_EXT:
        return False
    import conv_env
    return conv_env.is_on("HARNESS_READABLE_CODE")
