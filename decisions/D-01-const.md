# D-01. `const` 바인딩

> 작성 2026-11-10. 실험은 `/tmp/cd-exp/` 에서 했고 원천 저장소는 읽기만 했다.
> 근거 표기: **[실행]** = 이번에 직접 돌려 확인, **[기록]** = 원천 문서/커밋이 실측이라 적은 것, **[서술]** = 근거 없는 서술·관습.

## 1. 각 프로젝트의 입장

| 프로젝트 | 입장 | 근거 위치 | 코드 실태 [실행] |
|---|---|---|---|
| rbvm | **금지**. `local` 만. 2026-08-25 에 `src/` 200곳을 `local` 로 되돌림 | `rbvm/.claude/conventions.md:28-37` | `const` 0 / `local` 244 |
| quad | **채택(새 코드)**, 기존 `local` 은 일괄 전환 안 함 | `quad/.claude/base/architecture.md:783` | 게시 소스 4패키지에서 `const` **0줄**, `local` 1,440줄. 채택 뒤 `quad-base/src` 커밋 133개 |
| stl-luau | **기본**. 재대입 없는 바인딩은 `const`, `local const` 함정 경고 | `stl-luau/.claude/conventions.md:89`, `base/architecture.md:35` | `const` 1,963 / `local` 511 |
| tbox | **기본**. 재할당이 필요할 때만 `local` | `tbox/CLAUDE.md:74`, `tbox/mise.toml:11` | `const` 538 / `local` 15 |
| table-sim | **기본**. 함수도 `const function` | `table-sim/.claude/conventions.md:103` | `const` 4,013 / `local` 357 |
| devplorer | **기본**. 함수도 `const` | `devplorer/.claude/conventions.md:76` | `const` 6,095 / `local` 682 |
| moonwave-luau | **미정**(재작성 코드에서 정함, 질문 Q5–Q7) | `moonwave-luau/.claude/conventions.md:51-52` | 기존 `init.luau` 는 `local` 만 |

## 2. 입장이 생긴 실제 근거

- **rbvm 의 금지 근거는 사라졌다.** 이유는 "pesde 가 `const` 선언에서 자동 타입 익스포트를 못 한다"(2026-08-24, `rbvm/.claude/conventions.md:34-35`)였다.
  - pesde 0.7.4 에서 해소됐다. "타입 스텁 추출기가 `const` 를 파싱한다(0.7.3 은 failed to parse)" (`tbox/mise.toml:11`), "게시 검증기가 `const` 를 받는다(0.7.3은 거부, 실측)" (`quad/mise.toml:10`). [기록]
  - rbvm 문서는 2026-08-25 이후 갱신되지 않았다(`rbvm/CLAUDE.md:7` "[2026-08-25 기준]").
- **rbvm 이 적은 부수 효과는 사실이다.** stylua 2.5.2 의 `sort_requires` 는 `local X = require(...)` 블록만 정렬하고 `const` 블록은 그대로 둔다. [실행: `/tmp/cd-exp/syn/s1.luau`]
- **`const` 를 쓰면 stylua 버그 하나를 밟는다.** `const f = …` 다음 줄의 `;(f :: T)(1)` 에서 stylua 2.5.2 가 `;` 를 지운다.
  - 그 결과 런타임에 `Ambiguous syntax` 에러가 난다.
  - `local` 다음이면 `;` 를 앞 줄 끝으로 옮겨 안전하다.
  - [실행: `/tmp/cd-exp/syn/p1.luau`. stl 이 `conventions.md:93` 에 적은 것과 같음]
- **`local const x = 1` 은 문법 에러가 아니다.** `const` 라는 지역변수와 전역 대입 `x = 1` 이 된다. [실행]
  - 0.734·0.742 둘 다 실행되고, 린트(`SameLineStatement`, `UninitializedLocal`)만 경고한다. (→ 정정 절 참고)
  - stl `conventions.md:89` 와 일치한다.
- **`const function f()` 는 유효한 문법이다**(0.734·0.742 실행·분석 모두 통과). [실행: `c1.luau`]
- **lune 0.10.5 는 `const` 를 파싱하지 못한다**(`Incomplete statement`). [실행] → D-03.
- **quad 의 "채택"은 문서상이다.** 채택 뒤 133개 커밋이 있었는데도 게시 소스에 `const` 가 없다. 사실상의 관행은 `local` 이다. [실행]
  - 원인은 "기존 `local` 은 일괄 전환하지 않는다"(3.0.0 게시 전 diff 회피)는 단서와 관성이다.
  - 이를 막는 기술적 이유는 없다.
