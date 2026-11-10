--!strict
--@run
-- 주장: 팩의 "개수"는 타입에 남지 않는 자리가 있다. 아래 셋은 정적 타입이 number 인데 런타임 값은 nil 또는 string 이다.
--   (1) table.unpack({1, 2}) 의 셋째 값   (2) `...number` 반환의 넘친 자리   (3) `{ f() }` 에서 f 가 (number, string) 을 반환할 때 둘째 원소
--   table.pack 은 원소 유니온을 정확히 준다.
-- 근거: EmbeddedBuiltinDefinitions.cpp `unpack: <V>(list: {V}, ...) -> ...V`, `pack: <V>(...V) -> { n: number, [number]: V }`,
--       BuiltinDefinitions.cpp MagicPack 주석 `table.pack(1, "foo") -> {| n: number, [number]: number | string |}`
local _, _, z = table.unpack({ 1, 2 })
local zn: number = z -- bug-present
local zs: string = z -- expect-error: got 'number'
local function rets(): ...number return 1, 2 end
local _, _, r3 = rets()
local rn: number = r3 -- bug-present
local function two(): (number, string) return 1, "a" end
local arr = { two() }
local an: number = arr[2] -- bug-present
local as: string = arr[1] -- expect-error: got 'number'
local t = table.pack(1, "a")
local tn: number = t[1] -- expect-error: got 'number | string'
local tc: number = t.n
assert(zn == nil and rn == nil)
assert(type(an) == "string")
assert(tc == 2)
local _ = zs, as, tn
