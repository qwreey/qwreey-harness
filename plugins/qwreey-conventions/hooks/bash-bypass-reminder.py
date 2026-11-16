#!/usr/bin/env python3
"""PreToolUse(Bash) 리마인더: 셸·인터프리터로 파일을 읽거나 바꾸면 하네스 장치를 우회한다는 것을 알린다.

막지 않는다(permissionDecision 없음). additionalContext 만 주입한다.
level: 쓰기 신호(sed -i, 코드 파일로의 리다이렉트, 쓰기 신호가 있는 인터프리터 스크립트)가 있으면 warn, 읽기만 하는 인터프리터 명령은 info.

왜: Read/Edit/Write 도구를 거치지 않으면
  - paths 조건부 .claude/rules 가 로드되지 않을 수 있다. 실측 결과 Bash `cat` 은 로드되지만
    grep 은 로드되지 않았다. 인터프리터는 보장이 없다.
  - Edit|Write 매처에 걸린 PostToolUse 훅(포맷터, 검사기)이 돌지 않는다.
  - 스킬은 description 이 맞을 때만 로드되므로, 스크립트로 일괄 수정할 때는 규약을 놓치기 쉽다.

readable-code(HARNESS_READABLE_CODE=on)가 켜져 있고 명령이 코드 파일을 바꿀 것 같으면(changed_files), 그 파일만
`scripts/conventions-scan.py layout <file>` 로 확인하라는 한 줄을 더한다(conventions-check 의 layout 알림은 Edit|Write 만 본다). 파일마다 한 번.

종류마다 세션당 한 번만 알린다. rules 파일 안내는 파일마다 세션당 한 번이다(프로젝트·사용자 rules 와 설치된 플러그인들의 rules/).
상태 파일 위치: $TMPDIR/claude-bypass-reminder/<session_id>.c<compact 회차>[.a<agent_id>].json (compact_epoch.py. compact 뒤 다시 알린다)
"""
import importlib.util
import json
import os
import re
import shlex
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import compact_epoch  # noqa: E402
import conv_env  # noqa: E402
import harness_nonce  # noqa: E402
import layout_metrics  # noqa: E402
import rules_inject  # noqa: E402

# 플러그인이 싣는 rules(이 플러그인과 web-security 등 설치된 모든 플러그인의 `rules/`): 공식 .claude/rules 가 아니라 rules_inject 훅이
# 파일을 열 때 주입한다. 셸로 파일을 바꾸면 주입도 비껴가므로 이름을 짚는다
PLUGIN_RULES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "rules")
LAYOUT_SCAN = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts", "conventions-scan.py")


def _read_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _read_toml(path):
    try:
        import tomllib
        with open(path, "rb") as f:
            return tomllib.load(f)
    except Exception:  # 없거나 깨진 설정은 없는 것으로 본다(fail-open)
        return {}


def _market_dir(markets, market, name):
    """마켓 정의가 가리키는 플러그인 폴더. installed_plugins.json 의 installPath 는 폴더 마켓에서도 옛 캐시를 가리킬 수 있어 먼저 본다."""
    loc = (markets.get(market) or {}).get("installLocation") if isinstance(markets.get(market), dict) else None
    if not isinstance(loc, str):
        return None
    for e in _read_json(os.path.join(loc, ".claude-plugin", "marketplace.json")).get("plugins") or []:
        if isinstance(e, dict) and e.get("name") == name and isinstance(e.get("source"), str):
            d = os.path.normpath(os.path.join(loc, e["source"]))
            return d if os.path.isdir(d) else None
    return None