- `const` 의 이득(재대입을 컴파일 타임에 거부, `Variable 'x' is constant…`)은 모든 문서가 같은 서술을 쓴다. 성능 이득은 어디에도 실측이 없다. [서술]

## 3. 합의안

### 안 A. 공통 기본값 `const` + 프로젝트가 rules 에서 override
- 공통 규칙: "재대입 없는 바인딩은 `const`. `local const` 금지. `const` 뒤 `(` 로 시작하는 문장 금지. 기존 파일은 그 파일의 관행을 따른다."
- override: rbvm, quad 는 `.claude/rules/luau-local.md` 에 "이 저장소는 `local`(사유: …)"를 한 줄 둔다.

| 프로젝트 | 변경량 |
|---|---|
| stl, tbox, table-sim, devplorer | 0 |
| rbvm | rules 한 줄. 근거가 사라졌으니 사용자가 금지를 풀면 0 |
| quad | rules 한 줄("파일 안 일관성 우선"), 코드 0 |
| moonwave | Q5–Q7 결정에 맞춰 0 또는 한 줄 |

### 안 B. 조건부 규칙: "파일 안 일관성"이 먼저
- 규칙: "새 파일은 `const`. 기존 파일은 그 파일에 이미 `const` 가 있으면 `const`, 없으면 `local`. 섞지 않는다."
- quad 와 rbvm 의 현실을 그대로 설명한다. override 파일도 필요 없다.

| 프로젝트 | 변경량 |
|---|---|
| 모든 프로젝트 | 문서·코드 0 |
| rbvm | 기존 금지 문구만 공통 규칙과 충돌하므로 rbvm 쪽 문단 삭제 또는 유지 결정 |

## 4. 추천: 안 B 의 문장을 안 A 의 틀에 넣은 형태

- 공통 rules 의 문장은 이렇다. "**새 파일은 `const`. 기존 파일은 그 파일의 관행(`const`/`local`)을 따르고 한 파일 안에서 섞지 않는다.**"
- 함정 두 줄(`local const`, `const` 뒤 `(` 문장)을 같이 둔다.
- 이유는 넷이다.
  1. 다섯 저장소가 이미 `const` 다.
  2. 유일한 금지 근거(pesde 0.7.3)가 사라졌다.
  3. quad 의 문서와 코드 사이 괴리를 일괄 전환 없이 해소한다.
  4. 에이전트가 주변 코드를 보고 따라 쓰는 경향과 맞는다.
- rbvm 은 근거가 사라졌다는 사실과 함께 사용자에게 묻는다.

## 5. 사용자 확인 질문

rbvm 의 "`const` 금지"는 pesde 0.7.3 의 타입 익스포트 문제 때문이었고 0.7.4 에서 풀렸습니다. 이 금지를 풀어 rbvm 도 공통 규칙("새 파일은 `const`, 기존 파일은 그 파일 관행")을 따르게 할까요, 아니면 rbvm 만 `local` 고정으로 남길까요?

## 사용자 결정 (2026-11-10)

**확정: `const`를 써도 된다.** rbvm 의 금지 근거(pesde 0.7.3)는 사라졌다. 같은 파일 안에서 섞지 않는 것은 유지한다. rbvm 쪽 규약 갱신은 rbvm 세션 몫이다(HUMAN_TODO 또는 handoff).

## 정정 (2026-11-10, luau-kb 증류)
- "린트 경고만 난다"는 **nonstrict 에서만** 맞다. `--!strict` 에서는 luau-analyze 0.734·0.742 가 `TypeError: Unknown global 'x'` 를 낸다. 실행은 두 모드 모두 된다.
- 따라서 `const` 를 쓰지 않는 파일에서 실수로 `local const x = 1` 이 생기면 strict 검사가 잡아 준다. nonstrict 파일은 린트에만 기대야 한다.
- 근거: `/code/Projects/luau-kb/skills/luau-style/references/idioms.md` 정정, `/code/Projects/luau-kb/snippets/style-const-local-const-global.luau`
