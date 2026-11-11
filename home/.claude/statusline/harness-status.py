#!/usr/bin/env python3
"""statusline: 프로젝트·브랜치, 모델·effort·컨텍스트 %, 한도(5h·7d·리셋) 또는 비용, 서브에이전트, away 상태를 한 줄로.

settings.json: "statusLine": {"type": "command", "command": "python3 $HOME/.claude/statusline/harness-status.py", "refreshInterval": 10}
- 읽기 전용. 잠금을 잡지 않고 원장(lib/subagent_ledger.py) 파일을 읽기만 한다. 실패해도 있는 것만 낸다.
- 어떤 스타일이든(off 포함) rate_limits 를 $TMPDIR/claude-subagent-slots/<sid>.limits.json 에 적는다. away 훅이 이 파일을 읽는다.
- 설정(harness.env 키, 환경 변수 > 저장소 <project>/.claude/harness.env > 사용자 ~/.claude/harness.env, 전부 HARNESS_STATUSLINE_ 접두):
  STYLE=plain(기본)|nerd|minimal|off, LINES=1(기본)|2, COST=always(기본, 구독 여부와 무관한 작업량 지표)|auto(구독자면 숨김)|never, WARN_PCT=70, HOT_PCT=90
- 폭이 좁으면(COLUMNS) 뒤 항목부터 통째로 뺀다. NO_COLOR 가 있으면 색을 쓰지 않는다.
- 비용은 cost.total_cost_usd(목록가 환산, 서브에이전트 포함)다. away 예산은 원장 기준이다.
예(plain): `claude-doctor (main*) · Opus high ctx 34% · limit 5h 20% wk 50% reset 2h10m · agents 2 (opus 1, sonnet 1) · AWAY $3.10/$15 slots 2`
"""
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HOME = Path(__file__).resolve().parent.parent
PREFIX = "HARNESS_STATUSLINE_"
DEFAULTS = {"STYLE": "plain", "LINES": "1", "COST": "always", "WARN_PCT": "70", "HOT_PCT": "90"}
STYLES = ("plain", "nerd", "minimal", "off")
GIT_TTL = 10.0  # 더러움 표시(git status)만 캐시한다. 브랜치는 .git/HEAD 를 직접 읽어서 싸다.

# Nerd Font 코드포인트(BMP 사설 영역, Font Awesome 계열). 폰트가 없으면 빈 네모로 보이므로 기본은 plain.
ICON = {"dir": "", "branch": "", "model": "", "ctx": "", "limit": "", "reset": "",
        "cost": "", "agents": "", "away": "", "effort": ""}


