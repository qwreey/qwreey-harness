# roblox-api-types — Instance, Enum, 서비스, 속성의 타입 사용법

## 이 파일이 답하는 질문
- Q1 `Instance.new("Part")` 가 `Part` 로 추론되는 것은 정의 파일 덕분인가, 검사기 덕분인가? `luau-analyze` 로도 되나?
- Q2 `FindFirstChild` / `WaitForChild` 의 결과는 언제 nil 일 수 있나? 타입은 그것을 반영하나?
- Q3 `Instance` 를 구체 클래스로 좁히려면 무엇을 쓰나? `IsA`, `ClassName`, `typeof`, 캐스트 중 무엇이 되나?
- Q4 `GetAttribute` 결과는 어떻게 다루나? `SetAttribute` 는 무엇을 막아 주나?
- Q5 Enum 타입은 어떻게 적고, 문자열 이름 대입은 왜 타입 에러인가?
- Q6 `workspace.Foo`, `game.Players` 같은 자식 접근이 왜 에러이고, 어떻게 타입을 받나?
- Q7 타입은 non-nil 인데 런타임에 nil 이 오는 Roblox API 는 무엇인가?

## 목차
- §1 전제: 이 타입들은 luau-lsp `--platform=roblox` 에서만 나온다
- §2 Instance.new, GetService, Clone, FindFirstChildOfClass 계열
- §3 FindFirstChild, WaitForChild, 자식 접근과 nil
- §4 sourcemap 으로 DataModel 자식 타입 받기
- §5 좁히기: IsA, ClassName, 캐스트
- §6 속성(Attribute): GetAttribute 는 `unknown?`
- §7 `typeof` 와 `type`
- §8 Enum 타입
- §9 이벤트와 데이터 타입
- §10 타입이 런타임보다 낙관적인 자리
- §11 자료와 버전

표기: `verified` 는 스니펫이 `drafts/gaps/tools/check_roblox.py` 로 통과했다는 뜻이다. 이 검사기는 `luau-lsp analyze --platform=roblox --definitions=luau-kb/typedefs/globalTypes.d.luau --flag:LuauSolverV2=true` 를 쓰고, luau-lsp 1.70.1 과 1.69.0 둘 다에서 돌렸다. `described` 는 문서 서술만 있고 런타임(Studio)에서 확인하지 않았다는 뜻이다. 정의 파일은 quad `2ad2c03e`(2026-09-02)판의 복사본이다. 다른 판(rbvm, tbox)에서는 결과가 다를 수 있다(`luau-kb/typedefs/README.md`).

---

## §1 전제: 이 타입들은 luau-lsp `--platform=roblox` 에서만 나온다
status: verified · last-confirmed: luau-lsp 1.70.1 (1.69.0 동일) · 근거: `roblox-constructors-services.luau`, 짝 `roblox-constructors-standard.luau`

- 정의 파일의 `Instance.new` 는 `(className: string, parent: Instance?) -> Instance` 하나뿐이다. `GetService` 도 `(className: string) -> Instance` 다.
- 그런데 `--platform=roblox` 를 주면 결과가 `Part`, `RunService` 로 나오고, 없는 이름에는 `Invalid class name 'Bogus'` 가 난다. 같은 정의 파일에 `--platform=standard` 를 주면 이 추론과 이름 검사가 모두 사라진다(`Instance`).
- 따라서 이 기능은 **정의 파일이 아니라 luau-lsp 의 Roblox 플랫폼 코드**에서 온다. `luau-analyze` 는 정의 파일도 못 읽으므로 Roblox 코드를 검사할 수 없다.
- 검사기 기본값 함정이 둘 있다(1.70.1 실측).
  - `--flag:LuauSolverV2=true` 를 빼면 옛 솔버로 검사한다. 진단 열이 1 로 찍히는 것으로 알 수 있다.
  - `--platform` 을 두 번 주면 `Duplicate argument` 로 실행 자체가 실패한다.

## §2 Instance.new, GetService, Clone, FindFirstChildOfClass 계열
status: verified · last-confirmed: luau-lsp 1.70.1 (1.69.0 동일) · 근거: `roblox-constructors-services.luau` · 원천: luau.org/types/roblox-types ("We can automatically deduce what calls like Instance.new and game:GetService are supposed to return")

| 호출 | 타입 |
|---|---|
| `Instance.new("Part")` | `Part` |
| `Instance.new(cn)` (변수) | `Instance` |
| `Instance.new("Bogus")` | 에러 `Invalid class name` |
| `game:GetService("RunService")` / 변수 / `"Bogus"` / `"Part"`(서비스 아닌 클래스) | `RunService` / `Instance` / 에러 `Invalid service name` / 같은 에러 (ServiceProvider.md: 런타임은 nil) |
| `p:Clone()` (p: Part) | `Part` (nil 아님, §10) |
| `FindFirstChildOfClass("Part")` | `Part?` |
| `FindFirstChildWhichIsA("BasePart")` | `BasePart?` |
| `FindFirstAncestorOfClass("Model")` | `Model?` |

