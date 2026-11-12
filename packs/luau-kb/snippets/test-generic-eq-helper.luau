--!strict
-- 주장: 손으로 만든 단언 헬퍼 `eq<T>(actual: T, expected: T)` 는 두 인자의 타입이 달라도 타입 에러를 내지 않는다.
-- T 가 두 인자의 합(여기서는 number | string)으로 풀리기 때문이다. 정적 검사를 원하면 호출 자리에서 명시 타입 인자를
-- 주거나(`eq<<number>>`), 타입을 고정한 헬퍼(`eqNumber`)를 쓴다.
-- 덧붙여: pcall 이 돌려주는 에러 값은 any 라 `local s: number = err` 도 검사되지 않는다. 에러 값은 tostring 으로 받는다.
-- 근거: 이 파일(luau-analyze 0.734, 0.742; luau-lsp 1.70.1 새 솔버 동일). 런타임 판정은 그대로 동작한다(== 가 false).

local function eq<T>(actual: T, expected: T, label: string?)
	assert(actual == expected, label)
end
local function eqNumber(actual: number, expected: number)
	assert(actual == expected)
end

local n: number = 1
local function _cases()
	eq(n, "1") -- bug-present
	eq<<number>>(n, "1") -- expect-error: Expected this to be 'number', but got 'string'
	eqNumber(n, "1") -- expect-error: Expected this to be 'number', but got 'string'
end
eq(n, 1)
local _, err = pcall(error, "boom")
local wrongType: number = err -- bug-present
local asText: string = tostring(err)
local _n: number = asText -- expect-error: Expected this to be 'number', but got 'string'
