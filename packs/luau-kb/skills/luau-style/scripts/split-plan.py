#!/usr/bin/env python3
"""분리 계획기 (읽기 전용). 큰 .luau 파일 하나를 정적으로 읽고 "어떻게 나눌지" 판단 재료를 낸다.

사용:
  python3 -I split-plan.py <파일.luau> [--json] [--target 400] [--max 800] [--name 모듈이름] [--scope 함수이름]

내는 것:
  - 분석 범위: 최상위 함수, 또는 파일 대부분을 차지하는 한 함수(닫개 공장·`new` 본문)의 안쪽
  - 응집 군집: 호출 간선 + 공유 상태 + 구획(region·주석 띠)·이름 가족을 약한 사전 정보로 쓴 가중 모듈성 군집화
  - 군집별 후보 파일명, 줄 수, 공개 이름, 쓰는 상태
  - 군집 사이 간선(나눴을 때 생길 import), 순환 위험, 전방 선언이 파일 경계를 넘는지
  - 공유 상태를 어디로 옮길지, 공용 헬퍼, 반복 블록
  - "옮기기만" 커밋 순서

정적 근사다. 지역 이름 가림(shadowing)은 함수 안에서 같은 이름을 선언하면 바깥 참조로 보지 않는 정도로만 다룬다.
결과는 판단 재료이고 결정은 사람이 한다. 근거와 전략: luau-style references/splitting.md, structure.md.
쓰기 없음. 표준 라이브러리만 쓴다.
"""
import argparse
import collections
import json
import math
import os
import re
import sys

KEYWORDS = {"and", "break", "do", "else", "elseif", "end", "false", "for", "function", "if", "in", "local", "nil",
            "not", "or", "repeat", "return", "then", "true", "until", "while", "continue", "const"}
OPS = ["...", "..=", "//=", "::", "->", "==", "~=", "<=", ">=", "+=", "-=", "*=", "/=", "%=", "^=", "..", "//"]
# 이 토큰 뒤의 `if` 는 식(if-then-else 식, end 없음)이다. `<` `>` 는 넣지 않는다 - 반환 타입 `Arr<T>` 의 `>` 바로 뒤에
# 문장 `if` 가 온다
EXPR_BEFORE_IF = {"=", "(", ",", "{", "[", "return", "and", "or", "not", "==", "~=", "..", "+", "-", "*", "/", "%",
                  "^", "<=", ">=", "//", "+=", "-=", "*=", "/=", "%=", "^=", "..=", "in", "elseif", "if",
                  "while", "until"}
# 줄 끝에 있으면 다음 줄이 같은 문장이다
# `<` `>` 는 넣지 않는다: 줄 끝의 `>` 는 거의 늘 제네릭 닫기(`export type Arr<T> = ArrData<T>`)다
CONTINUE = {"=", ",", "(", "{", "[", "..", "+", "-", "*", "/", "%", "^", "and", "or", "not", "==", "~=",
            "<=", ">=", "//", "->", "::", ":", ".", "local", "const", "function", "return", "in", "+=", "-=", "..="}
REGION = re.compile(r"^\s*--\s*#region\b\s*(.*)$")
ENDREGION = re.compile(r"^\s*--\s*#endregion\b")
# 주석 띠: `-- ── units ──`, `-- ===== X =====`, `-- ----- X -----`, `--[[ ### X ### ]]`
BANNER = re.compile(r"^\s*--+\s*(?:[─━═]{2,}|[=\-#*~]{3,})\s*(.+?)\s*(?:[─━═=\-#*~]{2,})?\s*$")
STOP = {"get", "set", "is", "of", "on", "to", "new", "make", "do", "has", "can", "with", "at", "by", "for", "from",
        "the", "all", "many", "one", "in", "out", "into", "and", "or", "if", "try", "find", "add", "remove", "update",
        "check", "apply", "build", "handle", "run", "local", "fn", "x", "y", "unchecked", "inplace"}
EXEMPT = re.compile(r"^\s*(?:--|//|#)\s*@structure-exempt\s*:?\s*(.*)$")


# ─────────────────────────────── 토큰화 ───────────────────────────────

def long_bracket(src, i):
    """src[i] == '[' 에서 시작하는 긴 괄호의 등호 수. 아니면 -1."""
    j = i + 1
    while j < len(src) and src[j] == "=":
        j += 1
    return j - i - 1 if j < len(src) and src[j] == "[" else -1


def tokenize(src):
    """(kind, value, line) 목록. kind: name kw num str op. 주석은 버린다. 보간 문자열 `{식}` 안은 토큰으로 낸다."""
    toks, i, line, n = [], 0, 1, len(src)
    brace_stack = []  # 보간 문자열 안의 `{` 깊이 (각 원소: 그 보간에서 연 { 수)

    def read_backtick(i, line):
        # i 는 ` 다음 또는 } 다음 위치. 문자열 끝(`) 또는 보간 시작({)까지 읽는다
        while i < n:
            c = src[i]
            if c == "\\":
                i += 2
                continue
            if c == "\n":
                line += 1
            if c == "`":
                return i + 1, line, False
            if c == "{":
                return i + 1, line, True
            i += 1
        return i, line, False

    while i < n:
        c = src[i]
        if c == "\n":
            line += 1
            i += 1
            continue
        if c in " \t\r":
            i += 1
            continue
        if src.startswith("--", i):
            if i + 2 < n and src[i + 2] == "[" and long_bracket(src, i + 2) >= 0:
                lv = long_bracket(src, i + 2)
                close = "]" + "=" * lv + "]"
                j = src.find(close, i + 4 + lv)
                j = n if j < 0 else j + len(close)
                line += src.count("\n", i, j)
                i = j
            else:
                j = src.find("\n", i)
                i = n if j < 0 else j
            continue
        if c == "[" and long_bracket(src, i) >= 0:
            lv = long_bracket(src, i)
            close = "]" + "=" * lv + "]"
            j = src.find(close, i + 2 + lv)
            j = n if j < 0 else j + len(close)
            toks.append(("str", "S", line))
            line += src.count("\n", i, j)
            i = j
            continue
        if c in "\"'":
            j = i + 1
            while j < n and src[j] != c and src[j] != "\n":
                j += 2 if src[j] == "\\" else 1
            toks.append(("str", "S", line))
            i = j + 1
            continue
        if c == "`":
            toks.append(("str", "S", line))
            i, line, interp = read_backtick(i + 1, line)
            if interp:  # 보간 `{식}` 은 괄호처럼 낸다(안의 `if` 는 식이다)
                brace_stack.append(0)
                toks.append(("op", "(", line))
            continue
        if c == "}" and brace_stack and brace_stack[-1] == 0:
            brace_stack.pop()
            toks.append(("op", ")", line))
            i, line, interp = read_backtick(i + 1, line)
            if interp:
                brace_stack.append(0)
                toks.append(("op", "(", line))
            continue
        if c.isalpha() or c == "_":
            j = i + 1
            while j < n and (src[j].isalnum() or src[j] == "_"):
                j += 1
            w = src[i:j]
            toks.append(("kw" if w in KEYWORDS else "name", w, line))
            i = j
            continue
        if c.isdigit() or (c == "." and i + 1 < n and src[i + 1].isdigit()):
            j = i + 1
            while j < n and (src[j].isalnum() or src[j] in "._" or (src[j] in "+-" and src[j - 1] in "eE"
                                                                        and not src[i:j].lower().startswith("0x"))):
                j += 1
            toks.append(("num", "N", line))
            i = j
            continue
        for op in OPS:
            if src.startswith(op, i):
                toks.append(("op", op, line))
                i += len(op)
                break
        else:
            if brace_stack:
                if c == "{":
                    brace_stack[-1] += 1
                elif c == "}":
                    brace_stack[-1] -= 1
            toks.append(("op", c, line))
            i += 1
    return toks


# ─────────────────────────────── 블록 구조 ───────────────────────────────

def block_structure(toks):
    """토큰마다 블록 깊이(그 토큰 앞)와 괄호 깊이, 여는 키워드의 짝(닫는 토큰 번호)을 구한다."""
    depth = [0] * len(toks)
    pdepth = [0] * len(toks)
    match = {}
    stack, d, p = [], 0, 0
    pending_do = 0
    prev = None
    for i, (k, v, _) in enumerate(toks):
        depth[i], pdepth[i] = d, p
        if k == "op":
            if v in "({[":
                p += 1
            elif v in ")}]":
                p = max(0, p - 1)
        elif k == "kw":
            if v == "function":
                stack.append(i)
                d += 1
            elif v == "if":
                if prev not in EXPR_BEFORE_IF:
                    stack.append(i)
                    d += 1
            elif v in ("while", "for"):
                stack.append(i)
                d += 1
                pending_do += 1
            elif v == "do":
                if pending_do:
                    pending_do -= 1
                else:
                    stack.append(i)
                    d += 1
            elif v == "repeat":
                stack.append(i)
                d += 1
            elif v in ("end", "until"):
                if stack:
                    match[stack.pop()] = i
                d = max(0, d - 1)
        prev = v if k in ("op", "kw") else k
    return depth, pdepth, match


