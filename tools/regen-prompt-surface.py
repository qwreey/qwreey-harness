#!/usr/bin/env python3
"""모델이 보는 글(prompt surface) 스냅숏을 다시 만든다. 표준 라이브러리만 쓴다.

  python3 -I tools/regen-prompt-surface.py                  스냅숏(.txt)을 다시 쓰고 sizes.json 은 줄어든 항목만 낮춘다
  python3 -I tools/regen-prompt-surface.py --allow-growth   늘어난 항목과 새 항목도 sizes.json 에 올린다(커밋 메시지에 이유를 적는다)
  python3 -I tools/regen-prompt-surface.py --check          쓰지 않고 달라진 곳만 diff 로 보인다(달라졌으면 exit 1)

모은 글은 tools/tests/prompt-surface/<항목>.txt 하나씩, 크기(글자 수)는 sizes.json 에 둔다. 비교 테스트는 tools/tests/test-prompt-surface.py.
훅은 tools/tests/hook_sandbox.py 의 샌드박스에서 고정 salt 로 하위 프로세스로 돌린다. 기계마다 다른 경로와 오늘 날짜는 자리 표시로 바꾼다.

항목 이름(파일 이름 = 이름 + .txt)
  nonce-rule                         SessionStart, SubagentStart 에서 한 플러그인이 블록 맨 앞에 싣는 규칙 줄. 다른 블록에서는 빼고 따로 센다
                                     (어느 플러그인이 맡는지는 병렬 훅의 경합이라 고정되지 않는다)
  ambient.<플러그인>.<이벤트>          context/ambient.md, subagent.md 를 lib/ambient.py 사본이 싣는 꼴
  start.qwreey-sessions.<경우>        session-log 의 SessionStart(compact 닻, 대기 기록)
  skill.<플러그인>.<이름>              모델이 부를 수 있는 스킬의 목록 줄(disable-model-invocation 은 뺀다)
  agent.<플러그인>.<이름>              에이전트 정의의 목록 줄
  tool.qwreey-desk.desk              register.tsx 소스 글에서 꺼낸 도구 설명과 입력 스키마(모드를 돌리지 않는다)
  rule.<플러그인>.<이름>               rules_inject.py 가 맞는 파일을 Read 한 뒤 싣는 꼴(팩 rule 은 coderag 와 같은 출력인 참조 구현으로)
  notice.<훅>.<범주>                  훅 알림의 대표 하나씩
"""
import argparse
import difflib
import json
import os
import re
import shutil
import sys
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "tests"))
sys.path.insert(0, str(ROOT / "lib"))
import harness_nonce  # noqa: E402
from hook_sandbox import Sandbox, nonce as fixture_nonce  # noqa: E402

OUT = ROOT / "tools" / "tests" / "prompt-surface"
SIZES = OUT / "sizes.json"
REGEN = "python3 -I tools/regen-prompt-surface.py"
SID = "surface"
AMBIENTS = [("q", "plugins/q/scripts/ambient.py"), ("qwreey-advisor", "plugins/qwreey-advisor/hooks/ambient.py"),
            ("qwreey-operator", "plugins/qwreey-operator/hooks/ambient.py"), ("qwreey-workspace", "plugins/qwreey-workspace/scripts/ambient.py")]
AMBIENT_EVENTS = ("SessionStart", "SubagentStart", "PreCompact")
# 팩 rule 을 참조 구현으로 돌릴 때 임시 플러그인에 놓는 파일(tools/tests/test-coderag-rules-parity.py 와 같은 묶음)
RULES_INJECT_FILES = ("rules_inject.py", "conv_env.py", "harness_env.py", "compact_epoch.py", "harness_nonce.py")
CONV = "plugins/qwreey-conventions/hooks/"
HOOK_BUDGET = 9000  # 훅 출력 하나의 상한(글자). Claude Code 의 훅 출력 한도(1만 자) 아래로 여유를 둔 값
ZWSP = chr(0x200B)


# ---- 고정 텍스트 읽기 ----

