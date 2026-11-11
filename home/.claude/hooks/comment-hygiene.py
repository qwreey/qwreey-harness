#!/usr/bin/env python3
"""PostToolUse(Write|Edit|MultiEdit) 알림: 이번에 추가한 주석 줄에 작업 이력(원장 번호·날짜·라운드·세션/감사 경로·결정 문구)이 있으면 알린다.

막지 않는다(decision 없음). additionalContext(level=info)만 주입한다.

왜: quad 에서 설계 시각·원장 번호(H-973, Q188)·감사 라운드·.claude/ 경로가 주석에 쌓여 주석을 갈아엎어야 했다(2026-11-11 사용자).
규약(rules/comments.md): 주석은 코드가 지금 왜 이런가만 쓴다. 이력은 커밋 메시지·CHANGELOG·원장 문서로 보낸다.
추적이 필요하면 이유 문장 뒤에 `Ref: <날짜> <원장> <문서 §>` 꼬리 한 줄만 붙인다. 번호는 지우지 않는다.

보는 것: 이번에 추가된 줄만. Edit/MultiEdit 는 new_string 에서 old_string 에 없던 줄, Write 는 새 파일이면 전체, 덮어쓰기면
  tool_response.originalFile 과의 차이(없으면 structuredPatch 의 + 줄, 둘 다 없으면 보지 않는다 — 옛 줄을 새로 오인하지 않으려고).
그중 주석 줄만. 파일 전체를 확장자별 간이 렉서로 읽어(문자열 리터럴 안의 `--`·`//`·`#` 는 주석이 아니다) 줄마다 주석 조각을 얻는다.
  주석 문법: `--`·`--[[ ]]`(luau/lua), `//`·`/* */`(c 계열), `#`(py·sh), `<!-- -->`(html·astro).
탐지(저장소가 덮어쓸 수 있다): ledger `\\b[A-Z]{1,2}-?\\d{2,4}\\b`, date, round, path(.claude/ session/ audit/), decision("사용자 결정", "per user" 등).
허용: 줄이 `Ref:` 꼬리이고 같은 주석 덩어리(이어진 주석 줄)에 이유 문장(단어 3개 이상, 탐지 토큰 제외)이 있으면 통과.
  `---` 문서 주석 안의 번호는 통과가 아니다. Ref 줄은 문서 블록 위에 두면 같은 덩어리라 통과한다.
제외: 확장자 표 밖, 마크다운, 생성 파일(머리 6줄 표시), 픽스처·testdata·node_modules 등, 설정의 exclude.

저장소 설정: <프로젝트>/.claude/comments.json —
  {"allow_ref_tail": true, "public_ids": ["Quad\\\\d{4}"], "exclude": ["docs/**", "*.md"],
   "patterns": {"ledger": "<정규식>", "date": null}, "min_reason_words": 3}
  public_ids: 줄에서 먼저 지우고 검사하는 공개 식별자 정규식(내장 목록에 더한다). patterns: 이름별로 덮어쓰기, null 이면 끈다.
끄기: 환경 변수 COMMENT_HYGIENE=off
알림 중복: 같은 파일은 (session_id, 호출한 쪽, compact 회차)당 한 번. lib/compact_epoch.py 의 state_path 를 쓴다.
상태 파일: $TMPDIR/claude-comment-hygiene/<session_id>.c<회차>[.a<agent_id>].json
"""
import fnmatch
import importlib.util
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

NS = "claude-comment-hygiene"
REF = "~/.claude/rules/comments.md"
MAX_BYTES = 1_000_000

# 확장자 -> 렉서 계열
FAMILY = {".luau": "lua", ".lua": "lua", ".ts": "c", ".tsx": "c", ".js": "c", ".jsx": "c", ".mjs": "c", ".rs": "rust", ".go": "c", ".kt": "c",
          ".astro": "astro", ".py": "py", ".sh": "py", ".html": "html", ".htm": "html"}
SKIP_PARTS = {"node_modules", ".git", "luau_packages", "roblox_packages", "lune_packages", "Packages", "vendor", "third_party",
              "build", "dist", "refs", "typedefs", "testdata", "fixtures", "__snapshots__", "snapshots", "__pycache__", ".venv", "venv", "target"}
SKIP_SUFFIX = (".d.luau", ".d.ts", ".d.mts", ".min.js", ".gen.ts", ".pb.go", "_pb2.py", "_pb2_grpc.py")
GEN_MARK = re.compile(r"generated|do not edit|@generated|손으로 고치지 않는다|만든 것:", re.I)

