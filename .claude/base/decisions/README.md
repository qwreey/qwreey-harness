# decisions — Luau 프로젝트 사이에서 갈라진 규약의 합의안

작성 2026-11-10. 한 파일이 충돌 하나를 다룬다. 각 파일에는 입장(경로:줄), 실제 근거(실행·기록·서술 구분), 합의안 1~2개와 변경량, 추천, 사용자 확인 질문 1개가 들어 있다.
실험 산출물은 `/tmp/cd-exp/`(휘발성)에 있다. 원천 저장소는 읽기만 했다.

| ID | 주제 | 갈린 입장 | 이번에 확인한 핵심 사실 | 추천안(한 줄) |
|---|---|---|---|---|
| [D-01](D-01-const.md) | `const` | rbvm 금지 / quad 문서상 채택·코드 0줄 / 나머지 기본 | 금지 근거(pesde 0.7.3)는 0.7.4 에서 소멸. `const` 뒤 `(` 문장의 `;` 를 stylua 가 지움. `const function` 유효 | 새 파일은 `const`, 기존 파일은 그 파일 관행, 한 파일 안에서 섞지 않음 |
| [D-02](D-02-stylua.md) | stylua 설정 | Tabs 5곳 / Spaces 2곳, Always 2 / Input 4, quad 설정 없음 | 들여쓰기 전환은 3~33k줄. Always→Input 은 0줄. **하위 폴더 실행·`syntax` 누락 시 `f<<T>>` 가 exit 0 으로 시프트가 됨** | 값은 저장소 `stylua.toml` 소유, 공통 규칙은 "루트에서 실행·`syntax=Luau`·`<<` diff 확인"만. 새 저장소 기본은 Tabs+Input |
| [D-03](D-03-runner.md) | 러너 | luau 전용 / luau+lute / lune 금지 | lune 0.10.5 는 `const` 파싱 실패 | `luau` CLI 기본, fs·process 도구만 lute, lune 쓰지 않음 |
| [D-04](D-04-type-functions.md) | 타입 함수 | quad 진단 전용 / stl 페이퍼 금지·규약 주의 / tbox 핵심 API | 바깥 지역 참조 컴파일 실패 재현. "`error()` 는 진단이 안 보인다"는 0.734·0.742 에서 거짓(보이나 지저분함) | 기본 만들지 않음, 진단 전용 허용, 합성은 스파이크+사용자 승인(tbox 예외) — 함정 표는 버전 열과 함께 스킬에 |
| [D-05](D-05-toolchain-pins.md) | 버전 핀 | luau 0.742(stl) / 0.734(5곳), lsp 1.70.1 / 1.69.0 | 0.734 힙 손상은 210회 시도에 재현 0(기록 근거만). stl 은 0.734 로 30건, lsp 1.69 로 308건 | 공통 규칙은 "수치·결함 서술에 버전 명시, 0.734 는 비정상 종료=실패", 0.742 통일은 프로젝트별 목표 |
| [D-06](D-06-type-checker.md) | 검사 기준 도구 | analyze(stl·moonwave) / lsp(rbvm·table-sim·devplorer·tbox) / 둘 다(quad) | `luau-analyze` 엔 `--defs` 가 없음 → Roblox 전역 코드는 lsp 뿐. lsp 가 더 내는 경우도 있음 | 조건부: Roblox 전역 없으면 analyze, 있으면 lsp+defs+sourcemap. 공통은 게이트·exit code·stderr |
| [D-07](D-07-finished-todos.md) | 끝난 할 일 | 지운다(stl·quad) / 아래로 내린다(table-sim) / 취소선(devplorer) | table-sim "된 것" 구획이 17KB(42%) | 상시 로드되는 todos 에선 지우고, 보존은 import 안 되는 파일로. 코드 `TODO` 는 이유+추적처 |
| [D-08](D-08-comment-language.md) | 주석 언어 | 영어(quad) / 한국어(tbox 등) / 혼합(rbvm) | 7곳 모두 식별자·에러 영어, 5곳이 "파일 언어를 따름" | 그 파일의 기존 언어, 새 파일은 프로젝트 rules |
| [D-09](D-09-naming-casing.md) | 네이밍 케이싱 | 연산 Pascal(quad·stl·rbvm) / camel(table-sim·devplorer), 파일 소문자(tbox·rbvm), 타입 `T` 접두(tbox) | quad·stl 의 기준 문장이 사실상 같음 | 공통 5개(타입·모듈 Pascal, 지역 camel, `isX`, `_` 내부, 주변 따름)만 강제, 나머지 저장소 rules |
| [D-10](D-10-error-handling.md) | 에러 | 워커+번호(quad) / `Common.raise`(stl) / 소문자 시작(tbox) / 규칙 없음 | `error(msg, 2)` 가 `-O2` 인라인에서 위치를 잃음(재현) | 영어·리터럴 공통, 라이브러리는 손으로 센 level 금지 + 줄 단언, 형식은 저장소 |
| [D-11](D-11-object-shape-and-field-access.md) | 객체 모양·필드 읽기 | 네임스페이스만(stl AB) → 메서드 객체(BI)·quad·tbox / 매번 `module.x`(quad) 대 루프 지역 캐시(stl) | 두 필드 읽기 규칙은 조건이 달라 모순 아님 | 주입·재대입 값은 매번 읽기, 불변 함수는 실측된 뜨거운 루프만 지역. 객체 모양은 저장소 설계 |
| [D-12](D-12-require-paths.md) | require 경로 | `@game` 금지(devplorer) / `@game` 72곳(table-sim) | 정적 검사가 경로 오류를 못 잡음(기록 3곳) | `init.luau`·`@self`·리터럴·엔트리 이름·실제 require 테스트는 공통, `@game` 금지는 위치가 바뀌는 번들일 때만 |
| [D-13](D-13-file-structure.md) | 파일 길이·폴더·데이터 | 길이 기준 없음(전부) / 폴더: 가족 접기만(quad)·층과 기능 폴더(devplorer)·종류 폴더(stl) | 다섯 지적 모두 사람이 함. 리뷰 15건이 4천 줄 파일을 인용하고도 크기를 말하지 않음. 성장 속도 하루 수백~천 줄 | 경고 800·강제 1,500줄(테스트 두 배), 알림만(훅·rules·감사자), 폴더 대분류와 예외는 저장소 `structure.json`·rules |

