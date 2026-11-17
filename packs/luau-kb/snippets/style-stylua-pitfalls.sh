#!/usr/bin/env bash
# style-stylua-pitfalls.sh - stylua 가 조용히(또는 시끄럽게) 코드를 바꾸는 조건 둘. check_snippets.py 는 .luau 만 다루므로 여기서 잰다.
# 주장 (stylua 2.5.2, syntax = "Luau" 설정이 적용된 상태에서도):
#  P1 `const` 선언 다음 줄의 `;(f :: T)(1)` 에서 stylua 가 `;` 를 지운다 -> luau 가 "Ambiguous syntax" 로 실행을 거부한다.
#     같은 코드가 `local` 다음이면 `;` 를 앞 줄 끝으로 옮겨 안전하다. 처방: 지역으로 받아 부른다(`const g = f :: T; g(1)`).
#  P2 `-- stylua: ignore` 는 주석 전체가 정확히 그 글자일 때만 먹는다. 뒤에 설명을 붙이면 무시되고 포맷된다.
# `f<<T>>` 가 하위 폴더 실행에서 시프트로 바뀌는 건은 tools/repro-stylua-typeargs.sh 가 다룬다.
# 근거: decisions D-01 2, stl-luau/.claude/conventions.md:94-95, stl-luau/.claude/archive/question-resolved.md:1764-1768. 후보 S-130, S-131
# 기대와 어긋나면 rc=1(= stylua 동작이 바뀜 -> luau-style references/quality.md 3 갱신). 사용: bash snippets/style-stylua-pitfalls.sh [stylua] [luau]
set -u
MISE=${MISE_DATA_DIR:-$HOME/.local/share/mise}
S=${1:-$MISE/installs/stylua/2.5.2/stylua}
L=${2:-$MISE/installs/luau/0.742/luau}
d=$(mktemp -d /tmp/luau-kb-sty.XXXXXX)
trap 'rm -rf "$d"' EXIT
printf 'syntax = "Luau"\n' > "$d/stylua.toml"
printf '%s\n' 'const f: any = print' ';(f :: (number) -> ())(1)' > "$d/pc.luau"
printf '%s\n' 'local f: any = print' ';(f :: (number) -> ())(1)' > "$d/pl.luau"
printf '%s\n' '-- stylua: ignore' 'local t = {   1,2,     3 }' '-- stylua: ignore (aligned)' 'local u = {   1,2,     3 }' > "$d/ig.luau"
(cd "$d" && "$S" pc.luau pl.luau ig.luau) || { echo "stylua 실패"; exit 1; }
rc=0
if (cd "$d" && "$L" pc.luau >/dev/null 2>&1); then echo "P1 FAIL: const 뒤 ';' 가 살아남음 — 동작 변화"; rc=1; else echo "P1 ok: const 다음 ';' 삭제 → 실행 거부 ($(grep -c '^;' "$d/pc.luau") 개 남음)"; fi
if (cd "$d" && "$L" pl.luau >/dev/null 2>&1); then echo "P1 ok: local 다음은 안전"; else echo "P1 FAIL: local 다음도 깨짐"; rc=1; fi
grep -q '^local t = {   1,2,     3 }$' "$d/ig.luau" && echo "P2 ok: 정확한 ignore 는 보존" || { echo "P2 FAIL: 정확한 ignore 도 포맷됨"; rc=1; }
grep -q '^local u = { 1, 2, 3 }$' "$d/ig.luau" && echo "P2 ok: 설명 붙은 ignore 는 무시되어 포맷됨" || { echo "P2 FAIL: 설명 붙은 ignore 가 먹음 — 동작 변화"; rc=1; }
"$S" --version
exit $rc
