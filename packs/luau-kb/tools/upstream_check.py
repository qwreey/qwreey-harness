#!/usr/bin/env python3
"""luau-kb 업스트림 점검기. 표준 라이브러리만 쓰고 `python3 -I` 로 돈다.

사용:
  python3 -I tools/upstream_check.py                     # 저장소별 mise.toml 핀 vs GitHub 최신 릴리스 표
  python3 -I tools/upstream_check.py --notes             # + 가장 낡은 luau 핀 이후의 luau 릴리스 목록(atom 피드)
  python3 -I tools/upstream_check.py --offline           # 네트워크 없이 핀과 설치본만
  python3 -I tools/upstream_check.py --bug-scan 0.746    # 스니펫을 기준 버전과 새 버전으로 돌려 셋으로 분류
  python3 -I tools/upstream_check.py --bug-scan 0.746 --base 0.742

--bug-scan 분류:
  뒤집힘   새 버전에서 'bug-present 인데 진단 발생' (기준 버전엔 없던 것) -> 고쳐짐 후보
  새 실패  새 버전에만 있는 그 밖의 실패. 'expect-error 인데 0건' 은 한계가 풀렸을 수도, 검사가 꺼졌을 수도 있다
  같음     두 버전 결과가 같다(양쪽 다 실패한 파일은 '기존 실패' 로 따로 적는다)
설치는 하지 않는다. 새 버전이 없으면 `mise install luau@<ver>` 를 안내하고 rc=2 로 끝난다.
네트워크가 안 되면 최신 칸을 '?' 로 두고 계속한다(rc 는 0). GitHub API 는 비인증 60회/시간이라
먼저 releases/latest 리다이렉트(API 한도 밖)를 쓰고, 실패할 때만 API 를 쓴다.
"""
import argparse
import glob
import os
import re
import shutil
import subprocess
import sys
import tomllib
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
KB = os.path.dirname(HERE)
MISE = os.environ.get("MISE_DATA_DIR") or os.path.expanduser("~/.local/share/mise")
UA = {"User-Agent": "luau-kb-upstream-check"}

# 표의 도구 -> (GitHub 저장소, mise.toml 에 나올 수 있는 키들, mise installs 디렉터리 이름들)
TOOLS = {
    "luau": ("luau-lang/luau", ["luau", "github:luau-lang/luau", "aqua:luau-lang/luau"], ["luau"]),
    "luau-lsp": ("JohnnyMorganz/luau-lsp", ["github:JohnnyMorganz/luau-lsp", "luau-lsp", "ubi:JohnnyMorganz/luau-lsp"],
                 ["github-johnny-morganz-luau-lsp", "luau-lsp"]),
    "stylua": ("JohnnyMorganz/StyLua", ["stylua", "github:JohnnyMorganz/StyLua", "aqua:JohnnyMorganz/StyLua"], ["stylua"]),
    "rojo": ("rojo-rbx/rojo", ["github:rojo-rbx/rojo", "rojo", "aqua:rojo-rbx/rojo"], ["github-rojo-rbx-rojo", "rojo"]),
}


def vkey(s):
    """'v2.6.0' / '0.746' / '0.7.4+registry' -> 비교용 튜플. 숫자가 아니면 None."""
    m = re.match(r"^v?(\d+(?:\.\d+)*)", str(s).strip())
    return tuple(int(x) for x in m.group(1).split(".")) if m else None


def fetch(url, method="GET", timeout=8):
    req = urllib.request.Request(url, headers=UA, method=method)
    return urllib.request.urlopen(req, timeout=timeout)


def latest_tag(repo):
    """(태그, 출처 또는 에러). releases/latest 리다이렉트 -> 실패 시 API."""
    try:
        with fetch(f"https://github.com/{repo}/releases/latest", method="HEAD") as r:
            m = re.search(r"/releases/tag/([^/?#]+)$", r.geturl())
            if m:
                return m.group(1), "redirect"
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        first = str(e)
    else:
        first = "리다이렉트에 태그 없음"
    try:
        import json
        with fetch(f"https://api.github.com/repos/{repo}/releases/latest") as r:
            return json.load(r)["tag_name"], "api"
    except Exception as e:  # noqa: BLE001 — 네트워크·한도·JSON 무엇이든 우아하게
        return None, f"{first}; api: {e}"


def luau_release_titles():
    """luau 릴리스 atom 피드의 (태그, 갱신일) 목록. 실패하면 []."""
    try:
        with fetch("https://github.com/luau-lang/luau/releases.atom") as r:
            xml = r.read().decode("utf-8", "replace")
    except Exception:  # noqa: BLE001
        return []
    out = []
    for ent in re.findall(r"<entry>(.*?)</entry>", xml, re.S):
        t = re.search(r"<title>([^<]*)</title>", ent)
        u = re.search(r"<updated>([^<]*)</updated>", ent)
        if t:
            out.append((t.group(1).strip(), (u.group(1)[:10] if u else "?")))
    return out


