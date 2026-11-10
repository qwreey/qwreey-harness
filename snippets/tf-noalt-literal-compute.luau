--!strict
-- 주장: 싱글턴 '값'으로 계산하는 검사(버전 문자열 패턴 대조 등)는 type function 으로만 된다.
--       타입 수준에는 문자열 연산도 조건부 타입도 없다. type function 은 `:value()` 와 string 라이브러리로 계산한다.
--       `pcall` 대신 태그를 먼저 본다(`t:is("singleton")`). 버전에 덜 민감하다.
-- 근거: quad/type-version-check/src/init.luau:141 (CheckVersion), quad/.claude/base/typing-limits.md 8.18 처방
type function CheckMajor(actual: type, pattern: type): type
	if not (actual:is("singleton") and pattern:is("singleton")) then
		print("CheckMajor: both arguments must be string literals")
		return types.never
	end
	local a = tostring(actual:value())
	local p = tostring(pattern:value())
	if string.match(a, "^%d+") ~= string.match(p, "^%d+") then
		print("version mismatch: " .. a .. " vs " .. p)
		return types.never
	end
	return types.singleton(true)
end
type _Ok = CheckMajor<"3.4.0", "3.*.*">
type _Bad = CheckMajor<"4.0.0", "3.*.*"> -- expect-error: version mismatch: 4.0.0 vs 3.*.*
type _Wide = CheckMajor<string, "3.*.*"> -- expect-error: must be string literals
