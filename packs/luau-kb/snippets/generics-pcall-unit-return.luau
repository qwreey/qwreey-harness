--!strict
-- 주장: 반환이 `()` 인 제네릭 함수를 pcall(f, …) 에 바로 넘기면 맞는 호출도 T 를 풀지 못해 거부된다(위양성).
--       반환이 있는 제네릭(each2)은 같은 모양으로 통과하고, 람다로 감싸 부르면 통과한다.
-- 근거: 실측. 원천 stl-luau-doctor/.claude/conventions.md:114, audit/review-trait-2026-10-21-bd/REPORT.md:11 (후보 S-137)
local function each<T>(xs: { T }, fn: (T) -> ()): ()
	for _, x in xs do fn(x) end
end
local function each2<T>(xs: { T }, fn: (T) -> ()): number
	return 1
end
local a = pcall(each, { 1, 2 }, function(x: number) end) -- expect-error: Expected this to be exactly 'T'
local b = pcall(each2, { 1, 2 }, function(x: number) end)
local c = pcall(function() each({ 1, 2 }, function(x: number) end) end)
local d = pcall(function() each({ 1, 2 }, function(x: string) end) end) -- expect-error
local _ = a, b, c, d
