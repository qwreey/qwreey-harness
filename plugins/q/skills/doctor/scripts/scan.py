#!/usr/bin/env python3
"""harness-doctor 결정적 검사기. 읽기 전용이다. 대상 저장소에 아무것도 쓰지 않는다.

사용:
  python3 -I scan.py <저장소 경로> [--only 1,3,9] [--json] [--today YYYY-MM-DD]
  python3 -I scan.py --user            사용자 레벨(정본 home/.claude 와 실제 ~/.claude)
  python3 -I scan.py --sessions <경로>  실행 중인 Claude 세션만 본다

  python3 -I scan.py --env              읽은 harness.env 값과 쓸 수 있는 툴킷을 보인다

항목 번호: 0 세션, 1 상시 로드, 2 rules, 3 스킬, 4 낡음·모순, 5 공유 지식 후보(툴킷),
          6 복제본 표류, 7 설정, 8 툴체인(툴킷), 9 worktree, 10 메모리 이식성(memory_checks.py).
코어(이 파일)는 언어와 무관한 검사만 한다. 언어·툴체인 검사는 toolkits/<이름>.py 가 맡고,
저장소마다 감지 표식이 있을 때만 켠다(--toolkits 로 강제). 환경 고유값은 ~/.claude/harness.env 에서 읽는다.
판단이 필요한 것은 '경고'나 '정보'로만 낸다. 고칠지는 모델과 사용자가 정한다.
표준 라이브러리만 쓴다. git 은 GIT_OPTIONAL_LOCKS=0 으로 불러 인덱스를 건드리지 않는다.
"""
import argparse
import datetime as dt
import difflib
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import tomllib
from pathlib import Path
from types import SimpleNamespace

VERSION = "2"
HERE = Path(__file__).resolve()
USER_HOME = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
# 이 파일은 <claude-doctor>/plugins/q/skills/doctor/scripts/scan.py 다. 플러그인 캐시(~/.claude/plugins/…)로 설치되면
# claude-doctor 위치를 모르므로 HARNESS_DOCTOR_ROOT 환경 변수나 harness.env 로 알려야 정본 관련 검사가 켜진다.
_PATH_ROOT = HERE.parents[5] if (HERE.parents[4].name == "plugins" and (HERE.parents[5] / "home" / "MANIFEST").is_file()) else None


def _load_env():
    """harness.env 를 lib/harness_env.py 로 읽는다. lib 가 없으면 ({}, None)."""
    for lib in (USER_HOME / "lib" / "harness_env.py", *([_PATH_ROOT / "home" / ".claude" / "lib" / "harness_env.py"] if _PATH_ROOT else [])):
        if lib.is_file():
            spec = importlib.util.spec_from_file_location("harness_env", lib)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            cands = [USER_HOME / "harness.env"] + ([_PATH_ROOT / "home" / ".claude" / "harness.env"] if _PATH_ROOT else [])
            return mod.load(cands), mod
    return {}, None


ENV, ENVLIB = _load_env()
# 우선순위: 환경 변수 > 이 파일의 위치 > harness.env. 셋 다 없으면 정본 관련 검사(MANIFEST, 훅 사본)를 건너뛴다.
_root = os.environ.get("HARNESS_DOCTOR_ROOT") or (str(_PATH_ROOT) if _PATH_ROOT else ENV.get("HARNESS_DOCTOR_ROOT"))
DOCTOR_ROOT = Path(_root) if _root else None
CANON_HOME = DOCTOR_ROOT / "home" / ".claude" if DOCTOR_ROOT else USER_HOME
WORKSPACE = Path(ENV.get("HARNESS_WORKSPACE") or (DOCTOR_ROOT.parent if DOCTOR_ROOT else Path.cwd()))
# 위임 작업공간·초안 사본 접미(<repo>-<접미>). 형제 비교와 `all` 에서 뺀다.
COPY_SUFFIXES = ("-agy", "-scratch", "-codex", "-proto", "-doctor")
DESC_LIMIT = 1536
SKILL_MAX_LINES = 500
REF_TOC_LINES = 100
PROJECT_CLAUDE_GOAL = 80
USER_CLAUDE_GOAL = 40
OFFICIAL_LINES = 200
CHAR_LIMIT = 40000
TOTAL_BYTES_WARN = 20000
STALE_DAYS = 14
SKILL_KEYS = {
    "name", "description", "model", "allowed-tools", "argument-hint", "arguments",
    "disable-model-invocation", "user-invocable", "effort", "shell", "version", "when_to_use",
    "paths", "hooks", "context", "agent", "metadata", "license", "compatibility",
}
# 코어 부작용 낱말. 툴킷의 SIDE_EFFECT_WORDS 와 환경의 무거운 실행 래퍼(harness.env)가 build_side_effect 에서 더해진다.
SIDE_EFFECT_CORE = [
    r"git (?:commit|push|merge|rebase|reset --hard|tag|worktree (?:add|remove)|branch -[dD])\b", r"\brm -[rf]",
    r"커밋(?:한다|하고|해|을 만든)", "푸시한다", "배포한다", "업로드한다", "게시한다", "삭제한다", "지운다",
    r"\b(?:publish|deploy)\.(?:py|sh)\b", "setpriv",
]
SIDE_EFFECT = None
AGENT_EXES = {"claude", "agy", "antigravity", "gemini", "codex"}
BROAD_ALLOW = re.compile(r"^Bash\((?:sed|cp|mv|chmod|curl|wget|python3?|node|env|find|bash|sh|rm)(?::\*|\s\*|\*)?\)$")
SKIP_DIRS = {".git", "node_modules", "worktrees", "__pycache__"}  # 툴킷의 SKIP_DIRS 가 더해진다

findings = []


def add(item, sev, code, where, msg, ref=None):
    findings.append({"item": item, "sev": sev, "code": code, "where": str(where), "msg": msg, "ref": ref})


# ---------------------------------------------------------- 툴킷
def load_toolkits():
    """scripts/toolkits/<이름>.py 를 읽는다. HARNESS_TOOLKITS 가 있으면 그 목록만."""
    enabled = set((ENV.get("HARNESS_TOOLKITS") or "").split())
    out = {}
    for f in sorted((HERE.parent / "toolkits").glob("*.py")):
        if f.name.startswith("_") or (enabled and f.stem not in enabled):
            continue
        spec = importlib.util.spec_from_file_location(f"harness_toolkit_{f.stem}", f)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        out[getattr(mod, "NAME", f.stem)] = mod
    return out


TOOLKITS = load_toolkits()
for _tk in TOOLKITS.values():
    SKIP_DIRS |= set(getattr(_tk, "SKIP_DIRS", ()))


def heavy_wrap():
    """무거운 실행 래퍼 argv. lib 가 없으면 기본값(auto: choom 이 있으면 쓴다)과 같게 정한다."""
    if ENVLIB:
        return ENVLIB.heavy_wrap(ENV)
    import shutil
    return ["choom", "-n", "1000", "--"] if shutil.which("choom") else []


def build_side_effect():
    words = list(SIDE_EFFECT_CORE)
    for tk in TOOLKITS.values():
        words += list(getattr(tk, "SIDE_EFFECT_WORDS", []))
    wrap = heavy_wrap()
    if wrap:  # 이 환경의 무거운 실행 래퍼를 쓰라고 하는 스킬(예: `choom -n`)
        words.append(re.escape(" ".join(wrap[:2])))
    return re.compile("|".join(words))


SIDE_EFFECT = build_side_effect()


