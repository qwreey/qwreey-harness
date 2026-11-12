--!strict
-- 주장: 선언된 테이블 타입의 제네릭 메서드 결과가 검사되지 않는 결함(solver-declared-generic-field, S17)의 조건은 `self: any` 다.
--       `self` 를 그 타입 자신으로 적으면 결과가 검사된다. 교집합(`C & B`)으로 부르든 단독으로 부르든 같다.
--       비제네릭 메서드는 `self: any` 여도 검사된다. 원천의 "교집합 값의 메서드 호출이 any 를 돌려준다"는 이 결함이 교집합에서 보인 것이다.
-- 근거: 실측(0.734, 0.742). 원천 quad/.claude/research/kit-packaging-plan.md:73 (후보 Q-126)
type B = { Name: string }
type A = { GetOrCreate: <T>(self: A, k: string, f: () -> T) -> T }
type C = { GetOrCreate: <T>(self: any, k: string, f: () -> T) -> T }
type D = { Get: (self: any, k: string) -> number }
local qa = (nil :: any) :: A & B
local sa: string = qa:GetOrCreate("x", function() return 1 end) -- expect-error: but got 'number'
local qc = (nil :: any) :: C & B
local sc: string = qc:GetOrCreate("x", function() return 1 end) -- bug-present
local qc1 = (nil :: any) :: C
local sc1: string = qc1:GetOrCreate("x", function() return 1 end) -- bug-present
local qd = (nil :: any) :: D & B
local sd: string = qd:Get("x") -- expect-error: but got 'number'
local _ = sa, sc, sc1, sd
