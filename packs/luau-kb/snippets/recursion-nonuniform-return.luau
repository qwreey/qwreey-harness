--!strict
-- 주장: 제네릭 타입 Foo<T> 의 메소드가 '다른 타입 인자로 자기 자신'(Foo<U>)을 돌려주면(비균일 재귀),
--       인라인으로 선언한 메소드의 반환이 조용히 에러 타입이 되어 그 뒤 검사가 사라진다.
--       같은 메소드를 이름 붙은 함수로 선언하고 typeof(그 함수)로 필드 타입을 주면 다운스트림이 정확해진다.
--       같은 인자로만 재귀(-> Foo<T>)하면 문제없다.
-- 근거: quad/.claude/base/typing-limits.md 1(1) 3), H-24), RFC relax-recursive-type-restriction, luau-lang/luau#2380
type Tween<T> = { Value: T, Mapped: <U>(self: Tween<T>, fn: (T) -> U) -> Tween<U> }
local t = (nil :: any) :: Tween<number>
local mapped = t:Mapped(function(x: number) return tostring(x) end)
local leak: number = mapped.Value -- bug-present
local function Mapped2<T, U>(self: Tw2<T>, fn: (T) -> U): Tw2<U>
	return nil :: any
end
type Tw2<T> = { Value: T, Mapped: typeof(Mapped2) }
local t2 = (nil :: any) :: Tw2<number>
local m2 = t2:Mapped(function(x: number) return tostring(x) end)
local caught: number = m2.Value -- expect-error: Expected this to be 'number', but got 'string'
type Same<T> = { Value: T, Again: (self: Same<T>) -> Same<T> }
local s = (nil :: any) :: Same<string>
local uniform: number = s:Again().Value -- expect-error: Expected this to be 'number', but got 'string'
