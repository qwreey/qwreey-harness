"""harness-doctor 항목 10: auto memory 이식성 검사 (MEM-ORPHAN, MEM-REPO, MEM-SIZE). 읽기 전용.

scan.py 가 경로로 적재해 run(...) 만 부른다. 판정 로직(저장소 지식 신호, 키 규칙)은 같은 디렉터리의 memory_signals.py(qwreey-conventions 정본의 사본)와 공유한다.
  - 저장소 모드: 그 저장소의 키(와 worktree 메인 키)의 메모리만 본다. MEM-ORPHAN 은 이 저장소로 짝지어지는 고아 키만 낸다.
  - 사용자 모드(--user): 모든 키를 본다.
근거: audit/23. 키 규칙과 25KB·200줄 한도는 2.1.316 실측과 공식 문서(memory.md)다.
"""
import importlib.util
import json
import os
import re
import subprocess
from pathlib import Path

LINES_LIMIT = 200
BYTES_LIMIT = 25 * 1024
NEAR = 0.8
REPO_STRONG_SCORE = 5


def load_signals(candidates):
    for lib in candidates:
        f = Path(lib) / "memory_signals.py"
        if f.is_file():
            spec = importlib.util.spec_from_file_location("memory_signals", f)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod
    return None


def _git(args, cwd):
    try:
        p = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=10, env=dict(os.environ, GIT_OPTIONAL_LOCKS="0"))
        return p.stdout.strip() if p.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def memory_files(mdir):
    try:
        return sorted(p for p in Path(mdir).iterdir() if p.suffix == ".md" and p.is_file())
    except OSError:
        return []


def project_keys(root):
    """{key: Path(memory dir)} for keys whose memory dir holds at least one .md file (empty dirs are auto-created, ignored)."""
    out = {}
    try:
        for d in Path(root).iterdir():
            if d.is_dir() and memory_files(d / "memory"):
                out[d.name] = d / "memory"
    except OSError:
        pass
    return out


def session_cwds(keydir, limit=5):
    """Original working directories recorded in the key's session logs (first `limit` distinct)."""
    seen = []
    for f in sorted(Path(keydir).glob("*.jsonl"))[:limit]:
        try:
            with open(f, errors="replace") as fh:
                for i, line in enumerate(fh):
                    if i > 40:
                        break
                    m = re.search(r'"cwd"\s*:\s*"([^"]+)"', line)
                    if m and m.group(1) not in seen:
                        seen.append(m.group(1))
                        break
        except OSError:
            continue
    return seen


def pair_candidates(ms, key, mdir, live):
    """Candidates for where an orphaned memory went. live: {key: Path}. Returns [(path, why)] strongest first."""
    texts = "\n".join((f.read_text(errors="replace")[:50_000]) for f in memory_files(mdir))
    old_cwds = session_cwds(mdir.parent)
    names = {os.path.basename(c.rstrip("/")) for c in old_cwds}
    if not names:
        names = {key.rsplit("-", 1)[-1]}
    cands = {}
    for path in re.findall(r"(?<![\w.~])/[\w.+-]+(?:/[\w.+-]+)+", texts):
        p = Path(path.rstrip("."))
        while not p.exists() and p != p.parent:
            p = p.parent
        root = _git(["rev-parse", "--show-toplevel"], p if p.is_dir() else p.parent) if p != Path("/") else ""
        if root and ms.key_of(root) != key:
            cands.setdefault(root, []).append("memory text mentions this path")
    for lk, lp in live.items():
        if lk == key:
            continue
        if lp.name in names:
            cands.setdefault(str(lp), []).append(f"same directory name '{lp.name}'")
        url = _git(["remote", "get-url", "origin"], lp) if (lp / ".git").exists() else ""
        if url and url in texts:
            cands.setdefault(str(lp), []).append("origin URL appears in the memory text")
    return sorted(((p, "; ".join(dict.fromkeys(w))) for p, w in cands.items()), key=lambda x: -len(x[1]))[:5]


