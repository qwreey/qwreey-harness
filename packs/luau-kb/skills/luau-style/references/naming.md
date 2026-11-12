---
title: "이름 짓기"
description: "PascalCase·camelCase 공통 다섯 규칙(타입, require 받은 모듈 지역, isX 술어, _ 필드), 저장소마다 갈리는 케이스는 이웃 모듈을 따름, 새 저장소 기본값, 사용자가 정한 이름 처리, 필드가 메서드를 가리는 함정"
keywords:
  - "PascalCase"
  - "camelCase"
  - "네이밍 케이싱"
  - "naming convention"
  - "이름 짓기"
  - "파일 이름 대소문자"
  - "T 접두"
  - "isX 술어"
  - "_ 접두 필드"
  - "생성자 이름"
  - "공개 이름 변경"
  - "이름 변경 제안"
  - "필드가 메서드를 가림"
  - "field shadows method"
  - "한 글자 별칭"
kind: reference
category: luau/style/naming
tags: [policy]
last_verified: 2026-11-10
last_confirmed:
  - luau 0.734
  - luau 0.742
---
# naming — 이름 짓기

## 이 파일이 답하는 질문
- 이 함수 이름은 PascalCase 인가 camelCase 인가?
- 파일 이름은 대문자로 시작하나? 타입에 `T` 접두를 붙이나?
- `isArr` 같은 술어는 왜 소문자인가? `_` 로 시작하는 필드는 써도 되나?
- 공개 이름을 바꿔도 되나? 데이터 필드 이름이 메서드를 가릴 수 있나?

## 목차
- §1 공통 다섯 규칙 (모든 저장소)
- §2 저장소마다 다른 것 — 이웃을 따르는 법
- §3 새 저장소의 기본값 (제안)
- §4 어휘와 함정

---

## §1 공통 다섯 규칙
status: described (관례) · last-confirmed: 2026-11-10 저장소 7곳 문서·코드 실태 · 근거: claude-doctor `.claude/base/decisions/D-09-naming-casing.md` §1–2

일곱 저장소(quad, stl-luau, tbox, table-sim, devplorer, rbvm, moonwave-luau)가 문서와 코드에서 모두 따르는 규칙이다. 그래서 공통 rules 에 넣었다.

| 대상 | 케이스 | 예 |
|---|---|---|
| 타입 | PascalCase | `Arr<T>`, `HashMapData<K, V>`, `Blocker` |
| `require` 로 받은 모듈 지역 | PascalCase. 파일 이름이 소문자여도 지역은 Pascal | `local Brand = require("./Brand")`, `const Kind = require("../kind")` |
| 지역 변수·지역 함수 | camelCase | `arrLen`, `const function walk(value, depth)` |
| 종류 술어 | `isX` (camelCase) | `isArr(v)`, `isState(v)` |
| `_` 로 시작하는 필드 | 내부 계약. 언제든 바뀔 수 있고 케이스 규칙 밖이다 | `module._bookkeeping` |

```lua
-- 나쁜 예: require 받은 모듈을 camel 로, 술어를 Pascal 로
local errNs = require("./ErrorNamespace")
local function IsHeap(v) … end

-- 좋은 예
local Err = require("./ErrorNamespace")
local function isHeap(v: unknown): boolean … end
```

## §2 저장소마다 다른 것 — 이웃을 따르는 법
status: described · last-confirmed: 2026-11-10 실태 · 근거: `decisions/D-09-naming-casing.md` §1
> 정책: 결정(D-09, 2026-11-11). "§1 의 다섯만 공통으로 강제하고 나머지는 저장소 rules 가 정한다". 저장소 rules 가 있으면 그것이 이긴다.

**규칙: 같은 폴더의 이웃 모듈을 열어, 같은 종류의 이름이 어떤 케이스인지 보고 따른다.** 한 저장소 안에서 새로 섞지 않는다.

갈리는 대상은 다음과 같다(2026-11-10 스냅숏. 저장소별 값은 `project-overrides.md` §1).
- 네임스페이스 연산과 생성자: Pascal 계열(quad·stl·rbvm), camel 계열(table-sim·devplorer), 섞임(devplorer 실태)
- 콜론 메서드: Pascal(quad·rbvm), camel(tbox)
- 파일 이름: Pascal 다수, 소문자(tbox·rbvm)
- 타입 접두 `T`(`TNumber`): tbox 만 쓴다
- 상수 대문자(`VALUE`), 불리언 연산 `Is…` 접두: stl 만 쓴다

