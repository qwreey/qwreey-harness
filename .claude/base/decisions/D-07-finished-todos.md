# D-07. 끝난 할 일 처리 (`.claude/todos.md`) 와 코드 `TODO` 마커

> **상태: 확정(2026-11-11 사용자: 추천대로).** 4절의 추천안을 채택.

> 작성 2026-11-10. 크기는 `wc -c`, 구획 크기는 `awk`(제목별 바이트)로 쟀다.

## 1. 각 프로젝트의 입장

| 프로젝트 | 규칙 | 위치 | 지금 크기·실태 [실행] |
|---|---|---|---|
| stl-luau | **끝난 일은 지운다.** 경위는 커밋 메시지나 `archive/todos-history.md`. 10KB 안팎 | `stl-luau/.claude/todos.md:3-4` | 5.5KB, `doc-check.py` BUDGET 이 크기 감시 |
| quad | **해소된 항목은 그 자리에서 지운다**, 개수·목록은 소스를 가리킴 | `quad/.claude/todos.md:3-5` | 10.5KB. 00번에 날짜별 경과가 남음(감사 03 §7) |
| moonwave-luau | 정의는 `migration-plan.md`, 여기는 "지금 어디·다음 뭘" | `moonwave-luau/.claude/todos.md:3-4` | 3.0KB |
| rbvm | "작업이 끝나면 갱신"(지울지 명시 없음) | `rbvm/.claude/todos.md:3-4`, `conventions.md:81` | 4.9KB |
| table-sim | **지우지 않고 맨 아래 "된 것"으로 내린다**(2026-10-12 사용자 발언 근거) | `table-sim/.claude/todos.md:5-8` | **40.6KB 중 "된 것" 구획 17.0KB(42%, 101줄, `todos.md:160-260`)** |
| devplorer | 규칙 없음. 실태는 **취소선 + `[날짜 끝]`** 을 제자리에 남김 | `devplorer/.claude/todos.md:6-7` | 16.6KB, `~~` 20줄 |

코드 안 `TODO` 마커는 이렇다.

| 프로젝트 | 실태 |
|---|---|
| quad | 자율 구현 규약 시절 "코드엔 `-- TODO(H-nnn)` 마커만"(`conventions.md:525`, 마일스톤 종결 뒤 잔존 규약). 게시 소스는 원장 번호만 남기지 말고 이유 문장 + `Ref:` 꼬리(`conventions.md:345`). 게시 소스의 `TODO` 는 0건 |
| rbvm | 맨 `-- TODO:` 15건, 원장 연결 없음(`src/signal.luau:54,71`, `require.luau:16`) |
| stl, tbox, table-sim, devplorer | 0건 |

## 2. 실제 근거

- **table-sim 의 "내린다" 규칙은 근거가 있다.** 사용자가 "말했던 것이 다 검토되었는지" 대조하려 한 일회성 요구였다(`todos.md:5-6` 인용).
  - 상시 규칙이 될 이유는 그 발언에 없다. 대가는 매 세션 17KB(약 6~8k 토큰)를 로드하는 것이다. [실행 측정]
- **stl·quad 의 "지운다" 근거**: 항상 로드되는 문서라 크기 예산이 있다.
  - stl `doc-check.py` BUDGET(감사 04 §2.1)은 경위를 커밋·archive 가 가지게 한다. [기록]
- devplorer 의 취소선은 규칙이 아니라 관습이다. [서술]
- 공식 권장(감사 01)은 CLAUDE.md·import 를 짧게 유지하라는 것이다. 끝난 항목은 행동을 바꾸지 않는다.
- 코드 `TODO`: quad 는 공개 소스의 원장 번호가 외부 기여자에게 무의미하다는 이유로 `Ref:` 꼬리 규약을 만들었다(사용자 결정 2026-10-20). rbvm 의 맨 `TODO` 는 추적처가 없다. [기록]

## 3. 합의안

### 안 A. 공통 기본값 "지운다" + 기록은 다른 곳
- `todos.md` 에는 열린 일만 둔다. 끝나면 지운다.
- 남길 경위는 커밋 메시지 → `archive/todos-history.md`(선택) 순으로 둔다.
- 사용자 발언 대조처럼 "된 것 목록"이 필요한 순간에는 그 세션에 `session/` 또는 `archive/` 파일을 만든다.

| 프로젝트 | 변경량 |
|---|---|
| stl, quad, moonwave | 0 |
| rbvm | 문구 1줄("끝나면 지운다") |
| table-sim | 규칙 1줄 교체 + "된 것" 17KB 를 `archive/todos-done-2026-10.md` 로 이동 |
| devplorer | 취소선 20줄 이동 |

### 안 B. 조건부: 상시 로드 문서면 지운다, 아니면 자유
- `@import` 되는 todos 는 끝난 항목을 지운다.
- 상시 로드되지 않는 할 일 문서(예: `backlog.md`, 또는 SessionStart 훅이 열린 항목만 주입하는 구조, `.claude/archive/plan/PLAN-2026-11.md` §1 ③)는 형식이 자유다.
- table-sim 이 "된 것" 보존을 원하면 그 구획을 import 되지 않는 파일로 분리하는 것만으로 충족된다.

코드 `TODO` 는 두 안 모두 같은 규칙을 둔다.
- `-- TODO:` 는 **이유 문장 + 추적처**(`Ref: <날짜> <원장/이슈 번호>` 또는 `todos.md` 항목)를 붙인다.
- 끝나면 마커를 지운다.
- 공개 패키지 소스에는 원장 번호만 남기지 않는다(quad 규약의 일반화).

## 4. 추천: 안 B

- 문제의 본질은 "끝난 항목을 보존하느냐"가 아니라 "**매 세션 로드되느냐**"다.
- 안 B 는 table-sim 사용자의 보존 요구를 존중한다(파일만 분리). 동시에 로드 낭비를 없앤다.
- 이 규칙은 `.luau` 편집 규칙이 아니다. 그래서 `luau-core.md` 가 아니라 사용자 레벨 CLAUDE.md 또는 `paths: [".claude/todos.md"]` rules 에 둔다.
- 코드 `TODO` 규칙 한 줄만 `luau-core.md` 에 들어간다.

## 5. 사용자 확인 질문

table-sim 의 "된 것을 아래로 내린다"는 2026-10-12 의 대조 작업 때문에 생긴 규칙인데 지금 todos 의 42%(17KB)를 차지합니다. "항상 로드되는 todos 에서는 끝난 일을 지우고, 보존하고 싶으면 import 되지 않는 파일로 옮긴다"로 통일해도 될까요?