# ─────────────────────────────── 범위 안의 문장 ───────────────────────────────

class Unit:
    def __init__(self, kind, name, start_tok, end_tok, line0, line1):
        self.kind = kind          # func | local | type | field | import | return | misc | fwd
        self.name = name
        self.names = [name] if name else []
        self.t0, self.t1 = start_tok, end_tok
        self.line0, self.line1 = line0, line1
        self.doc0 = line0         # 바로 위 주석까지 포함한 시작 줄
        self.public = False
        self.section = None
        self.refs = collections.Counter()   # 범위 이름 -> 참조 수
        self.writes = set()                 # 범위 지역 중 다시 대입하거나 내용을 바꾼 것
        self.inner_funcs = 0
        self.fields = collections.Counter()  # 매개변수, 지역을 거쳐 읽는 필드(`session.bundles`) - 같은 자료를 만지는 신호
        self.init_kind = None               # local 의 초기값 모양: func require service literal table call nil none
        self.in_table = False               # 표 생성자 안의 메서드 필드
        self.alias = None                   # `f = g` 대입 정의의 g

    def lines(self):
        return self.line1 - self.doc0 + 1


def statements(toks, depth, pdepth, match, t0, t1, d):
    """토큰 [t0, t1) 범위에서 블록 깊이 d·괄호 깊이 0 인 문장의 시작 토큰 번호들."""
    starts = []
    base_p = pdepth[t0] if t0 < len(toks) else 0
    last_line = -1
    i = t0
    while i < t1:
        k, v, ln = toks[i]
        if depth[i] == d and pdepth[i] == base_p:
            prev = toks[i - 1] if i > t0 else None
            new_line = ln != last_line
            cont = prev is not None and prev[1] in CONTINUE and prev[0] in ("op", "kw")
            if (new_line and not cont) or (prev is not None and prev[1] == ";"):
                if not (k == "kw" and v in ("end", "until", "else", "elseif", "then", "do")):
                    starts.append(i)
        last_line = ln
        # 함수 본문은 건너뛴다(깊이가 달라서 어차피 안 걸리지만 빠르게)
        if k == "kw" and v == "function" and i in match and depth[i] == d:
            i = match[i]
            last_line = toks[i][2]
        i += 1
    return starts


def split_units(toks, depth, pdepth, match, t0, t1, d, module_names):
    starts = statements(toks, depth, pdepth, match, t0, t1, d)
    units = []
    for si, s in enumerate(starts):
        e = (starts[si + 1] if si + 1 < len(starts) else t1) - 1
        while e > s and toks[e][1] == ";":
            e -= 1
        u = classify(toks, s, e, match, module_names)
        if u:
            units.append(u)
            if u.kind in ("local", "return", "misc", "field"):
                ms = table_methods(toks, pdepth, match, u, module_names)
                units += ms
                if not ms and u.kind in ("misc", "local"):
                    units += anon_functions(toks, depth, match, u, d)
    return units


def anon_functions(toks, depth, match, parent, d):
    """호출 인자로 넘긴 익명 함수(`X.InputBegan:Connect(function(input) … end)`). 15줄 이상만 단위로 본다.
    이름은 바로 앞의 사건·호출 이름(`InputBegan`)에 줄 번호를 붙인다."""
    out = []
    j = parent.t0
    while j <= parent.t1:
        if toks[j][1] == "function" and depth[j] == d and j in match:
            end = match[j]
            if toks[end][2] - toks[j][2] + 1 >= 15:
                k, label = j - 1, None
                while k > parent.t0 and toks[k][1] in ("(", ","):
                    k -= 1
                if toks[k][0] == "name":
                    if toks[k][1] in ("Connect", "Once", "spawn", "defer", "delay") and k >= 2 and toks[k - 2][0] == "name":
                        label = toks[k - 2][1]
                    else:
                        label = toks[k][1]
                u = Unit("func", f"{label or 'anon'}@{toks[j][2]}", j, end, toks[j][2], toks[end][2])
                u.init_kind = "anon"
                out.append(u)
            j = end
        j += 1
    return out


def table_methods(toks, pdepth, match, parent, module_names):
    """표 생성자 안의 `Name = function(…) … end` 필드(공개 메서드 표). `local manager = { Register = function … }` 꼴."""
    out = []
    base = pdepth[parent.t0]
    j = parent.t0
    while j <= parent.t1 - 2:
        if toks[j][0] == "name" and toks[j + 1][1] == "=" and toks[j + 2][1] == "function" \
                and pdepth[j] == base + 1 and toks[j - 1][1] in ("{", ",", ";") and (j + 2) in match:
            end = match[j + 2]
            u = Unit("func", toks[j][1], j, end, toks[j][2], toks[end][2])
            u.public = True
            u.in_table = True
            out.append(u)
            j = end
        j += 1
    if out and parent.kind == "local":
        module_names.update(parent.names)
    return out


def classify(toks, s, e, match, module_names):
    k, v, ln = toks[s]
    end_line = toks[e][2]
    get = lambda j: toks[j][1] if j <= e else None
    if v == "@" or (k == "op" and v == "@"):
        # 속성(@native 등) 뒤의 정의
        j = s
        while j <= e and toks[j][1] in ("@",) or (j <= e and toks[j - 1][1] == "@"):
            j += 1
        u = classify(toks, j, e, match, module_names) if j <= e else None
        if u:
            u.line0 = u.doc0 = ln
        return u
    if v in ("local", "const"):
        if get(s + 1) == "function":
            name = get(s + 2)
            return Unit("func", name, s, e, ln, end_line)
        # local a, b: T = ...
        names, j = [], s + 1
        while j <= e and toks[j][0] == "name":
            names.append(toks[j][1])
            j += 1
            if get(j) == ":":  # 타입 주석은 , 나 = 까지 건너뛴다(괄호 깊이 고려)
                pd = 0
                j += 1
                while j <= e:
                    t = toks[j][1]
                    if t in "({[" or t == "<":
                        pd += 1
                    elif t in ")}]" or t == ">":
                        pd -= 1
                    elif pd <= 0 and t in (",", "="):
                        break
                    j += 1
            if get(j) == ",":
                j += 1
                continue
            break
        if not names:
            return None
        if get(j) != "=":
            u = Unit("local", names[0], s, e, ln, end_line)
            u.names = names
            u.init_kind = "none"
            return u
        rhs = j + 1
        u = Unit("local", names[0], s, e, ln, end_line)
        u.names = names
        r = get(rhs)
        if r == "function":
            u.kind = "func"
            u.init_kind = "func"
        elif r == "require" or (r in ("(",) and get(rhs + 1) == "require"):
            u.kind = "import"
        elif r == "game" and get(rhs + 1) == ":" and get(rhs + 2) == "GetService":
            u.kind = "import"
        elif r == "{":
            u.init_kind = "table"
        elif r == "setmetatable":
            u.init_kind = "table"
        elif r == "nil":
            u.init_kind = "nil"
        elif toks[rhs][0] in ("num", "str") or r in ("true", "false", "-"):
            u.init_kind = "literal"
        else:
            u.init_kind = "call"
        return u
    if v == "function":
        # function a.b:c(  /  function f(
        path, j = [], s + 1
        while j <= e and toks[j][0] == "name":
            path.append(toks[j][1])
            if get(j + 1) in (".", ":"):
                j += 2
            else:
                break
        if not path:
            return None
        u = Unit("func", path[-1], s, e, ln, end_line)
        if len(path) >= 2 and path[0] in module_names:
            u.public = True
        elif len(path) == 1:
            u.kind = "func"
            u.init_kind = "define"   # 전방 선언한 지역에 대입하는 정의일 수 있다
        return u
    if v in ("type", "export") and (get(s + 1) == "type" or toks[s + 1][0] == "name"):
        name = get(s + 2) if v == "export" else get(s + 1)
        if v == "type" and get(s + 1) == "function":
            name = get(s + 2)
        return Unit("type", name, s, e, ln, end_line)
    if v == "return":
        return Unit("return", None, s, e, ln, end_line)
    if k == "name":
        # M.f = function / M.x = ... / f = function
        j, path = s, []
        while j <= e and toks[j][0] == "name":
            path.append(toks[j][1])
            if get(j + 1) == ".":
                j += 2
            else:
                break
        if get(j + 1) == "=":
            rhs = get(j + 2)
            if len(path) >= 2 and path[0] in module_names:
                u = Unit("func" if rhs == "function" else "field", path[-1], s, e, ln, end_line)
                u.public = True
                return u
            if len(path) == 1 and rhs == "function":
                u = Unit("func", path[0], s, e, ln, end_line)
                u.init_kind = "define"
                return u
            if len(path) == 1 and j + 2 <= e and toks[j + 2][0] == "name" and j + 2 == e:
                # `linkLater = linkNow` - 전방 선언한 지역에 다른 함수를 대입하는 정의
                u = Unit("assign", path[0], s, e, ln, end_line)
                u.alias = toks[j + 2][1]
                return u
    return Unit("misc", None, s, e, ln, end_line)


