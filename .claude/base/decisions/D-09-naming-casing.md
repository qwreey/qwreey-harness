# D-09. 네이밍 케이싱 — 네임스페이스 함수·파일 이름·타입 접두

> **상태: 확정(2026-11-11 사용자: 추천대로).** 4절의 추천안을 채택.

> 작성 2026-11-10. 실태 통계는 `/tmp/cd-exp/sty/src/` 사본에서 정규식으로 셌다(`function X.y` / `function X.Y` 정의, `export type` 이름).

## 1. 각 프로젝트의 입장

| 주제 | quad | stl-luau | tbox | table-sim | devplorer | rbvm |
|---|---|---|---|---|---|---|
| 규칙 위치 | `base/architecture.md:682-751` | `conventions.md:14-32` | `CLAUDE.md:77`, `packages/tbox/CLAUDE.md` | 없음 | `conventions.md:77` | 없음 |
| 생성자·팩토리 | Pascal(`Source()`, `New`, `Claim`) | Pascal(`Arr.Of`, `TreeMap.New`) | Pascal | 실태 `Bag.new`(camel) | Pascal(공개 API) | Pascal(`New`) |
| 네임스페이스 연산 | Pascal(타입 고유 어휘) / camel(범용·엔진·주입 계약 `Dispatch.process`) | **Pascal 전부**(`Arr.PushBack`), 내부 `Common` 만 camel | 메서드 camel(`checkType`) | **camel 전부**(실태 473/473) | 혼합(실태 camel 395 · Pascal 83) | Pascal(실태 92/102) |
| 콜론 메서드 | Pascal(`state:Get()`) | (BI 전환 중) Pascal | camel | (Roblox API 호출만) | — | Pascal |
| 종류 술어 | camel `isState` | camel `stl.isArr` | camel `isSchema` | — | — | — |
| `_` 접두 | 내부 계약, 케이싱 규칙 밖 | — | — | — | — | — |
| 파일 이름 | Pascal(`Blocker.luau`) | Pascal | **소문자**(`number.luau`, `kind.luau`) | Pascal | Pascal | **소문자**(`signal.luau`) |
| 타입 이름 | Pascal | Pascal(`Arr<T>`) | **`T` 접두** Pascal(`TNumber`, 실태 130/158) | Pascal | Pascal | Pascal |
| 상수 | — | 대문자(`VALUE`, `NEXT`) | — | — | — | — |

## 2. 실제 근거

- **공통 규칙이 이미 있다.** quad 와 stl 은 같은 기준을 서로 다른 말로 적었다.
  - quad 2026-09-15 개정: "값을 만들거나 감싸는 함수는 대문자, 술어·생명주기·주입 계약은 소문자".
  - stl 1-5·1-6절: "값을 만들거나 감싸는 것은 대문자, 판별 술어와 지역 변수는 소문자".
  - 두 문서가 서로를 원형으로 인용한다. [기록]
- **차이의 근거**
  - stl 이 연산까지 Pascal 로 둔 근거는 "네임스페이스 함수가 곧 그 타입의 메서드 자리"라는 것이다(AB). 성능·정확성 근거는 없다. [서술]
  - table-sim 의 camel 은 문서 근거가 없고, 코드에서 생긴 관행이다. [서술]
  - tbox 의 `T` 접두는 패키지 고유 규칙이다(`CLAUDE.md:93` "패키지별 타입 네이밍 규칙(`T` 접두사 등)"). 사용자에게 보이는 스키마 타입(`TNumber`)과 런타임 값(`Number`)을 같은 이름공간에서 가르려는 것이다. [추정]
  - 소문자 파일 이름(tbox, rbvm)은 근거 문서가 없다. [서술]
- 기계적 이득은 하나다. `require` 받은 지역 이름 = 파일 이름 = 타입 이름이 되면 grep 한 번에 찾힌다. stl·devplorer 가 이 이유로 Pascal 파일을 쓴다(devplorer `conventions.md:66` "찾기 쉬운 쪽"). [기록]

## 3. 합의안

### 안 A. 공통 핵심 5개 + 나머지는 프로젝트 rules
공통(충돌 없음)은 다섯이다.
1. 타입은 Pascal.
2. `require` 받은 모듈 지역은 Pascal.
3. 지역 변수·지역 함수는 camel.
4. 종류 술어는 `isX` camel.
5. `_` 접두는 내부.

프로젝트 rules 에 둘 것은 넷이다.
- 네임스페이스 연산·메서드의 케이스(quad·stl·rbvm Pascal / table-sim·devplorer camel / tbox camel 메서드)
- 파일 이름 케이스
- 타입 접두(tbox `T`)
- 상수 표기

| 프로젝트 | 변경량 |
|---|---|
| quad, stl | 0(기존 표를 rules 로 옮기면 됨) |
| tbox, rbvm, table-sim, devplorer | 프로젝트 rules 2~3줄 신설(지금은 규칙이 문서에 없거나 흩어짐). 코드 0 |

### 안 B. 공통 기본값으로 quad·stl 기준까지 승격 — "값을 만들거나 감싸는 공개 함수는 Pascal, 그 밖은 camel"
- 새 저장소와 새 모듈의 기본값으로 둔다. 기존 저장소는 rules 에서 "이 저장소는 연산도 camel" 식으로 override 한다.
- table-sim·devplorer 는 override 한 줄이 필요하고, 코드는 0이다.

## 4. 추천: 안 A 를 공통 rules 로, 안 B 의 기준 문장은 스킬 `naming.md` 의 "새 저장소 기본값"으로

- 공통 rules 에 넣는 순간 강제가 된다. 그러니 현재 7곳이 모두 따르는 다섯만 넣는다.
- quad·stl 기준(만들거나 감싸면 Pascal)은 근거가 문서화된 유일한 기준이다. 스캐폴딩과 새 저장소 기본값으로 쓰기 좋지만, 이미 camel 인 저장소 둘을 고칠 이득은 없다.
- 에이전트에게 중요한 것은 "주변 모듈의 케이스를 따른다"는 한 줄이다. 그 줄을 공통 rules 에 둔다.

## 5. 사용자 확인 질문

네이밍은 공통으로 "타입·모듈 Pascal, 지역 camel, 술어 `isX`, `_`는 내부, 그 밖은 주변 코드를 따른다"만 강제하고, 네임스페이스 함수 케이스(quad·stl 의 Pascal 과 table-sim·devplorer 의 camel)는 저장소별로 두는 것으로 괜찮을까요? 새 저장소의 기본값을 quad·stl 기준으로 할지도 정해 주세요.
