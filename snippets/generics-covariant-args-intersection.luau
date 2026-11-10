--!strict
-- 주장: 공변(read 인덱서) 자리 둘에서 같은 T 를 풀 때 0.734 새 솔버는 합(|)이 아니라 교집합(&)을 골라
--       Concat(nums, strs) 가 { number & string } 이 되고 어느 쪽 대입도 통과했다. 0.742 는 number | string 으로 푼다.
--       불변 자리({ T }) 둘이면 섞임 자체가 "No valid instantiation" 에러.
-- 근거: stl-luau/.claude/base/typing-limits.md "공변 인자 둘에서 제네릭을 풀면 교집합" (luau 0.734 기록)
local function Concat<T>(...: { read [number]: T }): { T }
	return {}
end
local nums: { number } = { 1 }
local strs: { string } = { "a" }
local c = Concat(nums, strs)
local n: number = c[1] -- bug-present [<0.742] || expect-error: number | string [>=0.742]
local s: string = c[1] -- bug-present [<0.742] || expect-error: number | string [>=0.742]
local function Concat2<T>(a: { T }, b: { T }): { T }
	return {}
end
local c2 = Concat2(nums, strs) -- expect-error: No valid instantiation
