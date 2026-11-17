#!/usr/bin/env bash
# rbx-require-cli.sh - luau CLI 의 require-by-string 규칙과, 잘못된 경로를 정적 검사가 잡는 조건을 잰다.
# check_snippets.py 는 파일 하나만 다루므로 여러 파일이 필요한 주장을 여기서 잰다. 기대와 어긋나면 rc=1.
# 사용: bash snippets/rbx-require-cli.sh
#
# 주장 (luau 0.734, 0.742, luau-lsp 1.70.1):
#  Q1 `Foo/init.luau` 는 폴더 자신이다. 그 안의 `./Bar` 는 폴더의 형제, `@self/Bar` 는 폴더 안 파일이다.
#  Q2 일반 파일(`main.luau`)의 `./x` 는 같은 디렉터리다. 일반 파일의 `@self/x` 는 실패한다.
#  Q3 `require("./Foo")` 는 `Foo/init.luau` 를 싣는다. `X.luau` 를 `X/init.luau` 로 바꿔도 바깥 경로는 그대로다.
#  Q4 대상에 `X.luau` 와 `X/` 가 같이 있으면 "could not resolve child component "X" (ambiguous)".
#     요구하는 파일의 폴더(`tests/`)와 같은 이름의 형제 파일(`tests.luau`)이 있으면 그 폴더 안 모든 require 가
#     "could not reset to requiring context (ambiguous)". `tests/init.luau` 와 `src/init.luau` 가 둘 다 있다는 것만으로는 안 난다.
#  Q5 `tests/init.luau` 안의 `./src` 는 저장소 루트의 src 다(`../src` 는 실패). 엔트리를 init.luau 로 지으면 경로 기준이 바뀐다.
#  Q6 `.luaurc` 의 일반 alias(`"lib": "./lib"`)는 CLI 런타임 require 에서 동작한다.
#  Q7 require 는 심볼릭 링크를 따라가지 않는다(런타임 "could not resolve child component").
#  Q8 풀리지 않는 require(잘못된 경로, symlink)를 luau-analyze 는 strict 에서 "Unknown require: unsupported path" 로 잡는다(rc=1).
#     nonstrict(지시어, .luaurc 없음)에서는 진단 0건, rc=0 이다. luau-lsp analyze 도 없는 파일에는 strict 에서 "Unknown require" 를 낸다(symlink 는 따라가 푼다, Q11).
#  Q9 경로가 틀렸는데 우연히 다른 모듈로 풀리면 strict 에서도 진단이 없다(다른 모듈을 조용히 싣는다).
#  Q10 Studio 실측(rbvm engine-behavior:68-83)과 같은 관대함: 끝 슬래시 "./Sib/", 빈 세그먼트 ".//Sib" 는 성공, "./" 단독은 실패,
#      alias 는 대소문자를 가리지 않는다("@Self", "@SELF"). 값을 돌려주지 않는 모듈은 "module must return a single value".
#  Q11 alias 값에 ./ 접두가 없으면("lib": "lib") luau 런타임은 'could not jump to alias' 로, luau-analyze 는 "Unknown require" 로 실패하고
#      luau-lsp 만 푼다. Q6 과 합치면 "alias 는 편집기 전용" 이라는 관측의 조건이 이것이다. luau-lsp 는 symlink 도 따라가 푼다(런타임은 실패).
#  같은 주제를 luau-verify 쪽 snippets/verify-require.sh 도 잰다(R3, R4).
# 근거: stl-luau-doctor/.claude/base/architecture.md:37-57,305-330; quad/.claude/base/project-setup-plan.md:112-176;
#       quad/scripts/relink.sh:4-6; mrow/review/REVIEW.md:1159-1187; tbox/CLAUDE.md:141-145; claude-doctor .claude/scopes/packs/luau-kb/audit/08 Q-101~Q-104, claude-doctor .claude/scopes/packs/luau-kb/audit/09 S-123~S-125, X-02, X-04
set -u
MISE=${MISE_DATA_DIR:-$HOME/.local/share/mise}
LSP=$MISE/installs/github-johnny-morganz-luau-lsp/1.70.1/luau-lsp
d=$(mktemp -d /tmp/luau-kb-rbxreq.XXXXXX)
trap 'rm -rf "$d"' EXIT
fail=0
check() { # label, output, pattern, want(1=present,0=absent)
	if printf '%s' "$2" | grep -q -- "$3"; then got=1; else got=0; fi
	if [ "$got" = "$4" ]; then echo "ok   $1"; else echo "FAIL $1 (pattern '$3' present=$got want=$4)"; fail=1; fi
}
w() { mkdir -p "$(dirname "$d/$1")"; printf '%s\n' "$2" > "$d/$1"; }

