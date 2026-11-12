# 토론 자료: 모델용 문서 위생과 주석 문자 위생 (2026-11-11)

## 배경
- second-opinion 스킬을 정리하는 동안 모델이 읽는 파일에 작업 이력이 계속 섞여 있었다. SKILL.md, references, templates, agents 정의가 그런 파일이다. 섞여 있던 것:
  - audit 절 번호(".claude/audit/18 §11·§12")
  - 실측 표기("fork 비용 [실측 §12.5 + 추정]")
  - 날짜("2026-11-11")
  - "사용자 결정", 라운드 번호
- 사용자: "직접 실측을 했거나 근거를 적지 말아야 하는 부분에서도 적는 경우가 많다. 진짜 거기에 그런 사담을 넣어야 하나. 특히 원장 번호 §, 시한성·시각 지정성. 당장은 이 스킬의 문제지만 quad 에도 계속 있던 문제다."
- 사용자 추가: "주석에 non-ASCII 글자나 이모티콘, 한국어가 들어가는 경우도 보통 권장되지 않는데, 이것도 위생으로 잡을 수 있다고 본다. 비슷하게 넣어 보자."
- 사용자는 전역 규칙을 토론을 거쳐 확정하길 원한다. 매 세션 읽히는 문구라 미세한 차이가 누적되기 때문이다.

## 이미 있는 것
- `home/.claude/rules/comments.md`(전역 규칙, 영어)와 PostToolUse 훅 `home/.claude/hooks/comment-hygiene.py`(알림만 하고 막지 않음)가 있다.
  - 코드 주석에서 작업 이력을 잡는다: 원장 id, 날짜, `round N`, `.claude/`·`audit/`·`session/` 경로, 결정 문구.
  - 이유 문장과 `Ref:` 꼬리가 함께 있으면 통과한다.
  - 저장소 `.claude/comments.json` 으로 패턴·공개 id·제외 경로를 바꿀 수 있다.
  - 규칙에 "Comment language follows the language already used in that file." 가 있다. 현재는 언어를 위생 대상으로 보지 않는다.
- 같은 계열의 알림 훅이 이미 여럿이다: structure-reminder, memory-placement, bash-bypass-reminder, subagent-slots, second-opinion nudge 등. 훅 알림이 많아지면 피로가 생긴다.
- 사용자 원칙:
  - 알림만 하고 막지 않는다. 기존 주석은 손대는 줄만 고치고, 일괄 정리는 사용자가 신호를 줄 때만 한다.
  - 사용자가 정한 이름·구조는 바로 고치지 않고 제안한다.
  - 저장소 규칙이 전역 규칙에 우선한다.
- 회사 배포 맥락: 동료는 비프로그래머이거나 Luau 만 쓰는 한국인 개발자다(메모리 user-company-rollout).

## 실태 (2026-11-11, 대략적인 셈)
### 코드 주석 줄 (git ls-files 의 .luau .lua .rs .py .ts .go, 줄 머리 `--` `//` `#`)
| 저장소 | 주석 줄 | 한국어 포함 | non-ASCII 포함 | 이모지 |
|---|---|---|---|---|
| quad | 7692 | 1846 | 3012 | 31 |
| stl-luau | 9868 | 7348 | 7356 | 147 |
| rbvm | 215 | 51 | 51 | 0 |
| table-sim | 2819 | 2391 | 2391 | 0 |
| devplorer | 2798 | 2426 | 2426 | 2 |
| tbox | 1146 | 1008 | 1009 | 0 |
| luau-kb | 1245 | 933 | 936 | 0 |
| coderag | 1188 | 779 | 789 | 0 |
| claude-doctor | 498 | 347 | 349 | 1 |
대부분의 저장소에서 주석은 한국어가 주류다. quad 는 영어 비중이 높고, non-ASCII 중 한국어가 아닌 것(→ — · § 같은 문자)이 많다.

### 모델용 문서의 이력·시점 표지 (CLAUDE.md, .claude/*.md, .claude/rules, skills/plugins 의 md; audit/handoff/drafts/decisions 제외)
| 저장소 | 파일 | 날짜 표기 | 원장 id 꼴(대문자-숫자) |
|---|---|---|---|
| quad | 620 | 9781 | 17865 |
| stl-luau | 116 | 731 | 151 |
| table-sim | 114 | 1249 | 107 |
| devplorer | 88 | 443 | 885 |
| luau-kb | 78 | 618 | 947 |
| claude-doctor | 55 | 11 | 37 |
| coderag | 13 | 4 | 24 |
- quad 의 `.claude/` 아래에는 연구 원장(`base/typing-limits.md` 의 8.43 같은 번호, H-973 같은 id)이 많다. 이 문서들에서는 번호가 곧 구조다.
- luau-kb references 에는 `status: verified · last-confirmed: luau 0.742 · 근거: snippets/x.luau` 같은 줄이 있다. 근거 스니펫은 실행해서 확인할 수 있다.

## 초안 (토론 대상, 메인이 쓴 것)
### A. 모델용 문서 위생 `rules/model-facing-docs.md`
- 대상(paths): `**/SKILL.md`, `**/skills/**/*.md`, `**/agents/*.md`, `**/.claude/rules/*.md`, `**/CLAUDE.md`
| 종류 | 예 | 모델용 문서에 |
|---|---|---|
| 지금의 사실·지시 | "the fork is cheap only while the cache is warm" | 둔다 |
| 실행해 확인할 수 있는 근거 | `snippets/x.luau` | 둔다(행동에 쓰임) |
| 적용 범위 메타데이터 | `last_confirmed: luau 0.742` | frontmatter 에만 |
| 작업 이력·출처 | ".claude/audit/18 §12", "실측 §12.5", "사용자 결정(2026-11-11)", 라운드 | 빼서 audit/decisions/커밋으로 |
| 시한성 서술 | "현재 기준", "지난주 바꿈" | 빼거나 지금 시제의 사실로 |
- 훅: comment-hygiene 을 넓히거나 짝 훅을 둔다. 같은 경로에서 새로 추가된 줄만 보고, 알리기만 한다. 저장소 예외는 comments.json 방식으로 둔다.
### B. 주석 문자 위생 (사용자 추가 요청)
- 대상 후보: 이모지, non-ASCII 기호(→ — · § “ ”), 영어가 아닌 언어(한국어).
- 정할 것:
  - 기본값(전역)
  - 기존 "주석 언어는 그 파일의 언어를 따른다" 와의 관계
  - 저장소 설정
  - 알림 피로
  - 공개 라이브러리와 사내·학습용 저장소의 차이
  - 회사 동료(한국어 사용자)가 주석을 읽는 사람이라는 점

## 읽을 것
- `/code/Projects/claude-doctor/home/.claude/rules/comments.md`, `home/.claude/hooks/comment-hygiene.py`(패턴, comments.json 처리)
- `/code/Projects/claude-doctor/audit/24-skill-audit.md` §4(모델용 텍스트 원칙)
- 공식: platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices ("Avoid time-sensitive information" 절 등)
- 예시 표본(읽기만): `/code/Projects/quad/.claude/` 일부, `/code/Projects/luau-kb/skills/luau-style/references/modules.md`, `/code/Projects/stl-luau` 의 주석 표본