def frontmatter(path):
    """SKILL.md, 에이전트 정의의 frontmatter 를 dict 로. YAML 중 이 저장소가 쓰는 꼴만 읽는다: 한 줄 값, 따옴표 값, >- > | 블록."""
    text = path.read_text(encoding="utf-8")
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    if not m:
        return {}
    lines = m.group(1).split("\n")
    out, i = {}, 0
    while i < len(lines):
        km = re.match(r"([A-Za-z][\w-]*):\s*(.*)$", lines[i])
        i += 1
        if not km:
            continue
        key, val = km.group(1), km.group(2).strip()
        if val in (">-", ">", "|", "|-"):
            block = []
            while i < len(lines) and (lines[i].startswith((" ", "\t")) or not lines[i].strip()):
                block.append(lines[i].strip())
                i += 1
            val = ("\n" if val.startswith("|") else " ").join(block).strip()
        elif val.startswith('"') and val.endswith('"'):
            val = json.loads(val)
        elif val.startswith("'") and val.endswith("'"):
            val = val[1:-1].replace("''", "'")
        out[key] = val
    return out


def plugin_name(root):
    try:
        return json.loads((root / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))["name"]
    except (OSError, ValueError, KeyError):
        return root.name


def plugin_roots():
    """[(종류 접두, 플러그인 루트)]. 팩은 기본으로 꺼져 있으므로 이름에 pack 을 붙여 세션 시작 합계에서 뺀다."""
    return [("", p) for p in sorted((ROOT / "plugins").iterdir()) if p.is_dir()] + \
           [("pack.", p) for p in sorted((ROOT / "packs").iterdir()) if p.is_dir()]


def listings():
    """스킬과 에이전트의 목록 줄. Claude Code 가 시스템 알림과 Agent 도구 설명에 싣는 꼴(`- <플러그인>:<이름>: <설명>`)."""
    items = {}
    for kind, root in plugin_roots():
        name = plugin_name(root)
        for skill in sorted(root.glob("skills/*/SKILL.md")):
            fm = frontmatter(skill)
            if str(fm.get("disable-model-invocation", "")).lower() == "true":
                continue
            items["skill.%s%s.%s" % (kind, name, fm.get("name", skill.parent.name))] = "- %s:%s: %s" % (name, fm.get("name", skill.parent.name), fm.get("description", ""))
        for agent in sorted(root.glob("agents/*.md")):
            fm = frontmatter(agent)
            tools = " (Tools: %s)" % fm["tools"] if fm.get("tools") else ""
            items["agent.%s%s.%s" % (kind, name, fm.get("name", agent.stem))] = "- %s:%s: %s%s" % (name, fm.get("name", agent.stem), fm.get("description", ""), tools)
    return items


# ---- qwreey-desk 도구 설명: TS 소스의 리터럴을 읽는다(모드 엔진 없이) ----

JS_TOKEN = re.compile(r"""\s*(?:(?P<str>'(?:[^'\\\n]|\\.)*'|"(?:[^"\\\n]|\\.)*")|(?P<punct>[{}\[\]:,])|(?P<word>[A-Za-z_$][\w$]*))""")


def js_tokens(src):
    pos, out = 0, []
    while pos < len(src):
        if not src[pos:].strip():
            break
        m = JS_TOKEN.match(src, pos)
        if not m:
            raise ValueError("register.tsx: unexpected text in literal near %r" % src[pos:pos + 40])
        pos = m.end()
        if m.group("str"):
            out.append(("str", js_string(m.group("str"))))
        elif m.group("punct"):
            out.append((m.group("punct"), None))
        else:
            out.append(("word", m.group("word")))
    return out


def js_string(lit):
    """작은따옴표, 큰따옴표 JS 문자열 리터럴의 값. 이 파일이 쓰는 escape(\\' \\" \\\\ \\n)만 푼다."""
    body = lit[1:-1]
    return re.sub(r"\\(.)", lambda m: {"n": "\n", "t": "\t"}.get(m.group(1), m.group(1)), body)


def js_value(toks, i):
    kind, val = toks[i]
    if kind == "str":
        return val, i + 1
    if kind == "word":
        return {"true": True, "false": False}.get(val, val), i + 1
    if kind == "[":
        arr, i = [], i + 1
        while toks[i][0] != "]":
            v, i = js_value(toks, i)
            arr.append(v)
            if toks[i][0] == ",":
                i += 1
        return arr, i + 1
    if kind == "{":
        obj, i = {}, i + 1
        while toks[i][0] != "}":
            key = toks[i][1]
            if toks[i + 1][0] != ":":
                raise ValueError("register.tsx: expected ':' after %r" % key)
            obj[key], i = js_value(toks, i + 2)
            if toks[i][0] == ",":
                i += 1
        return obj, i + 1
    raise ValueError("register.tsx: unexpected token %r" % (toks[i],))


