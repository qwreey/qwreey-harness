#!/usr/bin/env python3
"""harness-doctor 결정적 검사기. 읽기 전용이다. 대상 저장소에 아무것도 쓰지 않는다.

사용:
  python3 -I scan.py <저장소 경로> [--only 1,3,9] [--json] [--today YYYY-MM-DD]
  python3 -I scan.py --user            사용자 레벨(정본 home/.claude 와 실제 ~/.claude)
  python3 -I scan.py --sessions <경로>  실행 중인 Claude 세션만 본다

  python3 -I scan.py --env              읽은 harness.env 값과 쓸 수 있는 툴킷을 보인다

항목 번호: 0 세션, 1 상시 로드, 2 rules, 3 스킬, 4 낡음·모순, 5 공유 지식 후보(툴킷),
          6 복제본 표류, 7 설정(+도메인 팩 pack_checks.py), 8 툴체인(툴킷), 9 worktree, 10 메모리 이식성(memory_checks.py).
코어(이 파일)는 언어와 무관한 검사만 한다. 항목별 구현은 같은 디렉터리의 scan_load.py(1·2·3), scan_stale.py(4),
scan_settings.py(6·7), scan_toolkit.py(툴킷 감지·ctx·실행)가 맡고, 이 파일은 공용 도우미·세션·worktree·출력·main 을 둔다. 언어·툴체인 검사는 toolkits/<이름>.py 가 맡고,
저장소마다 감지 표식이 있을 때만 켠다(--toolkits 로 강제). 환경 고유값은 harness.env 층(~/.claude/harness.env, 저장소 .claude/harness.env,
.claude/harness.local.env)에서 읽는다.
판단이 필요한 것은 '경고'나 '정보'로만 낸다. 고칠지는 모델과 사용자가 정한다.
표준 라이브러리만 쓴다. git 은 GIT_OPTIONAL_LOCKS=0 으로 불러 인덱스를 건드리지 않는다.
"""
import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path

VERSION = "2"
HERE = Path(__file__).resolve()
USER_HOME = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
# 이 파일은 <claude-doctor>/plugins/q/skills/doctor/scripts/scan.py 다. 플러그인 캐시(~/.claude/plugins/...)로 설치되면
# claude-doctor 위치를 모르므로 HARNESS_DOCTOR_ROOT 환경 변수나 harness.env 로 알려야 정본 관련 검사가 켜진다.
_PATH_ROOT = HERE.parents[5] if (HERE.parents[4].name == "plugins" and (HERE.parents[5] / "home" / "MANIFEST").is_file()) else None


# /q:doctor 만 읽는 harness.env 키 가운데 저장소 층이 바꾸지 못하는 것.
# HARNESS_AGENT_PUSH: 에이전트 git push 정책, normal(에이전트 push 가 정상 흐름) | deny | 빈 값(모름). scan_settings.py 가 읽는다.
# 환경을 설명하는 사용자의 말이라 클론한 저장소가 바꾸면 안 된다.
ENV_USER_ONLY = frozenset({"HARNESS_AGENT_PUSH"})


def _load_env():
    """harness.env 층(옆의 harness_env.py 사본의 load_layers)과 그 모듈. 설치된 ~/.claude/lib 판은 옛 판일 수 있어 쓰지 않는다.
    사용자 층은 ~/.claude/harness.env, 없으면 클론의 정본 home/.claude/harness.env. 저장소 층은 $CLAUDE_PROJECT_DIR, 없으면 cwd
    (검사 대상 저장소 인자가 아니다: ENV 는 인자를 읽기 전에 정한다)."""
    try:
        sys.path.insert(0, str(HERE.parent))
        import harness_env as mod
        cands = [USER_HOME / "harness.env"] + ([_PATH_ROOT / "home" / ".claude" / "harness.env"] if _PATH_ROOT else [])
        return mod.load_layers(mod.project_dir(os.getcwd()), candidates=cands, user_only=ENV_USER_ONLY), mod
    except Exception:
        return {}, None


