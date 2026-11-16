"""모델용 문서(CLAUDE.md, SKILL.md, agents, rules, skills/**/*.md) 검사: 문서 종류, 검사할 줄, 이력 표지.

conventions-check.py 가 쓰고(Edit, Write, Bash 경로), scripts/conventions-scan.py 는 그 모듈을 거쳐 쓴다. 표준 라이브러리만 쓴다.
"""
import os
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


# ---------- 모델용 문서의 꼴: 스킬 description, 본문 언어, 원장 id 의 경로 ----------
# 추가한 줄만 본다. 남은 문제 보고(record_leftovers)와 conventions-scan 에는 넣지 않는다: 한국어로 쓴 기존 문서 전체가 걸린다.
HANGUL_WORD = re.compile(r"[가-힣]{2,}")
LATIN_WORD = re.compile(r"[A-Za-z]{2,}")
QUOTED = re.compile("`[^`]*`|\"[^\"]*\"|\u201c[^\u201d]*\u201d")
DESC_WHEN = re.compile(r"\b(?:when|whenever|before|after|while)\b|\buse (?:it |this(?: skill)? )?(?:for|on|to|in|with)\b|\breach for\b", re.I)
DESC_PERSON = re.compile(r"(?<![\w'])(?:I (?:can|will|help|am)|I'll|I'm|you can|we can|we will|let me)\b", re.I)
DOC_KO_SHARE = 0.1  # 기존 줄 중 한국어 줄이 이보다 많으면(3줄 이상) 그 문서의 언어를 따른다
MD_PATH = re.compile(r"[^\s`'\"()<>\[\]]+\.md\b")
DOC_HINT = {"history marker": "keep the current fact or instruction and move dates, ids, rounds, who decided and change narration to "
                              "the commit message or an existing ledger",
            "language mismatch": "write it in English, since a model reads this file; wording shown to the user as is can stay "
                                 "Korean inside quotes",
            "ledger id path": "the .md file named on the line does not ship with this document; name a ledger file inside %s, "
                              "or drop the id"}


def skill_description(text):
    """SKILL.md frontmatter 의 (첫 줄, 끝 줄(0 기반), description 값, disable-model-invocation 여부). 없으면 None."""
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return None
    desc, dmi, i = None, False, 1
    while i < len(lines) and lines[i].strip() != "---":
        dmi = dmi or bool(re.match(r"disable-model-invocation:\s*true\b", lines[i]))
        m = re.match(r"description:[ \t]*(.*)$", lines[i])
        if not m:
            i += 1
            continue
        rest, j = m.group(1).strip(), i + 1
        while j < len(lines) and lines[j].strip() != "---" and (lines[j][:1] in " \t" or not lines[j].strip()):
            j += 1  # 접힌 값(>-, |)과 들여쓴 이어지는 줄
        val = " ".join(x.strip() for x in ([] if rest[:1] in ">|" else [rest]) + lines[i + 1:j] if x.strip())
        if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
            val = val[1:-1]
        desc, i = (i, j - 1, val), j
    return desc + (dmi,) if desc else None


def description_problems(val):
    """스킬 description 이 꼴(무엇과 언제, 영어, 3인칭, 한국어 계기는 끝에)을 벗어난 점들."""
    def korean(x):
        s = QUOTED.sub(" ", x)
        return x.lstrip().startswith("트리거") or len(HANGUL_WORD.findall(s)) > len(LATIN_WORD.findall(s))

    parts = re.split(r"(?<=[.!?])\s+", val.strip())
    while parts and korean(parts[-1]):
        parts.pop()  # 끝의 한국어 계기 문구
    body = " ".join(parts)
    bare = QUOTED.sub(" ", body)
    out = []
    if not body or len(HANGUL_WORD.findall(bare)) >= 3:
        out.append("not English outside the trailing Korean trigger phrases")
    if not DESC_WHEN.search(body):
        out.append("no when-clause")
    if DESC_PERSON.search(bare):
        out.append("first or second person")
    return out


def korean_line(line):
    s = QUOTED.sub(" ", URL.sub(" ", line))
    h = len(HANGUL_WORD.findall(s))
    return h >= 3 and h >= len(LATIN_WORD.findall(s))


def ship_root(path, root):
    """문서와 함께 배포되는 범위: 가장 가까운 플러그인 폴더(.claude-plugin 이 있는 곳), 없으면 저장소."""
    d = os.path.dirname(os.path.abspath(path))
    while d.startswith(root) and d != root:
        if os.path.isdir(os.path.join(d, ".claude-plugin")):
            return d
        d = os.path.dirname(d)
    return root


def doc_shape(text, added, path, rel, pub):
    """모델용 문서의 추가한 줄: 스킬 description 꼴, 영어가 아닌 줄(이미 한국어인 문서는 빼고), 함께 배포되지 않는 원장 경로.
    ([(줄 번호(1 기반), 범주)], {범주: 고치는 법}) 를 돌려준다."""
    out, det = [], {}
    if os.path.basename(rel) == "SKILL.md":
        d = skill_description(text)
        if d and not d[3] and any(k in added for k in range(d[0], d[1] + 1)):
            probs = description_problems(d[2])
            if probs:
                out.append((d[0] + 1, "skill description"))
                det["skill description"] = ("; ".join(probs) + ". Write what it does, then when to use it (\"Use when ...\"), in English "
                                            "and third person, with any Korean trigger phrases at the end; a skill with "
                                            "`disable-model-invocation: true` takes a one-line menu description instead")
    rows = doc_lines(text)
    old = [korean_line(l) for i, l in rows if i not in added and l.strip()]
    if not (sum(old) >= 3 and sum(old) > DOC_KO_SHARE * len(old)):
        out += [(i + 1, "language mismatch") for i, l in rows if i in added and korean_line(l)]
    if doc_class(rel) == "entry":
        root = os.path.abspath(path)
        for _ in Path(rel).parts:
            root = os.path.dirname(root)
        ship = ship_root(path, root)
        ledger = re.compile(DOC_PATTERNS["ledger"])
        for i, line in rows:
            if i not in added or DOC_STATUS.match(line):
                continue
            s = URL.sub(" ", INLINE_CODE.sub(" ", line))
            for p in pub:
                s = p.sub(" ", s)
            if not (ledger.search(PATH_TOKEN.sub(" ", s)) and HAS_MD_PATH.search(s)):
                continue  # 경로가 없는 원장 id 는 history marker 가 알린다
            if not any(shipped(m.split("#")[0], path, ship, root) for m in MD_PATH.findall(line)):
                out.append((i + 1, "ledger id path"))
                det["ledger id path"] = DOC_HINT["ledger id path"] % (os.path.relpath(ship, root) if ship != root else "this repo")
    return out, det


def shipped(p, path, ship, root):
    """경로 p 가 문서 폴더, 배포 범위, 저장소 중 하나에서 배포 범위 안의 있는 파일로 풀리나."""
    for base in (os.path.dirname(os.path.abspath(path)), ship, root):
        c = os.path.normpath(os.path.join(base, p))
        if (c == ship or c.startswith(ship + os.sep)) and os.path.isfile(c):
            return True
    return False
