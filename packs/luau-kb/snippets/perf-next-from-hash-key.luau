--!strict
--@run
-- 주장: next(t, k) 는 '내부 순서에서 k 다음'부터 돈다. k 가 해시부에 있으면 그 앞에 놓인 키는 k 보다 커도 건너뛴다.
--       그래서 "next(t, len) 부터 돌면 len 보다 큰 키를 다 찾는다"는 k 가 배열부에 있을 때만 맞다.
-- 근거: 후보 S-P34, stl-luau-doctor/.claude/base/perf-measurements.md 20절(무작위 대조 5000건 중 954건 오답)
local t: { [number]: number } = {}
for _, k in { 50, 60, 5, 70, 80, 90, 100 } do
	t[k] = k -- 1 이 없어 배열부가 생기지 않고 전부 해시부에 들어간다
end

local function keysAfter(start: number?): number
	local c = 0
	local k = next(t, start)
	while k ~= nil do
		if k > 5 then
			c += 1
		end
		k = next(t, k)
	end
	return c
end

local all = keysAfter(nil) -- 처음부터: 5 보다 큰 키 6개
local fromFive = keysAfter(5) -- 5 다음부터
assert(all == 6, "전체 순회는 6개를 본다")
assert(fromFive < all, "해시부의 5 다음부터 돌면 앞에 놓인 큰 키를 놓친다")

-- 대조군: 1..5 를 배열부에 채우면 next(t, 5) 가 해시부 키를 모두 본다
local u: { [number]: number } = {}
for i = 1, 5 do
	u[i] = i
end
for _, k in { 50, 60, 70, 80, 90, 100 } do
	u[k] = k
end
local c = 0
local k = next(u, 5)
while k ~= nil do
	c += 1
	k = next(u, k)
end
assert(c == 6, "배열부의 5 다음부터는 해시부 키를 모두 본다")
print("ok", all, fromFive, c)
