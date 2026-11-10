#!/usr/bin/env python3
"""PostToolUse(Write|Edit|MultiEdit) 리마인더: 편집한 소스 파일이 길어졌거나 폴더가 평평해지면 알린다.

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
테스트 파일은 줄 기준을 두 배로 본다. 머리 6줄에 생성물 표시가 있으면 보지 않는다.

저장소 설정: <프로젝트>/.claude/structure.json — {"warn": 800, "hard": 1500, "grow": 300, "flat": 15, "ignore": ["glob", …]}
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
DEFAULTS = {"warn": 800, "hard": 1500, "grow": 300, "flat": 15, "ignore": []}
REF = "~/.claude/skills/luau-style/references/structure.md"


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
    head = "\n".join(text.split("\n", 6)[:6])
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


def main():
    if os.environ.get("STRUCTURE_REMINDER", "").lower() == "off":
        return 0
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0
    tool = data.get("tool_name") or ""
    ti = data.get("tool_input") or {}
    path = ti.get("file_path") or ""
    if tool not in ("Write", "Edit", "MultiEdit") or not path or not is_src(os.path.basename(path)):
        return 0
    path = os.path.abspath(path)
    if not os.path.isfile(path) or set(path.split(os.sep)) & SKIP_PARTS:
        return 0
    root = project_root(path, data)
    cfg = load_cfg(root)
    rel = os.path.relpath(path, root)
    if any(fnmatch.fnmatch(rel, g) for g in cfg["ignore"]):
        return 0
    try:
        n, head = count_lines(path)
    except OSError:
        return 0
    if n is None or GEN_MARK.search(head):
        return 0

    sid = re.sub(r"[^\w-]", "", str(data.get("session_id") or "nosession"))
    state_dir = os.path.join(tempfile.gettempdir(), "claude-structure-reminder")
    os.makedirs(state_dir, exist_ok=True)
    state_path = os.path.join(state_dir, sid + ".json")
    try:
        state = json.load(open(state_path))
    except Exception:
        state = {}
    files = state.setdefault("files", {})
    seen_dirs = state.setdefault("dirs", [])

    resp = data.get("tool_response") if isinstance(data.get("tool_response"), dict) else {}
    # Write 의 tool_response.type 이 "create" 면 새 파일이다. 그 값이 없으면 세션에서 처음 쓴 Write 를 새 파일로 본다
    # (폴더 검사는 폴더마다 한 번이라 오판해도 알림이 한 번 더 나는 정도다). 성장 기준점은 확실히 새 파일일 때만 0 으로 둔다.
    surely_new = tool == "Write" and resp.get("type") == "create"
    created = surely_new or (tool == "Write" and resp.get("type") is None and path not in files)
    entry = files.get(path)
    if entry is None:
        add = added_lines(tool, ti)
        base = 0 if surely_new else (n - add if add is not None else n)
        entry = files[path] = {"base": max(0, base), "said": []}

    k = 2 if TEST_PATH.search(rel) else 1
    warn, hard, grow = cfg["warn"] * k, cfg["hard"] * k, cfg["grow"] * k
    notes = []
    said = entry["said"]
    if n >= hard and "hard" not in said:
        said += ["hard", "warn"]
        notes.append(f"`{rel}` 이 {n}줄로 강제 기준({hard}줄)을 넘었습니다. 지금 하던 수정은 마무리하되, 이 파일에 새 기능을 "
                     f"더 덧붙이기 전에 분리안(어떤 묶음을 어디로, '옮기기만' 커밋을 먼저)을 사용자에게 제시하고 답을 받으세요.")
    elif n >= warn and "warn" not in said:
        said.append("warn")
        notes.append(f"`{rel}` 이 {n}줄입니다(경고 기준 {warn}줄). 더 덧붙이기 전에 떼어 낼 책임 묶음이 있는지 보고, "
                     f"있으면 작업 보고에 분리 후보를 한 줄로 적으세요.")
    if n - entry["base"] >= grow and n >= warn and "grow" not in said:
        said.append("grow")
        notes.append(f"이번 세션에 `{rel}` 이 {entry['base']} → {n}줄(+{n - entry['base']})로 늘었습니다. 새 코드를 한 파일에 "
                     f"계속 붙이고 있다면 새 모듈로 낼 수 있는지 먼저 보세요.")

    if created:
        d = os.path.dirname(path)
        try:
            names = os.listdir(d)
        except OSError:
            names = []
        srcs = [x for x in names if is_src(x) and os.path.isfile(os.path.join(d, x))]
        subdirs = [x for x in names if os.path.isdir(os.path.join(d, x)) and not x.startswith(".")]
        drel = os.path.relpath(d, root)
        if os.path.basename(d).lower() not in HOMOGENEOUS and not TEST_PATH.search(rel):
            if len(srcs) >= cfg["flat"] and len(subdirs) <= 2 and drel not in seen_dirs:
                seen_dirs.append(drel)
                notes.append(f"`{drel}/` 에 소스 파일이 {len(srcs)}개 있고 하위 폴더는 {len(subdirs)}개입니다. "
                             f"같은 기능끼리 폴더(입구 init.luau)로 묶을지 사용자에게 제안하세요.")
            stem = os.path.splitext(os.path.basename(path))[0]
            m = PASCAL_PREFIX.match(stem)
            prefix = m.group(1) if m else stem
            def prefix_of(stem_):
                m_ = PASCAL_PREFIX.match(stem_)
                return m_.group(1) if m_ else stem_
            fam = sorted({os.path.splitext(x)[0] for x in srcs if prefix_of(os.path.splitext(x)[0]) == prefix})
            key = drel + "::" + prefix
            if len(fam) >= 3 and prefix not in subdirs and key not in seen_dirs:
                seen_dirs.append(key)
                notes.append(f"`{drel}/` 에 `{prefix}` 로 시작하는 파일이 {len(fam)}개입니다({', '.join(fam)}). "
                             f"`{prefix}/` 폴더(입구 init.luau)로 묶는 것을 검토하세요.")

    try:
        json.dump(state, open(state_path, "w"))
    except OSError:
        pass
    if not notes:
        return 0
    if not state.get("ref_said"):
        state["ref_said"] = True
        notes.append(f"기준과 나누는 법: {REF}. 저장소 .claude/structure.json 이 기준 값을 바꿀 수 있습니다.")
        try:
            json.dump(state, open(state_path, "w"))
        except OSError:
            pass
    json.dump({"hookSpecificOutput": {"hookEventName": "PostToolUse",
                                      "additionalContext": "[structure-reminder] " + " ".join(notes)}},
              sys.stdout, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
