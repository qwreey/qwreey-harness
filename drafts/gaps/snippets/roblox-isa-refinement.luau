--!strict
-- 주장: `x:IsA("<리터럴>")` 은 그 분기에서 x 를 그 클래스로 좁힌다(or 로 묶으면 유니온, `not ... then return` 뒤에도 유지).
--       IsA 에 변수를 넘기면 좁히지 않는다. 없는 클래스 이름은 에러다. `x.ClassName == "Part"` 는 Part 로 좁히지 않는다.
-- 근거: luau.org/types/roblox-types ("Roblox types can be refined using IsA"), create.roblox.com/.../classes/Object.md (IsA)
local function f(x: Instance, cls: string)
	if x:IsA("BasePart") then
		local k1: never = x -- expect-error: got 'BasePart'
	end
	if x:IsA("TextLabel") or x:IsA("TextButton") then
		local k2: never = x -- expect-error: TextButton | TextLabel
	end
	if x:IsA(cls) then
		local k3: never = x -- expect-error: got 'Instance'
	end
	if x:IsA("Prat") then -- expect-error: Unknown type 'Prat'
	end
	if x.ClassName == "Part" then
		local size = x.Size -- expect-error: does not have key 'Size'
	end
	if not x:IsA("BasePart") then return end
	local k5: never = x -- expect-error: got 'BasePart'
end
local maybe = workspace:FindFirstChild("X")
if maybe and maybe:IsA("BasePart") then
	local s: Vector3 = maybe.Size
end
local downcast = (maybe :: Part).Size
local nonsense = (maybe :: number) -- expect-error
local _ = f, downcast, nonsense
