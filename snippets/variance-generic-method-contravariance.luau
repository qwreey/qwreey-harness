--!strict
-- 주장: 제네릭 메소드(<Self>(self: Self, v: T) -> Self)를 평범한 함수 타입 필드에 대조하면
--       파라미터의 반공변이 검사되지 않는다. 비제네릭 메소드는 정상으로 거부된다.
-- 근거: quad/.claude/base/typing-limits.md 8.9 끝 "H-321"
type HasSet = { read Set: (self: any, v: number?) -> any }
type GRef<T> = { Set: <Self>(self: Self, v: T) -> Self }
type PRef<T> = { Set: (self: any, v: T) -> any }
local g = (nil :: any) :: GRef<string>
local p = (nil :: any) :: PRef<string>
local viaGeneric: HasSet = g -- bug-present
local viaPlain: HasSet = p -- expect-error: Expected this to be 'HasSet', but got 'PRef<string>'
