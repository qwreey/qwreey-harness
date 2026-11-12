#!/usr/bin/env python3
"""coderag 의 rule 주입 훅이 팩에 실린 파이썬 사본(rules_inject.py)과 같은 출력을 내는지 대조한다.
실행: python3 -I tools/tests/test-coderag-rules-parity.py   (종료 0 = 통과)

대조 대상: packs/<팩>/hooks/rules_inject.py (+ PreCompact 의 compact_epoch.py) 대 `coderag hook post-tool --pack <팩>` (+ `hook pre-compact`).
coderag 바이너리는 $CODERAG_BIN, 없으면 ../coderag/target/{debug,release}/coderag. 없으면 사유를 출력하고 0 으로 끝낸다.

격리: 두 쪽 모두 임시 폴더만 쓴다. 파이썬은 TMPDIR(회차·마커 상태), 코어는 CODERAG_HOME·CODERAG_CACHE(상태 `$CODERAG_HOME/state`).
팩은 임시 CODERAG_HOME/coderag.toml 의 [[packs]] path 로 등록한다.

정규화는 두 가지뿐이다(나머지는 stdout 바이트 그대로 비교한다).
  1. 끄기 스위치 이름: 파이썬 HARNESS_CONVENTIONS_RULES=off 에 대응해 코어는 CODERAG_RULES=off 를 준다.
  2. 상태 경로: 두 구현의 상태 위치는 서로 달라야 하므로(각자 임시 폴더) 비교하지 않는다. 출력에는 상태 경로가 나오지 않는다.
의도한 차이 하나: 파이썬은 훅 이벤트가 PostToolUse 가 아니어도 rule 마커를 먼저 소비하고 나서 출력을 포기한다. 코어는 이벤트를 먼저 보고
마커를 소비하지 않는다. 출력(빈 문자열)은 같아서 매트릭스에서는 같은 결과로 비교된다.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKS = ["web-security", "luau-kb"]


def find_bin():
    cands = [os.environ.get("CODERAG_BIN", "")]
    for kind in ("debug", "release"):
        cands.append(str(ROOT.parent / "coderag" / "target" / kind / "coderag"))
    return next((c for c in cands if c and os.access(c, os.X_OK)), None)


def base_env(tmp, extra):
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(tmp / "home"), "LANG": "C.UTF-8"}
    env.update(extra)
    return env


class Runner:
    def __init__(self, tmp, binary, pack, proj):
        self.tmp, self.bin, self.pack, self.proj = tmp, binary, pack, proj
        self.hooks = ROOT / "packs" / pack / "hooks"
        self.py_tmp = tmp / "py-tmp"
        self.cg_home = tmp / "cg-home"
        self.cg_cache = tmp / "cg-cache"
        self.cfg = tmp / "claude-cfg"
        for d in (self.py_tmp, self.cg_home, self.cg_cache, self.cfg, tmp / "home"):
            d.mkdir(parents=True, exist_ok=True)
        (self.cg_home / "coderag.toml").write_text(
            "".join('[[packs]]\nname = "%s"\npath = "%s"\n' % (p, ROOT / "packs" / p) for p in PACKS))

    def common(self, proj):
        return {"CLAUDE_PROJECT_DIR": str(proj), "CLAUDE_CONFIG_DIR": str(self.cfg)}

    def py(self, event, data, off, proj):
        env = base_env(self.tmp, {"TMPDIR": str(self.py_tmp), **self.common(proj)})
        if off:
            env["HARNESS_CONVENTIONS_RULES"] = "off"
        script = "rules_inject.py" if event == "hook" else "compact_epoch.py"
        argv = ["python3", "-I", str(self.hooks / script)] + ([] if event == "hook" else [self.pack])
        return subprocess.run(argv, input=json.dumps(data), capture_output=True, text=True, env=env, timeout=30, cwd=str(self.tmp)).stdout

    def cg(self, event, data, off, proj):
        env = base_env(self.tmp, {"CODERAG_HOME": str(self.cg_home), "CODERAG_CACHE": str(self.cg_cache), **self.common(proj)})
        if off:
            env["CODERAG_RULES"] = "off"
        argv = [self.bin, "hook", "post-tool" if event == "hook" else "pre-compact"] + (["--pack", self.pack] if event == "hook" else [])
        r = subprocess.run(argv, input=json.dumps(data), capture_output=True, text=True, env=env, timeout=30, cwd=str(self.tmp))
        return r.stdout


def scenarios(pack, proj, proj_excl, cfg):
    """(이름, [단계]) 목록. 단계 = (kind, 입력 dict, 옵션). kind: hook | compact."""
    if pack == "web-security":
        hit, hit2, miss, excl_rule = "src/app.ts", "deploy/run.sh", "README.md", "web-security"
        hit3 = "docker/Dockerfile"
    else:
        hit, hit2, miss, excl_rule = "src/a.luau", "src/b.lua", "notes.txt", "luau-core"
        hit3 = "pkg/init.luau"
    P = str(proj)

    def ev(tool, path, sid="s", key="file_path", **kw):
        d = {"hook_event_name": "PostToolUse", "session_id": sid, "tool_name": tool, "tool_input": {key: path}}
        d.update(kw)
        return d

    def pre(sid="s", **kw):
        return {"hook_event_name": "PreCompact", "session_id": sid, **kw}

    H = lambda d, **o: ("hook", d, o)
    C = lambda d: ("compact", d, {})
    out = []
    out.append(("read-hit-then-repeat", [H(ev("Read", f"{P}/{hit}", "a")), H(ev("Read", f"{P}/{hit}", "a")), H(ev("Edit", f"{P}/{hit}", "a"))]))
    out.append(("edit-first-wording", [H(ev("Edit", f"{P}/{hit}", "b")), H(ev("Write", f"{P}/{hit2}", "b"))]))
    out.append(("write-new-file", [H(ev("Write", f"{P}/{hit3}", "c")), H(ev("MultiEdit", f"{P}/{hit}", "c"))]))
    out.append(("no-match", [H(ev("Read", f"{P}/{miss}", "d")), H(ev("Edit", f"{P}/{miss}", "d"))]))
    out.append(("skip-dirs", [H(ev("Read", f"{P}/node_modules/x/{hit}", "e")), H(ev("Edit", f"{P}/dist/{hit}", "e")),
                              H(ev("Write", f"{P}/a/.git/{hit}", "e")), H(ev("Read", f"{P}/vendor/{hit}", "e")),
                              H(ev("Read", f"{P}/__pycache__/{hit}", "e")), H(ev("Read", f"{P}/build/{hit}", "e")),
                              H(ev("Read", f"{P}/.venv/{hit}", "e"))]))
    out.append(("skip-dir-name-in-project-parent", [H(ev("Read", f"{P}/{hit}", "f"))]))
    out.append(("outside-project", [H(ev("Read", f"/elsewhere/{hit}", "g")), H(ev("Edit", f"/elsewhere/{hit}", "g")),
                                    H(ev("Write", f"/elsewhere/{hit2}", "g")), H(ev("Read", f"/elsewhere/node_modules/{hit}", "g"))]))
    out.append(("memory-exception", [H(ev("Read", f"{cfg}/projects/p1/memory/{hit}", "h")), H(ev("Read", f"{cfg}/projects/p1/{hit}", "h")),
                                     H(ev("Read", f"{cfg}/projects/p1/memory/sub/{hit2}", "h"))]))
    out.append(("relative-path-with-cwd", [H(ev("Read", hit, "i", cwd=P)), H(ev("Edit", f"./{hit2}", "i", cwd=P)),
                                           H(ev("Read", f"x/../{hit3}", "i", cwd=P))]))
    out.append(("notebook-and-keys", [H(ev("NotebookEdit", f"{P}/{hit}", "j", key="notebook_path")), H(ev("Edit", "", "j")),
                                      H({"hook_event_name": "PostToolUse", "session_id": "j", "tool_name": "Read", "tool_input": {}})]))
    out.append(("subagent-own-key", [H(ev("Read", f"{P}/{hit}", "k")), H(ev("Read", f"{P}/{hit}", "k", agent_id="ag1")),
                                     H(ev("Read", f"{P}/{hit}", "k", agent_id="ag1")), H(ev("Read", f"{P}/{hit}", "k", agent_id="ag2"))]))
    out.append(("compact-rearms", [H(ev("Read", f"{P}/{hit}", "l")), H(ev("Read", f"{P}/{hit}", "l")), C(pre("l")),
                                   H(ev("Read", f"{P}/{hit}", "l")), H(ev("Read", f"{P}/{hit}", "l")), C(pre("l", trigger="auto")),
                                   H(ev("Edit", f"{P}/{hit}", "l"))]))
    out.append(("subagent-compact-does-not-bump", [H(ev("Read", f"{P}/{hit}", "m")), C(pre("m", agent_id="ag1")), H(ev("Read", f"{P}/{hit}", "m")),
                                                   H(ev("Read", f"{P}/{hit}", "m", agent_id="ag1")), C(pre("m", agent_id="ag1")),
                                                   H(ev("Read", f"{P}/{hit}", "m", agent_id="ag1"))]))
    out.append(("event-not-posttooluse", [H({"hook_event_name": "PreToolUse", "session_id": "n", "tool_name": "Read", "tool_input": {"file_path": f"{P}/{hit}"}}),
                                          H({"session_id": "n", "tool_name": "Read", "tool_input": {"file_path": f"{P}/{hit}"}})]))
    out.append(("no-session-id", [H({"hook_event_name": "PostToolUse", "tool_name": "Read", "tool_input": {"file_path": f"{P}/{hit}"}}),
                                  H({"hook_event_name": "PostToolUse", "tool_name": "Read", "tool_input": {"file_path": f"{P}/{hit}"}})]))
    out.append(("odd-session-id-chars", [H(ev("Read", f"{P}/{hit}", "../x/y z")), H(ev("Read", f"{P}/{hit}", "../x/y z"))]))
    out.append(("unicode-filename", [H(ev("Read", f"{P}/src/한글 {Path(hit).name}", "o"))]))
    out.append(("tool-name-missing", [H({"hook_event_name": "PostToolUse", "session_id": "p", "tool_input": {"file_path": f"{P}/{hit}"}})]))
    out.append(("off-switch", [H(ev("Read", f"{P}/{hit}", "q"), off=True), H(ev("Read", f"{P}/{hit}", "q"))]))
    out.append(("rules-exclude", [H(ev("Read", f"{proj_excl}/{hit}", "r"), proj=proj_excl)]))
    out.append(("garbage-input", [("raw", "not json file_path", {}), ("raw", "{}", {}), ("raw", "", {})]))
    return out


def main():
    binary = find_bin()
    if not binary:
        print("skip: coderag 바이너리가 없다($CODERAG_BIN 또는 ../coderag/target/{debug,release}/coderag)")
        return 0
    total, fails, injected = 0, [], 0
    with tempfile.TemporaryDirectory(prefix="rules-parity-") as t:
        for pack in PACKS:
            tmp = Path(t) / pack
            proj = tmp / "proj"
            proj_excl = tmp / "proj-excl"
            (proj / "src").mkdir(parents=True)
            excl_rule = "web-security" if pack == "web-security" else "luau-core"
            (proj_excl / ".claude").mkdir(parents=True)
            (proj_excl / ".claude" / "conventions.json").write_text(json.dumps({"rules_exclude": [excl_rule]}))
            r = Runner(tmp, binary, pack, proj)
            for name, steps in scenarios(pack, proj, proj_excl, r.cfg):
                for i, (kind, data, opt) in enumerate(steps):
                    p = opt.get("proj", proj)
                    off = opt.get("off", False)
                    if kind == "raw":
                        a = subprocess.run(["python3", "-I", str(r.hooks / "rules_inject.py")], input=data, capture_output=True, text=True,
                                           env=base_env(tmp, {"TMPDIR": str(r.py_tmp), "CLAUDE_PROJECT_DIR": str(p)}), timeout=30).stdout
                        b = subprocess.run([binary, "hook", "post-tool", "--pack", pack], input=data, capture_output=True, text=True,
                                           env=base_env(tmp, {"CODERAG_HOME": str(r.cg_home), "CODERAG_CACHE": str(r.cg_cache), "CLAUDE_PROJECT_DIR": str(p)}),
                                           timeout=30).stdout
                    else:
                        ek = "hook" if kind == "hook" else "compact"
                        a, b = r.py(ek, data, off, p), r.cg(ek, data, off, p)
                    if kind != "compact":
                        total += 1
                        injected += bool(a)
                    if a != b:
                        fails.append((pack, name, i, a, b))
        # 두 팩을 프로젝트 coderag.toml 로 함께 켠 경우: 팩마다 한 덩어리씩 한 JSON 으로 나온다.
        tmp = Path(t) / "both"
        r = Runner(tmp, binary, "web-security", tmp / "proj")
        (tmp / "proj").mkdir()
        (tmp / "proj" / "coderag.toml").write_text('[[packs]]\nname = "web-security"\n[[packs]]\nname = "luau-kb"\n')
        env = base_env(tmp, {"CODERAG_HOME": str(r.cg_home), "CODERAG_CACHE": str(r.cg_cache), "CLAUDE_PROJECT_DIR": str(tmp / "proj")})
        data = {"hook_event_name": "PostToolUse", "session_id": "z", "tool_name": "Read", "tool_input": {"file_path": str(tmp / "proj" / "x.luau")}}
        out = subprocess.run([binary, "hook", "post-tool"], input=json.dumps(data), capture_output=True, text=True, env=env, timeout=30).stdout
        total += 1
        try:
            ctx = json.loads(out)["hookSpecificOutput"]["additionalContext"]
            ok = 'plugin="luau-kb"' in ctx and 'plugin="web-security"' not in ctx
        except ValueError:
            ok = False
        if not ok:
            fails.append(("both", "project-switch", 0, "luau-kb 만 나와야 함(.luau 는 web-security 경로에 없다)", out))
        data["tool_input"]["file_path"] = str(tmp / "proj" / "x.sh")
        out = subprocess.run([binary, "hook", "post-tool"], input=json.dumps(data), capture_output=True, text=True, env=env, timeout=30).stdout
        total += 1
        if 'plugin=\\"web-security\\"' not in out:
            fails.append(("both", "project-switch", 1, "web-security 가 나와야 함", out))
    for pack, name, i, a, b in fails:
        print("FAIL %s/%s step %d\n  python: %r\n  coderag: %r" % (pack, name, i, a[:300], b[:300]))
    # 전부 빈 출력이면 대조가 아무것도 증명하지 못한다.
    if injected < 20:
        fails.append(("matrix", "coverage", 0, "", "주입 출력이 %d 건뿐" % injected))
    print("%d comparisons (%d with injection), %d failed" % (total, injected, len(fails)))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
