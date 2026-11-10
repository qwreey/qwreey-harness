--!strict
-- 주장: type function 실행 환경은 math/table/string/bit32/utf8/buffer 와 기본 라이브러리(pcall 포함)를 준다.
--       getfenv/setfenv/gcinfo/newproxy 는 막혀 있다: 정의 줄에 "Unknown global" 이 나고,
--       사용 자리에 "errored at runtime: … not supported in type functions" 가 난다.
--       type 이 아닌 값을 돌려주면 "returned a non-type value" 다.
--       어느 경우든 결과는 never 로 줄어든다. 그래서 사용 자리에 "reduced type is `never`" 불일치가 하나 더 붙는다.
-- 근거: Luau Analysis/src/TypeFunctionRuntime.cpp setTypeFunctionEnvironment / unavailableGlobals,
--       UserDefinedTypeFunction.cpp "returned a non-type value"
type function Fenv(t: type): type
	getfenv() -- expect-error: Unknown global 'getfenv'
	return t
end
type function NonType(t: type): type
	return 1 :: any
end
type function MathOk(t: type): type
	return types.singleton(string.format("%d", math.floor(2.5)))
end
local _e: Fenv<number> = 1 -- expect-error: not supported in type functions
local _n: NonType<number> = 1 -- expect-error: returned a non-type value
local _m: MathOk<number> = "2"
local _m2: MathOk<number> = "3" -- expect-error: Expected this to be '"2"'