# ---------------------------------------------------------------- 공용
def run(cmd, cwd=None, timeout=30):
    env = dict(os.environ, GIT_OPTIONAL_LOCKS="0", LC_ALL="C.UTF-8")
    if cmd[0] == "git":  # agy 처럼 다른 uid 가 만든 worktree 도 읽는다(읽기 전용 명령만 쓴다)
        cmd = ["git", "-c", "safe.directory=*"] + cmd[1:]
    try:
        p = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return p.stdout if p.returncode == 0 else None


def read(p):
    try:
        return Path(p).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def md5(p):
    h = hashlib.md5()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def rel(p, base):
    try:
        return str(Path(p).relative_to(base))
    except ValueError:
        return str(p)


def stats(p):
    t = read(p) or ""
    return {"lines": t.count("\n") + (0 if t.endswith("\n") or not t else 1), "bytes": len(t.encode()), "chars": len(t)}


def git_root(repo):
    """repo 가 git 작업 트리의 루트면 True. 반입 사본(intake/<이름>/)처럼 다른 저장소 안의 하위 디렉터리면 False."""
    out = run(["git", "rev-parse", "--show-toplevel"], cwd=repo)
    return bool(out) and Path(out.strip()).resolve() == Path(repo).resolve()


def repo_files(repo):
    out = run(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"], cwd=repo, timeout=60) \
        if git_root(repo) else None
    if out is not None:
        return [f for f in out.split("\0") if f and not f.startswith(".claude/worktrees/")]
    files = []
    for root, dirs, fs in os.walk(repo):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        files += [rel(Path(root) / f, repo) for f in fs]
    return files


def strip_code(text):
    """펜스 코드, 인라인 코드, HTML 주석을 같은 줄 수의 공백으로 바꾼다."""
    text = re.sub(r"<!--.*?-->", lambda m: "\n" * m.group(0).count("\n"), text, flags=re.S)
    out, fence = [], None
    for line in text.split("\n"):
        m = re.match(r"\s*(```|~~~)", line)
        if fence:
            out.append("")
            if m and m.group(1) == fence:
                fence = None
            continue
        if m:
            fence = m.group(1)
            out.append("")
            continue
        out.append(re.sub(r"`[^`]*`", "", line))
    return "\n".join(out)


# ------------------------------------------------------- frontmatter
def parse_frontmatter(text):
    """간이 YAML. (dict, 오류문자열|None). frontmatter 가 없으면 ({}, None)."""
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return {}, None
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        return None, "닫는 --- 가 없다"
    data, i, body = {}, 1, lines[1:end]
    i = 0
    while i < len(body):
        line = body[i]
        if not line.strip() or line.lstrip().startswith("#"):
            i += 1
            continue
        if "\t" in line[: len(line) - len(line.lstrip())]:
            return None, f"{i + 2}행: 탭 들여쓰기"
        m = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if not m:
            return None, f"{i + 2}행: 'key: value' 꼴이 아니다: {line[:60]}"
        key, val = m.group(1), m.group(2).rstrip()
        i += 1
        block = []
        while i < len(body) and (body[i].startswith((" ", "\t")) or not body[i].strip()):
            block.append(body[i])
            i += 1
        while block and not block[-1].strip():
            block.pop()
        if val in (">", ">-", ">+", "|", "|-", "|+"):
            parts = [b.strip() for b in block]
            data[key] = (" " if val[0] == ">" else "\n").join(parts).strip()
        elif val == "" and block and block[0].lstrip().startswith("- "):
            data[key] = [unquote(b.strip()[2:].strip()) for b in block if b.strip().startswith("- ")]
        elif val == "" and block:
            data[key] = {"_raw": "\n".join(block)}
        elif val.startswith("["):
            if not val.endswith("]"):
                return None, f"{key}: 닫히지 않은 목록"
            data[key] = [unquote(x.strip()) for x in split_list(val[1:-1]) if x.strip()]
        else:
            if (val[:1] in "\"'") and (len(val) < 2 or val[-1] != val[0]):
                return None, f"{key}: 닫히지 않은 따옴표"
            if block:  # 여러 줄 평문 스칼라
                val = " ".join([val] + [b.strip() for b in block])
            v = unquote(val)
            data[key] = {"true": True, "false": False}.get(v, v) if v == val else v
    return data, None


def split_list(s):
    out, cur, q = [], "", None
    for ch in s:
        if q:
            cur += ch
            if ch == q:
                q = None
        elif ch in "\"'":
            q = ch
            cur += ch
        elif ch == ",":
            out.append(cur)
            cur = ""
        else:
            cur += ch
    out.append(cur)
    return out


def unquote(s):
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
        return s[1:-1]
    return s


# ------------------------------------------------------------- glob
def expand_braces(p):
    m = re.search(r"\{([^{}]*)\}", p)
    if not m:
        return [p]
    return [x for alt in m.group(1).split(",") for x in expand_braces(p[: m.start()] + alt + p[m.end():])]


def glob_re(g):
    g = g.lstrip("./") if g.startswith("./") else g
    i, out = 0, ""
    while i < len(g):
        if g.startswith("**/", i):
            out += "(?:.*/)?"
            i += 3
        elif g.startswith("**", i):
            out += ".*"
            i += 2
        elif g[i] == "*":
            out += "[^/]*"
            i += 1
        elif g[i] == "?":
            out += "[^/]"
            i += 1
        elif g[i] == "[":
            j = g.find("]", i)
            out += g[i: j + 1] if j > 0 else re.escape(g[i])
            i = j + 1 if j > 0 else i + 1
        else:
            out += re.escape(g[i])
            i += 1
    return re.compile("^" + out + "$")


def glob_hits(pattern, files):
    rx = [glob_re(p) for p in expand_braces(pattern)]
    return sum(1 for f in files if any(r.match(f) for r in rx))


# ---------------------------------------------------------- 0 세션
def self_pids():
    pids, p = set(), os.getpid()
    while p > 1:
        pids.add(p)
        try:
            stat = Path(f"/proc/{p}/stat").read_text()
            p = int(stat.rsplit(")", 1)[1].split()[1])
        except (OSError, ValueError, IndexError):
            break
    return pids


def claude_sessions():
    """[(pid, cwd, 자기 조상 여부, 실행 파일)]. Claude 와 위임 에이전트(agy, codex)만 센다.
    `pgrep -f claude` 는 셸 스냅숏 경로에 'claude' 가 든 bash 래퍼까지 잡으므로 실행 파일 이름으로 거른다."""
    me, out = self_pids(), []
    for d in Path("/proc").iterdir():
        if not d.name.isdigit():
            continue
        try:
            exe = os.path.basename(os.readlink(d / "exe"))
            argv0 = (d / "cmdline").read_bytes().split(b"\0")[0].decode(errors="replace")
            cwd = os.readlink(d / "cwd")
        except OSError:
            continue
        name = exe if exe in AGENT_EXES else os.path.basename(argv0)
        if name in AGENT_EXES:
            out.append((int(d.name), cwd, int(d.name) in me, name))
    return out


def worktrees(repo):
    out = run(["git", "worktree", "list", "--porcelain"], cwd=repo)
    if out is None:
        return []
    wts, cur = [], {}
    for line in out.split("\n"):
        if not line.strip():
            if cur:
                wts.append(cur)
            cur = {}
            continue
        k, _, v = line.partition(" ")
        cur[k] = v or True
    if cur:
        wts.append(cur)
    return wts


def inside(path, root):
    path, root = str(path).rstrip("/"), str(root).rstrip("/")
    return path == root or path.startswith(root + "/")


def check_sessions(repo):
    sess = claude_sessions()
    wts = worktrees(repo) if git_root(repo) else []
    here = [s for s in sess if inside(s[1], repo) and not s[2]]
    for pid, cwd, _, exe in here:
        add(0, "오류", "SESSION-LIVE", cwd,
            f"실행 중인 {exe} 세션(pid {pid})이 이 경로에 있다. 직접 고치지 말고 인계 문서를 만든다.",
            "references/fix-protocol.md#실행-중인-세션")
    others = [w["worktree"] for w in wts if not inside(w["worktree"], repo) and not inside(repo, w["worktree"])]
    for pid, cwd, me, exe in sess:
        if not me and not inside(cwd, repo) and any(inside(cwd, w) for w in others):
            add(0, "정보", "SESSION-SIBLING", cwd,
                f"같은 git 저장소의 다른 worktree 에 {exe}(pid {pid})가 있다. 공유 파일(.git, 브랜치, 상태 문서)은 건드리지 않는다.")
    return here


# ------------------------------------------------------- 1 상시 로드
IMPORT_RX = re.compile(r"(?:^|\s)@((?:~/|\.{1,2}/|/)?[\w.\-][\w./\-]*)")


def imports_of(path):
    text = read(path)
    if text is None:
        return []
    res = []
    for m in IMPORT_RX.finditer(strip_code(text)):
        raw = m.group(1).rstrip(".,;:")
        p = Path(os.path.expanduser(raw)) if raw.startswith("~") else (Path(raw) if raw.startswith("/") else path.parent / raw)
        if p.is_file():
            res.append(p.resolve())
    return res


def import_tree(root):
    seen, order = set(), []

    def walk(p, depth, via):
        rp = p.resolve()
        if rp in seen:
            return
        seen.add(rp)
        order.append((rp, depth, via))
        if depth < 5:
            for q in imports_of(rp):
                walk(q, depth + 1, rp)

    walk(root, 0, None)
    return order


def rule_files(base):
    d = base / "rules"
    return sorted(d.rglob("*.md")) if d.is_dir() else []


def check_load(repo, user=False):
    base = repo if user else repo / ".claude"
    roots = [repo / "CLAUDE.md"] if user else [repo / "CLAUDE.md", repo / ".claude" / "CLAUDE.md", repo / "CLAUDE.local.md"]
    goal = USER_CLAUDE_GOAL if user else PROJECT_CLAUDE_GOAL
    loaded = []
    if not user:
        for anc in list(repo.parents)[:-1]:
            for name in ("CLAUDE.md", "CLAUDE.local.md"):
                if (anc / name).is_file():
                    loaded.append((anc / name, 0, None))
                    add(1, "정보", "LOAD-ANCESTOR", anc / name, "상위 디렉터리 CLAUDE.md 도 함께 로드된다.")
    for r in roots:
        if r.is_file():
            loaded += import_tree(r)
    for rp, depth, via in loaded:
        if via is not None:
            add(1, "경고", "LOAD-IMPORT", rel(via, repo),
                f"@{rel(rp, repo)} 를 import 한다 ({stats(rp)['bytes']:,} B). @import 는 비용을 줄이지 않는다.",
                "references/load-and-rules.md#1-상시-로드량")
            if depth > 4:
                add(1, "경고", "LOAD-HOPS", rel(rp, repo), "import 가 4홉을 넘는다. 넘친 쪽은 로드되지 않는다.")
    for rf in rule_files(base):
        fm, err = parse_frontmatter(read(rf) or "")
        if fm is not None and not fm.get("paths"):
            loaded.append((rf.resolve(), 0, "rules"))
    total = {"lines": 0, "bytes": 0, "chars": 0}
    rows = []
    for rp, depth, via in loaded:
        s = stats(rp)
        for k in total:
            total[k] += s[k]
        rows.append({"file": rel(rp, repo), **s, "via": "rules(paths 없음)" if via == "rules" else ("import" if via else "root")})
        if s["chars"] > CHAR_LIMIT:
            add(1, "오류", "LOAD-CHARS", rel(rp, repo), f"{s['chars']:,}자. 200K 창 기준 40,000자를 넘으면 뒷부분이 잘린다.")
        if s["lines"] >= OFFICIAL_LINES:
            add(1, "경고", "LOAD-OVER200", rel(rp, repo), f"{s['lines']}줄. 공식 권장은 파일당 200줄 미만.")
    for r in roots[:1]:
        if r.is_file():
            n = stats(r)["lines"]
            if n > goal:
                add(1, "경고", "LOAD-GOAL", rel(r, repo), f"{n}줄. 우리 목표는 {goal}줄 이하.",
                    "references/load-and-rules.md#1-상시-로드량")
    if total["bytes"] > TOTAL_BYTES_WARN:
        add(1, "경고", "LOAD-TOTAL", repo, f"상시 로드 합계 {total['bytes']:,} B / {total['lines']}줄 / {total['chars']:,}자.")
    for rp, _, _ in loaded:
        if rp.name in ("todos.md", "TODO.md", "ROADMAP.md"):
            t = read(rp) or ""
            strike = len(re.findall(r"^\s*[-*].*~~.+~~", t, re.M))
            m = re.search(r"^#+\s*(된 것|완료|Done|끝난)", t, re.M)
            done_bytes = len(t[m.start():].encode()) if m else 0
            if strike or done_bytes:
                add(1, "경고", "LOAD-TODOS-DONE", rel(rp, repo),
                    f"상시 로드되는 할 일 문서에 끝난 항목이 있다(취소선 {strike}줄, 끝난 절 {done_bytes:,} B). 처리 방식은 D-07 미결.",
                    "references/staleness-and-kb.md#d-07")
    return {"files": rows, "total": total}


# ---------------------------------------------------------- 2 rules
def norm_line(s):
    s = re.sub(r"<!--.*?-->", "", s)
    s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)
    s = re.sub(r"[`*_>#]|^\s*(?:[-+]|\d+\.)\s+", "", s)
    s = re.sub(r"\s*—\s*\"[^\"]*\"\s*$", "", s)  # 꼬리 근거 표기 제거
    return re.sub(r"\s+", " ", s).strip()


