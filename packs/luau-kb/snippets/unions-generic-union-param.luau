--!strict
-- 주장: 유니온 파라미터 `{ read [number]: T } | Data<T>` 의 T 는, 인자 타입 안에 갈래와 같은 모양이 (그대로든 교집합 조각으로든) 있으면 풀린다.
--       갈래 필드에 다른 필드를 더한 '평평한' 테이블이면 T 가 unknown 이 된다(구조적으로는 갈래의 서브타입인데도).
--       또 유니온 파라미터에는 테이블 리터럴의 기대 타입이 내려가지 않아, 옵셔널 필드를 넓히는 리터럴이 거부된다(유니온이 아닌 파라미터는 통과).
-- 근거: 실측. 원천 stl-luau-doctor/.claude/base/typing-limits.md:371-386 (후보 S-145; 원천의 "같은 별칭일 때만"은 재현 범위가 더 넓다 - 정정 참고)
type Data<T> = { read n: number, read data: { read [number]: T } }
type Arr<T> = Data<T> & { read Len: (self: any) -> number }
type Flat<T> = { read n: number, read data: { read [number]: T }, read Len: (self: any) -> number }
type Box<T> = { v: T }
local function From<T>(a: { read [number]: T } | Data<T>): Box<T> return (nil :: any) end
local s1: string = From((nil :: any) :: Data<number>).v -- expect-error: but got 'number'
local s2: string = From((nil :: any) :: Arr<number>).v -- expect-error: but got 'number'
local leaked = From((nil :: any) :: Flat<number>)
local s3: string = leaked.v -- expect-error: but got 'unknown'
type R = { key: string, value: number? }
local function Recs(a: { read [number]: R } | Data<R>) end
Recs({ { key = "a", value = 1 } }) -- expect-error
local function Recs2(a: { read [number]: R }) end
Recs2({ { key = "a", value = 1 } })
local _ = s1, s2, s3
