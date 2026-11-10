---
name: luau-style
description: >-
  Luau 코드의 네이밍, 문법 관용구, 모듈과 require 경로, 파일 길이와 분리(분리 계획기 split-plan.py, 타입 하나를 여러 파일로 나누는 꼴, 기준 예외 표식)·폴더 묶음·데이터와 코드 나누기, 에러 처리, 주석, 포맷(stylua), 테스트 관용, 검증·보고 방식의
  근거와 좋은 예/나쁜 예를 저장소별 차이와 결정 상태(확정/제안)와 함께 제공한다. 타입 검사가 못 잡는 언어 함정
  (table.insert, 순회 중 변경, 가변 인자 nil, 패턴과 UTF-8, NaN 경계 검사, coroutine.resume 의 에러 삼킴)도 다룬다.
  .luau 파일을 새로 쓰거나 고칠 때, 리뷰·감사에서 스타일이나 관용구를 판정할 때, PascalCase/camelCase, const 대 local,
  local const, if-then-else 식 대 and/or, f<<T>>, init.luau 와 @self, error level 과 -O2, pcall 함정, stylua 설정,
  --!strict, TODO 마커, 주석 언어가 질문일 때 쓴다. 타입 시스템 결함은 luau-types, 검사 도구 호출법은 luau-verify,
  require 경로 해석·코루틴 의미론은 luau-runtime, Roblox 엔진 동작은 roblox-engine, 성능 수치는 luau-perf 가 다룬다.
---

# luau-style

공통 필수 규칙은 rules `luau-core.md`(`paths: **/*.luau`)와 `code-structure.md`(D-13 확정)에 한 줄씩 있다. 이 스킬은 그 **근거, 예시, 저장소별 차이, 결정 상태**를 담는다.
저장소의 `.claude/rules/` 나 CLAUDE.md 가 다르게 정하면 **저장소가 이긴다**. 결정 상태와 저장소별 값은 `references/project-overrides.md` 에 있다.

## 1. 먼저 판단할 것

```
편집하려는 .luau 파일이 있다
├─ 사용자가 요청에서 이름·모양을 정했나? ── 예 → 그 이름으로 쓴다. 규칙과 어긋나면 바꾸지 말고, 이유와 함께 이름 변경을 제안한다(일괄 수정은 승인 뒤, naming §3)
├─ 저장소 .claude/rules/*.md 또는 CLAUDE.md 에 스타일 규칙이 있나? ── 예 → 그것을 따른다. 아래는 빈칸만 채운다
├─ 같은 파일에 이미 관행이 있나(const/local, 주석 언어, 함수 케이스)? ── 예 → 파일 관행을 따른다(섞지 않는다)
├─ 같은 폴더 이웃 모듈의 관행이 있나? ── 예 → 이웃을 따른다
└─ 새 저장소·빈 폴더 → naming §3, idioms §1, quality §3 의 기본값
```

```
이 코드는 어디서 도나?
├─ Roblox 전역(Instance, game, Vector3)을 쓴다 → 검사는 luau-lsp + 정의 파일 (quality §5, luau-verify)
├─ 순수 Luau → luau-analyze 로 검사, `luau` CLI 로 테스트 (공개 API 면 DX 확인에 luau-lsp 도)
└─ 복제돼 위치가 바뀌는 번들 → `@game/` 절대 require 를 쓰지 않는다 (modules §3, 제안 D-12)
```

```
에러를 던지려 한다
├─ 내 코드의 불변식 위반(자기 버그) → error(msg, 1) (errors §1)
├─ 사용자 입력이 틀렸고 사용자 줄을 가리켜야 한다
│   ├─ 저장소에 raise 헬퍼가 있다 → 그것을 쓴다
│   └─ 없다 → 손으로 센 level 대신 스택을 걷는 헬퍼(errors §2) 또는 error(msg, 1)
└─ 받은 에러를 다시 던진다 → error(e, 0) (errors §1)
```

## 2. 질문 → 읽을 파일

