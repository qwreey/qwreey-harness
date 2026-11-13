#!/usr/bin/env python3
"""PostToolUse(Write|Edit|MultiEdit|Bash) 리마인더: 편집한 소스 파일이 길어졌거나 폴더가 평평해지면 알린다.

막지 않는다(decision 없음). additionalContext 만 주입한다.

왜: 사용자가 직접 지적한 구조 문제(.claude/audit/12-code-structure.md)는 모두 "한 파일에 계속 덧붙이기"와
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

툴킷 무관(.claude/audit/14): 확장자별 기준은 아래 TOOLKITS 표(luau·web·rust·python·go·jvm)다. 표에 없는 확장자는 건드리지 않는다.
  harness.env(lib/harness_env.py)의 HARNESS_TOOLKITS 가 비어 있지 않으면 그 툴킷만 본다.
  저장소가 표를 덮어쓰거나 더할 수 있다(아래 structure.json). 기본 기준은 모든 툴킷이 같다(경고 800, 강제 1500, 테스트 두 배).

예외(사용자 결정 D-13, 2026-11-10 — 확실한 이유가 있으면 기준을 넘어도 되지만 이유를 남긴다):
  파일 머리 10줄 안  `--@structure-exempt: <사유>`  (luau. web·rust·go 는 `//@structure-exempt:`, python 은 `#@structure-exempt:`)
  또는 structure.json  "exempt": [{"path": "<글롭>", "reason": "<사유>"}]
  사유가 비었거나 사유가 아닌 말("나중에", "귀찮", "TODO", "-")이면 무효다 — 평소처럼 알리고 무효라고 덧붙인다.
  유효한 예외 파일은 경고·강제·성장 알림 대신 "Reason: …" 한 줄(알림 문구는 영어, .claude/audit/17)을 세션당 한 번만 낸다(경고 기준 이상일 때).
강제 기준을 넘은 .luau/.lua 파일에는 분리 계획기(split-plan.py) 명령을 한 줄 붙인다. 계획기는 ~/.claude/skills/luau-style 에서 찾고,
  없으면 harness.env 의 HARNESS_LUAU_KB 또는 ${HARNESS_DOCTOR_ROOT}/packs/luau-kb(없으면 ${HARNESS_WORKSPACE}/claude-doctor/packs/luau-kb)에서 찾는다. 못 찾으면 안내를 생략한다.

저장소 설정: <프로젝트>/.claude/structure.json —
  {"warn": 800, "hard": 1500, "grow": 300, "flat": 15, "ignore": ["glob", …], "exempt": [{"path": "glob", "reason": "…"}],
   "toolkits": {"web": {"ext": [".ts", ".vue"], "warn": 600, "hard": 1200}, "go": {"ext": [".go"], "comment": ["//"]}}}
  ignore 는 측정 대상이 아닌 것(외부 코드·머리 표시 없는 생성물)에만 쓴다.
  toolkits 항목 키: ext, comment(예외 표식 주석), skip_suffix, skip_parts, test(정규식), warn, hard, grow.
  같은 이름이면 기본 표의 해당 키를 덮어쓰고, 새 이름이면 툴킷을 더한다. 툴킷 안의 warn/hard/grow 가 최상위 값보다 앞선다.
  저장소가 더한 확장자는 Write/Edit 에서만 본다(Bash 경로 탐지는 기본 표의 확장자만 안다).
끄기: 환경 변수 STRUCTURE_REMINDER=off
상태 파일: $TMPDIR/claude-structure-reminder/<session_id>.c<compact 회차>[.a<agent_id>].json (알렸는지 여부. lib/compact_epoch.py. compact 뒤 다시 알린다)
성장 기준점: $TMPDIR/claude-structure-reminder/<session_id>.base.json (session_id 단위. compact 회차가 올라도 유지한다)
"""
import fnmatch
import importlib.util
import json
import os
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import compact_epoch  # noqa: E402
import harness_nonce  # noqa: E402

