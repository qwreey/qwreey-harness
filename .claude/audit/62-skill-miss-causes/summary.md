---
format: 1
title: 62. 스킬이 작업 중에 안 불리는 원인과 규약 지킴 목록
description: 규약 스킬은 실제 작업에서 거의 안 불림(comments 0/79, 셋 합 3/173); 원인은 포인터보다 rule 이 쓰기 뒤에 오거나(71) Bash 쓰기라 아예 안 오는 것(69); 지킴은 알림이 하고(42건 중 로드 1, 바로 고침 약 32), 스킬만 있는 요구(한국어 어미, 문체, 표시 자리, description 꼴 등)는 rule 이나 훅으로 옮기고 스킬은 절차·설정 참고로 둔다
---
# 62. 스킬이 작업 중에 안 불리는 원인과 규약 지킴 목록

> Snapshot 2026-11-16. May differ from now; check current files and git log before relying on it.

질문(사용자): "스킬이 읽히지 않는건 이유가 약간 다른것 같음. 룰도 요청 내용처럼 실릴거고, '자세한건 보라' 는데 그 자세한건 봐야할 동기가 없는거 아닐까". 패널 D7 a(원인 조사), D9 a(스킬을 줄이고 포인터; 메모: 규약은 안 읽어도 지켜져야 함, "위반이 나야지만 고쳐진다"), D6 메모(설정은 스킬에서 빼되 키보드 문자 등은 스킬 없이 지켜져야 함). 서브에이전트(opus)가 기록만 읽어 조사했고 메인이 이 요약을 썼다. 모델 비용 0. 원자료 `/tmp/skillmiss/`(커밋 안 함).

## 방법
- 실제 프로젝트 기록 1,501개(3.72 GB, main 과 `<sid>/subagents/`)를 줄 단위 JSON 으로 훑었다. 형제 저장소 기록은 모두 2026-11-10 에 끝나고 규약 스킬은 11-11 에 생겨서, 스킬이 목록에 있는 기록은 claude-doctor 세션뿐이다(main 3, 서브에이전트 161, 맥락 178, coderag 와 tbox 편집 포함). luau-kb 스킬이 실린 실제 세션은 없다.
- 계기: 소스 파일에 주석 줄을 더한 쓰기(comments), CLAUDE.md, SKILL.md, agents, rules, skills 문서 쓰기(agent-docs), `@copy-of`, `@start-replace`, `@dup-ok` 추가(code-reuse), `.claude/**.md` 쓰기(agent-records). Bash heredoc, sed, python 쓰기 포함, 맥락마다 첫 번만. 스킬 이름을 단 훅 알림도 셌다. 각 계기의 프롬프트나 브리프, 앞 동작 5개, rule 주입 시점과 포인터 문구, 보이는 thinking 을 뽑았다.

## 결과
| 스킬 | 계기 | 로드 | main / 서브 |
|---|---|---|---|
| comments | 79 | 0 | 10 / 69 |
| agent-records | 47 | 1 | 7 / 40 |
| agent-docs | 35 | 1 | 4 / 31 |
| code-reuse | 12 | 1 | 2 / 10 |

- 기록 전체의 대상 스킬 로드는 6번(agent-records 3, code-reuse 2, agent-docs 1, comments 0)이다. 모두 낯선 절차가 과제 자체일 때다: "Before you create, move ... load" rule 을 본 직후 `coderag records move` 앞, 사본 상수를 찾기 전, 브리프가 스킬을 짚은 보관 이동. 브리프가 스킬을 짚어도 2번은 안 불렀다.
- 알림 45건: 이력 19, 기호 15(가운뎃점 10, 말줄임 5, 가로줄 4, 화살표 4), 언어 12, copy-of 3. 스킬을 단 42건 중 로드 1, 같은 파일을 바로 고친 것 약 32(Edit 13, Bash 19). "Load the skill and fix" 명령형 8건도 로드 0.
- 서브에이전트가 Edit, Write 로 쓴 주석 줄의 기호 비율: comments rule 이 맥락에 있을 때 1.2%(18/1,441), 없을 때 4.5%(21/471).

## 원인
| 원인(주 원인 하나) | comments | agent-docs | agent-records | code-reuse | 듣는 처방 |
|---|---|---|---|---|---|
| A Bash 로 씀: rule 주입도 알림도 없음 | 39 | 21 | 9 | 0 | 훅만: Bash 가 바꾼 파일의 추가 줄 검사를 모델에게 |
| B rule 이 첫 쓰기 뒤에 옴(읽기를 cat, sed -n 으로 함, 서브 Bash 읽기 3,325 대 Read 645, 또는 새 파일) | 29 | 10 | 25 | 5 | 내용을 rule 본문에(쓴 뒤 주입이 "Check what you wrote" 로 사후 검사 역할), 훅 |
| C 포인터 있는 rule 이 쓰기 전에 있었는데 안 부름 | 4 | 2 | 3 | 3 | 내용을 rule 에; 트리거 꼴은 다음 행동이 맞을 때만(audit 57) |
| D rule 이 늦거나 안 옴(경로 불일치, 배포 전) | 7 | 1 | 9 | 3 | 훅 범위, paths |

겹치는 요인: 과제 표현에 해당 영역 낱말이 거의 없음(comments 2/79, agent-docs 9/35, agent-records 4/47, code-reuse 0/12): 주석은 모든 코드 작업에 딸린 일이라 description 이 순간과 안 맞는다. 같은 파일을 방금 읽고 바로 씀(comments 37/79). 보이는 thinking 은 과제만 말함("평가 러너가 ... 고친 뒤 커밋하겠습니다"), 한 번은 스킬 없이 아는 것을 적용("새 provider 파일의 주석은 영어 기준에 맞춰"). 서브에이전트도 스킬 목록은 받으니 목록 부재는 원인이 아니다.

