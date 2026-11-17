"""이 기기에서 Claude Code 로 일한 저장소 목록. 표준 라이브러리만 쓴다.
@copy-of: lib/known_repos.py
플러그인 사본(qwreey-workspace/scripts, qwreey-conventions/hooks)은 바이트가 같아야 한다. 옆의 harness_env.py 사본으로 설정을 읽는다.
고칠 때는 lib/known_repos.py 만 고치고 python3 -I tools/sync-copies.py --apply 로 사본에 옮긴다.

왜: 프로젝트를 어디에 두는지는 사람과 OS 마다 다르다(Windows 는 문서함, 바탕 화면 등). 작업공간 폴더 하나를 정하게 하는 대신
Claude Code 가 이미 남긴 세션 기록의 cwd 로 저장소를 모으고, 사람은 옵션으로 더하거나 뺀다.

출처(합집합, 그다음 제외):
1. <설정 디렉터리>/projects/*/ 마다 가장 최근 *.jsonl 하나의 앞부분(HEAD_BYTES)에서 처음 나오는 "cwd". 프로젝트 폴더 이름이
   cwd 에서 나오므로 한 폴더의 세션은 cwd 가 같아 하나만 읽는다. cwd 에서 위로 올라가 `.git` 이 있는 곳이 저장소 루트다.
2. HARNESS_WORKSPACE_EXTRA(`;` 구분): 저장소 경로, 또는 바로 아래 자식 저장소를 모두 넣을 폴더.
3. HARNESS_WORKSPACE(옛 설정, 사용자 harness.env 나 환경 변수): 바로 아래 자식 저장소.
4. HARNESS_WORKSPACE_EXCLUDE(`;` 구분 경로 또는 glob)로 뺀다. 경로는 그 저장소와 그 아래를, glob 은 저장소 경로 전체에 맞춘다.
worktree(`.git` 파일의 gitdir 이 다른 저장소의 .git/worktrees/ 를 가리킴)는 본 저장소로 합친다. 없어진 경로는 뺀다.
2, 4 의 키는 qwreey-workspace 의 userConfig 옵션(harness_workspace_extra, harness_workspace_exclude)이다. 다른 플러그인(qwreey-conventions)이
불러도 같은 값을 보도록 options() 가 그 플러그인의 옵션을 읽는다. 셋 다 저장소 층(.claude/harness.env)은 바꾸지 못한다.

캐시: $CLAUDE_PLUGIN_DATA/known_repos.json(없으면 캐시 없음). projects/ 아래 폴더마다의 mtime(새 세션 파일이 생기면 바뀐다),
옵션 값, 2, 3 의 폴더 mtime 이 같으면 저장한 목록을 다시 쓴다(있는지만 다시 본다). 폴더 mtime 이 바뀐 projects/ 폴더만 다시 읽는다.
실측(2026-11-17, projects/ 폴더 569개 가운데 jsonl 이 있는 것 141개, 결과 저장소 82개, 캐시 35 KB): 캐시 적중 2.2 ms(중앙값),
캐시 없이 12 ms, 첫 수집(설정 읽기와 캐시 쓰기 포함) 16 ms, 모두 OS 파일 캐시가 데워진 상태. 모듈 import 는 1 에서 4 ms(json, fnmatch 가 처음일 때).

쓰는 법: repos() 는 정렬된 저장소 루트 절대 경로 목록. 값을 직접 넘기면(extra=, exclude=, workspace=) 설정을 읽지 않는다.
repo_root(path) 는 path 를 담은 저장소 루트(worktree 는 본 저장소로), 없으면 None.
"""
import fnmatch
import json
import os
import re
import stat

# 사용자 harness.env 와 qwreey-workspace 옵션에서 읽는 키. 기본값은 userConfig 의 default 와 같아야 한다(tools/tests/test-plugin-userconfig.py).
KNOWN_REPOS_DEFAULTS = {"HARNESS_WORKSPACE_EXTRA": "", "HARNESS_WORKSPACE_EXCLUDE": ""}
# 기기마다 다른 경로라 클론한 저장소가 커밋한 파일로 바꾸면 안 된다. HARNESS_WORKSPACE 는 로더가 막는다(RETIRED_USER_ONLY).
KNOWN_REPOS_USER_ONLY = frozenset({"HARNESS_WORKSPACE_EXTRA", "HARNESS_WORKSPACE_EXCLUDE"})
OPTION_OWNER = "qwreey-workspace"
CACHE_FILE = "known_repos.json"
CACHE_VERSION = 1
# 세션 파일 앞부분에서 cwd 를 찾는 한도. 이 기기 실측으로 첫 cwd 는 18 KB 안에 있었다(앞줄은 제목, 모드 같은 짧은 줄).
HEAD_BYTES = 256 * 1024
HEAD_FIRST = 32 * 1024
_CWD = re.compile(rb'"cwd"\s*:\s*"((?:[^"\\]|\\.)*)"')
_GLOB = re.compile(r"[*?\[]")


