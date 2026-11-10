--!strict
-- 주장: 함수 모양 필드로 변성을 고를 수 있다(read 일 때만):
--       read p: () -> T  공변 / read p: (T) -> ()  반공변 / read p: (T) -> T  불변.
--       read 없는 함수 필드 p: () -> T 는 읽기·쓰기라 불변 비교된다.
-- 근거: stl-luau/.claude/base/typing-limits.md "팬텀·표식의 모양", quad 8.42
type FCo<T> = { read p: () -> T }
type FContra<T> = { read p: (T) -> () }
type FInv<T> = { read p: (T) -> T }
type FNoRead<T> = { p: () -> T }
local co: FCo<number> = { p = function() return 1 end }
local coWide: FCo<number | string> = co
local coNarrow: FCo<number> = (nil :: any) :: FCo<number | string> -- expect-error: Expected this to be
local contra: FContra<number | string> = { p = function(_x) end }
local contraNarrow: FContra<number> = contra
local contraOther: FContra<number> = (nil :: any) :: FContra<boolean> -- expect-error: Expected this to be
local inv: FInv<number> = { p = function(x) return x end }
local invWide: FInv<number | string> = inv -- expect-error: Expected this to be
local nr: FNoRead<number> = { p = function() return 1 end }
local nrWide: FNoRead<number | string> = nr -- expect-error: Expected this to be
