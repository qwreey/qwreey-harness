"""harness-doctor 툴킷: luau (Luau/Roblox). 판정 기준은 references/toolkits/luau.md.

scan.py 가 importlib 로 읽는다(-I 라 sys.path 에 기대지 않는다). 이 모듈은 scan.py 를 import 하지 않고
ctx 로 받은 도우미만 쓴다. 인터페이스는 plugins/q/docs/doctor-toolkits.md.
"""
import re

NAME = "luau"
TITLE = "Luau/Roblox"
REFERENCE = "references/toolkits/luau.md"
# 툴체인 핀을 비교할 mise 도구(짧은 이름)
PIN_TOOLS = ["luau", "luau-lsp", "stylua"]
MISE_MARKERS = {"luau", "luau-lsp", "stylua", "lune", "lute", "rojo", "wally", "pesde", "selene"}
ROOT_MARKERS = ("default.project.json", ".luaurc", "pesde.toml", "wally.toml", "selene.toml")
SKIP_DIRS = {"luau_packages", "lune_packages", "Packages"}
# 스킬 부작용 낌새에 더할 낱말(SKILL-SIDEFX). Studio 에 쓰는 동기화 도구.
SIDE_EFFECT_WORDS = [r"studio-sync"]


def detect(ctx):
    """감지 표식 목록. 비면 이 저장소에는 luau 툴킷을 켜지 않는다."""
    marks = []
    n = sum(1 for f in ctx.files if f.endswith(".luau"))
    if n:
        marks.append(f"*.luau {n}개")
    tools = ctx.mise_tools(ctx.repo / "mise.toml") if (ctx.repo / "mise.toml").is_file() else None
    hit = sorted(MISE_MARKERS & set(tools or {}))
    if hit:
        marks.append("mise.toml: " + ", ".join(hit))
    marks += [m for m in ROOT_MARKERS if (ctx.repo / m).is_file()]
    return marks


def check(ctx):
    if ctx.want(5):
        check_kb(ctx)
    if ctx.want(6):
        check_typedefs(ctx)
    if ctx.want(8):
        check_toolchain(ctx)


# ------------------------------------------------- 5 luau-kb 후보
KB_MARK = re.compile(r"<!--\s*luau-kb 후보")
KB_TERM = re.compile(r"luau-analyze|luau-lsp|새 솔버|new solver|솔버|type function|타입 함수|f<<|제네릭|generic|"
                     r"table\.(?:move|create|clone|freeze|pack)|math\.fmod|-O2|stylua|setmetatable|__index|pcall|"
                     r"상수 접기|인라인|업밸류|upvalue")
KB_EVID = re.compile(r"0\.7\d\d|\d+(?:\.\d+)?\s*배|\d+(?:~\d+)?\s*%|상류|upstream|결함|재현|실측")
KB_REF = REFERENCE + "#공유-지식-luau-kb"


def check_kb(ctx):
    repo = ctx.repo
    docs = [repo / "CLAUDE.md", repo / "GEMINI.md"] + sorted((repo / ".claude").glob("*.md")) + ctx.rule_files(repo / ".claude")
    marks, cands = [], {}
    for p in docs:
        if not p.is_file():
            continue
        lines = (ctx.read(p) or "").split("\n")
        for i, line in enumerate(lines, 1):
            if KB_MARK.search(line) and not re.search(r"`<!--", line):
                marks.append(f"{ctx.rel(p, repo)}:{i}")
                continue
            prev = lines[i - 2] if i > 1 else ""
            if KB_MARK.search(prev) or "`" * 3 in line:
                continue
            if KB_TERM.search(line) and KB_EVID.search(line):
                cands.setdefault(ctx.rel(p, repo), []).append(i)
    if marks:
        ctx.add(5, "정보", "KB-MARK", repo, f"luau-kb 후보 표시 {len(marks)}곳: " + ", ".join(marks[:8]) + (" …" if len(marks) > 8 else ""),
                KB_REF)
    for f, ls in sorted(cands.items(), key=lambda x: -len(x[1])):
        if len(ls) >= 2:
            ctx.add(5, "정보", "KB-CAND", f,
                    f"표시 없는 일반 Luau 지식 후보 {len(ls)}줄 (예: {', '.join(map(str, ls[:6]))}). 모델이 읽고 판정.",
                    KB_REF)


# ------------------------------------------------- 6 typedefs 사본
def check_typedefs(ctx):
    kb_defs = ctx.kb("luau") / "typedefs" / "globalTypes.d.luau"
    kb_md5 = ctx.md5(kb_defs) if kb_defs.is_file() else None
    for f in ctx.files:
        if re.search(r"(^|/)globalTypes[\w.]*\.d\.luau$", f):
            m = ctx.md5(ctx.repo / f)
            if kb_md5 is None:
                ctx.add(6, "정보", "DRIFT-TYPEDEFS", f, "luau-kb 정본이 없어 비교하지 못했다.")
            elif m == kb_md5:
                ctx.add(6, "정보", "DRIFT-TYPEDEFS", f, "luau-kb 정본과 같다(복제본). 참조로 바꿀지는 P5 범위.")
            else:
                ctx.add(6, "경고", "DRIFT-TYPEDEFS", f, f"luau-kb 정본과 md5 가 다르다({m[:8]} ≠ {kb_md5[:8]}). lsp 핀과 짝인지 확인.",
                        REFERENCE + "#typedefs-사본")


