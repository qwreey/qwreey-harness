#!/usr/bin/env python3
"""PreToolUse(Bash) 리마인더: 셸·인터프리터로 파일을 읽거나 바꾸면 하네스 장치를 우회한다는 것을 알린다.

막지 않는다(permissionDecision 없음). additionalContext 만 주입한다.

왜: Read/Edit/Write 도구를 거치지 않으면
  - paths 조건부 .claude/rules 가 로드되지 않을 수 있다. 실측 결과 Bash `cat` 은 로드되지만
    grep 은 로드되지 않았다. 인터프리터는 보장이 없다.
  - Edit|Write 매처에 걸린 PostToolUse 훅(포맷터, 검사기)이 돌지 않는다.
  - 스킬은 description 이 맞을 때만 로드되므로, 스크립트로 일괄 수정할 때는 규약을 놓치기 쉽다.

종류마다 세션당 한 번만 알린다. rules 파일 안내는 파일마다 세션당 한 번이다.
상태 파일 위치: $TMPDIR/claude-bypass-reminder/<session_id>.c<compact 회차>.json (lib/compact_epoch.py. compact 뒤 다시 알린다)
"""
import fnmatch
import importlib.util
import json
import os
import re
import sys
import tempfile
from pathlib import Path

INTERP = {"python", "python3", "node", "deno", "bun", "perl", "ruby", "lua", "luau", "lune", "lute"}
PREFIX = {"(", "{", "time", "nice", "env", "command", "exec", "nohup", "sudo", "choom", "prlimit", "timeout", "--"}
INPLACE = re.compile(r"\bsed\s+(-\S*\s+)*-i|\bperl\s+(-\S*\s+)*-\S*p\S*i|\bawk\s+-i\s+inplace|\bpatch\b|\bgit\s+apply\b")
CODE_EXT = r"\.(luau|lua|py|ts|tsx|js|jsx|mjs|cjs|astro|vue|svelte|css|rs|go|json|toml|md|mdx|ya?ml|sh)"
REDIRECT = re.compile(r"(?<![0-9&])>>?\s*['\"]?([^\s;|&'\"]+" + CODE_EXT + r")\b|\btee\s+(-a\s+)?['\"]?([^\s;|&'\"]+" + CODE_EXT + r")")
PATHLIKE = re.compile(r"[\w./@-]+" + CODE_EXT + r"\b")


def dedup_path(namespace, session_id):
    """State file keyed by (session_id, compact epoch) via lib/compact_epoch.py; falls back to session_id only."""
    try:
        spec = importlib.util.spec_from_file_location("compact_epoch", Path(__file__).resolve().parent.parent / "lib" / "compact_epoch.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.state_path(namespace, session_id)
    except Exception:
        d = os.path.join(tempfile.gettempdir(), namespace)
        os.makedirs(d, exist_ok=True)
        return os.path.join(d, re.sub(r"[^\w-]", "", str(session_id or "nosession")) + ".json")


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
    rules = []
    for d in dirs:
        if not os.path.isdir(d):
            continue
        for root, _, files in os.walk(d):
            for f in files:
                if not f.endswith(".md"):
                    continue
                p = os.path.join(root, f)
                try:
                    text = open(p, encoding="utf-8").read(4000)
                except OSError:
                    continue
                m = re.match(r"---\n(.*?)\n---", text, re.S)
                if not m:
                    continue
                globs = re.findall(r"^\s*-\s*['\"]?([^'\"\n]+)['\"]?\s*$", m.group(1), re.M)
                inline = re.search(r"^paths:\s*\[(.*)\]", m.group(1), re.M)
                if inline:
                    globs += [g.strip().strip("'\"") for g in inline.group(1).split(",")]
                if globs:
                    rules.append((p, globs))
    return rules


def matches(path, glob):
    path = path.lstrip("./")
    if fnmatch.fnmatch(path, glob):
        return True
    if glob.startswith("**/") and fnmatch.fnmatch(os.path.basename(path), glob[3:]):
        return True
    return fnmatch.fnmatch(path, glob.replace("**/", "*"))


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

    state_path = dedup_path("claude-bypass-reminder", data.get("session_id"))
    try:
        seen = set(json.load(open(state_path)))
    except Exception:
        seen = set()

    notes = []
    writes = bool(INPLACE.search(cmd) or REDIRECT.search(cmd))
    interp = any(h in INTERP for h in hs)

    if writes and "write" not in seen:
        seen.add("write")
        notes.append("This command changes files without the Edit/Write tools (sed -i, redirect, patch, ...). "
                     "PostToolUse hooks on Edit|Write (formatters, checkers) do not run, and path-scoped .claude/rules "
                     "and skill conventions for the file are not applied. After the change, Read the file to check it "
                     "against the conventions, and run the formatter/checker yourself.")
    elif interp and "interp" not in seen:
        seen.add("interp")
        notes.append("Reading or changing files through an interpreter (" + ", ".join(sorted(set(hs) & INTERP)) + ") bypasses the "
                     "Read/Edit/Write tools: path-scoped .claude/rules may not load and Edit|Write hooks do not run. "
                     "If you generate or bulk-edit source with a script, first check the relevant skills and rules "
                     "(naming, idioms).")

    if writes or interp:
        rules = load_rules([os.path.join(proj, ".claude", "rules"),
                            os.path.join(os.path.expanduser("~"), ".claude", "rules")])
        paths = {m.group(0) for m in PATHLIKE.finditer(cmd)}
        hit = [r for r, globs in rules if r not in seen and any(matches(p, g) for p in paths for g in globs)]
        if hit:
            seen.update(hit)
            rel = [os.path.relpath(h, proj) if h.startswith(proj) else h.replace(os.path.expanduser("~"), "~") for h in hit]
            notes.append("Rules that apply to files this command touches: " + ", ".join(rel) + " - Read them first if you have not.")

    if not notes:
        return 0
    try:
        json.dump(sorted(seen), open(state_path, "w"))
    except OSError:
        pass
    json.dump({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                      "additionalContext": '<harness-hook name="bash-bypass-reminder">\n' + " ".join(notes) + "\n</harness-hook>"}},
              sys.stdout, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
