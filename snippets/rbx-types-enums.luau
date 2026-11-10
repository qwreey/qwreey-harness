--!strict
--@lsp-roblox
-- 주장: 열거형 항목 타입은 `Enum.<이름>` 이고 서로 다른 열거형끼리는 대입이 안 된다. 일반 `EnumItem` 은 구체 열거형 자리에 못 들어간다.
--       GetEnumItems 는 `{Enum.X}`, FromName 은 `Enum.X?`. 오타 항목은 에러다.
--       문서는 열거형 속성에 이름 문자열을 대입해도 된다고 하지만(`part.Shape = "Cylinder"`), 타입 검사기는 string 을 거부한다.
--       문자열과의 == 비교도 에러다.
-- 근거: create.roblox.com/docs/en-us/luau/enums.md ("You can also use the item's Name property as a string"),
--       luau.org/types/roblox-types ("local m: Enum.Material = part.Material")
local p = Instance.new("Part")
local m: Enum.Material = p.Material
local k1: never = Enum.Material.Plastic -- expect-error: Enum.Material
local pt: Enum.PartType = Enum.Material.Plastic -- expect-error: Enum.PartType
local k2: never = Enum.Material:GetEnumItems() -- expect-error: {Enum.Material}
local k3: never = Enum.Material:FromName("Plastic") -- expect-error: Enum.Material?
p.Shape = "Cylinder" -- expect-error: got 'string'
p.Shape = Enum.PartType.Cylinder
if p.Material == "Plastic" then end -- expect-error: Cannot compare unrelated types
local ei: EnumItem = Enum.Material.Plastic
local function takesEnum(e: Enum.Material) end
takesEnum(ei) -- expect-error: got 'EnumItem'
takesEnum(ei :: Enum.Material)
local nm: string = Enum.Material.Plastic.Name
local val: string = Enum.Material.Plastic.Value -- expect-error: got 'number'
local bad = Enum.Material.Plastik -- expect-error: Key 'Plastik' not found
local _ = m, pt, nm, val, bad