def installed(tool):
    vs = set()
    for d in TOOLS[tool][2]:
        root = os.path.join(MISE, "installs", d)
        if os.path.isdir(root):
            for name in os.listdir(root):
                p = os.path.join(root, name)
                if os.path.isdir(p) and not os.path.islink(p) and vkey(name) and name.count(".") >= 1:
                    vs.add(name)
    return sorted(vs, key=vkey)


def pins(projects_root):
    rows = []
    for f in sorted(glob.glob(os.path.join(projects_root, "*", "mise.toml")) +
                    glob.glob(os.path.join(projects_root, "*", ".mise.toml"))):
        try:
            with open(f, "rb") as fh:
                tools = tomllib.load(fh).get("tools", {})
        except (OSError, tomllib.TOMLDecodeError) as e:
            rows.append((os.path.basename(os.path.dirname(f)), {"_err": str(e)}))
            continue
        got = {}
        for tool, (_, keys, _) in TOOLS.items():
            for k in keys:
                if k in tools:
                    v = tools[k]
                    got[tool] = v.get("version", "?") if isinstance(v, dict) else str(v)
                    break
        if got:
            rows.append((os.path.basename(os.path.dirname(f)), got))
    return rows


def table(args):
    latest = {}
    if not args.offline:
        for tool, (repo, _, _) in TOOLS.items():
            tag, src = latest_tag(repo)
            latest[tool] = tag
            if tag is None:
                print(f"[경고] {tool}: 최신 버전을 못 가져옴 ({src[:160]})", file=sys.stderr)
    names = list(TOOLS)
    print("| 저장소 | " + " | ".join(names) + " |")
    print("|---|" + "---|" * len(names))
    print("| **최신 릴리스** | " + " | ".join(latest.get(t) or "?" for t in names) + " |")
    print("| 설치됨(mise) | " + " | ".join(", ".join(installed(t)) or "—" for t in names) + " |")
    behind = 0
    for repo, got in pins(args.projects_root):
        if "_err" in got:
            print(f"| {repo} | mise.toml 파싱 실패: {got['_err'][:60]} |")
            continue
        cells = []
        for t in names:
            v = got.get(t)
            if not v:
                cells.append("—")
                continue
            lt = latest.get(t)
            old = bool(lt and vkey(v) and vkey(lt) and vkey(v) < vkey(lt))
            behind += old
            cells.append(f"{v}*" if old else v)
        print(f"| {repo} | " + " | ".join(cells) + " |")
    print("\n`*` = 최신 릴리스보다 낮은 핀." + (" 최신을 못 가져온 칸은 비교하지 않았다." if any(
        v is None for v in latest.values()) or args.offline else ""))
    if args.notes and not args.offline:
        luau_pins = [g["luau"] for _, g in pins(args.projects_root) if "luau" in g and vkey(g["luau"])]
        floor = min(luau_pins, key=vkey) if luau_pins else None
        rel = luau_release_titles()
        if not rel:
            print("\n[경고] luau 릴리스 피드를 못 가져옴", file=sys.stderr)
        elif floor:
            newer = [(t, d) for t, d in rel if vkey(t) and vkey(t) > vkey(floor)]
            print(f"\n가장 낡은 luau 핀 {floor} 이후 릴리스 (피드 최근 10개 안에서):")
            for t, d in newer:
                print(f"- {t} ({d}) https://github.com/luau-lang/luau/releases/tag/{t}")
            if len(newer) == len(rel):
                print("- (피드가 10개까지만 보여 준다. 더 오래된 것은 releases 페이지를 넘겨 본다)")


def tool_dir(v):
    base = os.environ.get("LUAU_BIN_DIR")
    if base and os.path.isdir(os.path.join(base, v)):
        return os.path.join(base, v)
    return os.path.join(MISE, "installs", "luau", v)


def run_harness(vers, files):
    cmd = [sys.executable, "-I", os.path.join(HERE, "check_snippets.py"), "--luau", ",".join(vers)] + files
    if shutil.which("choom"):
        cmd = ["choom", "-n", "1000", "--"] + cmd
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=KB)
    if r.returncode not in (0, 1) or ("ok   [" not in r.stdout and "FAIL [" not in r.stdout):
        sys.exit(f"하네스 실행 실패 rc={r.returncode}: {(r.stderr or r.stdout)[:400]}")
    res = {}  # (file, ver) -> [에러 줄]
    cur = None
    for line in r.stdout.splitlines():
        m = re.match(r"^(ok|FAIL) +\[([^\]]+)\] (.+)$", line)
        if m:
            cur = (m.group(3), m.group(2))
            res[cur] = []
        elif cur and line.startswith("      "):
            res[cur].append(line.strip())
    return res