# ─────────────────────────────── 참조 수집 ───────────────────────────────

def body_names(toks, t0, t1):
    """함수 본문 안에서 선언한 이름(매개변수·local·for 변수·내부 함수). 가림 근사용."""
    out = set()
    i = t0
    while i <= t1:
        k, v, _ = toks[i]
        if v in ("local", "const") and k == "kw":
            j = i + 1
            if j <= t1 and toks[j][1] == "function":
                j += 1
            while j <= t1 and toks[j][0] == "name":
                out.add(toks[j][1])
                j += 1
                if j <= t1 and toks[j][1] == ":":
                    break
                if j <= t1 and toks[j][1] == ",":
                    j += 1
                    continue
                break
        elif v == "for" and k == "kw":
            j = i + 1
            while j <= t1 and toks[j][1] not in ("in", "=", "do"):
                if toks[j][0] == "name":
                    out.add(toks[j][1])
                    # 타입 주석(`for i: number`) 안의 이름도 들어가지만 해롭지 않다
                j += 1
        elif v == "function" and k == "kw":
            j = i + 1
            while j <= t1 and toks[j][1] != "(":
                j += 1
            pd = 0
            while j <= t1:
                t = toks[j][1]
                if t == "(":
                    pd += 1
                elif t == ")":
                    pd -= 1
                    if pd == 0:
                        break
                elif pd == 1 and toks[j][0] == "name" and toks[j - 1][1] in ("(", ","):
                    out.add(t)
                j += 1
        i += 1
    return out


LIB_OBJS = {"math", "table", "string", "buffer", "coroutine", "utf8", "bit32", "os", "debug", "task", "Enum", "Vector3",
            "Vector2", "CFrame", "Color3", "UDim2", "UDim", "Instance", "TweenInfo", "NumberRange", "BrickColor",
            "game", "workspace", "script", "self"}


def collect_refs(u, toks, scope_names, module_names, skip_own_params=True, opaque=()):
    """함수 단위 u 가 참조하는 범위 이름과, 다시 대입하거나 바꾼 범위 지역."""
    t0, t1 = u.t0, u.t1
    # 정의 머리(local function name / function M.name)는 참조로 세지 않는다
    j = t0
    while j <= t1 and toks[j][1] != "(":
        j += 1
    inner = body_names(toks, j, t1)
    # 자기 매개변수는 body_names 의 첫 function 에서 잡히도록 머리부터 다시
    inner |= body_names(toks, t0, min(t1, j + 64)) if skip_own_params else set()
    i = j
    while i <= t1:
        k, v, _ = toks[i]
        if k == "kw" and v == "function":
            u.inner_funcs += 1
        if k != "name":
            i += 1
            continue
        prev = toks[i - 1][1] if i > 0 else None
        nxt = toks[i + 1][1] if i + 1 < len(toks) else None
        if prev in (".", ":"):
            # M.f 꼴: M 이 모듈 표면 f 를 참조
            obj = toks[i - 2][1] if i >= 2 else None
            first = toks[i - 3][1] not in (".", ":") if i >= 3 else True
            if prev == "." and obj in module_names and first:
                if v in scope_names:
                    u.refs[v] += 1
            elif prev == "." and toks[i - 2][0] == "name" and obj not in opaque and obj not in LIB_OBJS \
                    and obj not in module_names and nxt != "(":
                u.fields[v] += 1
            i += 1
            continue
        # 타입 주석 안의 이름(`: Record`)은 넘긴다 - 타입 이름은 scope_names 에 없으니 대체로 안전
        if v in inner or v not in scope_names:
            i += 1
            continue
        u.refs[v] += 1
        # 쓰기: name = / name += / name[..] = / name.x = / table.insert(name
        if nxt in ("=", "+=", "-=", "*=", "/=", "..=", "%=", "^=", "//=") and prev not in ("local", "const"):
            u.writes.add(v)
        elif nxt in ("[", "."):
            # 끝까지 따라가 = 가 오는지(간단히: 같은 줄에서 다음 = 이 == 가 아니고, 괄호 깊이 0 에서)
            pd, j2 = 0, i + 1
            while j2 <= t1 and toks[j2][2] == toks[i][2]:
                t = toks[j2][1]
                if t in "([{":
                    pd += 1
                elif t in ")]}":
                    pd -= 1
                elif pd == 0 and t == "=":
                    u.writes.add(v)
                    break
                elif pd == 0 and (t in ("(", ":") or toks[j2][0] == "kw"):
                    break
                j2 += 1
        if prev == "(" and i >= 3 and toks[i - 3][1] == "table" and toks[i - 2][1] in ("insert", "remove", "clear", "sort", "move"):
            u.writes.add(v)
        i += 1


# ─────────────────────────────── 범위 고르기 ───────────────────────────────

def find_module_names(toks, depth, pdepth):
    """모듈 표 이름 후보: 깊이 0 의 `local M = {}` 와 마지막 `return M`."""
    names = set()
    for i, (k, v, _) in enumerate(toks):
        if depth[i] == 0 and v in ("local", "const") and i + 3 < len(toks) and toks[i + 2][1] == "=" \
                and toks[i + 3][1] == "{" and toks[i + 4][1] == "}":
            names.add(toks[i + 1][1])
        if v == "return" and depth[i] == 0 and i + 1 < len(toks) and toks[i + 1][0] == "name" \
                and (i + 2 >= len(toks) or toks[i + 2][1] not in (".", ":", "(", "[")):
            names.add(toks[i + 1][1])
    return names


def inner_counts(toks, depth, match, u):
    """함수 단위 u 의 본문 바로 안(한 단계 깊이)의 함수 정의 수와 지역 선언 수."""
    f = next((j for j in range(u.t0, u.t1 + 1) if toks[j][1] == "function"), None)
    if f is None or f not in match:
        return 0, 0
    d = depth[f] + 1
    fn = sum(1 for j in range(f + 1, match[f]) if toks[j][1] == "function" and depth[j] == d)
    lo = sum(1 for j in range(f + 1, match[f]) if toks[j][1] in ("local", "const") and depth[j] == d
             and toks[j + 1][1] != "function")
    return fn, lo


def choose_scope(toks, depth, pdepth, match, module_names, nlines, force=None):
    """분석할 범위. 한 함수가 범위 줄의 절반 넘게 차지하고 안에 함수가 여덟 개 넘게 있으면 그 안으로 내려간다.
    force 를 주면(`--scope enter`) 그 이름의 함수 안으로 내려간다."""
    t0, t1, d = 0, len(toks), 0
    path = []
    names = set(module_names)
    while True:
        units = split_units(toks, depth, pdepth, match, t0, t1, d, names)
        span = max(1, (toks[t1 - 1][2] if t1 - 1 < len(toks) else nlines) - (toks[t0][2] if t0 < len(toks) else 1) + 1)
        big = None
        if force:
            hit = [u for u in units if u.kind == "func" and u.name == force]
            if hit:
                u = hit[0]
                f = next((j for j in range(u.t0, u.t1 + 1) if toks[j][1] == "function"), None)
                if f is not None and f in match:
                    big = (u, f)
                    force = None
        for u in units:
            if big:
                break
            if u.kind == "func" and u.lines() >= span * 0.5:
                # 본문 안 깊이 d+1 의 함수 정의 수
                f = next((j for j in range(u.t0, u.t1 + 1) if toks[j][1] == "function"), None)
                if f is None or f not in match:
                    continue
                inner = sum(1 for j in range(f + 1, match[f]) if toks[j][1] == "function" and depth[j] == d + 1)
                if inner >= 8:
                    big = (u, f)
        if not big:
            return t0, t1, d, units, path, names
        u, f = big
        path.append(f"{u.name} ({u.line0}–{u.line1})")
        # 안쪽 범위의 "모듈 표"는 그 안의 `local X = {}` 와 `return X`
        t0, t1, d = f + 1, match[f], d + 1
        inner_names = set()
        for j in range(t0, t1):
            if depth[j] == d and toks[j][1] in ("local", "const") and j + 4 < t1 and toks[j + 2][1] == "=" \
                    and toks[j + 3][1] == "{" and toks[j + 4][1] == "}":
                inner_names.add(toks[j + 1][1])
            if depth[j] == d and toks[j][1] == "return" and toks[j + 1][0] == "name" \
                    and toks[j + 2][1] not in (".", ":", "(", "["):
                inner_names.add(toks[j + 1][1])
        names = inner_names or names


