"""모델용 문서(CLAUDE.md, SKILL.md, agents, rules, skills/**/*.md) 검사: 문서 종류, 검사할 줄, 이력 표지.

conventions-check.py 가 쓰고(Edit, Write, Bash 경로), scripts/conventions-scan.py 는 그 모듈을 거쳐 쓴다. 표준 라이브러리만 쓴다.
"""
import re
from pathlib import Path

# 모델용 문서 패턴. 날짜, round, 결정 문구는 conventions-check.py 의 PATTERNS 와 설정 덮어쓰기를 공유한다.
DOC_PATTERNS = {
    "decision": r"사용자\s*(?:결정|합의)|\bper (?:the )?user\b|\bas (?:the user )?(?:discussed|decided|agreed)\b|\bthe user decided\b|사용자\s*20\d\d",
    "path": r"(?<![\w-])(?:audit|session|handoff)/|\.claude/(?:plan|base|research|audit|handoff|archive)/",
    "ref_path": r"(?<![\w-])audit/\d+",
    "tag": r"\[(?:실측|측정|추정|추론|measured|estimated?|inferred)[^\]]*\]",
    "narration": r"\b(?:previously|recently)\b|\bas of\b(?!\s+(?:v?\d|luau|version))|현재 기준|지난\s?(?:주|번)|요즘|사실 정정|\bfact fix\b",
    "banner": r"사실 정정|\bfact fix\b|정정\s*:|\bcorrection\s*:",
    "ledger": r"\b[A-Z]{1,2}-\d{2,4}\b",
}
DOC_ENTRY = ("date", "path", "round", "decision", "tag", "narration", "ledger")
DOC_REFERENCE = ("decision", "round", "ref_path", "tag", "banner")
DOC_STATUS = re.compile(r"^\s*(?:[-*>]\s*)?\**status\**\s*:", re.I)
INLINE_CODE = re.compile(r"`[^`]*`")
URL = re.compile(r"https?://\S+")
PATH_TOKEN = re.compile(r"\S*/\S*|\S+\.\w{1,5}\b")
HAS_MD_PATH = re.compile(r"\S+\.md\b")


def doc_class(rel):
    """모델용 문서면 "entry" 나 "reference", 아니면 None."""
    parts = Path(rel).parts
    name = parts[-1]
    if not name.endswith(".md"):
        return None
    if "skills" in parts[:-1]:
        after = parts[parts.index("skills") + 1:-1]
        return "reference" if "references" in after else "entry"
    if name in ("CLAUDE.md", "SKILL.md") or (len(parts) > 1 and parts[-2] == "agents"):
        return "entry"
    if ".claude" in parts[:-1] and "rules" in parts[:-1]:
        return "entry"
    return None


def doc_lines(text):
    """(줄 번호 0 기반, 검사할 줄) 쌍. frontmatter 와 코드 펜스 안은 뺀다."""
    out, fence, front = [], None, False
    for idx, line in enumerate(text.split("\n")):
        if idx == 0 and line.strip() == "---":
            front = True
            continue
        if front:
            front = line.strip() != "---"
            continue
        m = re.match(r"^\s*(`{3,}|~{3,})", line)
        if m:
            if fence is None:
                fence = m.group(1)[0]
            elif m.group(1)[0] == fence:
                fence = None
            continue
        if fence is None:
            out.append((idx, line))
    return out


def doc_check(text, added, rel, cfg, pats, pub):
    """모델용 문서에서 추가된 줄의 이력 표지. [(줄 번호(1 기반), 범주)]."""
    cls = doc_class(rel)
    if not cls:
        return []
    names = DOC_ENTRY if cls == "entry" else DOC_REFERENCE
    rx = {}
    for k in names:
        if k in ("date", "round", "decision"):
            if k == "decision" and k in pats:
                rx[k] = re.compile(DOC_PATTERNS[k], re.I)
            elif k in pats:
                rx[k] = pats[k]
        else:
            rx[k] = re.compile(DOC_PATTERNS[k], re.I if k in ("narration", "banner", "tag") else 0)
    out = []
    for idx, line in doc_lines(text):
        if idx not in added or DOC_STATUS.match(line):
            continue
        s = URL.sub(" ", INLINE_CODE.sub(" ", line))
        for p in pub:
            s = p.sub(" ", s)
        bare = PATH_TOKEN.sub(" ", s)  # 경로, 파일명 속 날짜나 id 는 이력이 아니다
        hit = False
        for k, r in rx.items():
            if k in ("path", "ref_path"):
                hit = hit or bool(r.search(s))
            elif k == "ledger":
                hit = hit or (bool(r.search(bare)) and not HAS_MD_PATH.search(s))
            else:
                hit = hit or bool(r.search(bare if k == "date" else s))
        if hit:
            out.append((idx + 1, "history marker"))
    return out
