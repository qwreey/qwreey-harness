--!strict
--@run
-- 주장: table.insert 는 조용히 틀리는 경우가 셋이다. ①②의 2값·③은 타입 검사가 잡지 않는다.
--       ① table.insert(t, nil) 은 아무것도 넣지 않는다 → 병렬 배열의 인덱스가 밀린다.
--       ② table.insert(t, f()) 에서 f 가 값 2개를 돌려주면 insert(t, pos, v) 오버로드가 된다(타입 검사 통과). 0개면 런타임 에러이고 --!strict 는 이것만 잡는다. → (f()) 로 한 값으로 자른다.
--       ③ 범위 밖 pos(0, #t+2 이상, 음수)는 던지지 않고 t[pos] = v 로 넣으며 #t 는 그대로다(Lua 5.3+ 와 다름). ipairs 로는 안 보인다.
-- 근거: devplorer dvr:2026-11-04-structure-outside.md:22, mrow-rv:275,291-300, moonwave-luau/.claude/conventions.md:122-123,
--       quad .claude/archive/v2-initial-implementation/pre-implementation-handtrace-round6.md:975-985. 후보 D-R32, M-14, Q-072
local function maybe(v: string?): string?
	return v
end
local names: { string? } = {}
table.insert(names, maybe(nil))
table.insert(names, "b")
assert(#names == 1 and names[1] == "b", "nil 을 넣은 자리가 사라져 b 가 1번이 된다")
names[2] = nil

local function two(): (number, string)
	return 1, "v"
end
local w: { any } = { "a", "b" }
table.insert(w, two())
assert(w[1] == "v" and w[2] == "a" and #w == 3, "pos=1, value='v' 로 해석된다")
local w2: { any } = { "a", "b" }
table.insert(w2, (two()))
assert(w2[3] == 1, "괄호로 한 값만 넘기면 끝에 붙는다")
local function none() end
assert(not pcall(function()
	table.insert({}, none()) -- expect-error: No overload
end))

local t: { any } = { 1, 2, 3 }
table.insert(t, 0, "z")
table.insert(t, 10, "w")
table.insert(t, -1, "n")
assert(#t == 3 and t[0] == "z" and t[10] == "w" and t[-1] == "n")
local seen = 0
for _, _ in ipairs(t) do
	seen += 1
end
assert(seen == 3)
