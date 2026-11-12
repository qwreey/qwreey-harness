"""harness-doctor 항목 1(상시 로드)·2(rules)·3(스킬) 검사. 읽기 전용.

scan.py 가 경로로 적재하고 C 에 자기 자신을 걸어 둔다. 공용 함수·상수·add 는 C.<이름> 으로 부른다(호출 시점에 찾는다).
"""
import difflib
import os
import re
from pathlib import Path

C = None


# ------------------------------------------------------- 1 상시 로드
IMPORT_RX = re.compile(r"(?:^|\s)@((?:~/|\.{1,2}/|/)?[\w.\-][\w./\-]*)")


def imports_of(path):
    text = C.read(path)
    if text is None:
        return []
    res = []
    for m in IMPORT_RX.finditer(C.strip_code(text)):
        raw = m.group(1).rstrip(".,;:")
        p = Path(os.path.expanduser(raw)) if raw.startswith("~") else (Path(raw) if raw.startswith("/") else path.parent / raw)
        if p.is_file():
            res.append(p.resolve())
    return res


def import_tree(root):
    seen, order = set(), []

    def walk(p, depth, via):
        rp = p.resolve()
        if rp in seen:
            return
        seen.add(rp)
        order.append((rp, depth, via))
        if depth < 5:
            for q in imports_of(rp):
                walk(q, depth + 1, rp)

    walk(root, 0, None)
    return order


def rule_files(base):
    d = base / "rules"
    return sorted(d.rglob("*.md")) if d.is_dir() else []


def check_load(repo, user=False):
    base = repo if user else repo / ".claude"
    roots = [repo / "CLAUDE.md"] if user else [repo / "CLAUDE.md", repo / ".claude" / "CLAUDE.md", repo / "CLAUDE.local.md"]
    goal = C.USER_CLAUDE_GOAL if user else C.PROJECT_CLAUDE_GOAL
    loaded = []
    if not user:
        for anc in list(repo.parents)[:-1]:
            for name in ("CLAUDE.md", "CLAUDE.local.md"):
                if (anc / name).is_file():
                    loaded.append((anc / name, 0, None))
                    C.add(1, "정보", "LOAD-ANCESTOR", anc / name, "상위 디렉터리 CLAUDE.md 도 함께 로드된다.")
    for r in roots:
        if r.is_file():
            loaded += import_tree(r)
    for rp, depth, via in loaded:
        if via is not None:
            C.add(1, "경고", "LOAD-IMPORT", C.rel(via, repo),
                f"@{C.rel(rp, repo)} 를 import 한다 ({C.stats(rp)['bytes']:,} B). @import 는 비용을 줄이지 않는다.",
                "references/load-and-rules.md#1-상시-로드량")
            if depth > 4:
                C.add(1, "경고", "LOAD-HOPS", C.rel(rp, repo), "import 가 4홉을 넘는다. 넘친 쪽은 로드되지 않는다.")
    for rf in rule_files(base):
        fm, err = C.parse_frontmatter(C.read(rf) or "")
        if fm is not None and not fm.get("paths"):
            loaded.append((rf.resolve(), 0, "rules"))
    total = {"lines": 0, "bytes": 0, "chars": 0}
    rows = []
    for rp, depth, via in loaded:
        s = C.stats(rp)
        for k in total:
            total[k] += s[k]
        rows.append({"file": C.rel(rp, repo), **s, "via": "rules(paths 없음)" if via == "rules" else ("import" if via else "root")})
        if s["chars"] > C.CHAR_LIMIT:
            C.add(1, "오류", "LOAD-CHARS", C.rel(rp, repo), f"{s['chars']:,}자. 200K 창 기준 40,000자를 넘으면 뒷부분이 잘린다.")
        if s["lines"] >= C.OFFICIAL_LINES:
            C.add(1, "경고", "LOAD-OVER200", C.rel(rp, repo), f"{s['lines']}줄. 공식 권장은 파일당 200줄 미만.")
    for r in roots[:1]:
        if r.is_file():
            n = C.stats(r)["lines"]
            if n > goal:
                C.add(1, "경고", "LOAD-GOAL", C.rel(r, repo), f"{n}줄. 우리 목표는 {goal}줄 이하.",
                    "references/load-and-rules.md#1-상시-로드량")
    if total["bytes"] > C.TOTAL_BYTES_WARN:
        C.add(1, "경고", "LOAD-TOTAL", repo, f"상시 로드 합계 {total['bytes']:,} B / {total['lines']}줄 / {total['chars']:,}자.")
    for rp, _, _ in loaded:
        if rp.name in ("todos.md", "TODO.md", "ROADMAP.md"):
            t = C.read(rp) or ""
            strike = len(re.findall(r"^\s*[-*].*~~.+~~", t, re.M))
            m = re.search(r"^#+\s*(된 것|완료|Done|끝난)", t, re.M)
            done_bytes = len(t[m.start():].encode()) if m else 0
            if strike or done_bytes:
                C.add(1, "경고", "LOAD-TODOS-DONE", C.rel(rp, repo),
                    f"상시 로드되는 할 일 문서에 끝난 항목이 있다(취소선 {strike}줄, 끝난 절 {done_bytes:,} B). 처리 방식은 D-07 미결.",
                    "references/staleness-and-kb.md#d-07")
    return {"files": rows, "total": total}


