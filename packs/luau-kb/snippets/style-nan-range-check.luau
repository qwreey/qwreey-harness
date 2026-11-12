--!strict
--@run
-- 주장: NaN 과의 비교는 모두 거짓이다. 그래서 `if v < min or v > max then reject` 꼴의 경계 검사를 NaN 이 통과한다.
--       `if not (v >= min and v <= max) then reject` 로 쓰면 막힌다. math.huge 는 max 검사로만 막히므로 상한이 없으면 따로 막는다.
--       NaN 은 자기와 같지 않아 == 기반 중복 제거도 늘 통과한다.
-- 근거: tbox tbox-cr:54-58,111-115,164-168, quad .claude/base/source-state-plan.md:1081-1085. 후보 X-14, Q-080
local nan = 0 / 0
local function badCheck(v: number): boolean -- true = 받아들임
	if v < 0 or v > 1 then
		return false
	end
	return true
end
local function goodCheck(v: number): boolean
	if not (v >= 0 and v <= 1) then
		return false
	end
	return true
end
assert(badCheck(nan) == true, "NaN 이 나쁜 검사를 통과한다")
assert(goodCheck(nan) == false)
assert(goodCheck(0.5) and not goodCheck(2))
assert(nan ~= nan)
local function nonNegative(v: number): boolean
	return v >= 0
end
assert(nonNegative(math.huge), "하한만 있으면 inf 가 통과한다")