def check_rules(repo, files, user=False):
    base = repo if user else repo / ".claude"
    rfs = rule_files(base)
    conv = [p for p in (base / "conventions.md", repo / "CONVENTIONS.md") if p.is_file()]
    conv_lines = []
    for c in conv:
        for i, line in enumerate((read(c) or "").split("\n"), 1):
            n = norm_line(line)
            if len(n) >= 25:
                conv_lines.append((c, i, n))
    summary = []
    for rf in rfs:
        text = read(rf) or ""
        fm, err = parse_frontmatter(text)
        r = rel(rf, repo)
        if fm is None:
            add(2, "오류", "RULE-PARSE", r, f"frontmatter 파싱 실패: {err}")
            continue
        paths = fm.get("paths")
        if isinstance(paths, str):
            paths = [p.strip() for p in paths.split(",") if p.strip()]
        st = stats(rf)
        summary.append({"file": r, "paths": paths or [], **st})
        if not paths:
            add(2, "경고", "RULE-NOPATHS", r, f"paths 가 없어 매 세션 로드된다 ({st['bytes']:,} B).",
                "references/load-and-rules.md#2-rules-구성")
        elif not user:
            for g in paths:
                if glob_hits(g, files) == 0:
                    add(2, "경고", "RULE-DEADGLOB", r, f"paths '{g}' 에 맞는 파일이 없다. 이 규칙은 로드될 일이 없다.")
        if st["bytes"] > 4500:
            add(2, "정보", "RULE-BIG", r, f"rule 하나가 {st['bytes']:,} B. 해당 파일을 읽을 때마다 실린다.")
        if conv_lines:
            dups = []
            for i, line in enumerate(text.split("\n"), 1):
                n = norm_line(line)
                if len(n) < 25:
                    continue
                best = None
                for c, j, cn in conv_lines:
                    sm = difflib.SequenceMatcher(None, n, cn, autojunk=False)
                    if sm.real_quick_ratio() < 0.6 or sm.quick_ratio() < 0.6:
                        continue
                    ratio = sm.ratio()
                    if ratio >= 0.6 and (best is None or ratio > best[0]):
                        best = (ratio, c, j)
                if best:
                    dups.append((i, best))
            if dups:
                ex = ", ".join(f"{i}↔{rel(c, repo)}:{j}({ratio:.2f})" for i, (ratio, c, j) in dups[:4])
                add(2, "경고", "RULE-DUP", r,
                    f"conventions 와 비슷한 줄 {len(dups)}개 (예: {ex}). 정본은 rules, conventions 는 '왜'만.",
                    "references/load-and-rules.md#rules-와-conventions-중복")
    return summary


