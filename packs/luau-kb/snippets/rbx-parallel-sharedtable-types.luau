--!strict
--@lsp-roblox
-- 주장: SharedTable 은 [string | number]: any 인덱서를 가진 extern 타입이다. 키 종류는 막지만 값 종류(함수 금지)와 키 범위(0 이상 2^32 미만 정수)는 막지 못한다.
--       정의의 __iter 는 키를 number 로 선언해, 문서상 허용되는 문자열 키가 반복에서 number 로 보인다.
--       새 솔버는 공식 문서 예제 그대로의 `for k, v in st do` 를 "__iter metamethod must return" 으로 거부한다(옛 솔버 짝: rbx-parallel-sharedtable-iter-old-solver.luau).
-- 근거: typedefs/globalTypes.d.luau `declare extern type SharedTable`, `declare SharedTable`; create.roblox.com reference/engine/datatypes/SharedTable.md (2026-11-10)
local SharedTableRegistry = game:GetService("SharedTableRegistry")

local st = SharedTable.new({ x = 1, name = "a" })
st.y = 2
st[1] = "first"
st[true] = 1 -- expect-error
st.f = function() end -- bug-present
st[-1] = "negative key" -- bug-present
local nested = SharedTable.new({ f = function() end }) -- bug-present

local old: number = SharedTable.increment(st, "x", 1)
local oldS: string = SharedTable.increment(st, "x", 1) -- expect-error
SharedTable.update(st, "x", function(v) return v + 1 end)
local snap = SharedTable.cloneAndFreeze(st, true)
SharedTable.clone(st, 1) -- expect-error
local n: number = SharedTable.size(st)

for k, v in st do -- expect-error: __iter metamethod must return
	local key: string = k -- expect-error: number
	local val: boolean = v
end

local reg: SharedTable = SharedTableRegistry:GetSharedTable("World")
SharedTableRegistry:SetSharedTable("World", nil)
SharedTableRegistry:SetSharedTable("World", {}) -- expect-error