def load_mod(name):
    spec = importlib.util.spec_from_file_location(name, HOME / "lib" / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def config(project_dir):
    """환경 변수 > 저장소 harness.env > 사용자 harness.env > 기본값. 이 스크립트의 키(접두)만 읽는다."""
    cfg = dict(DEFAULTS)
    try:
        he = load_mod("harness_env")
        files = []
        user = he.find_file([HOME / "harness.env"])
        if user:
            files.append(user)
        if project_dir:
            repo = Path(project_dir) / ".claude" / "harness.env"
            if repo.is_file():
                files.append(repo)  # 뒤에 읽은 것이 이긴다
        for f in files:
            for k, v in he.parse(f.read_text(encoding="utf-8")).items():
                if k.startswith(PREFIX):
                    cfg[k[len(PREFIX):]] = v
    except Exception:
        pass
    for k in cfg:
        if PREFIX + k in os.environ:
            cfg[k] = os.environ[PREFIX + k]
    cfg["STYLE"] = cfg["STYLE"].strip().lower()
    if cfg["STYLE"] not in STYLES:
        cfg["STYLE"] = "plain"
    return cfg


def fnum(cfg, key):
    try:
        return float(cfg[key])
    except (ValueError, TypeError):
        return float(DEFAULTS[key])


# ---------- git ----------
def git_head(cwd):
    """(브랜치 또는 짧은 해시, git 디렉터리). 프로세스를 띄우지 않고 HEAD 파일만 읽는다. 저장소가 아니면 (None, None)."""
    p = Path(cwd)
    for d in (p, *p.parents):
        g = d / ".git"
        try:
            if g.is_file():  # linked worktree: "gitdir: <경로>"
                t = g.read_text().strip()
                g = Path(t[8:]) if t.startswith("gitdir:") else g
                g = g if g.is_absolute() else d / g
            if g.is_dir():
                head = (g / "HEAD").read_text().strip()
                return (head[16:] if head.startswith("ref: refs/heads/") else head[:7]), d
        except OSError:
            return None, None
    return None, None


def git_dirty(root):
    """추적 파일 변경 여부. git status 는 느릴 수 있어 GIT_TTL 초 캐시한다."""
    base = os.path.join(os.environ.get("TMPDIR") or "/tmp", f"claude-statusline-git-{os.getuid()}")
    f = os.path.join(base, hashlib.md5(str(root).encode()).hexdigest()[:16])
    now = time.time()
    try:
        if now - os.path.getmtime(f) < GIT_TTL:
            return open(f).read() == "1"
    except OSError:
        pass
    try:
        r = subprocess.run(["git", "-C", str(root), "status", "--porcelain", "-uno"], capture_output=True, text=True, timeout=1.5,
                           env=dict(os.environ, GIT_OPTIONAL_LOCKS="0"))
        dirty = bool(r.stdout.strip()) if r.returncode == 0 else False
    except Exception:
        dirty = False
    try:
        os.makedirs(base, exist_ok=True)
        tmp = f"{f}.{os.getpid()}"
        with open(tmp, "w") as fh:
            fh.write("1" if dirty else "0")
        os.replace(tmp, f)
    except OSError:
        pass
    return dirty


def fmt_left(sec):
    sec = max(0, int(sec))
    d, h, m = sec // 86400, sec % 86400 // 3600, sec % 3600 // 60
    return f"{d}d{h}h" if d else f"{h}h{m:02d}m" if h else f"{m}m"


# ---------- 출력 ----------
class Paint:
    CODES = {"dim": "2", "bold": "1", "red": "31", "green": "32", "yellow": "33", "blue": "34", "magenta": "35", "cyan": "36"}

    def __init__(self):
        self.on = not os.environ.get("NO_COLOR")

    def __call__(self, color, s):
        return f"\x1b[{self.CODES[color]}m{s}\x1b[0m" if self.on and s else s


def build(d, cfg, rl, items, away, paint):
    """[(줄 번호, 보이는 글자 길이, 칠한 문자열)] 를 우선순위 순으로 돌려준다."""
    style = cfg["STYLE"]
    nerd = style == "nerd"
    mini = style == "minimal"
    warn, hot = fnum(cfg, "WARN_PCT"), fnum(cfg, "HOT_PCT")
    two = cfg["LINES"].strip() == "2"
    segs = []

    def add(line, parts):
        """parts: [(색, 글자)]. 글자 길이는 칠하기 전 기준이다."""
        parts = [(c, t) for c, t in parts if t]
        if parts:
            segs.append((line if two else 1, len(" ".join(t for _, t in parts)), " ".join(paint(c, t) if c else t for c, t in parts)))

    def pc(p):
        return "green" if p < warn else "yellow" if p < hot else "red"

    def ic(name):
        return ICON[name] if nerd else ""

    ws = d.get("workspace") or {}
    cwd = ws.get("current_dir") or d.get("cwd") or ""
    proj_dir = ws.get("project_dir") or cwd

    # 1. 프로젝트와 브랜치
    if not mini and proj_dir:
        name = os.path.basename(str(proj_dir).rstrip("/\\")) or str(proj_dir)
        branch, root = (git_head(cwd) if cwd else (None, None))
        wt = d.get("worktree") or {}
        branch = wt.get("branch") or branch
        dirty = "*" if branch and root and git_dirty(root) else ""
        if nerd:
            add(1, [("bold", ic("dir") + " " + name)] + ([("magenta", ic("branch") + " " + branch + dirty)] if branch else []))
        else:
            add(1, [("bold", name)] + ([("magenta", f"({branch}{dirty})")] if branch else []))

    # 2. 모델·effort·컨텍스트
    model = (d.get("model") or {}).get("display_name") or ""
    effort = (d.get("effort") or {}).get("level") or ""
    pct = (d.get("context_window") or {}).get("used_percentage")
    ctx_ok = isinstance(pct, (int, float))
    if mini:
        add(1, [("cyan", model), (pc(pct), f"{pct:.0f}%") if ctx_ok else (None, "")])
    elif nerd:
        add(1, [("cyan", ic("model") + " " + model) if model else (None, ""), ("dim", ic("effort") + effort) if effort else (None, ""),
                (pc(pct), ic("ctx") + " " + f"{pct:.0f}%") if ctx_ok else (None, "")])
    else:
        add(1, [("cyan", model), ("dim", effort), (pc(pct), f"ctx {pct:.0f}%") if ctx_ok else (None, "")])

    # 3. 한도(구독자) 또는 비용(그 밖)
    lp = []
    for w, lbl in (("five_hour", "5h"), ("seven_day", "wk")):
        e = rl.get(w)
        if isinstance(e, dict) and isinstance(e.get("used_percentage"), (int, float)):
            lp.append((lbl, e["used_percentage"], e.get("resets_at")))
    now = time.time()
    left = [r - now for _, _, r in lp if isinstance(r, (int, float)) and r > now]
    if lp:
        parts = [(pc(p), f"{lbl} {p:.0f}%") for lbl, p, _ in lp]
        if mini:
            parts = parts[:1]
            add(2, parts)
        else:
            if nerd:
                parts = [(c, (ic("limit") + " " if i == 0 else "") + t) for i, (c, t) in enumerate(parts)]
            else:
                parts[0] = (parts[0][0], "limit " + parts[0][1])
            if left:
                parts.append(("dim", (ic("reset") + " " if nerd else "reset ") + fmt_left(min(left))))
            add(2, parts)
    cost = (d.get("cost") or {}).get("total_cost_usd")
    mode = cfg["COST"].strip().lower()
    if isinstance(cost, (int, float)) and not mini and (mode == "always" or (mode != "never" and not lp)):
        add(2, [(None, (ic("cost") + " " if nerd else "") + f"${cost:.2f}")])

    # 4. 서브에이전트
    if items and not mini:
        L = away["L"]
        fam = ", ".join(f"{f} {n}" for f, n in L.by_family(items).items())
        add(2, [("blue", (ic("agents") + " " if nerd else "agents ") + f"{len(items)} ({fam})")])

    # 5. away
    if away.get("text"):
        add(2, [(away["color"], away["text"])])
    return segs


def fit(segs, line, cols):
    """한 줄에 들어갈 때까지 뒤 항목을 통째로 뺀다. 첫 항목은 남긴다."""
    row = [s for s in segs if s[0] == line]
    while len(row) > 1 and sum(s[1] for s in row) + 3 * (len(row) - 1) > cols:
        row.pop()
    return row


def main():
    try:
        d = json.load(sys.stdin)
        d = d if isinstance(d, dict) else {}
    except Exception:
        d = {}
    rl = d.get("rate_limits") if isinstance(d.get("rate_limits"), dict) else {}
    sid = d.get("session_id")
    ws = d.get("workspace") or {}
    cfg = config(os.environ.get("CLAUDE_PROJECT_DIR") or ws.get("project_dir") or ws.get("current_dir") or d.get("cwd"))
    away = {"L": None, "text": "", "color": "cyan"}
    items = []
    try:
        L = load_mod("subagent_ledger")
        away["L"] = L
        now = time.time()
        if sid:
            L.write_limits(sid, rl, now)  # 훅은 statusline 입력을 못 받으므로 파일로 넘긴다
        if cfg["STYLE"] != "off":
            lim = L.read_limits(sid)
            st = L.read(sid)
            ttl = float(L.CFG_DEFAULTS["HARNESS_SLOTS_RESERVE_SEC"])
            items = list(st["running"].values()) + [r for r in st["reserved"].values() if now - r.get("t", 0) <= ttl]
            a = st.get("away") or {}
            if a.get("on"):
                acfg = L.config(os.environ.get("CLAUDE_PROJECT_DIR"))
                e = L.away_eval(st, lim, now, persist=False, cfg=acfg)
                if a.get("budget_agents") is not None:
                    b = f"{e['spawned']}/{a['budget_agents']} agents"
                elif a.get("budget_pct") is not None:
                    w, dv = max(e["pct"].items(), key=lambda kv: kv[1]) if e["pct"] else (None, 0.0)
                    b = f"+{dv:.0f}/{a['budget_pct']:g}%" + (f" {L.WLABEL[w]}" if w else "") + (" (stale)" if e["stale"] else "")
                else:
                    b = f"${e['spent']:.2f}/${a.get('budget_usd', 0):g}"
                lv = e["level"]
                slots = a.get("over_slots", 1) if lv else a.get("slots")
                q = f" queued {a['queued']}" if a.get("queued") else ""
                tag = "HALT " if lv >= 2 else "OVER " if lv else ""
                head = (ICON["away"] if cfg["STYLE"] == "nerd" else "AWAY") + " "
                away["text"] = f"{head}{tag}{b} slots {slots}{q}"
                away["color"] = "red" if lv >= 2 else "yellow" if lv else "cyan"
    except Exception:
        away["text"] = ""
    if cfg["STYLE"] == "off":
        return 0
    paint = Paint()
    try:
        cols = int(os.environ.get("COLUMNS", "0")) - 4  # 화면 가장자리의 기본 여백
    except ValueError:
        cols = 0
    cols = cols if cols > 20 else 10**6
    segs = build(d, cfg, rl, items, away, paint)
    sep = " " + paint("dim", "·") + " "
    for line in (1, 2):
        row = fit(segs, line, cols)
        if row:
            print(sep.join(s[2] for s in row))
    return 0


if __name__ == "__main__":
    sys.exit(main())
