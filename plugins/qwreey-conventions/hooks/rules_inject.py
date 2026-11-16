#!/usr/bin/env python3
"""플러그인이 싣는 rules(`rules/*.md`, paths 프론트매터)를 파일 경로가 맞을 때 additionalContext 로 주입한다.
이 플러그인 자신의 rules 만 넣는다. 도메인 팩(packs/*)의 rules 는 coderag 플러그인의 `coderag hook post-tool` 이 넣고, 이 파일은 그
대조 기준이다(tools/tests/test-coderag-rules-parity.py 가 임시 팩 디렉터리에 복사해 같은 입력으로 비교한다). 플러그인 이름은 이 파일 위치의
`../.claude-plugin/plugin.json` 에서 읽으므로(없으면 상위 디렉터리 이름) 코드에 이름이 박혀 있지 않다.

왜: 플러그인은 `.claude/rules` 를 실을 수 없다. 공식 rules 는 Read 가 맞는 파일을 열 때 로드되므로, 같은 시점(PostToolUse)에
같은 본문을 훅이 넣는다. 실측(.claude/scopes/plugins/qwreey-conventions/audit/34 R1-R4): Read 뒤 주입은 다음 Edit 에서 지켜지고 서브에이전트에서도 같다.

이벤트: PostToolUse(Read|Edit|Write|MultiEdit|NotebookEdit)만. 맞는 rule 중 이 키로 아직 안 넣은 것을 넣는다.
  Read 뒤: 본문만. Edit·Write 뒤(이 키로 처음): 본문과 "방금 쓴 것을 rules 에 대조하고 어긋나면 Edit 로 고쳐라" 한 문장.
  PreToolUse deny 는 쓰지 않는다: 큰 새 파일 Write 를 통째로 다시 내게 하고 화면에 hook error 로 보이는 값이 더 컸다.

주입하지 않는 경로(비용): node_modules, .git, dist, build, .venv, vendor, __pycache__ 아래, 그리고 프로젝트(CLAUDE_PROJECT_DIR, 없으면 cwd) 밖을
  Read 하는 경우(형제 저장소는 읽기만 하는 일이라서). 예외는 설정 디렉터리의 `projects/*/memory/`. 프로젝트 밖이라도 편집은 주입한다.

dedup 키: (session, agent_id 또는 main, compact 회차, rule 이름). compact_epoch.state_path 가 앞 세 개를 정하고, rule 마다
  `<state>.<rule>` 마커를 O_CREAT|O_EXCL 로 만든다. 병렬 배치의 두 호출 중 하나만 마커를 얻어 이중 주입이 없다.
glob: 공식 paths 와 같게 `**`, `*`, `?`, `{a,b}`, `[..]`. 절대 경로에 맞춘다. 앞이 `**/` 이거나 `/` 로 시작하지 않는 패턴은 프로젝트 기준 상대
  경로(프로젝트 밖 파일은 절대 경로에서 앞 `/` 를 뗀 것)에 맞춘다.
끄기: HARNESS_CONVENTIONS_RULES=off (환경 변수 또는 harness.env). 저장소 `.claude/conventions.json` 의 `rules_exclude: ["comments", ...]` 로 rule 별 제외.
켜기 스위치: 프론트매터에 `switch: <KEY>` 가 있는 rule 은 harness.env 층(conv_env.env_value)에서 KEY 가 `on` 일 때만 넣는다. 개인 취향인 rule 을
  사용자가 자기 ~/.claude/harness.env 로 켜고 저장소가 .claude/harness.env 로 끌 수 있게 하려는 것이다. 마커를 잡기 전에 거르므로 세션 중간에
  켜도 다음 맞는 파일에서 실린다. `switch` 없는 rule 은 그대로다(팩 rule 은 `switch` 를 쓰지 않아 coderag 와의 대조가 같다).
저장소 설정 줄: comments rule 을 넣을 때 편집하는 파일의 저장소 설정에 comment_language 가 있으면 제목 아래에 그 값을 한 줄로 넣는다
  (setting_line). 이름이 `comments` 인 rule 에만 붙으므로 팩 rule 출력은 그대로다.
고칠 때 주의: 이 파일은 파일 열기마다 돈다. 표준 라이브러리만, 맞는 rule 이 없으면 바로 끝낸다.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
RULES_DIR = os.path.join(os.path.dirname(HERE), "rules")
PATH_KEYS = ("file_path", "notebook_path")
SKIP_DIRS = {"node_modules", ".git", "dist", "build", ".venv", "vendor", "__pycache__"}


def plugin_name():
    """plugin.json 의 name. 설치본은 상위 디렉터리가 버전이라 이름으로 못 쓰므로 먼저 파일을 본다."""
    root = os.path.dirname(HERE)
    try:
        with open(os.path.join(root, ".claude-plugin", "plugin.json"), encoding="utf-8") as f:
            name = json.load(f).get("name")
        if isinstance(name, str) and name:
            return name
    except (OSError, ValueError):
        pass
    return os.path.basename(root)


PLUGIN = plugin_name()
NS = "claude-%s-rules" % PLUGIN


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
    """(globs, body, switch) 또는 None. 프론트매터의 paths 와 switch(없으면 None)를 읽고 프론트매터를 뗀 본문을 돌려준다."""
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
    sw = re.search(r"^switch:\s*(\S+)\s*$", fm, re.M)
    return globs, text[m.end():].strip("\n"), (sw.group(1).strip("'\"") if sw else None)


def switch_on(key):
    """rule 의 switch 키가 켜졌나. 키가 없으면 늘 켜짐, 있으면 harness.env 층 값이 `on` 일 때만."""
    if not key:
        return True
    import conv_env
    return conv_env.is_on(key)


_cache = {}


def load_rules():
    """[(이름, [정규식], 본문, switch 키 또는 None)]. 프로세스당 한 번."""
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
            rules.append((f[:-3], [glob_to_regex(g) for g in r[0]], r[1], r[2]))
    _cache["rules"] = rules
    return rules


def project_root(data):
    return os.environ.get("CLAUDE_PROJECT_DIR") or data.get("cwd") or os.getcwd()


def rule_matches(regexes, abs_path, root):
    p = os.path.normpath(abs_path)
    rel = os.path.relpath(p, root) if p.startswith(root.rstrip("/") + "/") else p.lstrip("/")
    return any(rx.match(p.lstrip("/")) or rx.match(rel) or rx.match(p) for rx in regexes)


def repo_config(root):
    """저장소 `.claude/conventions.json`(없으면 예전 이름 comments.json)의 dict. 먼저 있는 파일 하나만 보고, 못 읽거나 dict 가 아니면 {}."""
    for name in ("conventions.json", "comments.json"):
        fp = os.path.join(root, ".claude", name)
        if os.path.exists(fp):
            try:
                with open(fp, encoding="utf-8") as f:
                    v = json.load(f)
                return v if isinstance(v, dict) else {}
            except Exception:
                return {}
    return {}


def excluded(root):
    v = repo_config(root).get("rules_exclude")
    return set(v) if isinstance(v, list) else set()


# 쓰는 글을 바꾸는 저장소 설정 값을 그 rule 본문에 한 줄로 넣는다. 스킬에만 두면 모델이 쓰기 전에 스킬을 열지 않아 지켜지지 않는다.
# 값은 모델에게 가는 태그 안에 들어가므로 언어 코드 꼴만 받는다(태그 흉내 글이 설정 파일에서 들어오지 않게).
LANG_CODE = re.compile(r"[A-Za-z]{2,3}(?:[-_][A-Za-z0-9]{2,8})?\Z")
SETTING_LINE = ("- This repo: comment_language = %s. Comments in a new file are written in it, whatever its sibling files use;"
                " an existing file keeps the language its comments already use.")


def setting_line(name, abs_path, data):
    """comments rule 에 붙일 저장소 설정 줄, 없으면 None. 설정은 conventions-check 가 comment_language 를 읽는 곳(편집하는 파일의 저장소)에서 읽는다."""
    if name != "comments":
        return None
    try:
        import conv_edit
        lang = repo_config(conv_edit.project_root(os.path.normpath(abs_path), data)).get("comment_language")
    except Exception:
        return None
    return SETTING_LINE % lang if isinstance(lang, str) and LANG_CODE.match(lang) else None


def with_setting(name, body, abs_path, data):
    """rule 본문의 제목 줄 바로 아래에 설정 줄을 넣는다. 설정이 없으면 본문 그대로."""
    line = setting_line(name, abs_path, data)
    if not line:
        return body
    head, sep, rest = body.partition("\n")
    return head + "\n" + line + sep + rest if head.startswith("#") else line + "\n" + body


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


def injection(files_label, picked, after_write, session_id=None):
    import harness_nonce
    text = "Rules for files matching these paths (shown once per context; you %s %s)." % ("wrote" if after_write else "opened", files_label)
    text += " Check what you wrote against them and fix only what conflicts.\n" if after_write else "\n"
    return ('<harness-hook name="rules-inject" level="info"%s>\n%s%s\n</harness-hook>'
            % (harness_nonce.attr(session_id), text, "\n".join(wrap(n, b) for n, b in picked)))


def skipped_dir(abs_path, root):
    """의존성·산출물 폴더 아래인가. 프로젝트 안이면 프로젝트 기준 상대 경로만 보아 상위 폴더 이름(예: /home/build)에 걸리지 않게 한다."""
    p = os.path.normpath(abs_path)
    r = root.rstrip("/") + "/"
    parts = p[len(r):].split("/") if p.startswith(r) else p.split("/")
    return any(x in SKIP_DIRS for x in parts[:-1])


def is_memory_path(abs_path):
    import conv_env
    base = os.path.join(os.path.normpath(conv_env.config_dir()), "projects") + "/"
    p = os.path.normpath(abs_path)
    if not p.startswith(base):
        return False
    parts = p[len(base):].split("/")
    return len(parts) >= 3 and parts[1] == "memory"


def should_skip(tool, abs_path, root):
    if skipped_dir(abs_path, root):
        return True
    if tool == "Read":
        inside = os.path.normpath(abs_path).startswith(root.rstrip("/") + "/")
        return not inside and not is_memory_path(abs_path)
    return False


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
        if should_skip(data.get("tool_name"), abs_path, root):
            return 0
        skip = excluded(root)
        hits = [(n, b) for n, rx, b, sw in load_rules() if n not in skip and rule_matches(rx, abs_path, root) and switch_on(sw)]
        if not hits:
            return 0
        import compact_epoch
        base = compact_epoch.state_path(PLUGIN, NS, data.get("session_id"), data.get("agent_id"))
        picked = [(n, b) for n, b in hits if claim(base, n)]
        if not picked:
            return 0
        if data.get("hook_event_name") != "PostToolUse":
            return 0
        picked = [(n, with_setting(n, b, abs_path, data)) for n, b in picked]
        label = os.path.basename(abs_path)
        out = {"hookSpecificOutput": {"hookEventName": "PostToolUse",
                                      "additionalContext": injection(label, picked, data.get("tool_name") != "Read", data.get("session_id"))}}
        json.dump(out, sys.stdout, ensure_ascii=False)
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
