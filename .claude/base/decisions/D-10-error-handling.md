# D-10. 에러 메시지 모양과 던지는 방식

> **상태: 확정(2026-11-11 사용자: 추천대로).** 4절의 추천안을 채택. 하단 '정정' 절이 반영된 추천안으로 확정.

> 작성 2026-11-10. 실험 `/tmp/cd-exp/syn/o2.luau`(luau 0.742, `-O1`/`-O2`).

## 1. 각 프로젝트의 입장

| 프로젝트 | 던지는 방식 | 메시지 모양 | 위치 |
|---|---|---|---|
| quad | 사용자 입력 검증은 `quad-error` 스택 워커(`errorBeforeNearest/errorBefore`), 내부 불변식은 `error(msg, 1)`. 손으로 센 `level` 금지 | `QuadNNNN Subject: reason (got X)`. 영어, ASCII, 부연은 ` - `. 포맷 헬퍼 금지(메시지 리터럴을 raise 줄에 통째로 → grep 가능) | `base/architecture.md:396-493`, `conventions.md:346` |
| stl-luau | `Common.raise(msg)` 만(첫 비라이브러리 프레임에서 던짐). `error(` 는 `Common` 안에만 | `"Module: 설명"`, 접두 `stl:` | `conventions.md:134-138` |
| tbox | `error(...)`(실태 49) | 영어, **소문자로 시작**(`number too big. maximum allowed value is …`) | `CLAUDE.md:79` |
| table-sim, devplorer | 규칙 없음. 실태는 `error("Run must be a function")`, 검증은 `(ok, err)` 반환 | 영어 | `table-sim/.claude/conventions.md:37`, `devplorer/.claude/conventions.md:19` |
| rbvm | `error(...)` 17, `-- TODO: fix error message` 잔존 | 규칙 없음 | `src/signal.luau:54` |

## 2. 실제 근거

- **손으로 센 `level` 이 `-O2` 에서 틀린다.** [실행]
  - `local function check() error("…", 2) end` 를 사용자 함수에서 불렀다.
  - `-O1` 이면 `./o2.luau:7: check: expected number` 로 사용자 줄을 가리킨다.
  - `-O2` 이면 **위치가 사라진다**(`check: expected number`). 인라인되면서 level 2 가 `pcall` C 프레임이 된다.
  - stl(`conventions.md:134`)과 quad(`architecture.md:520-529`, 스파이크 27)가 독립적으로 같은 결론을 냈다. 라이브 Roblox 는 `-O2` 가 기본이다. [기록 + 실행]
- **quad 의 "태그는 테이블 경유로 호출되는 함수에만"**: `-O2` 는 로컬 직접 호출 함수를 인라인하지만 테이블 필드 경유 호출은 인라인하지 않는다. [기록, 스파이크 27, 4개 플래그 조합]
- 메시지 모양 차이(`Quad0042 Subj: …` / `Module: …` / 소문자 시작)는 각 저장소의 공개 계약이다.
  - quad 는 번호가 4.0.0 부터 계약이다(`conventions.md:346`).
  - 서로 맞출 이유가 없다. [판단]
- 공통으로 다섯 저장소가 "에러 메시지는 영어"다(D-08).
- 에러 단언 테스트에는 메시지와 함께 **정확한 사용자 줄**을 단언한다. 메시지만 보면 level 이 틀려도 통과한다(stl `conventions.md:138`). [기록]

## 3. 합의안

### 안 A. 공통 원칙 + 저장소 고유 형식
공통 rules 는 넷이다.
1. 메시지는 영어, raise 줄에 리터럴로 둔다(grep 가능).
2. **라이브러리가 사용자 호출부를 가리켜야 하는 에러는 손으로 센 `error(msg, 2|3)` 을 쓰지 않는다.** 저장소의 raise 헬퍼를 쓰고, 없으면 내부 불변식처럼 `error(msg, 1)` 로 그 자리를 가리킨다.
3. 새 raise 자리에는 메시지와 사용자 줄을 같이 단언하는 테스트를 둔다.
4. 형식(번호, 접두, 대소문자)은 저장소 rules 를 따른다.

| 프로젝트 | 변경량 |
|---|---|
| quad, stl | 0 |
| tbox | 문서 0. `error(msg, 2)` 사용 여부 점검 필요(라이브러리) |
| table-sim, devplorer, rbvm | 앱 코드라 2번의 영향이 작음. 0~수 곳 |

### 안 B. 조건부: 게시 라이브러리만 2·3번 의무, 앱은 권장
- 2·3번의 비용(헬퍼·줄 단언)은 사용자 줄 정확성이 계약인 라이브러리에서만 값어치가 있다.
- 앱(table-sim, devplorer)과 실험 저장소(rbvm)는 권장으로 둔다.

## 4. 추천: 안 A 의 1·4번을 공통 rules 로, 2·3번은 안 B 처럼 "라이브러리면" 조건부

- `-O2` 위치 소실은 재현되는 사실이고 Roblox 기본 모드다. 그래서 규칙 근거가 단단하다.
- 앱 코드까지 줄 단언 테스트를 강제하면 비용 대비 이득이 작다.
- 메시지 형식은 공개 계약이라 저장소마다 다른 것이 정상이다.

## 5. 사용자 확인 질문

"라이브러리 코드에서는 손으로 센 `error(msg, 2)` 대신 저장소의 raise 헬퍼를 쓴다(`-O2` 인라인에서 위치가 사라짐 — 이번에 재현)"를 공통 규칙으로 넣을까요? tbox 는 지금 raise 헬퍼가 없는데, 필요하면 stl 의 `Common.raise` 방식을 권할지도 정해 주세요.

## 정정 (2026-11-10, .claude/scopes/packs/luau-kb/audit/11 §2-11 실측)
- "테이블 필드를 거쳐 호출하면 `-O2` 에서 안전하다"는 `function M.f` 처럼 **대입으로 만든 필드**에만 맞다.
  `local T = { f = function … end }` 처럼 테이블 리터럴 안에 쓴 필드 함수는 인라인된다.
- `error(msg, 2)` 는 위치를 잃기만 하는 것이 아니다. 호출자가 인라인되지 않은 경우에는 **틀린 줄**(호출자의 호출자)을 가리킨다.
- `--!native` / `@native` 는 최적화 수준 2 를 강제하므로 같은 문제가 생긴다. CLI 로 실측했고 엔진 안에서는 확인하지 않았다.
- 실례: quad 를 `-O2` 로 돌리면 테스트 3개가 실패한다. 그중 하나는 `quad-base/src/Relate.luau:28` 의 `error(…, 3)` 때문이다.
- 근거: `.claude/scopes/packs/luau-kb/archive/research/drafts/gaps/optimize-levels.md`, `snippets/optimize-o2-error-level.luau`, `.claude/scopes/packs/luau-kb/archive/research/drafts/gaps/tools/run_opt.sh`
