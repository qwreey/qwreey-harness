--!strict
-- 주장: 클로저 안의 루프에서 옵셔널 업밸류를 `if nav then` 으로 좁혀도 루프 몸통에서는 좁혀지지 않는다("could be nil").
--       같은 클로저의 루프 밖 좁히기는 통과한다. 우회는 루프 전에 non-nil 지역으로 받아 두는 것이다.
--       원천의 둘째 모양(필드를 좁힌 뒤 다른 호출이 끼면 실패)은 luau-analyze 0.734/0.742 에서는 재현되지 않는다(원천은 luau-lsp 1.69.0).
-- 근거: 실측. 원천 devplorer/.claude/feedback/quad-upstream-2026-10-20.md:492-496 (후보 D-F31)
type Nav = { X: () -> () }
local function mk(nav0: Nav?, list: { number })
	local nav = nav0
	return function()
		for _ in list do
			if nav then nav.X() end -- expect-error: could be nil
		end
		if nav then nav.X() end
		if nav then
			local n = nav
			for _ in list do n.X() end
		end
	end
end
local function other() end
local function g(ops: { Tick: ((number) -> ())? })
	if ops.Tick then other(); ops.Tick(1) end
end
local _ = mk, g
