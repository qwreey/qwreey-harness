--!strict
--@solver=old
-- 주장: pack-extra-args.luau 의 짝. 옛 솔버는 넘친 인자를 모두 잡는다.
-- 근거: 실측 (--solver=old)
local function take(a: number, b: number) end
take(1, 2, 3) -- expect-error: Argument count mismatch
take(1) -- expect-error: Argument count mismatch
local tbl = { f = function(a: number) end }
tbl.f(1, 2) -- expect-error: Argument count mismatch
local typed: (number, number) -> () = take
typed(1, 2, 3) -- expect-error: expects 2 arguments, but 3 are specified
math.abs(1, 2) -- expect-error: Argument count mismatch
