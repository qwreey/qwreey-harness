--!strict
-- 주장: 태그 유니온에서 같은 스코프의 좁히기 '전에' 필드를 읽으면 그 스코프에서 좁히기가 죽는다.
--       좁히기 전 읽기가 없거나, 새 지역 별칭(local p = o)으로 좁히면 된다.
-- 근거: stl-luau/.claude/base/typing-limits.md "태그 유니온 — 좁히기 전에 필드를 읽으면"
type Opt<T> = { isPresent: true, value: T } | { isPresent: false, value: nil }
local function readFirst(o: Opt<number>)
	print(o.value)
	if o.isPresent then
		local v: number = o.value -- expect-error: Expected this to be 'number', but got 'number?'
	end
end
local function narrowOnly(o: Opt<number>)
	if o.isPresent then
		local v: number = o.value
	end
end
local function viaAlias(o: Opt<number>)
	print(o.value)
	local p = o
	if p.isPresent then
		local v: number = p.value
	end
end
