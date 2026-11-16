# idioms.md — 문법·데이터 관용구

목차
- §1 `const` 와 `local` — 저장소 관행, 함정 둘
- §2 `if c then a else b` 식 — `and/or` 삼항 금지
- §3 `f<<T>>` 명시 타입 인자
- §4 nil·옵셔널·구멍
- §5 테이블 만들기와 채우기
- §6 전역 대입 함정 — 맨 `function name()`
- §7 메타테이블·메서드에 관한 사실

이 파일에서 답하는 질문
- 이 저장소에서 `const` 를 써도 되나? `local const` 는 왜 안 되나?
- `x and y or z` 를 그대로 둬도 되나?
- `f<<T>>` 는 오타인가?
- 옵셔널 값과 배열 구멍을 어떻게 다루나?
- 메서드 객체로 만들까, 네임스페이스 함수로 만들까?

검증 표기: **[실행]** = luau 0.734·0.742 로 이번에 재현(`/tmp/cd-exp/syn/*.luau`), **[기록]** = 저장소 문서의 실측.

---

## §1 `const` 와 `local`

status: 갈린 규약 — `.claude/base/decisions/D-01`. 저장소 값은 `project-overrides.md`.

규칙:
1. 그 파일의 관행을 따르고 한 파일 안에서 섞지 않는다.
2. 새 파일은 저장소 규칙을 따른다. 기본값은 "재대입 없는 바인딩은 `const`"(stl·tbox·table-sim·devplorer)이다.
3. rbvm 은 `local` 만 쓴다. quad 게시 소스는 실태상 `local` 이다.

`const` 는 `local` 을 **대체**한다. `const function f()` 도 유효하다. [실행]

**함정 1 — `local const`** [실행: 0.734·0.742 모두 실행됨, 린트 경고만]
```lua
-- 나쁜 예: 'const' 라는 지역변수 + 전역 대입 x = 1 이 된다. 문법 에러가 아니다
local const x = 1
-- 좋은 예
const x = 1
```

**함정 2 — `(` 로 시작하는 문장** [실행: stylua 2.5.2]
```lua
-- 나쁜 예: stylua 가 const 뒤의 ';' 를 지워 "Ambiguous syntax" 런타임 에러
const f: any = print
;(f :: (number) -> ())(1)
-- 좋은 예: 지역으로 받아서 부른다
const g = f :: (number) -> ()
g(1)
```
(`local` 뒤에서는 stylua 가 `;` 를 앞 줄 끝으로 옮겨 안전하다. 그래도 규칙은 같게 둔다.)

다른 도구의 `const` 지원 상태는 이렇다.
- lune 0.10.5 는 파싱하지 못한다. [실행]
- selene 0.31.0 은 panic 한다. [기록]
- pesde 0.7.4 이상은 된다. [기록]
- stylua `sort_requires` 는 `const` require 블록을 정렬하지 않는다. [실행]

## §2 `if` 식 — `and/or` 삼항 금지

status: quad `base/architecture.md:766-781`, stl `conventions.md:90`. 반대하는 저장소 없음.

```lua
-- 나쁜 예: 가운데 값이 false/nil 이면 fallback 으로 샌다
local label = isOn and nil or "off"            -- isOn 이어도 "off"
-- 좋은 예
local label = if isOn then nil else "off"
-- 허용: 단순 2항 기본값
local mod = props.Modifier or None
```
- `if … then … else …` 식은 2021-10 부터 공식 문법이다. 에이전트가 `and/or` 로 "고치지" 않는다.
- 분기도 더 적다(조건 하나만 시험). quad 는 가운데 값이 항상 참이어도 예외 없이 금지한다.
- 실제 버그 예는 quad `Dispatch.retractUnder` 정정이다.

## §3 `f<<T>>` 명시 타입 인자

status: rbvm `conventions.md:44-48`, tbox `CLAUDE.md:75`, stl `conventions.md:81-82`.

```lua
-- 이중 꺾쇠는 문법이다(단일 <T> 는 비교와 모호). 고치지 않는다
const proxy = Namespace.GetNamespaceFor<<ProxyNamespace>>(inst)   -- rbvm
const nums = Arr.Of<<number>>()                                     -- stl
const map = HashMap.New<<string, number>>()
-- 콜백을 넘길 땐 타입 인자나 파라미터 주석을 항상
const doubled = Arr.Map<<number>>(a, function(v) return v * 2 end)
```
- 제네릭이 안 풀리면 캐스트보다 이것을 먼저 쓴다.
- 포맷 위험은 `quality.md` §3 에 있다. 하위 폴더에서 stylua 를 돌리면 시프트 연산으로 바뀐다.