**처방**: 클래스 이름과 서비스 이름은 문자열 리터럴로 직접 쓴다. 이름을 변수나 테이블에 두면 `Instance` 로 떨어지고 이름 검사도 사라진다.

## §3 FindFirstChild, WaitForChild, 자식 접근과 nil
status: verified · last-confirmed: luau-lsp 1.70.1 (1.69.0 동일) · 근거: `roblox-find-wait-nil.luau` · 원천: create.roblox.com/docs/en-us/reference/engine/classes/Instance.md (FindFirstChild, WaitForChild)

| 호출 | 타입 | 문서상 런타임 |
|---|---|---|
| `FindFirstChild(name)` | `Instance?`. 검사 없이 `.Name` 을 읽으면 `could be nil` 에러 | 없으면 nil |
| `WaitForChild(name)` | `Instance` | 나타날 때까지 양보한다. 5초가 넘으면 "무한 양보 가능" 경고를 출력한다 |
| `WaitForChild(name, timeout)` | `Instance?` | 시간이 지나면 nil |
| `workspace.Foo` (sourcemap 없음) | 에러 `Key 'Foo' not found in external type 'Workspace'` | 없으면 런타임 에러 |

- 이름으로 받은 자식은 클래스를 모르므로 `Instance` 다. 구체 타입은 §5 의 `IsA` 로 좁히거나, §4 의 sourcemap 으로 받는다.
- 문서의 WaitForChild 시그니처 줄은 `timeOut: double` 에 반환 `Instance` 로 적혀 있다. 그러나 본문은 "시간이 지나면 nil 을 돌려준다"고 한다. 정의 파일은 오버로드 둘로 나눠 본문 쪽을 따른다. 시그니처 줄보다 정의 파일이 정확하다.

## §4 sourcemap 으로 DataModel 자식 타입 받기
status: verified · last-confirmed: luau-lsp 1.70.1 (1.69.0 동일) · 근거: `roblox-sourcemap-children.luau` · 원천: `luau-lsp analyze --help` ("--sourcemap PATH: path to a Rojo-style instance sourcemap to understand the DataModel")

- Rojo 형식 sourcemap(`rojo sourcemap` 출력)을 `--sourcemap` 으로 주면 두 가지가 달라진다.
  - `workspace.Foo` 가 sourcemap 의 클래스(`Part`)로 추론된다.
  - `rs:WaitForChild("Shared")` 도 `Folder` 로 추론된다.
- sourcemap 에 없는 자식은 여전히 에러다.
- `--no-strict-dm-types` 를 줘도 이 스니펫의 결과는 같았다. 이 옵션이 무엇을 바꾸는지는 확인하지 못했다.
- `game.Players` 처럼 서비스를 자식으로 읽는 것은 sourcemap 이 없으면 `Key 'Players' not found in external type 'DataModel'` 이다(`roblox-signals-datatypes.luau`). 서비스는 `game:GetService("Players")` 로 얻는다.

## §5 좁히기: IsA, ClassName, 캐스트
status: verified · last-confirmed: luau-lsp 1.70.1 (1.69.0 동일) · 근거: `roblox-isa-refinement.luau`, `roblox-docs-isa-sample.luau` · 원천: luau.org/types/roblox-types ("Roblox types can be refined using IsA"), create.roblox.com/.../classes/Object.md (IsA)

| 쓰는 법 | 결과 |
|---|---|
| `if x:IsA("BasePart") then` | 분기 안에서 `BasePart` |
| `x:IsA("TextLabel") or x:IsA("TextButton")` | `TextButton \| TextLabel` |
| `if not x:IsA("BasePart") then return end` | 이후 줄에서 `BasePart` |
| `maybe and maybe:IsA("BasePart")` (`Instance?`) | `BasePart` |
| `x:IsA(cls)` (변수) | 좁히지 않음(`Instance`) |
| `x:IsA("Prat")` (오타) | 에러 `Unknown type 'Prat'` |
| `x.ClassName == "Part"` | `Instance & { read ClassName: "Part" }`. **Part 가 아니다**. `x.Size` 는 에러다 |
| `(maybe :: Part)` | 허용된다. 하위 클래스로 내리는 캐스트라 검사가 없다 |
| `(maybe :: number)` | 에러(관계없는 타입) |