def bug_scan(args):
    new = args.bug_scan
    if not os.path.exists(os.path.join(tool_dir(new), "luau-analyze")):
        print(f"luau {new} 가 설치돼 있지 않다: {tool_dir(new)}\n"
              f"설치는 사용자 판단이다. 설치하려면(전역 설정·저장소 핀은 바뀌지 않는다):\n"
              f"  mise install luau@{new}")
        sys.exit(2)
    base = args.base
    if not base:
        cands = [v for v in installed("luau") if vkey(v) < vkey(new)]
        base = cands[-1] if cands else None
    if not base or not os.path.exists(os.path.join(tool_dir(base), "luau-analyze")):
        sys.exit(f"기준 버전이 없다(--base 로 지정): {base}")
    files = args.files or sorted(glob.glob(os.path.join(KB, "snippets", "*.luau")))
    files = [os.path.relpath(f, KB) if os.path.isabs(f) else f for f in files]
    res = run_harness([base, new], files)
    flipped, fresh, same, both_fail, healed, other_col = [], [], [], [], [], []
    for f in files:
        b, n = res.get((f, base)), res.get((f, new))
        if b is None or n is None:
            if any(k[0] == f for k in res):  # 하네스가 luau 버전 대신 다른 열(예: [lsp 1.70.1])로 검사한 파일
                other_col.append(f)
            else:
                fresh.append((f, ["하네스 출력에 이 파일이 없음"]))
            continue
        only_new = [e for e in n if e not in set(b)]  # 줄 번호 + 메시지가 같으면 같은 실패
        fl = [e for e in only_new if "bug-present 인데 진단 발생" in e]
        other = [e for e in only_new if e not in fl]
        if fl:
            flipped.append((f, fl))
        if other:
            fresh.append((f, other))
        if not fl and not other:
            if b and n:
                both_fail.append((f, n))
            elif b and not n:
                healed.append((f, b))
            else:
                same.append(f)
    print(f"# bug-scan: luau {base} -> {new} ({len(files)} 파일)\n")
    print(f"## 뒤집힘 (고쳐짐 후보) {len(flipped)}")
    for f, es in flipped:
        print(f"- {f}")
        for e in es:
            print(f"    {e}")
    print(f"\n## 새 실패 (깨짐 후보, 또는 한계가 풀림) {len(fresh)}")
    for f, es in fresh:
        print(f"- {f}")
        for e in es:
            hint = "  <- 한계가 풀렸는지, 검사가 꺼졌는지 확인" if "expect-error 인데 0건" in e else ""
            print(f"    {e}{hint}")
    print(f"\n## 같음 {len(same) + len(both_fail) + len(healed) + len(other_col)}")
    print(f"- 두 버전 모두 ok: {len(same)}")
    if other_col:
        print(f"- luau 버전과 무관한 열로 검사된 파일(예: Roblox 정의 파일 + luau-lsp): {len(other_col)}")
    for f, es in both_fail:
        print(f"- 기존 실패(두 버전 같은 실패, 이 스캔과 무관): {f}: {es[0][:120]}")
    for f, es in healed:
        print(f"- 기준 버전에서만 실패: {f}: {es[0][:120]}")
    print("\n다음: 뒤집힘은 스니펫 표식에 버전 조건([<" + new + "] / [>=" + new + "])을 달고 references 를 갱신,"
          " 새 실패는 퇴행인지 메시지 변화인지 재현해 판정한다 (skills/luau-upstream/references/version-bump.md).")


def main():
    ap = argparse.ArgumentParser(description="mise 핀 vs 업스트림 최신, 그리고 스니펫 bug-scan")
    ap.add_argument("--projects-root", default=os.environ.get("PROJECTS_ROOT") or os.environ.get("HARNESS_WORKSPACE") or os.path.expanduser("~/Projects"))
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--notes", action="store_true", help="가장 낡은 luau 핀 이후 릴리스 목록")
    ap.add_argument("--bug-scan", metavar="VER")
    ap.add_argument("--base", metavar="VER", help="bug-scan 기준 버전(기본: 설치된 것 중 VER 바로 아래)")
    ap.add_argument("files", nargs="*", help="bug-scan 대상(기본 snippets/*.luau)")
    args = ap.parse_args()
    if args.bug_scan:
        bug_scan(args)
    else:
        table(args)


if __name__ == "__main__":
    main()
