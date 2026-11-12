--!strict
-- 주장: 읽기·쓰기 필드 `x: V` 와 `y: V?` 가 같이 있으면 `T1<number?>` 를 넘겨도 V 를 풀지 못한다(V = number? 면 두 칸 모두 맞는데도).
--       불변 필드 둘이 하한 `number? | number`, 상한 `number? & number` 를 따로 걸기 때문이다. `y` 를 `read y: V?` 로 적으면 통과한다.
--       메서드 칸도 같은 이유로 `read` 를 붙이고 self 를 any 로 둔다(self 가 재귀 타입이면 read 여도 실패, 원천 기록).
-- 근거: 실측. 원천 stl-luau-doctor/.claude/audit/luau-solver-issues/DRAFTS.md:271-283, research/class-like/README.md:31-37 (후보 S-142)
type T1<V> = { x: V, y: V? }
local function f<V>(a: T1<V>) end
f((nil :: any) :: T1<number?>) -- expect-error: No valid instantiation could be inferred for generic type parameter V
f((nil :: any) :: T1<number>)
type T2<V> = { x: V, read y: V? }
local function g<V>(a: T2<V>) end
g((nil :: any) :: T2<number?>)
