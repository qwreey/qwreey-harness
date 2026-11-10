--!strict
--@lsp-roblox
--@sourcemap {"name":"Game","className":"DataModel","children":[{"name":"Workspace","className":"Workspace","children":[{"name":"Foo","className":"Part"}]},{"name":"ReplicatedStorage","className":"ReplicatedStorage","children":[{"name":"Shared","className":"Folder"}]}]}
-- 주장: Rojo sourcemap 을 주면 `workspace.Foo` 와 `WaitForChild("Shared")` 가 sourcemap 의 클래스로 추론된다. 없는 자식은 여전히 에러다.
-- 근거: luau-lsp analyze --help (`--sourcemap PATH: path to a Rojo-style instance sourcemap to understand the DataModel`), 실측
local k1: never = workspace.Foo -- expect-error: got 'Part'
local rs = game:GetService("ReplicatedStorage")
local k2: never = rs:WaitForChild("Shared") -- expect-error: got 'Folder'
local bar = workspace.Bar -- expect-error: Key 'Bar' not found
local _ = bar
