"""harness-doctor 툴킷 공용 부분: 툴킷 감지, 툴킷에 넘기는 ctx(kb_path 포함), 툴킷 실행, mise 핀 비교. 읽기 전용.

scan.py 가 경로로 적재하고 C 에 자기 자신을 걸어 둔다. 공용 함수·상수·add 는 C.<이름> 으로 부른다(호출 시점에 찾는다).
"""
import json
import tomllib
from pathlib import Path
from types import SimpleNamespace

C = None


# ------------------------------------------- 5, 6, 8 툴킷 (공용 도우미)
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
    핀 값은 저장소 소유라(D-05) 목표와 비교하지 않고 저장소 사이 불일치만 본다."""
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


def installed_plugin(name):
    """설치된 플러그인 <name>@<아무 마켓> 의 설치 폴더 또는 None(installed_plugins.json 의 첫 installPath)."""
    try:
        data = json.loads((C.USER_HOME / "plugins" / "installed_plugins.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    plugins = data.get("plugins") if isinstance(data, dict) else None
    for pid, recs in sorted((plugins or {}).items()):
        if pid.rpartition("@")[0] == name and isinstance(recs, list):
            for r in recs:
                p = Path(r.get("installPath") or "") if isinstance(r, dict) else None
                if p and p.is_dir():
                    return p
    # 설치 기록이 없어도 로컬 폴더 마켓의 상대 경로 플러그인은 켜기만 하면 제자리에서 실린다. 그 폴더를 마켓 정의에서 찾는다.
    try:
        markets = json.loads((C.USER_HOME / "plugins" / "known_marketplaces.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    for market in sorted(markets if isinstance(markets, dict) else {}):
        loc = markets[market].get("installLocation") if isinstance(markets[market], dict) else None
        if not isinstance(loc, str):
            continue
        try:
            entries = json.loads((Path(loc) / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8")).get("plugins") or []
        except (OSError, ValueError, AttributeError):
            continue
        for e in entries:
            if isinstance(e, dict) and e.get("name") == name and isinstance(e.get("source"), str):
                p = (Path(loc) / e["source"]).resolve()
                if p.is_dir():
                    return p
    return None


def toolkit_ctx(repo, files, projects, only, kb):
    def kb_path(name):
        """툴킷 공유 지식 폴더. 형제 <name>-kb 저장소, 하네스 저장소의 팩, 설치된 팩 플러그인 순. 없으면 없는 형제 경로를 돌려준다(검사가 '없음'으로 낸다)."""
        if kb:
            return kb
        cands = [projects / f"{name}-kb"]
        if C.DOCTOR_ROOT:
            cands.append(C.DOCTOR_ROOT / "packs" / f"{name}-kb")
        for cand in cands:
            if cand.is_dir():
                return cand
        return installed_plugin(f"{name}-kb") or cands[0]
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
