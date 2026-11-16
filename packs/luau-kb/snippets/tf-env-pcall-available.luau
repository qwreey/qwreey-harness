--!strict
-- 주장: luau-analyze 0.734, 0.742 와 luau-lsp 1.70.1 에서는 type function 안의 pcall 이 동작한다.
--       `types` API 가 던지는 에러(`t:parameters()` 를 함수 아닌 타입에 부름)도 pcall 이 잡는다(ok=false).
--       luau-lsp 1.69.0 은 같은 파일에 "Unknown global 'pcall'" 과 "this function is not supported in type functions" 를 낸다.
--       quad 8.18 의 관측이 그 판이다.
--       pcall 없이 쓰려면 먼저 태그를 본다(`t:is("table")`). `unknown`/`any` 를 분해하면 런타임 에러이므로 앞에서 걸러 낸다.
--       print 출력은 사용 자리의 TypeError 로 보이므로 그 메시지 자체를 기대값으로 삼는다.
-- 근거: quad/.claude/base/typing-limits.md 8.18 첫 문단(1.69.0), quad/quad-roblox-types/src/Surface/init.luau:15-16
--       ("A type function has no pcall"), tbox/packages/tbox/src/types.luau:68,111 (BUG-05 unknown 가드)
type function UsesPcall(t: type): type
	local ok = pcall(function()
		return 1
	end)
	print("pcall ok=" .. tostring(ok))
	return types.number
end
type function SafeParams(t: type): type
	local ok = pcall(function()
		return t:parameters()
	end)
	print("api ok=" .. tostring(ok))
	return types.number
end
type function Props(t: type): type
	for _ in t:properties() do
	end
	return t
end
local _p: UsesPcall<"x"> = 1 -- expect-error: pcall ok=true
local _s: SafeParams<number> = 1 -- expect-error: api ok=false
local _u: Props<unknown> = 1 -- expect-error: expected self to be either a table or class, but got unknown
local _t: Props<{ a: number }> = { a = 1 }
