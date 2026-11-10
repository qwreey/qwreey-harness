--!strict
-- 주장: GetAttribute 는 `unknown?` 이라 쓰기 전에 typeof/type 으로 좁혀야 한다. typeof 는 Roblox 데이터 타입("Vector3")까지,
--       type 은 Luau 기본 타입("number", "userdata")까지만 좁힌다. GetAttributes 는 `{ [string]: unknown }`.
--       SetAttribute 의 값은 `any` 라 지원하지 않는 타입(테이블, Instance)도 정적으로 통과한다(런타임 에러).
--       `typeof(u) == "Part"` 는 타입 검사기가 Part 로 좁히지만 런타임 typeof 는 인스턴스에 "Instance" 만 돌려준다(이 분기는 죽은 코드).
-- 근거: create.roblox.com/.../classes/Instance.md (GetAttribute: Variant, SetAttribute: "unsupported type ... error"),
--       .../studio/properties.md (attribute 지원 타입 목록), .../globals/RobloxGlobals.md (typeof), 정의 파일 `GetAttribute(...): unknown?`
local function g(x: Instance, u: unknown)
	local v = x:GetAttribute("Hp")
	local n: number = v -- expect-error: got 'unknown?'
	if typeof(v) == "number" then
		local a: number = v
	end
	if type(v) == "number" then
		local b: number = v
	end
	if typeof(v) == "Vector3" then
		local c: Vector3 = v
	end
	if type(v) == "userdata" then
		local d: never = v -- expect-error: got 'userdata'
	end
	local k7: never = x:GetAttributes() -- expect-error: { [string]: unknown }
	x:SetAttribute("T", {}) -- bug-present
	x:SetAttribute("T", Instance.new("Part")) -- bug-present
	if typeof(u) == "Instance" then
		local i: never = u -- expect-error: got 'Instance'
	end
	if typeof(u) == "Part" then
		local j: never = u -- expect-error: got 'Part'
	end
	local _ = n
end
local _ = g
