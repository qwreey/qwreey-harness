"""harness-doctor 항목 7(설정) 의 도메인 팩 검사: PACK-MISSING, PACK-DRIFT, PACK-UNUSED, PACK-USER-LEVEL, PACK-NO-CODERAG, PACK-UNREGISTERED, SET-CODERAG-BINARY. 읽기 전용.

팩은 기본 꺼짐(defaultEnabled false) 플러그인이다. 스위치는 프로젝트 coderag.toml 의 [[packs]] 목록 하나이고(rule 주입은 coderag 플러그인이
이 목록을 따른다), `coderag adapt --harness claude` 가 이 목록에서 .claude/settings.json 의 enabledPlugins(스킬 적재)를 만든다.
그래서 이 검사는 목록과 enabledPlugins 가 어긋났는지, 툴킷 표식이 있는데 목록에 없는지를 본다.
목록의 이름은 프로젝트 항목의 path 나 사용자 coderag 설정(`$CODERAG_HOME/coderag.toml`, 기본 ~/.coderag)의 등록으로 경로가 정해진다.
등록이 없으면 coderag 는 그 팩을 조용히 건너뛰므로 PACK-UNREGISTERED 로 알린다.
scan.py 가 경로로 적재해 run(...) 만 부른다. user_home, coderag_bin, coderag_home 은 주입한다(테스트는 실제 ~/.claude 와 PATH 를 읽지 않는다).
"""
import json
import os
import shutil
import tomllib
from pathlib import Path

# 팩 이름 -> (툴킷, 마켓). 팩 이름은 마켓과 무관하게 맞춘다(마켓이 옮겨져도 켜진 것으로 본다). 마켓은 안내 줄에만 쓴다.
PACKS = {
    "web-security": ("web", "claude-doctor-market"),
    "luau-kb": ("luau", "claude-doctor-market"),
}
REF = "plugins/q/skills/doctor/SKILL.md (항목 7, PACK-)"


def _enabled_map(path):
    """{팩 이름: True/False}. 파일이 없거나 깨졌으면 빈 dict."""
    try:
        ep = json.loads(Path(path).read_text(encoding="utf-8")).get("enabledPlugins") or {}
    except (OSError, ValueError, AttributeError):
        return {}
    return {k.split("@")[0]: bool(v) for k, v in ep.items() if isinstance(k, str)}


def _pack_entries(cfg):
    """coderag 설정 파일의 [[packs]] -> {이름: path 또는 None}. 파일이 없거나 깨졌으면 빈 dict."""
    try:
        packs = tomllib.loads(Path(cfg).read_text(encoding="utf-8")).get("packs") or []
    except (OSError, ValueError, AttributeError):
        return {}
    return {p["name"]: p.get("path") for p in packs if isinstance(p, dict) and isinstance(p.get("name"), str)}


def _listed_packs(repo):
    """프로젝트 coderag.toml 의 [[packs]] 이름 집합."""
    return set(_pack_entries(Path(repo) / "coderag.toml"))


def _known_markets(user_home):
    """Marketplace names this machine has added; None when the file is unreadable (then nothing is skipped)."""
    try:
        return set(json.loads((Path(user_home) / "plugins" / "known_marketplaces.json").read_text(encoding="utf-8")))
    except (OSError, ValueError, TypeError):
        return None


def _coderag_ok(coderag_bin):
    """harness.env 의 HARNESS_CODERAG, 없으면 PATH 의 coderag 가 실행 가능한가."""
    cand = coderag_bin or shutil.which("coderag")
    return bool(cand) and os.access(cand, os.X_OK)


