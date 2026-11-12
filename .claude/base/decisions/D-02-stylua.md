# D-02. stylua 설정 (`indent_type`, `call_parentheses` 외)

> 작성 2026-11-10. 실험: `/tmp/cd-exp/sty/`(각 프로젝트 소스 사본에 설정 5종을 적용해 바뀐 줄 수를 셈), `/tmp/cd-exp/syn/`.
> 도구: `/code/.local/share/mise/installs/stylua/2.5.2/stylua`.

## 1. 각 프로젝트의 입장

| 프로젝트 | indent | call_parentheses | 그 밖 | 위치 |
|---|---|---|---|---|
| stl-luau | Tabs | **Always** | syntax=Luau, 120, AutoPreferDouble, collapse Never | `stl-luau/stylua.toml:2-8`, `.claude/conventions.md:91` |
| moonwave-luau | Tabs | **Always** | +line_endings Unix, `syntax` 경고 주석 | `moonwave-luau/stylua.toml:8-15` |
| table-sim | Tabs | **Input** | +line_endings Unix | `table-sim/stylua.toml:1-8`, `.claude/conventions.md:102`("탭(quad 소스와 같다)") |
| devplorer | Tabs | **Input** | table-sim 과 md5 동일 | `devplorer/stylua.toml:1-8` |
| tbox | **Spaces** | **Input** | `space_after_function_names`·`block_newline_gaps` Never, `sort_requires` | `tbox/stylua.toml:1-13`, `CLAUDE.md:80-82` |
| rbvm | **Spaces** | **Input** | tbox 와 md5 동일 | `rbvm/stylua.toml:1-13` |
| quad | **설정 파일 없음** | — | 한 번도 커밋된 적 없음(`git log -- stylua.toml` 0건) | `quad/` 루트 |

- stl 의 머리 주석 "tbox/quad 와 같은 설정"(`stl-luau/stylua.toml:1`)은 **틀렸다**. tbox 는 Spaces+Input 이고 quad 는 설정이 없다.

## 2. 실제 근거

### 2-1. diff 실측 — 다른 설정을 적용하면 몇 줄이 바뀌나 [실행]

행은 소스, 열은 적용한 설정이다. 값은 "바뀐 원본 줄 수 / 파일 수"다.

| 소스(파일 수) | stl 설정 Tabs+Always | tbox 설정 Spaces+Input | table-sim 설정 Tabs+Input | Spaces+Always |
|---|---|---|---|---|
| stl (41) | **0** | 7,258 / 41 | **0** | 7,178 / 40 |
| tbox (40) | 3,419 / 37 | **0** | 3,419 / 37 | **0** |
| table-sim (67) | 535 / 15 | 23,566 / 65 | **0** | 23,566 / 65 |
| devplorer (172) | 134 / 31 | 32,738 / 172 | **0** | 32,866 / 172 |
| moonwave (1) | **0** | 1,000 / 1 | **0** | 1,000 / 1 |
| rbvm (11) | 1,463 / 10 | **0** | 1,463 / 10 | **0** |
| quad (67, 설정 없음) | 348 / 43 | 9,281 / 65 | 348 / 43 | 9,200 / 65 |

읽는 법은 다음과 같다.
- **`call_parentheses` 차이는 작고 한쪽으로만 난다.**
  - Always 를 쓰는 stl·moonwave 코드에 Input 을 적용하면 0줄이 바뀐다. Input 은 괄호를 그대로 두기 때문이다.
  - Input 을 쓰는 table-sim·devplorer 에 Always 를 적용하면 535줄·134줄이 바뀐다. 괄호 없는 호출(`f "x"`, `f { … }`)이 있다는 뜻이다.
  - tbox·rbvm 코드는 Always 를 적용해도 0줄이다. 괄호를 이미 다 쓴다.
- **`indent_type` 차이는 거의 모든 줄을 바꾼다**(3,419~32,866줄). 바꾸는 쪽은 사실상 전면 재포맷이다.
- **quad 의 348줄은 들여쓰기가 아니라 120열 초과 줄 재배치다**(긴 에러 메시지 리터럴). quad 는 손 포맷 + 탭이다.
  - 기본 설정(`syntax` 없음)으로 돌리면 `quad-types/src/init.luau:294` 의 `>>` 에서 **파싱 에러**가 난다.

### 2-2. `syntax = "Luau"` 와 실행 위치 [실행: `/tmp/cd-exp/syn/g1,g2.luau`, `root/sub`]

