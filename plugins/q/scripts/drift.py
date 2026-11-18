#!/usr/bin/env python3
"""설치 어긋남 고지: SessionStart 에서 사용자에게 한 줄(systemMessage)을 보인다. 모델에는 아무것도 주지 않는다.

두 가지를 본다.
1. 플러그인 어긋남(모든 저장소): 켜 둔 마켓 플러그인의 설치 버전이 마켓의 현재 plugin.json 버전보다 낮으면 이름·버전·
   `claude plugin update <name>@<market>` 을 보인다. 설치된 것은 installed_plugins.json, 켠 것은 settings 의 enabledPlugins,
   마켓 위치는 known_marketplaces.json 의 installLocation(directory·github·git 모두 로컬 사본이라 같은 방식으로 읽는다).
   읽기만 한다. 원격 마켓은 로컬 사본이 `marketplace update` 때만 새로워지므로 그 시점까지의 비교다.
2. home 어긋남(저장소 루트에 tools/home-sync.sh 가 있을 때만 = qwreey-harness): `home-sync.sh status`(실측 약 0.8초, 읽기 전용)를
   돌려 다른 파일·미적용 마이그레이션·고아가 있으면 한 줄.

같은 내용(해시)이면 하루에 한 번만 낸다(바뀌면 바로). 상태는 $TMPDIR/claude-q-drift/state.json. compact 로 다시 시작한 세션은 건너뛴다.
SessionStart 에서만 돈다(핫 경로 없음). 실패는 모두 삼킨다(fail-open). 끄기: q 옵션 harness_q_drift(/config), 또는 harness.env 나 환경 변수의 HARNESS_Q_DRIFT=off.
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time

DAY = 86400
STATUS_TIMEOUT = 6  # home-sync status 상한(초). SessionStart 훅 제한(10초)보다 짧게
DRIFT_DEFAULTS = {"HARNESS_Q_DRIFT": "on"}  # 끄기 스위치. q 옵션(/config) 이름은 harness_q_drift


def switched_off(project):
    """끄기 스위치: 환경 변수가 이기고, 없으면 harness.env 층(q 옵션 포함). 로더를 못 읽으면 켠 채로 둔다."""
    v = os.environ.get("HARNESS_Q_DRIFT")
    if v is None:
        try:
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # python3 -I 는 스크립트 디렉터리를 path 에 넣지 않는다
            import harness_env
            v = harness_env.load_layers(project, defaults=DRIFT_DEFAULTS).get("HARNESS_Q_DRIFT")
        except Exception:
            v = None
    return str(v or "").strip().lower() in ("off", "0", "no")


def cfg_dir():
    return os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude")


def read_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            v = json.load(f)
        return v if isinstance(v, dict) else {}
    except (OSError, ValueError):
        return {}


def ver_tuple(v):
    """'0.5.1' -> (0,5,1). 숫자 점 표기가 아니면 None(비교하지 않는다)."""
    if not isinstance(v, str) or not re.fullmatch(r"\d+(\.\d+)*", v.strip()):
        return None
    return tuple(int(x) for x in v.strip().split("."))


def enabled_plugins(project_dir):
    out = {}
    for p in (os.path.join(cfg_dir(), "settings.json"),
              os.path.join(project_dir, ".claude", "settings.json"),
              os.path.join(project_dir, ".claude", "settings.local.json")):
        ep = read_json(p).get("enabledPlugins")
        if isinstance(ep, dict):
            out.update({k: v for k, v in ep.items() if isinstance(k, str)})
    return [k for k, v in out.items() if v is True]


def market_version(install_loc, name):
    """마켓 사본에서 플러그인의 현재 버전. 상대 경로 source 만 읽는다(외부 source 는 None)."""
    mk = read_json(os.path.join(install_loc, ".claude-plugin", "marketplace.json"))
    for e in mk.get("plugins") or []:
        if not isinstance(e, dict) or e.get("name") != name:
            continue
        src = e.get("source")
        if isinstance(src, str) and src.startswith("."):
            v = read_json(os.path.join(install_loc, src, ".claude-plugin", "plugin.json")).get("version")
            if v:
                return v
        return e.get("version")
    return None


def plugin_drift(project_dir):
    """[(이름@마켓, 설치 버전, 마켓 버전)] 설치가 더 낮은 것만."""
    installed = read_json(os.path.join(cfg_dir(), "plugins", "installed_plugins.json")).get("plugins") or {}
    markets = read_json(os.path.join(cfg_dir(), "plugins", "known_marketplaces.json"))
    out = []
    for key in enabled_plugins(project_dir):
        name, _, market = key.partition("@")
        ents = installed.get(key)
        loc = (markets.get(market) or {}).get("installLocation") if market else None
        if not ents or not isinstance(ents, list) or not loc or not isinstance(ents[0], dict):
            continue
        have, want = ents[0].get("version"), market_version(loc, name)
        a, b = ver_tuple(have), ver_tuple(want)
        if a and b and a < b:
            out.append((key, have, want))
    return out


def plugin_line(items):
    if not items:
        return ""
    names = ", ".join(f"{k.split('@')[0]} {h} → {w}" for k, h, w in items)
    cmds = "; ".join(f"claude plugin update {k}" for k, _, _ in items)
    return f"플러그인 설치가 마켓보다 낮음: {names}. 갱신: {cmds}"


def find_home_sync(start):
    d = os.path.abspath(start)
    for _ in range(6):
        if os.path.isfile(os.path.join(d, "tools", "home-sync.sh")) and os.path.isfile(os.path.join(d, "home", "MANIFEST")):
            return d
        nd = os.path.dirname(d)
        if nd == d:
            break
        d = nd
    return None


DIFF_RX = re.compile(r"다름|실제에 없음|정본에 없음|링크 필요|링크 아닌|링크 대상 없음|정의 안 된")


def parse_status(text):
    """home-sync status 출력 -> (다른 파일 수, 미적용 마이그레이션 id 목록, 고아 수)."""
    files, migs, orphans, in_orphan = 0, [], 0, False
    for ln in text.splitlines():
        if ln.startswith("# "):
            in_orphan = "MANIFEST 에 없음" in ln or "끊어진 링크" in ln
            continue
        if not ln.strip():
            continue
        m = re.search(r"미적용:\s*(.+)$", ln)
        if ln.startswith("settings.json") and m:
            migs = [x.strip() for x in m.group(1).split(",") if x.strip()]
        elif ln.startswith("plugins:"):
            in_orphan = False  # 고아 절 뒤에 오는 플러그인 요약 줄
        elif in_orphan:
            if not ln.startswith(" ") and not ln.startswith("("):
                orphans += 1
        elif DIFF_RX.search(ln) and not ln.startswith("("):
            files += 1
    return files, migs, orphans


def home_line(root):
    p = subprocess.run(["bash", os.path.join(root, "tools", "home-sync.sh"), "status"], capture_output=True, text=True,
                       timeout=STATUS_TIMEOUT, stdin=subprocess.DEVNULL, cwd=root)
    if p.returncode != 0:
        return ""
    files, migs, orphans = parse_status(p.stdout)
    bits = []
    if files:
        bits.append(f"다른 파일 {files}개")
    if migs:
        bits.append(f"미적용 마이그레이션 {len(migs)}개")
    if orphans:
        bits.append(f"고아 {orphans}개")
    return f"~/.claude 가 정본(home/)과 어긋남: {', '.join(bits)}. 확인: tools/home-sync.sh status, 반영은 diff 를 본 뒤 apply" if bits else ""


def state_path():
    return os.path.join(tempfile.gettempdir(), "claude-q-drift", "state.json")


def due(state, key, text, now):
    """같은 문구면 하루에 한 번, 바뀌면 바로. 문구가 비면(어긋남 해소) 기록을 지워 다음 어긋남을 바로 알린다."""
    if not text:
        state.pop(key, None)
        return False
    h = hashlib.sha1(text.encode()).hexdigest()
    prev = state.get(key) or {}
    if prev.get("hash") == h and now - prev.get("t", 0) < DAY:
        return False
    state[key] = {"hash": h, "t": now}
    return True


def main():
    try:
        data = json.load(sys.stdin)
    except ValueError:
        return
    if not isinstance(data, dict) or data.get("agent_id") or data.get("source") == "compact":
        return
    project = os.environ.get("CLAUDE_PROJECT_DIR") or data.get("cwd") or os.getcwd()
    if switched_off(project):
        return
    lines = {}
    try:
        lines["plugin"] = plugin_line(plugin_drift(project))
    except Exception:
        pass
    root = find_home_sync(project)
    if root:
        try:
            lines["home"] = home_line(root)
        except Exception:
            pass
    sp, now = state_path(), time.time()
    state = read_json(sp)
    out = [t for k, t in lines.items() if due(state, k, t, now)]
    try:
        os.makedirs(os.path.dirname(sp), exist_ok=True)
        with open(sp + ".tmp", "w") as f:
            json.dump(state, f)
        os.replace(sp + ".tmp", sp)
    except OSError:
        pass
    if out:
        json.dump({"systemMessage": "\n".join(out)}, sys.stdout, ensure_ascii=False)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
