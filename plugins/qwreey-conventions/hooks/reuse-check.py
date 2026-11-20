#!/usr/bin/env python3
"""PostToolUse(Write|Edit|MultiEdit) 알림: 한 사실의 사본. 막지 않고 additionalContext(level=info) 한 블록만 낸다.

검사
  C1 `@copy-of: <경로>[#이름]` 사본이 원본과 같은가(파일은 바이트, 값은 문자열 묶음). 풀리지 않거나 다르면 알린다.
     `<저장소>:<경로>` 는 현재 저장소 옆의 같은 이름 폴더, 없으면 known_repos.py 의 저장소 목록에서 찾는다(sibling_repos). 못 찾으면 기록만 한다.
     영역 사본(`@start-replace: <경로>#<이름> [옵션]` ... `@end-replace`)은 정본 영역에서 만든 줄과 같은가(copy_regions.py, 정본은 lib/).
  C2 원본을 고치면 그것을 가리키는 사본 목록을 알린다(묶음은 원소가 바뀐 때만, 정본 영역은 그 안의 줄을 고친 때만).
  H1 추가한 문자열 묶음이 저장소의 다른 정의와 겹침(타입 합집합과 런타임 목록이 어긋난 것 포함). 기본은 그림자: 알리지 않고
     ${CLAUDE_PLUGIN_DATA}/reuse-shadow.jsonl(없으면 $TMPDIR/claude-qwreey-reuse/shadow.jsonl)에 한 줄씩 남긴다(본문 없음).
모드: 환경 변수 REUSE_CHECK=off|shadow|on 이 저장소 .claude/conventions.json 의 reuse.mode 를 이긴다. 기본 shadow.
  off 는 모든 검사를 끈다. CONVENTIONS_CHECK=off 도 이 훅을 끈다.
설정: .claude/conventions.json 의 reuse = {"mode", "allow": [{"path": 글롭, "reason"}], "vocab_ok": [[낱말...]], "min_shared": 3}
색인: $TMPDIR/claude-qwreey-reuse/<저장소 루트 해시>.json (저장소 단위, 파일 mtime·크기가 바뀐 것만 다시 읽는다).
  첫 색인은 300ms 에서 끊고 다음 편집에서 이어 만든다. 400ms 가 넘으면 판정을 그만둔다.
제외: .claude/, *-ignoreme*, 벤더 트리(vendor.lock.json 이 있는 폴더, vendor/ 등), 생성 파일, 시험·stories·gallery·examples·refs.
알림 중복: (session_id, 호출한 쪽, compact 회차, 상대 정의)당 한 번, 파일당 최대 2번.
턴 끝 보고용 기록: $TMPDIR/claude-conventions/<session_id>.reuse.<main|agent_id>.json (conventions-check 의 Stop 이 합쳐 보인다).
"""
import fnmatch
import functools
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time

T0 = time.perf_counter()
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import compact_epoch  # noqa: E402
import copy_regions  # noqa: E402
import harness_nonce  # noqa: E402
from conv_edit import GEN_MARK, MAX_BYTES, SKIP_PARTS, SKIP_SUFFIX, collect, project_root  # noqa: E402
from conv_env import env_value  # noqa: E402
from conv_lex import FAMILY, lex  # noqa: E402
from reuse_sets import FLAG_DEF, FLAG_TYPE, Budget, extract, reason_ok  # noqa: E402

NAME = "qwreey-conventions"
NS = "claude-conventions"
RULE_EXT = {".luau", ".lua", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".astro", ".rs", ".py", ".go", ".kt"}
H1_EXT = {".luau", ".lua", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".rs", ".py"}
LANG = {".luau": "luau", ".lua": "luau", ".ts": "ts", ".tsx": "ts", ".js": "ts", ".jsx": "ts", ".mjs": "ts", ".astro": "ts",
        ".rs": "rust", ".py": "py", ".go": "go", ".kt": "kt"}
CMT = {"luau": "--", "py": "#"}
SKIP_DIRS = SKIP_PARTS | {".claude", "stories", "gallery", "examples", "tests", "test", "__tests__", "spec", "specs"}
TEST_FILE = re.compile(r"\.(spec|test|story)\.|_test\.|(^|/)test[-_]|tests\.rs$", re.I)
GEN = re.compile(GEN_MARK.pattern + r"|생성:", re.I)
MANIFESTS = ("Cargo.toml", "package.json", "pyproject.toml", "wally.toml", "pesde.toml", "default.project.json")
COLD_MS, HARD_MS, WARM_BUDGET_MS = 300, 400, 150
MAX_FILES = 5000
MAX_NOTICES_PER_FILE = 2
LABEL_BUDGET = "budget"
INDEX_VERSION = 2  # 2: 표시에 영역 사본("r")이 들어간다. 옛 색인은 다시 만든다
SYNC_HINT = "Edit the canon region, then sync the copies (python3 -I tools/sync-copies.py --apply where the repo has it)."


# ---------- 설정, 경로 ----------

def load_cfg(root):
    try:
        with open(os.path.join(root, ".claude", "conventions.json"), encoding="utf-8") as f:
            r = json.load(f).get("reuse")
            return r if isinstance(r, dict) else {}
    except (OSError, ValueError, AttributeError):
        return {}


def mode_of(cfg):
    m = (os.environ.get("REUSE_CHECK") or env_value("REUSE_CHECK") or cfg.get("mode") or "shadow").lower()
    return m if m in ("off", "shadow", "on") else "shadow"