## §4 nil·옵셔널·구멍

- **구멍이 생길 수 있으면 타입에 `T?` 로 드러낸다**(stl 질문 T). 타입이 `T` 인데 실제로 `nil` 이 오면 집계 함수가 런타임 그물을 따로 쳐야 한다.
- **`#t` 를 길이로 믿지 않는다.** 가운데 구멍에서의 경계는 정의되지 않았고, 0.734→0.742 에서 실제로 다른 값을 돌려줬다(stl `mise.toml:18`). [기록] 길이를 따로 든다(`{ n = …, data = … }`).
- `x or y` 기본값은 허용한다. "명시적 없음"이 값으로 필요하면 센티널(quad `None`)을 쓴다.
- 맵 키 `nil`·NaN: 넣기는 에러, 조회·삭제는 "없음"(stl 규약). 다른 저장소는 정하지 않았다.
- `any` 를 인덱싱한 뒤 `~= nil` 로 좁히는 데는 함정이 있다 → `luau-types`.

## §5 테이블 만들기와 채우기

수치는 stl `base/perf-measurements.md`(`-O2`, 최소값). [기록]

| 하지 말 것 | 할 것 | 근거 |
|---|---|---|
| 원소 루프로 복사·이동 | `table.move`, `table.create(n)` | stl `conventions.md:146` |
| `table.pack(...)` 로 가변 인자 순회 | `select("#", ...)` + `select(i, ...)` 루프 | 1.6~2.3배 |
| 테이블을 만든 뒤 칸을 하나씩 대입 | 생성자 리터럴에 칸을 다 적는다 | 나중 대입 3배(perf §34) |
| 배열을 큐처럼 앞에서 `nil` 로 비움 | 머리 인덱스를 따로 든다 | 해시 부분으로 이동 1.7배(perf §40) |
| 인스턴스에 길이 필드를 데이터 키와 같이 둠(`self.size`) | `{ data = {…}, size = n }` 래퍼 | `Set("size", v)` 가 길이를 덮음(stl `HashMap.luau` 머리) |
| 가변 인자 내장(`math.max`)을 콜백으로 그대로 넘김 | 람다로 감싼다 | 위치 인자까지 값으로 받음(stl `conventions.md:75`) |

## §6 전역 대입 함정 — 맨 `function name()`

```lua
-- 나쁜 예: 모듈 스코프에서 앞선 local 없이 → 전역 name = function 대입
function helper(x) return x end
-- 좋은 예
local function helper(x) return x end   -- 또는 const function helper(x)
```
- quad 는 `luau-analyze` 의 `GlobalUsedAsLocal` 린트를 게이트에서 실패로 처리한다(`scripts/test.sh:16,34`).
- 린트가 이것을 언제나 잡지는 않는다(quad H-422 주석).

## §7 메타테이블·메서드에 관한 사실

status: 객체 모양은 저장소 설계라 갈린다(D-11). 여기에는 사실만 둔다.

- **콜론 호출은 `__index` 를 한 번 더 거친다.** `a:Len()` 1.00x, `Arr.Len(a)` 0.82x, `local Len = Arr.Len; Len(a)` 0.64x (stl perf §14). [기록]
- **메타테이블이 붙은 테이블의 `t[i]` 는 1.59배 느리다.** 빈 메타테이블도, `rawget` 도 못 피한다. `-O2`/codegen 에서는 1.66~2.00배다(perf §16·§18). [기록]
  - 뜨거운 데이터는 메타테이블 없는 안쪽 테이블에 두고, 루프 앞에서 `const data = self.data` 로 받는다(1.45배, perf §57).
- **메타메서드(`__tostring`, `__eq` …)는 `__index` 로 상속되지 않는다.** 파생 메타테이블은 각자 단다(quad `architecture.md:509`).
- **`__call` 로 콜러블 네임스페이스(`Arr(...)`)를 만들지 않는다.** 제네릭 생성자가 타입 인자를 잃고 모듈 오타도 못 잡는다(stl `conventions.md:38`). [기록]
- **자기 참조 메서드 시그니처를 솔버가 놓친다.** 저장소마다 우회가 다르다. tbox 는 `self: any` 로, stl 은 `return self :: any` 로 피한다. 상세와 버전 의존은 `luau-types`.
