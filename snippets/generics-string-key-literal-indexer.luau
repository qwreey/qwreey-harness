--!strict
--@run
-- 주장: 문자열 키 테이블 리터럴을 인덱서 타입 파라미터에 직접 넘기면 새 솔버가 값 타입을 보지 않는다.
--       같은 리터럴을 주석 단 지역에 담으면 잡힌다.
-- 근거: stl-luau/.claude/audit/luau-solver-issues/4-string-key-literal-indexer.luau
local function plain(t: { [string]: number }): number
	return t.x
end
local n: number = plain({ x = "bad" }) -- bug-present
local t: { [string]: number } = { x = "bad" } -- expect-error: Expected this to be 'number', but got 'string'
assert(type(n) == "string")