def allowed(rel, cfg):
    for a in cfg.get("allow") or []:
        if isinstance(a, dict) and a.get("path") and reason_ok(a.get("reason")) and fnmatch.fnmatch(rel, a["path"]):
            return True
    return False


def indexable(rel, vendored):
    """색인에 넣을 파일인가(경로만 본다)."""
    parts = rel.split("/")
    if os.path.splitext(rel)[1].lower() not in RULE_EXT or rel.endswith(SKIP_SUFFIX) or TEST_FILE.search(rel):
        return False
    if any(p in SKIP_DIRS or "-ignoreme" in p for p in parts[:-1]) or "-ignoreme" in parts[-1]:
        return False
    return not any(rel.startswith(v) for v in vendored)


def list_files(root):
    """저장소의 코드 파일(루트 기준 상대 경로). git 이 되면 git ls-files(무시 규칙을 따른다), 아니면 걷기."""
    names = None
    if os.path.exists(os.path.join(root, ".git")):
        try:
            p = subprocess.run(["git", "-C", root, "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
                               capture_output=True, timeout=3)
            if p.returncode == 0:
                names = [n for n in p.stdout.decode("utf-8", "replace").split("\0") if n]
        except (OSError, subprocess.SubprocessError):
            pass
    if names is None:
        names = []
        for dp, dn, fn in os.walk(root):
            dn[:] = [d for d in dn if d not in SKIP_DIRS and not d.startswith(".") and "-ignoreme" not in d]
            names += [os.path.relpath(os.path.join(dp, f), root) for f in fn]
    vendored = [os.path.dirname(n) + "/" for n in names if os.path.basename(n) == "vendor.lock.json" and os.path.dirname(n)]
    return [n for n in names if indexable(n, vendored)]


# ---------- 색인 ----------

def index_path(root):
    d = os.path.join(tempfile.gettempdir(), "claude-qwreey-reuse")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, sha1_12(root) + ".json")


def sha1_12(text):
    """sha1 hex 앞 12자. 짝 없는 서로게이트(UTF-8 이 아닌 폴더 이름)는 surrogatepass 바이트로 센다."""
    return hashlib.sha1(text.encode("utf-8", "surrogatepass")).hexdigest()[:12]


def rel_target(target):
    """표시 대상의 앞 `./` 들을 뗀다(`./.github/x.py` 는 `.github/x.py`, `../x` 는 그대로)."""
    while target.startswith("./"):
        target = target[2:]
    return target


def read_entry(root, rel, text=None, deadline=None):
    """[mtime_ns, size, 묶음, 표시]. 생성 파일은 비어 있다. deadline 을 넘기면 reuse_sets.Budget."""
    fp = os.path.join(root, rel)
    st = os.stat(fp)
    if text is None:
        text = open(fp, encoding="utf-8").read()
    if GEN.search("\n".join(text.split("\n", 6)[:6])):
        return [st.st_mtime_ns, st.st_size, [], []]
    sets, marks = extract(text, FAMILY.get(os.path.splitext(rel)[1].lower(), "c"), deadline)
    return [st.st_mtime_ns, st.st_size, sets, marks]


def load_index(root, files, own_rel):
    """(색인 dict, 바뀐 여부, 끊겼나). 편집한 파일은 호출한 쪽이 다시 채운다."""
    ip = index_path(root)
    try:
        with open(ip, encoding="utf-8") as f:
            idx = json.load(f)
        if idx.get("v") != INDEX_VERSION:
            idx = {"v": INDEX_VERSION, "files": {}}
    except (OSError, ValueError):
        idx = {"v": INDEX_VERSION, "files": {}}
    ents = idx["files"]
    cut = False
    dirty = False
    live = set(files)
    for rel in [r for r in ents if r not in live]:
        del ents[rel]
        dirty = True
    for rel in files:
        if rel == own_rel:
            continue
        try:
            st = os.stat(os.path.join(root, rel))
        except OSError:
            continue
        e = ents.get(rel)
        if e and e[0] == st.st_mtime_ns and e[1] == st.st_size:
            continue
        if st.st_size > MAX_BYTES:
            continue
        if (time.perf_counter() - T0) * 1000 > COLD_MS:
            cut = True
            break
        try:
            ents[rel] = read_entry(root, rel, deadline=T0 + COLD_MS / 1000)
            dirty = True
        except Budget:
            # 한도 안에 다 읽지 못한 파일은 빈 항목으로 둔다: 바뀔 때까지 다시 읽지 않아 다음 색인이 이 파일에서 멈추지 않는다
            ents[rel] = [st.st_mtime_ns, st.st_size, [], []]
            dirty = cut = True
            break
        except (OSError, UnicodeDecodeError):
            continue
    return idx, dirty, cut


def _index_bytes(idx):
    return json.dumps(idx, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def save_index(root, idx):
    """임시 파일에 쓰고 바꿔 단다. 짝 없는 서로게이트가 든 항목(UTF-8 이 아닌 파일 이름, 입력의 escape)은 빼고 쓴다."""
    ip = index_path(root)
    tmp = "%s.%d.tmp" % (ip, os.getpid())

    # Encode first, dropping entries python cannot encode
    try:
        data = _index_bytes(idx)
    except UnicodeEncodeError:
        files = {}
        for k, v in idx["files"].items():
            try:
                _index_bytes([k, v])
                files[k] = v
            except UnicodeEncodeError:
                continue
        data = _index_bytes({**idx, "files": files})

    # Write beside the index, then swap it in
    try:
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, ip)
    except OSError:
        pass


