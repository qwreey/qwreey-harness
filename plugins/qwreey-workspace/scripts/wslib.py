"""workspace 게이트, 지도, 알림이 같이 쓰는 도우미(표준 라이브러리만).

- 다른 저장소: 경로를 담은 git 저장소(known_repos.repo_root, worktree 는 본 저장소로)가 이 세션의 저장소와 다른 것. 작업공간 폴더를
  정하게 하지 않는다: 프로젝트를 두는 곳은 사람과 OS 마다 다르다. 다만 임시 폴더, ~/.cache 같은 known_repos 의 기본 제외와
  사용자가 HARNESS_WORKSPACE_EXCLUDE 로 뺀 저장소는 다른 저장소로 보지 않는다(시험이나 실측으로 잠깐 만든 저장소를 지키지 않게).
- 경로 판정은 normpath 만 한다(realpath 금지: ~/.claude/rules 의 symlink 는 형제 경로가 아니라 이 세션의 규칙 파일이다).
- Bash 명령 분류: 어떤 형제 저장소를 쓰는가("write"), 읽는가("read"). 하네스의 bash-bypass-reminder 분류기는
  경로를 보지 않고 코드 확장자 리다이렉트와 sed -i 만 쓰기로 보므로(.claude/audit/31 probes.md §2) 경로를 보는 분류기를 따로 둔다.
"""
from __future__ import annotations

import os
import re
import shlex
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # python3 -I 는 스크립트 디렉터리를 path 에 넣지 않는다
import known_repos  # noqa: E402

PREFIX = {"(", "{", "time", "nice", "env", "command", "exec", "nohup", "sudo", "choom", "prlimit", "timeout", "--", "builtin"}
INTERP = {"python", "python3", "node", "deno", "bun", "perl", "ruby", "lua", "luau", "lune", "lute"}
WRITE_ALL = {"rm", "rmdir", "mv", "touch", "mkdir", "truncate", "chmod", "chown", "shred", "unlink", "tee", "patch", "mkfifo"}
WRITE_LAST = {"cp", "install", "ln", "rsync", "scp"}
GIT_WRITE = {"commit", "add", "rm", "mv", "checkout", "switch", "reset", "restore", "push", "merge", "rebase", "cherry-pick",
             "clean", "apply", "am", "pull", "revert", "init", "clone"}
INPLACE = re.compile(r"\bsed\s+(-\S*\s+)*-\S*i|\bperl\s+(-\S*\s+)*-\S*i|\bawk\s+-i\s+inplace|\bgit\s+apply\b|\bdd\b.*\bof=")
SCRIPT_WRITE = re.compile(r"""['"][wa]\+?b?['"]|write|unlink|rmtree|rename|\.replace\(|copyfile|appendFile|\bmkdir""")
REDIR = re.compile(r"(?<![0-9&<>])\d?>>?(?!&)\s*([^\s;|&<>()]+)")
ABS = re.compile(r"(?:~|\$\{?HOME\}?|/)[^\s'\";|&<>()=]*")


# 이 플러그인만 읽는 harness.env 키. 켜기, 끄기 스위치는 userConfig 옵션(소문자 이름)으로도 정한다(plugin.json 의 default 와 같아야 한다).
ENV_DEFAULTS = {
    # workspace_gate.py: 다른 저장소 쓰기 게이트. off 면 끈다. 사용자 층과 옵션만 정한다(ENV_USER_ONLY).
    "HARNESS_WORKSPACE_GATE": "on",
    # stale_worktrees.py: 세션 시작에 이 저장소의 오래된 worktree 를 알린다. off 면 끈다. 저장소 층도 정할 수 있다.
    "HARNESS_WORKSPACE_STALE_WORKTREES": "on",
    # stale_worktrees.py: 세션 시작에 알리는 오래된 worktree 의 문턱(일, 손대지 않은 기간). off 나 0 이면 끈다. 저장소 층도 정할 수 있다.
    "HARNESS_WORKSPACE_STALE_WORKTREE_DAYS": "14",
    # sibling_notice.py: 기록에 형제 저장소 내부 경로를 쓰면 알린다. off 면 끈다. 저장소 층도 정할 수 있다.
    "HARNESS_WORKSPACE_SIBLING_NOTICE": "on",
}
# 게이트를 끄거나 비켜 가게 하는 키(뒤 둘은 known_repos.KNOWN_REPOS_USER_ONLY 와 같다). 클론한 저장소가 커밋한 파일로 게이트를 끄거나 저장소를 빼면 안 된다.
ENV_USER_ONLY = frozenset({"HARNESS_WORKSPACE_GATE", "HARNESS_WORKSPACE_EXTRA", "HARNESS_WORKSPACE_EXCLUDE"})