def desk_tool():
    src = (ROOT / "plugins" / "qwreey-desk" / "hooks" / "register.tsx").read_text(encoding="utf-8")
    m = re.search(r"^const TOOL_DESCRIPTION = (\[.*?\])\.join\(' '\)$", src, re.S | re.M)
    s = re.search(r"^const TOOL_SCHEMA = (\{.*?^\})$", src, re.S | re.M)
    r = re.search(r"\$\.tool\.register\(\{ name: '([\w-]+)', description: TOOL_DESCRIPTION, inputSchema: TOOL_SCHEMA", src)
    if not (m and s and r):
        raise ValueError("register.tsx: TOOL_DESCRIPTION, TOOL_SCHEMA or $.tool.register(...) not found in the expected shape")
    desc = " ".join(js_value(js_tokens(m.group(1)), 0)[0])
    schema = js_value(js_tokens(s.group(1)), 0)[0]
    return "name: %s\ndescription: %s\ninput_schema: %s" % (r.group(1), desc, json.dumps(schema, ensure_ascii=False, separators=(",", ":")))


# ---- 훅 출력 ----

def ambient_items(sb):
    items = {}
    for plugin, script in AMBIENTS:
        for ev in AMBIENT_EVENTS:
            payload = {"session_id": SID, "hook_event_name": ev, "cwd": "{repo}", "source": "startup"}
            if ev == "SubagentStart":
                payload.update(agent_id="a1", agent_type="general-purpose")
            text = sb.run(script, payload, argv=[ev]).text()
            if text:
                items["ambient.%s.%s" % (plugin, ev)] = text
    return items


def example_path(glob):
    """paths glob 의 첫 패턴에 맞는 상대 경로 하나."""
    g = glob.replace("**/", "")
    g = re.sub(r"\{([^,}]*)[^}]*\}", r"\1", g)
    g = re.sub(r"\[(.)[^\]]*\]", r"\1", g)
    return g.replace("*", "x").replace("?", "x")


def rule_files(rules_dir):
    out = []
    for f in sorted(rules_dir.glob("*.md")):
        fm = re.match(r"---\n(.*?)\n---", f.read_text(encoding="utf-8"), re.S)
        if not fm:
            continue
        inline = re.search(r"^paths:\s*\[\s*(['\"])(.*?)\1", fm.group(1), re.M)
        block = re.search(r"^paths:\s*\n\s+-\s*(['\"]?)([^'\"\n]+)\1", fm.group(1), re.M)
        first = (inline or block).group(2).strip() if (inline or block) else None
        sw = re.search(r"^switch:\s*(\S+)", fm.group(1), re.M)
        if first:
            out.append((f.stem, example_path(first), sw.group(1) if sw else None))
    return out


def rules_for(sb, label, hook, rules_dir):
    """rule 하나씩: 다른 rule 은 저장소 rules_exclude 로 빼고, 맞는 파일을 Read 한 뒤의 주입을 받는다. 켜기 스위치는 켠다."""
    items = {}
    rules = rule_files(rules_dir)
    conf = sb.repo / ".claude" / "conventions.json"
    for name, rel, switch in rules:
        conf.write_text(json.dumps({"rules_exclude": [n for n, _, _ in rules if n != name]}), encoding="utf-8")
        target = sb.write(rel, "x\n")
        r = sb.run(hook, {"session_id": "%s-%s-%s" % (SID, label, name), "cwd": "{repo}", "hook_event_name": "PostToolUse",
                          "tool_name": "Read", "tool_input": {"file_path": str(target)}}, env={switch: "on"} if switch else None)
        if not r.text():
            raise RuntimeError("rule %s/%s: no injection for %s" % (label, name, rel))
        items["rule.%s.%s" % (label, name)] = r.text()
        target.unlink()
    conf.unlink()
    return items


