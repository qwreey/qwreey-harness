--!strict
-- 주장: Actor 는 Model 을 상속한다. SendMessage 는 topic: string 뒤에 ...any 를 받아 함수 값도 타입상 통과한다(런타임에서는 VM 경계를 넘지 못한다).
--       BindToMessage/BindToMessageParallel 콜백은 (...any) -> ...any 라 메시지 페이로드 타입이 송신 쪽과 연결되지 않는다.
--       GetActor 는 Actor? 를 돌려준다.
-- 근거: typedefs/globalTypes.d.luau `declare extern type Actor extends Model`; create.roblox.com reference/engine/classes/Actor.md (last_updated 2026-11-10)
local actor = Instance.new("Actor")
local asModel: Model = actor
local asPart: BasePart = actor -- expect-error

actor:SendMessage("Greeting", "hello", 1, { 1, 2 })
actor:SendMessage(1, "hello") -- expect-error
actor:SendMessage("Callback", function() end) -- bug-present

local conn: RBXScriptConnection = actor:BindToMessageParallel("Greeting", function(greeting: Vector3) end)
local bad: number = actor:BindToMessage("Greeting", function() end) -- expect-error

local mine: Actor = script:GetActor() -- expect-error
local maybe = script:GetActor()
if maybe then
	maybe:SendMessage("Ready")
end
