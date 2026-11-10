--!strict
--@lsp-roblox
-- 주장: luau.org/types/roblox-types 의 IsA 예제는 그대로는 검사를 통과하지 않는다(파라미터는 x 인데 본문이 `child.Text`).
--       x 로 고치면 세 IsA 의 유니온에서 Text 를 읽을 수 있다.
-- 근거: luau.org/types/roblox-types (2026-11-10 받음) 예제 원문
local function getText(x : Instance) : string
    if x:IsA("TextLabel") or x:IsA("TextButton") or x:IsA("TextBox") then
        return child.Text -- expect-error: Unknown global 'child'
    end
    return ""
end
local function getTextFixed(x: Instance): string
	if x:IsA("TextLabel") or x:IsA("TextButton") or x:IsA("TextBox") then
		return x.Text
	end
	return ""
end
local _ = getText, getTextFixed
