--!strict
--@run
-- 주장: 자기 재귀 타입(재귀 별칭, 또는 self 에 자기 타입을 받는 메소드)이 유니온(옵셔널 포함)의 갈래이면
--       새 솔버가 그 타입 인자를 검사하지 않는다. 같은 값을 비옵셔널 자리에 넣으면 잡힌다.
-- 근거: stl-luau/.claude/audit/luau-solver-issues/5-recursive-alias-in-union.luau, quad 8.26 최소 재현
type Plain<T> = { value: T, next: Plain<T>? }
local ps: Plain<string> = { value = "s", next = nil }
local direct: Plain<number> = ps -- expect-error: Expected this to be
local optional: Plain<number>? = ps -- bug-present
local union: Plain<number> | boolean = ps -- bug-present
type Box<T> = { read V: T, Put: (self: Box<T>, v: T) -> () }
type BoxNoSelf<T> = { read V: T, Put: (v: T) -> () }
local function takeOpt(b: Box<number>?) end
local function takeDirect(b: Box<number>) end
local function takeNoSelf(b: BoxNoSelf<number>?) end
local bs = (nil :: any) :: Box<string>
takeOpt(bs) -- bug-present
takeDirect(bs) -- expect-error: Expected this to be
takeNoSelf((nil :: any) :: BoxNoSelf<string>) -- expect-error: Expected this to be
print("ok")
