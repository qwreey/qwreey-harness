--!strict
--@run
-- 주장: 프레임워크 없이 순수 luau CLI 에서 쓸 수 있는 최소 러너. 각 케이스를 pcall 로 격리해 실패를 모으고,
-- 실패가 있으면 마지막에 error(…, 0) 로 끝내 프로세스 종료 코드를 1 로 만든다(luau CLI 는 잡히지 않은 에러에 rc=1).
-- table-sim/<비공개> 과 같은 모양. 이 파일은 실패 케이스 하나를 일부러 넣고, 러너가 그것을 셌는지 단언한다.
-- 근거: 이 파일 실행(luau 0.734, 0.742).

type Case = { name: string, fn: () -> () }

local function runCases(cases: { Case }): (number, { string })
	local passed, failures = 0, {}
	for _, c in cases do
		local ok, err = pcall(c.fn)
		if ok then
			passed += 1
		else
			table.insert(failures, `{c.name}: {err}`)
		end
	end
	return passed, failures
end

local passed, failures = runCases({
	{ name = "통과", fn = function()
		assert(1 + 1 == 2)
	end },
	{ name = "음성 대조군(일부러 실패)", fn = function()
		assert(1 + 1 == 3, "1+1 은 3 이 아니다")
	end },
})
-- 음성 대조군: 러너가 실패를 실제로 세는지 확인한다(0 failed 가 "러너가 죽었다"는 뜻일 수 있으므로).
assert(passed == 1 and #failures == 1, `passed={passed} failed={#failures}`)
assert(string.find(failures[1], "1+1 은 3 이 아니다", 1, true) ~= nil, failures[1])
print(`{passed} passed, {#failures} failed (기대한 실패 1건)`)