# 툴킷 표: 확장자·예외 표식 주석·생성물 접미사·건너뛸 폴더·테스트 판정. 새 툴킷은 한 줄 더한다(또는 저장소 structure.json 의 toolkits).
TOOLKITS = {
    "luau": {"ext": [".luau", ".lua"], "comment": ["--"], "skip_suffix": [".d.luau"]},
    "web": {"ext": [".ts", ".tsx", ".js", ".jsx", ".mjs", ".astro"], "comment": ["//"],
            "skip_suffix": [".d.ts", ".d.mts", ".min.js", ".gen.ts"], "skip_parts": [".astro", ".next", ".turbo", ".svelte-kit"]},
    "rust": {"ext": [".rs"], "comment": ["//"], "skip_parts": ["target"]},
    "python": {"ext": [".py"], "comment": ["#"], "skip_suffix": ["_pb2.py", "_pb2_grpc.py"],
               "skip_parts": ["__pycache__", ".venv", "venv", "site-packages", ".mypy_cache"],
               "test": r"(^|/)test_[^/]*\.py$|_test\.py$|(^|/)conftest\.py$"},
    "go": {"ext": [".go"], "comment": ["//"], "skip_suffix": [".pb.go"]},
    "jvm": {"ext": [".kt"], "comment": ["//"]},
}
SKIP_PARTS = {"node_modules", ".git", "luau_packages", "roblox_packages", "lune_packages", "Packages", "vendor",
              "third_party", "build", "dist", "refs", "typedefs", "testdata", "media", "fixtures"}
HOMOGENEOUS = {"test", "tests", "spec", "specs", "stories", "spikes", "meshes", "assets", "examples", "gallery"}
GEN_MARK = re.compile(r"generated|do not edit|@generated|손으로 고치지 않는다|만든 것:", re.I)
TEST_PATH = re.compile(r"(^|/)(tests?|specs?|spikes?|bench|__tests__)(/|$)|\.(spec|test|story)\.|_test\.(go|rs)$", re.I)
PASCAL_PREFIX = re.compile(r"^([A-Z][a-z0-9]+)(?=[A-Z])")
INTERP = {"python", "python3", "node", "deno", "bun", "perl", "ruby", "lua", "luau", "lune", "lute"}
_EXTS = sorted({e[1:] for t in TOOLKITS.values() for e in t["ext"]}, key=len, reverse=True)
CODE = r"[\w./@-]+\.(?:" + "|".join(_EXTS) + r")\b"
INPLACE = re.compile(r"\bsed\s+(-\S*\s+)*-i|\bperl\s+(-\S*\s+)*-\S*p\S*i|\bawk\s+-i\s+inplace|\bpatch\b")
REDIRECT = re.compile(r"(?<![0-9&])>>?\s*['\"]?(" + CODE + r")|\btee\s+(?:-a\s+)?['\"]?(" + CODE + r")")
BASH_PATH = re.compile(CODE)
DEFAULTS = {"warn": 800, "hard": 1500, "grow": 300, "flat": 15, "ignore": [], "exempt": [], "toolkits": {}}
REF = "the qwreey-conventions rule code-structure (rules/code-structure.md in the plugin; injected when you open a matching file)"
PLANNER_REL = "skills/luau-style/scripts/split-plan.py"
# 사유가 아닌 말: 비었거나, 미루기·귀찮음·자리표시
NOT_A_REASON = re.compile(r"^(?:[-.…~_?!\s]*|todo|tbd|fixme|later|wip|n/?a|none|x+|임시|나중에?|나중에 ?나눔|추후|일단|귀찮.*)$", re.I)

_ENV = None


def harness_env():
    """~/.claude/lib/harness_env.py 로 harness.env 를 읽는다(한 번). 없거나 깨졌으면 {}."""
    global _ENV
    if _ENV is None:
        home = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
        try:
            spec = importlib.util.spec_from_file_location("harness_env", home / "lib" / "harness_env.py")
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            _ENV = mod.load([home / "harness.env"])
        except Exception:
            _ENV = {}
    return _ENV


def base_state_path(session_id):
    """Growth baselines per session_id (not per compact epoch): a compact must not reset the "+N lines this session" baseline."""
    d = os.path.join(tempfile.gettempdir(), "claude-structure-reminder")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, re.sub(r"[^\w-]", "", str(session_id or "nosession")) + ".base.json")


def dedup_path(namespace, session_id, agent_id=None):
    """State file keyed by (session_id, compact epoch): compact_epoch.py(이 플러그인 자기 회차)."""
    return compact_epoch.state_path("qwreey-conventions", namespace, session_id, agent_id)


def find_planner():
    """split-plan.py 경로. 못 찾으면 None(안내 생략)."""
    env = harness_env()
    cands = [Path.home() / ".claude" / PLANNER_REL]
    kb = env.get("HARNESS_LUAU_KB")
    if not kb:
        root = env.get("HARNESS_DOCTOR_ROOT") or (os.path.join(env["HARNESS_WORKSPACE"], "claude-doctor") if env.get("HARNESS_WORKSPACE") else "")
        kb = os.path.join(root, "packs", "luau-kb") if root else ""
    if kb:
        cands.append(Path(kb) / PLANNER_REL)
    return next((str(c) for c in cands if c.is_file()), None)


