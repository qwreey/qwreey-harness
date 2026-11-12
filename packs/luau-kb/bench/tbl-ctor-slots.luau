-- 주장(S-P19, S-P20): 번호 칸은 테이블 생성자에 같이 적는다. {value=v} 를 만든 뒤 node[1]=… 를 대입하면 만들기가 몇 배 느리다.
--   레코드를 전부 번호 칸으로 쓰면 이름 필드보다 만들기·메모리·접근이 싸다. 이름 필드가 하나라도 있으면 해시부가 따로 할당된다.
-- 원 수치: stl perf 34절(-O2, 노드 20만): A {prev,next,value=} 6.8ms, A2 나중 대입 21.3ms(3배), B 전부 이름 6.6ms, C 전부 번호 4.4ms.
--   메모리 A 112B, B 176B, C 96B. 순회 A 0.55~0.67x(B 대비). 38절: 6칸 트리 노드 전부 번호 칸 만들기 0.44x, 224→144B.
local Bench = require("./lib/bench")

local N = 200_000

Bench.run("tbl-ctor-slots/build", {
	{ name = "B 전부 이름 {value,prev,next}", fn = function()
		local prev = nil
		for i = 1, N do
			local node = { value = i, prev = prev, next = false }
			prev = node
		end
		return prev
	end },
	{ name = "A 번호+이름 {prev, false, value=}", fn = function()
		local prev = nil
		for i = 1, N do
			local node = { prev, false, value = i }
			prev = node
		end
		return prev
	end },
	{ name = "A2 {value=} 뒤 node[1], node[2] 대입", fn = function()
		local prev = nil
		for i = 1, N do
			local node: any = { value = i }
			node[1] = prev
			node[2] = false
			prev = node
		end
		return prev
	end },
	{ name = "C 전부 번호 {prev, false, v}", fn = function()
		local prev = nil
		for i = 1, N do
			local node = { prev, false, i }
			prev = node
		end
		return prev
	end },
}, { rounds = 9 })

-- 순회: 같은 사슬을 따라가며 값 더하기
local function chainB()
	local prev = nil
	for i = 1, N do prev = { value = i, prev = prev } end
	return prev
end
local function chainA()
	local prev = nil
	for i = 1, N do prev = { prev, value = i } end
	return prev
end
local function chainC()
	local prev = nil
	for i = 1, N do prev = { prev, i } end
	return prev
end
local hb, ha, hc = chainB(), chainA(), chainC()
Bench.run("tbl-ctor-slots/walk", {
	{ name = "B n.prev / n.value", fn = function()
		local s, n = 0, hb
		while n do s += n.value; n = n.prev end
		return s
	end },
	{ name = "A n[1] / n.value", fn = function()
		local s, n = 0, ha
		while n do s += n.value; n = n[1] end
		return s
	end },
	{ name = "C n[1] / n[2]", fn = function()
		local s, n = 0, hc
		while n do s += n[2]; n = n[1] end
		return s
	end },
}, { rounds = 9 })

Bench.mem("tbl-ctor-slots/mem", "B 전부 이름 3필드", 20_000, function(i) return { value = i, prev = false, next = false } end)
Bench.mem("tbl-ctor-slots/mem", "A 번호 2 + 이름 1", 20_000, function(i) return { false, false, value = i } end)
Bench.mem("tbl-ctor-slots/mem", "A2 이름 1 뒤 번호 2 대입", 20_000, function(i)
	local t: any = { value = i }
	t[1] = false
	t[2] = false
	return t
end)
Bench.mem("tbl-ctor-slots/mem", "C 전부 번호 3칸", 20_000, function(i) return { false, false, i } end)
Bench.mem("tbl-ctor-slots/mem", "트리 노드 이름 3 + 번호 3", 20_000, function(i) return { false, false, false, key = i, value = i, red = true } end)
Bench.mem("tbl-ctor-slots/mem", "트리 노드 전부 번호 6칸", 20_000, function(i) return { false, false, false, i, i, true } end)
