--!strict
--@lsp-roblox
-- 주장: --platform=roblox 의 luau-lsp 는 Instance.new / GetService / Clone / FindFirstChildOfClass 계열의 "문자열 리터럴"을 보고
--       구체 클래스를 돌려준다. 리터럴이 아니면 Instance 로 떨어진다. 없는 이름은 에러다.
-- 근거: luau.org/types/roblox-types ("We can automatically deduce what calls like Instance.new and game:GetService are supposed to return"),
--       정의 파일은 `new: (className: string, parent: Instance?) -> Instance` 뿐이다(짝: rbx-types-constructors-standard.luau).
local p = Instance.new("Part")
local k1: never = p -- expect-error: got 'Part'
local cn = "Part"
local k2: never = Instance.new(cn) -- expect-error: got 'Instance'
local bogus = Instance.new("Bogus") -- expect-error: Invalid class name 'Bogus'
local k3: never = game:GetService("RunService") -- expect-error: got 'RunService'
local k4: never = game:GetService(cn) -- expect-error: got 'Instance'
local bs = game:GetService("Bogus") -- expect-error: Invalid service name 'Bogus'
local notSvc = game:GetService("Part") -- expect-error: Invalid service name 'Part'
local k5: never = p:Clone() -- expect-error: got 'Part'
local k6: never = workspace:FindFirstChildOfClass("Part") -- expect-error: got 'Part?'
local k7: never = workspace:FindFirstChildWhichIsA("BasePart") -- expect-error: got 'BasePart?'
local k8: never = p:FindFirstAncestorOfClass("Model") -- expect-error: got 'Model?'
local _ = bogus, bs, notSvc
