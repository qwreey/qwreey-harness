#!/usr/bin/env python3
"""PreToolUse(Bash) guard: `pgrep -f PAT` / `pkill -f PAT` whose pattern matches the calling shell itself.

Why: Claude Code runs a Bash command as `bash -c '... eval '<command>' ...'`, so the shell's argv holds the whole command
text. `pgrep -f` matches against full command lines, and pgrep skips only itself, not its parent shell; a pattern that
appears in the command therefore always finds that shell. A background `until ! pgrep -f X; do sleep 2; done` waited
for hours on its own shell, and `pkill -f X` can kill the shell running it.

Decision (no wrapper program needed, so it runs on every platform):
  - find pgrep/pkill in command position (segment head after loop keywords and prefixes, or inside `$(...)` / backticks)
    with -f/--full and a pattern; -v, -A/--ignore-ancestors and the like skip it.
  - self-match = the pattern, read as a regex (-i honoured, -x as a full match), matches the command text. That is
    what the shell's argv holds, so the bracket trick (`[t]est`) passes on its own unless the plain text also appears.
    `$VAR` in the pattern is filled from assignments in the same command; an unknown variable skips the check.
  - inside a while/until loop (condition or body) -> deny (action). Otherwise pkill -> warn, pgrep -> info.
Heredoc bodies are dropped first (data, not commands), and git/gh commands pass (messages quote such commands).
"""
import json
import os
import re
import shlex
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # python3 -I 는 스크립트 디렉터리를 path 에 넣지 않는다
from shell_segments import segments  # heavy-proc-guard.py 와 같이 쓴다

TAG = "self-match-guard"
EXEMPT_HEADS = {"git", "gh"}
# 명령 자리 앞에 올 수 있는 낱말: 셸 키워드와 다른 프로그램을 실행하는 접두
LEAD_WORDS = {"while", "until", "if", "elif", "then", "do", "else", "!", "{", "(", "time", "nice", "nohup", "exec",
              "command", "env", "sudo", "timeout"}
FINDER = re.compile(r"(?:(?<=\$\()|(?<=`)|(?<![^\s({!]))(?:[\w./-]*/)?(pgrep|pkill)(?=\s)")
# procps-ng pgrep/pkill 의 값을 받는 옵션
ARG_SHORT = set("dgGOpPstuUFrq")
ARG_LONG = {"--delimiter", "--pgroup", "--group", "--older", "--pid", "--parent", "--session", "--terminal", "--euid",
            "--uid", "--pidfile", "--runstates", "--cgroup", "--ns", "--nslist", "--env", "--signal", "--queue"}
SIGNAL_OPT = re.compile(r"-(?:\d+|(?:SIG)?[A-Z][A-Z0-9]+(?:[+-]\d+)?)")
STOP_CHARS = set("();<>|&")
# shell_segments 는 `&&` 까지만 나눈다. 배경 실행 `a & until ...` 의 `&` 도 나눠야 루프 머리를 본다(`2>&1`, `&>` 는 그대로)
BACKGROUND = re.compile(r"(?<![>&<])&(?![>&])")
ASSIGN = re.compile(r"(?:^|[;&|\s(])([A-Za-z_]\w*)=(\"[^\"]*\"|'[^']*'|[^\s;&|)]*)")
VAR_USE = re.compile(r"\$\{?([A-Za-z_]\w*)\}?")


def lead_ok(words):
    """True when every word before the program is a shell keyword, a prefix, an assignment or a prefix option."""
    for w in words:
        if w in LEAD_WORDS or w.startswith("-") or re.fullmatch(r"[\d.]+[smhd]?", w) or re.fullmatch(r"[A-Za-z_]\w*=\S*", w):
            continue
        return False
    return True


def tokens(rest, closer):
    """Arguments after pgrep/pkill up to the end of its simple command (unquoted `)`, `;`, `|`, `>` and so on)."""
    lex = shlex.shlex(rest, posix=True, punctuation_chars=True)
    lex.whitespace_split = True
    out = []
    while True:
        try:
            t = lex.get_token()
        except ValueError:  # 잘린 따옴표: "$(pgrep -f x)" 의 닫는 따옴표만 남은 경우
            break
        if t is None or t == "" or set(t) <= STOP_CHARS:
            break
        if closer and t.endswith(closer):
            out.append(t[:-1])
            break
        out.append(t)
    return out


def parse(tool, args):
    """(pattern, flags) when the call matches full command lines by pattern; None when it cannot self-match."""
    full = icase = exact = False
    pattern = None
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--":
            pattern = args[i + 1] if i + 1 < len(args) else None
            break
        if a.startswith("--"):
            name = a.split("=", 1)[0]
            if name == "--full":
                full = True
            elif name in ("--inverse", "--ignore-ancestors"):
                return None
            elif name == "--ignore-case":
                icase = True
            elif name == "--exact":
                exact = True
            elif name in ARG_LONG and "=" not in a:
                i += 1
        elif a.startswith("-") and len(a) > 1:
            if tool == "pkill" and len(a) > 2 and SIGNAL_OPT.fullmatch(a):
                i += 1
                continue
            for j, c in enumerate(a[1:]):
                if c == "f":
                    full = True
                elif c in "vA":
                    return None
                elif c == "i":
                    icase = True
                elif c == "x":
                    exact = True
                elif c in ARG_SHORT:
                    if j == len(a) - 2:
                        i += 1
                    break
        else:
            pattern = a
            break
        i += 1
    if not full or not pattern:
        return None
    return pattern, icase, exact


