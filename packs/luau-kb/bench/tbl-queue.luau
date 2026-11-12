-- 주장(S-P18): 배열부 크기는 늘어날 때 '채워진 비율'로 정해진다. 그래서
--   (1) 앞에서 nil 로 비우며 head/tail 번호가 계속 커지는 큐(PIL 두 인덱스 큐)는 길이를 유지해도 키가 배열부를 벗어나 느리다.
--   (2) table.remove(t, 1) 은 O(n) 이다.  (3) 음수 키로 앞에 넣으면 해시부로 간다.
--   처방: 링 버퍼, 또는 비우지 않고 head 번호만 올린 뒤 통째로 버리기.
-- 원 수치: stl perf 24절(-O2, 20만 번, 9회 최소): 길이 100 유지 시 링 8.65 vs 두 인덱스 26.1ms(3배), PushFront 만 5.62 vs 14.08ms.
--   40절(-O2): 앞을 nil 로 비우는 층별 순회 큐 1.7배(36.7~40.2 vs 17.2~22.1ms).
local Bench = require("./lib/bench")

local OPS = 200_000
local LEN = 100

local function ring()
	local cap = 128
	local buf = table.create(cap, 0)
	local head, size = 1, 0
	local acc = 0
	for i = 1, OPS do
		-- push
		local tail = head + size
		if tail > cap then tail -= cap end
		buf[tail] = i
		size += 1
		if size > LEN then
			-- pop
			acc += buf[head]
			buf[head] = 0
			head += 1
			if head > cap then head = 1 end
			size -= 1
		end
	end
	return acc
end

local function twoIndexClear()
	local q = {}
	local first, last = 1, 0
	local acc = 0
	for i = 1, OPS do
		last += 1
		q[last] = i
		if last - first + 1 > LEN then
			acc += q[first]
			q[first] = nil
			first += 1
		end
	end
	return acc
end

local function headNoClear()
	local q = {}
	local first, last = 1, 0
	local acc = 0
	for i = 1, OPS do
		last += 1
		q[last] = i
		if last - first + 1 > LEN then
			acc += q[first]
			first += 1
		end
	end
	return acc
end

local function removeFront()
	local q = {}
	local acc = 0
	for i = 1, OPS do
		q[#q + 1] = i
		if #q > LEN then
			acc += table.remove(q, 1)
		end
	end
	return acc
end

Bench.run("tbl-queue/len100", {
	{ name = "링 버퍼", fn = ring },
	{ name = "두 인덱스, 앞을 nil 로 비움", fn = twoIndexClear },
	{ name = "head 만 올림(안 비움)", fn = headNoClear },
	{ name = "table.remove(q, 1)", fn = removeFront },
}, { rounds = 9 })

-- 앞에 넣기만: 음수 키(해시부) vs 링 버퍼
Bench.run("tbl-queue/pushfront", {
	{ name = "링 버퍼 앞에 넣기", fn = function()
		local cap = 262144
		local buf = table.create(cap, 0)
		local head = 1
		for i = 1, OPS do
			head -= 1
			if head < 1 then head = cap end
			buf[head] = i
		end
		return buf
	end },
	{ name = "음수 키 first -= 1", fn = function()
		local q = {}
		local first = 1
		for i = 1, OPS do
			first -= 1
			q[first] = i
		end
		return q
	end },
}, { rounds = 9 })
