--!strict
-- 주장: `pcall(string.find, s, p)` 처럼 선택 인자가 있는 내장 함수를 pcall 에 바로 넘기면, pcall 의 A... 가 내장 선언의 전체 인자 목록으로
--       굳어 "Argument count mismatch. Function expects 5 arguments, but only 3 are specified" 로 거부된다. 람다로 감싸면 된다.
-- 근거: 실측. 원천 devplorer/.claude/feedback/quad-upstream-2026-10-20.md:502-503 (후보 D-F33 의 순수 Luau 부분)
local ok, a = pcall(string.find, "abc", "b") -- expect-error: Argument count mismatch
local ok2, b = pcall(function() return string.find("abc", "b") end)
local _ = ok, a, ok2, b
