"""harness-doctor 툴킷 공용 부분: 툴킷 감지, 툴킷에 넘기는 ctx(kb_path 포함), 툴킷 실행, mise 핀 비교. 읽기 전용.

scan.py 가 경로로 적재하고 C 에 자기 자신을 걸어 둔다. 공용 함수·상수·add 는 C.<이름> 으로 부른다(호출 시점에 찾는다).
"""
import tomllib
from pathlib import Path
from types import SimpleNamespace

C = None


# ------------------------------------------- 5·6·8 툴킷 (공용 도우미)
def mise_tools(p):
    try:
        data = tomllib.loads(C.read(p) or "")
    except tomllib.TOMLDecodeError:
        return None
    tools = {}
    for k, v in (data.get("tools") or {}).items():
        short = k.split("/")[-1].split(":")[-1]
        tools[short] = v if isinstance(v, str) else (v.get("version") if isinstance(v, dict) else str(v))
    return tools


def toml_conf(p):
    try:
        return tomllib.loads(C.read(p) or "")
    except tomllib.TOMLDecodeError:
        return None


_SIBS = {}


def sibling_repos(repo, projects):
    """형제 저장소 경로. 자기 자신, 같은 git 저장소의 worktree, 위임·초안 사본(<repo>-agy 등)은 뺀다."""
    key = (str(repo), str(projects))
    if key not in _SIBS:
        mine = C.common_dir(repo)
        out = []
        for p in sorted(projects.iterdir()) if projects.is_dir() else []:
            if not p.is_dir() or p.resolve() == Path(repo).resolve() or p.name.endswith(C.COPY_SUFFIXES):
                continue
            if mine and (p / ".git").exists() and C.common_dir(p) == mine:
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
    for name, tk in C.TOOLKITS.items():
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
        pack = (C.DOCTOR_ROOT or C.WORKSPACE / "claude-doctor") / "packs" / f"{name}-kb"
        for cand in (projects / f"{name}-kb", pack):
            if cand.is_dir():
                return cand
        return C.WORKSPACE / f"{name}-kb"
    return SimpleNamespace(
        repo=repo, files=files, projects=projects, env=C.ENV, want=lambda n: n in only, add=C.add, kb=kb_path,
        read=C.read, md5=C.md5, run=C.run, rel=C.rel, inside=C.inside, strip_code=C.strip_code, rule_files=C.rule_files,
        common_dir=C.common_dir, mise_tools=mise_tools, toml=toml_conf,
        pin_mismatch=lambda mine, tools: pin_mismatch(repo, projects, mine, tools),
    )


def run_toolkits(repo, files, projects, only, kb, active):
    ctx = toolkit_ctx(repo, files, projects, only, kb)
    for name in active:
        C.TOOLKITS[name].check(ctx)