# ----------------------------------------------------------- 3 스킬
LINK_RX = re.compile(r"\]\(([^)#\s]+\.md)(?:#[^)]*)?\)|`([\w./\-]+\.md)`|(?<![\w/])((?:references|refs|docs)/[\w./\-]+\.md)")


def md_links(p, skill_dir):
    out = set()
    for m in LINK_RX.finditer(read(p) or ""):
        s = next(g for g in m.groups() if g)
        for cand in (p.parent / s, skill_dir / s):
            try:
                c = cand.resolve()
            except OSError:
                continue
            if c.is_file() and inside(c, skill_dir.resolve()) and c != p.resolve():
                out.add(c)
                break
    return out


def has_toc(text):
    head = text.split("\n")[:40]
    if any(re.match(r"^#+\s*(목차|차례|contents|table of contents|toc)\b", l.strip(), re.I) for l in head):
        return True
    return sum(1 for l in head if re.search(r"\]\(#", l)) >= 3


def skill_dirs(repo, user=False):
    base = (repo / "skills") if user else (repo / ".claude" / "skills")
    return sorted(p.parent for p in base.glob("*/SKILL.md")) if base.is_dir() else []


def check_skill(sd, repo):
    sk = sd / "SKILL.md"
    r = rel(sk, repo)
    text = read(sk) or ""
    fm, err = parse_frontmatter(text)
    info = {"skill": sd.name, "lines": stats(sk)["lines"]}
    if fm is None or not fm:
        add(3, "오류", "SKILL-PARSE", r, f"frontmatter 파싱 실패: {err or 'frontmatter 없음'}")
        return info
    name = fm.get("name", sd.name)
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", str(name)):
        add(3, "오류", "SKILL-NAME", r, f"name '{name}' 은 소문자·숫자·하이픈 64자 이내여야 한다.")
    if re.search(r"claude|anthropic", str(name)):
        add(3, "오류", "SKILL-NAME", r, f"name '{name}' 에 예약어(claude/anthropic)가 들어 있다.")
    if name != sd.name:
        add(3, "정보", "SKILL-NAME", r, f"name '{name}' 이 디렉터리 이름 '{sd.name}' 과 다르다.")
    desc = str(fm.get("description", "")) + str(fm.get("when_to_use", ""))
    info["desc_chars"] = len(desc)
    if not desc:
        add(3, "오류", "SKILL-DESC", r, "description 이 없다.")
    elif len(desc) > DESC_LIMIT:
        add(3, "오류", "SKILL-DESC", r, f"description+when_to_use {len(desc)}자. {DESC_LIMIT}자에서 잘린다.")
    for k in fm:
        if k not in SKILL_KEYS:
            add(3, "정보", "SKILL-KEY", r, f"알려지지 않은 frontmatter 키 '{k}'.")
    if info["lines"] > SKILL_MAX_LINES:
        add(3, "경고", "SKILL-LINES", r, f"SKILL.md {info['lines']}줄. 권장 500줄 이하 — references 로 나눈다.",
            "references/skills.md#3-스킬-상태")
    direct = md_links(sk, sd)
    mds = [p.resolve() for p in sd.rglob("*.md") if p.name != "SKILL.md"]
    for p in mds:
        depth = len(p.relative_to(sd.resolve()).parts)
        if depth > 2 and p not in direct:  # 하위 폴더라도 SKILL.md 가 바로 가리키면 1단계다(예: references/toolkits/)
            add(3, "경고", "SKILL-NEST", rel(p, repo), "references 가 하위 디렉터리로 중첩됐고 SKILL.md 가 바로 가리키지 않는다.")
    for p in direct:
        for q in md_links(p, sd):
            if q not in direct and q.name != "SKILL.md":
                add(3, "경고", "SKILL-NEST", rel(p, repo),
                    f"{q.name} 를 이 파일에서만 가리킨다(2단계). SKILL.md 에서 바로 가리키게 한다.")
    for p in mds:
        t = read(p) or ""
        n = t.count("\n")
        if n > REF_TOC_LINES and not has_toc(t):
            add(3, "경고", "SKILL-TOC", rel(p, repo), f"{n}줄인데 맨 위에 목차가 없다.")
        if p not in direct and not any(p in md_links(d, sd) for d in direct):
            add(3, "정보", "SKILL-ORPHAN", rel(p, repo), "SKILL.md 에서 닿지 않는 문서다.")
    dmi = fm.get("disable-model-invocation") in (True, "true")
    info["user_only"] = dmi
    if not dmi:
        body = text + "".join(read(p) or "" for p in sd.rglob("*") if p.is_file() and p.suffix in (".sh", ".py"))
        hits = sorted(set(m.group(0) for m in SIDE_EFFECT.finditer(body)))
        if hits:
            add(3, "경고", "SKILL-SIDEFX", r,
                f"부작용 낌새({', '.join(hits[:6])})가 있는데 disable-model-invocation 이 없다. 모델이 스스로 부를 수 있다.",
                "references/skills.md#부작용-판단")
    return info


def check_skills(repo, user=False):
    return [check_skill(sd, repo) for sd in skill_dirs(repo, user)]


# ------------------------------------------------------ 4 낡음·모순
DATED_RX = re.compile(r"(20\d\d-\d\d-\d\d)[^\]\n*—]{0,6}?(?:기준|현재)|(?:as of|기준:?)\s*(20\d\d-\d\d-\d\d)")
SUPERSEDE_RX = re.compile(r"뒤집|폐기|철회|무효|전환 중|바뀌었|superseded|reverted|no longer")
FIRM_RX = re.compile(r"확정|정해진|예외 없음|반드시|decided|always")
QID_RX = re.compile(r"질문\s*([A-Z]{1,3}(?:\s*[·,/]\s*[A-Z]{1,3})*)")


# "AB 규칙은 뒤집혔다", "질문 AB 는 폐기" 꼴에서 뒤집힌 쪽 ID 만 뽑는다(새 결정 ID 는 빼려고 '규칙/결정' 을 요구)
GONE_ID_RX = re.compile(r"(?<![A-Za-z])([A-Z]{2,3})(?![A-Za-z])[^A-Z\n]{0,4}(?:규칙|결정|방침|rule)"
                        r"(?=[^\n]*(?:뒤집|폐기|철회|무효|superseded|reverted))|"
                        r"질문\s*([A-Z]{2,3})\s*(?:은|는|이|가)?\s*(?:뒤집|폐기|철회|무효)")


def gone_ids(line):
    return {a or b for a, b in GONE_ID_RX.findall(line)}