# ---------- 패키지 ----------

def package_of(root, rel, cache):
    d = os.path.dirname(rel)
    if d in cache:
        return cache[d]
    cur = d
    while True:
        p = os.path.join(root, cur)
        if os.path.exists(os.path.join(p, ".claude-plugin", "plugin.json")) or any(os.path.exists(os.path.join(p, m)) for m in MANIFESTS):
            break
        if not cur:
            break
        cur = os.path.dirname(cur)
    cache[d] = cur
    return cur


def pkg_names(root, pkg):
    out = set()
    for m in ("Cargo.toml", "pesde.toml", "wally.toml", "pyproject.toml"):
        try:
            mm = re.search(r'^name\s*=\s*"([^"]+)"', open(os.path.join(root, pkg, m), encoding="utf-8").read(), re.M)
            if mm:
                out.add(mm.group(1))
        except OSError:
            pass
    try:
        out.add(json.load(open(os.path.join(root, pkg, "package.json"), encoding="utf-8")).get("name") or "")
    except (OSError, ValueError, AttributeError):
        pass
    out.discard("")
    return out | {n.split("/")[-1] for n in out}


def depends_on(root, a, b):
    """패키지 a 가 패키지 b 에 의존한다고 선언했나(Cargo path, wally·pesde·npm 이름)."""
    names = pkg_names(root, b)
    for m in MANIFESTS:
        try:
            t = open(os.path.join(root, a, m), encoding="utf-8").read()
        except OSError:
            continue
        for p in re.findall(r'path\s*=\s*"([^"]+)"', t):
            if os.path.normpath(os.path.join(a, p)) == os.path.normpath(b or "."):
                return True
        if any(re.search(r"(?<![\w-])" + re.escape(n) + r"(?![\w-])", t) for n in names):
            return True
    return False


def importable(root, ra, rb, cache):
    if LANG.get(os.path.splitext(ra)[1].lower()) != LANG.get(os.path.splitext(rb)[1].lower()):
        return False
    pa, pb = package_of(root, ra, cache), package_of(root, rb, cache)
    return pa == pb or depends_on(root, pa, pb) or depends_on(root, pb, pa)


# ---------- 판정 ----------

def shown(els):
    s = sorted(els)
    return ", ".join(f'"{x}"' for x in s[:5]) + (f" +{len(s) - 5}" if len(s) > 5 else "")


def judge(root, rel, st, ents, cfg, cache):
    """묶음 st 와 색인의 다른 묶음을 비교해 [(알림 id, 문구, 상대 rel, 상대 줄, 상대 이름, 공유 원소, k, n, j)]."""
    ln, name, flags, els, copyof, dup = st
    mine = frozenset(els)
    min_shared = int(cfg.get("min_shared") or 3)
    vocab = [frozenset(v) for v in cfg.get("vocab_ok") or [] if isinstance(v, list)]
    me_def, me_type = bool(flags & FLAG_DEF), bool(flags & FLAG_TYPE)
    ext = os.path.splitext(rel)[1].lower()
    my_file_mark = next((m[1] for m in ents.get(rel, [0, 0, [], []])[3] if m[3] == "f"), None)
    out = []
    for orel, e in ents.items():
        for o in e[2]:
            oln, oname, oflags, oels, ocopy, odup = o
            if orel == rel and ln == oln:
                continue
            theirs = frozenset(oels)
            shared = mine & theirs
            k = len(shared)
            j = k / len(mine | theirs)
            if not (k >= min_shared or (k >= 2 and j >= 0.5)):
                continue
            o_def, o_type = bool(oflags & FLAG_DEF), bool(oflags & FLAG_TYPE)
            if not (me_def or o_def):
                continue
            if orel == rel and not (me_def and o_def and abs(ln - oln) >= 50):
                continue
            if me_type != o_type:  # 타입 합집합과 런타임 목록: 어긋날 때만(N7)
                if mine == theirs or not (me_def and o_def) or LANG.get(ext) != LANG.get(os.path.splitext(orel)[1].lower()):
                    continue
                kind = "N7"
            elif me_type and mine != theirs:
                continue  # 타입끼리는 같을 때만
            else:
                kind = "N1"
            if any(vs >= shared for vs in vocab):
                continue
            # 표시한 사본과 그 원본의 짝은 알리지 않는다
            their_file = next((m[1] for m in e[3] if m[3] == "f"), None)
            if (my_file_mark and (my_file_mark == orel or my_file_mark == their_file)) or (their_file and their_file == rel):
                continue
            if copyof and (copyof == f"{orel}#{oname}" or copyof == ocopy) or (ocopy and ocopy == f"{rel}#{name}"):
                continue
            if (dup is not None and reason_ok(dup)) or (odup is not None and reason_ok(odup)):
                continue
            if kind == "N1" and not importable(root, rel, orel, cache):
                if not (me_def and o_def):
                    continue
                kind = "N2"
            out.append((kind, orel, oln, oname, shared, k, len(mine), j, oflags, theirs))
    return out


