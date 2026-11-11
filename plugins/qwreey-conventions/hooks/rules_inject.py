#!/usr/bin/env python3
"""플러그인이 싣는 rules(`rules/*.md`, paths 프론트매터)를 파일 경로가 맞을 때 additionalContext 로 주입한다.

왜: 플러그인은 `.claude/rules` 를 실을 수 없다. 공식 rules 는 Read 가 맞는 파일을 열 때 로드되므로, 같은 시점(PostToolUse)에
같은 본문을 훅이 넣는다. 실측(audit/34 R1-R4): Read 뒤 주입은 다음 Edit 에서 지켜지고 서브에이전트에서도 같다.

이벤트
  PostToolUse(Read|Edit|Write|MultiEdit|NotebookEdit): 맞는 rule 중 이 키로 아직 안 넣은 것을 넣는다.
  PreToolUse(Write|Edit|MultiEdit|NotebookEdit): 이 키로 아직 안 넣은 rule 이 맞으면 한 번 deny 하고 사유에 본문을 싣는다. 모델이 같은 호출을 다시 한다(R3).
    PreToolUse 의 additionalContext 는 도구가 실행된 뒤에야 모델에 닿으므로(audit/31) 그 편집을 막지 못한다. 그래서 allow+주입이 아니라 deny 다.
    Read 가 먼저 있었으면 PostToolUse 가 이미 마커를 만들어 deny 가 없다. deny 가 나는 경우: 새 파일 Write, 서브에이전트가 부모의 Read 만 믿고 Edit
    (Read 없이 가능함, 실측), compact 뒤 회차가 올라간 첫 편집.

dedup 키: (session, agent_id 또는 main, compact 회차, rule 이름). compact_epoch.state_path 가 앞 세 개를 정하고, rule 마다
  `<state>.<rule>` 마커를 O_CREAT|O_EXCL 로 만든다. 병렬 배치의 두 호출 중 하나만 마커를 얻어 이중 주입이 없다.
glob: 공식 paths 와 같게 `**`, `*`, `?`, `{a,b}`, `[..]`. 절대 경로에 맞춘다. 앞이 `**/` 이거나 `/` 로 시작하지 않는 패턴은 프로젝트 기준 상대
  경로(프로젝트 밖 파일은 절대 경로에서 앞 `/` 를 뗀 것)에 맞춘다.
끄기: HARNESS_CONVENTIONS_RULES=off (환경 변수 또는 harness.env). 저장소 `.claude/conventions.json` 의 `rules_exclude: ["comments", ...]` 로 rule 별 제외.
고칠 때 주의: 이 파일은 파일 열기마다 돈다. 표준 라이브러리만, 맞는 rule 이 없으면 바로 끝낸다.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
RULES_DIR = os.path.join(os.path.dirname(HERE), "rules")
PLUGIN = "qwreey-conventions"
NS = "claude-conventions-rules"
PATH_KEYS = ("file_path", "notebook_path")


def glob_to_regex(glob):
    """paths glob 을 정규식으로 바꾼다. `**/` 는 0개 이상의 디렉터리, `{a,b}` 는 선택, 중첩 가능."""
    out = []
    depth = 0
    i = 0
    n = len(glob)
    while i < n:
        c = glob[i]
        if c == "*":
            if glob[i:i + 3] == "**/":
                out.append("(?:.*/)?")
                i += 3
                continue
            if glob[i:i + 2] == "**":
                out.append(".*")
                i += 2
                continue
            out.append("[^/]*")
        elif c == "?":
            out.append("[^/]")
        elif c == "{":
            depth += 1
            out.append("(?:")
        elif c == "}" and depth:
            depth -= 1
            out.append(")")
        elif c == "," and depth:
            out.append("|")
        elif c == "[":
            j = glob.find("]", i + 2)
            if j < 0:
                out.append("\\[")
            else:
                body = glob[i + 1:j]
                if body.startswith("!"):
                    body = "^" + body[1:]
                out.append("[" + body.replace("\\", "\\\\") + "]")
                i = j
        else:
            out.append(re.escape(c))
        i += 1
    out.append(")" * depth)
    return re.compile("".join(out) + r"\Z")


def parse_rule(path):
    """(globs, body) 또는 None. 프론트매터의 paths 를 읽고 프론트매터를 뗀 본문을 돌려준다."""
    try:
        text = open(path, encoding="utf-8").read()
    except OSError:
        return None
    m = re.match(r"---\n(.*?)\n---\n?", text, re.S)
    if not m:
        return None
    fm = m.group(1)
    globs = []
    inline = re.search(r"^paths:\s*\[(.*)\]\s*$", fm, re.M)
    if inline:
        # 중괄호 안의 쉼표는 나누지 않는다
        buf, depth = "", 0
        for ch in inline.group(1):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
            if ch == "," and depth == 0:
                globs.append(buf)
                buf = ""
            else:
                buf += ch
        globs.append(buf)
    else:
        block = re.search(r"^paths:\s*\n((?:\s+-\s*.*\n?)+)", fm + "\n", re.M)
        if block:
            globs = re.findall(r"^\s+-\s*(.*)$", block.group(1), re.M)
    globs = [g.strip().strip("'\"") for g in globs if g.strip()]
    if not globs:
        return None
    return globs, text[m.end():].strip("\n")


_cache = {}


def load_rules():
    """[(이름, [정규식], 본문)]. 프로세스당 한 번."""
    if "rules" in _cache:
        return _cache["rules"]
    rules = []
    try:
        names = sorted(f for f in os.listdir(RULES_DIR) if f.endswith(".md"))
    except OSError:
        names = []
    for f in names:
        r = parse_rule(os.path.join(RULES_DIR, f))
        if r:
            rules.append((f[:-3], [glob_to_regex(g) for g in r[0]], r[1]))
    _cache["rules"] = rules
    return rules


def project_root(data):
    return os.environ.get("CLAUDE_PROJECT_DIR") or data.get("cwd") or os.getcwd()


def rule_matches(regexes, abs_path, root):
    p = os.path.normpath(abs_path)
    rel = os.path.relpath(p, root) if p.startswith(root.rstrip("/") + "/") else p.lstrip("/")
    return any(rx.match(p.lstrip("/")) or rx.match(rel) or rx.match(p) for rx in regexes)


def excluded(root):
    for name in ("conventions.json", "comments.json"):
        fp = os.path.join(root, ".claude", name)
        if os.path.exists(fp):
            try:
                with open(fp, encoding="utf-8") as f:
                    v = json.load(f).get("rules_exclude")
                return set(v) if isinstance(v, list) else set()
            except Exception:
                return set()
    return set()


def claim(base, name):
    """마커를 O_EXCL 로 만든다. 만들었으면 True(이 호출이 주입 담당), 이미 있으면 False."""
    try:
        fd = os.open("%s.%s" % (base, name), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)
        return True
    except FileExistsError:
        return False
    except OSError:
        return False  # 상태를 못 쓰면 주입하지 않는다(매 호출 반복 주입보다 낫다)


def wrap(name, body):
    return '<rule plugin="%s" name="%s">\n%s\n</rule>' % (PLUGIN, name, body)


def injection(files_label, picked):
    return ('<harness-hook name="rules-inject" level="info">\n'
            "Path-scoped rules from the %s plugin apply to %s (same as .claude/rules with paths). Follow them for this file.\n%s\n</harness-hook>"
            % (PLUGIN, files_label, "\n".join(wrap(n, b) for n, b in picked)))


def deny_reason(tool, files_label, picked):
    return ('<harness-hook name="rules-inject" level="action">\n'
            "This is not an error. Path-scoped rules apply to %s and had not been loaded yet, so this %s was held once. "
            "Retry the same %s call now with the rules applied. Do not mention this notice to the user.\n%s\n</harness-hook>"
            % (files_label, tool, tool, "\n".join(wrap(n, b) for n, b in picked)))


def main():
    try:
        raw = sys.stdin.read()
        if "file_path" not in raw and "notebook_path" not in raw:
            return 0
        data = json.loads(raw)
        import conv_env
        if conv_env.is_off("HARNESS_CONVENTIONS_RULES"):
            return 0
        ti = data.get("tool_input") or {}
        fp = next((ti[k] for k in PATH_KEYS if isinstance(ti.get(k), str) and ti.get(k)), None)
        if not fp:
            return 0
        root = project_root(data)
        abs_path = fp if os.path.isabs(fp) else os.path.join(data.get("cwd") or root, fp)
        skip = excluded(root)
        hits = [(n, b) for n, rx, b in load_rules() if n not in skip and rule_matches(rx, abs_path, root)]
        if not hits:
            return 0
        import compact_epoch
        base = compact_epoch.state_path(PLUGIN, NS, data.get("session_id"), data.get("agent_id"))
        picked = [(n, b) for n, b in hits if claim(base, n)]
        if not picked:
            return 0
        ev = data.get("hook_event_name")
        label = os.path.basename(abs_path)
        if ev == "PreToolUse":
            out = {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                          "permissionDecisionReason": deny_reason(data.get("tool_name") or "tool", label, picked)}}
        elif ev == "PostToolUse":
            out = {"hookSpecificOutput": {"hookEventName": ev, "additionalContext": injection(label, picked)}}
        else:
            return 0
        json.dump(out, sys.stdout, ensure_ascii=False)
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
