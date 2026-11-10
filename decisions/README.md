# decisions — 정책 결정 기록

저장소마다 정책이 갈린 항목을 모아 둔다. 이 저장소는 한쪽을 고르지 않는다. 사용자가 원하는 것은 통일이 아니라 합의점이다. 결정이 나면 `D-NN-제목.md` 로 요약을 남기고(맥락, 결정, 반영한 곳, 되돌릴 조건), 해당 references 의 `> 정책: 미정` 표시를 결정 링크로 바꾼다. 원문(입장, 근거, 합의안)은 `/code/Projects/claude-doctor/decisions/D-NN-*.md` 에 있고, 그쪽 `README.md` 끝의 "사용자 결정 현황" 표가 권위 있는 상태다.

## 미결 목록

| ID | 항목 | 갈린 입장 | 양쪽 근거가 있는 곳 |
|---|---|---|---|
| D-05 | luau 버전 핀 | 0.742(stl-luau) / 0.734(quad, tbox, table-sim, moonwave-luau, devplorer). 제안: "수치·결함 서술에 버전 명시, 0.734 비정상 종료는 실패" 공통, 0.742 통일은 프로젝트별 목표 | `skills/luau-verify/references/toolchain.md` §3, `snippets/RESULTS.md` (두 버전 차이 칸) |

D-07~D-12(끝난 할 일, 주석 언어, 네이밍, 에러, 객체 모양, require 경로)는 claude-doctor 에서 제안 상태다. 이 저장소의 references 는 그중 사실 부분(예: D-10 의 `-O2` 위치 소실 실측과 정정)만 싣고 정책은 정하지 않는다.

## 결정됨

| ID | 항목 | 결정 | 기록 |
|---|---|---|---|
| D-01 | `const` | 써도 된다. 금지 근거(pesde 0.7.3)는 0.7.4 에서 사라졌다. 한 파일 안에서 `const` 와 재대입 없는 `local` 을 섞지 않는다 | `D-01-const.md` |
| D-02 | stylua 설정 | 값(들여쓰기, `call_parentheses`)은 저장소 `stylua.toml` 이 소유한다. 공통 규칙은 '루트에서 실행, `syntax = "Luau"`, 포맷 뒤 `<<` diff 확인' 셋 | `D-02-stylua.md` |
| D-03 | 러너 | `luau` CLI 기본, lune 안 씀. 엔진 의존 동작은 필요한 부분만 mock, Studio MCP 는 mock 충실도 확인과 재현 불가 동작에만 | `D-03-runner.md` |
| D-04 | type function 사용 범위 | 사안별 판단. 기본 금지도 '진단 전용' 구분도 아니다. "부작용이 이득보다 큰가" 대 "이것 없이는 표현할 수 없는가"로 정하고, 부작용이 크면 스파이크와 사용자 승인 | `D-04-type-functions.md` |
| D-06 | 기준 검사기 | 정확성: 순수 Luau 는 luau-analyze, Roblox 전역은 luau-lsp + 정의 파일. DX: 공개 API 라이브러리는 luau-lsp 로 hover·자동완성·추론 타입 확인 | `D-06-type-checker.md` |

## 합의된 공통 분모 (결정 없이 references 에 반영함)

- 버전은 반드시 고정한다. 올릴 때는 음성 대조군 배터리 수치를 대조한다.
- 파일마다 `--!strict`.
- 한계를 우회하려고 공개 API·타입을 비틀지 않는다. 문서화, 관례, 되돌릴 링크.
- 업스트림 이슈 게시는 사용자가 결정한다.
- 테스트는 `-O1` 과 `-O2` 로 두 번 돌리고, 에러 테스트는 메시지와 사용자 줄을 같이 단언한다(stl-luau 실천과 D-10 의 사실 부분. `skills/luau-testing/`).
