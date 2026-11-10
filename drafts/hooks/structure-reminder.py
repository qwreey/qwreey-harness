#!/usr/bin/env python3
# 정본으로 이동 → home/.claude/hooks/structure-reminder.py (이 사본은 더 고치지 않는다)
"""PostToolUse(Write|Edit|MultiEdit|Bash) 리마인더: 편집한 소스 파일이 길어졌거나 폴더가 평평해지면 알린다.

막지 않는다(decision 없음). additionalContext 만 주입한다.

왜: 사용자가 직접 지적한 구조 문제(audit/12-code-structure.md)는 모두 "한 파일에 계속 덧붙이기"와
"새 파일을 부르는 쪽 옆에 계속 두기"에서 나왔다. devplorer 서버 init.luau 는 사흘 동안 692 → 4,101줄,
한 게임 저장소의 서버 모듈은 아흐레 동안 646 → 3,501줄, devui Window/Manager.luau 는 이틀 동안 273 → 3,352줄이 됐다.
Edit 도구는 조각만 보여 주므로 모델은 파일 전체 길이를 잘 보지 못한다. 그래서 길이를 바로 알려 준다.

알리는 것 (모두 세션당 한 번):
  warn  — 파일이 경고 기준(기본 800줄)을 넘음. 파일마다 한 번.
  hard  — 강제 기준(기본 1500줄)을 넘음. 더 덧붙이기 전에 분리안을 사용자에게 묻게 한다. 파일마다 한 번.
  grow  — 이번 세션에 그 파일이 GROW(기본 300)줄 넘게 늘었고 경고 기준 이상. 파일마다 한 번.
  flat  — 새 파일을 만든 폴더에 소스가 flat(기본 15)개 이상이고 하위 폴더가 2개 이하. 폴더마다 한 번.
  family — 새 파일과 같은 PascalCase 접두를 가진 파일이 그 폴더에 셋 이상(예: ItemPick, ItemView, ItemZoneView).
Bash 는 파일을 바꿨을 법한 명령(sed -i, 리다이렉트, tee, patch, 인터프리터)에 든 소스 경로만 본다.
audit 10 기준 이 세션들의 파일 수정은 Bash(sed -i·python) 쪽이 Edit 보다 열 배 많았다.
테스트 파일은 줄 기준을 두 배로 본다. 머리 6줄에 생성물 표시가 있으면 보지 않는다.

예외(사용자 결정 D-13, 2026-11-10 — 확실한 이유가 있으면 기준을 넘어도 되지만 이유를 남긴다):
  파일 머리 10줄 안  `--@structure-exempt: <사유>`  (TS·Go 는 `//@structure-exempt:`, Python 은 `#@structure-exempt:`)
  또는 structure.json  "exempt": [{"path": "<글롭>", "reason": "<사유>"}]
  사유가 비었거나 사유가 아닌 말("나중에", "귀찮", "TODO", "-")이면 무효다 — 평소처럼 알리고 무효라고 덧붙인다.
  유효한 예외 파일은 경고·강제·성장 알림 대신 "예외 사유: …" 한 줄을 세션당 한 번만 낸다(경고 기준 이상일 때).
강제 기준을 넘은 .luau 파일에는 분리 계획기(split-plan.py) 명령을 한 줄 붙인다.

저장소 설정: <프로젝트>/.claude/structure.json — {"warn": 800, "hard": 1500, "grow": 300, "flat": 15, "ignore": ["glob", …],
  "exempt": [{"path": "glob", "reason": "…"}]}.  ignore 는 측정 대상이 아닌 것(외부 코드·머리 표시 없는 생성물)에만 쓴다.
끄기: 환경 변수 STRUCTURE_REMINDER=off
상태 파일: $TMPDIR/claude-structure-reminder/<session_id>.json
"""
import fnmatch
import json
import os
import re
import sys
import tempfile

EXT = {".luau", ".lua", ".ts", ".tsx", ".js", ".mjs", ".go", ".py", ".kt", ".rs"}
SKIP_PARTS = {"node_modules", ".git", "luau_packages", "roblox_packages", "lune_packages", "Packages", "vendor",
              "third_party", "build", "dist", "refs", "typedefs", "testdata", "media", "fixtures"}
