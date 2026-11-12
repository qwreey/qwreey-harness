#!/usr/bin/env bash
# stylua 가 명시적 타입 인자 f<<T>>(...) 를 시프트 연산으로 재작성하는 조건을 재현한다.
# 기대(stylua 2.5.2 실측, 2026-11-10):
#   (a) syntax 설정이 없을 때(= stylua.toml 을 못 찾았을 때, 기본 문법): `id<<number>>(1)` -> `id << number >> 1`, rc=0 (조용한 오염)
#   (b) stylua.toml 에 syntax = "Luau" 가 있거나 --syntax luau 를 주면: 그대로 보존
# 판정이 기대와 같으면 rc=0, 다르면 rc=1(= stylua 동작이 바뀜 -> luau-verify references/tooling.md 갱신).
# 사용: tools/repro-stylua-typeargs.sh [stylua 경로]
set -u
S=${1:-${MISE_DATA_DIR:-/code/.local/share/mise}/installs/stylua/2.5.2/stylua}
D=$(mktemp -d)
trap 'rm -rf "$D"' EXIT
src='local function id<T>(x: T): T
	return x
end
local a = id<<number>>(1)
'
printf '%s' "$src" > "$D/a.luau"
(cd "$D" && "$S" a.luau) || { echo "stylua 실패"; exit 1; }
mkdir "$D/cfg" && printf 'syntax = "Luau"\n' > "$D/cfg/stylua.toml" && printf '%s' "$src" > "$D/cfg/b.luau"
(cd "$D/cfg" && "$S" b.luau) || { echo "stylua 실패(cfg)"; exit 1; }
ok=0
grep -q 'id << number >> 1' "$D/a.luau" && echo "(a) 설정 없음: 오염 재현 — $(grep 'local a' "$D/a.luau")" || { echo "(a) 오염이 재현되지 않음 — 동작 변화"; ok=1; }
grep -q 'id<<number>>(1)' "$D/cfg/b.luau" && echo "(b) syntax=Luau: 보존" || { echo "(b) syntax=Luau 에서도 오염 — 동작 변화"; ok=1; }
"$S" --version
exit $ok
