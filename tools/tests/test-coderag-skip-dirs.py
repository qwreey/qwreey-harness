#!/usr/bin/env python3
"""coderag 의 rules::SKIP_DIRS 가 참조 구현(rules_inject.py 의 SKIP_DIRS)과 같은 집합인지 소스에서 대조한다.
실행: python3 -I tools/tests/test-coderag-skip-dirs.py   (종료 0 = 통과)
coderag 소스는 $CODERAG_SRC, 없으면 ../coderag. 없으면 사유를 출력하고 0 으로 끝낸다.
"""
import ast
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
py = (ROOT / "plugins" / "qwreey-conventions" / "hooks" / "rules_inject.py").read_text(encoding="utf-8")
m = re.search(r"^SKIP_DIRS\s*=\s*(\{.*?\})", py, re.M | re.S)
if not m:
    print("FAIL: SKIP_DIRS not found in rules_inject.py")
    sys.exit(1)
ref = set(ast.literal_eval(m.group(1)))

src = Path(os.environ.get("CODERAG_SRC") or ROOT.parent / "coderag")
rs = src / "crates" / "coderag-core" / "src" / "rules" / "mod.rs"
if not rs.is_file():
    print(f"skip: {rs} not found")
    sys.exit(0)
m = re.search(r"^const SKIP_DIRS: &\[&str\]\s*=\s*&\[(.*?)\];", rs.read_text(encoding="utf-8"), re.M | re.S)
if not m:
    print("FAIL: const SKIP_DIRS not found in coderag rules/mod.rs")
    sys.exit(1)
got = set(re.findall(r'"([^"]+)"', m.group(1)))
if got != ref:
    print(f"FAIL: coderag-only {sorted(got - ref)}, rules_inject.py-only {sorted(ref - got)}")
    sys.exit(1)
print(f"ok ({len(ref)} dirs)")
