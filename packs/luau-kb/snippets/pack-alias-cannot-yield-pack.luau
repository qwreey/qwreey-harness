--!strict
-- 주장: 별칭은 팩을 결과로 낼 수 없고(`type P<T...> = T...`), 팩에서 앞 원소를 떼어 낼 수도 없다(`Car<S...>`).
--       팩 파라미터 뒤에 일반 타입 인자를 둘 수 없다.
-- 근거: rfcs docs/syntax-type-alias-type-packs.md "Drawbacks", "Multiple type pack parameters"
type P<T...> = T... -- expect-error: type pack is not allowed in this context
type Car<T, U...> = T
type X = Car<number, string, boolean>
local x: X = "s" -- expect-error: got 'string'
type Y<S...> = Car<S...> -- expect-error: expects at least 1 type argument
type Two<T..., U...> = (T...) -> U...
type Bad<S...> = Two<S..., number, string> -- expect-error
type Ok = Two<(number, string), (boolean)>
local ok: Ok = function(_: number, _: string) return true end
local _ = ok
