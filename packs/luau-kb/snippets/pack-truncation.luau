--!strict
-- 주장: 여러 값을 돌려주는 호출은 인자 목록·테이블 생성자의 "마지막" 자리에서만 펼쳐지고, 그 밖에서는 첫 값 하나로 잘린다.
--       괄호 `(f())` 와 `typeof(f())` 도 첫 값 하나다. 그래서 "튜플 타입"을 이름 붙여 둘 방법이 없다(팩은 값 자리에 못 둔다).
-- 근거: Lua 5.1 매뉴얼 §2.5 (adjust 규칙), luau.org/types/basic-types "Type packs"
local function two(): (number, string) return 1, "a" end
local function take(a: number, b: number) end
take(two()) -- expect-error: got 'string'
take(two(), 1)
local p = (two())
local ps: string = p -- expect-error: got 'number'
type X = typeof(two())
local x: X = "s" -- expect-error: got 'string'
local function retTwo(): (number, string) return two(), "x" end
local function retBad(): (number, string) return "x", two() end -- expect-error
local _ = retTwo, retBad