def load_env(cwd: str | None = None) -> dict:
    """harness.env 층 값(harness_env.load_layers: 사용자 < 저장소 < 저장소 local < 환경 변수). 읽기 실패는 빈 dict.
    늘 옆의 harness_env.py 사본을 쓴다: 설치된 ~/.claude/lib 판은 옛 판일 수 있어 ENV_USER_ONLY 를 모른다."""
    try:
        import harness_env
        return harness_env.load_layers(harness_env.project_dir(cwd), defaults={**known_repos.KNOWN_REPOS_DEFAULTS, **ENV_DEFAULTS},
                                       user_only=ENV_USER_ONLY)
    except Exception:
        return {}


def setting(key: str, vals: dict | None = None) -> str:
    if key in os.environ:
        return os.environ[key]
    return (vals if vals is not None else load_env()).get(key, "") or ""


def shown(path: str) -> str:
    """모델에게 보일 경로. 홈 아래는 `~/` 꼴로 줄인다(메시지마다 홈 경로를 되풀이하지 않게)."""
    home = os.path.expanduser("~")
    if home and home != os.sep and (path == home or path.startswith(home.rstrip(os.sep) + os.sep)):
        return "~" + path[len(home):].replace(os.sep, "/")
    return path


def is_off(key: str, vals: dict | None = None) -> bool:
    return setting(key, vals).strip().lower() in ("off", "0", "no", "false")


def expand(p: str) -> str:
    home = os.path.expanduser("~")
    # 바꿀 글을 함수로 준다: 글로 주면 re 가 그 안의 `\` 를 escape 로 읽어 Windows 홈(C:\Users)에서 re.error 로 끝난다
    p = re.sub(r"^\$\{?HOME\}?", lambda _: home, p)
    return os.path.expanduser(p) if p.startswith("~") else p


def norm(p: str, cwd: str) -> str:
    p = expand(p)
    if not os.path.isabs(p):
        p = os.path.join(cwd or "/", p)
    return os.path.normpath(p)


def inside(p: str, root: str) -> bool:
    # Windows 는 normpath 뒤 구분자가 백슬래시이고 대소문자를 가리지 않는다. 양쪽을 normcase 하고 두 구분자를 모두 받는다.
    p, root = os.path.normcase(p), os.path.normcase(root).rstrip("/\\")
    return p == root or p.startswith(root + os.sep) or p.startswith(root + "/")


def _own_config(root: str) -> bool:
    """홈 폴더나 Claude Code 설정 폴더 자체가 git 저장소(dotfiles)면 그 저장소는 '다른 저장소'가 아니다.
    memory, 계획, 설정 쓰기가 스킬 전까지 막히면 안 된다."""
    cfg = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude")
    r = os.path.normcase(os.path.normpath(root))
    return r == os.path.normcase(os.path.normpath(os.path.expanduser("~"))) or inside(r, os.path.normpath(cfg))


class Scope:
    """이 세션의 저장소에서 본 "다른 저장소" 판정. 한 훅 실행 안에서 같은 경로를 두 번 걷지 않게 결과를 기억한다.
    exclude 가 None 이면 known_repos 의 기본 제외와 사용자 제외(HARNESS_WORKSPACE_EXCLUDE)를 쓴다. 사용자 제외는 다른 저장소 후보가
    처음 나올 때 load(설정 읽기)를 불러 얻는다: 대부분의 호출은 이 세션 저장소 안 경로라 설정을 읽지 않고 끝난다."""

    def __init__(self, project: str, exclude=None, load=None):
        self.project = os.path.normpath(project) if project else ""
        self.own = os.path.normcase(known_repos.repo_root(self.project) or "") if self.project else ""
        self._exclude = None if exclude is None else list(exclude)
        self._load = load or load_env
        self.vals = None
        self._memo: dict[str, str | None] = {}

    def settings(self) -> dict:
        if self.vals is None:
            self.vals = self._load()
        return self.vals

    def exclude(self) -> list:
        if self._exclude is None:
            self._exclude = known_repos.default_exclude() + known_repos._split(self.settings().get("HARNESS_WORKSPACE_EXCLUDE", ""))
        return self._exclude

    def sibling(self, path: str) -> str | None:
        """path(normpath)를 담은 저장소가 이 세션의 저장소가 아니면 그 저장소 루트, 아니면 None."""
        if not path or (self.project and inside(path, self.project)):
            return None
        if path not in self._memo:
            root = known_repos.repo_root(path)
            if not root or os.path.normcase(root) == self.own:
                root = None
            elif _own_config(root) or known_repos.excluded(root, self.exclude()):
                root = None
            self._memo[path] = root
        return self._memo[path]


