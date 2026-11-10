# modules.md — 파일·모듈·require·배치

목차
- §1 파일 머리: `--!strict` + 머리 주석
- §2 모듈 모양: 테이블 하나를 돌려준다, 저장소별 틀
- §3 require 경로 규칙
- §4 폴더와 층
- §5 엔진 무관 로직 떼어 두기
- §6 모듈 필드 읽기 — 주입되는 값과 뜨거운 루프

이 파일에서 답하는 질문
- 새 모듈 파일의 첫 줄들은 어떻게 쓰나?
- `init.luau` 안에서 `./x` 가 왜 형제 폴더를 찾나?
- require 경로 오류를 왜 타입 검사가 못 잡나?
- 백엔드가 나중에 넣는 함수를 지역에 받아도 되나?

---

## §1 파일 머리

status: stl·devplorer·moonwave 문서, quad·table-sim·devplorer 실태 100%. 근거는 stl `typing-limits.md:105-124`.

```lua
--!strict
--[[
	Blocker — value-based emit deferral, as a POLICY on top of `state:Gate`.
	(무엇을 하는가 한 줄 → 공개 표면 요약 → 소유·수명 같은 "왜")
]]
```
- **`--!strict` 를 파일마다 단다.** `.luaurc` 의 `languageMode` 한 단어가 `nonstrict` 로 바뀌면 TypeError 310건이 0건이 된다. `--mode=strict` 플래그도 `.luaurc` 를 덮지 못한다. 파일 지시자만 믿을 수 있다. [기록]
- 머리 주석에는 **코드에서 알 수 없는 것**을 쓴다. 표현을 왜 골랐는지, 소유와 수명, 의존 방향이다. stl `HashMap.luau` 머리("왜 래퍼인가", "크기를 왜 따로 세는가")가 좋은 예다.
- `--!nocheck` 는 따라 할 관례가 아니다(moonwave K-2: 재작성으로 없앨 대상).

## §2 모듈 모양

- 모듈은 테이블(또는 값) **하나를** `return` 한다. 테스트 파일도 끝에서 값을 돌려준다. 안 하면 `module must return a single value` 가 난다.
- 저장소별 틀은 다르다. 그 저장소의 본보기 파일을 열어 따른다.

| 저장소 | 틀 | 본보기 |
|---|---|---|
| stl-luau | `const Kind = Trait.Struct("Stl.이름")` → top-level 함수 → 트레이트 등록 → `Kind.Seal({ … })`. BI 전환 중 — 새 코드는 `research/class-like/` | `src/Collections/Arr.luau`, `HashMap.luau` |
| quad | 프리미티브 = 브랜드 메타테이블 + Pascal 콜론 메서드, 표면 함수는 에러 워커에 태그 | `quad-base/src/Blocker.luau`, `quad-types/src/init.luau`(주석·region 본보기) |
| tbox | `Kind.Kind(tag, methods, optionNames)` + 팩토리 `Kind.New<<TFoo>>(…)`, `table.freeze({ factory = Foo, kind = FooKind })` | `packages/tbox/src/schema/number.luau` |
| devplorer | 모듈 테이블 + 닷 함수, 검증은 `(ok, err)` 반환 | `src/Client/Shared/Remotes/ArgCheck.luau` |

## §3 require 경로 규칙

status: stl `base/architecture.md:37-63,307-341`, tbox `CLAUDE.md:95-117`, moonwave `conventions.md:66-74`(luau 0.734 CLI 실측). Studio 는 rbvm `design/engine-behavior.md:68-83`(Studio 0.742 실측).

| 파일 | `./x` 가 가리키는 곳 | `@self/x` |
|---|---|---|
| `pkg/src/init.luau` | `pkg/x`(init 이 든 폴더의 **형제**) | `pkg/src/x.luau` |
| `pkg/src/a.luau` | `pkg/src/x.luau`(자기 형제) | (해당 없음) |

