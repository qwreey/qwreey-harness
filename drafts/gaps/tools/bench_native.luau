-- native codegen 벤치(초안). 실행: tools/bench_native.sh (choom 으로 감싸 -O1/-O2/--codegen 조합을 돈다)
-- 각 케이스는 같은 일을 하는 함수 쌍. 시간은 os.clock 최소값(ROUNDS 회), 단위 ms.
local ROUNDS = 7
local N = 2_000_000

local function untypedNum(a, b)
	return a * b + a - b * 0.5
end
local function typedNum(a: number, b: number): number
	return a * b + a - b * 0.5
end

local function untypedVec(v)
	return v.X * 2 + v.Y * 3 + v.Z
end
local function typedVec(v: vector): number
	return v.X * 2 + v.Y * 3 + v.Z
end

local function typedVecGivenTable(v: vector): number
	return v.X * 2 + v.Y * 3 + v.Z
end

local function strWork(i)
	local t = {}
	t[1] = tostring(i)
	t[2] = "x"
	return table.concat(t)
end

local function bench(name, fn)
	local best = math.huge
	for _ = 1, ROUNDS do
		local t0 = os.clock()
		fn()
		local dt = os.clock() - t0
		if dt < best then
			best = dt
		end
	end
	print(string.format("%-22s %8.2f ms", name, best * 1000))
end

local vec = vector.create(1, 2, 3)
local tbl = { X = 1, Y = 2, Z = 3 }
local sink = 0

bench("num untyped", function()
	local s = 0
	for i = 1, N do
		s += untypedNum(i, 3)
	end
	sink += s
end)
bench("num typed", function()
	local s = 0
	for i = 1, N do
		s += typedNum(i, 3)
	end
	sink += s
end)
bench("vec untyped", function()
	local s = 0
	for _ = 1, N do
		s += untypedVec(vec)
	end
	sink += s
end)
bench("vec typed", function()
	local s = 0
	for _ = 1, N do
		s += typedVec(vec)
	end
	sink += s
end)
bench("vec-annot given table", function()
	local s = 0
	for _ = 1, N do
		s += typedVecGivenTable(tbl :: any)
	end
	sink += s
end)
bench("table untyped", function()
	local s = 0
	for _ = 1, N do
		s += untypedVec(tbl)
	end
	sink += s
end)
bench("string/table alloc", function()
	local n = 0
	for i = 1, N // 4 do
		n += #strWork(i)
	end
	sink += n
end)
-- 테이블에 나중에 넣은 함수는 -O2 에서도 인라인되지 않는다(optimize-levels.md §3). 인라인을 빼고 타입 주석 효과만 본다
local F = {}
F.untypedVec = untypedVec
F.typedVec = typedVec
bench("vec untyped noinline", function()
	local s = 0
	for _ = 1, N do
		s += F.untypedVec(vec)
	end
	sink += s
end)
bench("vec typed noinline", function()
	local s = 0
	for _ = 1, N do
		s += F.typedVec(vec)
	end
	sink += s
end)
print("sink", sink > 0)
