--!strict
-- 주장: 캐스트 `x :: T` 는 두 타입이 겹칠 수 있는지만 본다. 함수 타입끼리, 테이블 타입끼리는 모양이 전혀 달라도 통과한다.
--       서로소인 원시 타입(number -> string)만 "unrelated" 로 거부한다. 캐스트는 검사가 아니라 선언이다.
-- 근거: 실측. 원천 stl-luau-doctor/.claude/research/luau-source/README.md:125 (TypeChecker2.cpp:3256-3262) (후보 S-140)
local f = function(x: number): number return x end
local g = f :: (string) -> boolean -- bug-present
local t = ({ a = 1 } :: { a: number }) :: { b: string } -- bug-present
local s = (5 :: number) :: string -- expect-error: Cannot cast 'number' into 'string' because the types are unrelated
local _ = g, t, s