## 목록
rule = 늘 실리는 본문, 훅 = Edit, Write 뒤 검사. Bash 쓰기는 모두 검사 밖. "스킬만" = 스킬에만 있고 아무도 검사하지 않음.
- comments. rule 과 훅으로 지킴: 이력 빼기, 키보드 문자(알림이 대체 문자를 줌), 이스케이프, 보이지 않는 문자(훅만), 언어(rule 에 comment_language 줄), Ref 이유 문장, 손댄 주석만. rule 만: 이유를 쓴다, 기존 id 는 지우지 않고 Ref 로. 스킬만: 한국어 어미(합니다체, 한다체)를 파일에 맞춤, 문체(띠 줄, 대문자나 IMPORTANT, 의례어, 식별자 백틱), 주석의 "previously" 서술, 문서 블록 위 Ref 자리, 일부러 둔 예외를 보고에 한 번 적기, 이력용 새 파일 금지. 참고: 설정 키, scan/fix 정리, readable-code 알림 표.
- code-reuse. 지킴: copy-of, start-replace 해석과 일치, 정본 편집과 sync-copies, dup-ok 이유(훅만). rule 만: 정책 값과 DEFAULT_, 한 정의, 공유 모듈, 비교 시험, 벤더 트리, why not 줄, 유니언과 목록. 중복 묶음 검사는 기본 shadow 라 사실상 rule 만. 스킬만: 표시는 줄 주석(문서 블록 아님)과 언어별 꼴(Astro, JSON, Rust), 형제 저장소 `<repo>:<path>` 꼴(HARNESS_WORKSPACE 있을 때만 알림), 생태계 목록은 팩 제안, 하는 김에 단순화.
- agent-docs. 지킴: 이력 빼기와 옮기기, references 허용. rule 만: 지우기 시험. 스킬만: 스킬 description 꼴(무엇과 언제, 영어, 3인칭, 한국어 계기), 모델 사이 글은 영어, 사례 나열 대신 원리, 관리자용 근거는 references/rationale.md, 원장 id 는 함께 배포되는 .md 와 함께(훅은 같은 줄 .md 만 봄).
- 크기: 가장 큰 주입 8,576 / 9,000 자(약 420 남음). 상한은 훅 출력 하나마다라 주입을 두 훅으로 나누면 늘어난다(미확인).

## 권고
- 규약(모델이 이미 할 줄 알지만 버릇으로 어기는 것)은 지킬 것 전부를 rule 본문에, 쓰면서나 쓴 뒤 바로 대조할 수 있는 꼴로 두고, 모든 쓰기 경로(Bash 포함)에 훅 검사를 둔다. 스킬은 지킴의 경로에 두지 않는다. 지식, 절차 스킬(기록 이동, 표시 문법, sync 도구, 설정)은 과제 표현에 맞춘 description 과 "Before you <행동>, load" 로 둔다. 관찰된 로드 6번이 모두 이 꼴이다. 시험: "스킬을 한 번도 안 읽으면 무엇이 깨지나" 의 답이 선택 절차뿐이어야 한다.
- D6 의 키보드 문자 등은 지금 rule 과 훅으로 지켜진다. 빈틈은 Bash 쓰기(원인 A 69): Bash 가 바꾼 파일의 git diff 추가 줄에 같은 검사를 돌려(PostToolUse:Bash 또는 Stop) 모델에게 알린다. 지금 Stop 은 도구로 고친 파일만, 사용자에게만 보인다.
- comments rule 에 넣을 것(약 200자, 포인터 줄을 줄이면 들어감): 한국어 어미 줄(훅 범주로도 가능: 니다, 다 어미를 파일 다수와 비교), 문체 한 줄("No banners, capitals or IMPORTANT for routine notes; skip ceremony words"), 알림 대응 한 줄("fix the named lines; leave a deliberate exception and say so once in your report"). 주석 이력 패턴에 서술("previously", "이전에는")을 더한다.
- 포인터: "Details, repo settings and what to do with a hook notice: load" 는 버린다(쓰기 전에 있던 16맥락에서 로드 0, 명령형 알림 8건도 0). 지식 작업용 트리거 한 줄만 둔다("Before a comment cleanup the user asked for, or editing `.claude/conventions.json`, load ..."). 알림은 스스로 완결되게(줄과 대체 문자) 두고 스킬 로드를 시키지 않는다.
- code-reuse 의 표시 자리와 언어별 꼴, 형제 저장소 꼴, agent-docs 의 description 꼴과 모델용 영어는 같은 시험에서 떨어지므로 rule 한 줄이나 훅 검사로 옮길 후보다.
- 사용자 메모("위반이 나야지만 고쳐진다")는 맞다. 다만 자료로는 그것이 이미 유일하게 작동하는 경로다(알림 뒤 고침 약 32/38, 쓰기 전 rule 은 comments 79번 중 8번만). 그러니 지킬 것을 rule 이나 훅으로 옮기면 스킬을 나눠도 지킴은 줄지 않는다.

## 한계
main 자료는 사실상 긴 세션 2개(같은 사용자의 하네스 작업)다. 게임 저장소나 Luau 자료는 없다. 계기 판정은 휴리스틱이다(주석 접두어, Bash 명령 1,500자 자름과 상대 경로, 이력 표지 잡음, "고침" 은 25동작 안 같은 파일 편집). thinking 은 173번 중 23번만 요약으로 보여 "안다고 판단" 은 추정이다. 기간 중 포인터 문구가 바뀌어(11-16 에 code-reuse, agent-docs 가 Before you 꼴로) 새 꼴을 본 계기는 적다. 저장소 개발 중 SKILL.md 를 읽은 것은 로드로 세지 않았다.