PATTERNS = {
    "ledger": r"\b[A-Z]{1,2}-?\d{2,4}\b",
    "date": r"\b20\d\d-\d\d-\d\d\b",
    "round": r"\bround\s*\d+\b|라운드\s*\d+|감사\s*\d+\s*차",
    "path": r"\.claude/|\bsession/|\baudit/",
    "decision": r"사용자\s*(?:결정|지시|요청|합의|말)|\bper (?:the )?user\b|\bas (?:the user )?(?:discussed|decided|agreed)\b|\bthe user (?:decided|asked|wanted|requested)\b",
}
LABEL = {"ledger": "ledger id", "date": "date", "round": "round", "path": "work-history path", "decision": "decision phrase"}
# 내장 공개 식별자·표준 번호: 줄에서 먼저 지운 뒤 검사한다. 저장소 public_ids 는 여기에 더한다.
BUILTIN_PUBLIC = [r"error-code:\s*\S+", r"\bR(?:6|15)\b", r"\bES\d{4}\b", r"\bH26[45]\b", r"\bUTF-?\d+\b", r"\bSHA-?\d+\b", r"\bP\d{2,3}\b(?=\s*(?:p|fps|hz))",
                  r"\b[A-Z]{1,2}\d{2,4}(?=px|pt|ms|hz|fps|kb|mb|gb)"]
REF_LINE = re.compile(r"^\s*Ref\s*:", re.I)
WORD = re.compile(r"[A-Za-zÀ-ɏ]{2,}|[가-힣]{2,}")
DEFAULTS = {"allow_ref_tail": True, "public_ids": [], "exclude": [], "patterns": {}, "min_reason_words": 3}


# ---------- 간이 렉서 ----------

def lex(text, fam):
    """줄마다 {"c": [주석 조각 문자열...], "code": 코드나 문자열이 있는가} 를 돌려준다. 주석은 줄 전체나 일부일 수 있다."""
    lines = text.split("\n")
    out = []
    state = None  # None | ("block", close) | ("str", close)
    for s in lines:
        row = {"c": [], "code": False}
        pos, n = 0, len(s)
        while pos < n:
            if state and state[0] == "block":
                j = s.find(state[1], pos)
                if j < 0:
                    row["c"].append(s[pos:])
                    pos = n
                else:
                    row["c"].append(s[pos:j])
                    pos = j + len(state[1])
                    state = None
                continue
            if state and state[0] == "str":
                row["code"] = True
                j = find_close(s, pos, state[1])
                if j < 0:
                    pos = n
                else:
                    pos = j + len(state[1])
                    state = None
                continue
            ch = s[pos]
            if ch in " \t\r":
                pos += 1
                continue
            r = open_comment_or_string(s, pos, fam)
            if r is None:
                row["code"] = True
                pos += 1
                continue
            kind, a, b = r  # kind: line|block|str|strline, a: 닫는 표식(또는 None), b: 여는 표식 길이
            if kind == "line":
                row["c"].append(s[pos + b:])
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
    """pos 에서 주석·문자열이 시작하면 (kind, 닫는 표식, 여는 표식 길이). 아니면 None."""
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


# ---------- 설정·경로 ----------

def project_root(path, data):
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    if env and path.startswith(env.rstrip("/") + "/"):
        return env
    d = os.path.dirname(path)
    while d and d != "/":
        if os.path.exists(os.path.join(d, ".git")) or os.path.isdir(os.path.join(d, ".claude")):
            return d
        d = os.path.dirname(d)
    return data.get("cwd") or os.path.dirname(path)


def load_cfg(root):
    cfg = {k: (dict(v) if isinstance(v, dict) else list(v) if isinstance(v, list) else v) for k, v in DEFAULTS.items()}
    try:
        user = json.load(open(os.path.join(root, ".claude", "comments.json")))
        if isinstance(user, dict):
            cfg.update(user)
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
    """rows: lex 결과, added: 추가된 줄 번호(0 기반) 집합. [(줄 번호(1 기반), 설명)] 를 돌려준다."""
    # 주석 덩어리: 코드 없이 주석만 있는 줄이 이어진 것. 코드와 한 줄에 있는 주석은 줄마다 따로.
    segs = [" ".join(comment_body(c) for c in r["c"]) if r["c"] else None for r in rows]
    standalone = [bool(r["c"]) and not r["code"] for r in rows]
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
            is_ref = bool(REF_LINE.match(body))
            if is_ref and cfg.get("allow_ref_tail", True):
                if has_reason:
                    continue
                problems.append((k + 1, "`Ref:` tail without a reason sentence in the same comment"))
                continue
            hits, _ = scan(body, pats, pub)
            if hits:
                seen = []
                for kind, tok in hits:
                    d = f"{LABEL.get(kind, kind)} `{tok[:24]}`"
                    if d not in seen:
                        seen.append(d)
                problems.append((k + 1, ", ".join(seen[:3])))
    return problems


def added_set(old, new, base_line):
    """new(여러 줄 문자열)의 줄 중 old 에 없던 줄의 파일 줄 번호(0 기반)."""
    have = Counter(l.strip() for l in old.split("\n")) if old else Counter()
    res = set()
    for idx, l in enumerate(new.split("\n")):
        t = l.strip()
        if not t:
            continue
        if have[t] > 0:
            have[t] -= 1
        else:
            res.add(base_line + idx)
    return res