def text_of(kind, rel, st, hit):
    ln, name = st[0], st[1] or "this list"
    _, orel, oln, oname, shared, k, n, j, oflags, theirs = hit
    mine = frozenset(st[3])
    c = CMT.get(LANG.get(os.path.splitext(rel)[1].lower()), "//")
    if kind == "N7":
        mt = "type" if st[2] & FLAG_TYPE else "list"
        ot = "type" if oflags & FLAG_TYPE else "list"
        miss, extra = sorted(theirs - mine), sorted(mine - theirs)
        return (f"{rel}:{ln}: {mt} {name} and {ot} {oname} at {orel}:{oln} hold different strings (missing {shown(miss) or 'none'}, "
                f"extra {shown(extra) or 'none'}). Make them match, or put `{c} @dup-ok: <reason>` above if they differ on purpose.")
    if kind == "N2":
        opkg = os.path.dirname(orel) or "."
        return (f"{rel}:{ln}: string set repeats {name} at {orel}:{oln} in {opkg}, which this package cannot import ({k}/{n} shared: {shown(shared)}). "
                f"Same knowledge: keep it, mark it `{c} @copy-of: {orel}#{oname or name}` and compare the two in the repo's tests (or generate one from the other); "
                f"do not add a cross-package import. A value each project sets differently: config with a `DEFAULT_*` fallback instead. "
                f"Only alike: `{c} @dup-ok: <reason>`, the reason saying why they are different facts.")
    return (f"{rel}:{ln}: string set repeats {oname or 'a list'} at {orel}:{oln} ({k}/{n} shared: {shown(shared)}). "
            f"Same knowledge: reference {oname or 'it'} instead, or move it to one module both import. "
            f"A value each project sets differently: config with a `DEFAULT_*` fallback instead. "
            f"Only alike: put `{c} @dup-ok: <reason>` above it, the reason saying why they are different facts.")


# ---------- 사본 검사(C1, C2) ----------

@functools.lru_cache(maxsize=None)  # 한 편집에 같은 저장소를 가리키는 표시가 여럿이어도 한 번만 찾는다
def sibling_repos(root, name):
    """`<저장소>:<경로>` 의 저장소 이름 name 에 맞는 폴더 후보(앞이 우선). 프로젝트를 어디에 두는지는 사람과 OS 마다 달라
    작업공간 폴더를 정하게 하지 않는다: 현재 저장소(worktree 면 본 저장소) 옆의 같은 이름 폴더가 있으면 그것 하나,
    없으면 이 기기에서 일한 저장소(known_repos: 세션 기록의 cwd 와 qwreey-workspace 옵션) 가운데 폴더 이름이 같은 것 전부(경로순)."""
    # known_repos 는 이 표시가 있을 때만 쓴다. 대부분의 편집은 이 import 와 수집을 치르지 않는다.
    import known_repos
    main = known_repos.repo_root(root) or root
    beside = os.path.join(os.path.dirname(os.path.normpath(main)), name)
    if os.path.isdir(beside):
        return (beside,)
    want = os.path.normcase(name)
    try:
        found = known_repos.repos()
    except Exception:  # 수집 실패는 "못 찾음": 훅은 편집을 막지 않는다
        found = []
    return tuple(r for r in found if os.path.normcase(os.path.basename(r)) == want)


def resolve(root, target):
    """(경로 또는 None, 풀 수 없는 이유 'sibling' 여부, 알림에 덧붙일 말). `<저장소>:<경로>` 는 sibling_repos 로 푼다.
    같은 이름 저장소가 여럿이면 그 경로가 있는 첫 후보를 쓰고, 어느 것과 비교했는지 알림 끝에 적는다(알림이 날 때만 보인다)."""
    if re.match(r"^[\w.-]+:[^/\\]", target) and "/" not in target.split(":", 1)[0]:
        repo, path = target.split(":", 1)
        cands = sibling_repos(root, repo)
        if not cands:
            return None, True, ""
        pick = next((c for c in cands if os.path.exists(os.path.join(c, path))), cands[0])
        note = f" ({len(cands)} repos named {repo} on this machine; compared with {pick}.)" if len(cands) > 1 else ""
        return os.path.join(pick, path), False, note
    return os.path.join(root, rel_target(target)), False, ""


def sets_of_file(root, rel_or_abs, ents):
    if rel_or_abs in ents:
        return ents[rel_or_abs][2]
    p = rel_or_abs if os.path.isabs(rel_or_abs) else os.path.join(root, rel_or_abs)
    try:
        return extract(open(p, encoding="utf-8").read(), FAMILY.get(os.path.splitext(p)[1].lower(), "c"))[0]
    except (OSError, UnicodeDecodeError):
        return None


