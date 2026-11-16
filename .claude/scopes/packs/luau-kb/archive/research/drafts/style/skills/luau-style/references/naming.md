# naming.md — 이름 짓기

목차
- §1 공통 다섯 규칙(모든 저장소)
- §2 저장소마다 다른 것 — 이웃을 따르는 법과 차이 표
- §3 새 저장소·새 모듈의 기본값(quad·stl 기준)
- §4 어휘와 함정

이 파일에서 답하는 질문
- 이 함수 이름은 Pascal 인가 camel 인가?
- 파일 이름은 대문자로 시작하나?
- `isArr` 는 왜 소문자인가?
- `_` 로 시작하는 필드는 써도 되나?
- 공개 이름을 바꿔도 되나?

---

## §1 공통 다섯 규칙

status: 7개 저장소 문서·실태 일치(2026-11-10). 근거 `.claude/base/decisions/D-09`.

| 대상 | 케이스 | 예(실제 코드) |
|---|---|---|
| 타입 | PascalCase | `Arr<T>`, `HashMapData<K, V>`(stl), `Blocker`(quad) |
| `require` 받은 모듈 지역 | PascalCase | `local Brand = require("./Brand")`(quad), `const Kind = require("../kind")`(tbox — 파일은 소문자여도 지역은 Pascal) |
| 지역 변수·지역 함수 | camelCase | `arrLen`, `moveLen`(stl), `const function walk(value, depth)`(devplorer) |
| 종류 술어 | `isX` camelCase | `stl.isArr(v)`, `isState`(quad), `Kind.isSchema`(tbox) |
| `_` 접두 필드 | 내부 계약 — 언제든 바뀜, 케이싱 규칙 밖 | `module._bookkeeping`, `Timeout._native`(quad) |

나쁜 예와 좋은 예:
```lua
-- 나쁜 예: require 받은 모듈을 camel 로, 술어를 Pascal 로
local errNs = require("./ErrorNamespace")
local function IsHeap(v) … end

-- 좋은 예
local Err = require("./ErrorNamespace")
local function isHeap(v: unknown): boolean … end
```

## §2 저장소마다 다른 것

**규칙: 같은 폴더의 이웃 모듈을 열어 같은 종류의 이름이 어떤 케이스인지 보고 따른다.** 저장소 rules 가 있으면 그것이 우선이다.

| 대상 | quad | stl-luau | tbox | table-sim | devplorer | rbvm |
|---|---|---|---|---|---|---|
| 생성자·팩토리 | Pascal(`Source()`, `New`, `Claim`) | Pascal(`Arr.Of`, `TreeMap.New`) | Pascal | 실태 camel(`Bag.new`) | Pascal | Pascal(`New`) |
| 네임스페이스 연산 | 타입 고유 어휘 Pascal(`Modifier.Overridden`), 범용·엔진·주입 계약 camel(`Dispatch.process`, `bindLifetime`) | Pascal 전부(`Arr.PushBack`), 내부 `Common` 만 camel | 메서드 camel(`checkType`, `canBeNil`) | camel(실태 473/473) | 혼합(camel 395 · Pascal 83) | Pascal(`SetNamespaceFor`) |
| 콜론 메서드 | Pascal(`state:Get()`, `blocker:On()`) | (BI 전환 중) Pascal | camel(`schema.inner:checkType(v)`) | — | — | Pascal |
| 파일 이름 | Pascal(`Blocker.luau`) | Pascal(`HashMap.luau`) | 소문자(`number.luau`) | Pascal | Pascal | 소문자(`signal.luau`) |
| 타입 접두 | 없음 | 없음 | `T`(`TNumber`, `TArray`) | 없음 | 없음 | 없음 |
| 상수 | — | 대문자(`VALUE`, `NEXT`) | — | — | — | — |
| 불리언 연산 | — | `Is…`, 형용사 하나만 접두 없이(`Empty`, `Equal`) | — | — | — | — |

이 차이는 저장소 사이에 통일하지 않는다(D-09). 한 저장소 안에서 새로 섞지 않는 것이 규칙이다.

## §3 새 저장소·새 모듈의 기본값

status: quad `base/architecture.md:688`(2026-09-15 개정)과 stl `conventions.md:14` 의 기준 문장이 같다. 기본값 후보이고 사용자 확인 대기(D-09 질문).

> **값을 만들거나 감싸는 함수(생성자·팩토리·슈거)와 그 타입 고유의 연산은 PascalCase. 판별 술어·생명주기 조작·주입 계약·엔진 내부 멤버는 camelCase.**

경계 판단 질문(quad): "이것이 특정 타입 하나의 전용 소유물인가?" — 예면 Pascal, 아니면 camel.

```lua
-- quad 의 경계 사례: 기존 인스턴스를 받기만 해도 생명주기를 시작시키면 생성자 부류
q.Claim(inst)        -- Pascal: 부기(bk)·소유 등록이 "생긴다"
q.dispose(inst)      -- camel: 누구의 소유물도 아닌 생명주기 조작
q.Backend.isClaimed(inst)  -- camel: 술어
```

## §4 어휘와 함정

- **공개 이름은 바꾸지 않는다.** 게시된 라이브러리에서 이름 변경은 호환성 파괴다(moonwave `conventions.md:59-61`, quad CHANGELOG 규약). 바꿔야 하면 사용자에게 묻는다.
- **`type…` 으로 시작하는 이름을 피한다.** 내장 `type`/`typeof` 와 헷갈린다(stl 은 그래서 토큰 조회를 `Trait.TokenOf` 라 지었다 — 질문 AH).
- **데이터 필드 이름이 메서드 이름과 겹치지 않게 한다.** 메타테이블 객체에서는 인스턴스 필드가 `__index` 보다 먼저 보여 메서드를 가린다. tbox 는 그래서 옵션 이름을 `format` 대신 `encoding` 으로 지었고, `Kind.New` 가 겹치는 이름을 거부한다(`packages/tbox/CLAUDE.md:113`).
  ```lua
  -- 나쁜 예: 데이터 필드 format 이 메서드 format(self) 를 가린다
  local obj = setmetatable({ format = "u8" }, { __index = { format = function(self) return "TNumber" end } })
  print(obj:format())   -- 'attempt to call a string value'
  -- 좋은 예: 필드 이름을 메서드와 다르게
  local obj2 = setmetatable({ encoding = "u8" }, { __index = { format = function(self) return "TNumber" end } })
  ```
- **한 글자 별칭은 처음 나올 때 정체를 밝힌다**(quad: `const D = q.Declaration` — "D 는 `q.Declaration` 의 관례 별칭").
- 어휘 표가 있는 저장소(stl: `Has` 키 / `Contains` 값 / `Merge` / `Concat` / `…Desc` / `At`·`IndexOf`, `FromTable` 복사 / `Adopt` 입양)는 그 표를 따른다.
