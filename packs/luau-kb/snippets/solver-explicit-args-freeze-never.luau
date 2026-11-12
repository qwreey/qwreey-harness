--!strict
-- 주장: 세 가지 작은 규칙.
--   ① 명시 타입 인자를 일부만 주면(`two<<number>>` 인데 타입 변수가 둘) 솔버 내부 에러가 난다 → 제네릭 순서가 곧 공개 표면이다.
--   ② table.freeze({ … }) 결과의 필드 타입은 `read` 다(대입이 read-only 에러).
--   ③ never 를 돌려주는 함수 호출 뒤를 함수의 끝으로 보지 않는다 → `return raise(…)` 로 쓴다.
-- 근거: 실측. 원천 stl-luau-doctor/.claude/base/trait-system.md:34,44, archive/conventions-2026-11-04.md:542-543 (후보 S-146)
local function two<A, B>(a: A, b: B): B return b end
local x = two<<number>>(1, "s") -- expect-error: Internal error
local t = table.freeze({ a = 1 })
t.a = 2 -- expect-error: is read-only
local function raise(m: string): never error(m) end
local function f(n: number): number
	if n > 0 then return n end
	raise("neg")
end -- expect-error: Not all codepaths in this function return 'number'
local function g(n: number): number
	if n > 0 then return n end
	return raise("neg")
end
local _ = x, f, g