HOMOGENEOUS = {"test", "tests", "spec", "specs", "stories", "spikes", "meshes", "assets", "examples", "gallery"}
GEN_MARK = re.compile(r"generated|do not edit|@generated|손으로 고치지 않는다|만든 것:", re.I)
TEST_PATH = re.compile(r"(^|/)(tests?|specs?|spikes?|bench)(/|$)|\.(spec|test|story)\.|_test\.go$", re.I)
PASCAL_PREFIX = re.compile(r"^([A-Z][a-z0-9]+)(?=[A-Z])")
INTERP = {"python", "python3", "node", "deno", "bun", "perl", "ruby", "lua", "luau", "lune", "lute"}
CODE = r"[\w./@-]+\.(?:luau|lua|tsx?|go|py|kt|rs|mjs|js)\b"
INPLACE = re.compile(r"\bsed\s+(-\S*\s+)*-i|\bperl\s+(-\S*\s+)*-\S*p\S*i|\bawk\s+-i\s+inplace|\bpatch\b")
REDIRECT = re.compile(r"(?<![0-9&])>>?\s*['\"]?(" + CODE + r")|\btee\s+(?:-a\s+)?['\"]?(" + CODE + r")")
BASH_PATH = re.compile(CODE)
DEFAULTS = {"warn": 800, "hard": 1500, "grow": 300, "flat": 15, "ignore": [], "exempt": []}
REF = "~/.claude/skills/luau-style/references/structure.md"
PLANNER = "~/.claude/skills/luau-style/scripts/split-plan.py"
EXEMPT_MARK = re.compile(r"^\s*(?:--|//|#)\s*@structure-exempt\b\s*:?\s*(.*?)\s*(?:\]\])?\s*$")
# 사유가 아닌 말: 비었거나, 미루기·귀찮음·자리표시
NOT_A_REASON = re.compile(r"^(?:[-.…~_?!\s]*|todo|tbd|fixme|later|wip|n/?a|none|x+|임시|나중에?|나중에 ?나눔|추후|일단|귀찮.*)$", re.I)


def reason_ok(reason):
    r = (reason or "").strip()
    return bool(r) and not NOT_A_REASON.match(r) and "귀찮" not in r and len(re.sub(r"\W", "", r)) >= 2


def exemption(head10, rel, cfg):
    """(사유, 유효한가, 어디서) 또는 None. 머리 표식이 structure.json 보다 앞선다."""
    for line in head10.split("\n"):
        m = EXEMPT_MARK.match(line)
        if m:
            return m.group(1), reason_ok(m.group(1)), "머리 표식"
    for e in cfg.get("exempt") or []:
        if isinstance(e, dict) and fnmatch.fnmatch(rel, str(e.get("path") or "")):
            return str(e.get("reason") or ""), reason_ok(e.get("reason")), "structure.json"
    return None


def project_root(path, data):
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    if env and path.startswith(env.rstrip("/") + "/"):
        return env
    d = os.path.dirname(path)
    while d and d != "/":
        if os.path.exists(os.path.join(d, ".git")) or os.path.isdir(os.path.join(d, ".claude")):
            return d
        d = os.path.dirname(d)
    return data.get("cwd") or os.path.dirname(path)


def load_cfg(root):
    cfg = dict(DEFAULTS)
    try:
        cfg.update(json.load(open(os.path.join(root, ".claude", "structure.json"))))
    except Exception:
        pass
    return cfg


def count_lines(path):
    with open(path, "rb") as f:
        raw = f.read()
    if b"\0" in raw[:1024]:
        return None, ""
    text = raw.decode("utf-8", "replace")
    head = "\n".join(text.split("\n", 10)[:10])
    return text.count("\n") + (0 if text.endswith("\n") or not text else 1), head


def added_lines(tool, ti):
    """편집이 늘린 줄 수 추정(Edit/MultiEdit). Write 는 None."""
    def delta(e):
        return (e.get("new_string") or "").count("\n") - (e.get("old_string") or "").count("\n")
    if tool == "Edit":
        return delta(ti)
    if tool == "MultiEdit":
        return sum(delta(e) for e in ti.get("edits") or [])
    return None


def is_src(name):
    return os.path.splitext(name)[1] in EXT and not name.endswith((".d.ts", ".min.js", ".d.luau"))


