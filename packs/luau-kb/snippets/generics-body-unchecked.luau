--!strict
--@run
-- 주장: 새 솔버는 제네릭 함수 몸통에서 타입 변수 값을 구체 타입 자리에(또는 그 반대로) 넣어도 검사하지 않는다.
--       캐스트 없이 정적 타입 number 에 런타임 문자열이 든다. 옛 솔버는 둘 다 잡는다.
-- 근거: stl-luau/.claude/audit/luau-solver-issues/3-*.luau, 3b-*.luau, DRAFTS.md 3번(원인 Subtyping.cpp:830-835)
local function h<V>(v: V): number
	return v -- bug-present
end
local function needsNumber(n: number): number
	return n
end
local function g<V>(v: V): number
	return needsNumber(v) -- bug-present
end
local function store<K, V>(t: { [K]: V }, k: K, v: V)
	t[k] = v
end
local function wrap<K, V>(t: { [K]: V }, k: K)
	store(t, k, "bad") -- bug-present
end
local function mono(v: string): number
	return v -- expect-error: Expected this to be 'number', but got 'string'
end
local n: number = h("str")
local nums: { [string]: number } = {}
wrap(nums, "x")
assert(type(n) == "string" and type(g("s")) == "string" and (nums.x :: any) == "bad")
