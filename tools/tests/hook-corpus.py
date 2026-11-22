"""실제 저장소 파일로 python 훅과 실행 형식(Rust 바이너리)을 대조한다: 같은 편집 입력에 같은 종료 코드와 stdout 인가. 표준 라이브러리만 쓴다.

실행:
  python3 -I tools/tests/hook-corpus.py --bin target/debug/qwreey-conventions [--per-repo 120] [--hook conventions-check ...] [--env K=V] REPO...

REPO 마다(읽기만 한다) git ls-files 에서 검사 대상 확장자 파일을 고르게 골라 임시 저장소(git init)에 같은 상대 경로로 복사하고,
REPO 의 .claude/conventions.json, .claude/structure.json 도 복사한다. 파일마다 세 가지 편집을 흉내 낸다:
  create(새 파일 Write), edit(가운데 덩어리의 Edit, old_string 은 그 덩어리에서 세 줄마다 하나를 뺀 것), overwrite(가운데를 뺀
  originalFile 과의 Write). 훅마다 양쪽은 각자의 TMPDIR, CLAUDE_PLUGIN_DATA 를 쓰고 같은 고정 salt, 설정 폴더, 저장소를 본다.
  세션 id 는 (파일, 편집)마다 새로 써서 알림 중복 거르기가 다른 입력에 번지지 않게 한다.
reuse-check 는 저장소 색인을 처음에 한 번씩 데워 둔다(python 판의 첫 색인 시간 한도 300 ms 가 결과를 흔들지 않게).
rules-inject 는 세 편집과 Read 를 본다. 바이너리가 플러그인의 native/ 에 있어야 그 위의 rules/ 를 읽는다(--bin 을 그 자리로 준다).
bash 는 bash-bypass-reminder(PreToolUse)와 bash-writes(PostToolUse)의 짝이다: 파일마다 가운데를 뺀 글을 써 두고, Pre, 파일을 다시 온전히
  쓰기(heredoc 명령 흉내), Post 를 한쪽씩 차례로 돌려 두 훅의 출력을 견준다. 임시 저장소는 커밋이 없어 모든 파일이 porcelain 에 나온다.
결과: 훅마다 입력 수, 같음, 다름, python 이 알린 수와 양쪽 CPU 합(자식 프로세스 user+sys). 다르면 앞 몇 개의 diff 를 보이고 exit 1.
"""
import argparse
import json
import os
import resource
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "plugins" / "qwreey-conventions"
HOOKS = ("conventions-check", "reuse-check", "structure-reminder", "rules-inject", "bash")
# 훅 이름 -> python 스크립트(이름이 다른 것만)
SCRIPTS = {"rules-inject": "rules_inject.py", "bash-writes": "bash_writes.py"}
EXTS = (".luau", ".lua", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".rs", ".py", ".go", ".kt", ".astro", ".sh", ".md")
MAX_BYTES = 1_000_000
SHOW_DIFFS = 5