- `syntax = "Luau"` 가 있으면 `f<<T>>(x)`, `T.Unsafe<<number>>({…})`, `f<<A, B>>(…)`, `Box<Box<number>>` 모두 **안전**하다.
  - 괄호 없는 `f<<T>> {…}` 는 `({…})` 로 정상 변환된다.
  - 이 결과는 감사 05 §1-1 과 같다.
- `syntax` 가 없으면(기본 `All`) 결과가 둘로 갈린다.
  - **단일 인자 꼴은 exit 0 으로 조용히 시프트 연산이 된다.** `id<<number>>(1)` → `id << number >> 1`.
  - 여러 인자나 중첩 제네릭은 파싱 에러로 시끄럽게 실패한다.
- **하위 디렉터리에서 `stylua 파일` 을 실행하면 상위의 `stylua.toml` 을 찾지 않는다.**
  - 그래서 기본 설정이 적용되고 위의 조용한 오염이 그대로 난다.
  - 해결책은 둘이다. 저장소 루트에서 실행하거나 `--search-parent-directories` 를 쓴다.
  - tbox `CLAUDE.md:81-82` 의 "루트에서 실행" 경고가 이것의 실체다.
- tbox `CLAUDE.md:84-91` 의 "`syntax = \"Luau\"` 인데도 오염된다"는 **재현되지 않는다**. 실제 위험은 "설정이 적용되지 않은 실행"이다.

### 2-3. 그 밖
- tbox·rbvm 고유 옵션(`space_after_function_names`, `block_newline_gaps` Never, `sort_requires`)은 근거 문서가 없다. 근거 없는 취향이다. [서술]
  - `sort_requires` 는 `const` require 블록을 정렬하지 않는다(D-01). [실행]
- 탭과 스페이스 선택에도 기록된 근거가 없다. table-sim 은 "quad 소스와 같다"는 것만 이유로 든다. [서술]

## 3. 합의안

### 안 A. 포맷은 저장소의 `stylua.toml` 이 정본 — 공통 규칙은 "실행 방법"만
- 공통 rules 에는 세 가지만 둔다.
  1. 손으로 포맷하지 말고 저장소 루트에서 `stylua` 를 쓴다(또는 `--search-parent-directories`).
  2. `stylua.toml` 에 `syntax = "Luau"` 가 있어야 한다.
  3. `<<` 가 든 파일은 포맷 뒤 diff 를 본다.
- 들여쓰기·괄호는 규칙에 적지 않는다. 각 저장소 `stylua.toml` 이 정하고 `--check` 게이트가 강제한다.
- 새 저장소 스캐폴딩 기본값은 **Tabs + Input**(+syntax=Luau, 120, AutoPreferDouble, collapse Never, line_endings Unix)이다.

| 프로젝트 | 변경량 |
|---|---|
| 기존 6개 | 0 |
| stl | 머리 주석 한 줄 정정("tbox/quad 와 같은" → 사실대로) |
| quad | 0, 또는 원하면 stylua.toml 추가 시 348줄 / 43파일(Tabs 계열 어느 쪽이든 동일) |

### 안 B. 단일 공통 `stylua.toml` 강제 (Tabs + Input)
- 전 저장소가 같은 파일을 쓴다.
- tbox 3,419줄·rbvm 1,463줄 전면 재포맷, quad 348줄, stl·moonwave·table-sim·devplorer 0줄이다.
- 얻는 것은 "저장소 사이 복사 시 포맷 차이 없음"뿐이다. tbox 는 외부 원격(Sol-s-Studio)이 있어 기여자 영향도 있다.

## 4. 추천: 안 A

- 포맷은 도구가 강제하므로 에이전트 규칙에 케이스별 취향을 적을 이유가 없다.
- 사고를 내는 것은 설정 값이 아니라 **설정이 적용되지 않은 실행**이다. 이번에 재현했다.
- 스캐폴딩 기본값을 Input 으로 두는 이유는 Always 코드에 적용해도 0줄이 바뀌기 때문이다. Tabs 는 다수(5/7)를 따랐다.

## 5. 사용자 확인 질문

포맷 설정은 저장소마다 지금 것을 그대로 두고, 공통 규칙에는 "루트에서 실행·`syntax = \"Luau\"` 필수·`<<` diff 확인"만 넣을까요? 아니면 tbox·rbvm 까지 Tabs+Input 하나로 통일할까요(tbox 3,419줄, rbvm 1,463줄 재포맷)?

## 사용자 결정 (2026-11-10)

**확정: 추천안에 동의.** 값은 저장소 `stylua.toml` 이 소유한다. 공통 규칙은 '루트에서 실행, `syntax = "Luau"`, `<<` diff 확인' 만 둔다.