# ─────────────────────────────── 구획과 가족 ───────────────────────────────

def sections(lines, line0, line1):
    """(시작 줄, 끝 줄, 제목) 목록. region 우선, 없으면 주석 띠."""
    regs, stack = [], []
    for i in range(line0, line1 + 1):
        l = lines[i - 1]
        m = REGION.match(l)
        if m:
            stack.append((i, clean_title(m.group(1))))
            continue
        if ENDREGION.match(l) and stack:
            s, t = stack.pop()
            regs.append((s, i, t))
    # 닫히지 않은 region 은 다음 region 이 열리는 줄 앞에서 끝난 것으로 본다(endregion 을 빠뜨린 파일이 흔하다)
    opens = sorted([r[0] for r in regs] + [s for s, _ in stack])
    for s, t in stack:
        nxt = [o for o in opens if o > s]
        regs.append((s, (nxt[0] - 1) if nxt else line1, t))
    if regs:
        # 안쪽 region 이 먼저 맞도록 짧은 것부터
        regs.sort(key=lambda r: r[1] - r[0])
        return regs, "region"
    bans = []
    for i in range(line0, line1 + 1):
        m = BANNER.match(lines[i - 1])
        if m and re.search(r"\w", m.group(1)):
            bans.append((i, clean_title(m.group(1))))
    out = [(s, (bans[k + 1][0] - 1 if k + 1 < len(bans) else line1), t) for k, (s, t) in enumerate(bans)]
    return out, ("banner" if out else None)


def clean_title(t):
    return re.sub(r"^[\s─━═=\-#*~]+|[\s─━═=\-#*~]+$", "", t).strip() or "(이름 없음)"


def words(name):
    parts = re.findall(r"[A-Z]+(?=[A-Z][a-z]|\d|$)|[A-Z]?[a-z]+|\d+", name or "")
    return [p.lower() for p in parts]


def families(names):
    """camelCase 앞 단어(prefix)·끝 단어(suffix) 가족. 셋 이상."""
    pre, suf = collections.defaultdict(list), collections.defaultdict(list)
    for n in names:
        w = words(n)
        if len(w) >= 2:
            pre[w[0]].append(n)
            suf[w[-1]].append(n)
    out = []
    for k, v in pre.items():
        if len(v) >= 3 and k not in ("get", "set", "is", "on", "new", "to", "has", "can"):
            out.append(("prefix", k, sorted(v)))
    for k, v in suf.items():
        if len(v) >= 3 and k not in ("of", "at", "to", "by", "for", "in"):
            out.append(("suffix", k, sorted(v)))
    out.sort(key=lambda x: -len(x[2]))
    return out


# ─────────────────────────────── 군집화 ───────────────────────────────

def modularity_cluster(nodes, edges, gamma=1.0):
    """가중 무향 그래프의 탐욕 모듈성 병합(CNM). edges: {(a, b): w}. 공동체 목록(노드 집합)을 돌려준다."""
    if not nodes:
        return []
    adj = collections.defaultdict(lambda: collections.defaultdict(float))
    m2 = 0.0
    for (a, b), w in edges.items():
        if a == b or w <= 0:
            continue
        adj[a][b] += w
        adj[b][a] += w
        m2 += 2 * w
    if m2 == 0:
        return [{n} for n in nodes]
    comm = {n: {n} for n in nodes}
    deg = {n: sum(adj[n].values()) / m2 for n in nodes}  # a_i
    e = {n: {o: w / m2 for o, w in adj[n].items()} for n in nodes}  # e_ij (양방향 각각)
    while True:
        best, pair = 0.0, None
        for i in sorted(e):                     # 정렬해서 돈다 - 같은 값이면 늘 같은 쌍을 고른다(결과가 실행마다 같게)
            for j in sorted(e[i]):
                eij = e[i][j]
                if i < j:
                    dq = 2 * (eij - gamma * deg[i] * deg[j])
                    if dq > best:
                        best, pair = dq, (i, j)
        if not pair:
            break
        i, j = pair
        # j 를 i 로 합친다
        for k, w in e[j].items():
            if k == i:
                continue
            e[i][k] = e[i].get(k, 0.0) + w
            e[k][i] = e[k].get(i, 0.0) + w
            del e[k][j]
        e[i].pop(j, None)
        del e[j]
        deg[i] += deg[j]
        del deg[j]
        comm[i] |= comm.pop(j)
    return list(comm.values())


# ─────────────────────────────── 반복 블록 ───────────────────────────────

def norm_line(l):
    l = l.strip()
    l = re.sub(r"--.*$", "", l).strip()
    l = re.sub(r"\"[^\"]*\"|'[^']*'", '"S"', l)
    l = re.sub(r"\b\d+(\.\d+)?\b", "N", l)
    return l


TRIV = re.compile(r"^(end|else|\}|\)|\},|\),|return|return nil|break|end\)|do|then|\{|\]|continue|)$")


def repeated_blocks(lines, line0, line1, W=3, min_count=3):
    idx = [(i, norm_line(lines[i - 1])) for i in range(line0, line1 + 1)]
    idx = [(i, l) for i, l in idx if l and not TRIV.match(l) and not l.startswith("--")]
    win = collections.defaultdict(list)
    for k in range(len(idx) - W + 1):
        key = "\n".join(l for _, l in idx[k:k + W])
        win[key].append(idx[k][0])
    out = []
    used = set()
    pos = {ln: k for k, (ln, _) in enumerate(idx)}
    for key, at in sorted(win.items(), key=lambda x: (-len(x[1]), x[1][0])):
        if len(at) < min_count:
            break
        if any(a in used for a in at):
            continue
        # 겹치는 창(같은 블록을 한 줄씩 민 것)은 하나로 본다
        for a in at:
            k = pos[a]
            for j in range(max(0, k - W + 1), min(len(idx), k + W)):
                used.add(idx[j][0])
        out.append({"count": len(at), "lines": at[:8], "text": key.split("\n")})
        if len(out) >= 6:
            break
    heads = collections.Counter(l for _, l in idx if re.match(r"^(local|const|if)\b", l) and len(l) > 14)
    rep = [{"count": c, "text": t} for t, c in heads.most_common(5) if c >= 8]
    return out, rep


# ─────────────────────────────── 계획 ───────────────────────────────

# 구획 제목의 흔한 한국어 낱말 -> 파일 이름 후보. 없으면 낱말, 중심 함수로 짓는다(사람이 고칠 후보일 뿐이다)
KO_NAMES = [("내부 헬퍼", "Internal"), ("헬퍼", "Util"), ("계약", "Impl"), ("조회", "Query"), ("unchecked", "Unchecked"),
            ("구멍", "Holes"), ("추가", "Insert"), ("꺼내기", "Remove"), ("복제", "Clone"), ("구간", "Range"),
            ("순서", "Order"), ("정렬", "Sort"), ("스트림", "Stream"), ("묶기", "Group"), ("접기", "Fold"),
            ("생성자", "Ctor"), ("만들기", "Ctor"), ("타입", "Types"), ("저장", "Persist"), ("불러오기", "Persist"),
            ("상태", "State"), ("입력", "Input"), ("끌기", "Drag"), ("그리기", "Render"), ("배치", "Layout"),
            ("검사", "Check"), ("변환", "Convert"), ("집계", "Aggregate"), ("탭", "Tabs"), ("분할", "Split")]


def title_name(title):
    t = re.sub(r"\(.*?\)", "", title).strip()
    for ko, en in KO_NAMES:
        if ko in t:
            return en
    ws = [w for w in re.findall(r"[A-Za-z][A-Za-z0-9]*", t) if w.lower() not in ("the", "a", "an", "of", "and", "header", "headers")]
    return pascal(" ".join(ws[:2])) if ws else None


def pascal(w):
    return "".join(x[:1].upper() + x[1:] for x in re.split(r"[^A-Za-z0-9]+", w) if x)