def rule_items(sb):
    items = {}
    for kind, root in plugin_roots():
        rules_dir = root / "rules"
        if not rules_dir.is_dir():
            continue
        name = plugin_name(root)
        if kind == "":
            hook = root / "hooks" / "rules_inject.py"
            if not hook.exists():
                continue
        else:
            # 팩은 훅이 없다. coderag 가 싣는 꼴은 참조 구현과 같으므로(패리티 테스트) 팩 이름의 임시 플러그인에서 돌린다
            plug = sb.root / "packplug" / name
            (plug / ".claude-plugin").mkdir(parents=True)
            (plug / ".claude-plugin" / "plugin.json").write_text(json.dumps({"name": name}))
            (plug / "hooks").mkdir()
            for f in RULES_INJECT_FILES:
                shutil.copy2(ROOT / CONV / f, plug / "hooks" / f)
            (plug / "rules").symlink_to(rules_dir)
            hook = plug / "hooks" / "rules_inject.py"
        items.update(rules_for(sb, kind + name, str(hook), rules_dir))
    return items


def post_write(sb, script, rel, content, sid, env=None):
    p = sb.write(rel, content)
    return sb.run(script, {"session_id": sid, "cwd": "{repo}", "hook_event_name": "PostToolUse", "tool_name": "Write",
                           "tool_input": {"file_path": str(p), "content": content}, "tool_response": {"type": "create"}}, env=env)


def post_edit(sb, script, rel, whole, old, new, sid):
    p = sb.write(rel, whole)
    return sb.run(script, {"session_id": sid, "cwd": "{repo}", "hook_event_name": "PostToolUse", "tool_name": "Edit",
                           "tool_input": {"file_path": str(p), "old_string": old, "new_string": new}, "tool_response": {}})


def conventions_notices(sb):
    cc, rc = CONV + "conventions-check.py", CONV + "reuse-check.py"
    korean = "".join("-- 한국어 주석 줄 %d 입니다\nlocal v%d = %d\n" % (i, i, i) for i in range(12))
    sb.write("k/old.luau", korean)
    big = "local function big(a)\n" + "".join("  local v%d = a + %d\n" % (i, i) for i in range(30)) + "  return a\nend\nreturn big\n"
    n = {
        "history": post_write(sb, cc, "a/x.luau", "local a = 1\n-- H-973 changed 2026-11-10 in round 15\nlocal b = 2\n", "cc1"),
        "symbol": post_write(sb, cc, "a/y.py", "x = 1\n# first \u00b7 second \u2192 third\n", "cc2"),
        "escape": post_write(sb, cc, "a/z.ts", "const a = 1\n// use \\u00b7 here\n", "cc3"),
        "invisible": post_write(sb, cc, "a/w.ts", "const a = 1\n// zero" + ZWSP + "width\n", "cc4"),
        "language": post_write(sb, cc, "k/new.luau", "-- This comment is written in English words here\nlocal x = 1\n", "cc5"),
        "layout": post_write(sb, cc, "l/big.luau", big, "cc6", env={"HARNESS_READABLE_CODE": "on"}),
        "doc-history": post_write(sb, cc, "CLAUDE.md", "# Repo\n- Decided in round 3 (2026-11-10), see .claude/audit/12/summary.md\n", "cc7"),
        "doc-skill-description": post_write(sb, cc, "skills/foo/SKILL.md", "---\nname: foo\ndescription: 이 스킬은 무언가를 한다\n---\n# Foo\n", "cc8"),
    }
    items = {"notice.conventions-check.%s" % k: r.text() for k, r in n.items()}
    # 턴 끝 사용자 보고(systemMessage): 편집한 파일에 남은 옛 문제와 원본과 다른 사본
    old = "-- 2026-01-01 legacy (D-12)\nlocal a = 1\n"
    post_edit(sb, cc, "s/old.luau", old + "local b = 2\n", "local a = 1\n", "local a = 1\nlocal b = 2\n", "cc9")
    sb.write("a/src.luau", '-- source\nlocal FORMS = { "coin", "stick", "back", "card" }\nreturn FORMS\n')
    bad = '-- @copy-of: a/src.luau#FORMS\nlocal FORMS = { "coin", "stick", "back", "dice" }\n'
    items["notice.reuse-check.copy-differs"] = post_write(sb, rc, "b/copy.luau", bad, "cc9").text()
    items["notice.conventions-check.stop-report"] = sb.run(cc, {"session_id": "cc9", "cwd": "{repo}", "hook_event_name": "Stop",
                                                               "stop_hook_active": False}).text()
    sb.write("b/ok.luau", '-- @copy-of: a/src.luau#FORMS\nlocal FORMS = { "coin", "stick", "back", "card" }\n')
    items["notice.reuse-check.copies-listed"] = post_edit(
        sb, rc, "a/src.luau", '-- source\nlocal FORMS = { "coin", "stick", "back", "card", "gem" }\nreturn FORMS\n',
        '"card" }', '"card", "gem" }', "rc2").text()
    sb.write("h/a.luau", 'local KINDS = { "omega", "sigma", "kappa", "theta" }\nreturn KINDS\n')
    items["notice.reuse-check.repeated-set"] = post_write(sb, rc, "h/b.luau", 'local K2 = { "omega", "sigma", "kappa", "theta" }\nreturn K2\n',
                                                          "rc3", env={"REUSE_CHECK": "on"}).text()
    return items


