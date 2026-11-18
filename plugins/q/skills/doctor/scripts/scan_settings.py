"""harness-doctor 항목 6(복제본 표류)·7(설정) 검사. 읽기 전용.

scan.py 가 경로로 적재하고 C 에 자기 자신을 걸어 둔다. 공용 함수·상수·add 는 C.<이름> 으로 부른다(호출 시점에 찾는다).
"""
import json
import os
import re
from pathlib import Path

try:
    import grp
    import pwd
except ImportError:  # Windows: 위임 드라이버가 돌지 않는 곳이라 uid 대역 검사도 계정을 보지 않는다
    grp = pwd = None

C = None


# ------------------------------------------------------ 6 복제본
def load_json(p):
    try:
        return json.loads(Path(p).read_text()), None
    except FileNotFoundError:
        return None, None
    except (OSError, ValueError) as e:
        return None, str(e)


def hook_cmds(settings):
    out = []
    for ev, groups in ((settings or {}).get("hooks") or {}).items():
        for g in groups or []:
            for h in g.get("hooks", []):
                if h.get("type") == "command":
                    out.append((ev, g.get("matcher", ""), h.get("command", "")))
    return out


def script_of(cmd):
    cmd = cmd.replace('"', "").replace("'", "")
    m = re.findall(r"[\w./$\"{}~\-]+\.(?:py|sh|js|ts)\b", cmd)
    return m[-1].strip('"') if m else None


def script_path(sc, repo=None):
    """훅 명령의 스크립트 경로를 푼다: $CLAUDE_PROJECT_DIR, $HOME 등 환경 변수, ~."""
    if repo is not None:
        sc = sc.replace("$CLAUDE_PROJECT_DIR", str(repo)).replace("${CLAUDE_PROJECT_DIR}", str(repo))
    return os.path.expanduser(os.path.expandvars(sc))


def user_settings():
    res = []
    for p in (C.USER_HOME / "settings.json", C.CANON_HOME / "settings.json"):
        s, _ = load_json(p)
        if s:
            res.append((p, s))
    return res


