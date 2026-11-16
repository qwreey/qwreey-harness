--!strict
--@run
--@run-opt=2
-- 주장: 시간에 기대는 로직(디바운스, 스로틀, 타이머)은 시계와 예약 함수를 주입하면 순수 luau CLI 에서 결정적으로 시험할 수 있다.
--   luau CLI 에는 task 도 이벤트 루프도 없으므로(typeof(task) == "nil"), 실제 시간을 기다리는 테스트는 만들 수조차 없다.
--   가상 시계는 advance(dt) 로 시간을 옮기고, 그 시점까지 예약된 콜백을 시각 순서대로 돌린다. 실기기 task.wait 의 지터와 무관하다.
-- 근거: 원천 quad/.claude/audit/sugar-studio-2026-09-08.md:23, quad/.claude/base/debounce-throttle-plan.md:45-47, 후보 Q-121, Q-070

type Clock = { now: () -> number, delay: (number, () -> ()) -> (), advance: (number) -> () }
local function newClock(): Clock
	local t = 0
	type Job = { at: number, seq: number, fn: () -> () }
	local pending: { Job } = {}
	local seq = 0
	local clock = {} :: Clock
	clock.now = function()
		return t
	end
	clock.delay = function(dt: number, fn: () -> ())
		seq += 1
		table.insert(pending, { at = t + dt, seq = seq, fn = fn })
	end
	clock.advance = function(dt: number)
		local target = t + dt
		while true do
			table.sort(pending, function(a: Job, b: Job)
				return if a.at == b.at then a.seq < b.seq else a.at < b.at
			end)
			local nxt = pending[1]
			if not nxt or nxt.at > target then
				break
			end
			table.remove(pending, 1)
			t = nxt.at
			nxt.fn()
		end
		t = target
	end
	return clock
end

-- 시험 대상: 마지막 호출 뒤 wait 초 동안 조용하면 한 번 부르는 디바운스(시계 주입)
local function debounce(clock: Clock, wait: number, fn: (any) -> ()): (any) -> ()
	local gen = 0
	return function(v)
		gen += 1
		local my = gen
		clock.delay(wait, function()
			if my == gen then
				fn(v)
			end
		end)
	end
end

assert(typeof((_G :: any).task) == "nil", "luau CLI 에는 task 가 없다")
local clock = newClock()
local got = {}
local d = debounce(clock, 0.5, function(v)
	table.insert(got, `{v}@{clock.now()}`)
end)
d("a")
clock.advance(0.3)
d("b")
clock.advance(0.3) -- a 는 무효화, b 는 아직
assert(#got == 0, table.concat(got, ","))
clock.advance(0.2) -- b 가 0.8 에 발화
assert(#got == 1 and got[1] == "b@0.8", table.concat(got, ","))
print("ok")