def _segments(cmd: str):
    return [s for s in re.split(r"&&|\|\||[;|\n]", cmd) if s.strip()]


def _head(words):
    i = 0
    while i < len(words) and (words[i] in PREFIX or re.fullmatch(r"[A-Za-z_]\w*=\S*", words[i])
                              or words[i].startswith("-") or re.fullmatch(r"[\d.]+[smhd]?", words[i])):
        i += 1
    return i


def _git_writes(args) -> bool:
    sub, rest = None, []
    i = 0
    while i < len(args):
        a = args[i]
        if a in ("-C", "-c", "--git-dir", "--work-tree"):
            i += 2
            continue
        if a.startswith("-"):
            i += 1
            continue
        sub, rest = a, args[i + 1:]
        break
    if sub is None:
        return False
    if sub in GIT_WRITE:
        return True
    if sub == "stash":
        return not rest or rest[0] in ("push", "pop", "apply", "drop", "save", "clear", "branch")
    if sub == "worktree":
        return bool(rest) and rest[0] in ("add", "remove", "prune", "move", "lock", "unlock")
    if sub in ("branch", "tag"):
        return any(r in ("-d", "-D", "-m", "-M", "-f", "--delete") for r in rest)
    return False


def classify_bash(cmd: str, cwd: str, scope: Scope):
    """(kind, X). kind 는 "write" | "read" | None, X 는 다른 저장소 루트. 다른 저장소를 건드리지 않으면 (None, None)."""
    found: dict[str, str] = {}  # X -> "read"|"write"

    def hit(x, kind):
        if x and found.get(x) != "write":
            found[x] = kind

    cur = cwd or scope.project or "/"
    for seg in _segments(cmd):
        try:
            words = shlex.split(seg, posix=True)
        except ValueError:
            words = seg.split()
        words = [w for w in words if w]
        if not words:
            continue
        hi = _head(words)
        if hi >= len(words):
            continue
        head = os.path.basename(words[hi])
        args = words[hi + 1:]
        if head in ("cd", "pushd"):
            tgt = next((a for a in args if not a.startswith("-")), "~")
            cur = norm(tgt, cur)
            hit(scope.sibling(cur), "read")
            continue
        seg_cwd = cur
        if head == "git":
            for j, a in enumerate(args[:-1]):
                if a == "-C":
                    seg_cwd = norm(args[j + 1], cur)
        redirs = [m.group(1) for m in REDIR.finditer(seg)]
        write_tokens = list(redirs)
        whole = False
        if head in WRITE_ALL or INPLACE.search(seg):
            whole = True
        elif head in WRITE_LAST:
            pos = [a for a in args if not a.startswith("-")]
            write_tokens += pos[-1:]
        elif head == "git" and _git_writes(args):
            whole = True
        elif head in INTERP and SCRIPT_WRITE.search(seg):
            whole = True
        # 이 세그먼트가 만지는 경로들
        cands = []
        for w in args + redirs:
            cands.append(w)
            cands += ABS.findall(w)
        # 처음 나온 순서로(dict): 두 저장소를 건드리면 먼저 나온 쪽을 알린다. set 이면 해시 순서라 실행마다 달랐다
        touched: dict[str, None] = {}
        for w in cands:
            if "/" in w or w.startswith(("~", "$HOME", "${HOME}", ".")) or w in redirs:
                touched[norm(w, seg_cwd)] = None
        for m in ABS.findall(seg):
            touched[norm(m, seg_cwd)] = None
        wt = {norm(w, seg_cwd) for w in write_tokens if w}
        x_cwd = scope.sibling(seg_cwd)
        if x_cwd and (args or redirs):
            def rel(w):
                return not os.path.isabs(expand(w)) and not w.startswith("~")
            # A whole-command write counts against the cwd repo only if it has a relative
            # argument; `cd sib && rm /abs/own/file` writes our repo, not the sibling.
            rel_args = [a for a in args if not a.startswith("-") and rel(a)]
            relative_write = any(rel(w) for w in write_tokens) or (whole and bool(rel_args))
            hit(x_cwd, "write" if relative_write else "read")
        for p in touched:
            x = scope.sibling(p)
            if x:
                hit(x, "write" if whole or p in wt else "read")
    for x, k in found.items():
        if k == "write":
            return "write", x
    for x, k in found.items():
        return "read", x
    return None, None