# Q1~Q3
w a/Bar.luau 'return "outer-Bar"'
w a/Foo/Bar.luau 'return "inner-Bar"'
w a/Foo/init.luau 'return { dot = require("./Bar"), self = require("@self/Bar") }'
w a/main.luau 'local f = require("./Foo"); print("Q1", f.dot, f.self); print("Q2", pcall(require, "@self/Bar"))'
w a/Moved/init.luau 'return "moved-dir"'
w a/use_moved.luau 'print("Q3", require("./Moved"))'
# Q4
w b/X.luau 'return "X-file"'
w b/X/init.luau 'return "X-dir"'
w b/main.luau 'print("Q4a", pcall(require, "./X"))'
w c/src/init.luau 'return "src-init"'
w c/tests/helper.luau 'return "helper"'
w c/tests/init.luau 'print("Q5a", pcall(require, "./src")); print("Q5b", pcall(require, "../src")); print("Q5c", pcall(require, "@self/helper"))'
w c2/src/init.luau 'return "src-init"'
w c2/tests/init.luau 'print("Q4b", pcall(require, "./src"))'
w c2/tests.luau 'return 1'
# Q6
w e/.luaurc '{"aliases": {"lib": "./lib"}}'
w e/lib/x.luau 'return "lib-x"'
w e/main.luau 'print("Q6", pcall(require, "@lib/x"))'
# Q7, Q8
w f/real/init.luau 'return { w = 1 }'
mkdir -p "$d/f/proj"; ln -s ../real "$d/f/proj/linked"
w f/proj/run.luau 'print("Q7", pcall(require, "./linked"))'
w f/proj/strict.luau '--!strict
local Lk = require("./linked")
local Nope = require("./Nope")
return nil'
w f/proj/loose.luau 'local Lk = require("./linked")
local Nope = require("./Nope")
local x: number = Lk.w
return nil'
# Q9: Pkg/init.luau 가 폴더 안 Util 을 부르려다 ./Util 을 썼는데 폴더 밖에 같은 이름 Util.luau 가 있다
w g/Util.luau '--!strict
return { name = "outer" }'
w g/Pkg/Util.luau '--!strict
return { name = "inner" }'
w g/Pkg/init.luau '--!strict
local U = require("./Util")
local n: string = U.name
return n'
w g/main.luau 'print("Q9", require("./Pkg"))'
# Q10
w h/Sib.luau 'return 1'
w h/Foo/Bar.luau 'return "b"'
w h/Foo/init.luau 'for _, p in { "./Sib/", ".//Sib", "./", "@Self/Bar", "@SELF/Bar" } do print("Q10", p, pcall(require, p)) end
return nil'
w h/NoReturn.luau 'local x = 1'
w h/main.luau 'require("./Foo"); print("Q10r", pcall(require, "./NoReturn"))'
# Q11
w i/.luaurc '{"aliases": {"lib": "lib"}}'
w i/lib/x.luau 'return "lib-x"'
w i/main.luau 'print("Q11", pcall(require, "@lib/x"))'
w i/typed.luau '--!strict
local x: number = require("@lib/x")
return nil'

