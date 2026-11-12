--!strict
--@run
-- 주장: `local const x = 1` 은 문법 에러가 아니다. 'const' 라는 이름의 지역 변수 선언과 전역 대입 `x = 1` 두 문장으로 읽힌다.
--       --!strict 에서는 luau-analyze 가 "Unknown global 'x'" 로 잡는다(아래 표식). nonstrict 에서는 린트 경고뿐이고, 실행은 어느 쪽이든 된다.
-- 근거: decisions D-01 §2(0.734·0.742 실행), stl-luau/.claude/conventions.md:89. 후보 S-131 과 같은 묶음의 const 함정.
local const x = 1 -- expect-error: Unknown global 'x'
assert((getfenv() :: any).x == 1, "x 가 전역에 들어가야 한다")
const y = 2 -- 대조군: 올바른 const 선언은 지역이다
assert((getfenv() :: any).y == nil and y == 2)
