--!strict
-- 주장: 교집합 안의 제네릭이 반환에도 나오면, 글자 그대로 같은 제네릭 함수 타입끼리도 대입이 거부된다(위양성).
--       S 가 반환에 없거나 교집합이 없으면 통과한다. 다른 선언에서 온 같은 모양 타입이 안 맞는 증상과 같은 뿌리.
-- 근거: stl-luau/.claude/audit/luau-solver-issues/8-generic-in-intersection-and-return.luau, quad 8.43
local p2: <S>(S & S) -> S = ((nil :: any) :: <S>(S & S) -> S) -- expect-error: Expected this to be
local p3: <S>({ number } & S) -> S? = ((nil :: any) :: <S>({ number } & S) -> S?) -- expect-error: Expected this to be
local o1: <S>({ number } & S) -> () = ((nil :: any) :: <S>({ number } & S) -> ())
local o3: <S>(S) -> S = ((nil :: any) :: <S>(S) -> S)