- Object.md 는 "상속을 무시하려면 ClassName 을 직접 비교하라"고 한다. 그러나 이 비교는 타입을 좁혀 주지 않는다. 정확한 클래스가 필요하면 `IsA` 로 먼저 좁힌 다음 `ClassName` 을 확인한다.
- luau.org 의 IsA 예제는 그대로 붙여 넣으면 `Unknown global 'child'` 다. 파라미터는 `x` 인데 본문이 `child.Text` 를 읽는다. `x.Text` 로 고치면 통과한다.

## §6 속성(Attribute): GetAttribute 는 `unknown?`
status: verified (타입), described (런타임 에러) · last-confirmed: luau-lsp 1.70.1 (1.69.0 동일) · 근거: `roblox-attributes-typeof.luau` · 원천: create.roblox.com/.../classes/Instance.md (GetAttribute, SetAttribute), .../studio/properties.md "Instance attributes"

- `GetAttribute(name)` 은 `unknown?` 이다. 문서 시그니처는 `Variant` 다. 바로 `number` 에 담으면 `got 'unknown?'` 에러가 난다. `typeof(v) == "number"`, `type(v) == "number"`, `typeof(v) == "Vector3"` 로 좁힌 뒤 쓴다.
- `GetAttributes()` 는 `{ [string]: unknown }` 이다.
- `SetAttribute(name, value)` 의 value 는 `any` 다. 그래서 `{}` 나 `Instance` 를 넣어도 **정적으로 통과한다**(스니펫 `bug-present`). 문서는 지원하지 않는 타입이면 에러를 던진다고 한다.
- 지원 타입(studio/properties.md 목록)은 string, boolean, number, UDim, UDim2, BrickColor, Color3, Vector2, Vector3, CFrame, NumberSequence, ColorSequence, NumberRange, Rect, Font 다. 이 목록에 테이블과 Instance 는 없다.
- 이름 규칙(영숫자와 `. - / _`, 100자 이하, `RBX` 접두 금지)도 타입이 막지 않는다(described).
- **처방**: 속성 읽기는 "타입별 getter 한 곳"으로 모은다. 예: `local function attrNumber(i: Instance, n: string): number? local v = i:GetAttribute(n) return if typeof(v) == "number" then v else nil end`. 쓰기도 허용 타입 유니온을 받는 래퍼로 감싸면 정적 검사가 생긴다.

## §7 `typeof` 와 `type`
status: verified (타입), described (런타임 값) · last-confirmed: luau-lsp 1.70.1 (1.69.0 동일) · 근거: `roblox-attributes-typeof.luau`, `roblox-signals-datatypes.luau` · 원천: create.roblox.com/.../globals/RobloxGlobals.md "typeof"

- `type` 은 Luau 기본 타입 이름만 안다. Roblox 데이터 타입과 인스턴스는 `"userdata"` 다. `type(v) == "userdata"` 는 v 를 Luau 의 `userdata` 타입으로 좁힌다.
- `typeof` 는 `"Vector3"`, `"CFrame"`, `"Instance"`, `"EnumItem"` 처럼 Roblox 타입 이름까지 돌려준다(RobloxGlobals.md). 타입 검사기도 `typeof(u) == "Instance"` 로 `Instance` 까지 좁힌다.
- **함정**: `typeof(u) == "Part"` 도 타입 검사기는 `Part` 로 좁혀 준다. 그러나 런타임 `typeof` 는 모든 인스턴스에 `"Instance"` 를 돌려주므로 이 분기는 실행되지 않는다. 클래스 판별은 `typeof(u) == "Instance" and u:IsA("Part")` 로 한다.
  - 런타임 값이 `"Instance"` 라는 것은 Studio 에서 확인하지 않았다. 문서 페이지에도 명시가 없다. 사용자 저장소의 실제 코드가 이 전제에 기대고 있다(`quad/quad-roblox/src/LifetimeHandle.luau:139`, `devplorer/src/Server/Core/StartConfig.luau:58`).
- `type(u) == "Instance"` 는 TypeError 가 아니라 린트 `UnknownType` 경고로만 나온다.
- `typeof(x)` 의 반환 타입은 그냥 `string` 이다. 리터럴 유니온이 아니다.

## §8 Enum 타입
status: verified · last-confirmed: luau-lsp 1.70.1 (1.69.0 동일) · 근거: `roblox-enums.luau` · 원천: create.roblox.com/docs/en-us/luau/enums.md, luau.org/types/roblox-types ("local m: Enum.Material = part.Material")

| 코드 | 결과 |
|---|---|
| `local m: Enum.Material = p.Material` | 항목 타입은 `Enum.<열거형>` |
| `local pt: Enum.PartType = Enum.Material.Plastic` | 에러. 열거형끼리는 섞이지 않는다 |
| `Enum.Material:GetEnumItems()` | `{Enum.Material}` |
| `Enum.Material:FromName("Plastic")` | `Enum.Material?` |
| `Enum.Material.Plastik` | 에러 `Key 'Plastik' not found` |
| `p.Shape = "Cylinder"` | **에러** `got 'string'` |
| `p.Material == "Plastic"` | 에러 `Cannot compare unrelated types` |
| `local ei: EnumItem = ...` 를 `Enum.Material` 파라미터에 넘김 | 에러. `ei :: Enum.Material` 로 내려야 한다 |
| `.Name` / `.Value` | `string` / `number` |

