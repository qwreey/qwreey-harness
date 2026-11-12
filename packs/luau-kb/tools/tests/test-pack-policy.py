#!/usr/bin/env python3
"""luau-kb 가 coderag 코어에서 옮겨 받은 정책 값(도구 목록, 코드 검사 제외 폴더, lifecycle 별칭)이 선언돼 있는지 본다.
실행: python3 -I packs/luau-kb/tools/tests/test-pack-policy.py   (종료 0 = 통과)
"""
import sys
import tomllib
from pathlib import Path

PACK = Path(__file__).resolve().parents[2]
LADDER = ["proposed", "accepted", "experimental", "available", "deprecated", "removed"]
failures = []


def check(cond, msg):
    if not cond:
        failures.append(msg)


man = tomllib.loads((PACK / "coderag.toml").read_text(encoding="utf-8"))
known = man.get("versions", {}).get("known", [])
for tool in ["luau", "luau-lsp", "stylua", "lute", "pesde", "selene", "darklua", "rojo", "lune", "wally"]:
    check(tool in known, f"[versions] known lacks {tool}")
excl = man.get("code", {}).get("exclude", [])
for d in ["Packages", "*_packages", ".pesde"]:
    check(d in excl, f"[code] exclude lacks {d}")

tax = tomllib.loads((PACK / "taxonomy.toml").read_text(encoding="utf-8"))
lc = tax.get("lifecycle", {})
envs = lc.get("envs", [])
check(bool(envs), "[lifecycle] envs is empty")
for alias, target in lc.get("aliases", {}).items():
    stage, _, rest = target.partition("(")
    check(stage in LADDER, f"alias {alias}: '{stage}' is not a stage")
    if rest:
        check(rest.rstrip(")") in envs, f"alias {alias}: env '{rest.rstrip(')')}' not in envs")

for f in failures:
    print("FAIL", f)
print("ok" if not failures else f"{len(failures)} failure(s)")
sys.exit(1 if failures else 0)