| 이런 질문/상황이면 | 읽을 곳 |
|---|---|
| 이름을 Pascal 로? camel 로? 파일 이름은? `T` 접두? | `references/naming.md` §1–3 |
| 공개 이름 변경, 필드가 메서드를 가림 | `references/naming.md` §4 |
| `const` 를 써도 되나, `local const`, `(` 로 시작하는 문장 | `references/idioms.md` §1 |
| `a and b or c` 를 고쳐야 하나, `if` 식이 오타인가 | `references/idioms.md` §2 |
| `f<<T>>` 가 오타인가 | `references/idioms.md` §3 |
| 옵셔널·구멍·`#t`, 테이블을 만들고 채우는 법 | `references/idioms.md` §4–5 |
| `function name()` 이 전역이 되나, 메타메서드 상속 | `references/idioms.md` §6–7 |
| 파일 머리, `--!strict`, 모듈이 돌려주는 값 | `references/modules.md` §1–2 |
| `require("./x")` 가 엉뚱한 파일을 찾는다, `@self`, `init.luau` 엔트리 | `references/modules.md` §3 |
| 패키지 사본이 둘, 타입 전용 require, 주입 값을 지역에 받기 | `references/modules.md` §4–5 |
| 에러 메시지 모양, 되던지기, err 의 타입 | `references/errors.md` §1 |
| `error(msg, 2)` 가 위치를 잃거나 틀린 줄을 가리킨다 (`-O2`, native) | `references/errors.md` §2 |
| `pcall(f(x))`, xpcall traceback, C 프레임 | `references/errors.md` §3 |
| 검증기에서 NaN·메타메서드·사용자 패턴 | `references/errors.md` §4 |
| 에러 테스트에서 무엇을 단언하나 | `references/errors.md` §5 |
| 주석 언어, `---`, `Ref:`, `--#region` | `references/quality.md` §1 |
| `TODO` 마커 | `references/quality.md` §2 |
| stylua 가 코드를 망쳤다, `stylua: ignore` 가 안 먹는다 | `references/quality.md` §3 |
| 테스트 관용(러너, 경계, 오라클) | `references/quality.md` §4 |
| 검사기 선택, exit code, "통과"라고 보고해도 되나 | `references/quality.md` §5 |
| `table.insert` 이상 동작, 순회 중 변경, 정렬 안정성 | `references/pitfalls.md` §1–2 |
| 가변 인자 `nil`, 다중 반환 잘림 | `references/pitfalls.md` §3 |
| `%a`·UTF-8·`%q` | `references/pitfalls.md` §4 |
| `coroutine.resume` 에러, yield 경계, 한 번만 초기화 | `references/pitfalls.md` §6 |
| 공유 설정 테이블, 얕은 clone | `references/pitfalls.md` §8 |
| 파일이 너무 긴가, 폴더로 묶을까, 기준을 넘겨 둘 이유가 있나(예외 표식) (D-13) | `references/structure.md` §2–5 |
| 큰 파일을 어디서 자르나, 타입 하나를 여러 파일로, 전방 선언·닫개 상태 | `references/splitting.md`, `scripts/split-plan.py <파일>` |
| 요청 표·세트 배치·색을 코드로 쓸까 표로 쓸까 생성할까 | `references/structure.md` §6 |
| 저장소 구조를 숫자로 재고 싶다, 성공·실패 사례 | `scripts/structure-scan.py`, `references/structure.md` §7–8 |
| 저장소마다 다른 값, 결정 상태 | `references/project-overrides.md` |

## 3. 다섯 원칙

1. **도구가 강제하는 것은 도구에 맡긴다.** 포맷은 저장소 `stylua.toml` 이 정하고, 판정은 게이트의 exit code 로 한다.
2. **주변을 따른다.** 파일 → 이웃 모듈 → 저장소 규칙 → 이 스킬의 기본값 순서다.
3. **조용히 지나가는 실수를 경계한다.** `local const`, 맨 `function`, 하위 폴더 stylua, `-O2` 의 error level, 형제로 풀리는 require, 진단 0건은 모두 에러 없이 틀린다.
4. **관측과 계약을 구분한다.** 테스트가 고정한 지금 동작은 "관측 — 계약 아님"으로 적는다.
5. **실측으로 주장한다.** 근거 스니펫은 `snippets/style-*`, 결과는 `snippets/RESULTS.md` 에 있다. 수치에는 Luau 버전을 적는다.

## 4. 이 스킬이 다루지 않는 것

- 타입 시스템 한계와 솔버 결함, type function → `luau-types`
- 측정 방법과 수치(메타테이블 비용, 호출 모양, 문자열) → `luau-perf`
- 검사기 호출법, 음성 대조군, 핀 → `luau-verify`
- require 경로 해석(CLI)·weak 표·코루틴 의미론 → `luau-runtime` / mock, Studio, Roblox 타입 → `luau-roblox` / Roblox 엔진·서비스 동작, Studio 쪽 require → `roblox-engine`·`roblox-net`·`roblox-world`
- 저장소 고유 설계(특정 라이브러리의 API, 트레이트, 오류 번호 체계) → 각 저장소 `.claude/`
