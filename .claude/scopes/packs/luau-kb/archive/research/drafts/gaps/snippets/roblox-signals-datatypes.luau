--!strict
-- 주장: 이벤트는 `RBXScriptSignal<인자...>` 로 타입이 있어 Connect 콜백 파라미터가 추론된다(Touched -> BasePart, Changed -> string).
--       `game.Players` 같은 서비스 자식 접근은 DataModel 에 키가 없어 에러다. GetService 를 쓴다.
--       LocalPlayer 는 `Player`(nil 아님)로 선언되어 있다. 서버에서는 nil 이다.
--       typeof 의 반환은 그냥 string 이다(리터럴 유니온 아님).
-- 근거: create.roblox.com/.../classes/Players.md (LocalPlayer), 정의 파일
local p = Instance.new("Part")
local k1: never = p.Touched -- expect-error: RBXScriptSignal<BasePart>
p.Touched:Connect(function(other)
	local k2: never = other -- expect-error: got 'BasePart'
end)
local k3: never = p.Changed -- expect-error: RBXScriptSignal<string>
local players = game.Players -- expect-error: Key 'Players' not found
local lp = game:GetService("Players").LocalPlayer
local lpName: string = lp.Name -- bug-present
local k4: never = typeof(p) -- expect-error: got 'string'
local k5: never = Vector3.new(1, 2, 3) * 2 -- expect-error: got 'Vector3'
local k6: never = CFrame.new() * Vector3.new() -- expect-error: got 'Vector3'
local _ = players, lpName
