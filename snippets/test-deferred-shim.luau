--!strict
--@run
--@run-opt=2
-- 주장: 순수 luau 에서 Roblox Deferred 시그널 배달을 흉내 내는 최소 심(shim)의 규칙과, 동기 mock 과 결과가 갈리는 지점.
--   규칙: Fire 는 연결별 큐에 적재, flush() 가 FIFO 로 비움(flush 중 새 발화는 같은 flush 뒤에 붙음), 같은 값 대입은 발화 안 함,
--   명시 Disconnect 는 대기분을 버림, 리스너 에러는 격리(다른 리스너는 돈다). 콜백은 배달 시점의 현재 값을 읽는다.
--   갈리는 점: 한 프레임에 "hello" → "world" 를 쓰면 동기 mock 은 콜백이 두 값을 차례로 보고, 지연 심은 두 번 모두 "world" 를 본다.
--   이 파일은 심 자체의 성질만 보인다. 엔진이 실제로 이렇게 배달하는지는 Studio 실측 기록(roblox-engine 스킬 signals-and-events.md)에 기대며, 심 결과는 엔진 실측이 아니다.
-- 근거: 원천 quad/.claude/audit/round13-e79-deferred-signals/README.md:1-30(심 설계·"엔진 실측 아님" 경고), 후보 Q-030·Q-018·Q-019·Q-023·Q-027

type Conn = { fn: (any) -> (), connected: boolean }
local function newProp(deferred: boolean, initial: any)
	local self = { value = initial, conns = {} :: { Conn }, queue = {} :: { Conn }, errors = {} :: { string } }
	local function deliver(c: Conn)
		if not c.connected then
			return -- 명시 Disconnect 된 연결의 대기분은 버린다
		end
		local ok, err = pcall(c.fn, self.value) -- 배달 시점의 현재 값
		if not ok then
			table.insert(self.errors, tostring(err)) -- 리스너 에러 격리
		end
	end
	function self.connect(fn: (any) -> ()): Conn
		local c = { fn = fn, connected = true }
		table.insert(self.conns, c)
		return c
	end
	function self.set(v: any)
		if v == self.value then
			return -- 같은 값은 발화하지 않는다
		end
		self.value = v
		for _, c in self.conns do
			if deferred then
				table.insert(self.queue, c)
			else
				deliver(c)
			end
		end
	end
	function self.flush()
		local i = 1
		while i <= #self.queue do -- flush 중 새로 쌓인 항목도 같은 flush 에서 처리
			deliver(self.queue[i])
			i += 1
		end
		table.clear(self.queue)
	end
	return self
end

local function scenario(deferred: boolean): { any }
	local p = newProp(deferred, "")
	local seen = {}
	p.connect(function(v)
		table.insert(seen, v)
	end)
	p.set("hello")
	p.set("world")
	p.set("world") -- 같은 값
	p.flush()
	return seen
end
local sync, def = scenario(false), scenario(true)
assert(#sync == 2 and sync[1] == "hello" and sync[2] == "world", table.concat(sync, ","))
assert(#def == 2 and def[1] == "world" and def[2] == "world", table.concat(def, ","))

-- 명시 Disconnect 는 대기분을 버리고, 리스너 에러는 다른 리스너를 막지 않는다
local p = newProp(true, 0)
local hits = 0
local c1 = p.connect(function()
	hits += 100
end)
p.connect(function()
	error("listener boom")
end)
p.connect(function()
	hits += 1
end)
p.set(1)
c1.connected = false
p.flush()
assert(hits == 1, `hits={hits}`)
assert(#p.errors == 1 and string.find(p.errors[1], "listener boom", 1, true) ~= nil, p.errors[1])
print("ok")
