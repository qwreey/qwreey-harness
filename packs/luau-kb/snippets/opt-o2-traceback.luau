--!strict
--!optimize 2
--@run
--@run-with --codegen => ok
-- 주장: 최적화 수준 2 에서 인라인된 함수는 스택 프레임이 없다. debug.traceback 에서 그 함수 이름 줄이 빠지고,
--   debug.info(1, "n") 는 인라인된 자리에서 바깥 함수 이름(여기선 최상위라 "")을 돌려준다. 줄 번호는 함수 몸통 줄이 남는다.
--   대조군: 가변 인자 함수는 인라인되지 않아 프레임과 이름이 그대로다. --codegen 도 같다.
-- 근거: luau.org/performance "Function inlining and loop unrolling"(debug.traceback 로 관측 가능하다고 명시), luau 0.734/0.742 실측
local function inner(): string
	return debug.traceback("tb", 1)
end
local function mid(): string
	local s = inner()
	return s
end
local tb = mid()
assert(not tb:find("function inner", 1, true), tb)
assert(not tb:find("function mid", 1, true), tb)
assert(tb:find(":10", 1, true), tb) -- inner 몸통 줄은 남는다

local function named(): string
	local n = debug.info(1, "n")
	return n
end
local got = named()
assert(got == "", got)

local function namedVararg(...: any): string
	local n = debug.info(1, "n")
	return n
end
local got2 = namedVararg()
assert(got2 == "namedVararg", got2)