def bash_paths(cmd, cwd):
    """Bash 명령이 바꿨을 법한 소스 경로. sed -i·perl -pi·patch·인터프리터면 명령에 든 소스 경로 전부,
    리다이렉트·tee 면 그 대상만. 프로젝트 밖(스크래치 /tmp 등)은 뺀다."""
    words = [os.path.basename(w) for seg in re.split(r"&&|\|\||[;|\n]", cmd) for w in seg.split()[:3]]
    if INPLACE.search(cmd) or set(words) & INTERP:
        found = [m.group(0) for m in BASH_PATH.finditer(cmd)]
    else:
        found = [m.group(1) or m.group(2) for m in REDIRECT.finditer(cmd)]
    proj = (os.environ.get("CLAUDE_PROJECT_DIR") or cwd).rstrip("/") + "/"
    out = []
    for p in found:
        p = os.path.normpath(p if os.path.isabs(p) else os.path.join(cwd, p))
        if p not in out and p.startswith(proj):
            out.append(p)
    return out[:8]


def check_file(path, tool, ti, data, state, created):
    """파일 하나의 길이·성장·폴더를 보고 알릴 문장들을 돌려준다."""
    if not is_src(os.path.basename(path)):
        return []
    path = os.path.abspath(path)
    if not os.path.isfile(path) or set(path.split(os.sep)) & SKIP_PARTS:
        return []
    root = project_root(path, data)
    cfg = load_cfg(root)
    rel = os.path.relpath(path, root)
    if any(fnmatch.fnmatch(rel, g) for g in cfg["ignore"]):
        return []
    try:
        n, head = count_lines(path)
    except OSError:
        return []
    if n is None or GEN_MARK.search("\n".join(head.split("\n")[:6])):
        return []
    files = state.setdefault("files", {})
    seen_dirs = state.setdefault("dirs", [])
    entry = files.get(path)
    if entry is None:
        add = added_lines(tool, ti)
        base = 0 if created == "sure" else (n - add if add is not None else n)
        entry = files[path] = {"base": max(0, base), "said": []}

    k = 2 if TEST_PATH.search(rel) else 1
    warn, hard, grow = cfg["warn"] * k, cfg["hard"] * k, cfg["grow"] * k
    notes = []
    said = entry["said"]
    ex = exemption(head, rel, cfg)
    exempt = bool(ex and ex[1])
    if exempt and n >= warn and "exempt" not in said:
        said.append("exempt")
        notes.append(f"`{rel}` ({n}줄)은 구조 예외입니다. 예외 사유: {ex[0]} ({ex[2]})")
    if exempt:
        pass  # 길이 알림 대신 위의 사유 한 줄만
    elif n >= hard and "hard" not in said:
        said += ["hard", "warn"]
        plan = (f" 나눌 묶음은 `python3 -I {PLANNER} {path}` 로 먼저 뽑아 보세요(읽기 전용)."
                if path.endswith((".luau", ".lua")) else "")
        notes.append(f"`{rel}` 이 {n}줄로 강제 기준({hard}줄)을 넘었습니다. 지금 하던 수정은 마무리하되, 이 파일에 새 기능을 "
                     f"더 덧붙이기 전에 분리안(어떤 묶음을 어디로, '옮기기만' 커밋을 먼저)을 사용자에게 제시하고 답을 받으세요.{plan}"
                     f" 확실한 이유(타입 한계·생성물·순수 데이터)로 한 파일이어야 하면 머리에 `--@structure-exempt: <사유>` 를 답니다.")
    elif n >= warn and "warn" not in said:
        said.append("warn")
        notes.append(f"`{rel}` 이 {n}줄입니다(경고 기준 {warn}줄). 더 덧붙이기 전에 떼어 낼 책임 묶음이 있는지 보고, "
                     f"있으면 작업 보고에 분리 후보를 한 줄로 적으세요.")
    if ex and not ex[1] and n >= warn and "exempt-bad" not in said and said:
        said.append("exempt-bad")
        notes.append(f"`{rel}` 의 구조 예외({ex[2]})는 사유가 비었거나 사유가 아니어서(\"{ex[0]}\") 무효입니다. "
                     f"이유를 적거나 표식을 지우세요.")
    if not exempt and n - entry["base"] >= grow and n >= warn and "grow" not in said:
        said.append("grow")
        notes.append(f"이번 세션에 `{rel}` 이 {entry['base']} → {n}줄(+{n - entry['base']})로 늘었습니다. 새 코드를 한 파일에 "
                     f"계속 붙이고 있다면 새 모듈로 낼 수 있는지 먼저 보세요.")

    if created and os.path.basename(os.path.dirname(path)).lower() not in HOMOGENEOUS and not TEST_PATH.search(rel):
        d = os.path.dirname(path)
        try:
            names = os.listdir(d)
        except OSError:
            names = []
        srcs = [x for x in names if is_src(x) and os.path.isfile(os.path.join(d, x))]
        subdirs = [x for x in names if os.path.isdir(os.path.join(d, x)) and not x.startswith(".")]
        drel = os.path.relpath(d, root)
        if len(srcs) >= cfg["flat"] and len(subdirs) <= 2 and drel not in seen_dirs:
            seen_dirs.append(drel)
            notes.append(f"`{drel}/` 에 소스 파일이 {len(srcs)}개 있고 하위 폴더는 {len(subdirs)}개입니다. "
                         f"같은 기능끼리 폴더(입구 init.luau)로 묶을지 사용자에게 제안하세요.")
        prefix = prefix_of(os.path.splitext(os.path.basename(path))[0])
        fam = sorted({os.path.splitext(x)[0] for x in srcs if prefix_of(os.path.splitext(x)[0]) == prefix})
        key = drel + "::" + prefix
        if len(fam) >= 3 and prefix not in subdirs and key not in seen_dirs:
            seen_dirs.append(key)
            notes.append(f"`{drel}/` 에 `{prefix}` 로 시작하는 파일이 {len(fam)}개입니다({', '.join(fam)}). "
                         f"`{prefix}/` 폴더(입구 init.luau)로 묶는 것을 검토하세요.")
    return notes