def bash_notices(sb):
    bb, bw = CONV + "bash-bypass-reminder.py", CONV + "bash_writes.py"

    def pre(cmd, sid, tid):
        return sb.run(bb, {"session_id": sid, "cwd": "{repo}", "hook_event_name": "PreToolUse", "tool_name": "Bash",
                           "tool_input": {"command": cmd}, "tool_use_id": tid})
    items = {"notice.bash-bypass-reminder.read-info": pre("python3 -c \"print(open('src/a.py').read())\"", "bb1", "t1").text(),
             "notice.bash-bypass-reminder.write-warn": pre("sed -i 's/a/b/' src/a.py", "bb2", "t2").text()}
    sb.write("src/a.py", "def f():\n    # Keep the order stable for callers.\n    return 1\n")
    sb.sh("git add -A && git commit -qm init")
    cmd ="cat > src/new.py <<'EOF'\nx = 1\n# first \u00b7 second\nEOF"
    pre(cmd, "bb3", "t3")
    sb.sh(cmd)
    items["notice.bash-writes.heredoc"] = sb.run(bw, {"session_id": "bb3", "cwd": "{repo}", "hook_event_name": "PostToolUse",
                                                     "tool_name": "Bash", "tool_input": {"command": cmd}, "tool_use_id": "t3"}).text()
    return items


def guard_notices(sb):
    gate = "plugins/qwreey-workspace/scripts/workspace_gate.py"
    ws = {"HARNESS_WORKSPACE": "{ws}"}
    smg = "plugins/qwreey-proc-guard/hooks/self-match-guard.py"

    def pre_gate(tool, ti, sid):
        return sb.run(gate, {"session_id": sid, "cwd": "{repo}", "hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": ti},
                      argv=["PreToolUse"], env=ws).text()

    def pre_bash(script, cmd, sid):
        return sb.run(script, {"session_id": sid, "cwd": "{repo}", "hook_event_name": "PreToolUse", "tool_name": "Bash",
                               "tool_input": {"command": cmd}}).text()
    sb.write("{ws}/other/src/engine.py", "x = 1\n")
    return {
        "notice.workspace-gate.write-deny": pre_gate("Edit", {"file_path": "{ws}/other/a.txt"}, "wg1"),
        "notice.workspace-gate.read-info": pre_gate("Read", {"file_path": "{ws}/other/CLAUDE.md"}, "wg2"),
        "notice.sibling-internals.record-path": post_write(sb, "plugins/qwreey-workspace/scripts/sibling_notice.py", ".claude/research/a.md",
                                                           "The loop lives in `../other/src/engine.py`.\n", "si1", env=ws).text(),
        "notice.self-match-guard.loop-deny": pre_bash(smg, 'until ! pgrep -f "test-x.py" >/dev/null; do sleep 2; done', "sm1"),
        "notice.self-match-guard.notice": pre_bash(smg, 'pgrep -f "test-x.py"; echo done', "sm2"),
    }