# ------------------------------------------------- 8 툴체인
SIBLING_CLAIM = re.compile(r"같은|같다|동일|따릅|따른|same as|matches")
TOOL_REF = REFERENCE + "#툴체인"


def check_toolchain(ctx):
    repo, projects = ctx.repo, ctx.projects
    if not any(f.endswith(".luau") for f in ctx.files):
        return  # 표식만 있고 소스가 없으면(스캐폴딩 전) 툴체인 검사는 하지 않는다 - 재구성 전과 같은 조건
    mise = repo / "mise.toml"
    tools = ctx.mise_tools(mise) if mise.is_file() else None
    if tools is None:
        ctx.add(8, "정보", "TOOL-PIN", "mise.toml", "mise.toml 이 없거나 읽히지 않는다. 버전 핀이 없다(D-05).")
    else:
        # 핀 값은 저장소 소유라(D-05) 공통 목표값이 없다. 형제 저장소 핀과 어긋날 때만 알린다.
        diff = ctx.pin_mismatch(tools, PIN_TOOLS)
        if diff:
            ctx.add(8, "정보", "TOOL-PIN", "mise.toml",
                    "핀: " + ", ".join(f"{k}={tools.get(k, '없음')}" for k in PIN_TOOLS) +
                    ". 형제 저장소 핀과 다름 — " + "; ".join(diff) + ". 핀은 저장소 소유(D-05)라 정보로만 낸다.",
                    TOOL_REF)
    sty = repo / "stylua.toml"
    alt = repo / ".stylua.toml"
    sp = sty if sty.is_file() else (alt if alt.is_file() else None)
    if sp is None:
        ctx.add(8, "경고", "TOOL-NOSTYLUA", repo, "stylua.toml 이 없다. 설정 없이 돌면 f<<T>> 가 시프트로 바뀐다(D-02).")
    else:
        conf = ctx.toml(sp)
        if conf is None:
            ctx.add(8, "오류", "TOOL-SYNTAX", ctx.rel(sp, repo), "stylua.toml 파싱 실패.")
        elif str(conf.get("syntax", "")).lower() != "luau":
            ctx.add(8, "오류", "TOOL-SYNTAX", ctx.rel(sp, repo), "syntax = \"Luau\" 가 없다. f<<T>> 가 exit 0 으로 시프트가 된다(D-02, 재현됨).",
                    TOOL_REF)
    if not (repo / ".luaurc").is_file():
        ctx.add(8, "정보", "TOOL-LUAURC", repo, ".luaurc 가 없다(strict 모드·lint 기본값 미정).")
    # 형제와 '같다'는 주석이 사실인지
    sibs = {p.name for p in projects.iterdir() if p.is_dir()} - {repo.name}
    for cfg in (mise, sp):
        if not cfg or not cfg.is_file():
            continue
        for i, line in enumerate((ctx.read(cfg) or "").split("\n"), 1):
            m = SIBLING_CLAIM.search(line)
            if not line.lstrip().startswith("#") or not m:
                continue
            # mise.toml 안에서 stylua.toml 모양을 말하면 stylua 설정끼리 비교한다
            kind = "stylua" if (cfg.name != "mise.toml" or "stylua.toml" in line) else "mise"
            named = [s for s in sorted(sibs) if re.search(rf"(?<![\w-]){re.escape(s)}(?![\w-])", line)]
            bad = []
            for s in named:
                if kind == "mise":
                    other, mine_v, load = projects / s / "mise.toml", ctx.mise_tools(cfg), ctx.mise_tools
                else:
                    other = projects / s / "stylua.toml"
                    other = other if other.is_file() else projects / s / ".stylua.toml"
                    mine_v, load = (ctx.toml(sp) if sp else None), ctx.toml
                theirs = load(other) if other.is_file() else None
                if theirs is None or mine_v is None:
                    bad.append(f"{s}({'mise.toml' if kind == 'mise' else 'stylua.toml'} 없음)")
                    continue
                keys = [k for k in PIN_TOOLS if k in mine_v or k in theirs] if kind == "mise" else sorted(set(mine_v) | set(theirs))
                dk = [f"{k} {mine_v.get(k, '없음')}≠{theirs.get(k, '없음')}" for k in keys if mine_v.get(k) != theirs.get(k)]
                if dk:
                    bad.append(f"{s}({', '.join(dk)})")
            if bad:
                strong = not re.match(r"따", m.group(0))
                ctx.add(8, "경고" if strong else "정보", "TOOL-CLAIM", f"{cfg.name}:{i}",
                        f"형제와 {'같다' if strong else '따른다'}는 주석이 사실과 다르다: {'; '.join(bad)}",
                        REFERENCE + "#형제와-같다는-주석")