def _listed_pack_dirs(proj):
    """{팩 rules 디렉터리: 팩 이름}. 팩 rule 은 프로젝트 coderag.toml 의 [[packs]] 에 있을 때만 coderag 가 넣으므로 그것만 알린다."""
    listed = [p for p in _read_toml(os.path.join(proj, "coderag.toml")).get("packs") or [] if isinstance(p, dict)]
    if not listed:
        return {}
    home = os.environ.get("CODERAG_HOME") or os.path.join(os.path.expanduser("~"), ".coderag")
    reg = {p.get("name"): p.get("path") for p in _read_toml(os.path.join(home, "coderag.toml")).get("packs") or [] if isinstance(p, dict)}
    out = {}
    for p in listed:
        path = p.get("path") or reg.get(p.get("name"))
        if isinstance(path, str) and isinstance(p.get("name"), str):
            out[os.path.join(path, "rules")] = p["name"]
    return out


def plugin_rule_dirs(proj=None):
    """{rules 디렉터리: 플러그인 이름}. 이 플러그인 것, 설치된 플러그인의 `rules/`(도메인 팩 제외), 이 프로젝트가 목록에 적은 팩의 `rules/`."""
    out = {PLUGIN_RULES: "qwreey-conventions"}
    cfg = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude")
    markets = _read_json(os.path.join(cfg, "plugins", "known_marketplaces.json"))
    for key, entries in (_read_json(os.path.join(cfg, "plugins", "installed_plugins.json")).get("plugins") or {}).items():
        name, _, market = key.partition("@")
        if name in out.values():  # 이 플러그인은 지금 도는 사본이 이긴다(설치된 옛 버전과 이중으로 나오지 않게)
            continue
        root = _market_dir(markets, market, name)
        if root is None:
            paths = [e.get("installPath") for e in entries if isinstance(e, dict)] if isinstance(entries, list) else []
            root = next((x for x in paths if isinstance(x, str)), None)
        if root is None or os.path.isfile(os.path.join(root, "coderag.toml")):
            continue  # 도메인 팩: 아래에서 프로젝트 목록으로만 더한다
        out[os.path.join(root, "rules")] = name
    if proj:
        out.update(_listed_pack_dirs(proj))
    return out


INTERP = {"python", "python3", "node", "deno", "bun", "perl", "ruby", "lua", "luau", "lune", "lute"}
PREFIX = {"(", "{", "time", "nice", "env", "command", "exec", "nohup", "sudo", "choom", "prlimit", "timeout", "--"}
INPLACE = re.compile(r"\bsed\s+(-\S*\s+)*-i|\bperl\s+(-\S*\s+)*-\S*p\S*i|\bawk\s+-i\s+inplace|\bpatch\b|\bgit\s+apply\b")
CODE_EXT = r"\.(luau|lua|py|ts|tsx|js|jsx|mjs|cjs|astro|vue|svelte|css|rs|go|json|toml|md|mdx|ya?ml|sh)"
# 셸 낱말 하나: 따옴표로 묶은 것(공백 포함)이나 공백, 따옴표, 연산자가 없는 덩어리
WORD = r"""'[^'\n]*'|"[^"\n]*"|[^\s;|&'"<>()]+"""
REDIRECT = re.compile(r"(?<![0-9&=-])>>?\s*(" + WORD + r")|\btee\s+(?:-a\s+)?(" + WORD + r")")
# 인터프리터 스크립트가 쓰기를 한다는 신호(qwreey-workspace 플러그인 scripts/wslib.py 의 SCRIPT_WRITE 와 같은 패턴. 서로 import 하지 않아 복사해 둔다).
# 읽기만 하는 python3 heredoc 이나 테스트 실행에 warn 을 내면 무겁다
SCRIPT_WRITE = re.compile(r"""['"][wa]\+?b?['"]|write|unlink|rmtree|rename|\.replace\(|copyfile|appendFile|\bmkdir""")
PATHLIKE = re.compile(r"[\w./@-]+" + CODE_EXT + r"\b")
CODE_FILE = re.compile(CODE_EXT + r"$", re.I)
QUOTED = re.compile(r"""'([^'\n]*)'|"([^"\n]*)\"""")


def dedup_path(namespace, session_id, agent_id=None):
    """State file keyed by (session_id, compact epoch): compact_epoch.py(이 플러그인 자기 회차)."""
    return compact_epoch.state_path("qwreey-conventions", namespace, session_id, agent_id)