def prefix_of(stem):
    m = PASCAL_PREFIX.match(stem)
    return m.group(1) if m else stem


def main():
    if os.environ.get("STRUCTURE_REMINDER", "").lower() == "off":
        return 0
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0
    tool = data.get("tool_name") or ""
    ti = data.get("tool_input") or {}
    resp = data.get("tool_response") if isinstance(data.get("tool_response"), dict) else {}
    if tool in ("Write", "Edit", "MultiEdit"):
        paths = [ti.get("file_path") or ""]
    elif tool == "Bash":
        paths = bash_paths(ti.get("command") or "", data.get("cwd") or os.getcwd())
    else:
        return 0
    paths = [p for p in paths if p and is_src(os.path.basename(p))]
    if not paths:
        return 0

    sid = re.sub(r"[^\w-]", "", str(data.get("session_id") or "nosession"))
    state_dir = os.path.join(tempfile.gettempdir(), "claude-structure-reminder")
    os.makedirs(state_dir, exist_ok=True)
    state_path = os.path.join(state_dir, sid + ".json")
    try:
        state = json.load(open(state_path))
    except Exception:
        state = {}

    notes = []
    for p in paths:
        # Write 의 tool_response.type 이 "create" 면 확실히 새 파일이다. 그 값이 없으면 세션에서 처음 쓴 Write 를 새 파일로 본다
        # (폴더 알림은 폴더마다 한 번이라 오판해도 한 번 더 나는 정도다). 성장 기준점은 확실할 때만 0 으로 둔다.
        created = None
        if tool == "Write":
            if resp.get("type") == "create":
                created = "sure"
            elif resp.get("type") is None and os.path.abspath(p) not in state.get("files", {}):
                created = "guess"
        notes += check_file(p, tool, ti, data, state, created)

    if notes and not state.get("ref_said"):
        state["ref_said"] = True
        notes.append(f"기준과 나누는 법: {REF}. 저장소 .claude/structure.json 이 기준 값을 바꿀 수 있습니다.")
    try:
        json.dump(state, open(state_path, "w"))
    except OSError:
        pass
    if not notes:
        return 0
    json.dump({"hookSpecificOutput": {"hookEventName": "PostToolUse",
                                      "additionalContext": "[structure-reminder] " + " ".join(notes)}},
              sys.stdout, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
