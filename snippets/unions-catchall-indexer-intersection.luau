--!strict
-- 주장: `[string]: any` 같은 catch-all 인덱서를 가진 타입과의 교집합(`{ ShouldStop: boolean } & NS`)은 이름 있는 필드까지 사실상 any 로 만든다.
--       non-optional boolean 필드에 nil 을 대입해도, 그 필드를 string 에 담아도 새 솔버는 0건이다. 교집합 없는 같은 필드는 잡힌다.
--       "검사 통과"가 로직 검증이 아닌 대표 사례다(옛 솔버는 같은 모양에서 교집합 노이즈를 대량으로 낸다, 원천 340건).
-- 근거: 실측. 원천 rbvm/.claude/design/known-issues.md:18-45 (후보 R-51, 원천은 luau-lsp 1.69.0)
type NS = { Name: string, [string]: any }
type X = { ShouldStop: boolean } & NS
local x = (nil :: any) :: X
x.ShouldStop = nil -- bug-present
local y: string = x.ShouldStop -- bug-present
local z = (nil :: any) :: { ShouldStop: boolean }
z.ShouldStop = nil -- expect-error: Expected this to be 'boolean', but got 'nil'
local _ = y
