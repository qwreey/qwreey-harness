"""harness-doctor 항목 4(낡음·모순) 검사. 읽기 전용.

scan.py 가 경로로 적재하고 C 에 자기 자신을 걸어 둔다. 공용 함수·상수·add 는 C.<이름> 으로 부른다(호출 시점에 찾는다).
"""
import datetime as dt
import re

C = None


# ------------------------------------------------------ 4 낡음·모순
DATED_RX = re.compile(r"(20\d\d-\d\d-\d\d)[^\]\n*—]{0,6}?(?:기준|현재)|(?:as of|기준:?)\s*(20\d\d-\d\d-\d\d)")
SUPERSEDE_RX = re.compile(r"뒤집|폐기|철회|무효|전환 중|바뀌었|superseded|reverted|no longer")
FIRM_RX = re.compile(r"확정|정해진|예외 없음|반드시|decided|always")
QID_RX = re.compile(r"질문\s*([A-Z]{1,3}(?:\s*[·,/]\s*[A-Z]{1,3})*)")


# "AB 규칙은 뒤집혔다", "질문 AB 는 폐기" 꼴에서 뒤집힌 쪽 ID 만 뽑는다(새 결정 ID 는 빼려고 '규칙/결정' 을 요구)
GONE_ID_RX = re.compile(r"(?<![A-Za-z])([A-Z]{2,3})(?![A-Za-z])[^A-Z\n]{0,4}(?:규칙|결정|방침|rule)"
                        r"(?=[^\n]*(?:뒤집|폐기|철회|무효|superseded|reverted))|"
                        r"질문\s*([A-Z]{2,3})\s*(?:은|는|이|가)?\s*(?:뒤집|폐기|철회|무효)")


def gone_ids(line):
    return {a or b for a, b in GONE_ID_RX.findall(line)}


def qids(line):
    return {x.strip() for m in QID_RX.finditer(line) for x in re.split(r"[·,/]", m.group(1))}


def last_commit(repo, f):
    out = C.run(["git", "log", "-1", "--format=%cs", "--", str(f)], cwd=repo)
    return out.strip() if out else None


def state_docs(repo):
    names = ["CLAUDE.md", "GEMINI.md", "AGENTS.md", "ROADMAP.md", "HUMAN_TODO.md"]
    cands = [repo / n for n in names] + [repo / ".claude" / n for n in
                                          ("CLAUDE.md", "todos.md", "project-context.md", "ROADMAP.md", "conventions.md")]
    return [p for p in cands if p.is_file()]


def check_stale(repo, today):
    docs = state_docs(repo)
    basis = {}
    for p in docs:
        text = C.read(p) or ""
        clean, old = C.strip_code(text), []
        for i, line in enumerate(clean.split("\n"), 1):
            for m in DATED_RX.finditer(line):
                d = m.group(1) or m.group(2)
                try:
                    age = (today - dt.date.fromisoformat(d)).days
                except ValueError:
                    continue
                basis.setdefault(p, []).append(d)
                if age > C.STALE_DAYS:
                    old.append((i, d, age, line.strip()[:60]))
        if old:
            i, d, age, ex = max(old, key=lambda x: x[2])
            C.add(4, "경고", "STALE-DATED", C.rel(p, repo),
                f"날짜 기준 상태 서술 {len(old)}곳이 {C.STALE_DAYS}일을 넘었다(줄 {', '.join(str(o[0]) for o in old[:8])}). "
                f"가장 오래된 것 {d}({age}일): {ex}", "references/staleness-and-kb.md#4-낡음과-모순")
        tags = len(re.findall(r"\*\*\[20\d\d-\d\d-\d\d", text))
        if tags >= 10:
            C.add(4, "정보", "STALE-DATETAGS", C.rel(p, repo), f"날짜 신설 태그 '**[YYYY-MM-DD' {tags}개. 경위는 기록 문서로.")
    latest = {C.rel(p, repo): max(v) for p, v in basis.items()}
    if len(set(latest.values())) > 1:
        C.add(4, "정보", "STALE-MISMATCH", repo,
            "상태 문서마다 '기준' 날짜가 다르다: " + ", ".join(f"{k}={v}" for k, v in sorted(latest.items())))
    # 규약 문서 사이 모순: CLAUDE 쪽이 '뒤집혔다'고 한 질문 ID 를 GEMINI/AGENTS 가 '확정'으로 서술
    claude_side = [p for p in docs if p.name in ("CLAUDE.md", "conventions.md")] + C.rule_files(repo / ".claude")
    superseded = set()
    for p in claude_side:
        for line in C.strip_code(C.read(p) or "").split("\n"):
            superseded |= gone_ids(line)
    claude_md = repo / "CLAUDE.md"
    cdate = last_commit(repo, claude_md) if claude_md.is_file() else None
    for p in docs:
        if p.name not in ("GEMINI.md", "AGENTS.md"):
            continue
        section = ""
        for i, line in enumerate(C.strip_code(C.read(p) or "").split("\n"), 1):
            if line.startswith("#"):
                section = line
            ids = qids(line) & superseded
            if ids and (FIRM_RX.search(line) or FIRM_RX.search(section)) and not SUPERSEDE_RX.search(line + section):
                C.add(4, "경고", "STALE-SUPERSEDED", f"{C.rel(p, repo)}:{i}",
                    f"질문 {'·'.join(sorted(ids))} 을 확정처럼 적었는데 CLAUDE.md/conventions/rules 는 뒤집혔다고 한다.",
                    "references/staleness-and-kb.md#에이전트-문서-사이-모순")
        gdate = last_commit(repo, p)
        if cdate and gdate and gdate < cdate:
            C.add(4, "정보", "STALE-AGENTDOC-OLD", C.rel(p, repo),
                f"마지막 커밋 {gdate} 로 CLAUDE.md({cdate})보다 오래됐다. 규약이 따라왔는지 확인.")
