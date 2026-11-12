--!strict
-- 주장: 새 솔버는 선언 주석(기대 타입)을 인자 없는 제네릭 호출 안으로 전파하지 않는다.
--       주석을 달면 조용히 새는 대신 Box<unknown, unknown> 불일치 에러(위양성)가 난다. f<<T>> 가 답.
-- 근거: stl-luau/.claude/base/typing-limits.md "1. 인자 없는 생성자"
type Box<K, V> = { data: { [K]: V } }
local function New<K, V>(): Box<K, V>
	return { data = {} }
end
local function Flat<T>(xs: { { T } }): { T }
	return {}
end
local annotated: Box<string, number> = New() -- expect-error: Box<unknown, unknown>
local explicit = New<<string, number>>()
explicit.data.x = "bad" -- expect-error: but got 'string'
local flat = Flat({})
local first: boolean = flat[1] -- expect-error: got 'unknown'
local flat2 = Flat<<number>>({})
local first2: boolean = flat2[1] -- expect-error: got 'number'
