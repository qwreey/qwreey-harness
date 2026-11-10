--!strict
--@run
-- 주장: pcall 의 타입은 (boolean, R...) 이라 실패 분기의 둘째 값도 R(여기선 number)로 본다. 실제로는 에러 메시지(string)다.
--       pcall 은 넘긴 인자를 함수 파라미터와 대조한다.
-- 근거: EmbeddedBuiltinDefinitions.cpp `declare function pcall<A..., R...>(f: (A...) -> R..., ...: A...): (boolean, R...)`,
--       xpcall 위의 FIXME 주석("Since we can't represent the return value, we use (boolean, R1...)")
local function half(a: number): number
	if a < 0 then error("negative") end
	return a / 2
end
local ok, v = pcall(half, -1)
if not ok then
	local asNumber: number = v -- bug-present
	local asString: string = v -- expect-error: got 'number'
	assert(type(asNumber) == "string")
	local _ = asString
end
pcall(half, "x") -- expect-error: got 'string'
