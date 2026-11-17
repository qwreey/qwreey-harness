#!/usr/bin/env bash
# tf-cross-module.sh - check_snippets.py 는 파일 하나만 다루므로, 모듈 둘 이상이나 무한 루프가 필요한 type function
# 주장을 여기서 잰다. 기대와 어긋나면 rc=1. 사용: bash snippets/tf-cross-module.sh
#
# 주장:
#  M1 luau-analyze 0.734, 0.742: 정의 모듈이 한 번도 인스턴스화하지 않은 `export type function` 도 소비자에서 평가된다.
#  M2 luau-lsp 1.69.0 analyze(옵션 없음 = 모든 FFlag 켬): 프라이밍 안 한 함수는 소비자에서 진단 0건이다(조용히 무효).
#     `type _Prime = F<…>` 를 둔 함수는 평가된다. `--flag:LuauDoNotExportBrokenTypeFunction=false` 나 `--no-flags-enabled` 면 둘 다 평가된다.
#  M3 luau-lsp 1.70.1: 그 FFlag 가 없어졌다("Unknown FFlag", 분석은 계속). 프라이밍 없이도 평가된다.
#  M4 export 하지 않은 type function 을 `M.F<…>` 로 쓰면 "Unknown type". 그 함수를 감싼 export 별칭(`M.ViaHidden<T>`)은 동작한다.
#  M5 다른 모듈의 별칭은 type function 안에서 직접 못 쓴다(`M.Point` 는 outer local 'M' SyntaxError). 지역 별칭(`type Local = M.Point`)으로 받으면 쓸 수 있다.
#  M6 type function 안의 무한 루프는 luau-analyze 와 luau-lsp analyze 를 멈춘다(시간 한도 없음). 여기서는 timeout 5초로 잰다.
# 근거: quad/.claude/base/typing-limits.md 8.18(2026-09-16 정정), 8.22; quad/type-version-check/src/init.luau:229-235;
#       tbox/packages/tbox/scripts/analyze.luau:24-32; tbox/.vscode/settings.json
set -u
MISE=${MISE_DATA_DIR:-$HOME/.local/share/mise}
LSPDIR=$MISE/installs/github-johnny-morganz-luau-lsp
d=$(mktemp -d /tmp/luau-kb-tfx.XXXXXX)
trap 'rm -rf "$d"' EXIT
cat > "$d/lib.luau" <<'L'
--!strict
export type Point = { x: number }
export type function Echo(t: type): type
	return types.singleton(t:value())
end
type function Hidden(t: type): type
	return types.string
end
export type ViaHidden<T> = Hidden<T>
return {}
L
cat > "$d/libprimed.luau" <<'L'
--!strict
export type function Echo2(t: type): type
	return types.singleton(t:value())
end
type _Prime = Echo2<"p">
return {}
L
cat > "$d/use.luau" <<'L'
--!strict
local M = require("./lib")
local P = require("./libprimed")
local _a: M.Echo<"q"> = 5
local _b: P.Echo2<"q"> = 5
local _c: M.ViaHidden<number> = 5
type Local = M.Point
type function UsesImported(t: type): type
	return Local
end
local _d: UsesImported<number> = { x = "no" }
L
cat > "$d/usehidden.luau" <<'L'
--!strict
local M = require("./lib")
local _h: M.Hidden<number> = 5
L
cat > "$d/loop.luau" <<'L'
--!strict
type function Loop(t: type): type
	while true do end
	return t
end
local _a: Loop<number> = 1
L
fail=0
check() { # label, output, pattern, want(1=present,0=absent)
	if printf '%s' "$2" | grep -q -- "$3"; then got=1; else got=0; fi
	if [ "$got" = "$4" ]; then echo "ok   $1"; else echo "FAIL $1 (pattern '$3' present=$got want=$4)"; fail=1; fi
}
cd "$d" || exit 1
for v in 0.734 0.742; do
	A=$MISE/installs/luau/$v/luau-analyze
	out=$($A use.luau 2>&1)
	check "M1 [$v] unprimed Echo evaluated" "$out" "use.luau(4,25)" 1
	check "M4 [$v] ViaHidden works" "$out" "use.luau(6,33): TypeError: Expected this to be 'string'" 1
	check "M5 [$v] imported alias via local alias" "$out" "use.luau(11," 1
	out=$($A usehidden.luau 2>&1)
	check "M4 [$v] non-exported F is Unknown type" "$out" "Unknown type 'M.Hidden'" 1
	timeout 5 "$A" loop.luau >/dev/null 2>&1; rc=$?
	check "M6 [$v] infinite loop hangs (rc=124)" "$rc" "^124$" 1
done
if [ -x "$LSPDIR/1.69.0/luau-lsp" ]; then
	L=$LSPDIR/1.69.0/luau-lsp
	out=$($L analyze --platform=standard --flag:LuauSolverV2=true use.luau 2>&1)
	check "M2 [lsp 1.69.0] unprimed Echo silent" "$out" "use.luau(4,25)" 0
	check "M2 [lsp 1.69.0] primed Echo2 evaluated" "$out" "use.luau(5,26)" 1
	out=$($L analyze --platform=standard --flag:LuauSolverV2=true --flag:LuauDoNotExportBrokenTypeFunction=false use.luau 2>&1)
	check "M2 [lsp 1.69.0 flag=false] unprimed evaluated" "$out" "use.luau(4,25)" 1
fi
if [ -x "$LSPDIR/1.70.1/luau-lsp" ]; then
	L=$LSPDIR/1.70.1/luau-lsp
	out=$($L analyze --platform=standard --flag:LuauSolverV2=true use.luau 2>&1)
	check "M3 [lsp 1.70.1] unprimed Echo evaluated" "$out" "use.luau(4,25)" 1
	out=$($L analyze --platform=standard --flag:LuauSolverV2=true --flag:LuauDoNotExportBrokenTypeFunction=false use.luau 2>&1)
	check "M3 [lsp 1.70.1] flag removed" "$out" "Unknown FFlag: LuauDoNotExportBrokenTypeFunction" 1
	timeout 5 "$L" analyze --platform=standard --flag:LuauSolverV2=true loop.luau >/dev/null 2>&1; rc=$?
	check "M6 [lsp 1.70.1] infinite loop hangs (rc=124)" "$rc" "^124$" 1
fi
exit $fail
