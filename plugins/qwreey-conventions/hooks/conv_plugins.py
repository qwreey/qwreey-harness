"""설치된 Claude Code 플러그인의 폴더 찾기. bash-bypass-reminder(다른 플러그인의 rules/)와 structure-reminder(luau-kb 팩의 분리 계획기)가 쓴다.

Claude Code 자신의 파일만 본다: <설정 디렉터리>/plugins/installed_plugins.json(설치된 플러그인과 installPath),
<설정 디렉터리>/plugins/known_marketplaces.json(마켓 위치). 이 플러그인을 클론한 위치나 작업공간 폴더는 보지 않는다.
읽기 실패는 "없음"으로 본다(훅은 세션을 막지 않는다). 표준 라이브러리만 쓴다.
"""
import json
import os


def config_dir():
    return os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude")


def read_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def market_dir(markets, market, name):
    """마켓 정의가 가리키는 플러그인 폴더. installed_plugins.json 의 installPath 는 폴더 마켓에서도 옛 캐시를 가리킬 수 있어 먼저 본다."""
    loc = (markets.get(market) or {}).get("installLocation") if isinstance(markets.get(market), dict) else None
    if not isinstance(loc, str):
        return None
    for e in read_json(os.path.join(loc, ".claude-plugin", "marketplace.json")).get("plugins") or []:
        if isinstance(e, dict) and e.get("name") == name and isinstance(e.get("source"), str):
            d = os.path.normpath(os.path.join(loc, e["source"]))
            return d if os.path.isdir(d) else None
    return None


def installed_roots(cfg=None):
    """[(이름, 마켓, 폴더)]: installed_plugins.json 순서. 폴더는 마켓 정의가 가리키는 곳, 없으면 첫 installPath, 둘 다 없으면 빠진다."""
    cfg = cfg or config_dir()
    markets = read_json(os.path.join(cfg, "plugins", "known_marketplaces.json"))
    markets = markets if isinstance(markets, dict) else {}
    plugins = read_json(os.path.join(cfg, "plugins", "installed_plugins.json"))
    plugins = plugins.get("plugins") if isinstance(plugins, dict) else None
    out = []
    for key, entries in (plugins if isinstance(plugins, dict) else {}).items():
        name, _, market = str(key).partition("@")
        root = market_dir(markets, market, name)
        if root is None:
            paths = [e.get("installPath") for e in entries if isinstance(e, dict)] if isinstance(entries, list) else []
            root = next((x for x in paths if isinstance(x, str) and os.path.isdir(x)), None)
        if root is not None:
            out.append((name, market, root))
    return out


def plugin_root(name, cfg=None):
    """설치된 플러그인 name 의 폴더. 여러 마켓에 있으면 마켓 이름순 첫째(실행마다 같은 답). 없으면 None."""
    hits = sorted((m, r) for n, m, r in installed_roots(cfg) if n == name)
    return hits[0][1] if hits else None