## §3 새 저장소의 기본값
status: described · 근거: quad `.claude/base/architecture.md:688`(2026-09-15 개정), stl-luau `.claude/conventions.md:14` — 두 저장소의 기준 문장이 같다
> 정책: 결정(D-09, 2026-11-11). 이 기준(값을 만들거나 감싸는 공개 함수는 Pascal, 그 밖은 camel)을 새 저장소 기본값으로 쓴다. 이미 camel 인 저장소를 고치지는 않는다. 저장소 rules 가 정하면 그쪽을 따른다.

> **값을 만들거나 감싸는 함수(생성자·팩토리·슈거)와 그 타입 고유의 연산은 PascalCase. 판별 술어·생명주기 조작·주입 계약·엔진 내부 멤버는 camelCase.**

**사용자가 정한 이름이 규칙과 어긋나면 바꾸지 말고, 이유와 함께 이름 변경을 제안한다(일괄 수정은 승인 뒤).** (사용자 결정 D-13 의 4, 2026-11-10)
- 요청에 `add(name, count)` 처럼 이름이 있으면 코드는 그 이름으로 쓴다. 이 절의 기본값은 이름이 정해지지 않았을 때만 쓴다.
- 그 이름이 이 절이나 저장소 규칙과 어긋나면 작업 보고에 제안을 적는다. 예: "`add` 는 이 저장소 기본값(타입 고유 연산은 Pascal)이면 `Add` 입니다. 바꿀까요?"
- 제안은 바람직하다. 사용자도 이름을 잘못 지을 수 있다. 다만 승인 전에 고치지 않는다. 이미 여러 파일에 퍼진 이름이면 승인 뒤 한 커밋으로 일괄 바꾼다.

경계를 판단하는 질문은 하나다. "이것이 특정 타입 하나의 전용 소유물인가?" 예면 Pascal, 아니면 camel 이다.

```lua
Thing.New(opts)        -- Pascal: 값을 만든다
Thing.Claim(inst)      -- Pascal: 기존 값을 받아도 소유·수명이 "생긴다"면 생성자 부류
Thing.dispose(inst)    -- camel: 누구의 소유물도 아닌 생명주기 조작
Thing.isClaimed(inst)  -- camel: 술어
```

## §4 어휘와 함정
status: described (공개 이름·어휘) / verified (필드가 메서드를 가림) · last-confirmed: luau 0.742 (0.734 동일) · 근거: `snippets/style-metatable-shadow-inherit.luau`, tbox `packages/tbox/CLAUDE.md:113`, moonwave-luau `.claude/conventions.md:59-61` · 후보 Q-077

- **공개 이름은 바꾸지 않는다.** 게시된 라이브러리에서 이름 변경은 호환성 파괴다. 바꿔야 하면 사용자에게 묻는다.
- **`type…` 으로 시작하는 이름을 피한다.** 내장 `type`/`typeof` 와 헷갈린다. 예를 들어 "타입 토큰 조회"는 `TokenOf` 처럼 짓는다.
- **데이터 필드 이름이 메서드 이름과 겹치지 않게 한다.** 메타테이블 객체에서는 인스턴스 필드가 `__index` 보다 먼저 보인다. 그래서 같은 이름의 메서드가 가려진다.
  ```lua
  -- 나쁜 예: 데이터 필드 format 이 메서드 format(self) 를 가린다
  local obj = setmetatable({ format = "u8" }, { __index = Methods })
  obj:format()   --> attempt to call a string value
  -- 좋은 예: 필드 이름을 메서드와 다르게(encoding)
  local obj = setmetatable({ encoding = "u8" }, { __index = Methods })
  ```
  옵션 이름을 받는 생성자라면 메서드와 겹치는 이름을 생성 시점에 거부하는 것도 방법이다.
- **한 글자 별칭은 처음 나올 때 정체를 밝힌다.** 예: `const D = Lib.Declaration -- D 는 Lib.Declaration 의 관례 별칭`.
- 저장소에 어휘 표가 있으면 따른다(예: `Has` 키 / `Contains` 값, `FromTable` 은 복사 / `Adopt` 는 입양).
