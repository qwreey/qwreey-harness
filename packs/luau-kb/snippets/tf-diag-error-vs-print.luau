--!strict
-- 주장: type function 의 진단 통로는 둘이다.
--   (a) `print(...)` 는 로그가 아니다. 결과 타입이 멀쩡해도 사용 자리마다 TypeError 로 뜬다.
--       그래서 디버그 출력으로 쓰면 검사가 빨갛게 된다.
--   (b) `print` + `types.never` 는 메시지 한 줄과 "Expected this to be unreachable" 을 낸다.
--   (c) `error("…")` 도 메시지는 보인다(0.734, 0.742, luau-lsp 1.69.0, 1.70.1).
--       다만 모양이 "'F' type function errored at runtime: F:<줄>: ..." 이다(0.734 는 `[string "F"]:<줄>:`).
--       결과가 never 로 줄어 "reduced type is `never`" 불일치가 덧붙는다.
--       파라미터 주석 자리에 쓰면 선언 줄에 한 번 뜨고, 호출마다 두 건씩 다시 뜬다.
-- 근거: quad/.claude/base/typing-limits.md 0 "error()가 아니라 print + types.never",
--       quad/.claude/luau-test/done/23 머리 주석 1번, stl-luau/.claude/papers/03-tuple.md:23,
--       stl-luau/.claude/conventions.md:84 3), qwreey-harness .claude/base/decisions/D-04-type-functions.md 2
type function PrintOnly(t: type): type
	print("debug: " .. t.tag)
	return t
end
type function PrintNever(t: type): type
	print("custom message")
	return types.never
end
type function Err(t: type): type
	error("bad input")
end
local _p: PrintOnly<number> = 1 -- expect-error: debug: number
local _q: PrintNever<number> = 1 -- expect-error: custom message
local _r: Err<number> = 1 -- expect-error: errored at runtime
local function useErr(_v: Err<number>) end -- expect-error: bad input
useErr(1) -- expect-error: reduced type is `never`
useErr(2) -- expect-error: errored at runtime