def _unquote(word):
    return word[1:-1] if len(word) >= 2 and word[0] == word[-1] and word[0] in "'\"" else word


def redirect_targets(cmd):
    """`>`, `>>`, `tee` 가 쓰는 코드 파일 경로(따옴표를 벗긴 것)."""
    out = []
    for m in REDIRECT.finditer(cmd):
        target = _unquote(m.group(1) or m.group(2) or "")
        if CODE_FILE.search(target):
            out.append(target)
    return out


def cmd_paths(cmd):
    """명령에 든 코드 파일 경로. 따옴표로 묶은 것은 공백이 있어도 통째로 하나다."""
    paths = []
    for m in QUOTED.finditer(cmd):
        inner = m.group(1) if m.group(1) is not None else m.group(2)
        if CODE_FILE.search(inner) and " " in inner.strip():
            paths.append(inner)
    bare = QUOTED.sub(lambda m: m.group(0) if " " not in m.group(0).strip("'\"").strip() else " ", cmd)
    return set(paths) | {m.group(0) for m in PATHLIKE.finditer(bare)}


def heads(cmd):
    for seg in re.split(r"&&|\|\||[;|\n]", cmd):
        words = seg.replace("(", " ( ").split()
        i = 0
        while i < len(words) and (words[i] in PREFIX or re.fullmatch(r"[A-Za-z_]\w*=\S*", words[i])
                                  or words[i].startswith("-") or re.fullmatch(r"[\d.]+[smhd]?", words[i])):
            i += 1
        if i < len(words):
            w = words[i]
            if w == "mise" and words[i + 1:i + 2] == ["exec"]:
                rest = words[i + 2:]
                rest = rest[rest.index("--") + 1:] if "--" in rest else rest
                w = rest[0] if rest else w
            yield os.path.basename(w)


def load_rules(dirs):
    """[(rule 파일 경로, [정규식])]. glob 해석은 rules_inject 의 것을 쓴다(중괄호 등 공식 paths 문법을 둘이 따로 구현하지 않는다)."""
    rules = []
    for d in dirs:
        if not os.path.isdir(d):
            continue
        for root, _, files in os.walk(d):
            for f in sorted(files):
                if f.endswith(".md"):
                    r = rules_inject.parse_rule(os.path.join(root, f))
                    if r and rules_inject.switch_on(r[2]):  # 꺼진 rule 은 주입도 안 되므로 이름을 대지 않는다
                        rules.append((os.path.join(root, f), [rules_inject.glob_to_regex(g) for g in r[0]]))
    return rules


def describe(path, plugin_dirs, proj):
    for d, plugin in plugin_dirs.items():
        if path.startswith(d + os.sep):
            return "%s (%s rule: %s)" % (path[len(d) + 1:-3], plugin, path)
    return os.path.relpath(path, proj) if path.startswith(proj) else path.replace(os.path.expanduser("~"), "~")


def _abs(path, cwd):
    return os.path.normpath(path if os.path.isabs(path) else os.path.join(cwd, path))


def _inside(path, root):
    return path.startswith(os.path.normpath(root).rstrip("/") + "/")


