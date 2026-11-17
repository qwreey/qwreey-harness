"""harness.env 읽기. 하네스 훅, 플러그인, /q:doctor, statusline 이 같이 쓴다(표준 라이브러리만).
@copy-of: home/.claude/lib/harness_env.py
정본은 claude-doctor 의 home/.claude/lib/harness_env.py(설치되면 ~/.claude/lib/harness_env.py)다. 플러그인은 늘 자기 옆의 바이트 같은
사본을 쓴다: 설치본은 home-sync apply 때만 바뀌어 플러그인보다 옛 판일 수 있고, 옛 판은 플러그인의 user_only 를 모른다.
설치본은 같은 home/ 에서 함께 설치되는 스크립트(statusline)만 읽는다. 사본은 정본만 고친 뒤 python3 -I tools/sync-copies.py --apply 로 맞춘다.

이 모듈은 방식(파일 형식, 층, 저장소 층 막기)과 여러 플러그인이 같이 읽는 키만 안다. 한 플러그인만 읽는 키의 기본값과
사용자 전용 여부는 그 플러그인이 읽는 곳 옆에 두고 load_layers(defaults=, user_only=) 로 넘긴다.
사용자가 키를 읽는 곳은 home/.claude/harness.env 의 주석이다.

파일 형식: 한 줄에 `KEY=VALUE`. `#` 로 시작하는 줄과 빈 줄은 무시한다.
- 값의 바깥 따옴표('…' 또는 "…")는 벗긴다. 줄 끝 주석은 따옴표 밖의 ` #` 부터다.
- `${NAME}` 과 `$NAME` 은 앞에서 정의한 키(아래 층 포함)나 환경 변수로 바꾼다. 맨 앞의 `~` 는 $HOME 이다.
- 셸로 source 하지 않는다(실행 없음). tools/home-sync.sh 도 같은 규칙으로 읽는다.

층(load_layers): 키마다 합치고 번호가 큰 층이 이긴다. 높은 층에 키가 있으면 빈 값이어도 그 값이다.
  1. DEFAULTS + 호출자 defaults(값의 `~` 와 `$NAME` 은 여기서 푼다)
  2. 사용자: $HARNESS_ENV, 없으면 호출자 후보, 없으면 <설정 디렉터리>/harness.env($CLAUDE_CONFIG_DIR 또는 ~/.claude)
  3. 플러그인 옵션: <설정 디렉터리>/settings.json 의 pluginConfigs["<플러그인>@<마켓>"].options (/config, /plugin configure 가 쓴다)
  4. 저장소 공유: <project>/.claude/harness.env (커밋한다)
  5. 저장소 개인: <project>/.claude/harness.local.env (커밋하지 않는다. 저장소 .gitignore 에 넣는다)
  6. 프로세스 환경 변수
4, 5 층은 USER_ONLY, RETIRED_USER_ONLY, LEGACY_USER_ONLY 와 호출자 user_only 의 키(실행 경로, 기기 고유값, 보안 게이트)를 바꾸지 못한다.
<project> 는 호출자가 주거나, 안 주면 $CLAUDE_PROJECT_DIR(project_dir() 은 그것이 없을 때 훅 stdin 의 cwd). 없으면 4, 5 층이 없다.
HARNESS_ENV 는 사용자 층 파일 하나만 바꾼다. 저장소 층은 그대로 위에 얹힌다.
load(candidates) 는 사용자 층 하나만 읽는 옛 호출용이다(플러그인 옵션 층도 없다).

플러그인 옵션 층(3):
- 플러그인 이름은 이 파일에서 위로 5단계 안에 처음 있는 .claude-plugin/plugin.json 의 name 이다. 못 찾으면(~/.claude/lib 설치본,
  statusline) 이 층이 없다. 같은 이름이 여러 마켓에 있으면 settings.json enabledPlugins 에서 true 인 것, 그래도 여럿이면 이름순 첫째.
- 그 plugin.json 의 userConfig 에 선언된 키만 읽는다(옵션을 지운 뒤 남은 값은 무시). 옵션 키는 환경 변수 이름의 소문자다
  (harness_reply_language 는 HARNESS_REPLY_LANGUAGE). userConfig 가 없으면 settings.json 을 열지 않는다.
- 값: true/false 는 on/off, 숫자는 문자열, 목록은 `;` 로 잇는다. `;` 로 나눈 조각마다 맨 앞 `~` 는 $HOME 이다(`$NAME` 은 풀지 않는다).
- 다른 플러그인의 옵션을 읽어야 하는 공용 모듈(known_repos)은 load_layers(options={이름: 키들}) 로 넘긴다. 이때는 넘긴 키가 선언이다.
- CLAUDE_PLUGIN_OPTION_* 환경 변수는 쓰지 않는다: Bash 로 부르는 스크립트에는 들어가지 않아 훅과 스크립트가 다른 값을 볼 수 있다.
- 관리 설정(managed settings)의 pluginConfigs 는 읽지 않는다(이 하네스가 대상으로 삼는 설치가 아니다).
- 비용(2026-11-17 실측, load_layers 한 번의 중앙값): 이 층이 없을 때 0.012 ms, userConfig 없는 플러그인은 plugin.json 읽기로 0.032 ms,
  userConfig 가 있으면 settings.json(4 KB) 해석을 더해 0.069 ms. json 을 아직 import 하지 않은 프로세스는 import 약 1 ms 를 더 낸다.
  같은 프로세스 안에서는 파일 mtime 과 크기가 같으면 해석한 값을 다시 쓴다.
"""
import os
import re
from pathlib import Path