## 결정 뒤 옮길 곳

- 공통 필수 한 줄은 `.claude/research/drafts/style/rules/luau-core.md`(사용자 레벨 rules 후보)로 옮긴다.
- 근거·예시는 `.claude/research/drafts/style/skills/luau-style/references/` 로 옮긴다.
- 저장소별 override 는 각 저장소의 `.claude/rules/*.md` 에 둔다. 다른 세션이 작업 중인 저장소라 여기서 만들지 않는다.

## 이번에 발견한 낡은 서술 (각 저장소 세션에 전달할 것)

> 2026-11-10: 아래 8건은 luau-kb 정정과 합쳐 저장소별 `.claude/handoff/<repo>-corrections.md`(quad 는 `.claude/handoff/quad.md` 의 C12·C36)로 옮겼다. 전달은 그 파일로 한다.


- `stl-luau/stylua.toml:1` 의 "tbox/quad 와 같은 설정"은 거짓이다. tbox 는 Spaces+Input 이고 quad 는 설정 파일이 없다.
- `stl-luau/mise.toml:18-19` 의 "quad 는 luau 를 고정하지 않는데"는 거짓이다. quad 는 0.734 를 핀했다.
- `table-sim/mise.toml:3-5` 의 "형제와 같은 값"은 거짓이다. stl 은 0.742/1.70.1, quad 는 lsp 1.70.1 이다.
- `rbvm/.claude/conventions.md:28-37` 의 `const` 금지 근거는 이미 해소됐다(D-01).
- `tbox/CLAUDE.md:84-91` 의 "`syntax=Luau` 여도 오염"은 재현되지 않는다. 실제 원인은 설정이 적용되지 않은 실행이다(D-02).
- quad `typing-limits.md:69` 와 stl `papers/03-tuple.md:23` 의 "`error()` 대신 `print`"는 0.734 이상에서 필수가 아니다(D-04).
- stl `papers/03-tuple.md:15` "type function 을 쓰지 않습니다"는 `conventions.md:84` "금지 아님"과 어긋난다(D-04).
- quad `base/architecture.md:783` 의 "새 코드는 `const`"는 게시 소스의 실태(0줄)와 어긋난다(D-01).

## 사용자 결정 현황 (2026-11-10, 2026-11-11 갱신)

| ID | 상태 | 요지 |
|---|---|---|
| D-01 | 확정 | `const` 사용 가능. 금지 근거는 소멸했다 |
| D-02 | 확정 | 추천안 그대로 |
| D-03 | 확정, 보완 | `luau` 기본 + 필요한 부분만 mock. Roblox 서비스·환경 동작은 Studio MCP 로 확인 |
| D-04 | 수정 | '기본 금지' 가 아니라 '부작용과 불가피성의 판단 문제'. 제약을 모아 정리한다(strip-nil 처럼 없으면 불가능한 경우가 있음) |
| D-06 | 보완 | DX(자동완성·hover·추론 표시) 확인에는 순수 Luau 에서도 luau-lsp 를 쓴다 |
| D-05, D-07~D-12 | 확정(2026-11-11) | 사용자: 추천대로. 각 문서 4절의 추천안 채택(D-10 은 정정 절 반영) |
| D-13 | **확정+보완** | 800·1,500 알림만. 이유를 기록하면 예외 가능. 대분류는 저장소가 정하되 관례·성공 사례 제시. Arr 예외 없음 → 분리 계획기. 사용자 이름은 제안만 |
