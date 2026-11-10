---
name: luau-style
description: >-
  Luau 코드의 네이밍·관용구·모듈 구조·파일 길이와 분리·폴더 묶음·데이터와 코드 나누기·에러 처리·주석·포맷·테스트 관용의 근거와 좋은 예/나쁜 예를 저장소별 차이와 함께 제공한다.
  .luau 파일을 새로 쓰거나 고칠 때, 리뷰·감사에서 스타일이나 관용구를 판정할 때, 이름(PascalCase/camelCase)·const 대 local·
  if-then-else 식·f<<T>>·require 경로(@self, init.luau)·error 레벨·stylua 설정·--!strict·TODO 마커가 질문일 때 쓴다.
  타입 시스템 결함은 luau-types, 성능 측정은 luau-perf, 검사 도구 사용법은 luau-verify 가 다룬다.
---

# luau-style

공통 필수 규칙은 사용자 레벨 rules `luau-core.md`(`paths: **/*.luau`)에 한 줄씩 있다. 이 스킬은 그 **근거, 예시, 저장소별 차이**를 담는다.
저장소의 `.claude/rules/` 나 CLAUDE.md 가 다르게 정하면 **저장소가 이긴다**. 갈린 규약의 합의 상태는 `references/project-overrides.md` 에 있다.

## 1. 먼저 판단할 것 (결정 트리)

```
편집하려는 .luau 파일이 있다
├─ 저장소 .claude/rules/*.md 또는 CLAUDE.md 에 스타일 규칙이 있나? ── 예 → 그것을 따른다. 아래는 빈칸만 채운다
├─ 같은 파일에 이미 관행이 있나(const/local, 주석 언어, 함수 케이스)? ── 예 → 파일 관행을 따른다(섞지 않음)
├─ 같은 폴더 이웃 모듈의 관행이 있나? ── 예 → 이웃을 따른다
└─ 새 저장소·빈 폴더 → naming§3, idioms§1 의 "새 저장소 기본값"
```

```
이 코드는 어디서 도나?
├─ Roblox 전역(Instance, game, Vector3)을 쓴다 → 검사는 luau-lsp + 정의 파일 (luau-verify)
├─ 순수 Luau(라이브러리, 엔진 무관 로직) → luau-analyze, `luau` CLI 로 테스트
└─ 위치가 바뀌는 번들(복제되는 클라이언트 코드) → `@game/` 절대 require 금지 (modules§3)
```

```
라이브러리(게시 패키지)인가?
├─ 예 → 에러는 raise 헬퍼 + "메시지 + 사용자 줄" 단언 테스트 (quality§1), 공개 이름 변경 금지 (naming§4)
└─ 아니오(앱·도구) → quality§1 의 리터럴·영어 규칙만
```

## 2. 질문 → 읽을 파일

| 이런 질문/상황이면 | 읽을 곳 |
|---|---|
| 이름을 Pascal 로? camel 로? 파일 이름은? `T` 접두? | `references/naming.md` §1–3 |
| `const` 를 써도 되나, `local const` 가 왜 문제인가 | `references/idioms.md` §1 |
| `a and b or c` 를 고쳐야 하나, `if` 식이 오타인가 | `references/idioms.md` §2 |
| `f<<T>>` 가 오타인가, 언제 쓰나 | `references/idioms.md` §3 |
| 옵셔널·구멍·`nil` 키, `x or y` | `references/idioms.md` §4 |
| 테이블을 어떻게 만들고 채우나(벌크, 가변 인자) | `references/idioms.md` §5 |
| `function name()` 이 전역이 되나 | `references/idioms.md` §6 |
| 메타테이블 메서드냐 네임스페이스 함수냐 | `references/idioms.md` §7, `project-overrides.md` D-11 |
| 파일 머리, 모듈 모양, `return` | `references/modules.md` §1–2 |
| `require("./x")` 가 왜 안 되나, `@self`, `init.luau` | `references/modules.md` §3 |
| 폴더·층·순환 | `references/modules.md` §4 |
| 파일이 너무 긴가, 어떻게 나누나, 폴더로 묶을까 | `references/structure.md` §2–5 |
| 요청 표·세트 배치·색을 코드로 쓸까 표로 쓸까 생성할까 | `references/structure.md` §6 |
| 저장소 구조를 숫자로 재고 싶다 | `scripts/structure-scan.py` (`references/structure.md` §8) |
| 주입되는 값을 지역에 받아도 되나 / 루프에서 캐시 | `references/modules.md` §6 |
| 에러 메시지 모양, `error(msg, 2)` | `references/quality.md` §1 |
| 주석 언어, `---` 문서 주석, `Ref:`, `--#region` | `references/quality.md` §2 |
| stylua 가 코드를 망쳤다 / 설정 | `references/quality.md` §3 |
| 테스트를 어떻게 쓰나(프레임워크 없음, 경계, 오라클) | `references/quality.md` §4 |
| 통과했다고 보고해도 되나 | `references/quality.md` §5 |
| `TODO` 마커 | `references/quality.md` §6 |
| 저장소마다 다른 값(stylua, 핀, 러너, 타입 함수) | `references/project-overrides.md` |

## 3. 다섯 원칙 (모든 저장소 공통)

1. **도구가 강제하는 것은 도구에 맡긴다.** 포맷은 저장소 `stylua.toml` 이 정하고 판정은 게이트 exit code 로 한다. 문서로 외우지 않는다.
2. **주변을 따른다.** 파일 → 이웃 모듈 → 저장소 규칙 → 이 스킬의 기본값 순서다.
3. **조용히 지나가는 실수를 경계한다.** 예: `local const`, 하위 폴더 stylua, `-O2` 의 error level, require 경로, 진단 0건. 이들은 에러 없이 틀린다.
4. **관측과 계약을 구분한다.** 테스트가 고정한 지금 동작은 "관측 — 계약 아님"으로 적는다.
5. **성능·타입 주장은 실측으로 한다.** 수치에는 Luau 버전을 같이 적는다.

## 4. 이 스킬이 다루지 않는 것

- 타입 시스템 한계와 솔버 결함(제네릭 누수, 변성, 재귀 타입, 타입 함수 함정 표) → `luau-types`
- 측정 방법과 수치(메타테이블 세금 모드별 표, codegen) → `luau-perf`
- 검사기 사용법(음성 대조군, 한도 플래그, 핀 올리기) → `luau-verify`
- 저장소 고유 설계(stl 트레이트, quad 디스패치·QuadNNNN, tbox Kind, rbvm GC) → 각 저장소 `.claude/`

## 5. 출처

인벤토리 `claude-doctor/drafts/style/inventory.md`, 결정 `claude-doctor/decisions/D-01…D-12`(2026-11-10). 예시 코드는 quad·stl-luau·tbox·devplorer·table-sim·rbvm 의 실제 패턴을 줄여 옮겼다.
