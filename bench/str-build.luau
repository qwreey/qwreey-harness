-- 주장(M-04, M-05, D-R28): 문자열 성능 기준선.
--   s ..= c 누적은 O(n^2) 이다(길이를 두 배로 하면 시간이 약 네 배). 표에 모아 table.concat 한 번이면 선형이다.
--   숫자 목록 파싱은 string.gmatch + tonumber 가 Luau 로 글자마다 도는 파서보다 몇 십 배 빠르다(C 로 내려가는 쪽이 이긴다).
--   .-.-.- 같은 패턴은 역추적이 다항 시간이다(길이 조금에 시간이 급증).
-- 원 수치: mrow REVIEW(0.734): ..= 10만자 0.80s, 20만 3.07s, 40만 12.76s; concat 0.035→0.150s. gmatch+tonumber 약 125ns/항목, 글자 파서 약 40배.
--   devplorer(0.734): .-.-.-.-.-.-b 12자 0.3ms, 18자 3ms, 24자 15ms, 60자 100초 초과.
local Bench = require("./lib/bench")

local function concatGrow(n: number)
	return function()
		local s = ""
		for _ = 1, n do s ..= "x" end
		return #s
	end
end
local function concatTable(n: number)
	return function()
		local parts = table.create(n)
		for i = 1, n do parts[i] = "x" end
		return #table.concat(parts)
	end
end
-- 같은 그룹 안에서 n 을 두 배씩: 기준은 ..= 1만자. 2만·4만의 비율이 약 4·16 이면 O(n^2)
Bench.run("str-build/concat", {
	{ name = "..= 1만자", fn = concatGrow(10_000) },
	{ name = "..= 2만자", fn = concatGrow(20_000) },
	{ name = "..= 4만자", fn = concatGrow(40_000) },
	{ name = "table.concat 1만자", fn = concatTable(10_000) },
	{ name = "table.concat 4만자", fn = concatTable(40_000) },
}, { rounds = 7 })

local nums = table.create(100_000)
for i = 1, 100_000 do nums[i] = tostring(i * 7) end
local csv = table.concat(nums, ",")
Bench.run("str-build/parse", {
	{ name = "gmatch + tonumber", fn = function()
		local s = 0
		for w in string.gmatch(csv, "[^,]+") do s += tonumber(w) :: number end
		return s
	end },
	{ name = "글자마다 string.byte 파서", fn = function()
		local s, cur = 0, 0
		local byte = string.byte
		for i = 1, #csv do
			local b = byte(csv, i)
			if b == 44 then
				s += cur
				cur = 0
			else
				cur = cur * 10 + (b - 48)
			end
		end
		return s + cur
	end },
	{ name = "글자마다 string.sub 파서", fn = function()
		local s, cur = 0, 0
		for i = 1, #csv do
			local c = string.sub(csv, i, i)
			if c == "," then
				s += cur
				cur = 0
			else
				cur = cur * 10 + (tonumber(c) :: number)
			end
		end
		return s + cur
	end },
}, { rounds = 7 })

local pat = ".-.-.-.-.-.-b"
local function backtrack(len: number)
	local subject = string.rep("a", len)
	return function()
		return string.find(subject, pat)
	end
end
Bench.run("str-build/backtrack", {
	{ name = "12자", fn = backtrack(12) },
	{ name = "18자", fn = backtrack(18) },
	{ name = "24자", fn = backtrack(24) },
}, { rounds = 5, control = false })
