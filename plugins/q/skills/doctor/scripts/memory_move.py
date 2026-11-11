#!/usr/bin/env python3
"""auto memory 를 한 프로젝트 키에서 다른 키로 복사한다(폴더를 옮겨 끊긴 메모리 잇기). 기본은 dry-run.

사용(키가 `-` 로 시작하므로 `--from-key=` 처럼 `=` 로 붙인다):
  python3 -I memory_move.py --from-key=<옛 키> --to <새 저장소 경로 | 새 키> [--apply] [--projects <~/.claude/projects>]

동작: 새 키의 memory/ 에 옛 키의 *.md 를 복사한다. 원본은 남긴다(삭제 없음).
  - 같은 이름이고 내용이 같으면 건너뛴다. 이름이 같고 내용이 다르면 덮어쓰지 않고 `<이름>.from-<옛 키 끝 8자>.md` 로 복사한다.
  - MEMORY.md 는 새 키에 없으면 복사, 있으면 옛 줄 중 새 쪽에 없는 줄을 끝에 붙인다(줄 수 한도 200줄은 보고만 한다).
  - --apply 가 없으면 아무것도 쓰지 않고 계획만 출력한다. 사용자 동의를 받은 뒤에만 --apply 를 붙인다.
새 키 규칙은 lib/memory_signals.py 의 key_of 와 같다(영숫자 외 문자를 '-' 로).
"""
import argparse
import re
import shutil
import sys
from pathlib import Path


def key_of(path):
    return re.sub(r"[^A-Za-z0-9]", "-", str(path))


def plan(src, dst, tag):
    """[(action, name, detail)] without touching disk. src/dst are memory dirs."""
    steps = []
    for f in sorted(src.glob("*.md")):
        t = dst / f.name
        if f.name == "MEMORY.md":
            if not t.exists():
                steps.append(("copy", f.name, "새 키에 없음: 복사"))
            else:
                have = set(t.read_text().splitlines())
                new = [l for l in f.read_text().splitlines() if l.strip() and l not in have]
                steps.append(("append", f.name, f"새 키 MEMORY.md 에 없는 줄 {len(new)}개를 끝에 붙임") if new else ("skip", f.name, "추가할 줄 없음"))
        elif not t.exists():
            steps.append(("copy", f.name, "복사"))
        elif t.read_bytes() == f.read_bytes():
            steps.append(("skip", f.name, "같은 내용이 이미 있음"))
        else:
            steps.append(("copy-as", f"{f.stem}.from-{tag}.md", f"{f.name} 이(가) 새 키에 다른 내용으로 있어 덮어쓰지 않고 다른 이름으로 복사"))
    return steps


def apply(src, dst, steps):
    dst.mkdir(parents=True, exist_ok=True)
    for action, name, _ in steps:
        if action == "copy":
            shutil.copy2(src / name, dst / name)
        elif action == "copy-as":
            orig = name.split(".from-")[0] + ".md"
            shutil.copy2(src / orig, dst / name)
        elif action == "append":
            have = set((dst / name).read_text().splitlines())
            new = [l for l in (src / name).read_text().splitlines() if l.strip() and l not in have]
            with open(dst / name, "a") as fh:
                fh.write(("" if (dst / name).read_text().endswith("\n") else "\n") + "\n".join(new) + "\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--from-key", required=True)
    ap.add_argument("--to", required=True, help="새 저장소 경로(절대) 또는 새 프로젝트 키")
    ap.add_argument("--projects", default=str(Path.home() / ".claude" / "projects"))
    ap.add_argument("--apply", action="store_true", help="실제로 복사한다(기본은 dry-run)")
    a = ap.parse_args()
    projects = Path(a.projects)
    to_key = key_of(Path(a.to).resolve()) if a.to.startswith("/") else a.to
    src, dst = projects / a.from_key / "memory", projects / to_key / "memory"
    if not src.is_dir():
        print(f"옛 키 메모리가 없다: {src}", file=sys.stderr)
        return 2
    if a.from_key == to_key:
        print("같은 키다", file=sys.stderr)
        return 2
    steps = plan(src, dst, a.from_key[-8:])
    print(f"{'적용' if a.apply else 'dry-run'}: {src} -> {dst}  (원본은 남긴다)")
    for action, name, detail in steps:
        print(f"  {action:8} {name}: {detail}")
    if not a.apply:
        print("아무것도 쓰지 않았다. 동의를 받은 뒤 --apply 를 붙여 다시 실행한다.")
        return 0
    apply(src, dst, steps)
    print("복사 완료. 새 세션에서 /memory 로 확인하고, 옛 키 폴더는 사용자가 직접 정리한다(삭제 금지 원칙).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