def config_dir():
    return os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude")


def options():
    """{HARNESS_WORKSPACE_EXTRA, HARNESS_WORKSPACE_EXCLUDE, HARNESS_WORKSPACE: 문자열}.
    층: 사용자 harness.env < qwreey-workspace 옵션 < 환경 변수. 저장소 층은 이 키들을 못 바꾸므로 읽지 않는다."""
    keys = (*KNOWN_REPOS_DEFAULTS, "HARNESS_WORKSPACE")
    try:
        import harness_env
        vals = harness_env.load_layers("", defaults=KNOWN_REPOS_DEFAULTS, user_only=KNOWN_REPOS_USER_ONLY,
                                       options={OPTION_OWNER: KNOWN_REPOS_USER_ONLY})
    except Exception:
        vals = dict(os.environ)
    return {k: str(vals.get(k) or "").strip() for k in keys}


def _split(value):
    return [os.path.expanduser(p.strip()) for p in str(value or "").split(";") if p.strip()]


def _git_entry(d):
    """d/.git 이 폴더면 'dir', 파일이면 'file', 없으면 None."""
    try:
        st = os.stat(os.path.join(d, ".git"))
    except OSError:
        return None
    return "dir" if stat.S_ISDIR(st.st_mode) else "file"


def _fold(d):
    """.git 이 파일인 d 를 본 저장소로. gitdir 이 <본>/.git/worktrees/<이름> 이면 <본>, 아니면(서브모듈 등) d. 본 저장소가 없으면 None."""
    try:
        with open(os.path.join(d, ".git"), encoding="utf-8", errors="replace") as f:
            line = f.readline().strip()
    except OSError:
        return None
    if not line.startswith("gitdir:"):
        return d
    gitdir = os.path.normpath(os.path.join(d, line[7:].strip()))
    parts = gitdir.replace("\\", "/").split("/")
    for i in range(len(parts) - 2, 0, -1):
        if parts[i] == ".git" and parts[i + 1] == "worktrees":
            main = os.path.normpath("/".join(parts[:i]) or "/")
            return main if _git_entry(main) == "dir" else None
    return d


def repo_root(path):
    """path(파일이나 폴더)를 담은 저장소 루트. worktree 는 본 저장소로 합친다. 없으면 None."""
    d = os.path.abspath(path)
    while True:
        kind = _git_entry(d)
        if kind == "dir":
            return d
        if kind == "file":
            return _fold(d)
        up = os.path.dirname(d)
        if up == d:
            return None
        d = up


def _cwd_of(folder):
    """projects/<폴더> 에서 가장 최근 jsonl 의 첫 cwd. 없으면 ''."""
    try:
        files = [(e.stat().st_mtime_ns, e.path) for e in os.scandir(folder) if e.name.endswith(".jsonl") and e.is_file()]
    except OSError:
        return ""
    # 가장 최근 파일에 cwd 가 아직 없으면(막 만들어진 세션) 그다음 파일을 본다. 셋까지만.
    for _, path in sorted(files, reverse=True)[:3]:
        try:
            with open(path, "rb") as f:
                # 대개 첫 수 KB 안에 있어 작게 먼저 읽는다. 없을 때만 한도까지 더 읽는다.
                head = f.read(HEAD_FIRST)
                m = _CWD.search(head)
                if not m and len(head) == HEAD_FIRST:
                    head += f.read(HEAD_BYTES - HEAD_FIRST)
                    m = _CWD.search(head)
        except OSError:
            continue
        if m:
            try:
                return json.loads(b'"' + m.group(1) + b'"')
            except ValueError:
                continue
    return ""


def _project_dirs(projects):
    """{projects/ 아래 폴더 이름: mtime_ns}."""
    out = {}
    try:
        for e in os.scandir(projects):
            if e.is_dir(follow_symlinks=False):
                try:
                    out[e.name] = e.stat(follow_symlinks=False).st_mtime_ns
                except OSError:
                    pass
    except OSError:
        pass
    return out


