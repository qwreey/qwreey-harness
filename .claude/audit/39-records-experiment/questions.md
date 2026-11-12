# 재편 실험 recall 질문 12개

출처 표시: user = 실제 사용자 트랜스크립트 발화에서 가져오거나 고침(q01-q06, q08). 나머지는 기록 종류를 덮으려고 만듦. 정답은 gold.json(path + anchor).

| id | 종류 | 질문 |
|---|---|---|
| q01 | user | 메모리에만 적혀 레포에 안 실려서 다른 사람이 열면 누락되는 문제(메모리는 이식되지 않음)를 어떻게 다루기로 했나? |
| q02 | user | coderag 의 global/project 계층은 어떻게 나뉘고, 기록용으로는 무엇을 선언해야 하나? |
| q03 | user | coderag 검색이 경로:줄범위로 돌려주면 Read offset/limit 자투리가 토큰을 먹지 않나? 출력 형식은 어떻게 되어 있나? |
| q04 | user | compact 로 길게 이어지는 세션에서, 세션 시작 때 한 번 주입하는 맥락(훅·rules·output style)은 compact 뒤에도 남나? |
| q05 | user | 몇 시간째 방치된 shell task 나 멈춘 subagent 를 하네스가 알려주지 않는 문제는 어디에 어떻게 두기로 했나? |
| q06 | user+landed | 예전 second-opinion 플러그인(audit/context)은 무엇으로 대체됐고 왜 바꿨나? |
| q07 | decisions | 타입 함수(type function) 정책은 프로젝트별로 어떻게 다르고 무엇으로 정했나? |
| q08 | user+sessions | 한글로 물었는데 영어로 답하는 문제는 얼마나 자주 났고 감지 방안은 무엇이 검토됐나? |
| q09 | drafts-landed | 세션 기록 요약을 claude -p 로 돌릴지 API 직접 호출로 할지 어떻게 정했고 왜인가? |
| q10 | rejected | coderag 에 첫 줄 status 파서(C3)를 넣는 안은 왜 안 넣기로 했나? |
| q11 | plan | 도메인 팩을 기본 꺼짐으로 하는 합의와 선행 실측은 무엇인가? |
| q12 | handoff | table-sim 의 mise.toml 핀이 형제 프로젝트와 같다는 서술은 맞나, 정정은 어디에 있나? |

덮는 범위: audit(q01-05,q06,q10), decisions(q07), drafts 중 landed(q06 second-opinion, q09 session-log), handoff(q12), PLAN.md(q11), .claude/sessions(q08). 끝났거나 대체·기각된 문서에 답이 있는 문항: q06(landed+superseded 제안), q09(landed), q10(기각된 안).