# 여러 플러그인이 읽는 키만. 한 플러그인만 읽는 키는 그 플러그인이 정한다(tools/tests/test-harness-env-owners.py 가 겹침을 본다).
DEFAULTS = {
    # 툴체인 설치 경로(mise installs). shim 이 실패할 때 직접 부를 곳.
    "HARNESS_TOOL_INSTALLS": "~/.local/share/mise/installs",
    # 무거운 실행 래퍼(heavy_wrap). 키가 없으면 auto(choom 이 PATH 에 있으면 `choom -n 1000 --`), 빈 값이면 끔.
    "HARNESS_HEAVY_WRAP": "auto",
    # 켤 툴킷(공백 구분). 비면 전부. /q:doctor 는 이 목록 안에서 저장소마다 자동 감지한다.
    "HARNESS_TOOLKITS": "",
    # 위임(agy, codex) uid 표 위치(위임 드라이버, /q:doctor 의 uid 충돌 검사). 비면 저장소 안의 사본.
    "HARNESS_DELEGATE_REGISTRY": "",
}

_KEY = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)$")
_REF = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}|\$([A-Za-z_][A-Za-z0-9_]*)")


def _value(raw):
    raw = raw.strip()
    if raw[:1] in ("'", '"'):
        q = raw[0]
        end = raw.find(q, 1)
        return raw[1:end] if end > 0 else raw[1:]
    m = re.search(r"\s#", raw)
    return (raw[: m.start()] if m else raw).strip()


def expand(s, scope):
    s = _REF.sub(lambda m: scope.get(m.group(1) or m.group(2), os.environ.get(m.group(1) or m.group(2), "")), s)
    return os.path.expanduser(s) if s.startswith("~") else s


def parse(text, base=None):
    scope = dict(base or {})
    out = {}
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        m = _KEY.match(line)
        if not m:
            continue
        key = m.group(1)
        val = os.environ[key] if key in os.environ else expand(_value(m.group(2)), scope)  # 환경 변수가 이긴다
        scope[key] = out[key] = val
    return out


PROJECT_FILES = (".claude/harness.env", ".claude/harness.local.env")  # 저장소 층, 뒤가 이긴다
# 저장소 층이 바꾸지 못하는 키 가운데 여러 플러그인이 읽는 것: 실행할 프로그램과 경로, 기기 고유값. 클론한 저장소가 커밋해 둔
# 파일(harness.local.env 도 커밋될 수 있다)로 남의 하네스가 이것을 바꾸면 안 된다. 사용자 층과 환경 변수만 정한다.
# HARNESS_CODERAG 는 /q:doctor 가 읽고 qwreey-sessions:recall 이 모델에게 사용자 harness.env 에서 읽게 한다.
USER_ONLY = frozenset({
    "HARNESS_TOOL_INSTALLS", "HARNESS_HEAVY_WRAP", "HARNESS_DELEGATE_REGISTRY",
    "HARNESS_CODERAG",
})
# 기본값을 두지 않는 옛 위치 키. 플러그인은 이제 이 키 없이 돌지만 옛 설정에 남아 있고 읽는 곳(known_repos 의 옛 출처, 저자 도구)이 있다.
# 클론한 저장소가 이것으로 작업공간이나 정본 위치를 돌리면 안 되므로 저장소 층은 계속 막는다. 환경 변수는 지금처럼 이긴다.
RETIRED_USER_ONLY = frozenset({"HARNESS_WORKSPACE", "HARNESS_DOCTOR_ROOT"})
# 이 판보다 옛 플러그인은 installed() 로 이 설치본을 읽고 user_only 를 넘기지 않아, 예전 로더가 막던 키를 여기서 대신 막는다. 설치된 플러그인 가운데 이 판보다 옛것이 없으면 지운다.
LEGACY_USER_ONLY = frozenset({
    "HARNESS_AGENT_PUSH", "HARNESS_LUAU_KB", "HARNESS_ROBLOX_DOCS_CACHE", "HARNESS_WORKSPACE_GATE",
    "SESSION_LOG_HOME", "SESSION_LOG_CLAUDE",
    "HARNESS_DELEGATE_AGY_BIN", "HARNESS_DELEGATE_CODEX_BIN", "HARNESS_DELEGATE_AGY_HOME", "HARNESS_DELEGATE_CODEX_HOME",
    "HARNESS_DELEGATE_AGY_WORKTREE", "HARNESS_DELEGATE_AGY_UNISOLATED", "HARNESS_DELEGATE_CODEX_SANDBOX", "HARNESS_DELEGATE_KEEP_ENV", "HARNESS_DELEGATE_STATE",
    "HARNESS_DELEGATE_MAX_CONCURRENT", "HARNESS_DELEGATE_RUNS_DAYS",
})


