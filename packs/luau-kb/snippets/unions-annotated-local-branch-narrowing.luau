--!strict
-- 주장: 새 솔버는 주석을 단 지역(`local h: S<number> | St<number>`)도 분기마다 대입한 값의 타입으로 좁히고, 갈래가 합쳐지는 자리에서
--       그 유니온으로 되돌린다. 갈래마다 같은 이름의 제네릭 메서드가 있으면 합친 뒤 호출이 "Cannot call a value of the union type" 로 거부된다.
--       우회: 값을 if-식으로 만들어 한 타입으로 주석 단 지역에 담는다(아래 k), 또는 값을 돌려주는 함수로 뺀다.
-- 근거: 실측. 원천 devplorer/.claude/feedback/quad-upstream-2026-10-20.md:48-58 (후보 D-F30, 원천은 luau-lsp 1.69.0)
type S<T> = { kind: "s", v: T, Compute: <U>(self: S<T>, fn: (T) -> U) -> U }
type St<T> = { kind: "st", v: T, Compute: <U>(self: St<T>, fn: (T) -> U) -> U }
local given = (nil :: any) :: number | St<number> | nil
local mkS = (nil :: any) :: (number) -> S<number>
local mkSt = (nil :: any) :: (number) -> St<number>
local dflt = (nil :: any) :: St<number>
local h: St<number> | S<number>
if type(given) == "number" then h = mkS(given) elseif given ~= nil then h = given else h = dflt end
h:Compute(function(x) return x end) -- expect-error: Cannot call a value of the union type
local k: St<number> = if type(given) == "number" then mkSt(given) elseif given ~= nil then given else dflt
local r: number = k:Compute(function(x: number) return x end)
local _ = r