```lua
-- packages/tbox_squish/src/init.luau
-- 나쁜 예: ../ 는 packages/roblox_packages 를 찾는다 (실제로 이렇게 깨져 있었음)
const Tbox = require("../roblox_packages/tbox")
-- 좋은 예
const Tbox = require("./roblox_packages/tbox")
const Types = require("@self/types")
```
- **require 경로 오류는 정적 검사가 못 잡는다.** 새 모듈에는 그 모듈을 실제로 `require` 하는 테스트를 둔다.
- **인자는 문자열 리터럴로 쓴다.** 동적 경로는 `ambiguous` 에러를 낸다.
- **테스트 엔트리를 `init.luau` 로 짓지 않는다**(`tests/run.luau`). `src/init.luau` 와 겹쳐 `could not reset to requiring context (ambiguous)` 가 난다.
- **require 는 symlink 를 따라가지 않는다.** pesde 워크스페이스 링크를 실행 검증하려면 `cp -rL` 로 복사한 임시 디렉터리에서 돌린다(tbox `mise.toml:28-43`).
- Studio 에서 접두 없는 문자열(`require("x")`)은 에러다. `@Self` 는 대소문자를 무시한다. CLI 와 Studio 의 해석이 같은지는 아직 표로 비교하지 않았다.
- **`@game/…` 절대 경로**는 조건부다(D-12).
  - 클라이언트로 복제돼 위치가 바뀌는 번들에서는 금지한다(devplorer).
  - 고정 위치(`ReplicatedStorage/TableSim`)에서만 도는 코드는 허용한다(table-sim).

## §4 폴더와 층

- 기능마다 폴더를 두고 입구는 `init.luau` 로 한다. 혼자 서는 작은 모듈은 폴더를 만들지 않는다. 사용자는 파일이 한 곳에 몰리면 보기 어렵다는 이유로 quad 를 대대적으로 재배치한 적이 있다(devplorer `conventions.md:62-68`).
- **층을 쌓고 아래층이 위층을 부르지 않는다.**
  - devplorer 의 서버 층은 `Core → Policy → Handlers → Window → Console → init` 이다.
  - stl 의 의존 방향표에 따르면 `HashMap` 은 `Arr` 을 모른다.
  - 규칙을 고칠 땐 `require` 를 grep 해서 확인한다. devplorer 는 처음 쓴 층 규칙이 실제 코드와 달라 거짓이었던 적이 있다.
- 구조를 고치는 코드가 컨테이너 파일 안에 생기면 하위 층으로 뺄지 먼저 본다(stl 3층).

## §5 엔진 무관 로직 떼어 두기

- 오브젝트 모델, 직렬화, 권한 판정, 트리 평탄화, 프로토콜 검증은 **Roblox API 없이** 짜서 `luau` CLI 스펙으로 돌린다(table-sim `:96`, devplorer `:53`).
- 엔진 쪽이 필요하면 최소 mock(부모·자식 트리 + 프로퍼티 bag + 변경 시그널)을 쓴다. Fusion 식 Studio 전용 테스트는 쓰지 않는다(quad `architecture.md:808-819`).
- Roblox 데이터타입을 다루는 순수 라이브러리는 **로드 시점에 `Vector3` 같은 전역을 참조하지 않는다.** 판별은 `typeof(v) == "Vector3"` 문자열 비교로 한다(tbox `CLAUDE.md:149-154`).

## §6 모듈 필드 읽기

status: 조건부 합의(D-11). 두 입장은 조건이 달라 모순이 아니다.

**(a) 나중에 주입되거나 재대입되는 값은 매번 `Module.x` 로 읽는다**(quad H-174, devplorer `State.이름`).
```lua
-- 나쁜 예: Init 시점에 받아 둠 → 백엔드 설치 전 스텁을 영원히 잡는다
local bindLifetime = module.bindLifetime
-- 나쁜 예: 위임 래퍼
local function bindLifetime(...) return module.bindLifetime(...) end
-- 좋은 예: 부를 때마다 읽는다(정적 해시 필드 읽기는 충분히 빠르다)
module.bindLifetime(inst, owner)
```

**(b) 바뀌지 않는 함수는 실측된 뜨거운 루프에서만 지역으로 받는다**(stl perf §14: 0.82x → 0.64x).
```lua
const Push = Arr.PushBack           -- 루프 밖에서 한 번
for i = 1, n do Push(out, f(i)) end
```
(b) 를 초기화·이벤트 경로에까지 퍼뜨리지 않는다. 이득이 재는 오차 안이다.
