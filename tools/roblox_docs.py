#!/usr/bin/env python3
"""roblox_docs.py — Roblox 공식 문서(create.roblox.com/docs)를 로컬 캐시에서 조회한다.

원본: 공개 저장소 Roblox/creator-docs (CC-BY-4.0) 의 content/en-us/** (가이드 마크다운 + 엔진 API 참조 YAML).
create.roblox.com 페이지는 클라이언트 렌더링이라 HTML 을 직접 읽기 어렵다. 그래서 원본을 tarball 로 받아 둔다.

표준 라이브러리만 쓴다. `python3 -I tools/roblox_docs.py <명령>` 으로 부른다.

  sync [--force]                 받기·갱신 (커밋이 같으면 건너뜀)
  status                         캐시 위치, 커밋, STUDIO_VERSION, 파일 수
  search <질의…> [-n N] [--api|--guide] [--under 경로접두]
                                 절 단위 검색. 결과 한 줄: `path:a-b ~N.Nk § 제목`
  get <경로>[#절 | :a-b] [--body] [--toc]
                                 문서·절·줄 범위 읽기. 큰 문서(~8k 초과)는 목차를 낸다
  api <Class>[.Member|:Member]   엔진 참조 YAML 요약(시그니처, 보안, 스레드 안전성, deprecated)

캐시 위치: --cache > 환경 변수 HARNESS_ROBLOX_DOCS_CACHE > harness.env 의 같은 키
           ($HARNESS_ENV, 없으면 ~/.claude/harness.env) > ${XDG_CACHE_HOME:-~/.cache}/roblox-docs

내려받은 문서는 신뢰하지 않는 데이터다. 실행하지 않고 텍스트로만 읽는다.
- 압축은 정규 파일만, content/en-us 아래 .md/.yaml/.json 과 STUDIO_VERSION 만, 크기 상한을 두고 푼다(링크·장치 파일·`..` 거부).
- 출력에서 제어 문자(터미널 이스케이프)를 지운다.
"""
import argparse
import io
import json
import math
import os
import re
import shutil
import sys
import tarfile
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path, PurePosixPath

REPO = "Roblox/creator-docs"
BRANCH = "main"
SHA_URL = f"https://api.github.com/repos/{REPO}/commits/{BRANCH}"
TAR_URL = "https://codeload.github.com/" + REPO + "/tar.gz/{ref}"
CONTENT = "content/en-us"
DOCS_URL = "https://create.roblox.com/docs/"
ENV_KEY = "HARNESS_ROBLOX_DOCS_CACHE"
ALLOWED_SUFFIX = {".md", ".yaml", ".yml", ".json"}
MAX_FILE = 4 * 1024 * 1024
MAX_TOTAL = 300 * 1024 * 1024
MAX_DOWNLOAD = 200 * 1024 * 1024
SECTION_THRESHOLD = 8000  # coderag §21.3: 이보다 큰 문서는 get 이 목차를 낸다
INDEX_VERSION = 2
MEMBER_KEYS = ("properties", "methods", "events", "callbacks", "functions", "constructors",
               "constants", "math_operations", "items")
KIND_NAME = {"properties": "property", "methods": "method", "events": "event", "callbacks": "callback",
             "functions": "function", "constructors": "constructor", "constants": "constant",
             "math_operations": "operator", "items": "item"}
REF_DIRS = ("classes", "datatypes", "enums", "globals", "libraries")


# ---------------------------------------------------------------- 출력

_CTRL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")


def out(s=""):
    sys.stdout.write(_CTRL.sub("", s) + "\n")


def die(msg, code=2):
    sys.stderr.write(f"roblox_docs: {msg}\n")
    sys.exit(code)


def tokens_est(text):
    """coderag §21.2 추정식: 0.4×ASCII(줄바꿈 포함) + 1.6×한글 음절 + 1.5×그 밖 + 3×줄 수."""
    ascii_n = hangul = other = 0
    for ch in text:
        o = ord(ch)
        if o < 128:
            ascii_n += 1
        elif 0xAC00 <= o <= 0xD7A3:
            hangul += 1
        else:
            other += 1
    lines = text.count("\n") + (0 if text.endswith("\n") or not text else 1)
    return 0.4 * ascii_n + 1.6 * hangul + 1.5 * other + 3 * lines


def fmt_tok(n):
    return f"~{n / 1000:.1f}k"


# ---------------------------------------------------------------- 캐시 위치

