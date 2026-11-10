--!strict
--@run
-- 주장: ① 패턴 클래스 %a·%w 는 ASCII 만 본다. %a 는 '_' 와 숫자를 포함하지 않아 "@(%a+)" 가 "@must_use" 를 "must" 에서 끊는다.
--       ② #s 와 string.len 은 바이트 수다("한" = 3). 잘못된 UTF-8 에서 utf8.len 은 nil 과 위치를 돌려주고 utf8.codes 는 던진다.
--       ③ string.format("%q", s) 는 개행을 "백슬래시 + 실제 개행" 으로 써서 출력이 두 줄이 된다.
-- 근거: devplorer dvr:2026-10-19-server-structure.md:160, dvr:2026-10-19-shared-specs.md:21-30, moonwave-luau/.claude/known-issues.md:170-183,
--       mrow-rv:357-367. 후보 D-R27, D-R29, D-R26
assert(string.match("@must_use", "@(%a+)") == "must")
assert(string.match("@must_use", "@([%w_]+)") == "must_use")
assert(string.match("é", "%a") == nil)
assert(#"한" == 3 and utf8.len("한") == 1)
local n, pos = utf8.len("ok\xff")
assert(n == nil and pos == 3)
assert(not pcall(function()
	for _, _ in utf8.codes("ok\xff") do
	end
end))
local q = string.format("%q", "a\nb")
assert(q == '"a\\\nb"', q)
