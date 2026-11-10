--!strict
--@run
-- 주장: 모듈 스코프의 맨 `function helper()` 는 전역 대입 `helper = function ...` 이다. --!strict 에서도 타입 진단이 0건이고 실행된다.
--       반면 함수 안에서 처음 대입하는 전역 변수는 "Unknown global" 로 잡힌다(대조군). 함수 선언 꼴이 더 조용하다.
-- 근거: quad scripts/test.sh:16,34(GlobalUsedAsLocal 린트를 게이트 실패로 취급), quad/.claude/conventions.md:348-355. 후보 Q-082
function helper(v: number): number
	return v
end
local M = {}
function M.run(): number
	return helper(1)
end
assert((getfenv() :: any).helper ~= nil, "helper 는 전역이다")
assert(M.run() == 1)
local function f(): number
	counter = 1 -- expect-error: Unknown global 'counter'
	return 1
end
local function g(): number -- 좋은 예: local function 은 지역이다
	return 2
end
assert((getfenv() :: any).g == nil and f() + g() == 3)
