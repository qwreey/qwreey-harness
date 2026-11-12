#!/usr/bin/env bash
# verify-require.sh — check_snippets.py 는 파일 하나만 다루므로, 모듈 여럿·symlink·.luaurc alias 가 필요한 require 주장을 여기서 잰다.
# 기대와 어긋나면 rc=1. 사용: bash snippets/verify-require.sh [luau 버전...]   (기본 0.734 0.742)
#
# 주장 (luau CLI = luau, luau-analyze. lsp = luau-lsp 1.70.1 analyze --platform=standard 새 솔버):
#  R1 풀리지 않는 require: --!strict 면 luau-analyze 가 그 줄에 "Unknown require" 를 낸다. 모듈 값은 any 라 이후 오용은 안 잡힌다.
#  R2 같은 파일이 nonstrict(지시어 없음)면 진단 0건, rc=0 — "거짓 클린". 런타임에서만 터진다.
#  R3 symlink 디렉터리를 거친 require: luau 런타임은 "could not resolve child component" 로 실패하고, luau-analyze(strict)는
#     "Unknown require" 를 낸다. luau-lsp 는 symlink 를 따라가 모듈을 풀고 진짜 타입 에러까지 잡는다(에디터는 깨끗한데 실행은 실패).
#  R4 .luaurc alias 값의 모양: "./lib" 나 절대 경로는 luau 런타임·luau-analyze·luau-lsp 모두 푼다. 접두 없는 "lib" 는 luau 런타임이
#     'could not jump to alias' 로 실패하고 luau-analyze 는 "Unknown require", luau-lsp 만 푼다(편집기 전용처럼 보이는 원인).
#  R5 Foo/init.luau 안의 "./Bar" 는 Foo 의 형제(폴더 밖)를 가리킨다. 폴더 안 Foo/Bar.luau 는 "@self/Bar" 로 부른다.
#     일반 파일에서 "@self/x" 는 실패한다.
#  R6 `luau-analyze src tests` 처럼 같은 모듈이 두 경로로 열리면 같은 진단이 './src/X.luau' 와 절대 경로로 두 번 보고된다.
# 근거(후보): Q-102, Q-103, Q-104, S-123, S-124, S-126, S-128 (claude-doctor .claude/audit/08, claude-doctor .claude/audit/09). 원천 서술 Q-104 "커스텀 alias 는
#   CLI 런타임에서 실패"는 alias 값에 ./ 가 없을 때만 맞다(quad .luaurc 가 "quad-base/src" 꼴).
set -u
MISE=${MISE_DATA_DIR:-/code/.local/share/mise}
LSP=$MISE/installs/github-johnny-morganz-luau-lsp/1.70.1/luau-lsp
vers=("$@"); [ $# -eq 0 ] && vers=(0.734 0.742)
d=$(mktemp -d /tmp/luau-kb-req.XXXXXX)
trap 'rm -rf "$d"' EXIT
fail=0
ok() { echo "ok   [$v] $*"; }
bad() { echo "FAIL [$v] $*"; fail=1; }
has() { grep -q -- "$2" <<<"$1"; }

mkdir -p "$d/real" "$d/proj" "$d/Foo" "$d/al/lib" "$d/al/app" "$d/dup/src" "$d/dup/tests"
printf 'return { n = 1 }\n' > "$d/real/mod.luau"
ln -s ../real "$d/proj/linked"
printf -- '--!strict\nlocal m = require("./missing")\nlocal s: string = m.n\nprint(s)\n' > "$d/strict.luau"
printf -- 'local m = require("./missing")\nlocal s: string = m.n\nprint(s)\n' > "$d/nonstrict.luau"
printf -- '--!strict\nlocal m = require("./linked/mod")\nlocal s: string = m.n\nprint(s)\n' > "$d/proj/link.luau"
printf -- '--!strict\nlocal B = require("./Bar")\nlocal S = require("@self/Bar")\nreturn { B = B, S = S }\n' > "$d/Foo/init.luau"
printf 'return { n = 1 }\n' > "$d/Foo/Bar.luau"
printf -- '--!strict\nlocal S = require("@self/Bar")\nreturn { S = S }\n' > "$d/Foo/selfonly.luau"
printf -- '--!strict\nlocal F = require("./Foo")\nprint(F)\n' > "$d/useFoo.luau"
printf -- 'local x = require("@self/x")\nprint(x)\n' > "$d/plainself.luau"
printf 'return { n = 1 }\n' > "$d/al/lib/x.luau"
printf -- '--!strict\nlocal x = require("@lib/x")\nlocal s: string = x.n\nprint(x.n)\n' > "$d/al/app/main.luau"
printf -- '--!strict\nlocal x: number = "a"\nreturn { x = x }\n' > "$d/dup/src/X.luau"
printf -- '--!strict\nlocal X = require("../src/X")\nprint(X.x)\n' > "$d/dup/tests/t.luau"

for v in "${vers[@]}"; do
	L=$MISE/installs/luau/$v
	o=$(cd "$d" && "$L/luau-analyze" strict.luau 2>&1); rc=$?
	if [ $rc -eq 1 ] && has "$o" "strict.luau(2,11): TypeError: Unknown require" && ! has "$o" "(3,"; then ok "R1 strict: require 줄만 Unknown require"; else bad "R1 rc=$rc $o"; fi
	o=$(cd "$d" && "$L/luau-analyze" nonstrict.luau 2>&1); rc=$?
	if [ $rc -eq 0 ] && [ -z "$o" ]; then ok "R2 nonstrict: 0건 rc=0 (거짓 클린)"; else bad "R2 rc=$rc $o"; fi
	o=$(cd "$d" && "$L/luau" nonstrict.luau 2>&1); rc=$?
	if [ $rc -ne 0 ] && has "$o" "could not resolve child component"; then ok "R2b 런타임에서는 실패"; else bad "R2b rc=$rc $o"; fi
	o=$(cd "$d/proj" && "$L/luau" link.luau 2>&1); rc=$?
	if [ $rc -ne 0 ] && has "$o" 'could not resolve child component "linked"'; then ok "R3 런타임은 symlink 를 따라가지 않음"; else bad "R3 rc=$rc $o"; fi
	o=$(cd "$d/proj" && "$L/luau-analyze" link.luau 2>&1)
	if has "$o" "Unknown require"; then ok "R3b analyze(strict)는 Unknown require"; else bad "R3b $o"; fi
	for val in "./lib" "$d/al/lib"; do
		echo "{\"aliases\": {\"lib\": \"$val\"}}" > "$d/al/.luaurc"
		o=$(cd "$d/al" && "$L/luau" app/main.luau 2>&1); rc=$?
		[ $rc -eq 0 ] && [ "$o" = 1 ] && ok "R4 alias '$val': 런타임 동작" || bad "R4 '$val' rc=$rc $o"
		o=$(cd "$d/al" && "$L/luau-analyze" app/main.luau 2>&1)
		has "$o" "(3,19): TypeError: Expected this to be 'string', but got 'number'" && ok "R4 alias '$val': analyze 가 모듈을 풂" || bad "R4a '$val' $o"
	done
	echo '{"aliases": {"lib": "lib"}}' > "$d/al/.luaurc"
	o=$(cd "$d/al" && "$L/luau" app/main.luau 2>&1); rc=$?
	if [ $rc -ne 0 ] && has "$o" 'could not jump to alias "lib"'; then ok "R4 alias 'lib'(접두 없음): 런타임 실패"; else bad "R4 lib rc=$rc $o"; fi
	o=$(cd "$d/al" && "$L/luau-analyze" app/main.luau 2>&1)
	has "$o" "(2,11): TypeError: Unknown require" && ok "R4 alias 'lib': analyze 는 Unknown require" || bad "R4a lib $o"
	o=$(cd "$d" && "$L/luau" useFoo.luau 2>&1); rc=$?
	if [ $rc -ne 0 ] && has "$o" 'error requiring module "./Bar"'; then ok "R5 init.luau 의 ./Bar 는 폴더 밖"; else bad "R5 rc=$rc $o"; fi
	# Foo/selfonly.luau 는 일반 파일이라 그 안의 @self/Bar 는 실패해야 한다
	printf -- '--!strict\nlocal F = require("./Foo/selfonly")\nprint(F.S.n)\n' > "$d/useSelf.luau"
	o=$(cd "$d" && "$L/luau" useSelf.luau 2>&1); rc=$?
	if [ $rc -ne 0 ] && has "$o" 'could not resolve child component "Bar"'; then ok "R5b 일반 파일의 @self/Bar 는 실패"; else bad "R5b rc=$rc $o"; fi
	printf -- '--!strict\nlocal F = require("./Foo")\nprint(F.S.n)\n' > "$d/useFooSelf.luau"
	sed -i 's|^local B = require("./Bar")$|local B = nil|' "$d/Foo/init.luau"
	o=$(cd "$d" && "$L/luau" useFooSelf.luau 2>&1); rc=$?
	if [ $rc -eq 0 ] && [ "$o" = 1 ]; then ok "R5c init.luau 의 @self/Bar 는 폴더 안"; else bad "R5c rc=$rc $o"; fi
	sed -i 's|^local B = nil$|local B = require("./Bar")|' "$d/Foo/init.luau"
	o=$(cd "$d" && "$L/luau" plainself.luau 2>&1); rc=$?
	[ $rc -ne 0 ] && ok "R5d 최상위 일반 파일의 @self 도 실패" || bad "R5d rc=$rc $o"
	o=$(cd "$d/dup" && "$L/luau-analyze" src tests 2>&1)
	n=$(grep -c "X.luau(2,19): TypeError" <<<"$o")
	if [ "$n" -eq 2 ] && has "$o" "./src/X.luau(2,19)"; then ok "R6 같은 진단이 두 경로로 2번"; else bad "R6 n=$n $o"; fi
done

v=lsp-1.70.1
if [ -x "$LSP" ]; then
	o=$(cd "$d/proj" && "$LSP" analyze --platform=standard --flag:LuauSolverV2=true link.luau 2>&1)
	if has "$o" "link.luau(3,19): TypeError: Expected this to be 'string'" && ! has "$o" "Unknown require"; then ok "R3c luau-lsp 는 symlink 를 따라감"; else bad "R3c $o"; fi
	echo '{"aliases": {"lib": "lib"}}' > "$d/al/.luaurc"
	o=$(cd "$d/al" && "$LSP" analyze --platform=standard --flag:LuauSolverV2=true app/main.luau 2>&1)
	if has "$o" "main.luau(3,19): TypeError" && ! has "$o" "Unknown require"; then ok "R4c luau-lsp 는 접두 없는 alias 도 풂"; else bad "R4c $o"; fi
else
	echo "skip [$v] luau-lsp 없음"
fi
exit $fail
