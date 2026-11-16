--!strict
-- 주장: type function 안의 Lua 재귀가 깊으면 "errored at runtime: ... stack overflow" 진단이 된다(검사기는 죽지 않는다).
--       type function 이 자기 자신을 부르는 얕은 재귀(문자열 길이 10)는 문제없다.
--       반대로 무한 루프는 검사기를 멈춘다. luau-analyze 와 luau-lsp analyze 모두 시간 한도가 없다.
--       그래서 스니펫으로 두지 않고 tf-cross-module.sh 의 loop 절에서 timeout 으로 잰다.
-- 근거: quad/.claude/base/typing-limits.md 5 "type function이 자기 자신을 호출하면 stack overflow",
--       quad/.claude/audit/type-recursive-issue-with-typeof/REPORT.md:41,224-236
type function Deep(t: type): type
	local function rec(n: number): number
		if n == 0 then
			return 0
		end
		return 1 + rec(n - 1)
	end
	rec(1000000)
	return t
end
type function Len(t: type): type
	local s = t:value() :: string
	if #s == 0 then
		return types.number
	end
	return Len(types.singleton(string.sub(s, 2)))
end
local _d: Deep<number> = 1 -- expect-error: stack overflow
local _l: Len<"abcdefghij"> = 1
local _l2: Len<"abcdefghij"> = "x" -- expect-error: Expected this to be 'number'