def reason_ok(reason):
    r = (reason or "").strip()
    return bool(r) and not NOT_A_REASON.match(r) and "귀찮" not in r and len(re.sub(r"\W", "", r)) >= 2


def exemption(head10, rel, cfg, comments):
    """(사유, 유효한가, 어디서) 또는 None. 머리 표식이 structure.json 보다 앞선다."""
    mark = re.compile(r"^\s*(?:" + "|".join(re.escape(c) for c in comments) +
                      r")\s*@structure-exempt\b\s*:?\s*(.*?)\s*(?:\]\]|\*/)?\s*$")
    for line in head10.split("\n"):
        m = mark.match(line)
        if m:
            return m.group(1), reason_ok(m.group(1)), "header mark"
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


def toolkit_table(cfg):
    """기본 표 − HARNESS_TOOLKITS 밖의 툴킷 + 저장소 structure.json 의 덮어쓰기·추가."""
    enabled = set((harness_env().get("HARNESS_TOOLKITS") or "").split())
    table = {k: dict(v) for k, v in TOOLKITS.items() if not enabled or k in enabled}
    over = cfg.get("toolkits")
    for name, spec in (over.items() if isinstance(over, dict) else []):
        if isinstance(spec, dict):
            table[name] = {**table.get(name, {}), **spec}
    return table


def toolkit_of(name, table):
    """(툴킷 이름, 항목) 또는 None. 생성물 접미사면 None."""
    ext = os.path.splitext(name)[1]
    for tk, spec in table.items():
        if ext in (spec.get("ext") or []):
            return None if name.endswith(tuple(spec.get("skip_suffix") or ())) else (tk, spec)
    return None


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


def check_file(path, tool, ti, data, state, created, bases=None):
    """파일 하나의 길이·성장·폴더를 보고 알릴 문장들을 돌려준다."""
    path = os.path.abspath(path)
    if not os.path.isfile(path):
        return []
    root = project_root(path, data)
    cfg = load_cfg(root)
    table = toolkit_table(cfg)
    hit = toolkit_of(os.path.basename(path), table)
    if not hit:
        return []
    tk, spec = hit
    rel = os.path.relpath(path, root)
    parts = set(rel.split(os.sep)[:-1])
    if parts & (SKIP_PARTS | set(spec.get("skip_parts") or [])):
        return []
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
        bases = {} if bases is None else bases
        if path not in bases:  # 성장 기준점은 세션 단위(compact 뒤에도 유지). 알림 여부(said)만 회차 단위다
            add = added_lines(tool, ti)
            base = 0 if created == "sure" else (n - add if add is not None else n)
            bases[path] = max(0, base)
        entry = files[path] = {"base": bases[path], "said": []}

    is_test = bool(TEST_PATH.search(rel) or (spec.get("test") and re.search(spec["test"], rel)))
    k = 2 if is_test else 1
    warn, hard, grow = (spec.get(x, cfg[x]) * k for x in ("warn", "hard", "grow"))
    comments = spec.get("comment") or ["--", "//", "#"]
    notes = []
    said = entry["said"]
    ex = exemption(head, rel, cfg, comments)
    exempt = bool(ex and ex[1])
    if exempt and n >= warn and "exempt" not in said:
        said.append("exempt")
        notes.append(Note("info", f"`{rel}` ({n} lines) has a structure exemption. Reason: {ex[0]} ({ex[2]})"))
    if exempt:
        pass  # 길이 알림 대신 위의 사유 한 줄만
    elif n >= hard and "hard" not in said:
        said += ["hard", "warn"]
        planner = find_planner() if tk == "luau" else None
        plan = f" First extract candidate groups with `python3 -I {planner} {path}` (read-only)." if planner else ""
        notes.append(Note("action", f"`{rel}` is {n} lines, over the hard limit ({hard}). Finish the current edit, but before adding more features "
                     f"to this file, propose a split to the user (which groups go where; a move-only commit first) and wait for an answer.{plan}"
                     f" If the file must stay whole for a solid reason (type limits, generated, pure data), put "
                     f"`{comments[0]}@structure-exempt: <reason>` in its header."))
    elif n >= warn and "warn" not in said:
        said.append("warn")
        notes.append(Note("warn", f"`{rel}` is {n} lines (warn limit {warn}). Before adding more, check for a responsibility group to split out; "
                     f"if there is one, name the split candidate in one line in your report."))
    if ex and not ex[1] and n >= warn and "exempt-bad" not in said and said:
        said.append("exempt-bad")
        notes.append(Note("warn", f"The structure exemption on `{rel}` ({ex[2]}) is invalid: the reason is empty or not a reason (\"{ex[0]}\"). "
                     f"Give a real reason or remove the mark."))
    if not exempt and n - entry["base"] >= grow and n >= warn and "grow" not in said:
        said.append("grow")
        notes.append(Note("warn", f"`{rel}` grew {entry['base']} -> {n} lines (+{n - entry['base']}) this session. If you keep appending new code "
                     f"to one file, first see whether it can become a new module."))

    if created and os.path.basename(os.path.dirname(path)).lower() not in HOMOGENEOUS and not is_test:
        d = os.path.dirname(path)
        try:
            names = os.listdir(d)
        except OSError:
            names = []
        srcs = [x for x in names if toolkit_of(x, table) and os.path.isfile(os.path.join(d, x))]
        subdirs = [x for x in names if os.path.isdir(os.path.join(d, x)) and not x.startswith(".")]
        drel = os.path.relpath(d, root)
        entry_name = "init.luau" if tk == "luau" else "an index file"
        if len(srcs) >= cfg["flat"] and len(subdirs) <= 2 and drel not in seen_dirs:
            seen_dirs.append(drel)
            notes.append(Note("info", f"`{drel}/` has {len(srcs)} source files and {len(subdirs)} subfolders. "
                         f"If related files form groups, consider proposing folders ({entry_name}); a flat layout by design needs nothing."))
        prefix = prefix_of(os.path.splitext(os.path.basename(path))[0])
        fam = sorted({os.path.splitext(x)[0] for x in srcs if prefix_of(os.path.splitext(x)[0]) == prefix})
        key = drel + "::" + prefix
        if len(fam) >= 3 and prefix not in subdirs and key not in seen_dirs:
            seen_dirs.append(key)
            notes.append(Note("info", f"`{drel}/` has {len(fam)} files starting with `{prefix}` ({', '.join(fam)}). "
                         f"Consider grouping them into a `{prefix}/` folder ({entry_name})."))
    return notes