def config_dir():
    return Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")


def project_dir(cwd=None):
    """저장소 층의 루트: $CLAUDE_PROJECT_DIR, 없으면 cwd(훅 stdin 의 cwd), 둘 다 없으면 None."""
    p = os.environ.get("CLAUDE_PROJECT_DIR") or cwd
    return Path(p) if p else None


def find_file(candidates):
    env = os.environ.get("HARNESS_ENV")
    for p in ([env] if env else []) + [str(c) for c in candidates]:
        if p and Path(p).is_file():
            return Path(p)
    return None


def _base(defaults):
    vals = {k: expand(v, {}) for k, v in {**DEFAULTS, **(defaults or {})}.items()}
    # 옛 위치 키는 DEFAULTS 를 떠났어도 환경 변수로 준 값은 지금처럼 결과에 있어야 한다(scan.py 등이 ENV.get 으로 읽는다).
    vals.update({k: os.environ[k] for k in (*vals, *RETIRED_USER_ONLY) if k in os.environ})
    return vals


_JSON = {}  # 경로 -> ((mtime_ns, size), 값). 한 프로세스가 load_layers 를 여러 번 불러도 파일을 한 번만 해석한다
_MANIFEST = {}  # 시작 디렉터리 -> (이름, {환경 변수 이름}) 또는 None


def _json_file(path):
    try:
        st = os.stat(path)
    except OSError:
        return None
    key = (st.st_mtime_ns, st.st_size)
    hit = _JSON.get(str(path))
    if hit and hit[0] == key:
        return hit[1]
    import json  # 여기서만 쓴다. userConfig 없는 플러그인의 훅은 settings.json 을 열지 않으므로 import 도 아낀다
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        data = None
    _JSON[str(path)] = (key, data)
    return data


def plugin_manifest(start=None):
    """(플러그인 이름, userConfig 에 선언된 키를 대문자로 바꾼 집합) 또는 None.
    start(기본: 이 파일)의 디렉터리부터 위로 5단계 안에서 처음 만나는 .claude-plugin/plugin.json 을 본다."""
    d = os.path.dirname(os.path.abspath(start or __file__))
    if d in _MANIFEST:
        return _MANIFEST[d]
    found, cur = None, d
    for _ in range(5):
        data = _json_file(os.path.join(cur, ".claude-plugin", "plugin.json"))
        if isinstance(data, dict) and isinstance(data.get("name"), str):
            uc = data.get("userConfig")
            found = (data["name"], frozenset(k.upper() for k in uc if isinstance(k, str)) if isinstance(uc, dict) else frozenset())
            break
        up = os.path.dirname(cur)
        if up == cur:
            break
        cur = up
    _MANIFEST[d] = found
    return found


def option_value(v):
    """settings.json 옵션 값 하나를 harness.env 꼴 문자열로. 쓸 수 없는 값(null, 객체)은 None."""
    if isinstance(v, bool):
        return "on" if v else "off"
    if isinstance(v, (int, float)):
        return str(int(v)) if isinstance(v, float) and v.is_integer() else str(v)
    if isinstance(v, list):
        parts = [option_value(x) for x in v]
        return ";".join(p for p in parts if p is not None)
    if isinstance(v, str):
        # 경로 여럿을 받는 옵션은 `;` 구분 문자열이다. 대화상자에 적은 ~ 를 조각마다 푼다.
        return ";".join(os.path.expanduser(p) if p.startswith("~") else p for p in v.split(";"))
    return None


