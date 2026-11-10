--!strict
--@lsp-roblox
-- 주장: Roblox 정의 파일(typedefs/globalTypes.d.luau:7857)은 `DateTime:ToLocalTime()` 의 반환을 `{ any }` 로 적는다.
--       그래서 문서상 있는 필드(`Year` 등)를 읽으면 "Key 'Year' not found in table '{any}'" 로 거부된다. 결과에 레코드 타입을 주석으로 단다.
--       정의 파일 버전에 따르는 사실이다(정의 파일을 바꾸면 다시 잰다).
-- 근거: 실측(luau-lsp 1.70.1, 1.69.0 + 이 저장소 정의 파일). 원천 devplorer/.claude/feedback/quad-upstream-2026-10-20.md:502 (후보 D-F33)
local t = DateTime.now():ToLocalTime()
local y: number = t.Year -- expect-error: Key 'Year' not found in table '{any}'
type LocalTime = { Year: number, Month: number, Day: number }
local u = (DateTime.now():ToLocalTime() :: any) :: LocalTime
local m: number = u.Month
local _ = y, m