def plan(path, target=400, maxlines=800, modname=None, scope=None):
    src = open(path, encoding="utf-8", errors="replace").read()
    lines = src.split("\n")
    nlines = len(lines) - (1 if lines and lines[-1] == "" else 0)
    toks = tokenize(src)
    depth, pdepth, match = block_structure(toks)
    module_names = find_module_names(toks, depth, pdepth)
    t0, t1, d, units, scope_path, names = choose_scope(toks, depth, pdepth, match, module_names, nlines, scope)
    closure = bool(scope_path)
    modname = modname or os.path.splitext(os.path.basename(path))[0]
    if modname == "init":
        modname = os.path.basename(os.path.dirname(os.path.abspath(path)))
    exempt = None
    for l in lines[:10]:
        m = EXEMPT.match(l)
        if m:
            exempt = m.group(1).strip()

    # 단위 앞 주석 줄을 그 단위에 붙인다
    prev_end = (toks[t0][2] - 1) if t0 < len(toks) else 0
    for u in units:
        j = u.line0 - 1
        while j > prev_end and lines[j - 1].strip().startswith("--") and not REGION.match(lines[j - 1]) \
                and not ENDREGION.match(lines[j - 1]) and not BANNER.match(lines[j - 1]):
            j -= 1
        u.doc0 = j + 1
        prev_end = u.line1

    # 이름 표
    scope_names = set()
    for u in units:
        if u.kind in ("func", "local", "import", "fwd"):
            scope_names.update(u.names)
    func_by_name = {}
    fwd = {}
    for u in units:
        if u.kind == "func":
            # 같은 이름이면 실제 정의(`function f`-`local function f`)가 자리표시보다 앞선다
            if u.init_kind == "define":
                func_by_name.setdefault(u.name, u)
            else:
                func_by_name[u.name] = u
    locals_ = {}
    for u in units:
        if u.kind == "local":
            for n in u.names:
                locals_[n] = u
    # 전방 선언: 값 없이(또는 빈 함수로) 선언한 지역을 뒤에서 `function name` / `name = function` 으로 정의
    for u in units:
        if u.kind == "func" and u.init_kind == "define" and u.name in locals_:
            fwd[u.name] = {"declared": locals_[u.name].line0, "defined": u.line0}
    # local f: T = function() end 뒤 f = function ... 처럼 자리표시자를 둔 경우도 전방 선언이다
    for u in units:
        if u.kind == "func" and u.init_kind == "func":
            later = [x for x in units if x is not u and x.kind == "func" and x.init_kind == "define" and x.name == u.name]
            if later:
                fwd[u.name] = {"declared": u.line0, "defined": later[0].line0}
                u.kind = "fwd"

    # `local f: T = function() end` ... `f = g` 처럼 다른 함수를 대입해 정의하는 전방 선언
    alias_of = {}
    for u in units:
        if u.kind == "assign" and (u.name in locals_ or any(x.kind in ("func", "fwd") and x.name == u.name for x in units)):
            decl = locals_[u.name].line0 if u.name in locals_ else next(x.line0 for x in units if x.name == u.name)
            fwd[u.name] = {"declared": decl, "defined": u.line0, "alias": u.alias}
            alias_of[u.name] = u.alias
            for x in units:
                if x.kind == "func" and x.name == u.name and x.init_kind == "func":
                    x.kind = "fwd"   # 자리표시 빈 함수는 단위가 아니다
    funcs = [u for u in units if u.kind == "func"]
    consts_guess = {n for n, lu in locals_.items() if lu.init_kind in ("table", "call") and n[:1].isupper()}
    for u in funcs:
        collect_refs(u, toks, scope_names, names,
                     opaque={n for x in units if x.kind == "import" for n in x.names} | set(consts_guess))
    # 반환 표에 든 이름은 공개다
    for u in units:
        if u.kind in ("return", "local"):
            seg = toks[u.t0:u.t1 + 1]
            for a in range(len(seg) - 2):
                if seg[a][0] == "name" and seg[a + 1][1] == "=" and seg[a + 2][0] == "name" \
                        and seg[a - 1][1] in ("{", ",") and seg[a + 2][1] in func_by_name:
                    func_by_name[seg[a + 2][1]].public = True
    # 구획
    secs, sec_kind = sections(lines, toks[t0][2] if t0 < len(toks) else 1, toks[t1 - 1][2] if t1 - 1 < len(toks) else nlines)
    for u in units:
        for s, e, t in secs:
            if s <= u.line0 <= e:
                u.section = t
                break
    secs = sorted(secs)
    sec_span = {t: e - s_ + 1 for s_, e, t in secs}
    # 상태 분류
    state_users = collections.defaultdict(set)
    written = collections.defaultdict(set)
    for u in funcs:
        for r in u.refs:
            if r in locals_:
                state_users[r].add(u.name)
        for w in u.writes:
            if w in locals_:
                written[w].add(u.name)
    state, consts = {}, {}
    for n, lu in locals_.items():
        if n in fwd:
            continue
        users = state_users.get(n, set())
        if n in written or lu.init_kind in ("none", "nil"):
            state[n] = {"line": lu.line0, "users": sorted(users), "writers": sorted(written.get(n, ())),
                        "scalar": lu.init_kind in ("literal", "nil", "none")}  # 숫자, 불리언: 다른 모듈로 가면 값 복사
        else:
            consts[n] = {"line": lu.line0, "users": sorted(users)}

    # ── 그래프 ──
    fnames = [u.name for u in funcs]
    fset = set(fnames)
    calls = collections.Counter()
    callers = collections.defaultdict(set)
    for u in funcs:
        for r, c in u.refs.items():
            if r in fset and r != u.name:
                calls[(u.name, r)] += c
                callers[r].add(u.name)
    nfun = max(1, len(funcs))
    by = {u.name: u for u in funcs}
    # 공용 헬퍼: 작고 상태를 쓰지 않으며 여러 곳(전체 함수의 8% 이상, 최소 5)에서 부르는 것
    hub_min = max(5, int(nfun * 0.08))
    helpers = {n for n in fnames if len(callers[n]) >= hub_min and by[n].lines() <= 40
               and not any(r in state for r in by[n].refs)}
    # 구획이 있으면: 자기 구획 밖의 셋 이상 구획에서 부르는 작은 무상태 함수(생성 헬퍼 newEmpty 같은 것)도 아래층이다.
    # 이런 허브를 군집에 두면 부르는 쪽을 모두 끌어당겨 잡동사니 군집이 생긴다.
    for n in fnames:
        secs_from = {by[x].section for x in callers[n] if by[x].section and by[x].section != by[n].section}
        if len(secs_from) >= 3 and by[n].lines() <= 60 and not any(r in state for r in by[n].refs):
            helpers.add(n)
    # 핵심 상태: 함수의 30% 넘게 쓰는 상태는 군집을 붙이는 신호로 쓰지 않는다
    core_state = {s for s, v in state.items() if len(v["users"]) > max(6, nfun * 0.3)}
    fams = families(fnames)
    word_fam = collections.defaultdict(list)
    for n in fnames:
        for w in sorted(set(words(n))):
            if w not in STOP and len(w) > 2:
                word_fam[w].append(n)
    word_fam = {w: ms for w, ms in word_fam.items() if 3 <= len(ms) <= max(6, nfun * 0.25)}
    fdf = collections.defaultdict(list)
    for u in funcs:
        for f in u.fields:
            fdf[f].append(u.name)
    field_fam = {f: ms for f, ms in fdf.items() if 2 <= len(ms) <= max(4, nfun * 0.12)}

    sec_w = 1.0 if sec_kind == "region" else 0.6   # region 은 작성자가 직접 그은 경계라 더 믿는다

    def build_edges(members):
        mem = set(members)
        E = collections.Counter()
        for (a, b), c in calls.items():
            if a in mem and b in mem and a not in helpers and b not in helpers:
                key = (a, b) if a < b else (b, a)
                E[key] += 1.0 + min(2, c - 1) * 0.25
        for s, v in state.items():
            if s in core_state:
                continue
            us = [x for x in v["users"] if x in mem and x not in helpers]  # users 는 정렬된 목록
            for x in us:
                E[(x, "$" + s) if x < "$" + s else ("$" + s, x)] += 1.0
        # 구획, 가족은 가상 노드로 약하게 묶는다
        for u in funcs:
            if u.name in mem and u.name not in helpers and u.section:
                E[(u.name, "§" + u.section)] += sec_w
        # 이름 낱말 가족(bagOpen, bagTake, spawnBag -> "bag"): 공개 진입점은 서로 부르지 않아서 이것이 주된 신호다
        for w, ms in sorted(word_fam.items()):
            ms = [x for x in ms if x in mem and x not in helpers]
            if len(ms) >= 3:
                for x in ms:
                    E[(x, "~" + w)] += 0.5
        # 같은 필드를 만지는 함수(session.bundles, record.bag): 상태가 매개변수 안에 있는 모듈의 신호
        for f, ms in sorted(field_fam.items()):
            ms = [x for x in ms if x in mem and x not in helpers]
            if len(ms) >= 2:
                for x in ms:
                    E[(x, "." + f)] += 0.3
        # 이웃한 정의는 아주 약하게(나눈 파일이 원래 순서를 지키게)
        order = [u.name for u in funcs if u.name in mem and u.name not in helpers]
        for a, b in zip(order, order[1:]):
            E[(a, b) if a < b else (b, a)] += 0.15
        nodes = set()
        for a, b in E:
            nodes.add(a)
            nodes.add(b)
        for x in mem:
            if x not in helpers:
                nodes.add(x)
        return nodes, E

    def lines_of(ms):
        return sum(by[x].lines() for x in ms if x in by)

    def cluster(members, gamma, depth_=0):
        nodes, E = build_edges(members)
        cs = modularity_cluster(sorted(nodes), E, gamma)
        out = []
        for c in cs:
            fs = [x for x in c if x in by]
            if not fs:
                continue
            if lines_of(fs) > maxlines and depth_ < 4 and len(fs) > 3:
                out += cluster(fs, gamma * 1.6, depth_ + 1)
            else:
                out.append(set(fs))
        return out

    main = [n for n in fnames if n not in helpers]
    clusters = cluster(main, 1.0)
    # 작은 군집(target 의 1/5 미만)은 가장 많이 이어진 군집에 붙인다
    def link(a, b):
        w = 0
        for x in a:
            for y in b:
                w += calls.get((x, y), 0) + calls.get((y, x), 0)
        sa = {s for x in a for s in by[x].refs if s in state and s not in core_state}
        sb = {s for x in b for s in by[x].refs if s in state and s not in core_state}
        return w + len(sa & sb)
    changed = True
    while changed:
        changed = False
        clusters.sort(key=lambda c: (lines_of(c), min(by[x].line0 for x in c)))
        for c in clusters:
            if lines_of(c) >= target * 0.4 or len(clusters) <= 2:
                continue
            others = [o for o in clusters if o is not c]
            best = max(others, key=lambda o: (link(c, o), -lines_of(o), -min(by[x].line0 for x in o)))
            if link(c, best) == 0:
                # 이어진 데가 없으면 같은 구획의 군집, 그것도 없으면 그대로 둔다
                sec = collections.Counter(by[x].section for x in c).most_common(1)[0][0]
                cand = [o for o in others if sec and any(by[x].section == sec for x in o)]
                if not cand:
                    # 그것도 없으면 바로 앞에 정의된 함수의 군집(원래 파일에서 옆에 있던 것)
                    first = min(c, key=lambda x: by[x].line0)
                    before = [u.name for u in funcs if u.line0 < by[first].line0 and u.name not in c]
                    cand = [o for o in others if before and before[-1] in o]
                    if not cand:
                        continue
                best = cand[0]
            if lines_of(best) + lines_of(c) > maxlines:
                continue
            best |= c
            clusters.remove(c)
            changed = True
            break

    # ── 공용 헬퍼 다시 보기 ──
    # 군집을 정한 뒤, 셋 이상의 다른 군집이 부르는 작은 무상태 함수는 공용(Util)으로 올린다.
    # 공용 헬퍼가 군집 함수를 부르면 Util -> 군집 -> Util 순환이 되므로, 그 피호출이 작고 무상태면 같이 올리고 아니면 내린다.
    cid0 = {x: k for k, c in enumerate(clusters) for x in c}
    for n in fnames:
        if n in helpers or n not in cid0:
            continue
        from_cl = {cid0[x] for x in callers[n] if x in cid0 and cid0[x] != cid0[n]}
        if len(from_cl) >= 3 and by[n].lines() <= 60 and not any(r in state for r in by[n].refs):
            helpers.add(n)
    banned = set()
    for _ in range(6):
        for h in sorted(helpers):
            if h not in helpers:
                continue
            for r in by[h].refs:
                if r in by and r not in helpers and r != h:
                    if r not in banned and by[r].lines() <= 60 and not any(x in state for x in by[r].refs):
                        helpers.add(r)
                    else:
                        helpers.discard(h)
                        banned.add(h)
                        break
    clusters = [c - helpers for c in clusters]
    clusters = [c for c in clusters if c]
    # 공용에서 내려온 함수는 가장 많이 부르는 군집으로
    placed = set().union(*clusters) if clusters else set()
    for n in fnames:
        if n in helpers or n in placed:
            continue
        score = [(sum(1 for x in callers[n] if x in c) + sum(1 for r in by[n].refs if r in c), k) for k, c in enumerate(clusters)]
        k = max(score)[1] if score else None
        if k is None:
            clusters.append({n})
        else:
            clusters[k].add(n)

    # ── 군집 정리 ──
    order_line = {u.name: u.line0 for u in funcs}
    clusters = sorted(clusters, key=lambda c: min(order_line[x] for x in c))
    cid = {x: k for k, c in enumerate(clusters) for x in c}
    for h in helpers:
        cid[h] = "H"

    total_w = collections.Counter(w for u in funcs for w in set(words(u.name)) if w not in STOP and len(w) > 2)

    def cover_sc(w, k, c):
        return (k / len(c)) * (k / total_w[w]) * (1 + math.log(1 + k))

    taken = set()

    def name_cluster(c):
        """이름 후보와 근거. 1) 대부분이 한 구획이면 구획 제목 2) 멤버 이름에 많이 나오는 낱말 3) 가장 많이 이어진 함수."""
        secs_ = collections.Counter()
        for x in c:
            secs_[by[x].section] += by[x].lines()
        top_sec, top_sec_lines = secs_.most_common(1)[0] if secs_ else (None, 0)
        sec_share = top_sec_lines / max(1, lines_of(c))
        sec = top_sec if top_sec and sec_share >= 0.5 and sec_span.get(top_sec, 0) <= maxlines * 1.5 else None
        if not closure and any(x in ("new", "New", "init", "Init", "start", "Start") for x in c):
            return "init", sec, "생성자"
        if sec and sec_share >= 0.6 and sec_span.get(sec, 0) <= maxlines:
            nm = title_name(sec)
            if nm and nm not in taken:
                return nm, sec, "구획"
        wc = collections.Counter(w for x in sorted(c) for w in sorted(set(words(x))) if w not in STOP and len(w) > 2)
        ranked = sorted(((cover_sc(w, k, c), w) for w, k in wc.items() if k >= 2 and k / len(c) >= 0.1), reverse=True)
        central = max(sorted(c), key=lambda x: sum(calls.get((x, y), 0) + calls.get((y, x), 0) for y in c))
        for _, w in ranked:
            if pascal(w) not in taken:
                return pascal(w), sec, ("낱말" if wc[w] / len(c) >= 0.3 else "낱말(약함)")
        return pascal(central), sec, "중심 함수(약함)"

    out_clusters = []
    used_names = collections.Counter()
    for k, c in enumerate(clusters):
        nm, sec, why = name_cluster(c)
        used_names[nm] += 1
        if used_names[nm] > 1:
            nm = f"{nm}{used_names[nm]}"
        taken.add(nm)
        ms = sorted(c, key=lambda x: order_line[x])
        st = collections.Counter(s for x in ms for s in by[x].refs if s in state)
        ranges = []
        for x in ms:
            a, b = by[x].doc0, by[x].line1
            if ranges and a <= ranges[-1][1] + 8:
                ranges[-1][1] = max(ranges[-1][1], b)
            else:
                ranges.append([a, b])
        alts = []
        for cand in [pascal(max(ms, key=lambda x: by[x].lines()))] + \
                [pascal(w) for w, _ in sorted(collections.Counter(w for x in ms for w in set(words(x))
                                                                   if w not in STOP and len(w) > 2).items(),
                                              key=lambda kv: (-kv[1], kv[0]))[:3]]:
            if cand != nm and cand not in alts:
                alts.append(cand)
        out_clusters.append({"id": k, "file": nm, "why": why, "alts": alts[:3], "section": sec, "lines": lines_of(ms), "funcs": ms,
                             "public": [x for x in ms if by[x].public], "state": dict(st.most_common()),
                             "ranges": ranges})
    names_by_id = {c["id"]: c["file"] for c in out_clusters}
    names_by_id["H"] = "Core"

    # ── 군집 사이 간선 ──
    cross = collections.Counter()
    cross_syms = collections.defaultdict(set)
    for (a, b), c in calls.items():
        ca, cb = cid.get(a), cid.get(b)
        if ca is None or cb is None or ca == cb:
            continue
        cross[(ca, cb)] += 1
        cross_syms[(ca, cb)].add(b)
    # 강하게 이어진 성분(순환)과, 끊을 간선(되먹임 간선 집합 - Eades 순서에서 거꾸로 가는 간선)
    def eades(nodes):
        """위층(부르는 쪽) → 아래층(불리는 쪽) 순서. 거꾸로 가는 간선이 적게 되도록 고른다(Eades–Lin–Smyth)."""
        rest = set(nodes)
        seq_l, seq_r = [], []
        while rest:
            sinks = [x for x in rest if not any((x, y) in cross for y in rest if y != x)]
            if sinks:
                for x in sorted(sinks, key=str):
                    seq_r.insert(0, x)
                    rest.discard(x)
                continue
            srcs = [x for x in rest if not any((y, x) in cross for y in rest if y != x)]
            if srcs:
                for x in sorted(srcs, key=str):
                    seq_l.append(x)
                    rest.discard(x)
                continue
            x = max(rest, key=lambda v: (sum(cross[(v, y)] for y in rest) - sum(cross[(y, v)] for y in rest), str(v)))
            seq_l.append(x)
            rest.discard(x)
        return seq_l + seq_r

    G = collections.defaultdict(set)
    for (a, b) in cross:
        G[a].add(b)
    sccs = tarjan(list(names_by_id), G)
    cycles = []
    for comp in sccs:
        if len(comp) < 2:
            continue
        seq = eades(comp)
        pos = {x: k for k, x in enumerate(seq)}
        back = [(a, b) for a in comp for b in comp if (a, b) in cross and pos[a] > pos[b]]
        back.sort(key=lambda e: (-cross[e], names_by_id[e[0]], names_by_id[e[1]]))
        cycles.append({"clusters": [names_by_id[x] for x in seq],
                       "cut": [{"from": names_by_id[a], "to": names_by_id[b], "calls": cross[(a, b)],
                                "symbols": sorted(cross_syms[(a, b)])[:6]} for a, b in back],
                       "cut_calls": sum(cross[e] for e in back)})

    cycles.sort(key=lambda c: c["clusters"])

    # ── 상태 배치 ──
    placement = []
    for s, v in sorted(state.items(), key=lambda x: x[1]["line"]):
        cs = sorted({names_by_id[cid[x]] for x in v["users"] if x in cid})
        if not cs:
            where = "(함수에서 안 씀 — 초기화 코드만)"
        elif len(cs) == 1:
            where = cs[0]
        else:
            where = "State"
        placement.append({"name": s, "line": v["line"], "users": len(v["users"]), "clusters": cs, "to": where,
                          "written_by": len(v["writers"]), "core": s in core_state})

    # 전방 선언이 경계를 넘는가
    fwd_out = []
    # 대입으로 정의한 전방 선언의 부르는 쪽: 그 이름을 참조하는 함수
    for u in funcs:
        for r in u.refs:
            if r in alias_of:
                callers[r].add(u.name)
    for n, f in fwd.items():
        home = cid.get(alias_of.get(n, n))
        users = [x for x in callers.get(n, ()) if x in cid]
        other = sorted({names_by_id[cid[x]] for x in users if cid[x] != home})
        fwd_out.append({"name": n, "declared": f["declared"], "defined": f["defined"],
                        "home": names_by_id.get(home, "?"), "used_from": other})

    # ── 옮기기만 순서: 아래층부터(Eades 순서를 뒤집음). 아직 옮기지 않은 군집(위층)의 이름은 늦은 조회로 받는다 ──
    movable = [c["id"] for c in out_clusters if c["file"] != "init"]
    seq_all = eades(movable)
    order = []
    moved = {"H"}
    for x in reversed(seq_all):
        deps = sorted({b for (a, b) in cross if a == x and b != x}, key=str)
        req = [names_by_id[b] for b in deps if b in moved]
        late = [{"to": names_by_id[b], "symbols": sorted(cross_syms[(x, b)])[:6]} for b in deps if b not in moved]
        order.append({"file": names_by_id[x], "requires": req, "late": late})
        moved.add(x)

    reps, heads = repeated_blocks(lines, toks[t0][2] if t0 < len(toks) else 1, toks[t1 - 1][2] if t1 - 1 < len(toks) else nlines)

    types_lines = sum(u.lines() for u in units if u.kind == "type")
    pub_count = sum(1 for u in funcs if u.public)
    return {
        "file": path, "module": modname, "lines": nlines, "exempt": exempt,
        "scope": {"path": scope_path, "closure": bool(scope_path), "line0": toks[t0][2] if t0 < len(toks) else 1,
                  "line1": toks[t1 - 1][2] if t1 - 1 < len(toks) else nlines},
        "counts": {"funcs": len(funcs), "public": pub_count, "types_lines": types_lines,
                   "state": len(state), "consts": len(consts), "imports": sum(1 for u in units if u.kind == "import"),
                   "sections": len(secs), "section_kind": sec_kind},
        "sections": [{"line0": s, "line1": e, "title": t} for s, e, t in secs],
        "families": [{"kind": k, "word": w, "members": m} for k, w, m in fams[:10]],
        "helpers": sorted(helpers, key=lambda x: order_line[x]),
        "helper_lines": lines_of(helpers),
        "clusters": out_clusters,
        "cross": [{"from": names_by_id[a], "to": names_by_id[b], "calls": n, "symbols": sorted(cross_syms[(a, b)])[:8]}
                  for (a, b), n in sorted(cross.items(), key=lambda x: -x[1])],
        "imports_after_split": len(cross),
        "cycles": cycles,
        "forward_decls": fwd_out,
        "state": placement,
        "consts": {k: v["line"] for k, v in consts.items()},
        "order": order,
        "long_funcs": [dict(zip(("inner_funcs", "inner_locals"), inner_counts(toks, depth, match, u)),
                            name=u.name, line0=u.line0, lines=u.lines(), cluster=names_by_id.get(cid.get(u.name), "?"))
                       for u in sorted(funcs, key=lambda u: -u.lines()) if u.lines() >= 150],
        "repeated_blocks": reps,
        "repeated_heads": heads,
    }