for v in 0.734 0.742; do
	B=$MISE/installs/luau/$v
	out=$(cd "$d/a" && "$B/luau" main.luau 2>&1; cd "$d/a" && "$B/luau" use_moved.luau 2>&1)
	check "Q1 [$v] init ./ is folder sibling, @self is inside" "$out" "Q1	outer-Bar	inner-Bar" 1
	check "Q2 [$v] @self in plain file fails" "$out" "Q2	false" 1
	check "Q3 [$v] ./Moved loads Moved/init.luau" "$out" "Q3	moved-dir" 1
	out=$(cd "$d/b" && "$B/luau" main.luau 2>&1)
	check "Q4 [$v] X.luau + X/ -> ambiguous child" "$out" 'could not resolve child component "X" (ambiguous)' 1
	out=$(cd "$d/c" && "$B/luau" tests/init.luau 2>&1)
	check "Q5 [$v] tests/init.luau: ./src is repo-root src" "$out" "Q5a	true	src-init" 1
	check "Q5 [$v] tests/init.luau: ../src fails" "$out" "Q5b	false" 1
	check "Q5 [$v] tests/init.luau: @self/helper ok" "$out" "Q5c	true	helper" 1
	check "Q4 [$v] src/init + tests/init alone: no ambiguity" "$out" "ambiguous" 0
	out=$(cd "$d/c2" && "$B/luau" tests/init.luau 2>&1)
	check "Q4 [$v] tests.luau beside tests/ -> reset ambiguous" "$out" "could not reset to requiring context (ambiguous)" 1
	out=$(cd "$d/e" && "$B/luau" main.luau 2>&1)
	check "Q6 [$v] .luaurc alias works at runtime" "$out" "Q6	true	lib-x" 1
	out=$(cd "$d/f/proj" && "$B/luau" run.luau 2>&1)
	check "Q7 [$v] symlink not followed" "$out" 'could not resolve child component "linked"' 1
	out=$(cd "$d/f/proj" && "$B/luau-analyze" strict.luau 2>&1); rc=$?
	check "Q8 [$v] strict: Unknown require reported" "$out" "strict.luau(2,12): TypeError: Unknown require: unsupported path" 1
	check "Q8 [$v] strict: rc=1" "$rc" "^1$" 1
	out=$(cd "$d/f/proj" && "$B/luau-analyze" loose.luau 2>&1); rc=$?
	check "Q8 [$v] nonstrict: no TypeError" "$out" "TypeError" 0
	check "Q8 [$v] nonstrict: rc=0" "$rc" "^0$" 1
	out=$(cd "$d/g" && "$B/luau-analyze" Pkg/init.luau 2>&1); rc=$?
	check "Q9 [$v] wrong-but-resolving path: no TypeError" "$out" "TypeError" 0
	out=$(cd "$d/g" && "$B/luau" main.luau 2>&1)
	check "Q9 [$v] wrong-but-resolving path loads the outer module" "$out" "Q9	outer" 1
	out=$(cd "$d/h" && "$B/luau" main.luau 2>&1)
	check "Q10 [$v] trailing slash ok" "$out" "Q10	./Sib/	true	1" 1
	check "Q10 [$v] empty segment ok" "$out" "Q10	.//Sib	true	1" 1
	check "Q10 [$v] bare ./ fails" "$out" "Q10	./	false" 1
	check "Q10 [$v] alias case-insensitive" "$out" "Q10	@SELF/Bar	true	b" 1
	check "Q10 [$v] module without return value" "$out" "module must return a single value" 1
	out=$(cd "$d/i" && "$B/luau" main.luau 2>&1)
	check "Q11 [$v] alias value without ./ fails at runtime" "$out" 'could not jump to alias "lib"' 1
	out=$(cd "$d/i" && "$B/luau-analyze" typed.luau 2>&1)
	check "Q11 [$v] alias value without ./: analyze Unknown require" "$out" "Unknown require" 1
done
out=$(cd "$d/i" && "$LSP" analyze --platform=standard --flag:LuauSolverV2=true typed.luau 2>&1)
check "Q11 [lsp 1.70.1] alias value without ./ resolved by lsp" "$out" "Expected this to be 'number', but got 'string'" 1
out=$(cd "$d/f/proj" && "$LSP" analyze --platform=standard --flag:LuauSolverV2=true strict.luau 2>&1)
check "Q11 [lsp 1.70.1] lsp follows symlink (no Unknown require on line 2)" "$out" "strict.luau(2,12): TypeError: Unknown require" 0
check "Q8 [lsp 1.70.1] strict: Unknown require reported for a missing file" "$out" "strict.luau(3,14): TypeError: Unknown require" 1
exit $fail
