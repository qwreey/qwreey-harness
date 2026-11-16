--!strict
-- 주장: 레코드의 키마다 값 타입을 바꾸는 사상('mapped type')은 type function 으로만 된다.
--       Luau 타입 문법에는 `{ [K in keyof T]: … }` 가 없다(SyntaxError). 대안은 손으로 다시 쓰는 것이다.
--       type function 은 properties() 를 돌며 바꾼다. 원본 `T` 는 그대로 두고 결과만 새 타입이다.
-- 근거: quad/.claude/base/typing-limits.md 5 (Store<T> -> { [K]: Source<V> } 합성, 2026-08-25 폐기),
--       tbox/packages/tbox/src/types.luau:63 (TObjectPropsFlatten), tbox/packages/tbox/src/schema/json/partial.luau:13 (PartialStatic)
type Source<T> = { Get: (self: Source<T>) -> T }
type function MapToSource(t: type): type
	local out = types.newtable()
	for k, p in t:properties() do
		out:setproperty(k, Source(p.read))
	end
	return out
end
type Rec = MapToSource<{ hp: number, name: string }>
local r: Rec = nil :: any
local _hp: number = r.hp:Get()
local _bad: string = r.hp:Get() -- expect-error: Expected this to be 'string', but got 'number'
type Mapped<T> = { [K in keyof<T>]: Source<T[K]> } -- expect-error