def check_copies(root, rel, text, own_entry, ents, added_lines):
    """C1. [(줄, 알림 문구 또는 None(풀 수 없음, 기록만), 결과, 대상, 새로 건드렸나)]. 결과: ok | unresolved | differs | sibling."""
    res = []
    for ln, tgt, name, kind in own_entry[3]:
        if kind == "r":
            continue  # 영역 사본은 check_regions
        if tgt == rel and kind == "f":
            continue  # 자기 경로를 적은 표시는 원본 표시
        path, sib, which = resolve(root, tgt)
        if sib:
            res.append((ln, None, "sibling", tgt, False))
            continue
        if kind == "f":
            try:
                same = open(path, "rb").read() == text.encode("utf-8")
            except OSError:
                res.append((ln, f"{rel}:{ln}: @copy-of {tgt} does not resolve. Fix the copy or the mark.{which}", "unresolved", tgt, True))
                continue
            touched = bool(added_lines)
            if same:
                res.append((ln, None, "ok", tgt, False))
            else:
                res.append((ln, f"{rel}:{ln}: @copy-of {tgt} differs from this copy. Edit the source, then copy it over.{which}", "differs", tgt, touched))
            continue
        mine = next((s for s in own_entry[2] if s[4] == f"{tgt}#{name}"), None)
        srcsets = sets_of_file(root, tgt if tgt in ents else path, ents) if os.path.exists(path) else None
        src = next((s for s in (srcsets or []) if s[1] == name), None)
        touched = (bool(mine) and (mine[0] - 1) in added_lines) or (ln - 1) in added_lines
        if src is None:
            res.append((ln, f"{rel}:{ln}: @copy-of {tgt}#{name} does not resolve (no such file or name). Fix the copy or the mark.{which}", "unresolved", tgt, touched))
        elif mine is None:
            res.append((ln, None, "ok", tgt, False))
        elif mine[3] != src[3]:
            a, b = sorted(set(src[3]) - set(mine[3])), sorted(set(mine[3]) - set(src[3]))
            res.append((ln, f"{rel}:{ln}: @copy-of {tgt}#{name} differs: missing {shown(a) or 'none'}, extra {shown(b) or 'none'}. Fix the copy or the mark.{which}",
                        "differs", tgt, touched))
        else:
            res.append((ln, None, "ok", tgt, False))
    return res


def check_regions(root, rel, path, text, added_lines):
    """C1 영역 사본. check_copies 와 같은 모양의 결과. 정본 영역은 건너뛴다."""
    if "@start-replace" not in text and "@end-replace" not in text:
        return []
    regions, errors = copy_regions.parse_regions(text)
    res = [(ln, f"{rel}:{ln}: copy marker: {msg}. Fix the marker.", "unresolved", "", (ln - 1) in added_lines) for ln, msg in errors]
    lines = text.split("\n")
    for r in regions:
        if copy_regions.is_canon(r, path, (root,)):
            continue
        tgt = f"{r['path']}#{r['name']}"
        touched = any(r["start"] <= k <= r["end"] for k in added_lines)
        top = r["path"].split("/")
        if top[0] == ".." and len(top) > 1 and not os.path.isdir(os.path.join(root, "..", top[1])):
            res.append((r["line"], None, "sibling", tgt, False))  # 형제 저장소가 이 기계에 없다
            continue
        try:
            want = copy_regions.expected(r, path, (root,))
        except copy_regions.MarkError as e:
            res.append((r["line"], f"{rel}:{r['line']}: @start-replace {tgt} does not resolve ({e}). Fix the copy or the mark.", "unresolved", tgt, touched))
            continue
        if want == copy_regions.body(lines, r):
            res.append((r["line"], None, "ok", tgt, False))
        else:
            res.append((r["line"], f"{rel}:{r['line']}: @start-replace {tgt} differs from its canon. {SYNC_HINT}", "differs", tgt, touched))
    return res


def canon_regions_touched(rel, path, text, added_lines, root):
    """이 파일의 정본 영역 중 추가한 줄이 든 것의 이름."""
    if "@start-replace" not in text:
        return set()
    return {r["name"] for r in copy_regions.parse_regions(text)[0]
            if copy_regions.is_canon(r, path, (root,)) and any(r["start"] < k < r["end"] for k in added_lines)}


def source_copies(rel, ents, prev, now, touched_file, touched_regions=frozenset(), now_marks=None):
    """C2. 이 파일이 원본인 사본 목록 [(이름, [사본 rel:줄...], 줄)]. 묶음은 원소가 바뀐 때만, 파일은 추가한 줄이 있을 때."""
    by, regions = {}, {}
    for orel, e in ents.items():
        for ln, tgt, name, kind in e[3]:
            if orel == rel or rel_target(tgt) != rel:
                continue
            if kind == "r":
                regions.setdefault(name, []).append(f"{orel}:{ln}")
                continue
            by.setdefault((name if kind == "v" else None), []).append(f"{orel}:{ln}")
    out = []
    for name, copies in regions.items():
        if name in touched_regions:
            out.append((name, copies, next((m[0] for m in (now_marks or []) if m[3] == "r" and m[2] == name), 1)))
    for name, copies in by.items():
        if name is None:
            if touched_file:
                out.append((os.path.basename(rel), copies, 1))
            continue
        cur = next((s for s in now if s[1] == name), None)
        old = next((s for s in (prev or []) if s[1] == name), None)
        if cur and (old is None or old[3] != cur[3]):
            out.append((name, copies, cur[0]))
    return out


# ---------- 표시 자리와 꼴(M1) ----------
# 표시는 줄 주석에 둔다. 문서 주석(Rust ///, /** */, Luau --- 와 --[=[ ]=])은 문서 도구가 표시를 싣거나 태그로 읽고,
# 영역 표시는 copy_regions.MARK 꼴의 줄만 읽힌다. 형제 저장소는 @copy-of 가 <저장소>:<경로>, @start-replace 가 ../<저장소>/<경로> 다.
MARK_WORD = re.compile(r"@(copy-of|start-replace|end-replace)(?![\w-])")
COPY_AT = re.compile(r"@copy-of:[ \t]*([A-Za-z0-9_.][^\s`'\"<>]*)")
REGION_PATH = re.compile(r"@start-replace:[ \t]*([^\s#]+)#")
MIXED_COPY = re.compile(r"^\.\./([\w.-]+):([^/\\].*)$")
COLON_REGION = re.compile(r"^(?:\.\./)?([\w.-]+):([^/\\].*)$")
JSON_EXT = {".json", ".jsonc"}
BLOCKISH = ("block", "doc", "html")


