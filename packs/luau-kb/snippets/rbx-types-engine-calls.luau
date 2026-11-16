--!strict
--@lsp-roblox
-- 주장: 엔진 호출에서 타입이 잡아 주는 것과 런타임에만 드러나는 것을 가른다(정의 파일 + luau-lsp --platform=roblox).
--   잡는다: Connect 에 함수가 아닌 값(런타임은 던지지 않고 콘솔 경고만 남긴다, Q-026), task.delay 의 인자 순서(시간이 먼저, Q-065),
--           Completed 콜백 인자 타입(Enum.PlaybackState), TweenInfo 의 enum 자리에 다른 enum.
--           GetPropertyChangedSignal 의 없는 속성 이름(리터럴일 때만. luau-lsp Roblox 플랫폼 기능).
--   못 잡는다(bug-present):
--           TweenService:Create 의 목표 표(타입은 { [any]: any }라 보간 불가 속성, 없는 속성도 통과, 런타임은 Create 가 던진다, Q-032, Q-036),
--           TweenInfo.new 의 enum 자리에 명시적 nil(타입은 선택 인자로 받지만 런타임은 거부, Q-036).
-- 근거: typedefs/globalTypes.d.luau (RBXScriptSignal, task, TweenService, TweenInfo); quad .claude/audit/round8-studio-2026-09-08.md:13,
--       quad .claude/base/tween-plan.md:211-215,497-528, quad .claude/audit/tween-premises-2026-10-22/REPORT.md:9-19
local TweenService = game:GetService("TweenService")
local p = Instance.new("Part")

p.Touched:Connect(5) -- expect-error
p.Touched:Connect(function(hit: BasePart) end)

task.delay(1, function() end)
task.delay(function() end, 1) -- expect-error

local info = TweenInfo.new(1, Enum.EasingStyle.Quad, Enum.EasingDirection.Out)
local badInfo = TweenInfo.new(1, Enum.EasingDirection.Out) -- expect-error
local nilInfo = TweenInfo.new(1, nil, Enum.EasingDirection.Out) -- bug-present

local tw = TweenService:Create(p, info, { Transparency = 0.5 })
local twBad = TweenService:Create(p, info, { Bogus = 1, Name = "x" }) -- bug-present
tw.Completed:Connect(function(state)
	local s: Enum.PlaybackState = state
	local n: number = state -- expect-error
end)

local sig = p:GetPropertyChangedSignal("Bogus") -- expect-error: Key 'Bogus' not found
local nameSig = p:GetPropertyChangedSignal(string.lower("Name")) -- 리터럴이 아니면 검사하지 않는다
local _ = { nilInfo, twBad, sig, nameSig, badInfo }