def patch_added(sp):
    """tool_response.structuredPatch(훈크 목록)에서 새 파일 기준 추가 줄 번호(0 기반)."""
    res = set()
    for h in sp or []:
        try:
            cur = int(h["newStart"]) - 1
            for l in h.get("lines") or []:
                if l.startswith("+"):
                    res.add(cur)
                    cur += 1
                elif l.startswith("-"):
                    continue
                else:
                    cur += 1
        except (KeyError, TypeError, ValueError):
            return None
    return res


def locate(text, new_string):
    """text 안에서 new_string 이 시작하는 줄 번호(0 기반). 없으면 None."""
    if not new_string:
        return None
    k = text.find(new_string)
    return None if k < 0 else text.count("\n", 0, k)


def collect(tool, ti, resp, text):
    """(검사할 텍스트, 추가 줄 번호 집합) 또는 None. 텍스트는 가능하면 파일 전체."""
    if tool == "Write":
        content = ti.get("content")
        if not isinstance(content, str):
            return None
        t = resp.get("type")
        orig = resp.get("originalFile")
        if t == "create":
            return content, added_set("", content, 0)
        if isinstance(orig, str):
            return content, added_set(orig, content, 0)
        sp = patch_added(resp.get("structuredPatch"))
        return (content, sp) if sp is not None else None
    edits = [ti] if tool == "Edit" else [e for e in (ti.get("edits") or []) if isinstance(e, dict)]
    if text is None:
        return None
    added = set()
    for e in edits:
        new, old = e.get("new_string"), e.get("old_string") or ""
        if not isinstance(new, str) or not new:
            continue
        base = locate(text, new)
        if base is None:
            continue
        added |= added_set(old, new, base)
    return text, added


def dedup_path(sid, agent_id):
    try:
        spec = importlib.util.spec_from_file_location("compact_epoch", Path(__file__).resolve().parent.parent / "lib" / "compact_epoch.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.state_path(NS, sid, agent_id)
    except Exception:
        import tempfile
        d = os.path.join(tempfile.gettempdir(), NS)
        os.makedirs(d, exist_ok=True)
        who = ".a" + re.sub(r"[^\w-]", "", str(agent_id)) if agent_id else ""
        return os.path.join(d, re.sub(r"[^\w-]", "", str(sid or "nosession")) + who + ".json")


def main():
    if os.environ.get("COMMENT_HYGIENE", "").lower() == "off":
        return 0
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0
    tool = data.get("tool_name") or ""
    if tool not in ("Write", "Edit", "MultiEdit"):
        return 0
    ti = data.get("tool_input") or {}
    path = ti.get("file_path") or ""
    ext = os.path.splitext(path)[1].lower()
    fam = FAMILY.get(ext)
    if not path or not fam:
        return 0
    resp = data.get("tool_response") if isinstance(data.get("tool_response"), dict) else {}
    root = project_root(path, data)
    cfg = load_cfg(root)
    rel = os.path.relpath(path, root)
    if excluded(path, rel, cfg):
        return 0
    try:
        text = Path(path).read_text(encoding="utf-8") if os.path.getsize(path) <= MAX_BYTES else None
    except (OSError, UnicodeDecodeError):
        text = None
    got = collect(tool, ti, resp, text)
    if not got:
        return 0
    text, added = got
    if not added or any(GEN_MARK.search(l) for l in text.split("\n", 6)[:6]):
        return 0
    pats, pub = compile_patterns(cfg)
    problems = check_lines(lex(text, fam), added, pats, pub, cfg)
    if not problems:
        return 0

    state_path = dedup_path(data.get("session_id"), data.get("agent_id"))
    try:
        state = json.load(open(state_path))
    except Exception:
        state = {}
    key = os.path.abspath(path)
    if key in state.get("files", {}):
        return 0
    state.setdefault("files", {})[key] = len(problems)
    try:
        json.dump(state, open(state_path, "w"))
    except OSError:
        pass

    shown = "; ".join(f"L{ln} {why}" for ln, why in problems[:5])
    more = f" (+{len(problems) - 5} more)" if len(problems) > 5 else ""
    body = (f"Comment lines you added in `{rel}` carry work history: {shown}{more}. "
            f"A comment says why the code is this way now; history goes to the commit message, CHANGELOG, or ledger doc. "
            f"If the repo tracks ledgers, keep the reason sentence and move the number to one `Ref: <date> <ledger> <doc section>` tail line. "
            f"Do not delete numbers and do not rewrite old comments in bulk; fix only lines you touch. Rules: {REF}.")
    json.dump({"hookSpecificOutput": {"hookEventName": "PostToolUse",
                                      "additionalContext": f'<harness-hook name="comment-hygiene" level="info">\n{body}\n</harness-hook>'}},
              sys.stdout, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