class Note(str):
    """Message text with an urgency level (info|warn|action; None = no level of its own). See HOOK-MESSAGES.md."""
    def __new__(cls, level, text):
        o = super().__new__(cls, text)
        o.level = level
        return o


def top_level(notes):
    order = ["info", "warn", "action"]
    lv = [n.level for n in notes if getattr(n, "level", None) in order]
    return max(lv, key=order.index) if lv else "info"


def render(notes, session_id=None):
    """One tag per level, highest first, so a lower notice is not read at a higher level. Level-less notes ride with the highest."""
    top = top_level(notes)
    tags = []
    for lv in ("action", "warn", "info"):
        body = [n for n in notes if (getattr(n, "level", None) or top) == lv]
        if body:
            tags.append(f'<harness-hook name="structure-reminder" level="{lv}"{harness_nonce.attr(session_id)}>\n' + " ".join(body) + "\n</harness-hook>")
    return "\n".join(tags)


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
    paths = [p for p in paths if p]
    if not paths:
        return 0

    sid = re.sub(r"[^\w-]", "", str(data.get("session_id") or "nosession"))
    state_path = dedup_path("claude-structure-reminder", data.get("session_id"), data.get("agent_id"))
    try:
        state = json.load(open(state_path))
    except Exception:
        state = {}
    base_path = base_state_path(data.get("session_id"))
    try:
        bases = json.load(open(base_path))
    except Exception:
        bases = {}
    n_bases = len(bases)

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
        notes += check_file(p, tool, ti, data, state, created, bases)

    if notes and not state.get("ref_said"):
        state["ref_said"] = True
        notes.append(Note(None, f"Limits and how to split: {REF}. The repo's .claude/structure.json can change the limits and the toolkit table."))
    try:
        json.dump(state, open(state_path, "w"))
        if len(bases) != n_bases:
            json.dump(bases, open(base_path, "w"))
    except OSError:
        pass
    if not notes:
        return 0
    json.dump({"hookSpecificOutput": {"hookEventName": "PostToolUse",
                                      "additionalContext": render(notes, data.get("session_id"))}},
              sys.stdout, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