- **문서와 타입의 어긋남**: enums.md 는 "항목의 Name 문자열을 대입해도 된다"며 `part.Shape = "Cylinder"` 를 예로 든다. 런타임은 받아 주지만(described) 타입 검사기는 거부한다. strict 코드에서는 항상 `Enum.PartType.Cylinder` 처럼 쓴다. 문서도 이것을 "best practice" 라고 부른다.
- 정의 파일에서 항목 타입은 `EnumMaterial extends EnumItem` 이고 열거형 객체는 `EnumMaterial_INTERNAL extends Enum` 이다. 진단 메시지에는 둘 다 `Enum.Material` 로 찍혀서 헷갈릴 수 있다.

## §9 이벤트와 데이터 타입
status: verified · last-confirmed: luau-lsp 1.70.1 (1.69.0 동일) · 근거: `roblox-signals-datatypes.luau`

- 이벤트는 `RBXScriptSignal<인자...>` 다. `p.Touched` 는 `RBXScriptSignal<BasePart>`, `p.Changed` 는 `RBXScriptSignal<string>` 이다. `Connect(function(other) ... end)` 의 `other` 가 `BasePart` 로 추론된다.
- `GetPropertyChangedSignal(...)` 은 정의 파일에 `RBXScriptSignal<>` 로 적혀 있다. 그런데 진단에는 `RBXScriptSignal<...any>` 로 보였다(1.70.1).
- 데이터 타입 연산도 타입이 있다. `Vector3 * number`, `CFrame * Vector3` 는 `Vector3` 다.

## §10 타입이 런타임보다 낙관적인 자리
status: verified (무진단), described (런타임 값) · last-confirmed: luau-lsp 1.70.1 (1.69.0 동일) · 근거: `roblox-find-wait-nil.luau`, `roblox-signals-datatypes.luau`, `roblox-attributes-typeof.luau`

| API | 타입 | 문서상 런타임 |
|---|---|---|
| `Instance:Clone()` | `Part` (non-nil) | `Archivable = false` 이면 nil (Instance.md) |
| `Players.LocalPlayer` | `Player` (non-nil) | 서버 Script 에서는 nil (Players.md) |
| `Instance:SetAttribute(n, {})` | 통과 | 지원하지 않는 타입이면 에러 |
| `typeof(u) == "Part"` 분기 | `Part` 로 좁혀짐 | 실행되지 않음 (§7) |

각 줄은 스니펫에서 `bug-present` 로 고정했다. 정의 파일이나 luau-lsp 가 바뀌어 진단이 생기면 스니펫이 실패해서 알려 준다.

## §11 자료와 버전
| 자료 | 버전/날짜 |
|---|---|
| luau.org/types/roblox-types | 2026-11-10 받음, 날짜 없음. 예제는 play.luau.org iframe 에서 디코드 |
| create.roblox.com: `luau/type-checking.md`, `luau/enums.md`, `scripting/attributes.md`, `studio/properties.md`, `reference/engine/classes/{Instance,Object,ServiceProvider,Players}.md`, `reference/engine/globals/RobloxGlobals.md` | 모두 `llms.txt`(머리 `Last updated: 2026-11-10T00:40:57Z`)에서 찾은 경로. 각 페이지의 `last_updated` 는 2026-11-10T00:40Z 대로, 문서 빌드 시각이다 |
| 정의 파일 | `luau-kb/typedefs/globalTypes.d.luau` (quad `2ad2c03e`, 2026-09-02, md5 `be071eac…`) |
| 검사기 | luau-lsp 1.70.1, 1.69.0 (`analyze`, 새 솔버) |
| 사용자 코드 근거 | quad `quad-roblox/src/LifetimeHandle.luau:139`, devplorer `src/Server/Core/StartConfig.luau:58` |

확인하지 못한 것: 런타임 동작 전부(Studio 필요, MCP 금지), `--no-strict-dm-types` 의 효과, 옛 솔버(`LuauSolverV2=false`)에서의 IsA·Enum 결과(§2 표만 옛 솔버에서 같은 타입이 나옴을 확인), rbvm/tbox 판 정의 파일에서의 차이.

---
들어갈 luau-kb 스킬: **roblox-luau** (`references/instance-enum-types.md` 신규). §1 의 검사기 함정은 **luau-verify** `checkers.md` 에도 한 줄을 넣는다.