def qids(line):
    return {x.strip() for m in QID_RX.finditer(line) for x in re.split(r"[·,/]", m.group(1))}


def last_commit(repo, f):
    out = run(["git", "log", "-1", "--format=%cs", "--", str(f)], cwd=repo)
    return out.strip() if out else None


def state_docs(repo):
    names = ["CLAUDE.md", "GEMINI.md", "AGENTS.md", "ROADMAP.md", "HUMAN_TODO.md"]
    cands = [repo / n for n in names] + [repo / ".claude" / n for n in
                                          ("CLAUDE.md", "todos.md", "project-context.md", "ROADMAP.md", "conventions.md")]
    return [p for p in cands if p.is_file()]


def check_stale(repo, today):
    docs = state_docs(repo)
    basis = {}
    for p in docs:
        text = read(p) or ""
        clean, old = strip_code(text), []
        for i, line in enumerate(clean.split("\n"), 1):
            for m in DATED_RX.finditer(line):
                d = m.group(1) or m.group(2)
                try:
                    age = (today - dt.date.fromisoformat(d)).days
                except ValueError:
                    continue
                basis.setdefault(p, []).append(d)
                if age > STALE_DAYS:
                    old.append((i, d, age, line.strip()[:60]))
        if old:
            i, d, age, ex = max(old, key=lambda x: x[2])
            add(4, "경고", "STALE-DATED", rel(p, repo),
                f"날짜 기준 상태 서술 {len(old)}곳이 {STALE_DAYS}일을 넘었다(줄 {', '.join(str(o[0]) for o in old[:8])}). "
                f"가장 오래된 것 {d}({age}일): {ex}", "references/staleness-and-kb.md#4-낡음과-모순")
        tags = len(re.findall(r"\*\*\[20\d\d-\d\d-\d\d", text))
        if tags >= 10:
            add(4, "정보", "STALE-DATETAGS", rel(p, repo), f"날짜 신설 태그 '**[YYYY-MM-DD' {tags}개. 경위는 기록 문서로.")
    latest = {rel(p, repo): max(v) for p, v in basis.items()}
    if len(set(latest.values())) > 1:
        add(4, "정보", "STALE-MISMATCH", repo,
            "상태 문서마다 '기준' 날짜가 다르다: " + ", ".join(f"{k}={v}" for k, v in sorted(latest.items())))
    # 규약 문서 사이 모순: CLAUDE 쪽이 '뒤집혔다'고 한 질문 ID 를 GEMINI/AGENTS 가 '확정'으로 서술
    claude_side = [p for p in docs if p.name in ("CLAUDE.md", "conventions.md")] + rule_files(repo / ".claude")
    superseded = set()
    for p in claude_side:
        for line in strip_code(read(p) or "").split("\n"):
            superseded |= gone_ids(line)
    claude_md = repo / "CLAUDE.md"
    cdate = last_commit(repo, claude_md) if claude_md.is_file() else None
    for p in docs:
        if p.name not in ("GEMINI.md", "AGENTS.md"):
            continue
        section = ""
        for i, line in enumerate(strip_code(read(p) or "").split("\n"), 1):
            if line.startswith("#"):
                section = line
            ids = qids(line) & superseded
            if ids and (FIRM_RX.search(line) or FIRM_RX.search(section)) and not SUPERSEDE_RX.search(line + section):
                add(4, "경고", "STALE-SUPERSEDED", f"{rel(p, repo)}:{i}",
                    f"질문 {'·'.join(sorted(ids))} 을 확정처럼 적었는데 CLAUDE.md/conventions/rules 는 뒤집혔다고 한다.",
                    "references/staleness-and-kb.md#에이전트-문서-사이-모순")
        gdate = last_commit(repo, p)
        if cdate and gdate and gdate < cdate:
            add(4, "정보", "STALE-AGENTDOC-OLD", rel(p, repo),
                f"마지막 커밋 {gdate} 로 CLAUDE.md({cdate})보다 오래됐다. 규약이 따라왔는지 확인.")


# ------------------------------------------------------ 6 복제본
def load_json(p):
    try:
        return json.loads(Path(p).read_text()), None
    except FileNotFoundError:
        return None, None
    except (OSError, ValueError) as e:
        return None, str(e)


def hook_cmds(settings):
    out = []
    for ev, groups in ((settings or {}).get("hooks") or {}).items():
        for g in groups or []:
            for h in g.get("hooks", []):
                if h.get("type") == "command":
                    out.append((ev, g.get("matcher", ""), h.get("command", "")))
    return out


def script_of(cmd):
    cmd = cmd.replace('"', "").replace("'", "")
    m = re.findall(r"[\w./$\"{}~\-]+\.(?:py|sh|js|ts)\b", cmd)
    return m[-1].strip('"') if m else None


def script_path(sc, repo=None):
    """훅 명령의 스크립트 경로를 푼다: $CLAUDE_PROJECT_DIR, $HOME 등 환경 변수, ~."""
    if repo is not None:
        sc = sc.replace("$CLAUDE_PROJECT_DIR", str(repo)).replace("${CLAUDE_PROJECT_DIR}", str(repo))
    return os.path.expanduser(os.path.expandvars(sc))


def user_settings():
    res = []
    for p in (USER_HOME / "settings.json", CANON_HOME / "settings.json"):
        s, _ = load_json(p)
        if s:
            res.append((p, s))
    return res