def task_notices(sb):
    items = {}
    bg = "plugins/qwreey-operator/hooks/subagent-bg-tasks.py"
    tp = sb.write("{sandbox}/agent-a1.jsonl", [{"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "t0", "content":
                  "Command running in background with ID: b7x9k2. Output is being written to: /tmp/x/b7x9k2.output."}]}}])
    tasks = [{"id": "b7x9k2", "type": "shell", "status": "running", "description": "sleep 600"},
             {"id": "bmain1", "type": "shell", "status": "running", "description": "main's watcher"}]
    items["notice.subagent-bg-tasks.own-task"] = sb.run(bg, {
        "session_id": "bg1", "agent_id": "a1", "cwd": "{repo}", "hook_event_name": "SubagentStop", "last_assistant_message": "Done.",
        "stop_hook_active": False, "background_tasks": tasks, "agent_transcript_path": str(tp)}).text()
    stale = "plugins/q/scripts/stale_work.py"
    for cat, sid, task, env in (
            ("stalled", "st1", {"id": "b1", "type": "shell", "status": "running", "description": "Wait for tests"},
             {"HARNESS_Q_STALE_IDLE_MIN": "5", "HARNESS_Q_STALE_AGE_MIN": "0", "HARNESS_Q_STALE_LONG_MIN": "999"}),
            ("long-running", "st2", {"id": "b2", "type": "workflow", "status": "running", "description": "Long flow"},
             {"HARNESS_Q_STALE_IDLE_MIN": "999", "HARNESS_Q_STALE_AGE_MIN": "999", "HARNESS_Q_STALE_LONG_MIN": "0"})):
        tpath = sb.write("{sandbox}/projects/-fake/%s.jsonl" % sid, "")
        sb.write("{tmp}/claude-%d/-fake/%s/tasks/%s.output" % (os.getuid(), sid, task["id"]), "", mtime_ago=3600)
        user = sb.run(stale, {"hook_event_name": "Stop", "session_id": sid, "transcript_path": str(tpath), "background_tasks": [task]}, env=env)
        model = sb.run(stale, {"hook_event_name": "UserPromptSubmit", "session_id": sid, "prompt": "hi"}, env=env)
        items["notice.stale-work.%s" % cat] = model.text() + "\n--- systemMessage (Stop) ---\n" + user.text()
    return items


def human(text, uuid, ts):
    return {"type": "user", "origin": {"kind": "human"}, "promptSource": "typed", "uuid": uuid, "timestamp": ts, "cwd": "{repo}",
            "message": {"role": "user", "content": text}}


def assistant(text, tools=()):
    return {"type": "assistant", "timestamp": "2026-11-10T01:01:00Z", "message": {"role": "assistant", "content": [{"type": "text", "text": text}] + list(tools)}}


