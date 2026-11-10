--!strict
-- 주장: native 코드 생성은 타입 주석으로 특수화한다. --!native 파일(= -O2 + 타입 정보 수준 1)에서 x64 코드 크기(asmSize, 바이트):
--       파라미터 any 918 → vector 136, 로컬 주석(local w: vector = v) 160. 숫자 파라미터 any 253 → number 130.
--       vector? (옵셔널) 주석은 효과가 없고 오히려 크다(1029). any 주석은 주석 없음과 같다.
--       주석이 쓰이는 조건: 파라미터 주석은 -O2 이상이거나 타입 정보 수준 1(-t1, --!native, @native)일 때, 로컬·캐스트·upvalue 주석은 수준 1일 때만.
--       CLI -O1 만으로는 모든 주석이 무시된다(typed 896 = untyped).
--       tools/run_opt.sh 가 luau-compile --codegen --record-stats=function 으로 검사한다(x64).
-- 근거: Compiler/include/Luau/Compiler.h typeInfoLevel 주석, Compiler.cpp "if (options.typeInfoLevel >= 1 || options.optimizationLevel >= 2) buildTypeMap"
--       create.roblox.com/docs/en-us/luau/native-code-gen.md "Use type annotations"
local get: () -> any = function(): any return vector.create(1, 2, 3) end
local function untyped(v: any)
	return v.x + v.y + v.z
end
local function typed(v: vector)
	return v.x + v.y + v.z
end
local function optional(v: vector?)
	assert(v)
	return v.x + v.y + v.z
end
local function localAnn(v: any)
	local w: vector = v
	return w.x + w.y + w.z
end
local function castAnn()
	local w = get() :: vector
	return w.x + w.y + w.z
end
local function nums(a: number, b: number)
	return a * b + a
end
local function nonums(a: any, b: any)
	return a * b + a
end
return { untyped, typed, optional, localAnn, castAnn, nums, nonums }