def _folder_repos(folder, self_ok):
    """folder 가 저장소면(self_ok 일 때) 그것, 아니면 바로 아래 자식 저장소들."""
    if self_ok and _git_entry(folder):
        r = repo_root(folder)
        return [r] if r else []
    out = []
    try:
        children = [e.path for e in os.scandir(folder) if e.is_dir()]
    except OSError:
        return out
    for c in children:
        kind = _git_entry(c)
        r = c if kind == "dir" else _fold(c) if kind == "file" else None
        if r:
            out.append(r)
    return out


def _excluded(root, patterns):
    r = os.path.normcase(root)
    for pat in patterns:
        if _GLOB.search(pat):
            if fnmatch.fnmatch(r, os.path.normcase(pat)) or fnmatch.fnmatch(root.replace("\\", "/"), pat.replace("\\", "/")):
                return True
            continue
        p = os.path.normcase(os.path.abspath(pat))
        if r == p or r.startswith(p.rstrip(os.sep) + os.sep):
            return True
    return False


def _mtime(path):
    try:
        return os.stat(path).st_mtime_ns
    except OSError:
        return None


def _cache_path(cache):
    if cache is None:
        data = os.environ.get("CLAUDE_PLUGIN_DATA")
        return os.path.join(data, CACHE_FILE) if data else ""
    return str(cache) if cache else ""


def _read_cache(path):
    if not path:
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) and data.get("version") == CACHE_VERSION else {}


def _write_cache(path, data):
    if not path:
        return
    tmp = "%s.%d.tmp" % (path, os.getpid())
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        os.replace(tmp, path)  # 다른 훅이 동시에 읽어도 반쯤 쓴 파일을 보지 않게
    except OSError:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def repos(extra=None, exclude=None, workspace=None, cfg=None, cache=None):
    """저장소 루트 절대 경로 목록(정렬). extra, exclude, workspace 가 None 이면 options() 에서 읽는다.
    cfg 는 설정 디렉터리(기본 $CLAUDE_CONFIG_DIR 또는 ~/.claude), cache 는 캐시 파일(None 이면 $CLAUDE_PLUGIN_DATA 아래, '' 이면 끔)."""
    if extra is None or exclude is None or workspace is None:
        o = options()
        extra = o["HARNESS_WORKSPACE_EXTRA"] if extra is None else extra
        exclude = o["HARNESS_WORKSPACE_EXCLUDE"] if exclude is None else exclude
        workspace = o["HARNESS_WORKSPACE"] if workspace is None else workspace
    projects = os.path.join(cfg or config_dir(), "projects")
    folders = [(f, True) for f in _split(extra)] + ([(os.path.expanduser(workspace.strip()), False)] if str(workspace or "").strip() else [])
    key = {"projects": projects, "extra": extra, "exclude": exclude, "workspace": workspace,
           "folders": [[f, _mtime(f)] for f, _ in folders]}
    dirs = _project_dirs(projects)
    path = _cache_path(cache)
    old = _read_cache(path)
    prev = old.get("dirs") if isinstance(old.get("dirs"), dict) else {}
    if old.get("key") == key and len(prev) == len(dirs) and all(prev.get(n, (None,))[0] == m for n, m in dirs.items()):
        return [r for r in old.get("repos", []) if isinstance(r, str) and os.path.isdir(r)]
    seen = {}
    for name, m in dirs.items():
        p = prev.get(name)
        cwd = p[1] if isinstance(p, list) and len(p) == 2 and p[0] == m else _cwd_of(os.path.join(projects, name))
        seen[name] = [m, cwd]
    found = [repo_root(cwd) for _, cwd in seen.values() if cwd and os.path.isdir(cwd)]
    for f, self_ok in folders:
        found += _folder_repos(f, self_ok)
    pats = _split(exclude)
    # 심볼릭 링크는 풀지 않는다: 사용자가 보는 경로(세션 cwd 와 같은 꼴)를 그대로 돌려준다. 비교하는 쪽도 같은 꼴로 비교한다.
    roots = {}
    for r in found:
        if r:
            r = os.path.normpath(r)
            roots.setdefault(os.path.normcase(r), r)
    out = sorted(r for r in roots.values() if os.path.isdir(r) and not _excluded(r, pats))
    _write_cache(path, {"version": CACHE_VERSION, "key": key, "dirs": seen, "repos": out})
    return out