def session_notices(sb):
    hook = "plugins/qwreey-sessions/scripts/hook.py"
    rr = "plugins/qwreey-sessions/scripts/records_read.py"
    items = {}
    # 큰 기록 통째 Read: coderag 가 PATH 에 있을 때의 안내까지 보이도록 가짜 coderag 를 둔다
    bindir = sb.root / "bin"
    bindir.mkdir()
    (bindir / "coderag").write_text("#!/bin/sh\n")
    (bindir / "coderag").chmod(0o755)
    sb.write(".claude/audit/01-x/summary.md", {"repeat": "y", "times": 40 * 1024})
    items["notice.records-read.gate-deny"] = sb.run(rr, {"session_id": "rr1", "cwd": "{repo}", "hook_event_name": "PreToolUse", "tool_name": "Read",
                                                        "tool_input": {"file_path": "{repo}/.claude/audit/01-x/summary.md"}}, argv=["PreToolUse"],
                                                    env={"PATH": "%s:/usr/bin:/bin" % bindir}).text()
    sb.write("{store}/k/records/r.md", "x")
    items["notice.records-read.snapshot-read"] = sb.run(rr, {"session_id": "rr2", "cwd": "{repo}", "hook_event_name": "PostToolUse", "tool_name": "Read",
                                                            "tool_input": {"file_path": "{store}/k/records/r.md"}}, argv=["PostToolUse"]).text()
    tp = sb.write("{sandbox}/sess-1.jsonl", [
        human("값을 4242 로 해 줘. plugins/q/README.md 도 고쳐", "u1", "2026-11-10T01:00:00Z"),
        assistant("알겠다", [{"type": "tool_use", "id": "t1", "name": "Edit", "input": {"file_path": "{repo}/src/a.py", "old_string": "a", "new_string": "b"}}]),
        {"type": "user", "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t1", "content": "ok"}]}},
        human("D-12 결정대로 가자. 테스트도 돌려", "u2", "2026-11-10T01:05:00Z"),
        assistant("done"),
    ])
    base = {"session_id": "sess-1", "transcript_path": str(tp), "cwd": "{repo}"}
    items["start.qwreey-sessions.compact-anchors"] = sb.run(hook, dict(base, hook_event_name="SessionStart", source="compact"), argv=["SessionStart"]).text()
    # PreCompact 는 요약 워커를 떼어 내 띄우므로(같은 저장소를 쓴다) 기록을 만들고 읽는 일이 다 끝난 뒤 맨 끝에 부른다
    # 대기 기록: 테스트용 가짜 claude 로 요약을 하나 만든다(모델 호출 없음)
    fake = str(ROOT / "plugins" / "qwreey-sessions" / "tests" / "fixtures" / "fake_claude.py")
    r = sb.run("plugins/qwreey-sessions/scripts/cli.py", "", argv=["flush", "--session", "sess-1", "--transcript", str(tp), "--force", "--wait"],
               env={"SESSION_LOG_CLAUDE": fake, "SESSION_LOG_MIN_CHARS": "10", "SESSION_LOG_FORCE_MIN_CHARS": "10"})
    if r.rc != 0:
        raise RuntimeError("session-log flush failed: %s" % r.stderr)
    tp2 = sb.write("{sandbox}/sess-2.jsonl", [human("hello", "v1", "2026-11-10T02:00:00Z"), assistant("hi")])
    b2 = {"session_id": "sess-2", "transcript_path": str(tp2), "cwd": "{repo}"}
    items["start.qwreey-sessions.pending"] = sb.run(hook, dict(b2, hook_event_name="SessionStart", source="startup"), argv=["SessionStart"],
                                                    env={"SESSION_LOG_HANDOVER_LIVE_MIN": "0"}).text()
    items["notice.session-log.commit"] = sb.run(hook, dict(b2, hook_event_name="PreToolUse", tool_name="Bash", tool_input={"command": "git commit -m x"}),
                                                argv=["PreToolUse"]).text()
    tp3 = sb.write("{sandbox}/sess-3.jsonl", [human("값을 4242 로 해 줘. plugins/q/README.md 도 고쳐", "w1", "2026-11-10T03:00:00Z"),
                                               assistant("ok"), human("D-12 결정대로 가자. 테스트도 돌려", "w2", "2026-11-10T03:05:00Z")])
    items["notice.session-log.precompact"] = sb.run(hook, {"session_id": "sess-3", "transcript_path": str(tp3), "cwd": "{repo}",
                                                           "hook_event_name": "PreCompact", "trigger": "manual", "custom_instructions": ""},
                                                    argv=["PreCompact"]).text()
    return items


# ---- 모으기, 크기 ----

def collect():
    """{항목 이름: 글}. 글은 정규화했고 nonce 규칙 줄은 nonce-rule 항목으로만 남긴다."""
    items = {}
    with Sandbox(prefix="prompt-surface-") as sb:
        items.update(ambient_items(sb))
        items.update(rule_items(sb))
        items.update(conventions_notices(sb))
        items.update(bash_notices(sb))
        items.update(guard_notices(sb))
        items.update(task_notices(sb))
        items.update(session_notices(sb))
        rule_seen = []

        def clean(text):
            rule_seen.extend(harness_nonce.RULE_RE.findall(text))
            text = harness_nonce.RULE_RE.sub("", text)
            text = sb.normalize(text)
            key = re.sub(r"[^A-Za-z0-9]", "-", str(sb.root))
            text = text.replace(key, "<sandbox-key>").replace(date.today().isoformat(), "<today>")
            # 세션 기록은 UTC 날짜를 적는다. 한국 시각 09:00 전에는 지역 날짜와 하루 어긋나므로 UTC 날짜도 같은 자리표시로 바꾼다.
            return text.replace(datetime.now(timezone.utc).date().isoformat(), "<today>")
        items = {k: clean(v) for k, v in items.items()}
        if not rule_seen:
            raise RuntimeError("no hook emitted the nonce rule line")
        items["nonce-rule"] = harness_nonce.RULE.format(nonce=fixture_nonce(SID))
    items.update(listings())
    items["tool.qwreey-desk.desk"] = desk_tool()
    empty = sorted(k for k, v in items.items() if not v.strip())
    if empty:
        raise RuntimeError("hook emitted nothing for: %s" % ", ".join(empty))
    return dict(sorted(items.items()))


