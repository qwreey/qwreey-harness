--!strict
-- 주장: 교집합 타입 컨테이너를 `for … in c do` 로 돌면(인덱서 경유) 루프 변수 타입을 잃는다(0건).
--       메서드가 이터레이터 삼중항을 돌려주면(`for i, v in c:Iter()`) for-in 이 그 함수의 반환 타입을 보므로 타입이 산다.
--       이터레이터 함수는 `(number, T)` 로 선언한다. 정직하게 `(number?, T?)` 로 적으면 루프 변수가 옵셔널이 된다(내장 ipairs 도 앞쪽 꼴).
-- 근거: 실측. 원천 stl-luau-doctor/.claude/base/perf-measurements.md:76-91 (spikes/35, 37) (후보 S-P50)
type Arr<T> = { read [number]: T } & { read n: number }
type Iterable<T> = Arr<T> & { Iter: (self: any) -> ((any, number) -> (number, T), any, number) }
type IterOpt<T> = Arr<T> & { Iter: (self: any) -> ((any, number) -> (number?, T?), any, number) }
local a = (nil :: any) :: Iterable<number>
for i, v in a:Iter() do
	local s: string = v -- expect-error: Expected this to be 'string', but got 'number'
	local k: number = i + v
	local _ = s, k
end
local b = (nil :: any) :: IterOpt<number>
for _, v in b:Iter() do
	local k: number = v + 1 -- expect-error: Operator '+' could not be applied
	local _ = k
end
for _, v in a do
	local s: string = v -- bug-present
	local _ = s
end