def changed_files(cmd, cwd, proj, targets, abs_paths, interp_writes):
    """이 명령이 바꿀 것 같은 코드 파일(절대 경로). 저장소 밖으로의 리다이렉트(`git diff > /tmp/x`)는 넣지 않는다.

    리다이렉트와 tee 는 그 대상만, 제자리 편집(sed -i, patch)과 쓰는 인터프리터 스크립트는 어느 경로를 쓰는지 몰라
    명령에 든 경로를 다 넣되 리다이렉트로 저장소 밖에 쓰는 경로는 뺀다.
    """
    redirected = {_abs(t, cwd) for t in targets}
    out = {t for t in redirected if _inside(t, proj)}
    if INPLACE.search(cmd) or interp_writes:
        out |= {ap for ap in abs_paths if ap not in redirected or _inside(ap, proj)}
    return out


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0
    cmd = (data.get("tool_input") or {}).get("command") or ""
    sid = re.sub(r"[^\w-]", "", str(data.get("session_id") or "nosession"))
    cwd = data.get("cwd") or os.getcwd()
    proj = os.environ.get("CLAUDE_PROJECT_DIR") or cwd
    hs = list(heads(cmd))
    if hs and hs[0] in ("git", "gh") and not INPLACE.search(cmd):
        return 0

    state_path = dedup_path("claude-bypass-reminder", data.get("session_id"), data.get("agent_id"))
    try:
        seen = set(json.load(open(state_path)))
    except Exception:
        seen = set()

    notes = []
    levels = []  # info < warn < action; the tag carries the highest
    targets = redirect_targets(cmd)
    writes = bool(INPLACE.search(cmd) or targets)
    interp = any(h in INTERP for h in hs)
    interp_writes = interp and bool(SCRIPT_WRITE.search(cmd))
    risky = writes or interp_writes  # 쓰기 신호가 없으면 규칙 안내와 인터프리터 안내는 info

    if writes and "write" not in seen:
        seen.add("write")
        levels.append("warn")
        notes.append("This command changes files without the Edit/Write tools (sed -i, redirect, patch, ...), so "
                     "PostToolUse hooks on Edit|Write (formatters, checkers) do not run and path-scoped .claude/rules "
                     "and skill conventions for the file are not applied. If the file has such conventions, Read it after "
                     "the change to check it against them, and run the formatter/checker yourself.")
    elif interp and "interp" not in seen:
        seen.add("interp")
        levels.append("warn" if interp_writes else "info")
        notes.append("Reading or changing files through an interpreter (" + ", ".join(sorted(set(hs) & INTERP)) + ") bypasses the "
                     "Read/Edit/Write tools: path-scoped .claude/rules may not load and Edit|Write hooks do not run. "
                     "If you generate or bulk-edit source with a script, first check the relevant skills and rules "
                     "(naming, idioms). Scratch or generated output needs nothing.")

    if writes or interp:
        plugin_dirs = plugin_rule_dirs(proj)
        rules = load_rules([os.path.join(proj, ".claude", "rules"),
                            os.path.join(os.path.expanduser("~"), ".claude", "rules"),
                            *plugin_dirs])
        abs_paths = [_abs(p, cwd) for p in cmd_paths(cmd)]
        hit = [r for r, rxs in rules if r not in seen and any(rules_inject.rule_matches(rxs, ap, proj) for ap in abs_paths)]
        if hit:
            seen.update(hit)
            levels.append("warn" if risky else "info")
            rel = [describe(h, plugin_dirs, proj) for h in hit]
            notes.append("Rules that apply to files this command touches: " + ", ".join(rel) + ". If this command writes these files, read the rules first if you have not; read-only commands need nothing.")

        # Readable-code check for code files this command writes
        changed = changed_files(cmd, cwd, proj, targets, abs_paths, interp_writes)
        code = sorted(ap for ap in changed if os.path.splitext(ap)[1].lower() in layout_metrics.LANG_BY_EXT and "layout:" + ap not in seen)
        if code and conv_env.is_on("HARNESS_READABLE_CODE"):
            seen.update("layout:" + ap for ap in code)
            levels.append("warn")
            shown = " ".join(shlex.quote(os.path.relpath(ap, proj) if _inside(ap, proj) else ap) for ap in code[:4])
            notes.append("The readable-code layout notice does not see Bash edits: if this command changes functions, run "
                         f"`python3 -I {LAYOUT_SCAN} layout {shown}` afterwards and fix what it flags in the functions you changed.")

    if not notes:
        return 0
    try:
        json.dump(sorted(seen), open(state_path, "w"))
    except OSError:
        pass
    json.dump({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                      "additionalContext": f'<harness-hook name="bash-bypass-reminder" level="{"warn" if "warn" in levels else "info"}"{harness_nonce.attr(data.get("session_id"))}>\n' + " ".join(notes) + "\n</harness-hook>"}},
              sys.stdout, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
