--!strict
--@lsp-roblox
-- 주장: FindFirstChild 는 `Instance?` 라 nil 검사 전 필드 접근이 에러다. WaitForChild(name) 은 `Instance`(nil 아님),
--       WaitForChild(name, timeout) 은 `Instance?` 다. sourcemap 없이 `workspace.Foo` 같은 자식 접근은 에러다.
--       Clone() 은 Archivable=false 면 nil 을 돌려주지만 타입은 nil 을 포함하지 않는다.
-- 근거: create.roblox.com/docs/en-us/reference/engine/classes/Instance.md (FindFirstChild, WaitForChild, Clone),
--       luau-kb/typedefs/globalTypes.d.luau `WaitForChild(self, name: string, timeout: number): Instance?`
local c = workspace:FindFirstChild("X")
local n1 = c.Name -- expect-error: could be nil
if c then
	local n2: string = c.Name
end
local w = workspace:WaitForChild("Y")
local n3: string = w.Name
local w2 = workspace:WaitForChild("Y", 5)
local n4 = w2.Name -- expect-error: could be nil
local foo = workspace.Foo -- expect-error: Key 'Foo' not found
local p = Instance.new("Part")
p.Archivable = false
local cloneName: string = p:Clone().Name -- bug-present
local _ = n1, n3, n4, foo, cloneName