def common_dir(path):
    out = run(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"], cwd=path)
    return out.strip() if out else None


def registry_uids():
    """harness.env 의 HARNESS_DELEGATE_REGISTRY(key<TAB>root<TAB>uid…) → {uid: {저장소 이름}}."""
    reg = ENV.get("HARNESS_DELEGATE_REGISTRY")
    out = {}
    for line in (read(reg) or "").split("\n") if reg else []:
        cols = line.split("\t")
        if len(cols) >= 3 and not line.startswith("#") and cols[2].strip().isdigit():
            out.setdefault(cols[2].strip(), set()).add(Path(cols[1].strip()).name)
    return out


def check_drift(repo, files, projects):
    # 언어 고유 사본(예: luau 의 globalTypes.d.luau)은 툴킷이 본다(DRIFT-TYPEDEFS).
    canon_guard = DOCTOR_ROOT / "plugins" / "qwreey-proc-guard" / "hooks" / "heavy-proc-guard.py" if DOCTOR_ROOT else Path("/nonexistent")
    for f in files:
        name = os.path.basename(f)
        if name == "heavy-proc-guard.py" and canon_guard.is_file():
            same = md5(repo / f) == md5(canon_guard)
            add(6, "정보" if same else "경고", "DRIFT-HOOK", f,
                "qwreey-proc-guard 플러그인의 정본과 같다." if same else "qwreey-proc-guard 플러그인의 정본(plugins/qwreey-proc-guard/hooks)과 다르다. 플러그인으로 일원화 대상.")
        if name == "agy-delegate.sh" or f.endswith("skills/delegate-agy/SKILL.md"):
            add(6, "정보", "DRIFT-DELEGATE", f, "agy 위임 사본. 통합안 claude-doctor/drafts/delegate (P4) 로 대체 예정.",
                "references/drift-and-settings.md#위임-사본")
    # uid 충돌: 저장소 안의 위임 사본 + 환경의 중앙 uid 표
    uids = registry_uids()
    for sh in projects.glob("*/.claude/tools/agy-delegate.sh"):
        m = re.search(r"AGY_UID[:=]-?\$?\{?[\w:-]*?(\d{4,6})", read(sh) or "")
        if m:
            uids.setdefault(m.group(1), set()).add(sh.parts[-4])
    mycd = common_dir(repo)
    for uid, owners in uids.items():
        owners = {o for o in owners if o == repo.name or common_dir(projects / o) != mycd}  # 같은 저장소의 worktree 는 하나로
        if len(owners) > 1 and repo.name in owners:
            add(6, "경고", "DRIFT-UID", repo, f"agy uid {uid} 를 {', '.join(sorted(owners))} 가 함께 쓴다(격리 깨짐).")
    # 사용자 레벨과 같은 훅을 프로젝트가 또 등록
    ukeys = {}
    for p, s in user_settings():
        label = "실제 ~/.claude" if p.parent == USER_HOME else "정본 home/.claude"
        for ev, mt, cmd in hook_cmds(s):
            sc = script_of(cmd)
            if sc:
                ukeys.setdefault((ev, os.path.basename(sc)), []).append(label)
    for sp in (repo / ".claude" / "settings.json", repo / ".claude" / "settings.local.json"):
        s, _ = load_json(sp)
        for ev, mt, cmd in hook_cmds(s):
            sc = script_of(cmd)
            if sc and (ev, os.path.basename(sc)) in ukeys:
                add(6, "경고", "DRIFT-HOOKDUP", rel(sp, repo),
                    f"{ev} 훅 {os.path.basename(sc)} 를 사용자 레벨({', '.join(ukeys[(ev, os.path.basename(sc))])})도 등록한다. 두 번 돈다.",
                    "references/drift-and-settings.md#훅-중복")
    # 같은 이름 스킬 사본
    mycommon = common_dir(repo)
    for sd in skill_dirs(repo):
        mine_md5 = md5(sd / "SKILL.md")
        others = list(projects.glob(f"*/.claude/skills/{sd.name}/SKILL.md")) + \
            list(projects.glob(f"*/docs/skills/{sd.name}/SKILL.md")) + list(projects.glob(f"*/skills/{sd.name}/SKILL.md")) + \
            [USER_HOME / "skills" / sd.name / "SKILL.md"]
        for o in others:
            if not o.is_file() or inside(o.resolve(), repo.resolve()) or "worktrees" in o.parts:
                continue
            if mycommon and common_dir(o.parent) == mycommon:
                continue
            if md5(o) != mine_md5:
                add(6, "경고", "DRIFT-SKILLCOPY", rel(sd / "SKILL.md", repo),
                    f"같은 이름 스킬 {o} 와 내용이 다르다(사본 표류?). 어느 쪽이 정본인지 확인.")


# ------------------------------------------------------- 7 설정
PUSH_NOTE = {
    "normal": "이 환경은 에이전트 push 가 정상 흐름이다(harness.env HARNESS_AGENT_PUSH=normal). 걷을지는 사용자 판단, HUMAN_TODO.",
    "deny": "이 환경은 에이전트 push 를 막는 정책이다(HARNESS_AGENT_PUSH=deny). 그대로 둔다.",
}


def check_settings(repo, files):
    nested = not git_root(repo) and run(["git", "rev-parse", "--show-toplevel"], cwd=repo)
    inrepo = None if nested else run(["git", "rev-parse", "--is-inside-work-tree"], cwd=repo)
    for sp in (repo / ".claude" / "settings.json", repo / ".claude" / "settings.local.json"):
        s, err = load_json(sp)
        r = rel(sp, repo)
        if err:
            add(7, "오류", "SET-JSON", r, f"JSON 파싱 실패: {err}")
            continue
        if s is None:
            continue
        for ev, mt, cmd in hook_cmds(s):
            sc = script_of(cmd)
            if sc:
                path = script_path(sc, repo)
                if not os.path.isabs(path):
                    path = str(repo / path)
                if not os.path.isfile(path):
                    add(7, "오류", "SET-HOOKPATH", r, f"{ev} 훅 스크립트가 없다: {sc}")
        perm = s.get("permissions") or {}
        for d in perm.get("deny") or []:
            if "git push" in d:
                note = PUSH_NOTE.get(ENV.get("HARNESS_AGENT_PUSH", ""), "에이전트 push 정책은 harness.env HARNESS_AGENT_PUSH 로 정한다.")
                add(7, "정보", "SET-PUSHDENY", r, f"deny '{d}'. {note}", "references/drift-and-settings.md#7-설정")
        for a in perm.get("allow") or []:
            if BROAD_ALLOW.match(a.strip()):
                add(7, "경고", "SET-BROADALLOW", r, f"allow '{a}' 는 임의 변경·실행을 연다.")
        if sp.name == "settings.local.json" and inrepo:
            if run(["git", "check-ignore", "-q", str(sp)], cwd=repo) is None:
                add(7, "경고", "SET-LOCALIGNORE", r, "settings.local.json 이 무시되지 않는다(개인 설정이 커밋될 수 있음).")
    if nested:  # 반입 사본(intake/<이름>/) 등: 바깥 저장소의 git 상태는 이 대상의 것이 아니다
        add(7, "정보", "SET-NOGIT", repo, f"자기 git 저장소가 아니다(바깥 저장소 {nested.strip()} 안의 하위 디렉터리). "
            "반입 사본이면 정상이다. git 기반 검사(7의 나머지, 9 worktree)는 건너뛴다.", "references/drift-and-settings.md#7-설정")
        return
    if not inrepo:
        add(7, "경고", "SET-NOGIT", repo, "git 저장소가 아니다.")
        return
    ign = run(["git", "check-ignore", "-v", ".claude/worktrees/x"], cwd=repo)
    if ign is None:
        add(7, "경고", "SET-WTIGNORE", ".gitignore", "`.claude/worktrees/` 가 무시되지 않는다. worktree 가 생기면 git status 가 범람한다.",
            "references/drift-and-settings.md#7-설정")
    elif "info/exclude" in ign.split(":")[0] or not ign.split(":")[0].endswith(".gitignore"):
        add(7, "정보", "SET-WTIGNORE", ign.split(":")[0],
            "`.claude/worktrees/` 를 이 기기의 로컬 exclude 로만 무시한다. clone 에는 없다(.gitignore 한 줄 후보).")
    tracked = run(["git", "ls-files", "--", ".claude", "CLAUDE.md"], cwd=repo) or ""
    if not tracked.strip() and ((repo / ".claude").is_dir() or (repo / "CLAUDE.md").is_file()):
        add(7, "오류", "SET-UNTRACKED", repo, "`.claude/` 와 CLAUDE.md 가 한 번도 커밋되지 않았다.")
    else:
        st = run(["git", "status", "--porcelain", "--untracked-files=all", "--", ".claude", "CLAUDE.md", "GEMINI.md", "AGENTS.md"],
                 cwd=repo, timeout=60) or ""
        unt = [l for l in st.split("\n") if l.startswith("??")]
        mod = [l for l in st.split("\n") if l and not l.startswith("??")]
        if unt or mod:
            add(7, "정보", "SET-DIRTY", repo, f"에이전트 문서 중 미추적 {len(unt)}개, 미커밋 변경 {len(mod)}개.")


# ------------------------------------------- 5·6·8 툴킷 (공용 도우미)
def mise_tools(p):
    try:
        data = tomllib.loads(read(p) or "")
    except tomllib.TOMLDecodeError:
        return None
    tools = {}
    for k, v in (data.get("tools") or {}).items():
        short = k.split("/")[-1].split(":")[-1]
        tools[short] = v if isinstance(v, str) else (v.get("version") if isinstance(v, dict) else str(v))
    return tools


def toml_conf(p):
    try:
        return tomllib.loads(read(p) or "")
    except tomllib.TOMLDecodeError:
        return None


_SIBS = {}


def sibling_repos(repo, projects):
    """형제 저장소 경로. 자기 자신, 같은 git 저장소의 worktree, 위임·초안 사본(<repo>-agy 등)은 뺀다."""
    key = (str(repo), str(projects))
    if key not in _SIBS:
        mine = common_dir(repo)
        out = []
        for p in sorted(projects.iterdir()) if projects.is_dir() else []:
            if not p.is_dir() or p.resolve() == Path(repo).resolve() or p.name.endswith(COPY_SUFFIXES):
                continue
            if mine and (p / ".git").exists() and common_dir(p) == mine:
                continue
            out.append(p)
        _SIBS[key] = out
    return _SIBS[key]


def pin_mismatch(repo, projects, mine, tools):
    """mine(이 저장소 mise 핀)과 형제 저장소 핀이 다른 도구마다 '도구: 값(저장소, …)' 문자열.
    D-05 처럼 목표값이 확정되지 않은 동안에는 목표와 비교하지 않고 저장소 사이 불일치만 본다."""
    out = []
    theirs = {}
    for sib in sibling_repos(repo, projects):
        t = mise_tools(sib / "mise.toml") if (sib / "mise.toml").is_file() else None
        for k in tools:
            if t and k in t:
                theirs.setdefault(k, {}).setdefault(t[k], []).append(sib.name)
    for k in tools:
        others = {v: names for v, names in theirs.get(k, {}).items() if v != mine.get(k)}
        if others:
            out.append(f"{k} {mine.get(k, '없음')} ↔ " + ", ".join(f"{v}({'·'.join(n)})" for v, n in sorted(others.items())))
    return out


def detect_toolkits(repo, files, force=None):
    """{이름: [감지 표식]}. force 가 있으면 그 목록을 감지와 무관하게 켠다('none' 이면 모두 끈다)."""
    ctx = toolkit_ctx(repo, files, repo.parent, set(), None)
    out = {}
    for name, tk in TOOLKITS.items():
        if force is not None:
            if name in force:
                out[name] = ["--toolkits 로 켬"]
            continue
        marks = tk.detect(ctx)
        if marks:
            out[name] = marks
    return out


def toolkit_ctx(repo, files, projects, only, kb):
    def kb_path(name):
        if kb:
            return kb
        cand = projects / f"{name}-kb"
        return cand if cand.is_dir() else WORKSPACE / f"{name}-kb"
    return SimpleNamespace(
        repo=repo, files=files, projects=projects, env=ENV, want=lambda n: n in only, add=add, kb=kb_path,
        read=read, md5=md5, run=run, rel=rel, inside=inside, strip_code=strip_code, rule_files=rule_files,
        common_dir=common_dir, mise_tools=mise_tools, toml=toml_conf,
        pin_mismatch=lambda mine, tools: pin_mismatch(repo, projects, mine, tools),
    )


def run_toolkits(repo, files, projects, only, kb, active):
    ctx = toolkit_ctx(repo, files, projects, only, kb)
    for name in active:
        TOOLKITS[name].check(ctx)


# ----------------------------------------------------- 10 메모리 이식성 (구현은 memory_checks.py)
def check_memory(repo, user=False):
    spec = importlib.util.spec_from_file_location("memory_checks", HERE.parent / "memory_checks.py")
    mc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mc)
    ms = mc.load_signals([HERE.parent])
    if ms is None:
        add(10, "정보", "MEM-SKIP", HERE.parent, "memory_signals.py 가 없어 메모리 검사를 건너뛴다")
        return
    mc.run(add, ms, USER_HOME, repo=repo, user=user)


