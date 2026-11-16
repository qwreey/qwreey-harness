--!strict
-- 주장: type function 몸통은 같은 파일의 바깥 지역 변수(local 함수 포함)를 참조할 수 없다. 파서 단계의
--       SyntaxError 라서 그 파일의 type function 이 아니라 '그 줄'이 컴파일 실패로 보고된다.
--       런타임 유틸과 type function 안의 로직을 공유하려면 코드를 중복해야 한다(quad type-version-check 가 그렇게 함).
-- 근거: stl-luau/.claude/conventions.md:84 1), quad/type-version-check/src/init.luau:45-50, Luau Ast/src/Parser.cpp
--       "Type function cannot reference outer local"
local function helper(n: number): number
	return n + 1
end
type function UsesOuter(t: type): type
	local _ = helper(1) -- expect-error: Type function cannot reference outer local 'helper'
	return t
end
local _x: UsesOuter<number> = helper(1)
