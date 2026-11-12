--!strict
--@run
-- 주장: 제네릭 팩 `...: A...` 은 테이블에 담는 순간 타입을 잃는다. `{ ... }` 는 `{nil}`, `table.pack(...)` 은 인자 에러이고,
--       꺼내서 다시 넘기면 "Expected 'A...', got '...nil'" 이다. 팩은 값으로 저장할 수 없다.
--       우회: 호출부 시그니처에서 A... 로 검사를 받고, 저장은 `{ ... } :: any` 로 한 뒤 select("#") 로 개수를 따로 든다.
-- 근거: 실측. EmbeddedBuiltinDefinitions.cpp `pack: <V>(...V) -> ...` (V 하나로는 이질 팩을 못 받음)
local function deferBad<A...>(fn: (A...) -> (), ...: A...)
	local packed = table.pack(...) -- expect-error: Expected this to be '...V', but got 'A...'
	local listed = { ... }
	local probe: never = listed -- expect-error: {nil}
	fn(table.unpack(listed)) -- expect-error: got '...nil'
	local _ = packed
end
local function defer<A...>(fn: (A...) -> (), ...: A...): () -> ()
	local args: { any } = { ... } :: any
	local n = select("#", ...)
	return function()
		fn(table.unpack(args, 1, n))
	end
end
local seen = {}
local run = defer(function(a: number, b: string?, c: boolean)
	seen = { a, b, c }
end, 1, nil, true)
defer(function(a: number, b: string) end, 1, 2) -- expect-error: got 'number'
run()
assert(seen[1] == 1 and seen[2] == nil and seen[3] == true)
local _ = deferBad
