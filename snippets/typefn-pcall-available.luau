--!strict
-- 주장: luau-analyze 0.734·0.742 와 luau-lsp 1.70.1 에서는 type function 안의 pcall 이 동작한다.
--       (quad 8.18 의 "pcall 은 not supported" 는 luau-lsp 1.69.0 관측 — 이 버전들에선 재현되지 않음.)
--       print 출력은 사용 자리의 TypeError 로 보이므로, 그 메시지 자체를 기대값으로 삼는다.
-- 근거: quad/.claude/base/typing-limits.md 8.18 첫 문단(1.69.0), 이 저장소 RESULTS.md
type function UsesPcall(t: type): type
	local ok = pcall(function()
		return 1
	end)
	print("pcall ok=" .. tostring(ok))
	return types.number
end
local p: UsesPcall<"x"> = 1 -- expect-error: pcall ok=true