def run(add, repo, active, user_home, coderag_bin=None, coderag_home=None):
    """active 는 {툴킷 이름: 표식}. add 는 scan.add 와 같은 시그니처. coderag_bin 은 harness.env HARNESS_CODERAG 값.
    coderag_home 이 없으면 $CODERAG_HOME, 그것도 없으면 ~/.coderag."""
    repo, user_home = Path(repo), Path(user_home)
    coderag_home = Path(coderag_home or os.environ.get("CODERAG_HOME") or Path.home() / ".coderag")
    project_entries = _pack_entries(repo / "coderag.toml")
    registered = _pack_entries(coderag_home / "coderag.toml")
    for name, path in project_entries.items():
        if not (path or registered.get(name)):
            add(7, "경고", "PACK-UNREGISTERED", repo / "coderag.toml",
                f"coderag.toml 의 팩 {name} 이 어디에도 경로가 없다(이 항목에 path 도, {coderag_home / 'coderag.toml'} 등록도 없음). "
                f"coderag 는 이 팩을 조용히 건너뛰어 rule 이 주입되지 않는다. 사용자 coderag 설정에 "
                f'`[[packs]]` `name = "{name}"` `path = "<팩 폴더>"` 를 더한다.', REF)
    proj_file = repo / ".claude" / "settings.json"
    proj = _enabled_map(proj_file)
    proj.update(_enabled_map(repo / ".claude" / "settings.local.json"))  # local 이 project 를 덮는다
    user = _enabled_map(user_home / "settings.json")
    listed_all = _listed_packs(repo)
    known = _known_markets(user_home)
    in_use = False
    for pack, (toolkit, market) in PACKS.items():
        eff = proj[pack] if pack in proj else user.get(pack, False)
        listed = pack in listed_all
        in_use = in_use or listed or eff
        # 아직 추가되지 않은 마켓의 팩은 켤 수 없으니 MISSING 을 내지 않는다(모든 luau 저장소에 소음이 된다).
        installable = known is None or market in known
        if toolkit in active and not listed and pack not in proj and installable:
            marks = "; ".join(active[toolkit][:2])
            add(7, "경고", "PACK-MISSING", repo / "coderag.toml",
                f"{toolkit} 툴킷 표식({marks})이 있는데 도메인 팩 {pack} 이 이 프로젝트의 coderag.toml 에 없다. "
                f'coderag.toml 에 `[[packs]]` 와 `name = "{pack}"` 두 줄을 더하고 `coderag adapt --harness claude` 를 실행한다'
                f"(enabledPlugins 에 {pack}@{market} 가 생긴다. 사용자 승인 뒤).", REF)
        elif toolkit not in active and (listed or eff):
            where = "coderag.toml 목록" if listed else ("프로젝트 enabledPlugins" if proj.get(pack) else "사용자 레벨 enabledPlugins")
            add(7, "정보", "PACK-UNUSED", repo / "coderag.toml" if listed else (proj_file if proj.get(pack) else user_home / "settings.json"),
                f"도메인 팩 {pack} 이 {where}에서 켜져 있는데 {toolkit} 툴킷 표식이 없다. 이 저장소에는 필요 없을 수 있다.", REF)
        if listed and proj.get(pack) is False:
            add(7, "경고", "PACK-DRIFT", proj_file,
                f"도메인 팩 {pack} 이 coderag.toml 에는 있는데 enabledPlugins 에서 false 다. 스킬이 적재되지 않는다. "
                f"coderag adapt 는 명시한 false 를 덮어쓰지 않으니 목록과 settings 중 어느 쪽이 맞는지 사람이 정한다.", REF)
        elif listed and not eff:
            add(7, "경고", "PACK-DRIFT", proj_file,
                f"도메인 팩 {pack} 이 coderag.toml 에는 있는데 enabledPlugins 에 없다. 스킬이 적재되지 않는다. "
                f"`coderag adapt --harness claude` 로 {pack}@{market} 를 더한다.", REF)
        elif not listed and proj.get(pack):
            add(7, "경고", "PACK-DRIFT", proj_file,
                f"도메인 팩 {pack} 이 enabledPlugins 에서 켜져 있는데 coderag.toml 에 없다. rule 이 주입되지 않는다. "
                f'coderag.toml 에 `[[packs]]` 와 `name = "{pack}"` 를 더한다.', REF)
        if user.get(pack):
            add(7, "정보", "PACK-USER-LEVEL", user_home / "settings.json",
                f"도메인 팩 {pack} 이 사용자 레벨 enabledPlugins 에서 켜져 있다. 팩은 프로젝트별로 켠다"
                f"(정본 home/settings-migrations 로 걷어 내고 {toolkit} 저장소의 coderag.toml 목록과 adapt 로 켠다).", REF)
    coderag_on = proj["coderag"] if "coderag" in proj else user.get("coderag", False)
    if in_use and not _coderag_ok(coderag_bin):
        add(7, "경고", "PACK-NO-CODERAG", repo / "coderag.toml",
            "도메인 팩이 켜져 있는데 coderag 바이너리가 없거나 실행할 수 없다(harness.env 의 HARNESS_CODERAG, 없으면 PATH). "
            "팩 rule 이 주입되지 않는다. coderag 를 빌드하고 coderag 플러그인을 설치한다.", REF)
    elif coderag_on and not _coderag_ok(coderag_bin):
        # 팩과 무관: 기록 규약 rule(coderag:agent-records)도 coderag 훅이 싣는다. 래퍼는 바이너리가 없으면 훅에서 조용히 0 으로 끝난다.
        add(7, "경고", "SET-CODERAG-BINARY", user_home / "settings.json",
            "coderag 플러그인이 켜져 있는데 coderag 바이너리가 없거나 실행할 수 없다(harness.env 의 HARNESS_CODERAG, 없으면 PATH). "
            "훅이 조용히 끝나 기록 규약 rule 이 실리지 않는다. coderag 를 빌드한다.", REF)
