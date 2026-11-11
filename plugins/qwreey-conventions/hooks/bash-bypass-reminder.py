#!/usr/bin/env python3
"""PreToolUse(Bash) 리마인더: 셸·인터프리터로 파일을 읽거나 바꾸면 하네스 장치를 우회한다는 것을 알린다.

막지 않는다(permissionDecision 없음). additionalContext 만 주입한다.
level: 쓰기 신호(sed -i, 코드 파일로의 리다이렉트, 쓰기 신호가 있는 인터프리터 스크립트)가 있으면 warn, 읽기만 하는 인터프리터 명령은 info.

왜: Read/Edit/Write 도구를 거치지 않으면
  - paths 조건부 .claude/rules 가 로드되지 않을 수 있다. 실측 결과 Bash `cat` 은 로드되지만
    grep 은 로드되지 않았다. 인터프리터는 보장이 없다.
  - Edit|Write 매처에 걸린 PostToolUse 훅(포맷터, 검사기)이 돌지 않는다.
  - 스킬은 description 이 맞을 때만 로드되므로, 스크립트로 일괄 수정할 때는 규약을 놓치기 쉽다.

종류마다 세션당 한 번만 알린다. rules 파일 안내는 파일마다 세션당 한 번이다(프로젝트·사용자 rules 와 설치된 플러그인들의 rules/).
상태 파일 위치: $TMPDIR/claude-bypass-reminder/<session_id>.c<compact 회차>[.a<agent_id>].json (compact_epoch.py. compact 뒤 다시 알린다)
"""
import importlib.util
import json
import os
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import compact_epoch  # noqa: E402
import rules_inject  # noqa: E402

# 플러그인이 싣는 rules(이 플러그인과 web-security 등 설치된 모든 플러그인의 `rules/`): 공식 .claude/rules 가 아니라 rules_inject 훅이
# 파일을 열 때 주입한다. 셸로 파일을 바꾸면 주입도 비껴가므로 이름을 짚는다
PLUGIN_RULES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "rules")


def plugin_rule_dirs():
    """{rules 디렉터리: 플러그인 이름}. 이 플러그인 것과 installed_plugins.json 이 가리키는 설치 경로의 `rules/`."""
    out = {PLUGIN_RULES: "qwreey-conventions"}
    cfg = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude")
    try:
        with open(os.path.join(cfg, "plugins", "installed_plugins.json"), encoding="utf-8") as f:
            for key, entries in (json.load(f).get("plugins") or {}).items():
                for e in entries if isinstance(entries, list) else []:
                    if isinstance(e, dict) and isinstance(e.get("installPath"), str):
                        name = key.split("@")[0]
                        if name not in out.values():  # 이 플러그인은 지금 도는 사본이 이긴다(설치된 옛 버전과 이중으로 나오지 않게)
                            out[os.path.join(e["installPath"], "rules")] = name
    except (OSError, ValueError, AttributeError):
        pass
    return out
INTERP = {"python", "python3", "node", "deno", "bun", "perl", "ruby", "lua", "luau", "lune", "lute"}
PREFIX = {"(", "{", "time", "nice", "env", "command", "exec", "nohup", "sudo", "choom", "prlimit", "timeout", "--"}
INPLACE = re.compile(r"\bsed\s+(-\S*\s+)*-i|\bperl\s+(-\S*\s+)*-\S*p\S*i|\bawk\s+-i\s+inplace|\bpatch\b|\bgit\s+apply\b")
CODE_EXT = r"\.(luau|lua|py|ts|tsx|js|jsx|mjs|cjs|astro|vue|svelte|css|rs|go|json|toml|md|mdx|ya?ml|sh)"
REDIRECT = re.compile(r"(?<![0-9&])>>?\s*['\"]?([^\s;|&'\"]+" + CODE_EXT + r")\b|\btee\s+(-a\s+)?['\"]?([^\s;|&'\"]+" + CODE_EXT + r")")
# 인터프리터 스크립트가 쓰기를 한다는 신호(q 플러그인 scripts/wslib.py 의 SCRIPT_WRITE 와 같은 패턴. 서로 import 하지 않아 복사해 둔다).
# 읽기만 하는 python3 heredoc 이나 테스트 실행에 warn 을 내면 무겁다
SCRIPT_WRITE = re.compile(r"""['"][wa]\+?b?['"]|write|unlink|rmtree|rename|\.replace\(|copyfile|appendFile|\bmkdir""")
PATHLIKE = re.compile(r"[\w./@-]+" + CODE_EXT + r"\b")


