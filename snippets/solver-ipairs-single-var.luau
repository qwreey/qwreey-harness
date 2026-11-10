--!strict
--@run
-- 주장(위양성): 새 솔버는 루프 변수 하나만 쓰는 `for i in ipairs(t)` 를 거부한다.
--   메시지 "Argument count mismatch. Function expects 2 arguments, but 2 are specified" 가 ipairs 호출 위치에 난다.
--   두 변수(`for i, v in ipairs(t)`), `pairs` 한 변수, `next` 삼중항 한 변수, 일반화 순회 `for i in t` 는 통과한다.
--   옛 솔버(--solver=old)는 0건이다. 실행은 정상이다(아래 assert).
--   이 줄의 expect-error 는 '지금 이 위양성이 있다'를 고정한다. 고쳐지면 하네스가 실패해 문서 갱신을 알린다.
-- 근거: luau-analyze 0.734·0.742·0.746, luau-lsp 1.69.0·1.70.1 analyze 모두 같은 자리(ipairs 호출, 10열).
--   원천: luau-style 에이전트 보고, 메인 세션 재현(2026-11-10). 업스트림 동일 이슈 못 찾음(GitHub 검색 2026-11-10, 인접 #2986).
-- 우회: 두 변수로 받고 `_` 를 쓴다(`for i, _ in ipairs(t)`), 또는 숫자 for(`for i = 1, #t`).
local t = { 10, 20, 30 }
local n = 0
for i in ipairs(t) do -- expect-error: Function expects 2 arguments, but 2 are specified
	n += i
end
for i, _ in ipairs(t) do
	n += i
end
for i in pairs(t) do
	n += i
end
for k in next, t do
	n += k
end
for i in t do
	n += i
end
assert(n == 30, tostring(n))
