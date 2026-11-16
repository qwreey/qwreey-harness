--!strict
-- 주장: 제네릭 몸통 무검사(generics-body-unchecked) 위에 0.739 의 땜질(LuauSoundGenericMismatches)이 얹혔다. 기대 타입이
--       '정확히' 스코프 안의 T 일 때만 거절한다: 0.742 는 `return 5`(-> T)를 잡지만 0.734 는 못 잡는다. `T?` 반환, 지역 초기화,
--       T 값을 구체 자리에 넣는 방향은 두 버전 모두 무진단이다.
--       우회: 몸통을 구체 '탐침 타입'({ read __probeA: true })으로 쓰면 제네릭 갈래를 타지 않아 양방향이 검사된다.
-- 근거: 실측. 원천 stl-luau-doctor/.claude/research/luau-source/README.md 1-3, 1-5 절(0.742 소스 TypeChecker2.cpp, Subtyping.cpp:830-835),
--       stl conventions.md:75 (후보 S-138)
local function f<T>(x: T): T
	return 5 -- bug-present [<0.742] || expect-error: Expected this to be 'T', but got 'number' [>=0.742]
end
local function g<T>(x: T): T?
	return 123 -- bug-present
end
local function h<T>(x: T)
	local y: T = "s" -- bug-present
	local z: number = x -- bug-present
	local _ = y, z
end
type Probe = { read __probeA: true }
local function p(x: Probe): Probe
	local z: number = x -- expect-error: Expected this to be 'number', but got 'Probe'
	local _ = z
	return 5 -- expect-error: Expected this to be 'Probe', but got 'number'
end
local _ = f, g, h, p