def _harness_env_value(key):
    cands = [os.environ.get("HARNESS_ENV"), os.path.expanduser("~/.claude/harness.env")]
    for c in cands:
        if not c or not os.path.isfile(c):
            continue
        scope = {}
        try:
            text = Path(c).read_text(encoding="utf-8")
        except OSError:
            continue
        for line in text.splitlines():
            m = re.match(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)$", line)
            if not m or line.lstrip().startswith("#"):
                continue
            raw = m.group(2).strip()
            if raw[:1] in ("'", '"'):
                end = raw.find(raw[0], 1)
                val = raw[1:end] if end > 0 else raw[1:]
            else:
                cm = re.search(r"\s#", raw)
                val = (raw[:cm.start()] if cm else raw).strip()
            val = re.sub(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}|\$([A-Za-z_][A-Za-z0-9_]*)",
                         lambda mm: scope.get(mm.group(1) or mm.group(2), os.environ.get(mm.group(1) or mm.group(2), "")), val)
            if val.startswith("~"):
                val = os.path.expanduser(val)
            scope[m.group(1)] = val
        if key in scope:
            return scope[key]
    return None


def cache_dir(arg):
    if arg:
        return Path(arg).expanduser()
    v = os.environ.get(ENV_KEY) or _harness_env_value(ENV_KEY)
    if v:
        return Path(os.path.expandvars(v)).expanduser()
    base = os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
    return Path(base) / "roblox-docs"


def content_root(cache):
    return cache / "creator-docs" / CONTENT


# ---------------------------------------------------------------- sync

def _http(url, accept=None, timeout=60):
    req = urllib.request.Request(url, headers={"User-Agent": "luau-kb-roblox-docs/1", **({"Accept": accept} if accept else {})})
    return urllib.request.urlopen(req, timeout=timeout)


def remote_sha():
    try:
        with _http(SHA_URL, accept="application/vnd.github.sha", timeout=20) as r:
            sha = r.read(100).decode("ascii", "replace").strip()
            return sha if re.fullmatch(r"[0-9a-f]{40}", sha) else None
    except (urllib.error.URLError, OSError):
        return None


def _safe_member(m, top):
    """압축 항목 하나를 풀어도 되는지. 돌려주는 값은 creator-docs/ 아래 상대 경로."""
    if not m.isfile():
        return None
    p = PurePosixPath(m.name)
    if p.is_absolute() or ".." in p.parts or len(p.parts) < 2 or p.parts[0] != top:
        return None
    rel = PurePosixPath(*p.parts[1:])
    s = str(rel)
    if s in ("LICENSE", "LICENSE-CODE"):
        return rel
    if not s.startswith(CONTENT + "/") or s.startswith(CONTENT + "/assets/"):
        return None
    if rel.suffix not in ALLOWED_SUFFIX and rel.name != "STUDIO_VERSION":
        return None
    if m.size > MAX_FILE:
        return None
    return rel