def is_hook_output(name):
    return name.split(".")[0] in ("ambient", "start", "rule", "notice")


def totals(sizes):
    """세션 시작에 늘 실리는 것(메인), 서브에이전트 시작에 훅이 싣는 것, 켠 팩이 더하는 것."""
    def s(pred):
        return sum(v for k, v in sizes.items() if pred(k))
    hooks = s(lambda k: k == "nonce-rule" or (k.startswith("ambient.") and k.endswith(".SessionStart")))
    lists = s(lambda k: k.startswith(("skill.", "agent.", "tool.")) and ".pack." not in "." + k)
    return {
        "session_start": hooks + lists,
        "session_start_hooks": hooks,
        "session_start_listings": lists,
        "subagent_start_hooks": s(lambda k: k == "nonce-rule" or (k.startswith("ambient.") and k.endswith(".SubagentStart"))),
        "packs_listings": s(lambda k: k.startswith(("skill.pack.", "agent.pack."))),
    }


def load_sizes():
    try:
        return json.loads(SIZES.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"items": {}, "totals": {}}


def snapshot_files():
    return {p.stem: p.read_text(encoding="utf-8") for p in sorted(OUT.glob("*.txt"))}


def diff(old, new):
    """[줄] unified diff. 없어진 항목과 새 항목도 함께."""
    out = []
    for name in sorted(set(old) | set(new)):
        a, b = old.get(name), new.get(name)
        if a == b:
            continue
        out.extend(difflib.unified_diff((a or "").splitlines(), (b or "").splitlines(),
                                        "a/%s.txt" % name if a is not None else "/dev/null",
                                        "b/%s.txt" % name if b is not None else "/dev/null", lineterm="", n=1))
    return out


def merged_sizes(items, old, allow_growth):
    """새 sizes: 줄어든 항목은 낮추고, 늘어난 항목과 새 항목은 allow_growth 일 때만 올린다. (sizes, 막힌 항목 [(이름, 옛, 새)])."""
    new, blocked = {}, []
    for name, text in items.items():
        size = len(text)
        prev = old.get(name)
        if prev is not None and size > prev and not allow_growth:
            blocked.append((name, prev, size))
            new[name] = prev
        elif prev is None and not allow_growth:
            blocked.append((name, 0, size))
        else:
            new[name] = size
    return new, blocked


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true", help="write nothing; show the diff, exit 1 when it differs")
    ap.add_argument("--allow-growth", action="store_true", help="raise sizes.json for items that grew or are new")
    a = ap.parse_args()
    items = collect()
    lines = diff(snapshot_files(), items)
    if a.check:
        print("\n".join(lines) if lines else "prompt surface unchanged")
        return 1 if lines else 0
    OUT.mkdir(parents=True, exist_ok=True)
    for p in OUT.glob("*.txt"):
        if p.stem not in items:
            p.unlink()
    for name, text in items.items():
        (OUT / (name + ".txt")).write_text(text, encoding="utf-8")
    sizes, blocked = merged_sizes(items, load_sizes().get("items", {}), a.allow_growth)
    SIZES.write_text(json.dumps({"items": sizes, "totals": totals(sizes)}, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print("wrote %d items to %s (%d lines of diff)" % (len(items), OUT.relative_to(ROOT), len(lines)))
    print("session start total: %d chars" % totals({k: len(v) for k, v in items.items()})["session_start"])
    if blocked:
        print("sizes.json not raised for items that grew or are new (rerun with --allow-growth and give the reason in the commit message):")
        for name, prev, size in blocked:
            print("  %s: %d -> %d" % (name, prev, size))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