# ---------------------------------------------------------- 2 rules
def norm_line(s):
    s = re.sub(r"<!--.*?-->", "", s)
    s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)
    s = re.sub(r"[`*_>#]|^\s*(?:[-+]|\d+\.)\s+", "", s)
    s = re.sub(r"\s*—\s*\"[^\"]*\"\s*$", "", s)  # 꼬리 근거 표기 제거
    return re.sub(r"\s+", " ", s).strip()


def check_rules(repo, files, user=False):
    base = repo if user else repo / ".claude"
    rfs = rule_files(base)
    conv = [p for p in (base / "conventions.md", repo / "CONVENTIONS.md") if p.is_file()]
    conv_lines = []
    for c in conv:
        for i, line in enumerate((C.read(c) or "").split("\n"), 1):
            n = norm_line(line)
            if len(n) >= 25:
                conv_lines.append((c, i, n))
    summary = []
    for rf in rfs:
        text = C.read(rf) or ""
        fm, err = C.parse_frontmatter(text)
        r = C.rel(rf, repo)
        if fm is None:
            C.add(2, "오류", "RULE-PARSE", r, f"frontmatter 파싱 실패: {err}")
            continue
        paths = fm.get("paths")
        if isinstance(paths, str):
            paths = [p.strip() for p in paths.split(",") if p.strip()]
        st = C.stats(rf)
        summary.append({"file": r, "paths": paths or [], **st})
        if not paths:
            C.add(2, "경고", "RULE-NOPATHS", r, f"paths 가 없어 매 세션 로드된다 ({st['bytes']:,} B).",
                "references/load-and-rules.md#2-rules-구성")
        elif not user:
            for g in paths:
                if C.glob_hits(g, files) == 0:
                    C.add(2, "경고", "RULE-DEADGLOB", r, f"paths '{g}' 에 맞는 파일이 없다. 이 규칙은 로드될 일이 없다.")
        if st["bytes"] > 4500:
            C.add(2, "정보", "RULE-BIG", r, f"rule 하나가 {st['bytes']:,} B. 해당 파일을 읽을 때마다 실린다.")
        if conv_lines:
            dups = []
            for i, line in enumerate(text.split("\n"), 1):
                n = norm_line(line)
                if len(n) < 25:
                    continue
                best = None
                for c, j, cn in conv_lines:
                    sm = difflib.SequenceMatcher(None, n, cn, autojunk=False)
                    if sm.real_quick_ratio() < 0.6 or sm.quick_ratio() < 0.6:
                        continue
                    ratio = sm.ratio()
                    if ratio >= 0.6 and (best is None or ratio > best[0]):
                        best = (ratio, c, j)
                if best:
                    dups.append((i, best))
            if dups:
                ex = ", ".join(f"{i}↔{C.rel(c, repo)}:{j}({ratio:.2f})" for i, (ratio, c, j) in dups[:4])
                C.add(2, "경고", "RULE-DUP", r,
                    f"conventions 와 비슷한 줄 {len(dups)}개 (예: {ex}). 정본은 rules, conventions 는 '왜'만.",
                    "references/load-and-rules.md#rules-와-conventions-중복")
    return summary


# ----------------------------------------------------------- 3 스킬
LINK_RX = re.compile(r"\]\(([^)#\s]+\.md)(?:#[^)]*)?\)|`([\w./\-]+\.md)`|(?<![\w/])((?:references|refs|docs)/[\w./\-]+\.md)")


def md_links(p, skill_dir):
    out = set()
    for m in LINK_RX.finditer(C.read(p) or ""):
        s = next(g for g in m.groups() if g)
        for cand in (p.parent / s, skill_dir / s):
            try:
                c = cand.resolve()
            except OSError:
                continue
            if c.is_file() and C.inside(c, skill_dir.resolve()) and c != p.resolve():
                out.add(c)
                break
    return out


