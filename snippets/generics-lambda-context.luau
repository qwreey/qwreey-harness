--!strict
-- 주장: 제네릭 호출의 인자로 넘긴 함수 리터럴에는 기대 함수 타입이 흘러들지 않는다.
--       (a) 몸통이 파라미터를 제약하면 "Consider placing the following annotations" 에러
--       (b) 명시 타입 인자 f<<T, U>> 를 주면 파라미터가 그 타입으로 정해진다
--       (c) 분기마다 다른 타입을 돌려주면 첫 return 이 결과 타입을 굳힌다 — 반환 주석이나 <<T, U?>> 로 푼다
-- 근거: stl-luau/.claude/base/typing-limits.md "콜백 파라미터 주석도 없앱니다", "첫 return 이 결과 타입을 굳힘"
local function Map<T, U>(xs: { T }, f: (T) -> U): { U }
	local out = {}
	for i, x in xs do
		out[i] = f(x)
	end
	return out
end
local nums = { 1, 2, 3 }
local a = Map(nums, function(v) return v * 2 end) -- expect-error: Consider placing the following annotations
local b = Map<<number, number>>(nums, function(v) return v.foo end) -- expect-error: does not have key 'foo'
local c = Map(nums, function(v: number) if v > 1 then return nil end return v end) -- expect-error: Expected this to be 'nil', but got 'number'
local d = Map(nums, function(v: number): number? if v > 1 then return nil end return v end)
local e = Map<<number, number?>>(nums, function(v) if v > 1 then return nil end return v end)
