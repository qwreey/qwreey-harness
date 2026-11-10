-- luau-perf 벤치 하네스. 방법론은 skills/luau-perf/references/benchmarking-method.md 를 따른다.
--
-- 한 그룹(Bench.run)은 "같은 일을 다른 모양으로 하는 케이스" 묶음이다. 첫 케이스가 기준(1.00)이다.
-- - 워밍업: 처음 WARMUP 라운드는 버린다(코드 캐시, 표 성장, 네이티브 컴파일 이후 상태를 잰다).
-- - 반복: ROUNDS 라운드. 라운드마다 케이스 순서를 한 칸씩 돌려 시간 표류가 한쪽에만 쌓이지 않게 한다.
-- - GC 통제: 각 측정 직전에 앞 결과를 놓고 collectgarbage("collect"). 앞 케이스의 쓰레기와 살아 있는 결과가 뒤 케이스 시간에 섞이지 않는다.
-- - 통계: 중앙값을 기준으로 비율을 낸다. 최소값도 함께 출력한다(원천 stl 문서는 최소값을 썼다).
--   할당이 많은 그룹은 GC 단계가 측정 구간에 들어가느냐에 따라 분포가 둘로 갈린다. control 이 1.00 에서 벗어나면
--   summarize.py --stat min 으로 최소값 비율도 본다.
-- - 음성 대조군: 기준 케이스를 이름만 바꿔 한 번 더 잰다(control). 이 비율이 1.00 에서 벗어난 만큼이 잡음 바닥이다.
-- - 시간: os.clock (CPU 시간, 초).
-- 출력(한 줄에 하나, 탭 구분, summarize.py 가 읽는다):
--   RESULT <그룹> <케이스> <중앙값 ms> <최소 ms> <중앙값 비율>
--   MEM    <그룹> <케이스> <객체당 바이트>
local Bench = {}

export type Case = {
	name: string,
	-- setup 이 있으면 측정 밖에서 부르고 그 반환값을 fn 에 넘긴다
	setup: (() -> any)?,
	fn: (any) -> any,
}

export type Opts = {
	rounds: number?,
	warmup: number?,
	gc: boolean?, -- false 면 측정 전 collect 를 하지 않는다(GC 비용 자체를 볼 때)
	control: boolean?, -- false 면 대조군을 넣지 않는다
}

local held: any = nil -- 결과를 붙잡아 계산이 버려지지 않게 한다

local function median(xs: { number }): number
	local s = table.clone(xs)
	table.sort(s)
	local n = #s
	if n % 2 == 1 then
		return s[(n + 1) // 2]
	end
	return (s[n // 2] + s[n // 2 + 1]) / 2
end

local function minOf(xs: { number }): number
	local m = math.huge
	for _, x in xs do
		if x < m then
			m = x
		end
	end
	return m
end

function Bench.run(group: string, cases: { Case }, opts: Opts?)
	local o: Opts = opts or {}
	local rounds = o.rounds or 11
	local warmup = o.warmup or 2
	local all = table.clone(cases)
	if o.control ~= false then
		local b = cases[1]
		table.insert(all, { name = "control", setup = b.setup, fn = b.fn })
	end
	local times: { { number } } = {}
	for i = 1, #all do
		times[i] = {}
	end
	local k = #all
	for r = 1, warmup + rounds do
		for j = 0, k - 1 do
			local idx = (r + j - 1) % k + 1
			local c = all[idx]
			held = nil -- 앞 케이스의 결과를 놓아 힙 크기가 다음 측정에 섞이지 않게 한다
			local state = if c.setup then c.setup() else nil
			if o.gc ~= false then
				collectgarbage("collect")
			end
			local t0 = os.clock()
			local v = c.fn(state)
			local dt = os.clock() - t0
			held = v
			if r > warmup then
				table.insert(times[idx], dt)
			end
		end
	end
	local base = median(times[1])
	for i, c in all do
		local med = median(times[i])
		print(string.format("RESULT\t%s\t%s\t%.4f\t%.4f\t%.4f", group, c.name, med * 1000, minOf(times[i]) * 1000, med / base))
	end
end

-- n 개를 만들어 붙잡은 채 collect 한 뒤 늘어난 힙을 객체 수로 나눈다.
function Bench.mem(group: string, name: string, n: number, make: (number) -> any)
	local keep = table.create(n)
	collectgarbage("collect")
	local before = collectgarbage("count")
	for i = 1, n do
		keep[i] = make(i)
	end
	collectgarbage("collect")
	local after = collectgarbage("count")
	held = keep
	print(string.format("MEM\t%s\t%s\t%.1f", group, name, (after - before) * 1024 / n))
	held = nil
end

-- 테스트 데이터용 결정적 난수(xorshift32). math.random 의 시드 차이를 없앤다.
function Bench.rng(seed: number): () -> number
	local s = seed
	return function()
		s = bit32.bxor(s, bit32.lshift(s, 13))
		s = bit32.bxor(s, bit32.rshift(s, 17))
		s = bit32.bxor(s, bit32.lshift(s, 5))
		return s
	end
end

function Bench.keep(v: any)
	held = v
end

return Bench
