--!strict
-- 주장: task.desynchronize/synchronize 는 인자 없이 () 를 돌려주는 함수로 선언돼 있고, ConnectParallel 은 Connect 와 같은 콜백 타입을 쓴다.
--       타입 검사기는 실행 단계(직렬/병렬)를 모른다. 병렬 단계에서 속성 쓰기나 Unsafe 메서드(Destroy) 호출을 정적으로 잡지 못한다.
-- 근거: typedefs/globalTypes.d.luau `declare task`, `RBXScriptSignal<T...>`; create.roblox.com scripting/multithreading.md (2026-11-10)
local RunService = game:GetService("RunService")
local part = Instance.new("Part")

task.desynchronize()
task.synchronize()
local r: number = task.desynchronize() -- expect-error
task.desynchronize(1) -- expect-error

local c1: RBXScriptConnection = RunService.Heartbeat:ConnectParallel(function(dt: number) end)
RunService.Heartbeat:ConnectParallel(function(dt: string) end) -- expect-error
local c2: number = RunService.Heartbeat:ConnectParallel(function() end) -- expect-error

RunService.Heartbeat:ConnectParallel(function()
	part.Name = "written in parallel" -- bug-present
	part:Destroy() -- bug-present
	task.synchronize()
	part.Name = "written in serial"
end)
