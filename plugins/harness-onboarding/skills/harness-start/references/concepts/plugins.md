# plugins — 스킬·훅 등을 묶어 설치하는 꾸러미

> 한 줄: plugin 은 **스킬, subagent, 훅, MCP 서버 등을 한 번에 설치하는 꾸러미**다. marketplace(장터)는 그 꾸러미 목록이다.

## 쉽게 말하면
- 앱 스토어(마켓)에서 앱(플러그인)을 받는 것과 같다. 회사도 자기 마켓을 만들 수 있다.
- 지금 이 온보딩(`harness-onboarding`)도 플러그인이다.

## 꾸러미에 들어갈 수 있는 것
| 넣을 수 있다 | 넣을 수 없다 |
|---|---|
| 스킬, subagent, 훅, MCP 서버, 언어 서버(LSP), 출력 스타일, 실행 파일 | CLAUDE.md(플러그인 안에 둬도 읽히지 않는다), 권한 규칙 |
- 그래서 "항상 지킬 약속" 은 플러그인이 아니라 CLAUDE.md·관리 설정으로 따로 배포해야 한다.

## 설치와 관리
| 하고 싶은 것 | 방법 |
|---|---|
| 둘러보기·켜기·끄기 | `/plugin` |
| 마켓 추가 | `claude plugin marketplace add <git 주소나 폴더>` |
| 설치 | `claude plugin install <플러그인>@<마켓>` |
| 설치된 목록 | `claude plugin list` |
| 무엇이 들었고 비용이 얼마인지 | `claude plugin details <플러그인>` |
- 설치·마켓 추가는 **설치** 이므로 동의 후에만 한다.

## 회사 마켓 (지금 있는 것)
| 마켓 | 플러그인 | 누구에게 |
|---|---|---|
| claude-doctor-market | `harness-onboarding` (이 온보딩) | 모두 |
| claude-doctor-market | `session-log` (세션 기록 자동 요약) | 긴 작업을 하는 개발자 |
| luau-kb-market | `luau-kb` (Luau·Roblox 지식 스킬 12개) | Luau 개발자. Luau 저장소에서만 켜기 권장 |

## 주의
- 플러그인의 훅·스크립트는 **내 권한으로 실행**된다. 회사 마켓이 아닌 곳의 플러그인은 담당자에게 먼저 묻는다.
- 깔수록 스킬 설명이 상시 비용으로 쌓인다. 안 쓰는 건 끈다.
- 마켓에서 복사해 설치한 플러그인은 버전이 올라가야 갱신된다. 로컬 폴더 마켓은 제자리에서 읽어 바로 반영된다.
- 회사는 관리 설정(`extraKnownMarketplaces` + `enabledPlugins`)으로 마켓과 플러그인을 모두에게 미리 깔거나, 허용 목록(`strictKnownMarketplaces`)으로 다른 마켓을 막을 수 있다.

## 흔한 오해
- "플러그인 = 프로그램 설치" → 대부분은 글(스킬)이지만 훅·MCP 는 실제 프로그램을 돌린다.
- "플러그인 넣으면 CLAUDE.md 도 따라온다" → 안 따라온다.

## 1분 실습
- `/plugin` 을 열어 설치된 탭만 본다(바꾸지 않는다).

## 이해 확인 질문 (설명 뒤 하나만 골라 묻는다)
- 플러그인으로 배포할 수 없는 것 하나는? (답: CLAUDE.md, 권한 규칙)
- 출처 모를 플러그인이 위험한 이유는?

## 근거
- 공식: code.claude.com/docs/en/plugins/components (구성 요소, 루트 CLAUDE.md 미로드, 훅 권한), discover-plugins, plugins/create-marketplace, plugins/org (관리 설정 배포, 허용 목록), plugins/loading (제자리 로드)
- 공식: commands (`/plugin`), CLI `claude plugin details` (로컬 v2.1.316 에서 확인)