def has_toc(text):
    head = text.split("\n")[:40]
    if any(re.match(r"^#+\s*(목차|차례|contents|table of contents|toc)\b", l.strip(), re.I) for l in head):
        return True
    return sum(1 for l in head if re.search(r"\]\(#", l)) >= 3


def skill_dirs(repo, user=False):
    base = (repo / "skills") if user else (repo / ".claude" / "skills")
    return sorted(p.parent for p in base.glob("*/SKILL.md")) if base.is_dir() else []


def check_skill(sd, repo):
    sk = sd / "SKILL.md"
    r = C.rel(sk, repo)
    text = C.read(sk) or ""
    fm, err = C.parse_frontmatter(text)
    info = {"skill": sd.name, "lines": C.stats(sk)["lines"]}
    if fm is None or not fm:
        C.add(3, "오류", "SKILL-PARSE", r, f"frontmatter 파싱 실패: {err or 'frontmatter 없음'}")
        return info
    name = fm.get("name", sd.name)
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", str(name)):
        C.add(3, "오류", "SKILL-NAME", r, f"name '{name}' 은 소문자·숫자·하이픈 64자 이내여야 한다.")
    if re.search(r"claude|anthropic", str(name)):
        C.add(3, "오류", "SKILL-NAME", r, f"name '{name}' 에 예약어(claude/anthropic)가 들어 있다.")
    if name != sd.name:
        C.add(3, "정보", "SKILL-NAME", r, f"name '{name}' 이 디렉터리 이름 '{sd.name}' 과 다르다.")
    desc = str(fm.get("description", "")) + str(fm.get("when_to_use", ""))
    info["desc_chars"] = len(desc)
    if not desc:
        C.add(3, "오류", "SKILL-DESC", r, "description 이 없다.")
    elif len(desc) > C.DESC_LIMIT:
        C.add(3, "오류", "SKILL-DESC", r, f"description+when_to_use {len(desc)}자. {C.DESC_LIMIT}자에서 잘린다.")
    for k in fm:
        if k not in C.SKILL_KEYS:
            C.add(3, "정보", "SKILL-KEY", r, f"알려지지 않은 frontmatter 키 '{k}'.")
    if info["lines"] > C.SKILL_MAX_LINES:
        C.add(3, "경고", "SKILL-LINES", r, f"SKILL.md {info['lines']}줄. 권장 500줄 이하 — references 로 나눈다.",
            "references/skills.md#3-스킬-상태")
    direct = md_links(sk, sd)
    mds = [p.resolve() for p in sd.rglob("*.md") if p.name != "SKILL.md"]
    for p in mds:
        depth = len(p.relative_to(sd.resolve()).parts)
        if depth > 2 and p not in direct:  # 하위 폴더라도 SKILL.md 가 바로 가리키면 1단계다(예: references/toolkits/)
            C.add(3, "경고", "SKILL-NEST", C.rel(p, repo), "references 가 하위 디렉터리로 중첩됐고 SKILL.md 가 바로 가리키지 않는다.")
    for p in direct:
        for q in md_links(p, sd):
            if q not in direct and q.name != "SKILL.md":
                C.add(3, "경고", "SKILL-NEST", C.rel(p, repo),
                    f"{q.name} 를 이 파일에서만 가리킨다(2단계). SKILL.md 에서 바로 가리키게 한다.")
    for p in mds:
        t = C.read(p) or ""
        n = t.count("\n")
        if n > C.REF_TOC_LINES and not has_toc(t):
            C.add(3, "경고", "SKILL-TOC", C.rel(p, repo), f"{n}줄인데 맨 위에 목차가 없다.")
        if p not in direct and not any(p in md_links(d, sd) for d in direct):
            C.add(3, "정보", "SKILL-ORPHAN", C.rel(p, repo), "SKILL.md 에서 닿지 않는 문서다.")
    dmi = fm.get("disable-model-invocation") in (True, "true")
    info["user_only"] = dmi
    if not dmi:
        body = text + "".join(C.read(p) or "" for p in sd.rglob("*") if p.is_file() and p.suffix in (".sh", ".py"))
        hits = sorted(set(m.group(0) for m in C.SIDE_EFFECT.finditer(body)))
        if hits:
            C.add(3, "경고", "SKILL-SIDEFX", r,
                f"부작용 낌새({', '.join(hits[:6])})가 있는데 disable-model-invocation 이 없다. 모델이 스스로 부를 수 있다.",
                "references/skills.md#부작용-판단")
    return info


def check_skills(repo, user=False):
    return [check_skill(sd, repo) for sd in skill_dirs(repo, user)]
