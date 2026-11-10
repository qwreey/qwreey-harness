--!strict
--@args --platform=standard
-- 주장: roblox-constructors-services.luau 의 짝. 같은 정의 파일이라도 --platform=standard 면 구체 클래스 추론과 이름 검사가 없다.
--       즉 이 추론은 정의 파일이 아니라 luau-lsp 의 Roblox 플랫폼 기능이다. luau-analyze 로는 재현할 수 없다.
-- 근거: 실측
local p = Instance.new("Part")
local k1: never = p -- expect-error: got 'Instance'
local bogus = Instance.new("Bogus")
local k3: never = game:GetService("RunService") -- expect-error: got 'Instance'
local k6: never = workspace:FindFirstChildOfClass("Part") -- expect-error: got 'Instance?'
local _ = bogus