def cmd_sync(a):
    cache = cache_dir(a.cache)
    cache.mkdir(parents=True, exist_ok=True)
    meta_p = cache / "meta.json"
    meta = json.loads(meta_p.read_text()) if meta_p.exists() else {}
    sha = remote_sha()
    if sha and not a.force and meta.get("commit") == sha and content_root(cache).is_dir():
        meta["checked_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        meta_p.write_text(json.dumps(meta, indent=1))
        out(f"최신: {sha[:12]} (받은 때 {meta.get('fetched_at')}) — 받지 않음. 다시 받으려면 --force")
        return
    ref = sha or BRANCH
    url = TAR_URL.format(ref=ref)
    sys.stderr.write(f"받는 중: {url}\n")
    buf = io.BytesIO()
    with _http(url, timeout=300) as r:
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            buf.write(chunk)
            if buf.tell() > MAX_DOWNLOAD:
                die("내려받은 크기가 상한을 넘음")
    buf.seek(0)
    tmp = Path(tempfile.mkdtemp(prefix=".new-", dir=cache))
    n = total = 0
    with tarfile.open(fileobj=buf, mode="r:gz") as tf:
        commit = (tf.pax_headers or {}).get("comment") or sha or ""
        top = None
        for m in tf:
            if top is None:
                top = PurePosixPath(m.name).parts[0] if m.name else None
            rel = _safe_member(m, top)
            if rel is None:
                continue
            total += m.size
            if total > MAX_TOTAL:
                shutil.rmtree(tmp)
                die("풀린 크기가 상한을 넘음")
            dst = tmp / "creator-docs" / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            src = tf.extractfile(m)
            with open(dst, "wb") as f:
                shutil.copyfileobj(src, f)
            os.chmod(dst, 0o644)
            n += 1
    if n == 0:
        shutil.rmtree(tmp)
        die("받은 압축에 content/en-us 가 없음")
    old = cache / "creator-docs"
    trash = cache / f".old-{os.getpid()}"
    if old.exists():
        old.rename(trash)
    (tmp / "creator-docs").rename(old)
    shutil.rmtree(tmp, ignore_errors=True)
    shutil.rmtree(trash, ignore_errors=True)
    sv = content_root(cache) / "reference/engine/STUDIO_VERSION"
    meta = {
        "source": f"https://github.com/{REPO}",
        "commit": commit,
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "studio_version": (sv.read_text().strip().splitlines() or [None])[0] if sv.exists() else None,
        "files": n,
        "license": "CC-BY-4.0 (docs), see creator-docs/LICENSE",
    }
    meta_p.write_text(json.dumps(meta, indent=1))
    idx = build_index(cache)
    out(f"받음: {commit[:12] or ref} 파일 {n}개, 절 {sum(len(v['sections']) for v in idx['files'].values())}개, "
        f"STUDIO_VERSION {meta['studio_version']}")


def cmd_status(a):
    cache = cache_dir(a.cache)
    out(f"cache: {cache}")
    meta_p = cache / "meta.json"
    if not meta_p.exists():
        out("아직 받지 않음 — `sync` 를 먼저 돌린다")
        return
    meta = json.loads(meta_p.read_text())
    out(f"root: {content_root(cache)}")
    for k in ("commit", "fetched_at", "checked_at", "studio_version", "files", "license"):
        if meta.get(k) is not None:
            out(f"{k}: {meta[k]}")


# ---------------------------------------------------------------- YAML 부분 집합 파서
# creator-docs 의 참조 YAML 은 생성기가 쓴 규칙적인 꼴이다: 블록 매핑·시퀀스, `|` 블록 스칼라,
# 평문·작은따옴표·큰따옴표 스칼라, 빈 `[]`/`{}`. 앵커·흐름 컬렉션(비지 않은 것)·태그는 없다(2026-11 확인).

class Node(dict):
    __slots__ = ("start", "end")


class _Y:
    def __init__(self, text):
        self.raw = text.split("\n")
        self.lines = []  # (indent, content, lineno 1-based) — 빈 줄·주석 줄은 None 표시
        for i, l in enumerate(self.raw, 1):
            s = l.lstrip(" ")
            if not s.strip() or s.startswith("#"):
                self.lines.append((None, "", i))
            else:
                self.lines.append((len(l) - len(s), s.rstrip(), i))
        self.n = len(self.lines)

    def skip(self, i):
        while i < self.n and self.lines[i][0] is None:
            i += 1
        return i

    def block(self, i, ind):
        i = self.skip(i)
        if i >= self.n:
            return None, i
        li, c, _ = self.lines[i]
        if c == "-" or c.startswith("- "):
            return self.seq(i, li)
        return self.mapping(i, li)

    def seq(self, i, ind):
        res = []
        while True:
            i = self.skip(i)
            if i >= self.n:
                break
            li, c, ln = self.lines[i]
            if li != ind or not (c == "-" or c.startswith("- ")):
                break
            rest = c[1:].lstrip(" ")
            if not rest:
                v, i = self.block(i + 1, ind + 1)
                res.append(v)
                continue
            if _is_key(rest):
                self.lines[i] = (ind + (len(c) - len(rest)), rest, ln)
                v, i = self.mapping(i, self.lines[i][0])
                res.append(v)
            else:
                v, i = self.scalar_at(i, ind, rest)
                res.append(v)
        return res, i

    def mapping(self, i, ind):
        res = Node()
        res.start = self.lines[i][2]
        last = i
        while True:
            i = self.skip(i)
            if i >= self.n:
                break
            li, c, ln = self.lines[i]
            if li != ind or c == "-" or c.startswith("- ") or not _is_key(c):
                break
            key, rest = _split_key(c)
            if rest[:1] in ("|", ">") and re.fullmatch(r"[|>][-+]?[0-9]?", rest):
                v, i = self.block_scalar(i, ind, rest)
            elif rest == "":
                j = self.skip(i + 1)
                if j < self.n and self.lines[j][0] > ind:
                    v, i = self.block(j, self.lines[j][0])
                elif j < self.n and self.lines[j][0] == ind and (self.lines[j][1] == "-" or self.lines[j][1].startswith("- ")):
                    v, i = self.seq(j, ind)
                else:
                    v, i = None, i + 1
            else:
                v, i = self.scalar_at(i, ind, rest)
            res[key] = v
            last = i - 1
        while last > 0 and self.lines[last][0] is None:
            last -= 1
        res.end = self.lines[max(last, 0)][2]
        return res, i

    def block_scalar(self, i, ind, ind_char):
        j = i + 1
        body = []
        bind = None
        while j < self.n:
            li, c, ln = self.lines[j]
            if li is None:
                body.append("")
                j += 1
                continue
            if li <= ind:
                break
            if bind is None:
                bind = li
            body.append(self.raw[ln - 1][bind:] if li >= bind else c)
            j += 1
        while body and body[-1] == "":
            body.pop()
        j2 = j
        while j2 > i + 1 and self.lines[j2 - 1][0] is None:
            j2 -= 1
        text = "\n".join(body)
        if ind_char.startswith(">"):
            text = re.sub(r"(?<!\n)\n(?!\n)", " ", text)
        if "-" not in ind_char:
            text += "\n"
        return text, j

    def scalar_at(self, i, ind, rest):
        parts = [rest]
        j = i + 1
        while j < self.n:
            li, c, _ = self.lines[j]
            if li is None:
                k = self.skip(j)
                if k < self.n and self.lines[k][0] > ind and not rest.startswith(("'", '"')):
                    parts.append("\n")
                    j += 1
                    continue
                break
            if li <= ind:
                break
            parts.append(c)
            j += 1
        return _scalar(" ".join(p for p in parts if p != "\n") if len(parts) > 1 else rest), j


def _is_key(c):
    return re.match(r"^[A-Za-z_][\w.\-]*:(\s|$)", c) is not None or re.match(r"^'[^']*':(\s|$)", c) is not None


def _split_key(c):
    if c.startswith("'"):
        end = c.index("':")
        return c[1:end], c[end + 2:].strip()
    k, _, rest = c.partition(":")
    return k, rest.strip()


def _scalar(s):
    s = s.strip()
    if s in ("[]",):
        return []
    if s in ("{}",):
        return {}
    if s.startswith("'") and s.endswith("'") and len(s) >= 2:
        return s[1:-1].replace("''", "'")
    if s.startswith('"') and s.endswith('"') and len(s) >= 2:
        try:
            return json.loads(s)
        except ValueError:
            return s[1:-1]
    if s in ("", "~", "null"):
        return None
    return s


def parse_yaml(text):
    y = _Y(text)
    v, _ = y.block(0, 0)
    return v if v is not None else Node()


# ---------------------------------------------------------------- 색인 (절)

def _md_sections(text):
    """마크다운을 제목 단위 절로 나눈다. 코드 펜스 안의 # 는 제목이 아니다."""
    lines = text.split("\n")
    title = None
    body_start = 0
    if lines and lines[0].strip() == "---":
        for k in range(1, min(len(lines), 60)):
            if lines[k].strip() == "---":
                fm = parse_yaml("\n".join(lines[1:k]))
                if isinstance(fm, dict):
                    title = fm.get("title")
                body_start = k + 1
                break
    heads = []
    fence = None
    for k in range(body_start, len(lines)):
        s = lines[k]
        m = re.match(r"^\s{0,3}(`{3,}|~{3,})", s)
        if m:
            if fence is None:
                fence = m.group(1)[0]
            elif m.group(1)[0] == fence:
                fence = None
            continue
        if fence:
            continue
        m = re.match(r"^(#{1,6})\s+(.*?)\s*#*\s*$", s)
        if m:
            heads.append((k, len(m.group(1)), m.group(2)))
    n = len(lines) - (1 if lines and lines[-1] == "" else 0)
    secs = []
    first = heads[0][0] if heads else n
    if first > body_start or not heads:
        secs.append({"a": 1, "b": max(first, 1), "title": title or "(머리)", "level": 0})
    stack = []
    for idx, (k, lvl, t) in enumerate(heads):
        end = n
        for k2, l2, _ in heads[idx + 1:]:
            if l2 <= lvl:
                end = k2
                break
        while stack and stack[-1][0] >= lvl:
            stack.pop()
        stack.append((lvl, t))
        secs.append({"a": k + 1, "b": end, "title": " › ".join(x[1] for x in stack), "level": lvl,
                     "own_b": (heads[idx + 1][0] if idx + 1 < len(heads) else n)})
    return title, secs


def _first_sentence(text, limit=110):
    for para in re.split(r"\n\s*\n", text):
        p = para.strip()
        if not p or p.startswith(("|", "```", "<", "#", "!", "---", "title:", "description:")):
            continue
        p = re.sub(r"\s+", " ", p)
        p = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", p)
        p = plain(p)
        m = re.match(r"(.+?[.!?])(\s|$)", p)
        s = m.group(1) if m else p
        return s if len(s) <= limit else s[:limit - 1] + "…"
    return ""


def _yaml_sections(text):
    doc = parse_yaml(text)
    if not isinstance(doc, dict):
        return None, []
    name = doc.get("name") or "?"
    secs = []
    first_member = None
    for key in MEMBER_KEYS:
        v = doc.get(key)
        if isinstance(v, list):
            for it in v:
                if isinstance(it, Node):
                    first_member = it.start if first_member is None else min(first_member, it.start)
    total = text.count("\n") + (0 if text.endswith("\n") else 1)
    secs.append({"a": 1, "b": (first_member - 1) if first_member else total, "title": f"{name} ({doc.get('type', '?')})",
                 "summary": _oneline(doc.get("summary"))})
    for key in MEMBER_KEYS:
        v = doc.get(key)
        if not isinstance(v, list):
            continue
        for it in v:
            if not isinstance(it, Node):
                continue
            nm = str(it.get("name"))
            dep = _is_deprecated(it)
            secs.append({"a": it.start, "b": it.end, "title": f"{nm} ({KIND_NAME[key]}{', deprecated' if dep else ''})",
                         "summary": _oneline(it.get("summary"))})
    return name, secs


def _oneline(s, limit=110):
    if not s:
        return ""
    s = plain(re.sub(r"\s+", " ", str(s)).strip())
    return s if len(s) <= limit else s[:limit - 1] + "…"


def build_index(cache):
    root = content_root(cache)
    files = {}
    for p in sorted(root.rglob("*")):
        if not p.is_file() or p.suffix not in (".md", ".yaml"):
            continue
        rel = p.relative_to(root).as_posix()
        text = p.read_text(encoding="utf-8", errors="replace")
        if p.suffix == ".md":
            title, secs = _md_sections(text)
            lines = text.split("\n")
            for s in secs:
                s["o"] = s.get("own_b", s["b"])
                s["summary"] = _first_sentence("\n".join(lines[s["a"] - 1 + (1 if s.get("level") else 0): s["o"]]))
        else:
            try:
                title, secs = _yaml_sections(text)
            except Exception as e:  # 파서가 모르는 꼴: 파일 하나를 통째 절로
                sys.stderr.write(f"YAML 해석 실패 {rel}: {e}\n")
                title, secs = rel, [{"a": 1, "b": text.count("\n") + 1, "title": rel, "summary": ""}]
        lines = text.split("\n")
        for s in secs:
            s.setdefault("o", s["b"])
            s["w"] = len(" ".join(lines[s["a"] - 1:s["o"]]).split())
        files[rel] = {"title": title, "sections": [{k: s[k] for k in ("a", "b", "o", "w", "title", "summary") if k in s} for s in secs]}
    idx = {"version": INDEX_VERSION, "files": files}
    (cache / "index.json").write_text(json.dumps(idx, ensure_ascii=False))
    return idx


def load_index(cache):
    p = cache / "index.json"
    if not content_root(cache).is_dir():
        die(f"캐시가 없음: {cache} — 먼저 `python3 -I tools/roblox_docs.py sync`", 3)
    if p.exists():
        idx = json.loads(p.read_text())
        if idx.get("version") == INDEX_VERSION:
            return idx
    return build_index(cache)


# ---------------------------------------------------------------- 표기 정리

_REF = re.compile(r"`(Class|Datatype|Enum|Global|Library)\.([^`|]+?)(?:\|([^`]+))?`")


def plain(s):
    """`Class.Tween|Tweens` 같은 참조 표기를 읽기 쉬운 이름으로 바꾼다."""
    def rep(m):
        kind, name, alias = m.group(1), m.group(2), m.group(3)
        if alias:
            return f"`{alias}`"
        if kind == "Enum":
            return f"`Enum.{name}`"
        if kind == "Global":
            name = re.sub(r"^(LuaGlobals|RobloxGlobals)\.", "", name)
        return f"`{name}`"
    return _REF.sub(rep, s)


def _is_deprecated(it):
    tags = it.get("tags") or []
    return (isinstance(tags, list) and "Deprecated" in tags) or bool((it.get("deprecation_message") or "").strip())


# ---------------------------------------------------------------- 경로 해석

def resolve(cache, raw):
    root = content_root(cache)
    s = raw.strip()
    s = re.sub(r"^https?://create\.roblox\.com/docs/", "", s)
    s = re.sub(r"^/?docs/", "", s)
    s = re.sub(r"^en-us/", "", s)
    s = re.sub(r"^content/en-us/", "", s)
    s = s.lstrip("/")
    cands = [s]
    stem = re.sub(r"\.(md|yaml)$", "", s)
    for base in (stem, "reference/engine/" + stem):
        cands += [base + ".md", base + ".yaml", base + "/index.md"]
    for c in cands:
        p = root / c
        try:
            p.resolve().relative_to(root.resolve())
        except ValueError:
            continue
        if p.is_file():
            return p.relative_to(root).as_posix()
    # 마지막: 끝 경로가 같은 파일 하나
    tail = PurePosixPath(stem).name.lower()
    hits = [p for p in root.rglob("*") if p.is_file() and p.suffix in (".md", ".yaml") and p.stem.lower() == tail]
    hits = [h for h in hits if h.relative_to(root).as_posix().lower().endswith(stem.lower() + h.suffix)] or hits
    if len(hits) == 1:
        return hits[0].relative_to(root).as_posix()
    if hits:
        die("여러 파일이 맞음: " + ", ".join(h.relative_to(root).as_posix() for h in hits[:8]))
    die(f"없는 경로: {raw} (search 로 찾는다)", 4)


def doc_url(rel):
    return DOCS_URL + re.sub(r"(/index)?\.(md|yaml)$", "", rel)


# ---------------------------------------------------------------- search

def cmd_search(a):
    cache = cache_dir(a.cache)
    idx = load_index(cache)
    root = content_root(cache)
    terms = [t.lower() for t in re.findall(r"[\w.:]+", " ".join(a.query)) if t]
    if not terms:
        die("질의가 비었음")
    pre = [re.compile(r"(?<![\w])" + re.escape(t), re.I) for t in terms]
    exact = [re.compile(r"(?<![\w])" + re.escape(t) + r"(?![\w])", re.I) for t in terms]
    rows = []
    df = [0] * len(terms)
    nsec = wsum = 0
    for rel, f in idx["files"].items():
        if a.api and not rel.startswith("reference/"):
            continue
        if a.guide and rel.startswith("reference/"):
            continue
        if a.under and not rel.startswith(a.under.strip("/")):
            continue
        nsec += len(f["sections"])
        wsum += sum(s.get("w", 0) for s in f["sections"])
        text = (root / rel).read_text(encoding="utf-8", errors="replace")
        lines = text.split("\n")
        for s in f["sections"]:
            body = "\n".join(lines[s["a"] - 1:s["o"]])
            # 정확한 낱말은 1, 앞부분만 맞으면(optimize → optimization) 0.5
            tf = []
            for k in range(len(terms)):
                e = len(exact[k].findall(body))
                tf.append(e + 0.5 * (len(pre[k].findall(body)) - e))
            if not any(tf):
                continue
            for k, c in enumerate(tf):
                if c:
                    df[k] += 1
            head = s["title"] + " " + rel
            rows.append((rel, s, tf, head, body))
    N = max(1, nsec)
    avg = max(1.0, wsum / N)
    idf = [math.log(1 + (N - d + 0.5) / (d + 0.5)) for d in df]
    k1, bb = 1.2, 0.75
    scored = []
    for rel, s, tf, head, body in rows:
        hit = sum(1 for c in tf if c)
        norm = k1 * (1 - bb + bb * max(1, s.get("w", 1)) / avg)
        sc = 0.0
        for k, c in enumerate(tf):
            if c:
                sc += idf[k] * c * (k1 + 1) / (c + norm)
                if pre[k].search(head):
                    sc += 1.5 * idf[k]
        sc *= (hit / len(terms)) ** 2
        scored.append((sc, rel, s, body))
    scored.sort(key=lambda x: (-x[0], x[1], x[2]["a"]))
    out(f"root: {root}")
    if not scored:
        out("결과 없음")
        return
    for sc, rel, s, body in scored[:a.n]:
        out(f"{rel}:{s['a']}-{s['o']} {fmt_tok(tokens_est(body))} § {s['title']}")
        if s.get("summary") and not a.brief:
            out(f"  {s['summary']}")


# ---------------------------------------------------------------- get

def cmd_get(a):
    cache = cache_dir(a.cache)
    idx = load_index(cache)
    root = content_root(cache)
    spec = a.target
    rng = sec = None
    m = re.match(r"^(.*?):(\d+)(?:-(\d+))?$", spec)
    if m and not spec.startswith("http"):
        spec, rng = m.group(1), (int(m.group(2)), int(m.group(3) or m.group(2)))
    elif "#" in spec:
        spec, sec = spec.split("#", 1)
    rel = resolve(cache, spec)
    text = (root / rel).read_text(encoding="utf-8", errors="replace")
    lines = text.split("\n")
    f = idx["files"].get(rel, {"title": rel, "sections": []})
    total = len(lines) - (1 if lines and lines[-1] == "" else 0)
    if sec:
        want = sec.lower().replace("-", " ")
        cands = [s for s in f["sections"]
                 if want in s["title"].lower().replace("-", " ") or want == _slug(s["title"].split(" › ")[-1])]
        if not cands:
            die(f"절이 없음: #{sec} — `get {rel} --toc` 로 목차를 본다", 4)
        def rank(s):
            last = s["title"].split(" › ")[-1].split(" (")[0]
            short = re.split(r"[.:]", last)[-1]
            if sec in (last, short):
                return (0, s["b"] - s["a"])
            if want in (last.lower(), short.lower(), _slug(last)):
                return (1, s["b"] - s["a"])
            return (2, s["b"] - s["a"])
        cands.sort(key=rank)
        s = cands[0]
        rng = (s["a"], s["b"])
        title = s["title"]
    elif rng:
        title = next((s["title"] for s in reversed(f["sections"]) if s["a"] <= rng[0] <= s["b"]), f.get("title") or rel)
    else:
        title = f.get("title") or rel
    if rng:
        a0, b0 = max(1, rng[0]), min(total, rng[1])
        body = "\n".join(lines[a0 - 1:b0])
        out(f"{rel}:{a0}-{b0} {fmt_tok(tokens_est(body))} § {title}  <{doc_url(rel)}>")
        out("---")
        out(body)
        return
    body = "\n".join(lines[:total])
    tok = tokens_est(body)
    out(f"{rel}:1-{total} {fmt_tok(tok)} § {title}  <{doc_url(rel)}>")
    if a.toc or (tok > SECTION_THRESHOLD and not a.body):
        if not a.toc:
            out(f"(큰 문서 {fmt_tok(tok)} — 목차만 낸다. 절은 `get {rel}#<절>` 또는 `get {rel}:a-b`, 통째는 --body)")
        for s in f["sections"]:
            seg = "\n".join(lines[s["a"] - 1:s["b"]])
            out(f"L{s['a']}-{s['b']} {fmt_tok(tokens_est(seg))}  {s['title']}")
        return
    out("---")
    out(body)


def _slug(t):
    return re.sub(r"[^\w]+", " ", t.lower()).strip()


# ---------------------------------------------------------------- api

def _load_ref(cache, name):
    root = content_root(cache) / "reference/engine"
    for d in REF_DIRS:
        p = root / d / f"{name}.yaml"
        if p.is_file():
            return p
    low = name.lower()
    for d in REF_DIRS:
        for p in (root / d).glob("*.yaml"):
            if p.stem.lower() == low:
                return p
    return None


def _sig(it, kind):
    ps = []
    for p in it.get("parameters") or []:
        if not isinstance(p, dict):
            continue
        s = f"{p.get('name')}: {p.get('type')}"
        if p.get("default") not in (None, ""):
            s += f" = {p.get('default')}"
        ps.append(s)
    name = str(it.get("name"))
    if kind == "property":
        return f"{name}: {it.get('type')}"
    if kind == "item":
        return f"{name} = {it.get('value')}"
    if kind == "constant":
        return f"{name}: {it.get('type')}"
    if kind == "operator":
        return f"{it.get('type_a', '?')} {it.get('operation', name)} {it.get('type_b', '?')} -> {it.get('return_type', '?')}"
    rets = [str(r.get("type")) for r in it.get("returns") or [] if isinstance(r, dict)]
    r = f": {', '.join(rets)}" if rets else (": ()" if kind in ("method", "function", "callback") else "")
    return f"{name}({', '.join(ps)}){r}"


def _security(v):
    if isinstance(v, dict):
        return f"read {v.get('read')} / write {v.get('write')}"
    return str(v) if v is not None else "-"


def cmd_api(a):
    cache = cache_dir(a.cache)
    load_index(cache)
    root = content_root(cache)
    q = a.name.strip()
    m = re.match(r"^([\w]+)(?:[.:](.+))?$", q)
    if not m:
        die("꼴: Class, Class.Member, Class:Method")
    cls, member = m.group(1), m.group(2)
    p = _load_ref(cache, cls)
    if p is None:
        die(f"참조에 없음: {cls} (search --api {cls} 로 찾는다)", 4)
    chain = []
    seen = set()
    while p is not None and p.stem not in seen:
        seen.add(p.stem)
        text = p.read_text(encoding="utf-8", errors="replace")
        chain.append((p, parse_yaml(text), text))
        inh = chain[-1][1].get("inherits") or []
        p = _load_ref(cache, inh[0]) if inh else None
    meta = json.loads((cache / "meta.json").read_text()) if (cache / "meta.json").exists() else {}
    stamp = f"[creator-docs {str(meta.get('commit', ''))[:12]} · STUDIO_VERSION {meta.get('studio_version')}]"
    if member:
        for path, doc, text in chain:
            hits = []
            for key in MEMBER_KEYS:
                for it in doc.get(key) or []:
                    if not isinstance(it, Node):
                        continue
                    nm = str(it.get("name"))
                    short = re.split(r"[.:]", nm)[-1]
                    if short.lower() == member.lower() or nm.lower() == q.lower():
                        hits.append((it, KIND_NAME[key], short == member))
            if hits:
                if any(h[2] for h in hits):  # 대소문자까지 같은 것이 있으면 그것만(Destroy 대 옛 destroy)
                    hits = [h for h in hits if h[2]]
                for n, (it, kind, _) in enumerate(hits):
                    if n:
                        out(f"--- 오버로드 {n + 1}/{len(hits)}")
                    _print_member(root, path, it, kind, text, stamp, inherited=(path != chain[0][0]))
                return
        die(f"멤버가 없음: {q} (상속 사슬 {' > '.join(c[0].stem for c in chain)})", 4)
    path, doc, text = chain[0]
    rel = path.relative_to(root).as_posix()
    out(f"{doc.get('name')} ({doc.get('type')}) — {rel}  <{doc_url(rel)}>  {stamp}")
    if len(chain) > 1:
        out("inherits: " + " > ".join(c[0].stem for c in chain[1:]))
    tags = doc.get("tags") or []
    if tags:
        out("tags: " + ", ".join(map(str, tags)))
    if _is_deprecated(doc):
        out("DEPRECATED: " + _oneline(doc.get("deprecation_message"), 300))
    if doc.get("memory_category"):
        out(f"memory_category: {doc.get('memory_category')}")
    out("summary: " + _oneline(doc.get("summary"), 400))
    for key in MEMBER_KEYS:
        items = [it for it in doc.get(key) or [] if isinstance(it, Node)]
        if not items:
            continue
        out(f"{key} ({len(items)}):")
        for it in items:
            kind = KIND_NAME[key]
            flags = []
            if _is_deprecated(it):
                flags.append("deprecated")
            sec = it.get("security")
            if sec not in (None, "None") and not (isinstance(sec, dict) and set(sec.values()) <= {"None"}):
                flags.append(_security(sec))
            if it.get("thread_safety"):
                flags.append(str(it.get("thread_safety")))
            out(f"  L{it.start}-{it.end} {_sig(it, kind)}" + (f"  [{' · '.join(flags)}]" if flags else ""))
    if len(chain) > 1:
        out(f"(상속 멤버는 `api {chain[1][0].stem}` 로 본다)")


def _print_member(root, path, it, kind, text, stamp, inherited):
    rel = path.relative_to(root).as_posix()
    seg = "\n".join(text.split("\n")[it.start - 1:it.end])
    out(f"{it.get('name')} ({kind}{', 상속' if inherited else ''}) — {rel}:{it.start}-{it.end} {fmt_tok(tokens_est(seg))}  <{doc_url(rel)}>  {stamp}")
    out(f"signature: {_sig(it, kind)}")
    row = []
    if "security" in it:
        row.append(f"security: {_security(it.get('security'))}")
    if it.get("thread_safety"):
        row.append(f"thread_safety: {it.get('thread_safety')}")
    caps = it.get("capabilities")
    if caps:
        row.append("capabilities: " + ", ".join(map(str, caps)))
    if row:
        out(" · ".join(row))
    tags = [t for t in (it.get("tags") or []) if t]
    out(f"deprecated: {'예' if _is_deprecated(it) else '아니오'}" + (f" · tags: {', '.join(map(str, tags))}" if tags else ""))
    if (it.get("deprecation_message") or "").strip():
        out("deprecation_message: " + _oneline(it.get("deprecation_message"), 400))
    if kind == "property":
        extra = [f"{k}: {it.get(k)}" for k in ("category", "default") if it.get(k) not in (None, "")]
        ser = it.get("serialization")
        if isinstance(ser, dict):
            extra.append(f"serialization: load {ser.get('can_load')} / save {ser.get('can_save')}")
        if extra:
            out(" · ".join(extra))
    out("summary: " + _oneline(it.get("summary"), 400))
    params = [p for p in it.get("parameters") or [] if isinstance(p, dict)]
    if params:
        out("parameters:")
        for p in params:
            d = f" = {p.get('default')}" if p.get("default") not in (None, "") else ""
            out(f"  {p.get('name')}: {p.get('type')}{d} — {_oneline(p.get('summary'), 200)}")
    rets = [r for r in it.get("returns") or [] if isinstance(r, dict) and not (r.get("type") == "()" and not (r.get("summary") or "").strip())]
    if rets:
        out("returns:")
        for r in rets:
            out(f"  {r.get('type')}" + (f" — {_oneline(r.get('summary'), 200)}" if (r.get("summary") or "").strip() else ""))
    desc = (it.get("description") or "").strip()
    if desc:
        out("description:")
        for line in plain(desc).split("\n"):
            out("  " + line)
    cs = it.get("code_samples") or []
    if cs:
        out("code_samples: " + ", ".join(map(str, cs)))


# ---------------------------------------------------------------- main

def main(argv=None):
    ap = argparse.ArgumentParser(prog="roblox_docs.py", description="Roblox 문서(creator-docs) 로컬 조회")
    ap.add_argument("--cache", help=f"캐시 디렉터리 (기본: ${ENV_KEY} > harness.env > ${{XDG_CACHE_HOME:-~/.cache}}/roblox-docs)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("sync", help="받기·갱신")
    p.add_argument("--force", action="store_true")
    p.set_defaults(fn=cmd_sync)
    p = sub.add_parser("status", help="캐시 상태")
    p.set_defaults(fn=cmd_status)
    p = sub.add_parser("search", help="절 단위 검색")
    p.add_argument("query", nargs="+")
    p.add_argument("-n", type=int, default=8)
    g = p.add_mutually_exclusive_group()
    g.add_argument("--api", action="store_true", help="엔진·클라우드 참조(reference/)만")
    g.add_argument("--guide", action="store_true", help="가이드(참조 밖)만")
    p.add_argument("--under", help="이 경로 접두 아래만 (예: scripting/)")
    p.add_argument("--brief", action="store_true", help="요약 줄 없이 한 줄씩")
    p.set_defaults(fn=cmd_search)
    p = sub.add_parser("get", help="문서·절·줄 범위 읽기")
    p.add_argument("target", help="경로[#절] 또는 경로:a-b (경로는 content/en-us 기준, URL·.md 표기도 받음)")
    p.add_argument("--body", action="store_true", help="큰 문서도 통째로")
    p.add_argument("--toc", action="store_true", help="목차만")
    p.set_defaults(fn=cmd_get)
    p = sub.add_parser("api", help="엔진 API 요약")
    p.add_argument("name", help="Class, Class.Member, Class:Method, 라이브러리 task.defer, 전역 LuaGlobals.collectgarbage")
    p.set_defaults(fn=cmd_api)
    a = ap.parse_args(argv)
    try:
        a.fn(a)
    except BrokenPipeError:
        pass


if __name__ == "__main__":
    main()
