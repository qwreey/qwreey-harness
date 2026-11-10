--!strict
--@run
-- 주장: 약한 키 표 __mode = "k" 는 키가 수거되어도 해시 칸 배열이 줄지 않아 메모리가 남는다. "ks"(shrinkable)면 수거 뒤 줄어든다.
-- 근거: 후보 S-P35, stl-luau-doctor/.claude/base/perf-measurements.md 32절(리뷰어 실측: 40만 종에 +8MB, "ks" 면 0)
local collect = (_G :: any).collectgarbage

local function residue(mode: string): number
	collect("collect")
	local before = collect("count")
	local t = setmetatable({}, { __mode = mode }) :: { [any]: boolean }
	for _ = 1, 20_000 do
		t[{}] = true
	end
	for _ = 1, 3 do
		collect("collect")
	end
	local after = collect("count")
	assert(next(t) == nil, "키는 모두 수거됐다")
	return (after - before) * 1024 -- 표 하나가 남긴 바이트
end

local k = residue("k")
local ks = residue("ks")
assert(k > 100_000, `"k" 는 칸 배열을 붙잡는다: {k}`)
assert(ks < 10_000, `"ks" 는 줄어든다: {ks}`)
print("ok", k, ks)