def run(add, ms, home, repo=None, user=False, root="/"):
    """Adds findings (item 10). repo: Path of the target repository (repo mode). home: config dir (~/.claude). root: filesystem root for key resolution."""
    projects = Path(home) / "projects"
    keys = project_keys(projects)
    resolved = {k: ms.resolve_key(k, root) for k in keys}
    own = set()
    if repo and not user:
        tops = [_git(["rev-parse", "--show-toplevel"], repo) or str(repo)]
        main = _git(["worktree", "list", "--porcelain"], repo).split("\n")[0].replace("worktree ", "", 1)
        if main:
            tops.append(main)
        own = {ms.key_of(t) for t in tops}
        custom = ms.memory_dirs(repo, home)["custom"]
        for c in custom:
            if memory_files(c):
                keys[f"(autoMemoryDirectory) {c}"] = c
                resolved[f"(autoMemoryDirectory) {c}"] = Path(repo)
                own.add(f"(autoMemoryDirectory) {c}")
    live = {k: p for k, p in resolved.items() if p}
    for k, mdir in sorted(keys.items()):
        if (repo and not user) and k not in own:
            if not resolved[k]:  # orphan: report here only if it pairs with this repo
                c = [x for x in pair_candidates(ms, k, mdir, live) if os.path.realpath(x[0]) == os.path.realpath(repo)]
                if c:
                    add(10, "경고", "MEM-ORPHAN", mdir, f"경로가 사라진 키 `{k}` 의 메모리 {len(memory_files(mdir))}개가 이 저장소로 짝지어진다({c[0][1]}). "
                        "옮기기: `scripts/memory_move.py` (기본 dry-run, 동의 후 복사)", "references/memory-portability.md")
            continue
        if not resolved[k] and not k.startswith("(auto"):
            cands = pair_candidates(ms, k, mdir, live)
            hint = ("짝 후보: " + ", ".join(f"{p} ({w})" for p, w in cands)) if cands else "짝 후보 없음"
            add(10, "경고", "MEM-ORPHAN", mdir, f"키 `{k}` 의 경로가 사라졌다. 메모리 {len(memory_files(mdir))}개가 안 읽힌다. {hint}",
                "references/memory-portability.md")
        _size(add, mdir)
        _repo_knowledge(add, ms, mdir)


def _size(add, mdir):
    idx = Path(mdir) / "MEMORY.md"
    try:
        text = idx.read_text(errors="replace")
        size = idx.stat().st_size
    except OSError:
        return
    n = text.count("\n") + (0 if text.endswith("\n") or not text else 1)
    if n > LINES_LIMIT or size > BYTES_LIMIT:
        add(10, "경고", "MEM-SIZE", idx, f"MEMORY.md {n}줄 {size:,}B: 한도(앞 {LINES_LIMIT}줄 또는 {BYTES_LIMIT:,}B)를 넘어 뒤쪽은 세션 시작 때 읽히지 않는다. 한 줄 요약만 남기고 상세는 토픽 파일로",
            "references/memory-portability.md")
    elif n >= LINES_LIMIT * NEAR or size >= BYTES_LIMIT * NEAR:
        add(10, "정보", "MEM-SIZE", idx, f"MEMORY.md {n}줄 {size:,}B: 한도(앞 {LINES_LIMIT}줄 또는 {BYTES_LIMIT:,}B)의 80% 를 넘었다", "references/memory-portability.md")


def _repo_knowledge(add, ms, mdir):
    for f in memory_files(mdir):
        if f.name == "MEMORY.md":
            continue
        verdict, score, sig, typ = ms.classify(f.read_text(errors="replace"))
        if verdict == "repo":
            add(10, "경고" if score >= REPO_STRONG_SCORE else "정보", "MEM-REPO", f,
                f"저장소 지식으로 보인다(type={typ or '없음'}, 점수 {score}: {ms.describe(sig, 2)}). 후보일 뿐이니 원문을 읽고 판정", "references/memory-portability.md")