def resolve(pattern, cmd):
    """Fill `$VAR` from assignments in the command; None when a variable stays unknown."""
    values = {}
    for m in ASSIGN.finditer(cmd):
        v = m.group(2)
        values[m.group(1)] = v[1:-1] if v[:1] in "\"'" and len(v) > 1 else v
    missing = []

    def sub(m):
        if m.group(1) in values:
            return values[m.group(1)]
        missing.append(m.group(1))
        return m.group(0)

    out = VAR_USE.sub(sub, pattern)
    return None if missing else out


def self_matches(pattern, icase, exact, cmd):
    argv = "/bin/bash -c " + cmd
    try:
        rx = re.compile(pattern, re.I if icase else 0)
    except re.error:  # POSIX 클래스처럼 Python 이 못 읽는 ERE: 글자 그대로 들어 있는지로 짐작
        return pattern.lower() in argv.lower() if icase else pattern in argv
    return bool(rx.fullmatch(argv) if exact else rx.search(argv))


def find(cmd):
    """[(tool, pattern, in_wait_loop)] for every self-matching pgrep/pkill -f call."""
    hits, stack = [], []
    for seg in (part for _head, whole in segments(cmd) for part in BACKGROUND.split(whole)):
        words = seg.replace("(", " ( ").split()
        for w in words:
            w = w.rstrip(")")
            if w in ("while", "until"):
                stack.append("wait")
            elif w in ("for", "select"):
                stack.append("for")
                break
            elif w == "done":
                if stack:
                    stack.pop()
            elif w not in LEAD_WORDS:
                break
        in_loop = "wait" in stack
        for m in FINDER.finditer(seg):
            before = seg[:m.start()]
            closer = ")" if before.endswith("$(") else "`" if before.endswith("`") else None
            if not closer and not lead_ok(before.replace("(", " ( ").split()):
                continue
            rest = seg[m.end():]
            if closer == "`":  # 백틱 안의 패턴에는 백틱이 없다. 먼저 잘라야 바깥 따옴표가 토큰을 망치지 않는다
                rest = rest.split("`", 1)[0]
            got = parse(m.group(1), tokens(rest, closer))
            if not got:
                continue
            pattern = resolve(got[0], cmd)
            if pattern is None or not self_matches(pattern, got[1], got[2], cmd):
                continue
            hit = (m.group(1), got[0], in_loop)
            if hit not in hits:
                hits.append(hit)
    return hits


def bracket(pattern):
    if pattern[:1].isalnum():
        return "[%s]%s" % (pattern[0], pattern[1:])
    return "[t]est-delegate"


def short(pattern):
    return pattern if len(pattern) <= 60 else pattern[:57] + "..."


SHELL_NOTE = "Claude Code runs each Bash command through a shell whose argv holds the whole command line"


def alternatives(tool, pattern):
    return ("`%s -x <process name>` (matches the name, not the command line); the bracket trick `%s -f \"%s\"`, whose own text no "
            "longer matches (only while the plain text appears nowhere else in the command); or `%s -A -f` (procps-ng 4.0.3+, skips "
            "the calling shell)" % (tool, tool, bracket(pattern), tool))


def messages(hits):
    """{level: [text]} for the hits; deny when any call sits in a while/until loop."""
    loop = [h for h in hits if h[2]]
    if loop:
        tool, pattern, _ = loop[0]
        text = ("`%s -f \"%s\"` runs inside a while/until loop. %s, so the pattern matches that shell itself: the loop never ends%s. Re-run with %s. "
                "To wait for a job, run it with run_in_background and wait for its completion notification instead of polling."
                % (tool, short(pattern), SHELL_NOTE, " and pkill kills the shell running it" if tool == "pkill" else "",
                   alternatives(tool, pattern)))
        return {"deny": [text]}
    out = {}
    for tool, pattern, _ in hits:
        if tool == "pkill":
            out.setdefault("warn", []).append(
                "`pkill -f \"%s\"` also matches the shell running this command (%s), so it can kill that shell and cut the "
                "command short. If you mean another process, consider %s; if losing the rest of this command does not matter, "
                "nothing to do." % (short(pattern), SHELL_NOTE, alternatives(tool, pattern)))
        else:
            out.setdefault("info", []).append(
                "`pgrep -f \"%s\"` also matches the shell running this command (%s), so it finds at least that shell and "
                "succeeds. If the result or exit status matters, consider %s; otherwise nothing to do."
                % (short(pattern), SHELL_NOTE, alternatives(tool, pattern)))
    return out


def main():
    try:
        data = json.load(sys.stdin)
    except ValueError:
        return
    if not isinstance(data, dict):
        return
    cmd = (data.get("tool_input") or {}).get("command")
    if not isinstance(cmd, str) or ("pgrep" not in cmd and "pkill" not in cmd):
        return
    segs = list(segments(cmd))
    if segs and segs[0][0] in EXEMPT_HEADS:
        return
    hits = find(cmd)
    if not hits:
        return
    import harness_nonce
    nonce = harness_nonce.attr(data.get("session_id"))
    msgs = messages(hits)

    def tag(level, texts):
        return '<harness-hook name="%s" level="%s"%s>\n%s\n</harness-hook>' % (TAG, level, nonce, "\n".join(texts))

    if "deny" in msgs:
        out = {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": tag("action", msgs["deny"])}
    else:
        out = {"hookEventName": "PreToolUse",
               "additionalContext": "\n".join(tag(lv, msgs[lv]) for lv in ("warn", "info") if lv in msgs)}
    json.dump({"hookSpecificOutput": out}, sys.stdout)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