def dedup_path(namespace, session_id, agent_id=None):
    """State file keyed by (session_id, compact epoch): compact_epoch.py(이 플러그인 자기 회차)."""
    return compact_epoch.state_path("qwreey-conventions", namespace, session_id, agent_id)


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
                    if r:
                        rules.append((os.path.join(root, f), [rules_inject.glob_to_regex(g) for g in r[0]]))
    return rules


def describe(path, plugin_dirs, proj):
    for d, plugin in plugin_dirs.items():
        if path.startswith(d + os.sep):
            return "%s (%s rule: %s)" % (path[len(d) + 1:-3], plugin, path)
    return os.path.relpath(path, proj) if path.startswith(proj) else path.replace(os.path.expanduser("~"), "~")


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
    writes = bool(INPLACE.search(cmd) or REDIRECT.search(cmd))
    interp = any(h in INTERP for h in hs)
    interp_writes = interp and bool(SCRIPT_WRITE.search(cmd))
    risky = writes or interp_writes  # 쓰기 신호가 없으면 규칙 안내와 인터프리터 안내는 info

    if writes and "write" not in seen:
        seen.add("write")
        levels.append("warn")
        notes.append("This command changes files without the Edit/Write tools (sed -i, redirect, patch, ...). "
                     "PostToolUse hooks on Edit|Write (formatters, checkers) do not run, and path-scoped .claude/rules "
                     "and skill conventions for the file are not applied. After the change, Read the file to check it "
                     "against the conventions, and run the formatter/checker yourself.")
    elif interp and "interp" not in seen:
        seen.add("interp")
        levels.append("warn" if interp_writes else "info")
        notes.append("Reading or changing files through an interpreter (" + ", ".join(sorted(set(hs) & INTERP)) + ") bypasses the "
                     "Read/Edit/Write tools: path-scoped .claude/rules may not load and Edit|Write hooks do not run. "
                     "If you generate or bulk-edit source with a script, first check the relevant skills and rules "
                     "(naming, idioms).")

    if writes or interp:
        plugin_dirs = plugin_rule_dirs()
        rules = load_rules([os.path.join(proj, ".claude", "rules"),
                            os.path.join(os.path.expanduser("~"), ".claude", "rules"),
                            *plugin_dirs])
        paths = {m.group(0) for m in PATHLIKE.finditer(cmd)}
        abs_paths = [os.path.normpath(p if os.path.isabs(p) else os.path.join(cwd, p)) for p in paths]
        hit = [r for r, rxs in rules if r not in seen and any(rules_inject.rule_matches(rxs, ap, proj) for ap in abs_paths)]
        if hit:
            seen.update(hit)
            levels.append("warn" if risky else "info")
            rel = [describe(h, plugin_dirs, proj) for h in hit]
            notes.append("Rules that apply to files this command touches: " + ", ".join(rel) + " - Read them first if you have not.")

    if not notes:
        return 0
    try:
        json.dump(sorted(seen), open(state_path, "w"))
    except OSError:
        pass
    json.dump({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                      "additionalContext": f'<harness-hook name="bash-bypass-reminder" level="{"warn" if "warn" in levels else "info"}">\n' + " ".join(notes) + "\n</harness-hook>"}},
              sys.stdout, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