def pick(repo, per_repo):
    """REPO 의 검사 대상 파일(상대 경로) 가운데 고르게 per_repo 개."""
    out = subprocess.run(["git", "-C", str(repo), "ls-files", "-z"], capture_output=True, check=True).stdout
    names = [n for n in out.decode("utf-8", "replace").split("\0") if n.endswith(EXTS)]
    names = [n for n in names if (repo / n).is_file() and (repo / n).stat().st_size <= MAX_BYTES]
    step = max(1, len(names) // per_repo)
    return names[::step][:per_repo]


def edits(rel, text):
    """(이름, tool, tool_input, tool_response) 세 가지 편집."""
    lines = text.split("\n")
    n = len(lines)
    a = n // 3
    b = min(n, a + max(3, min(30, n // 3)))
    chunk = lines[a:b]
    old = [x for i, x in enumerate(chunk) if i % 3 != 1]
    original = middle_cut(text)
    yield "create", "Write", {"content": text}, {"type": "create"}
    if "\n".join(chunk).strip():
        yield "edit", "Edit", {"old_string": "\n".join(old), "new_string": "\n".join(chunk)}, {}
    yield "overwrite", "Write", {"content": text}, {"type": "update", "originalFile": original}
    yield "read", "Read", {}, {}


def middle_cut(text):
    """가운데 덩어리를 뺀 글(edits 의 overwrite 와 같은 자리)."""
    lines = text.split("\n")
    n = len(lines)
    a = n // 3
    b = min(n, a + max(3, min(30, n // 3)))
    return "\n".join(lines[:a] + lines[b:])


def bash_pair(side, dst, rel, text, sid, env):
    """한쪽에서 Pre, 쓰기, Post. (Pre 결과, Post 결과)."""
    path = dst / rel
    path.write_text(middle_cut(text), encoding="utf-8")
    cmd = "cat > '%s' <<'QWREEY_EOF'\n%s\nQWREEY_EOF" % (rel, text)
    base = {"session_id": sid, "cwd": str(dst), "tool_name": "Bash", "tool_input": {"command": cmd}, "tool_use_id": "toolu_" + sid}
    pre = side.run("bash-bypass-reminder", dict(base, hook_event_name="PreToolUse"), env)
    path.write_text(text, encoding="utf-8")
    post = side.run("bash-writes", dict(base, hook_event_name="PostToolUse"), env)
    return pre, post


class Side:
    """한쪽(python 또는 exec)의 임시 폴더와 명령."""

    def __init__(self, base, name, cmd_of):
        self.name = name
        self.tmp = base / ("tmp-" + name)
        self.data = base / ("data-" + name)
        self.tmp.mkdir()
        self.data.mkdir()
        self.cmd_of = cmd_of
        self.cpu = {}

    def run(self, hook, payload, env):
        env = dict(env, TMPDIR=str(self.tmp), CLAUDE_PLUGIN_DATA=str(self.data))
        before = resource.getrusage(resource.RUSAGE_CHILDREN)
        p = subprocess.run(self.cmd_of(hook), input=json.dumps(payload), capture_output=True, text=True, env=env, timeout=30)
        after = resource.getrusage(resource.RUSAGE_CHILDREN)
        cpu = (after.ru_utime - before.ru_utime) + (after.ru_stime - before.ru_stime)
        self.cpu[hook] = self.cpu.get(hook, 0.0) + cpu
        return p.returncode, p.stdout


def base_env(sandbox, repo_dir):
    env = {k: v for k, v in os.environ.items() if not k.startswith(("HARNESS_", "CONVENTIONS_", "REUSE_", "STRUCTURE_", "MEMORY_", "CLAUDE_"))}
    env.update(HOME=str(sandbox / "home"), CLAUDE_CONFIG_DIR=str(sandbox / "cfg"), CLAUDE_PROJECT_DIR=str(repo_dir),
               CLAUDE_PLUGIN_ROOT=str(PLUGIN), QWREEY_HARNESS_SALT_FILE=str(sandbox / "salt"))
    return env


def setup_repo(sandbox, src, files):
    """임시 저장소에 고른 파일과 설정을 복사한다."""
    dst = sandbox / "repos" / src.name
    dst.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(dst)], check=True)
    for rel in files + [".claude/conventions.json", ".claude/structure.json"]:
        if (src / rel).is_file():
            (dst / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src / rel, dst / rel)
    return dst


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bin", required=True)
    ap.add_argument("--per-repo", type=int, default=120)
    ap.add_argument("--hook", action="append", choices=HOOKS)
    ap.add_argument("--env", action="append", default=[], metavar="KEY=VALUE", help="extra environment for both sides (e.g. REUSE_CHECK=on)")
    ap.add_argument("repos", nargs="+")
    args = ap.parse_args()
    hooks = args.hook or list(HOOKS)
    binary = str(Path(args.bin).resolve())

    sandbox = Path(tempfile.mkdtemp(prefix="hook-corpus-"))
    (sandbox / "home").mkdir()
    (sandbox / "cfg").mkdir()
    (sandbox / "salt").write_text("00" * 32)
    py = Side(sandbox, "python", lambda h: [sys.executable, "-I", "-X", "utf8", str(PLUGIN / "hooks" / SCRIPTS.get(h, h + ".py"))])
    ex = Side(sandbox, "exec", lambda h: [binary, "hook", h])
    stats = {h: {"inputs": 0, "same": 0, "different": 0, "notices": 0} for h in hooks}
    diffs = []
    try:
        for src in map(lambda r: Path(r).resolve(), args.repos):
            files = pick(src, args.per_repo)
            dst = setup_repo(sandbox, src, files)
            env = base_env(sandbox, dst)
            env.update(kv.split("=", 1) for kv in args.env)

            # Warm the reuse index on both sides
            if "reuse-check" in hooks and files:
                warm = {"session_id": "warm", "cwd": str(dst), "hook_event_name": "PostToolUse", "tool_name": "Write",
                        "tool_input": {"file_path": str(dst / files[0]), "content": ""}, "tool_response": {"type": "create"}}
                for side in (py, ex):
                    side.run("reuse-check", warm, env)
                    side.run("reuse-check", warm, env)

            for i, rel in enumerate(files):
                text = (dst / rel).read_text(encoding="utf-8", errors="replace")
                if "bash" in hooks:
                    sid = "b%s-%d" % (src.name, i)
                    a, b = bash_pair(py, dst, rel, text, sid, env), bash_pair(ex, dst, rel, text, sid, env)
                    for k, name in enumerate(("pre", "post")):
                        s = stats["bash"]
                        s["inputs"] += 1
                        s["notices"] += bool(a[k][1].strip())
                        if a[k] == b[k]:
                            s["same"] += 1
                        else:
                            s["different"] += 1
                            diffs.append(("bash", src.name, rel, name, a[k], b[k]))
                for name, tool, ti, resp in edits(rel, text):
                    payload = {"session_id": "c%s-%d-%s" % (src.name, i, name), "cwd": str(dst), "hook_event_name": "PostToolUse",
                               "tool_name": tool, "tool_input": dict(ti, file_path=str(dst / rel)), "tool_response": resp}
                    for hook in (h for h in hooks if h != "bash"):
                        a = py.run(hook, payload, env)
                        b = ex.run(hook, payload, env)
                        s = stats[hook]
                        s["inputs"] += 1
                        s["notices"] += bool(a[1].strip())
                        if a == b:
                            s["same"] += 1
                        else:
                            s["different"] += 1
                            diffs.append((hook, src.name, rel, name, a, b))
    finally:
        shutil.rmtree(sandbox, ignore_errors=True)

    for hook, s in stats.items():
        if hook == "bash":
            py.cpu[hook] = py.cpu.get("bash-bypass-reminder", 0) + py.cpu.get("bash-writes", 0)
            ex.cpu[hook] = ex.cpu.get("bash-bypass-reminder", 0) + ex.cpu.get("bash-writes", 0)
        print("%-19s %4d inputs: %4d same, %d different, python notices %d; CPU python %.2f s, exec %.2f s"
              % (hook, s["inputs"], s["same"], s["different"], s["notices"], py.cpu.get(hook, 0), ex.cpu.get(hook, 0)))
    for hook, repo, rel, name, a, b in diffs[:SHOW_DIFFS]:
        print("DIFFERENT %s %s:%s (%s)\n  python: exit %d %s\n  exec:   exit %d %s" % (hook, repo, rel, name, a[0], a[1][:600], b[0], b[1][:600]))
    return 1 if diffs else 0


if __name__ == "__main__":
    sys.exit(main())
