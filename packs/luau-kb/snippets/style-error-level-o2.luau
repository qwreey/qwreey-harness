--!strict
--!optimize 2
--@run
-- 주장: -O2(라이브 Roblox 기본으로 알려짐, --!native 도 강제)에서는 로컬 헬퍼가 인라인되어 손으로 센 error(msg, n) 이 사용자 줄을 잃는다.
--       1) error(msg, 1) 은 인라인돼도 throw 한 줄을 가리킨다(내부 불변식에는 안전하다).
--       2) "라이브러리 소스가 아닌 첫 프레임" 을 debug.info 로 찾아 던지는 raise 헬퍼는 사용자 줄을 정확히 가리킨다.
--       사용자 코드는 다른 소스 이름(loadstring 의 "=user")으로 흉내 낸다. -O1 대조와 인라인 규칙은 opt-* 스니펫 담당(qwreey-harness .claude/scopes/packs/luau-kb/archive/research/drafts/gaps run_opt.sh B1 - B4).
-- 근거: decisions D-10 2, 정정, stl-luau/.claude/conventions.md:134-138, quad/.claude/base/architecture.md:520-529(스파이크 27). 후보 S-116, Q-097
local LIB_SOURCE = debug.info(1, "s")
local function raise(msg: string): never
	local level = 1
	while true do
		local s = debug.info(level, "s")
		if s == nil then
			break
		end
		if s ~= LIB_SOURCE and s ~= "[C]" then
			error(msg, level)
		end
		level += 1
	end
	error(msg, 0)
end
local Lib = {}
local function checkIndexCounted(i: any)
	if type(i) ~= "number" then
		error("Lib: index must be a number", 3) -- 나쁜 예: 손으로 센 level
	end
end
local function checkIndexRaise(i: any)
	if type(i) ~= "number" then
		raise("Lib: index must be a number") -- 좋은 예
	end
end
function Lib.atCounted(t: { any }, i: any): any
	checkIndexCounted(i)
	return t[i]
end
function Lib.atRaise(t: { any }, i: any): any
	checkIndexRaise(i)
	return t[i]
end
local function invariant(x: number)
	if x < 0 then
		error("Lib: invariant broken", 1) -- line 45
	end
end
function Lib.internal(x: number)
	invariant(x)
end
local load = (_G :: any).loadstring -- getfenv 를 쓰면 모듈 전체의 인라인이 꺼진다(luau-compile --remarks)
local userSrc = "local Lib = ...\nreturn function() return Lib.atCounted({}, 'x') end,\n function() return Lib.atRaise({}, 'x') end"
local userCounted, userRaise = load(userSrc, "=user")(Lib)
local _, eCounted = pcall(userCounted)
local _, eRaise = pcall(userRaise)
local _, eInv = pcall(Lib.internal, -1)
assert(not string.find(eCounted, "user:", 1, true), "-O2: 손으로 센 level 은 사용자 줄을 못 가리킨다: " .. eCounted)
assert(eRaise == "user:3: Lib: index must be a number", eRaise)
assert(string.find(tostring(eInv), ":45: Lib: invariant broken", 1, true), tostring(eInv))
