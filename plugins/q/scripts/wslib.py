"""workspace 게이트와 지도가 같이 쓰는 도우미(표준 라이브러리만).

- 작업공간 루트: 환경 변수 HARNESS_WORKSPACE, 없으면 harness.env(하네스 lib/harness_env.py 의 읽는 방식). 둘 다 없으면 "".
- 경로 판정은 normpath 만 한다(realpath 금지: ~/.claude/rules 의 symlink 는 형제 경로가 아니라 이 세션의 규칙 파일이다).
- Bash 명령 분류: 어떤 형제 저장소를 쓰는가("write"), 읽는가("read"). 하네스의 bash-bypass-reminder 분류기는
  경로를 보지 않고 코드 확장자 리다이렉트와 sed -i 만 쓰기로 보므로(audit/31 probes.md §2) 경로를 보는 분류기를 따로 둔다.
"""
from __future__ import annotations

import importlib.util
import os
import re
import shlex

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


def config_dir() -> str:
    return os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude")


def load_env() -> dict:
    """harness.env 값(환경 변수가 이김). 읽기 실패는 빈 dict."""
    cd = config_dir()
    try:
        spec = importlib.util.spec_from_file_location("harness_env", os.path.join(cd, "lib", "harness_env.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.load([os.path.join(cd, "harness.env")])
    except Exception:
        return {}


def setting(key: str, vals: dict | None = None) -> str:
    if key in os.environ:
        return os.environ[key]
    return (vals if vals is not None else load_env()).get(key, "") or ""


def workspace(vals: dict | None = None) -> str:
    ws = setting("HARNESS_WORKSPACE", vals).strip()
    return os.path.normpath(os.path.expanduser(ws)) if ws else ""


def expand(p: str) -> str:
    home = os.path.expanduser("~")
    p = re.sub(r"^\$\{?HOME\}?", home, p)
    return os.path.expanduser(p) if p.startswith("~") else p


def norm(p: str, cwd: str) -> str:
    p = expand(p)
    if not os.path.isabs(p):
        p = os.path.join(cwd or "/", p)
    return os.path.normpath(p)


def inside(p: str, root: str) -> bool:
    return p == root or p.startswith(root.rstrip("/") + "/")


def sibling_of(path: str, ws: str, project: str) -> str | None:
    """path 가 ws/<X> 안이고 X 가 이 세션의 저장소가 아니면 X. 아니면 None. path 는 이미 normpath."""
    if not ws or not inside(path, ws) or path == ws:
        return None
    x = path[len(ws):].lstrip("/").split("/", 1)[0]
    if not x or (project and inside(project, os.path.join(ws, x))) or (project and inside(path, project)):
        return None
    return x


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


def classify_bash(cmd: str, cwd: str, ws: str, project: str):
    """(kind, X). kind 는 "write" | "read" | None. 형제 저장소를 건드리지 않으면 (None, None)."""
    found: dict[str, str] = {}  # X -> "read"|"write"

    def hit(x, kind):
        if x and found.get(x) != "write":
            found[x] = kind

    cur = cwd or project or "/"
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
            hit(sibling_of(cur, ws, project), "read")
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
        touched = set()
        for w in cands:
            if "/" in w or w.startswith(("~", "$HOME", "${HOME}", ".")) or w in redirs:
                touched.add(norm(w, seg_cwd))
        for m in ABS.findall(seg):
            touched.add(norm(m, seg_cwd))
        wt = {norm(w, seg_cwd) for w in write_tokens if w}
        x_cwd = sibling_of(seg_cwd, ws, project)
        if x_cwd and (args or redirs):
            def rel(w):
                return not os.path.isabs(expand(w)) and not w.startswith("~")
            # A whole-command write counts against the cwd repo only if it has a relative
            # argument; `cd sib && rm /abs/own/file` writes our repo, not the sibling.
            rel_args = [a for a in args if not a.startswith("-") and rel(a)]
            relative_write = any(rel(w) for w in write_tokens) or (whole and bool(rel_args))
            hit(x_cwd, "write" if relative_write else "read")
        for p in touched:
            x = sibling_of(p, ws, project)
            if x:
                hit(x, "write" if whole or p in wt else "read")
    for x, k in found.items():
        if k == "write":
            return "write", x
    for x, k in found.items():
        return "read", x
    return None, None
