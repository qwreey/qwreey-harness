# project-overrides.md — 저장소마다 다른 값 한눈에

목차
- §1 표: 갈린 규약 × 저장소
- §2 읽는 법과 갱신 규칙

이 파일에서 답하는 질문
- 이 저장소의 stylua·`const`·러너·검사기·핀은 무엇인가?
- 공통 규칙과 저장소 규칙이 다르면 어느 쪽인가?

---

## §1 갈린 규약 × 저장소 (2026-11-10 실태, 결정은 `claude-doctor/decisions/`)

| 항목(결정) | quad | stl-luau | tbox | table-sim | devplorer | rbvm | moonwave |
|---|---|---|---|---|---|---|---|
| `const`(D-01) | 문서상 채택, 게시 소스 실태 `local` | 기본 | 기본 | 기본(`const function` 포함) | 기본 | **금지**(근거 소멸, 사용자 확인 대기) | 미정(Q5–Q7) |
| stylua indent / parens(D-02) | 설정 없음(손 포맷, 탭) | Tabs / Always | Spaces / Input(+sort_requires) | Tabs / Input | Tabs / Input | Spaces / Input(+sort_requires) | Tabs / Always |
| 러너(D-03) | luau | luau | luau + lute | luau | luau | (테스트 없음) | luau |
| 타입 함수(D-04) | 진단 전용 | 주의(시제품·사용자 확인) | 핵심 API(합성) | 없음 | 없음 | 없음 | 없음 |
| luau / luau-lsp 핀(D-05) | 0.734 / 1.70.1 | 0.742 / 1.70.1 | 0.734 / 1.69.0 | 0.734 / 1.69.0 | 0.734 / 1.69.0 | 없음 / 1.69.0 | 0.734 / 1.69.0 |
| 검사 기준(D-06) | analyze + lsp(엔진 무관 이중), Roblox 쪽 lsp | analyze | lsp | lsp | lsp | lsp | analyze |
| 끝난 todos(D-07) | 지움 | 지움 | — | 아래로 내림 | 취소선 | 갱신 | 지움 |
| 주석 언어(D-08) | 영어 | 한국어 지배·파일 언어 | 한국어 | 한국어·파일 언어 | 한국어·파일 언어 | 짧게 영어·이유는 한국어 | 파일 언어 |
| 네임스페이스 함수 케이스(D-09) | 타입 고유 Pascal / 범용 camel | Pascal | 메서드 camel | camel | 혼합 | Pascal | — |
| 파일 이름(D-09) | Pascal | Pascal | 소문자 | Pascal | Pascal | 소문자 | — |
| 에러 형식(D-10) | `QuadNNNN Subj: reason (got X)`, 워커 | `Module: 설명`, `Common.raise` | 소문자 시작 | 규칙 없음 | `(ok, err)` 검증 | 규칙 없음 | — |
| 객체 모양(D-11) | 메타테이블 + Pascal 메서드 | AB→BI 전환 중 | Kind 메타테이블 + camel 메서드, freeze | 모듈 + 닷 함수 | 모듈 + 닷 함수 | 프록시 메타테이블 | — |
| `@game/` require(D-12) | — | — | — | 사용(고정 위치) | **금지**(복제 번들) | — | — |

## §2 읽는 법과 갱신 규칙

- 저장소 `.claude/rules/` 또는 CLAUDE.md 가 이 표와 다르면 **저장소가 맞다**. 이 표는 2026-11-10 시점의 스냅숏이다.
- 결정이 나면 이 표와 `.claude/base/decisions/README.md` 를 같이 고친다. 결정 전 항목은 "현재 실태"만 적고 권고를 섞지 않는다.
- 새 저장소는 이 표의 어느 열도 복사하지 않는다. `naming.md` §3, `idioms.md` §1 의 기본값과 스캐폴딩 스킬을 쓴다.