def plugin_options(name, keys, cfg=None):
    """({환경 변수 이름: 값}, 읽은 플러그인 id 또는 ''): settings.json 의 pluginConfigs["<name>@<마켓>"].options 에서 keys 만."""
    if not keys:
        return {}, ""
    data = _json_file(Path(cfg or config_dir()) / "settings.json")
    pcs = data.get("pluginConfigs") if isinstance(data, dict) else None
    if not isinstance(pcs, dict):
        return {}, ""
    ids = [i for i in pcs if isinstance(i, str) and i.rpartition("@")[0] == name and isinstance(pcs[i], dict)]
    if not ids:
        return {}, ""
    enabled = data.get("enabledPlugins") if isinstance(data.get("enabledPlugins"), dict) else {}
    pid = min(ids, key=lambda i: (enabled.get(i) is not True, i))
    opts = pcs[pid].get("options")
    out = {}
    for key in keys if isinstance(opts, dict) else ():
        v = option_value(opts.get(key.lower()))
        if v is not None:
            out[key] = v
    return out, pid


def _options_layer(vals, extra=None):
    """플러그인 옵션 층을 vals 에 얹고 읽은 플러그인 id 들을 돌려준다. 자기 플러그인(plugin_manifest)이 extra 보다 나중이라 겹치면 이긴다."""
    own = plugin_manifest()
    want = [(n, frozenset(k)) for n, k in (extra or {}).items() if not (own and n == own[0])]
    if own and (own[1] or (extra or {}).get(own[0])):
        # 공용 모듈이 자기 플러그인 이름을 넘겼으면 선언된 키에 그 키를 더해 한 번만 읽는다.
        want.append((own[0], own[1] | frozenset((extra or {}).get(own[0]) or ())))
    ids = []
    for name, keys in want:
        got, pid = plugin_options(name, keys)
        if pid:
            ids.append(pid)
        vals.update({k: os.environ[k] if k in os.environ else v for k, v in got.items()})
    return ids


def _read(vals, f, skip=frozenset()):
    try:
        vals.update({k: v for k, v in parse(f.read_text(encoding="utf-8"), vals).items() if k not in skip})
        return True
    except (OSError, UnicodeDecodeError):
        return False


def load(candidates=(), defaults=None):
    """사용자 층만: {키: 값} 과 '_file' (읽은 파일 경로 또는 '')."""
    vals = _base(defaults)
    f = find_file(candidates)
    if f and not _read(vals, f):
        f = None
    vals["_file"] = str(f) if f else ""
    return vals


def layer_files(project=None, candidates=None):
    """(사용자 층 파일 또는 None, 저장소 층 파일들 낮은 층부터).
    project 가 None 이면 $CLAUDE_PROJECT_DIR, 빈 값이면 저장소 층이 없다. candidates 가 None 이면 <설정 디렉터리>/harness.env."""
    user = find_file(candidates if candidates is not None else [config_dir() / "harness.env"])
    if project is None:
        project = os.environ.get("CLAUDE_PROJECT_DIR") or ""
    repo = []
    for rel in PROJECT_FILES if project else ():
        p = Path(project) / rel
        # 저장소가 설정 디렉터리의 부모(~)이면 저장소 층이 사용자 파일과 같다. 두 번 읽지 않는다.
        if p.is_file() and not (user and p.resolve() == user.resolve()):
            repo.append(p)
    return user, repo


def load_layers(project=None, candidates=None, defaults=None, user_only=(), options=None):
    """모든 층을 합친 {키: 값}. '_file' 은 읽은 사용자 층 파일(또는 ''), '_files' 는 읽은 파일 전부(낮은 층부터, 공백 구분),
    '_options' 는 옵션을 읽은 플러그인 id(공백 구분, 없으면 '').
    defaults 는 호출자 키의 기본값, user_only 는 저장소 층이 바꾸지 못할 호출자 키(USER_ONLY 에 더해진다),
    options 는 자기 플러그인 말고 옵션을 더 읽을 플러그인 {이름: 환경 변수 이름들}."""
    vals = _base(defaults)
    user, repo = layer_files(project, candidates)
    user = user if user and _read(vals, user) else None
    ids = _options_layer(vals, options)
    skip = USER_ONLY | RETIRED_USER_ONLY | LEGACY_USER_ONLY | frozenset(user_only)
    read = ([user] if user else []) + [f for f in repo if _read(vals, f, skip)]
    vals["_file"] = str(user) if user else ""
    vals["_files"] = " ".join(str(f) for f in read)
    vals["_options"] = " ".join(ids)
    return vals


def heavy_wrap(vals):
    """무거운 실행 래퍼 argv 목록. 끔이거나 실행 파일이 없으면 []."""
    import shutil  # 여기서만 쓴다. 훅마다 모듈을 읽으므로 import 비용(수 ms)을 아낀다
    w = vals.get("HARNESS_HEAVY_WRAP", "auto").strip()
    if w == "auto":
        w = "choom -n 1000 --" if shutil.which("choom") else ""
    argv = w.split()
    return argv if argv and shutil.which(argv[0]) else []
