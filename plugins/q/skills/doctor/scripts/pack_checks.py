"""harness-doctor 항목 7(설정) 의 도메인 팩 검사: PACK-MISSING, PACK-UNUSED, PACK-USER-LEVEL. 읽기 전용.

팩은 기본 꺼짐(defaultEnabled false) 플러그인이라 저장소가 자기 .claude/settings.json 의 enabledPlugins 로 켠다.
툴킷 표식(scan.py detect_toolkits 결과)이 있는 저장소에만 켜지게 하려는 것이다. scan.py 가 경로로 적재해 run(...) 만 부른다.
user_home 은 주입한다(테스트는 실제 ~/.claude 를 읽지 않는다).
"""
import json
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


def _known_markets(user_home):
    """Marketplace names this machine has added; None when the file is unreadable (then nothing is skipped)."""
    try:
        return set(json.loads((Path(user_home) / "plugins" / "known_marketplaces.json").read_text(encoding="utf-8")))
    except (OSError, ValueError, TypeError):
        return None


def run(add, repo, active, user_home):
    """active 는 {툴킷 이름: 표식}. add 는 scan.add 와 같은 시그니처."""
    repo, user_home = Path(repo), Path(user_home)
    proj_file = repo / ".claude" / "settings.json"
    proj = _enabled_map(proj_file)
    proj.update(_enabled_map(repo / ".claude" / "settings.local.json"))  # local 이 project 를 덮는다
    user = _enabled_map(user_home / "settings.json")
    known = _known_markets(user_home)
    for pack, (toolkit, market) in PACKS.items():
        eff = proj[pack] if pack in proj else user.get(pack, False)
        # 아직 추가되지 않은 마켓의 팩은 켤 수 없으니 MISSING 을 내지 않는다(모든 luau 저장소에 소음이 된다).
        installable = known is None or market in known
        if toolkit in active and not eff and proj.get(pack) is not False and installable:
            marks = "; ".join(active[toolkit][:2])
            add(7, "경고", "PACK-MISSING", proj_file,
                f"{toolkit} 툴킷 표식({marks})이 있는데 도메인 팩 {pack} 이 이 프로젝트에 켜져 있지 않다. "
                f'.claude/settings.json 의 "enabledPlugins" 에 `"{pack}@{market}": true` 를 더한다(사용자 승인 뒤).', REF)
        elif toolkit not in active and eff:
            where = "프로젝트" if proj.get(pack) else "사용자 레벨"
            add(7, "정보", "PACK-UNUSED", proj_file if proj.get(pack) else user_home / "settings.json",
                f"도메인 팩 {pack} 이 {where}에서 켜져 있는데 {toolkit} 툴킷 표식이 없다. 이 저장소에는 필요 없을 수 있다.", REF)
        if user.get(pack):
            add(7, "정보", "PACK-USER-LEVEL", user_home / "settings.json",
                f"도메인 팩 {pack} 이 사용자 레벨 enabledPlugins 에서 켜져 있다. 팩은 프로젝트별로 켠다"
                f"(정본 home/settings-migrations 로 걷어 내고 {toolkit} 저장소의 .claude/settings.json 에서 켠다).", REF)
