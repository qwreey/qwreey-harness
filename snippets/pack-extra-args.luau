--!strict
-- 주장: 새 솔버는 `local function`/함수 리터럴로 정의한 함수에 인자를 "더" 넘기면 잡지 않는다. 모자란 인자는 잡는다.
--       같은 모양이라도 변수에 함수 타입 주석을 달거나 내장 함수면 잡는다. 옛 솔버는 모두 잡는다(짝: pack-extra-args-old.luau).
-- 근거: 실측(원인 소스 줄은 미확인. OverloadResolver.cpp isArityCompatible 은 오버로드 경로만 다룬다)
local function take(a: number, b: number) end
take(1, 2, 3) -- bug-present
take(1) -- expect-error: Argument count mismatch
local tbl = { f = function(a: number) end }
tbl.f(1, 2) -- bug-present
local typed: (number, number) -> () = take
typed(1, 2, 3) -- expect-error: expects 2 arguments, but 3 are specified
math.abs(1, 2) -- expect-error: Argument count mismatch