def tarjan(nodes, G):
    index, low, on, st, out = {}, {}, set(), [], []
    counter = [0]

    def visit(v):
        index[v] = low[v] = counter[0]
        counter[0] += 1
        st.append(v)
        on.add(v)
        for w in G.get(v, ()):
            if w not in index:
                visit(w)
                low[v] = min(low[v], low[w])
            elif w in on:
                low[v] = min(low[v], index[w])
        if low[v] == index[v]:
            comp = []
            while True:
                w = st.pop()
                on.discard(w)
                comp.append(w)
                if w == v:
                    break
            out.append(comp)

    sys.setrecursionlimit(10000)
    for v in nodes:
        if v not in index:
            visit(v)
    return out


# ─────────────────────────────── 출력 ───────────────────────────────

def compress(names, limit=14):
    return ", ".join(names[:limit]) + (f" … 외 {len(names) - limit}" if len(names) > limit else "")


def show(p):
    M = p["module"]
    c = p["counts"]
    print(f"# 분리 계획: `{p['file']}` ({p['lines']}줄)")
    print()
    if p["exempt"] is not None:
        print(f"> 파일 머리 예외 표식: {p['exempt'] or '(사유 없음 — 무효)'}. 계획은 참고로 낸다.")
        print()
    sc = p["scope"]
    if sc["closure"]:
        print(f"- 분석 범위: **{' → '.join(sc['path'])}** 의 안쪽({sc['line0']}–{sc['line1']}줄). 파일 대부분이 한 함수의 본문이라 "
              f"그 안의 지역 함수와 닫개 상태를 단위로 봤다. 이 상태는 인스턴스마다 따로라서 **모듈 수준 `State.luau` 로 옮길 수 없다** — "
              f"먼저 상태 표(객체)로 꺼내 함수에 넘기는 단계가 필요하다(splitting.md §닫개).")
    else:
        print(f"- 분석 범위: 최상위({sc['line0']}–{sc['line1']}줄)")
    print(f"- 함수 {c['funcs']}개(공개 {c['public']}), 타입 선언 {c['types_lines']}줄, 상태 {c['state']}개, 상수 {c['consts']}개, "
          f"require·서비스 {c['imports']}개, 구획 {c['sections']}개({c['section_kind'] or '없음'})")
    print(f"- 군집 {len(p['clusters'])}개 + 공용 헬퍼 {len(p['helpers'])}개({p['helper_lines']}줄). "
          f"나누면 군집 사이 require {p['imports_after_split']}개, 순환 {len(p['cycles'])}묶음.")
    print()
    print("## 1. 응집 군집 (후보 파일)")
    print()
    print("| 후보 파일 | 줄 | 함수 | 공개 | 원래 구획 | 줄 범위 | 쓰는 상태 |")
    print("|---|---|---|---|---|---|---|")
    for cl in p["clusters"]:
        rg = ", ".join(f"{a}–{b}" for a, b in cl["ranges"][:4]) + (" …" if len(cl["ranges"]) > 4 else "")
        st = ", ".join(list(cl["state"])[:5]) + (" …" if len(cl["state"]) > 5 else "")
        print(f"| `{M}/{cl['file']}.luau` | {cl['lines']} | {len(cl['funcs'])} | {len(cl['public'])} | "
              f"{cl['section'] or '-'} | {rg} | {st or '-'} |")
    if p["helpers"]:
        print(f"| `{M}/Core.luau` (공용 아래층) | {p['helper_lines']} | {len(p['helpers'])} | - | - | - | - |")
    print()
    for cl in p["clusters"]:
        alt = f"; 다른 후보 {', '.join(cl['alts'])}" if cl["alts"] and "약함" in cl["why"] else ""
        print(f"- **{cl['file']}** (이름 근거: {cl['why']}{alt}): {compress(cl['funcs'])}")
    if p["helpers"]:
        print(f"- **Core**(셋 이상의 군집이 부르는 작은 무상태 함수 — 다른 파일들이 require 하는 아래층. init 에 두면 순환이 된다): {compress(p['helpers'])}")
    print()
    print("## 2. 군집 사이 간선 (나눈 뒤의 require)")
    print()
    if p["cross"]:
        print("| 부르는 쪽 → 불리는 쪽 | 호출 쌍 | 넘는 이름 |")
        print("|---|---|---|")
        for e in p["cross"][:20]:
            print(f"| {e['from']} → {e['to']} | {e['calls']} | {compress(e['symbols'], 6)} |")
        if len(p["cross"]) > 20:
            print(f"| … 외 {len(p['cross']) - 20} | | |")
    else:
        print("- 없음")
    print()
    print("## 3. 순환 위험")
    print()
    if not p["cycles"]:
        print("- 없음. 군집 사이 호출이 한 방향이다.")
    for cy in p["cycles"]:
        print(f"- 서로 부르는 군집 {len(cy['clusters'])}개. 위층 → 아래층 순서 제안: {' → '.join(cy['clusters'])}")
        print(f"  - 이 순서를 거스르는 간선 {len(cy['cut'])}개(호출 쌍 {cy['cut_calls']})만 끊으면 순환이 없다:")
        for x in cy["cut"][:8]:
            print(f"    - {x['from']} → {x['to']} {x['calls']}쌍: {', '.join(x['symbols'])}")
        if len(cy["cut"]) > 8:
            print(f"    - … 외 {len(cy['cut']) - 8}")
        print("  - 끊는 법: 그 이름을 부르는 쪽 군집으로 옮기기(작으면) → 내부 표 늦은 조회(`S.f(...)`, splitting.md §3) → "
              "인자로 넘기기(콜백 주입) 순으로 본다.")
    print()
    print("## 4. 전방 선언")
    print()
    if not p["forward_decls"]:
        print("- 없음")
    for f in p["forward_decls"]:
        tail = (f"다른 군집({', '.join(f['used_from'])})이 부른다 → 파일 경계를 넘으므로 늦은 조회 표로 바꿔야 한다"
                if f["used_from"] else "같은 군집 안에서만 쓴다 → 그 파일 안에 그대로 둘 수 있다")
        print(f"- `{f['name']}`: 선언 {f['declared']}줄, 정의 {f['defined']}줄, 정의는 {f['home']} — {tail}")
    print()
    print("## 5. 공유 상태를 어디로")
    print()
    shared = [s for s in p["state"] if s["to"] == "State"]
    single = [s for s in p["state"] if s["to"] not in ("State",) and not s["to"].startswith("(")]
    unused = [s for s in p["state"] if s["to"].startswith("(")]
    if shared:
        holder = "상태 표(인스턴스마다 하나, 함수에 넘김)" if p["scope"]["closure"] else f"`{M}/State.luau` (`State.이름` 으로 읽고 씀)"
        print(f"- 여러 군집이 쓰는 것 → {holder}:")
        for s in shared:
            print(f"  - `{s['name']}` ({s['line']}줄) — 함수 {s['users']}개, 쓰는 함수 {s['written_by']}개, 군집 {', '.join(s['clusters'])}"
                  + (" [핵심 상태]" if s["core"] else ""))
        print("  - 숫자·불리언 상태를 다른 모듈이 다시 대입하면 사본이 갈라진다. 표의 필드로 옮겨 `State.x = …` 로 쓴다.")
    if single:
        print("- 한 군집만 쓰는 것 → 그 파일로 같이 옮김: " + ", ".join(f"`{s['name']}`→{s['to']}" for s in single))
    if unused:
        print("- 함수에서 안 쓰는 것(초기화 코드에서만): " + ", ".join(f"`{s['name']}`" for s in unused))
    if not p["state"]:
        print("- 없음 (상태 없는 모듈 — 옮기기만으로 나눌 수 있다)")
    print()
    print("## 6. \"옮기기만\" 커밋 순서")
    print()
    step = 1
    if p["scope"]["closure"]:
        print(f"{step}. **(다시 짜기)** 닫개 상태를 상태 표로 꺼낸다. 지역 함수가 `ctx` 를 받게 바꾼다. 이 커밋은 옮기기가 아니다 — "
              f"동작 diff 0 을 테스트로 확인한다. 이 단계를 건너뛰면 분리가 멈춘다(실제 사례의 교훈).")
        step += 1
    print(f"{step}. `{M}.luau` → `{M}/init.luau` 로 접는다(바깥 require 경로 그대로).")
    step += 1
    if p["counts"]["types_lines"] >= 60:
        print(f"{step}. 타입 선언({p['counts']['types_lines']}줄)을 `{M}/Types.luau` 로 옮기고 init 이 재수출한다(`export type X = Types.X`).")
        step += 1
    if shared and not p["scope"]["closure"]:
        print(f"{step}. 공유 상태 {len(shared)}개를 `{M}/State.luau` 로 옮긴다.")
        step += 1
    if p["helpers"]:
        print(f"{step}. 공용 아래층 함수 {len(p['helpers'])}개를 `{M}/Core.luau` 로 옮긴다(init 이 아니라 여기를 다른 조각이 require 한다).")
        step += 1
    for f in p["forward_decls"]:
        if f["used_from"]:
            print(f"{step}. 경계를 넘는 전방 선언(`{'`, `'.join(x['name'] for x in p['forward_decls'] if x['used_from'])}`)을 내부 표 늦은 조회로 바꾼다.")
            step += 1
            break
    for o in p["order"]:
        name = o["file"]
        cl = next(x for x in p["clusters"] if x["file"] == name)
        print(f"{step}. 옮기기만: **{name}** ({cl['lines']}줄, 함수 {len(cl['funcs'])}) → `{M}/{name}.luau`"
              + (f". require: {', '.join(o['requires'])}" if o["requires"] else "")
              + (f". init 이 공개 {len(cl['public'])}개를 재수출" if cl["public"] else ""))
        if o["late"]:
            print("   - 아직 위층에 있는 이름은 늦은 조회로 받는다: "
                  + "; ".join(f"{l['to']}.{', '.join(l['symbols'])}" for l in o["late"]))
        step += 1
    print(f"{step}. 이음매 감사(옮긴 상태가 값으로 묶였나, 정리 누락, 순서)와 문서의 옛 `파일:줄` 갱신.")
    print()
    if p["long_funcs"]:
        print("## 7. 긴 함수 (파일을 나눠도 남는 덩어리 — 본문을 단계별 함수로)")
        print()
        for f in p["long_funcs"][:8]:
            lump = ""
            if f["inner_funcs"] >= 5:
                lump = (f" — **닫개 덩어리**: 안쪽 함수 {f['inner_funcs']}개가 지역 {f['inner_locals']}개를 같이 쥔다. "
                        f"상태 표로 먼저 꺼내야 옮기기만으로 나눌 수 있다. 안쪽 계획: `--scope {f['name']}`")
            print(f"- `{f['name']}` {f['lines']}줄 ({f['line0']}줄~, {f['cluster']}){lump}")
        print()
    print("## 8. 반복 블록 (고치기 커밋 후보 — 옮긴 뒤에)")
    print()
    if not p["repeated_blocks"] and not p["repeated_heads"]:
        print("- 없음")
    for r in p["repeated_blocks"]:
        print(f"- {r['count']}회 ({', '.join(map(str, r['lines'][:6]))}{' …' if r['count'] > 6 else ''}줄): `" + " ⏎ ".join(r["text"])[:160] + "`")
    for r in p["repeated_heads"]:
        print(f"- 같은 머리 줄 {r['count']}회: `{r['text'][:120]}`")
    print()
    print("## 9. 참고: 이름 가족과 구획")
    print()
    for f in p["families"][:8]:
        print(f"- {'접두' if f['kind'] == 'prefix' else '접미'} `{f['word']}` {len(f['members'])}개: {compress(f['members'], 8)}")
    if p["sections"]:
        print(f"- 구획 {len(p['sections'])}개: " + "; ".join(f"{s['title']}({s['line0']}–{s['line1']})" for s in p["sections"][:16])
              + (" …" if len(p["sections"]) > 16 else ""))
    print()


def main():
    ap = argparse.ArgumentParser(description="큰 .luau 파일의 분리 계획(읽기 전용)")
    ap.add_argument("file")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--target", type=int, default=400, help="군집 한 파일의 목표 줄 수(작은 군집 병합 기준)")
    ap.add_argument("--max", type=int, default=800, help="이보다 큰 군집은 더 잘게 나눈다")
    ap.add_argument("--name", help="모듈 이름(기본: 파일 이름)")
    ap.add_argument("--scope", help="이 이름의 함수 본문 안을 분석한다(닫개 덩어리 — 예: --scope enter)")
    a = ap.parse_args()
    p = plan(a.file, a.target, a.max, a.name, a.scope)
    if a.json:
        json.dump(p, sys.stdout, ensure_ascii=False, indent=1)
        print()
    else:
        show(p)


if __name__ == "__main__":
    main()
