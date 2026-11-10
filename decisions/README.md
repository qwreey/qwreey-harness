# decisions — 정책 결정 기록

저장소마다 정책이 갈린 항목을 모아 둔다. 이 저장소는 한쪽을 고르지 않는다. 사용자가 원하는 것은 통일이 아니라 합의점이다. 결정이 나면 `NNNN-제목.md` 로 기록하고(맥락, 선택지, 결정, 되돌릴 조건), 해당 references 의 `> 정책: 미정` 표시를 결정 링크로 바꾼다.

## 미결 목록

| # | 항목 | 갈린 입장 | 양쪽 근거가 있는 곳 |
|---|---|---|---|
| 1 | type function 사용 범위 | quad: 진단 전용(결과 타입 합성 금지) / stl-luau: 쓰지 않음 | `skills/luau-types/references/type-functions.md` §0 |
| 2 | `const` | rbvm: 금지(pesde 타입 익스포트 문제) / stl-luau·quad·tbox 등: 재대입 없는 바인딩은 `const` | `skills/luau-verify/references/tooling.md` §3 |
| 4 | luau 버전 핀 | 0.742(stl-luau) / 0.734(quad, tbox, table-sim, moonwave-luau, devplorer) | `skills/luau-verify/references/toolchain.md` §3, `snippets/RESULTS.md` (두 버전 차이 4칸) |
| 6 | stylua 세부 | 들여쓰기 Tabs/Spaces, `call_parentheses` Always/Input | `skills/luau-verify/references/tooling.md` §4 |

## 결정됨

| # | 항목 | 결정 | 기록 |
|---|---|---|---|
| 3 | 러너 | `luau` CLI 기본, lune 안 씀. 엔진 의존 동작은 필요한 부분만 mock, Studio MCP 는 mock 충실도 확인과 재현 불가 동작에만 | `D-03-runner.md` |
| 5 | 기준 검사기 | 정확성: 순수 Luau 는 luau-analyze, Roblox 전역은 luau-lsp + 정의 파일. DX: 공개 API 라이브러리는 luau-lsp 로 hover·자동완성·추론 타입 확인 | `D-06-type-checker.md` |

## 합의된 공통 분모 (결정 없이 references 에 반영함)

- 버전은 반드시 고정한다. 올릴 때는 음성 대조군 배터리 수치를 대조한다.
- 파일마다 `--!strict`.
- 한계를 우회하려고 공개 API·타입을 비틀지 않는다. 문서화, 관례, 되돌릴 링크.
- type function 으로 결과 타입을 합성하지 않는다(1번의 두 입장이 공유하는 선).
- 업스트림 이슈 게시는 사용자가 결정한다.
