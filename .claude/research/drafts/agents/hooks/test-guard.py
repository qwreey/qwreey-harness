#!/usr/bin/env python3
"""auditor-readonly-guard 회귀 표. 실행: python3 -I test-guard.py  (exit 0 = 전부 기대대로)"""
import json, os, subprocess, sys

GUARD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "auditor-readonly-guard.py")
CWD = "/code/Projects/example"
S = "/tmp/claude-audit"

# (기대: 0 통과 / 2 차단, 도구, 입력)
CASES = [
    (0, "Bash", "git status --porcelain"),
    (0, "Bash", "git -C /code/Projects/x log --oneline -5"),
    (0, "Bash", "git show HEAD:src/init.luau | head -40"),
    (0, "Bash", "git diff HEAD -- src 2>&1"),
    (0, "Bash", "git branch --show-current"),
    (0, "Bash", "git stash list"),
    (2, "Bash", "git stash"),
    (2, "Bash", "git checkout -- src/a.luau"),
    (2, "Bash", "git -c core.x=1 add -A"),
    (2, "Bash", "git branch -D foo"),
    (2, "Bash", "git commit -m x"),
    (0, "Bash", f"mkdir -p {S}/types && cat > {S}/types/neg.luau <<'EOF'\nlocal a: number = \"x\" -- 잡혀야 함\nif a > 1 then print(a) end\nEOF"),
    (0, "Bash", f"mise exec -- luau-analyze {S}/types/neg.luau; echo $?"),
    (0, "Bash", f"choom -n 1000 -- prlimit --data=3221225472 -- luau {S}/bench.luau > {S}/out.txt 2>&1"),
    (0, "Bash", "rg -n 'a > b' src | head"),
    (0, "Bash", "luau-analyze src/init.luau 2>&1 >/dev/null"),
    (2, "Bash", "echo x > src/init.luau"),
    (2, "Bash", "echo x >> notes.md"),
    (2, "Bash", "sed -i 's/a/b/' src/init.luau"),
    (0, "Bash", "sed -n '1,40p' src/init.luau"),
    (2, "Bash", "perl -pi -e 's/a/b/' x.luau"),
    (2, "Bash", "rm -rf .claude/worktrees/x"),
    (0, "Bash", f"rm -rf {S}/types"),
    (2, "Bash", f"cp src/init.luau {S}/../escape.luau"),
    (0, "Bash", f"cp src/init.luau {S}/copy.luau && luau {S}/copy.luau"),  # cp 는 대상(마지막 인자)만 본다
    (2, "Bash", "curl https://example.com"),
    (2, "Bash", "mise exec -- pesde install"),
    (2, "Bash", "mise trust"),
    (2, "Bash", "ls | tee listing.txt"),
    (0, "Write", f"{S}/probe.luau"),
    (2, "Write", f"{CWD}/src/probe.luau"),
    (2, "Edit", f"{CWD}/src/init.luau"),
    (2, "Write", f"{CWD}/.claude/agent-memory/luau-type-auditor/MEMORY.md"),
    (2, "mcp__roblox-studio__execute_luau", ""),
]


def run(tool, arg):
    ti = {"command": arg} if tool == "Bash" else {"file_path": arg}
    p = subprocess.run([sys.executable, "-I", GUARD], input=json.dumps({"tool_name": tool, "tool_input": ti, "cwd": CWD}),
                       capture_output=True, text=True)
    return p.returncode, p.stderr.strip()


bad = 0
for want, tool, arg in CASES:
    rc, err = run(tool, arg)
    ok = rc == want
    bad += not ok
    print(("ok  " if ok else "FAIL"), want, rc, tool, (arg.splitlines() or [""])[0][:70], ("" if ok else "| " + err))
print(f"{len(CASES) - bad}/{len(CASES)}")
sys.exit(1 if bad else 0)