# ----------------------------------------------------- 9 worktree
def check_worktrees(repo, now):
    wts = worktrees(repo) if git_root(repo) else []
    sess = claude_sessions()
    if not wts:
        return []
    main = Path(wts[0]["worktree"])
    gitdir = Path(common_dir(repo) or main / ".git")
    rows = []
    for w in wts[1:]:
        path = Path(w["worktree"])
        locked = w.get("locked")
        live = [f"{exe}:{pid}" for pid, cwd, me, exe in sess if inside(cwd, path) and not me]
        meta = gitdir / "worktrees" / path.name
        mt = 0.0
        for q in (meta / "index", meta / "HEAD", meta / "logs" / "HEAD", path):
            try:
                mt = max(mt, q.stat().st_mtime)
            except OSError:
                pass
        idle_h = (now - mt) / 3600 if mt else None
        dirty = run(["git", "status", "--porcelain"], cwd=path, timeout=20) if path.is_dir() else None
        ndirty = len([l for l in (dirty or "").split("\n") if l.strip()]) if dirty is not None else None
        head = w.get("HEAD")
        ahead = run(["git", "rev-list", "--count", f"{wts[0].get('HEAD', 'HEAD')}..{head}"], cwd=main) if head else None
        row = {"path": str(path), "branch": w.get("branch", "(detached)"), "locked": bool(locked), "live": live,
               "idle_h": round(idle_h, 1) if idle_h is not None else None, "dirty": ndirty,
               "unmerged": int(ahead) if ahead and ahead.strip().isdigit() else None,
               "prunable": bool(w.get("prunable"))}
        rows.append(row)
        busy = locked or live or (idle_h is not None and idle_h < 2) or path == repo or inside(repo, path)
        desc = (f"브랜치 {row['branch'].replace('refs/heads/', '')}, lock={'예' if locked else '아니오'}, "
                f"세션={live or '없음'}, 마지막 활동 {row['idle_h']}시간 전, 미커밋 {ndirty}, 메인에 없는 커밋 {row['unmerged']}")
        if inside(repo, path):
            continue
        if busy:
            add(9, "정보", "WT-ACTIVE", path, "쓰는 중일 수 있다(정리 금지). " + desc)
        else:
            add(9, "경고", "WT-CANDIDATE", path, "정리 후보. 삭제는 HUMAN_TODO 로. " + desc,
                "references/worktrees.md#9-worktree-위생")
    reg = {str(Path(w["worktree"]).resolve()) for w in wts}
    wd = main / ".claude" / "worktrees"
    if wd.is_dir():
        for d in wd.iterdir():
            if d.is_dir() and str(d.resolve()) not in reg:
                add(9, "경고", "WT-ORPHAN", d, "git worktree 목록에 없는 디렉터리. 내용 확인 뒤 HUMAN_TODO 로.")
    return rows


# ----------------------------------------------------------- 출력
SEV_ORDER = {"오류": 0, "경고": 1, "정보": 2}
TITLES = {10: "메모리 이식성", 0: "실행 중인 세션", 1: "상시 로드량", 2: "rules 구성", 3: "스킬 상태", 4: "낡음과 모순",
          5: "공유 지식 쏠림(툴킷 KB)", 6: "복제본 표류", 7: "설정", 8: "툴체인(툴킷)", 9: "worktree 위생"}