def opener_kind(prefix, seg, fam):
    """주석 조각의 종류: line, docline(줄 문서 주석), block, doc(블록 문서 주석), html. prefix 는 조각 앞 글(여는 표식으로 끝난다), seg 는 조각 본문."""
    if prefix.endswith("<!--"):
        return "html"
    if fam == "lua":
        m = re.search(r"--\[(=*)\[$", prefix)
        if m:
            return "doc" if m.group(1) else "block"
        return "docline" if seg.startswith("-") and not seg.startswith("--") else "line"
    if prefix.endswith("/*"):
        return "doc" if (seg.startswith("*") and not seg.startswith("*/")) or (fam == "rust" and seg.startswith("!")) else "block"
    if fam == "rust" and prefix.endswith("//") and seg.startswith("/") and not seg.startswith("//"):
        return "docline"
    return "line"


def comment_kinds(text, fam):
    """줄마다 [(시작 열, 끝 열, 종류)]. 줄 끝까지 열린 블록의 종류는 다음 줄로 잇는다."""
    out, carry = [], None
    rows = lex(text, fam, keep_code=True)
    for k, s in enumerate(text.split("\n")):
        segs = []
        for a, b in rows[k]["s"]:
            kind = carry if (a == 0 and carry) else opener_kind(s[:a], s[a:b], fam)
            segs.append((a, b, kind))
        if segs and segs[-1][1] == len(s):
            carry = segs[-1][2] if segs[-1][2] in BLOCKISH else None
        elif k + 1 < len(rows) and rows[k + 1]["in"] and re.search(r"(?:--\[=*\[|/\*|<!--)$", s):
            carry = opener_kind(s, "", fam)  # 여는 표식이 줄 끝이면 조각이 없다
        elif segs or not rows[k]["in"]:
            carry = None  # 빈 줄은 열린 블록을 잇는다
        out.append(segs)
    return out


def mark_text(s, p):
    """줄 s 의 p 에서 시작하는 표시 글(닫는 주석 표식 앞까지)."""
    return re.split(r"\*/|\]=*\]|-->", s[p:], maxsplit=1)[0].rstrip()


def line_comment(text, fam):
    return "%s %s" % ("--" if fam == "lua" else "#" if fam == "py" else "//", text)


def marker_notes(rel, ext, text, added):
    """M1. 추가한 줄의 표시가 읽히지 않거나 문서에 실리는 자리, 섞인 형제 저장소 꼴. [(줄, 알림)]."""
    fam = FAMILY.get(ext, "c")
    lines = text.split("\n")
    todo = [i for i in sorted(added) if i < len(lines) and MARK_WORD.search(lines[i])]
    if not todo:
        return []
    kinds = comment_kinds(text, fam)
    out = []
    for i in todo:
        s = lines[i]
        m = MARK_WORD.search(s)
        mk, p, ln = "@" + m.group(1), m.start(), i + 1
        seg = next(((a, b, k) for a, b, k in kinds[i] if a <= p <= b), None)
        if seg is None:
            # 파이썬 독스트링의 표시는 머리 10줄 안(파일 사본)에서만 읽힌다
            bare = s.lstrip().lstrip("rRbBuU").lstrip("\"'").lstrip()
            if fam == "py" and i >= copy_regions.HEADER_LINES and bare.startswith(mk) and (mk != "@copy-of" or COPY_AT.match(bare)):
                out.append((ln, f"{rel}:{ln}: the {mk} marker is inside a docstring past the first 10 lines, where it is not read. "
                                f"Put it in a line comment above the copied lines: `{line_comment(mark_text(bare, 0), fam)}`."))
            continue
        a, _, kind = seg
        if s[a:p].strip(" \t" + ("*!" if kind in BLOCKISH else "/!-")):
            continue  # 주석 글 중간에 든 이름(설명, 인용한 예)은 표시가 아니다
        if mk == "@copy-of" and not COPY_AT.match(s, p):
            continue
        body = mark_text(s, p)
        fix = line_comment(body, fam)
        if kind in ("doc", "docline"):
            out.append((ln, f"{rel}:{ln}: the {mk} marker is in a doc comment, which documentation tools publish or read as a doc tag. "
                            f"Move it to a plain line comment: `{fix}`."))
        elif kind == "html" and mk == "@copy-of":
            out.append((ln, f"{rel}:{ln}: the @copy-of marker is in an HTML comment, which can reach the built page. "
                            f"In an Astro template write `{{/* {body} */}}`; in the frontmatter or a script, `{fix}`."))
        elif mk != "@copy-of" and not copy_regions.MARK.match(s):
            out.append((ln, f"{rel}:{ln}: this {mk} is not read as a region marker: a region marker sits alone on a line comment "
                            f"(`#`, `//`, `--`), e.g. `{fix}`."))
        elif mk == "@copy-of":
            tgt = COPY_AT.match(s, p).group(1).rstrip(".,;)*/}")
            mm = MIXED_COPY.match(tgt)
            if mm:
                out.append((ln, f"{rel}:{ln}: @copy-of {tgt} mixes the two sibling-repo forms. @copy-of names a sibling repo as "
                                f"`<repo>:<path>` (`{mm.group(1)}:{mm.group(2)}`); `../<repo>/<path>` is the @start-replace form."))
        elif mk == "@start-replace":
            rp = REGION_PATH.search(s, p)
            mm = COLON_REGION.match(rp.group(1)) if rp else None
            if mm:
                out.append((ln, f"{rel}:{ln}: @start-replace {rp.group(1)} uses the `<repo>:<path>` form, which only @copy-of reads. "
                                f"A region names a sibling repo by its path from this repo's root: `../{mm.group(1)}/{mm.group(2)}`."))
    return out


