#!/usr/bin/env bash
# style-require-paths.sh - require-by-string 경로 규칙(luau CLI). 파일이 여럿 필요해서 check_snippets.py 대신 여기서 잰다.
# 주장 (luau 0.734, 0.742):
#  R1 `init.luau` 는 자기가 든 폴더 자체를 뜻한다. 그 안의 `./x` 는 폴더의 **형제**(pkg/x.luau), `@self/x` 는 폴더 안(pkg/src/x.luau)이다.
#     형제 자리에 같은 이름 파일이 있으면 에러 없이 그 파일을 읽는다(조용한 오배선).
#  R2 테스트 엔트리를 `tests/init.luau` 로 지으면 그 안의 `./helper` 는 tests/ 가 아니라 저장소 루트를 찾는다 -> "could not resolve child component".
#     "(ambiguous)" 는 `X.luau` 와 `X/` 가 형제로 같이 있을 때 난다(X-04 의 두 설명 중 mrow 쪽이 맞음).
#  R3 --!strict 의 luau-analyze 는 **없는** 경로와 동적 경로를 "Unknown require: unsupported path" 로 잡는다. nonstrict 는 0건이다.
#     R1 의 오배선처럼 **있는 다른 파일로 풀리는** 경로는 어느 모드에서도 못 잡는다. 그래서 새 모듈은 실제로 require 하는 테스트가 필요하다.
#  R4 CLI 런타임은 동적 경로(`"./pkg/" .. name`)도 실행한다. 정적 검사(R3)만 거부한다.
# 근거: quad .claude/base/project-setup-plan.md:144-167, stl-luau/.claude/base/architecture.md:37-63, tbox/CLAUDE.md:95-117,141-147,
#       mrow-rv:1183-1187. 후보 Q-101, S-123, X-02, X-04. Studio 쪽 규칙(접두 필수 등)은 roblox-engine require-in-roblox.md 담당.
# 기대와 어긋나면 rc=1. 사용: bash snippets/style-require-paths.sh [버전...]   (기본 0.734 0.742)
set -u
MISE=${MISE_DATA_DIR:-/code/.local/share/mise}
vers=("$@"); [ $# -eq 0 ] && vers=(0.734 0.742)
d=$(mktemp -d /tmp/luau-kb-req.XXXXXX)
trap 'rm -rf "$d"' EXIT
mkdir -p "$d/r1/pkg/src" "$d/r2/tests" "$d/r2b/src" "$d/r3"
printf 'return "inside"\n' > "$d/r1/pkg/src/x.luau"
printf 'return "sibling"\n' > "$d/r1/pkg/x.luau"
printf '%s\n' '--!strict' 'return { dot = require("./x"), self = require("@self/x") }' > "$d/r1/pkg/src/init.luau"
printf '%s\n' 'local m = require("./pkg/src")' 'assert(m.dot == "sibling" and m.self == "inside", m.dot .. "/" .. m.self)' > "$d/r1/main.luau"
printf 'return 2\n' > "$d/r2/tests/helper.luau"
printf '%s\n' 'return require("./helper")' > "$d/r2/tests/init.luau"
printf 'return 4\n' > "$d/r2b/src.luau"; printf 'return 5\n' > "$d/r2b/src/init.luau"
printf '%s\n' 'return require("./src")' > "$d/r2b/main.luau"
printf '%s\n' '--!strict' 'local m = require("./nope")' 'return m' > "$d/r3/missing.luau"
printf '%s\n' 'local m = require("./nope")' 'return m' > "$d/r3/missing-nonstrict.luau"
printf '%s\n' '--!strict' 'local name = "x"' 'return require("../r1/pkg/" .. name)' > "$d/r3/dynamic.luau"
rc=0
ok() { echo "ok   [$v] $*"; }
bad() { echo "FAIL [$v] $*"; rc=1; }
for v in "${vers[@]}"; do
	L=$MISE/installs/luau/$v/luau; A=$MISE/installs/luau/$v/luau-analyze
	(cd "$d/r1" && "$L" main.luau >/dev/null 2>&1) && ok "R1 init.luau: ./x=형제, @self/x=안" || bad "R1"
	out=$(cd "$d/r2" && "$L" tests/init.luau 2>&1); [[ $out == *"could not resolve child component \"helper\""* ]] && ok "R2 tests/init.luau 의 ./ 는 루트" || bad "R2: $out"
	out=$(cd "$d/r2b" && "$L" main.luau 2>&1); [[ $out == *"(ambiguous)"* ]] && ok "R2 X.luau+X/ → ambiguous" || bad "R2b: $out"
	out=$(cd "$d/r3" && "$A" missing.luau 2>&1); [[ $out == *"Unknown require: unsupported path"* ]] && ok "R3 strict: 없는 경로 잡음" || bad "R3a: $out"
	(cd "$d/r3" && "$A" missing-nonstrict.luau >/dev/null 2>&1) && ok "R3 nonstrict: 없는 경로 0건" || bad "R3b"
	(cd "$d/r1" && "$A" pkg/src/init.luau >/dev/null 2>&1) && ok "R3 오배선(./x→형제)은 strict 에서도 0건" || bad "R3c"
	out=$(cd "$d/r3" && "$A" dynamic.luau 2>&1); [[ $out == *"unsupported path"* ]] && ok "R3 strict: 동적 경로 거부" || bad "R3d: $out"
	out=$(cd "$d/r3" && "$L" dynamic.luau 2>&1); [ $? -eq 0 ] && ok "R4 런타임은 동적 경로 실행" || bad "R4: $out"
done
exit $rc