def render(target, extra, today):
    out = [f"# harness-doctor 진단: {target}", "",
           f"- scan.py v{VERSION}, {today}. 읽기 전용 검사. 판단이 필요한 항목은 경고·정보로 냈다.",
           "- 집계: " + ", ".join(f"{s} {sum(1 for f in findings if f['sev'] == s)}" for s in SEV_ORDER)]
    tks = extra.get("toolkits")
    if tks is not None:
        out.append("- 툴킷: " + ("; ".join(f"{k} ({', '.join(v[:3])}) → `{TOOLKITS[k].REFERENCE}`" for k, v in tks.items())
                                 if tks else "감지 없음(코어 검사만)"))
    out.append("")
    load = extra.get("load")
    if load:
        t = load["total"]
        out += ["## 상시 로드 파일", "", "| 파일 | 경로 | 줄 | 바이트 | 글자 |", "|---|---|---:|---:|---:|"]
        out += [f"| {r['file']} | {r['via']} | {r['lines']} | {r['bytes']:,} | {r['chars']:,} |" for r in load["files"]]
        out += [f"| **합계** | | **{t['lines']}** | **{t['bytes']:,}** | **{t['chars']:,}** |", ""]
    for item in sorted({f["item"] for f in findings}):
        out += [f"## {item}. {TITLES[item]}", "", "| 등급 | 코드 | 위치 | 내용 |", "|---|---|---|---|"]
        for f in sorted((f for f in findings if f["item"] == item), key=lambda f: SEV_ORDER[f["sev"]]):
            msg = f["msg"].replace("|", "\\|") + (f" → `{f['ref']}`" if f["ref"] else "")
            out.append(f"| {f['sev']} | {f['code']} | `{f['where']}` | {msg} |")
        out.append("")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("repo", nargs="?")
    ap.add_argument("--user", action="store_true", help="사용자 레벨(정본 home/.claude)을 본다")
    ap.add_argument("--sessions", action="store_true", help="세션 확인만 한다")
    ap.add_argument("--only", help="항목 번호 목록, 예: 1,2,3")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--today", help="YYYY-MM-DD (기본: 오늘)")
    ap.add_argument("--projects", help="형제 저장소 루트 (기본: 저장소의 부모)")
    ap.add_argument("--kb", help="툴킷 공유 지식 저장소 경로 (기본: <projects>/<툴킷>-kb, 없으면 <작업공간>/<툴킷>-kb)")
    ap.add_argument("--toolkits", help="켤 툴킷을 감지와 무관하게 지정 (예: luau,web / none)")
    ap.add_argument("--env", action="store_true", help="harness.env 값과 툴킷 목록만 보인다")
    a = ap.parse_args()
    if a.env:
        print(f"# harness.env: {ENV.get('_file') or '(없음 — 기본값)'}")
        print(f"DOCTOR_ROOT={DOCTOR_ROOT or '(모름)'}\nWORKSPACE={WORKSPACE}\nCANON_HOME={CANON_HOME}\nUSER_HOME={USER_HOME}")
        for k, v in sorted(ENV.items()):
            if not k.startswith("_"):
                print(f"{k}={v}")
        wrap = heavy_wrap()
        print(f"# 무거운 실행 래퍼: {' '.join(wrap) or '없음(끔)'}")
        print("# 툴킷: " + ", ".join(f"{k} → {getattr(t, 'REFERENCE', '')}" for k, t in TOOLKITS.items()))
        return 0
    today = dt.date.fromisoformat(a.today) if a.today else dt.date.today()
    only = {int(x) for x in a.only.split(",")} if a.only else set(range(11))
    extra = {}
    if a.user:
        target = CANON_HOME
        if 1 in only:
            extra["load"] = check_load(target, user=True)
        if 2 in only:
            check_rules(target, [], user=True)
        if 3 in only:
            extra["skills"] = check_skills(target, user=True)
            if USER_HOME.resolve() != CANON_HOME.resolve():
                for sd in skill_dirs(USER_HOME, user=True):
                    if not (CANON_HOME / "skills" / sd.name).exists() and not sd.is_symlink():
                        extra["skills"].append(check_skill(sd, USER_HOME))
                        add(3, "정보", "SKILL-UNMANAGED", USER_HOME / "skills" / sd.name,
                            "정본(home/.claude)에도 MANIFEST 링크에도 없는 사용자 스킬이다.")
        if 10 in only:
            check_memory(None, user=True)
        manifest = DOCTOR_ROOT / "home" / "MANIFEST" if DOCTOR_ROOT else None
        if manifest and manifest.is_file():
            scope = {"HARNESS_DOCTOR_ROOT": str(DOCTOR_ROOT), "HARNESS_WORKSPACE": str(WORKSPACE)}
            scope.update({k: v for k, v in ENV.items() if v and not k.startswith("_")})
            for line in (read(manifest) or "").split("\n"):
                parts = line.split()
                if len(parts) == 3 and parts[0] == "link":
                    parts[2] = ENVLIB.expand(parts[2], scope) if ENVLIB else os.path.expandvars(parts[2])
                    if not Path(parts[2]).exists():
                        add(3, "오류", "LINK-TARGET", f"MANIFEST: {parts[1]}", f"링크 대상이 없다: {parts[2]}")
                    elif (Path(parts[2]) / "SKILL.md").is_file() and 3 in only:
                        extra.setdefault("skills", []).append(check_skill(Path(parts[2]), Path(parts[2]).parent))
        if 7 in only:
            for p in (CANON_HOME / "settings.json", USER_HOME / "settings.json"):
                s, err = load_json(p)
                if err:
                    add(7, "오류", "SET-JSON", p, f"JSON 파싱 실패: {err}")
                for ev, mt, cmd in hook_cmds(s):
                    sc = script_of(cmd)
                    if sc and not os.path.isfile(script_path(sc)):
                        add(7, "오류", "SET-HOOKPATH", p, f"{ev} 훅 스크립트가 없다: {sc}")
            add(7, "정보", "SET-SYNC", "tools/home-sync.sh", "정본과 실제의 차이는 `tools/home-sync.sh status` 로 본다.")
    else:
        if not a.repo:
            ap.error("저장소 경로가 필요하다 (또는 --user)")
        target = Path(a.repo).resolve()
        if not target.is_dir():
            ap.error(f"디렉터리가 아니다: {target}")
        projects = Path(a.projects).resolve() if a.projects else target.parent
        kb = Path(a.kb).resolve() if a.kb else None
        if a.sessions:
            only = {0}
        files = repo_files(target) if only - {0} else []
        force = None if not a.toolkits else {x.strip() for x in a.toolkits.split(",")} - {"none"}
        bad = (force or set()) - set(TOOLKITS)
        if bad:
            ap.error(f"모르는 툴킷: {', '.join(sorted(bad))} (있는 것: {', '.join(TOOLKITS)})")
        active = detect_toolkits(target, files, force) if only - {0} else {}
        if only - {0}:
            extra["toolkits"] = active
        steps = [
            (0, lambda: extra.__setitem__("sessions", check_sessions(target))),
            (1, lambda: extra.__setitem__("load", check_load(target))),
            (2, lambda: extra.__setitem__("rules", check_rules(target, files))),
            (3, lambda: extra.__setitem__("skills", check_skills(target))),
            (4, lambda: check_stale(target, today)),
            (6, lambda: check_drift(target, files, projects)),
            (7, lambda: check_settings(target, files)),
            (10, lambda: check_memory(target)),
            (9, lambda: extra.__setitem__("worktrees", check_worktrees(target, dt.datetime.now().timestamp()))),
        ]
        for n, fn in steps:
            if n in only:
                fn()
        if only & {5, 6, 8}:  # 툴킷 검사는 감지된 툴킷만, 항목 5(공유 지식)·6(사본)·8(툴체인)에 낸다
            run_toolkits(target, files, projects, only, kb, active)
    if a.json:
        print(json.dumps({"target": str(target), "today": str(today), "findings": findings, **extra},
                         ensure_ascii=False, indent=1, default=str))
    else:
        print(render(target, extra, today))
    return 2 if any(f["sev"] == "오류" for f in findings) else (1 if findings else 0)


if __name__ == "__main__":
    sys.exit(main())
