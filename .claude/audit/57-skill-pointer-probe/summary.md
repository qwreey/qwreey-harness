---
format: 1
title: 57. rule 의 스킬 포인터가 스킬 로드를 일으키는지 실측
description: rule 끝 "자세한 건 스킬" 포인터는 로드를 못 일으킴(sonnet 7문형 0/21, opus 현행 0/3); opus 는 "Before you <행동>, load X" 만 3/3; 스킬은 description 이 과제와 맞을 때만 로드됨(code-reuse·agent-records 3/3); 흔한 경우에 필요한 사실은 rule 본문에
---
# 57. rule 의 스킬 포인터 실측

> Snapshot 2026-11-16. May differ from now; check current files and git log before relying on it.

질문(사용자): "스킬이 읽히지 않는건 이유가 약간 다른것 같음. 룰도 요청 내용처럼 실릴거고, '자세한건 보라' 는데 그 자세한건 봐야할 동기가 없는거 아닐까 싶기도. … rules 에서 skill 이 언급되는 경우 어떤 동작을 띄는지는 좀만 더 연구를 해봐야하나 싶기도 하네." 서브에이전트(opus)가 측정하고 메인이 이 요약을 썼다. 원자료 `/tmp/skillptr/`(커밋 안 함). 비용 약 USD 4.0.

## 설정
- 플러그인 사본을 `--plugin-dir` 로 실음(qwreey-conventions: rules_inject, bash-bypass-reminder 훅만; coderag 대역: agent-records rule·스킬, 같은 rules_inject). 실제 세션처럼 rule 은 Read 뒤 훅 additionalContext 로, 스킬은 목록에 이름·description 으로 보인다. 실제 세션은 스킬이 약 30개라 로드율이 이보다 높지는 않을 것이다.
- 임시 `CLAUDE_CONFIG_DIR`(자격 증명만, 실행마다 삭제), `--setting-sources project`. 주 격자는 Bash 를 껐다(파일럿에서 sonnet 이 heredoc 으로 써서 rule 이 쓰기 뒤에 오거나 안 옴). 그래서 rule 이 늘 쓰기 전에 도착하는, 포인터에 가장 유리한 조건이다.

## 주석 과제
스킬에만 있는 사실: 새 파일은 `.claude/conventions.json` 의 `comment_language` 를 따른다. 한국어 프롬프트, 형제 파일 한국어 주석, 설정은 en. 과제는 `streak.py` 에 함수 하나 추가.

| 형태 | sonnet 로드 | sonnet 영어 주석 | opus 로드 | opus 영어 주석 |
|---|---|---|---|---|
| a 포인터 없음 | 0/3 | 0/3 | - | - |
| b 현행 "Details...: load X" | 0/3 | 0/3 | 0/3 | 3/3(탐색 중 conventions.json 을 읽음, 스킬 덕이 아님) |
| c "Before you write or edit a comment or docstring, load X" | 0/3 | 0/3 | 3/3(쓰기 전) | 3/3 |
| d "If you are unsure ..., X answers it" | 0/3 | 0/3 | - | - |
| e 사실을 rule 에 넣음(+b) | 0/3 | 0/2(1회 주석 없음) | 0/3 | 2/3 |
| f 빠진 것 명시 + "now" | 0/3 | 0/3 | - | - |
| g 트리거를 rule 맨 위로 | 0/3 | 0/3 | - | - |
| b, Bash 허용 | 0/3(rule 은 쓰기 뒤 2, 없음 1) | 0/3 | | |

opus a, d, f, g 는 자동 모드 분류기가 추가 opus 실행을 막아 측정하지 못했다(우회하지 않음).

## description 이 과제와 맞는 경우 (sonnet, 포인터 없음)
- code-reuse(가져올 수 없는 형제 저장소 STATUSES 복사): 쓰기 전 로드 3/3, 표시 3/3, 비교 시험 3/3. `<repo>:<path>` 형식은 1/3; 2회는 스킬의 `<repo>:<path>`(copy-of)와 region 의 `../<repo>/<path>` 를 섞은 `../statuslib:...`.
- agent-records("기록해 줘"): 첫 동작으로 로드 3/3, Snapshot 줄·`format: 1`·snapshot 에 status 없음 모두 3/3.

## 결론
- 스킬은 description 이 사용자의 과제 표현과 맞을 때 rule 보다 먼저 로드된다. 그때 포인터는 상관없다.
- 과제와 description 이 어긋나면(함수를 쓰다가 주석) rule 의 포인터는 sonnet 에서 어떤 문형도 효과가 없고, opus 에서는 다가올 행동을 짚은 트리거 문형만 효과가 있었다.
- rule 은 Read 묶음 뒤에 오고 다음 동작이 곧 Write 라 로드할 계기가 없다. sonnet 은 rule 이 요구하는 쓰기 전 추가 행동(스킬 로드, 설정 파일 확인)을 하지 않는다. rule 에 사실을 넣어도 따로 찾아봐야 적용되는 사실(e)은 지키지 않았다.

## 권고
- 흔한 경우의 출력을 바꾸는 사실은 rule 본문에, 쓰면서 바로 적용할 수 있는 꼴로 넣는다. 저장소 설정 값(`comment_language` 등)은 주입 훅이 rule 과 함께 그 값을 넣는다("This repo: comment_language = en").
- 포인터가 필요하면 "Before you <구체 행동>, load `<skill>`" 로 쓴다. "Details/Markers...: load" 꼴은 버린다.
- 스킬 로드를 늘리려면 description 을 과제 표현에 맞춘다(comments 는 "소스 코드를 쓸 때" 쪽; 미측정, 로드 비용 고려).
- code-reuse 스킬 Markers 표에 형제 저장소 `@copy-of` 예시를 넣어 region 경로 꼴과 구분한다.

## 한계
칸당 3회. opus 결과는 3회에 기댄다. description 이 어긋나는 과제는 주석 하나뿐이다. thinking 이 가려져 건너뛴 이유는 보지 못했다.