def json_marker_note(rel, text, added):
    """JSON 에는 표시를 둘 주석이 없고 이 훅도 읽지 않는다. 첫 줄 하나만 알린다."""
    lines = text.split("\n")
    for i in sorted(added):
        if i < len(lines) and (COPY_AT.search(lines[i]) or "@start-replace:" in lines[i]):
            return (f"{rel}:{i + 1}: JSON cannot hold a copy marker, and nothing reads one here. Drop it and name the source "
                    f"in the code that reads this file or in the test that compares it with the source.")
    return None


# ---------- 기록 ----------

def shadow_log(rec):
    """한 줄 더한다. 짝 없는 서로게이트가 든 기록은 쓰지 못해 건너뛴다."""
    d = os.environ.get("CLAUDE_PLUGIN_DATA") or os.path.join(tempfile.gettempdir(), "claude-qwreey-reuse")
    try:
        line = (json.dumps(rec, ensure_ascii=False) + "\n").encode("utf-8")
    except UnicodeEncodeError:
        return
    try:
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "reuse-shadow.jsonl" if os.environ.get("CLAUDE_PLUGIN_DATA") else "shadow.jsonl"), "ab") as f:
            f.write(line)
    except OSError:
        pass


def record_report(data, path, rel, dup, differ):
    """턴 끝 보고용: 이 파일의 전부터 있던 중복 수와 어긋난 사본 수. 같은 파일은 마지막 편집 기준으로 덮어쓰고 0이면 지운다."""
    try:
        d = os.path.join(tempfile.gettempdir(), NS)
        os.makedirs(d, exist_ok=True)
        who = re.sub(r"[^\w-]", "", str(data.get("agent_id"))) if data.get("agent_id") else "main"
        fp = os.path.join(d, re.sub(r"[^\w-]", "", str(data.get("session_id") or "nosession")) + ".reuse." + who + ".json")
        try:
            rec = json.load(open(fp))
        except (OSError, ValueError):
            rec = {}
        key = os.path.abspath(path)
        if dup or differ:
            rec[key] = {"rel": rel, "dup": dup, "differ": differ, "t": time.time()}
        elif key in rec:
            del rec[key]
        else:
            return
        data = json.dumps(rec, ensure_ascii=False).encode("utf-8")  # 서로게이트가 들면 여기서 끝나 옛 파일이 남는다
        with open(fp, "wb") as f:
            f.write(data)
    except Exception:
        pass


