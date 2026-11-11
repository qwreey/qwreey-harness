"""Auto memory helpers shared by hooks/memory-placement.py and the /q:doctor memory checks. Standard library only.

Why: auto memory (~/.claude/projects/<key>/memory/) is machine-local. Knowledge that belongs to a repository
(paths, build commands, conventions, pitfalls) written there does not travel with the repo, to another clone,
another machine or a teammate (audit/23). This module decides "does this memory text look like repo knowledge".

Key rule (measured on Claude Code 2.1.316, audit/23 section 1): project key = every character outside [A-Za-z0-9]
in the absolute project path replaced by "-" ("/tmp/a.dot_1" -> "-tmp-a-dot-1"). The mapping is lossy, so a key is
resolved back to a path by walking the filesystem (resolve_key).
"""
import os
import re
from pathlib import Path

# ---------- frontmatter ----------

def parse_memory(text):
    """Returns (type, name, body). `type` is read from top-level or from metadata: (nested) frontmatter; "" if absent."""
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?", text, re.S)
    if not m:
        return "", "", text
    fm, body = m.group(1), text[m.end():]
    t = re.search(r"^\s*type:\s*([\w-]+)", fm, re.M)
    n = re.search(r"^name:\s*(.+)$", fm, re.M)
    return (t.group(1).lower() if t else ""), (n.group(1).strip() if n else ""), body


# ---------- signals ----------

EXT = r"(?:luau|lua|ts|tsx|js|jsx|mjs|py|rs|go|kt|md|json|toml|yaml|yml|sh|astro|html|css|sql)"
RE_PATH = re.compile(r"(?<![\w/~.])(?:\.?[\w-]+/)+[\w.-]+\." + EXT + r"\b")
RE_SYMBOL = re.compile(r"`[A-Za-z_][\w]*(?:(?:\.|::|:)[A-Za-z_]\w*)+(?:\(\))?`|`[A-Za-z_]\w*\(\)`")
RE_COMMAND = re.compile(r"`(?:make|npm|pnpm|yarn|bun|cargo|go|pytest|python3?|lune|rojo|luau|luau-analyze|selene|stylua|wally|just|tsc|vitest|jest)\b[^`\n]*`")
RE_HERE = re.compile(r"\b(?:in|for|of) (?:this|the) (?:repo|repository|codebase|project)\b|\bthis (?:repo|repository|codebase)\b|이 (?:저장소|레포|프로젝트|코드베이스)(?:에서|의|는|에는)?", re.I)
RE_CONV = re.compile(r"\b(?:convention|always use|never use|must not|do not use|gotcha|pitfall|workaround|invariant)\b|규약|컨벤션|항상 .{0,12}(?:쓴다|사용|한다)|금지|함정|주의", re.I)
RE_ENV = re.compile(r"sandbox|this machine|my machine|container|dev ?server|mise\b|~/\.claude|/code/\.|\bshim\b|이 기기|샌드박스|개발 서버|내 환경|이 환경", re.I)
RE_ABS_ENV = re.compile(r"(?:~|/home/\w+|/code/\.claude|/tmp)/[\w./-]*")


def signals(body):
    """Returns {"path": [...], "command": [...], "here": [...], "symbol": [...], "conv": [...], "env": [...]} (matched snippets)."""
    cleaned = RE_ABS_ENV.sub(" ", body)
    out = {
        "path": [m.group(0) for m in RE_PATH.finditer(cleaned)],
        "command": [m.group(0) for m in RE_COMMAND.finditer(body)],
        "here": [m.group(0) for m in RE_HERE.finditer(body)],
        "symbol": [m.group(0) for m in RE_SYMBOL.finditer(body)],
        "conv": [m.group(0) for m in RE_CONV.finditer(body)],
        "env": [m.group(0) for m in RE_ENV.finditer(body)],
    }
    return {k: list(dict.fromkeys(v)) for k, v in out.items()}


STRONG = ("path", "command", "here")
TYPE_BONUS = {"project": 1, "reference": -1}
THRESHOLD = 3


def classify(text):
    """Returns (verdict, score, signals, type). verdict is "repo" (looks like repo knowledge) or "keep".

    Score: strong signal (path, build/test command, "in this repo") 2 each kind, weak (symbol, convention word) 1 each kind,
    type bonus (project +1, reference -1), environment wording -2. type=user is always "keep" (personal traits).
    """
    t, _name, body = parse_memory(text)
    sig = signals(body)
    score = sum(2 for k in STRONG if sig[k]) + sum(1 for k in ("symbol", "conv") if sig[k]) + TYPE_BONUS.get(t, 0)
    if sig["env"]:
        score -= 2
    verdict = "keep" if t == "user" else ("repo" if score >= THRESHOLD and any(sig[k] for k in STRONG + ("symbol",)) else "keep")
    return verdict, score, sig, t


def describe(sig, limit=3):
    """Short evidence string, e.g. 'path src/a.py; command `make all`'."""
    parts = []
    for k in ("path", "command", "here", "symbol", "conv"):
        if sig.get(k):
            parts.append(f"{k} {', '.join(sig[k][:limit])}")
    return "; ".join(parts)


# ---------- locations ----------

def key_of(path):
    return re.sub(r"[^A-Za-z0-9]", "-", str(path))


def config_home():
    return Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")


def resolve_key(key, root="/"):
    """Finds the existing directory whose key_of() equals `key`, walking the filesystem. Returns Path or None.

    The key is lossy ("/", ".", "_", "-" and spaces all become "-"), so this matches directory entries by their
    sanitized names instead of splitting the key.
    """
    def walk(d, prefix):
        try:
            entries = sorted(os.scandir(d), key=lambda e: e.name)
        except OSError:
            return None
        for e in entries:
            cand = prefix + "-" + re.sub(r"[^A-Za-z0-9]", "-", e.name)
            if cand == key:
                return Path(e.path)
            if key.startswith(cand + "-") and e.is_dir(follow_symlinks=True):
                r = walk(e.path, cand)
                if r:
                    return r
        return None
    return walk(root, "")


def memory_dirs(cwd=None, home=None):
    """Directories that count as auto memory for a session in `cwd`: <config>/projects/*/memory plus autoMemoryDirectory settings."""
    import json
    home = Path(home) if home else config_home()
    extra = []
    files = [home / "settings.json"]
    if cwd:
        p = Path(cwd)
        for d in [p, *p.parents]:
            if (d / ".claude").is_dir():
                files += [d / ".claude" / "settings.json", d / ".claude" / "settings.local.json"]
    for f in files:
        try:
            v = json.loads(f.read_text()).get("autoMemoryDirectory")
        except (OSError, ValueError, AttributeError):
            continue
        if isinstance(v, str) and (v.startswith("/") or v.startswith("~/")):
            extra.append(Path(os.path.expanduser(v)))
    return {"default_root": home / "projects", "custom": extra}


def is_memory_path(file_path, cwd=None, home=None):
    """True if file_path is inside an auto memory directory."""
    try:
        fp = Path(os.path.abspath(os.path.expanduser(file_path)))
    except (TypeError, ValueError):
        return False
    md = memory_dirs(cwd, home)
    root = md["default_root"]
    try:
        rel = fp.relative_to(os.path.abspath(root))
        if len(rel.parts) >= 3 and rel.parts[1] == "memory":
            return True
    except ValueError:
        pass
    for c in md["custom"]:
        try:
            fp.relative_to(os.path.abspath(c))
            return True
        except ValueError:
            continue
    return False
