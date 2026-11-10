--!strict
-- 주장: (a) 유니온에서 nil 을 빼는 StripNil type function 은 동작한다(제네릭 <U>(Ref<U?>) -> U 로는 unknown 이 되는 자리의 대안).
--           신 솔버는 type function 본문도 검사하므로 지역 테이블에 { type } 주석이 필요하다.
--       (b) type function 안의 error() 는 "errored at runtime" 진단으로 보이지만, 결과 타입이 줄어들지 않아
--           사용 자리마다 'Bad<number>' 불일치가 덧붙는다. print + types.never 쪽이 메시지가 깔끔하다(typefn-diagnostic-only).
-- 근거: quad/.claude/base/typing-limits.md 8.14, §0 / luau-test/done/23 머리 주석 1번
type function StripNil(t: type): type
	if t:is("union") then
		local comps: { type } = {}
		for _, c in t:components() do
			if not c:is("nil") then
				table.insert(comps, c)
			end
		end
		if #comps == 1 then
			return comps[1]
		end
		return types.unionof(table.unpack(comps))
	end
	return t
end
local a: StripNil<number?> = 1
local b: StripNil<number?> = nil -- expect-error: Expected this to be 'number', but got 'nil'
local c: StripNil<(number | string)?> = "x"
local d: StripNil<(number | string)?> = nil -- expect-error: Expected this to be 'number | string', but got 'nil'
local e: StripNil<boolean> = true
type function Bad(t: type): type
	error("boom")
end
local f: Bad<number> = 1 -- expect-error: errored at runtime