def main():
    import conv_env  # 끄기 스위치는 harness.env 층과 /config 옵션에서도 읽는다
    if conv_env.is_off("CONVENTIONS_CHECK"):
        return 0
    try:
        data = json.load(sys.stdin)
    except ValueError:
        return 0
    tool = data.get("tool_name") or ""
    ti = data.get("tool_input") or {}
    path = ti.get("file_path") or ""
    ext = os.path.splitext(path)[1].lower()
    is_json = ext in JSON_EXT
    if tool not in ("Write", "Edit", "MultiEdit") or not (ext in RULE_EXT or is_json):
        return 0
    root = project_root(path, data)
    rel = os.path.relpath(path, root)
    if is_json and any(p in SKIP_DIRS or "-ignoreme" in p for p in rel.split("/")[:-1]):
        return 0
    if rel.startswith("..") or not (is_json or indexable(rel, [])) or os.path.getsize(path) > MAX_BYTES:
        return 0
    d = os.path.dirname(rel)
    while d:  # 벤더 트리는 표시도 검사도 하지 않는다
        if os.path.exists(os.path.join(root, d, "vendor.lock.json")):
            return 0
        d = os.path.dirname(d)
    cfg = load_cfg(root)
    mode = mode_of(cfg)
    if mode == "off" or allowed(rel, cfg):
        return 0
    try:
        text = open(path, encoding="utf-8").read()
    except (OSError, UnicodeDecodeError):
        return 0
    resp = data.get("tool_response") if isinstance(data.get("tool_response"), dict) else {}
    got = collect(tool, ti, resp, text)
    if not got:
        return 0
    text, added = got
    if GEN.search("\n".join(text.split("\n", 6)[:6])):
        return 0

    sid, agent = data.get("session_id"), data.get("agent_id")
    sp = compact_epoch.state_path(NAME, "claude-reuse", sid, agent)
    try:
        state = json.load(open(sp))
    except (OSError, ValueError):
        state = {}
    seen = state.setdefault("seen", [])
    notes = []

    # M1 marker placement and sibling forms
    if is_json:
        note = json_marker_note(rel, text, added)
        if note and f"m:{rel}:json" not in seen:
            seen.append(f"m:{rel}:json")
            emit(sid, sp, state, [note])
        return 0
    flagged = set()
    for ln, msg in marker_notes(rel, ext, text, added):
        flagged.add(ln)
        if f"m:{rel}:{ln}" not in seen:
            seen.append(f"m:{rel}:{ln}")
            notes.append(msg)

    files = list_files(root)
    if len(files) > MAX_FILES:  # 편집한 파일의 패키지 안만 본다(패키지 밖 중복은 못 본다)
        pk = package_of(root, rel, {})
        files = [f for f in files if f.startswith(pk + "/")] if pk else files[:MAX_FILES]
    idx, dirty, cut = load_index(root, files, rel)
    ents = idx["files"]
    prev = ents.get(rel)
    try:
        own = read_entry(root, rel, text, deadline=T0 + HARD_MS / 1000)
    except Budget:  # 편집한 파일을 한도 안에 다 읽지 못했다: 판정 없이 지금까지 읽은 색인만 남긴다
        if dirty:
            save_index(root, idx)
        return 0
    ents[rel] = own
    if dirty or prev is None or prev[2:] != own[2:]:
        save_index(root, idx)

    pkg_cache = {}
    log = []

    def log_rec(check, notice, st, hit, extra=None):
        r = {"id": sha1_12(f"{rel}:{st[0] if st else 0}:{check}:{notice}"), "t": int(time.time()),
             "repo": os.path.basename(root), "lang": LANG.get(ext), "check": check, "notice": notice, "at": f"{rel}:{st[0] if st else 0}"}
        if hit:
            r.update({"other": f"{hit[1]}:{hit[2]}", "name": st[1], "shared": [x[:40] for x in sorted(hit[4])[:8]], "k": hit[5], "n": hit[6],
                      "j": round(hit[7], 2), "signals": {"def": [bool(st[2] & FLAG_DEF), bool(hit[8] & FLAG_DEF)],
                                                         "type": [bool(st[2] & FLAG_TYPE), bool(hit[8] & FLAG_TYPE)]}})
        r.update(extra or {})
        log.append(r)

    # C1
    differ = 0
    for ln, msg, status, tgt, touched in check_copies(root, rel, text, own, ents, added) + check_regions(root, rel, path, text, added):
        if status in ("differs", "unresolved"):
            differ += 1
        if msg and touched and ln not in flagged:  # 꼴 알림(M1)이 같은 줄의 고칠 것을 이미 말했다
            key = f"c1:{rel}:{ln}:{status}"
            if key not in seen:
                seen.append(key)
                notes.append(msg)
        if status != "ok":
            log_rec("C1", "N4" if msg else "none", None, None, {"status": status})
    # C2
    now = own[2]
    for name, copies, ln in source_copies(rel, ents, prev[2] if prev else None, now, bool(added),
                                          canon_regions_touched(rel, path, text, added, root), own[3]):
        key = f"c2:{rel}:{name}"
        if key not in seen:
            seen.append(key)
            notes.append(f"{rel}:{ln}: {name} has {len(copies)} @copy-of copies: {', '.join(copies[:5])}"
                         f"{' +%d' % (len(copies) - 5) if len(copies) > 5 else ''}. If this change altered what they copy, update them too (python3 -I tools/sync-copies.py --apply where the repo has it).")
            log_rec("C2", "N3", None, None, {"name": name, "copies": len(copies)})
    # H1
    dup_old = 0
    if ext in H1_EXT and (time.perf_counter() - T0) * 1000 < HARD_MS:
        prev_els = {frozenset(s[3]) for s in prev[2]} if prev else None
        for st in now:
            if (time.perf_counter() - T0) * 1000 > HARD_MS:
                break
            hits = judge(root, rel, st, ents, cfg, pkg_cache)
            if not hits:
                continue
            is_new = (frozenset(st[3]) not in prev_els) if prev_els is not None else ((st[0] - 1) in added)
            if not is_new:
                dup_old += 1
                continue
            hit = max(hits, key=lambda h: h[7])
            msg = text_of(hit[0], rel, st, hit)
            if st[5] is not None and not reason_ok(st[5]):
                msg += f' @dup-ok at {rel}:{st[0]} has no reason ("{st[5]}").'
            log_rec("H1", hit[0], st, hit)
            key = f"h1:{rel}:{hit[1]}:{hit[2]}"
            if mode == "on" and key not in seen and state.setdefault("n", {}).get(rel, 0) < MAX_NOTICES_PER_FILE:
                seen.append(key)
                state["n"][rel] = state["n"].get(rel, 0) + 1
                notes.append(msg)
    ms = round((time.perf_counter() - T0) * 1000)
    for r in log:
        r["ms"] = ms
        r["budget"] = bool(cut or ms > WARM_BUDGET_MS)
        shadow_log(r)
    record_report(data, path, rel, dup_old if mode == "on" else 0, differ)
    emit(sid, sp, state, notes)
    return 0


def emit(sid, sp, state, notes):
    """상태를 저장하고, 알림이 있으면 한 블록으로 낸다."""
    try:
        json.dump(state, open(sp, "w"))
    except OSError:
        pass
    if notes:
        msg = f'<harness-hook name="{NAME}" level="info"{harness_nonce.attr(sid)}>{"; ".join(notes)}</harness-hook>'
        json.dump({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": msg}}, sys.stdout, ensure_ascii=False)


if __name__ == "__main__":
    sys.exit(main())