def common_dir(path):
    out = C.run(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"], cwd=path)
    return out.strip() if out else None


UID_RANGE = re.compile(r"^\s*(\d+)\s*-\s*(\d+)\s*$")
# 위임 드라이버(qwreey-delegate 의 delegate_workspace.py MAX_UID_RANGE)가 받는 대역의 최대 크기. 다른 플러그인이라
# import 하지 않고 tests/test-delegate-uids.py 가 두 값을 맞춰 본다.
MAX_UID_RANGE = 4096
MAX_LISTED_UIDS = 10


def account_of(uid):
    """uid 가 실제 계정 번호면 'user' 나 'group', 아니면 ''. 위임 작업은 그 번호를 uid 와 gid 로 함께 쓴다."""
    if pwd is None:
        return ""
    try:
        pwd.getpwuid(uid)
        return "user"
    except KeyError:
        pass

    try:
        grp.getgrgid(uid)
        return "group"
    except KeyError:
        return ""


def delegate_uid_range():
    """(첫 uid, 끝 uid) 또는 잘못된 값이면 None. HARNESS_DELEGATE_UIDS(사용자 층과 qwreey-delegate 옵션)."""
    m = UID_RANGE.match(C.ENV.get("HARNESS_DELEGATE_UIDS") or "")
    if not m:
        return None
    first, last = int(m.group(1)), int(m.group(2))
    return (first, last) if 0 < first <= last and last - first + 1 <= MAX_UID_RANGE else None


def check_delegate_uids(repo, projects):
    """위임 uid 대역 검사(DRIFT-UID): 대역이 잘못됐거나 비었는지, 실제 계정과 겹치는지, 옛 저장소 사본이 대역 안 uid 를 쓰는지."""
    if not (C.DOCTOR_ROOT or C.installed_plugin("qwreey-delegate")):
        return
    value = C.ENV.get("HARNESS_DELEGATE_UIDS") or ""
    rng = delegate_uid_range()
    if rng is None:
        C.add(6, "경고", "DRIFT-UID", "HARNESS_DELEGATE_UIDS",
              f"위임 uid 대역 {value!r} 이 잘못됐다(예: 61000-61015, 0 보다 크고 {MAX_UID_RANGE}개 이하). 위임 실행이 모두 거절된다.",
              "references/drift-and-settings.md#위임-uid-대역")
        return

    # 실제 계정과 겹치는 uid 는 드라이버가 건너뛴다. 모두 겹치면 위임이 돌 uid 가 없다
    first, last = rng
    taken = [(u, account_of(u)) for u in range(first, last + 1)]
    taken = [(u, kind) for u, kind in taken if kind]
    if taken:
        shown = ", ".join(f"{u}({kind})" for u, kind in taken[:MAX_LISTED_UIDS])
        more = f" 외 {len(taken) - MAX_LISTED_UIDS}개" if len(taken) > MAX_LISTED_UIDS else ""
        left = last - first + 1 - len(taken)
        C.add(6, "경고", "DRIFT-UID", "HARNESS_DELEGATE_UIDS",
              f"위임 uid 대역 {first}-{last} 에 실제 계정 번호가 있다: {shown}{more}. "
              + (f"드라이버가 건너뛰어 동시에 {left}개까지 돈다." if left else "남는 uid 가 없어 위임 실행이 모두 거절된다."),
              "references/drift-and-settings.md#위임-uid-대역")

    # 옛 저장소 사본(agy-delegate.sh)이 고정 uid 를 쓰면 대역의 위임과 같은 uid 로 돈다
    for sh in projects.glob("*/.claude/tools/agy-delegate.sh"):
        m = re.search(r"AGY_UID[:=]-?\$?\{?[\w:-]*?(\d{4,6})", C.read(sh) or "")
        if m and first <= int(m.group(1)) <= last and sh.parts[-4] == repo.name:
            C.add(6, "경고", "DRIFT-UID", C.rel(sh, repo),
                  f"옛 위임 사본이 uid {m.group(1)} 를 쓴다. 위임 uid 대역 {first}-{last} 안이라 대역의 위임과 같은 uid 로 돈다(격리 깨짐).",
                  "references/drift-and-settings.md#위임-uid-대역")


def check_drift(repo, files, projects):
    # 언어 고유 사본(예: luau 의 globalTypes.d.luau)은 툴킷이 본다(DRIFT-TYPEDEFS).
    canon_guard = C.DOCTOR_ROOT / "plugins" / "qwreey-proc-guard" / "hooks" / "heavy-proc-guard.py" if C.DOCTOR_ROOT else Path("/nonexistent")
    for f in files:
        name = os.path.basename(f)
        if name == "heavy-proc-guard.py" and canon_guard.is_file():
            same = C.md5(repo / f) == C.md5(canon_guard)
            C.add(6, "정보" if same else "경고", "DRIFT-HOOK", f,
                "qwreey-proc-guard 플러그인의 정본과 같다." if same else "qwreey-proc-guard 플러그인의 정본(plugins/qwreey-proc-guard/hooks)과 다르다. 플러그인으로 일원화 대상.")
        if name == "agy-delegate.sh" or f.endswith("skills/delegate-agy/SKILL.md"):
            C.add(6, "정보", "DRIFT-DELEGATE", f, "agy 위임 사본. 통합안 claude-doctor/.claude/scopes/plugins/qwreey-delegate/research/drafts/delegate (P4) 로 대체 예정.",
                "references/drift-and-settings.md#위임-사본")
    check_delegate_uids(repo, projects)
    # 사용자 레벨과 같은 훅을 프로젝트가 또 등록
    ukeys = {}
    for p, s in user_settings():
        label = "실제 ~/.claude" if p.parent == C.USER_HOME else "정본 home/.claude"
        for ev, mt, cmd in hook_cmds(s):
            sc = script_of(cmd)
            if sc:
                ukeys.setdefault((ev, os.path.basename(sc)), []).append(label)
    for sp in (repo / ".claude" / "settings.json", repo / ".claude" / "settings.local.json"):
        s, _ = load_json(sp)
        for ev, mt, cmd in hook_cmds(s):
            sc = script_of(cmd)
            if sc and (ev, os.path.basename(sc)) in ukeys:
                C.add(6, "경고", "DRIFT-HOOKDUP", C.rel(sp, repo),
                    f"{ev} 훅 {os.path.basename(sc)} 를 사용자 레벨({', '.join(ukeys[(ev, os.path.basename(sc))])})도 등록한다. 두 번 돈다.",
                    "references/drift-and-settings.md#훅-중복")
    # 같은 이름 스킬 사본
    mycommon = common_dir(repo)
    for sd in C.skill_dirs(repo):
        mine_md5 = C.md5(sd / "SKILL.md")
        others = list(projects.glob(f"*/.claude/skills/{sd.name}/SKILL.md")) + \
            list(projects.glob(f"*/docs/skills/{sd.name}/SKILL.md")) + list(projects.glob(f"*/skills/{sd.name}/SKILL.md")) + \
            [C.USER_HOME / "skills" / sd.name / "SKILL.md"]
        for o in others:
            if not o.is_file() or C.inside(o.resolve(), repo.resolve()) or "worktrees" in o.parts:
                continue
            if mycommon and common_dir(o.parent) == mycommon:
                continue
            if C.md5(o) != mine_md5:
                C.add(6, "경고", "DRIFT-SKILLCOPY", C.rel(sd / "SKILL.md", repo),
                    f"같은 이름 스킬 {o} 와 내용이 다르다(사본 표류?). 어느 쪽이 정본인지 확인.")


# ------------------------------------------------------- 7 설정
PUSH_NOTE = {
    "normal": "이 환경은 에이전트 push 가 정상 흐름이다(harness.env HARNESS_AGENT_PUSH=normal). 걷을지는 사용자 판단, HUMAN_TODO.",
    "deny": "이 환경은 에이전트 push 를 막는 정책이다(HARNESS_AGENT_PUSH=deny). 그대로 둔다.",
}


def check_settings(repo, files):
    nested = not C.git_root(repo) and C.run(["git", "rev-parse", "--show-toplevel"], cwd=repo)
    inrepo = None if nested else C.run(["git", "rev-parse", "--is-inside-work-tree"], cwd=repo)
    for sp in (repo / ".claude" / "settings.json", repo / ".claude" / "settings.local.json"):
        s, err = load_json(sp)
        r = C.rel(sp, repo)
        if err:
            C.add(7, "오류", "SET-JSON", r, f"JSON 파싱 실패: {err}")
            continue
        if s is None:
            continue
        for ev, mt, cmd in hook_cmds(s):
            sc = script_of(cmd)
            if sc:
                path = script_path(sc, repo)
                if not os.path.isabs(path):
                    path = str(repo / path)
                if not os.path.isfile(path):
                    C.add(7, "오류", "SET-HOOKPATH", r, f"{ev} 훅 스크립트가 없다: {sc}")
        perm = s.get("permissions") or {}
        for d in perm.get("deny") or []:
            if "git push" in d:
                note = PUSH_NOTE.get(C.ENV.get("HARNESS_AGENT_PUSH", ""), "에이전트 push 정책은 harness.env HARNESS_AGENT_PUSH 로 정한다.")
                C.add(7, "정보", "SET-PUSHDENY", r, f"deny '{d}'. {note}", "references/drift-and-settings.md#7-설정")
        for a in perm.get("allow") or []:
            if C.BROAD_ALLOW.match(a.strip()):
                C.add(7, "경고", "SET-BROADALLOW", r, f"allow '{a}' 는 임의 변경·실행을 연다.")
        if sp.name == "settings.local.json" and inrepo:
            if C.run(["git", "check-ignore", "-q", str(sp)], cwd=repo) is None:
                C.add(7, "경고", "SET-LOCALIGNORE", r, "settings.local.json 이 무시되지 않는다(개인 설정이 커밋될 수 있음).")
    hl = repo / ".claude" / "harness.local.env"
    if inrepo and hl.is_file() and C.run(["git", "check-ignore", "-q", str(hl)], cwd=repo) is None:
        C.add(7, "경고", "SET-LOCALIGNORE", C.rel(hl, repo), "harness.local.env 가 무시되지 않는다(개인 harness 설정이 커밋될 수 있음).")
    if nested:  # 반입 사본(intake/<이름>/) 등: 바깥 저장소의 git 상태는 이 대상의 것이 아니다
        C.add(7, "정보", "SET-NOGIT", repo, f"자기 git 저장소가 아니다(바깥 저장소 {nested.strip()} 안의 하위 디렉터리). "
            "반입 사본이면 정상이다. git 기반 검사(7의 나머지, 9 worktree)는 건너뛴다.", "references/drift-and-settings.md#7-설정")
        return
    if not inrepo:
        C.add(7, "경고", "SET-NOGIT", repo, "git 저장소가 아니다.")
        return
    ign = C.run(["git", "check-ignore", "-v", ".claude/worktrees/x"], cwd=repo)
    if ign is None:
        C.add(7, "경고", "SET-WTIGNORE", ".gitignore", "`.claude/worktrees/` 가 무시되지 않는다. worktree 가 생기면 git status 가 범람한다.",
            "references/drift-and-settings.md#7-설정")
    elif "info/exclude" in ign.split(":")[0] or not ign.split(":")[0].endswith(".gitignore"):
        C.add(7, "정보", "SET-WTIGNORE", ign.split(":")[0],
            "`.claude/worktrees/` 를 이 기기의 로컬 exclude 로만 무시한다. clone 에는 없다(.gitignore 한 줄 후보).")
    tracked = C.run(["git", "ls-files", "--", ".claude", "CLAUDE.md"], cwd=repo) or ""
    if not tracked.strip() and ((repo / ".claude").is_dir() or (repo / "CLAUDE.md").is_file()):
        C.add(7, "오류", "SET-UNTRACKED", repo, "`.claude/` 와 CLAUDE.md 가 한 번도 커밋되지 않았다.")
    else:
        st = C.run(["git", "status", "--porcelain", "--untracked-files=all", "--", ".claude", "CLAUDE.md", "GEMINI.md", "AGENTS.md"],
                 cwd=repo, timeout=60) or ""
        unt = [l for l in st.split("\n") if l.startswith("??")]
        mod = [l for l in st.split("\n") if l and not l.startswith("??")]
        if unt or mod:
            C.add(7, "정보", "SET-DIRTY", repo, f"에이전트 문서 중 미추적 {len(unt)}개, 미커밋 변경 {len(mod)}개.")