ENV, ENVLIB = _load_env()
# 우선순위: 환경 변수 > 이 파일의 위치 > harness.env. 셋 다 없으면 정본 관련 검사(MANIFEST, 훅 사본)를 건너뛴다.
_root = os.environ.get("HARNESS_DOCTOR_ROOT") or (str(_PATH_ROOT) if _PATH_ROOT else ENV.get("HARNESS_DOCTOR_ROOT"))
DOCTOR_ROOT = Path(_root) if _root else None
CANON_HOME = DOCTOR_ROOT / "home" / ".claude" if DOCTOR_ROOT else USER_HOME
WORKSPACE = Path(ENV.get("HARNESS_WORKSPACE") or (DOCTOR_ROOT.parent if DOCTOR_ROOT else Path.cwd()))
# 위임 작업공간, 초안 사본 접미(<repo>-<접미>). 형제 비교와 `all` 에서 뺀다.
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
    try:
        procs = list(Path("/proc").iterdir())
    except OSError:  # /proc 이 없는 플랫폼(Windows, macOS): 살아 있는 세션 검사를 건너뛴다
        return out
    for d in procs:
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


# ---------------------------------------------------- 검사 모듈(같은 디렉터리)
# -I 라 sys.path 에 기대지 않고 경로로 적재한다. 모듈은 공용 함수를 C(이 모듈)에서 호출 시점에 찾는다.
def _part(name, *exports):
    spec = importlib.util.spec_from_file_location(name, HERE.parent / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.C = sys.modules[__name__]
    globals().update({n: getattr(mod, n) for n in exports})


_part("scan_load", "rule_files", "check_load", "check_rules", "skill_dirs", "check_skill", "check_skills")
_part("scan_stale", "check_stale")
_part("scan_settings", "load_json", "hook_cmds", "script_of", "script_path", "common_dir", "check_drift", "check_settings")
_part("scan_toolkit", "detect_toolkits", "run_toolkits")


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


# ----------------------------------------------------- 7 도메인 팩 (구현은 pack_checks.py)
def check_packs(repo, active):
    spec = importlib.util.spec_from_file_location("pack_checks", HERE.parent / "pack_checks.py")
    pc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pc)
    pc.run(add, repo, active, USER_HOME, ENV.get("HARNESS_CODERAG"))


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
    ap.add_argument("--kb", help="툴킷 공유 지식 저장소 경로 (기본: <projects>/<툴킷>-kb, 없으면 <doctor>/packs/<툴킷>-kb, 그것도 없으면 <작업공간>/<툴킷>-kb)")
    ap.add_argument("--toolkits", help="켤 툴킷을 감지와 무관하게 지정 (예: luau,web / none)")
    ap.add_argument("--env", action="store_true", help="harness.env 값과 툴킷 목록만 보인다")
    a = ap.parse_args()
    if a.env:
        print(f"# harness.env 층(낮은 층부터): {ENV.get('_files') or '(없음 - 기본값)'}")
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
            (7, lambda: check_packs(target, active)),
            (10, lambda: check_memory(target)),
            (9, lambda: extra.__setitem__("worktrees", check_worktrees(target, dt.datetime.now().timestamp()))),
        ]
        for n, fn in steps:
            if n in only:
                fn()
        if only & {5, 6, 8}:  # 툴킷 검사는 감지된 툴킷만, 항목 5(공유 지식), 6(사본), 8(툴체인)에 낸다
            run_toolkits(target, files, projects, only, kb, active)
    if a.json:
        print(json.dumps({"target": str(target), "today": str(today), "findings": findings, **extra},
                         ensure_ascii=False, indent=1, default=str))
    else:
        print(render(target, extra, today))
    return 2 if any(f["sev"] == "오류" for f in findings) else (1 if findings else 0)


if __name__ == "__main__":
    sys.exit(main())
