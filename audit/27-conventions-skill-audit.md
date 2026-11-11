# qwreey-conventions 스킬 감사와 남은 주석 보고

범위: `plugins/qwreey-conventions` 의 스킬 둘(`comments`, `agent-docs`), 짝 규칙(`home/.claude/rules/comments.md`, `agent-docs.md`), 훅 알림 문구. 커밋하지 않았다.
기준: skill-creator SKILL.md(쓰기 지침, description, Explain the why, progressive disclosure), 공식 best-practices, `audit/24-skill-audit.md` §4.
보는 자리: (1) 훅 알림을 받고 스킬을 연 모델, (2) 주석이나 문서를 쓰는 중에 스스로 연 모델.

## A. 감사

현황: description 은 486자와 504자(목표 300~500 근처, 상한 1,024 안), 본문 118줄과 66줄(500줄 안), references 없음, 영어 본문과 한국어 트리거 구절은 audit/24 §4-12 와 맞는다. 이유 문장(Test 문장, 가운뎃점이 걸리는 이유, Ref 꼬리)은 이미 있다. 아래는 어긋난 것이다.

### 바로 고친 것 (명백)

| # | 심각도 | 문제 | 고친 내용 |
|---|---|---|---|
| 1 | 중 | agent-docs 가 "유지보수 근거는 스킬 밖 docs 폴더"라 하는데 audit/24 §4-2 와 이 하네스의 실제 관행(스킬 안 `references/rationale.md`)과 모순 | 스킬 안 `references/rationale.md`(한 줄 링크)와 스킬 밖 docs 폴더를 둘 다 허용 |
| 2 | 중 | agent-docs 표의 "입구 문서: skill 바로 아래 다른 파일"이 훅 동작과 다름(훅은 `references/` 밖의 skills 아래 모든 `.md` 를 입구로 본다) | "`references/` 밖의 skill 아래 다른 파일"로 |
| 3 | 중 | rules/comments.md 의 `paths` 에 `sh, html, htm` 이 없는데 훅은 검사한다(.sh, .html 주석을 쓸 때 규칙이 안 로드됨) | 글롭에 추가 |
| 4 | 중 | comments 의 "기존 id 는 지우지 않는다"와 "이력은 커밋 메시지로"가 새로 쓰는 이력과 기존 id 를 구분하지 않아 충돌처럼 읽힘 | 기존 id 는 `Ref:` 꼬리로, 지금 쓰는 이력은 커밋 메시지로 구분해 적음 |
| 5 | 중 | 알림을 받은 모델에게 "고친 결과"를 보여 주는 예시가 없음(스킬 둘 다). agent-docs 는 예시가 전혀 없음 | comments 에 알림 한 건의 전후 예, agent-docs 에 이력 문장을 사실과 출처로 나누는 전후 예 |
| 6 | 낮 | comments 의 "공개 id 는 이력이 아니다"가 맨 끝에 있어 알림 처리 중 앞서 읽는 "What a comment says" 에서 안 보임 | "What a comment says" 로 올림, 중복 절 삭제 |
| 7 | 낮 | `min_reason_words` 와 `patterns` 의 null(끔)이 스킬 설정 설명에 없음(README 에만 있음) | 추가 |
| 8 | 낮 | agent-docs 의 "Move, do not delete" 에 이유가 없음 | 한 절로 이유 추가(출처를 지우면 나중에 결정을 추적할 수 없다) |
| 9 | 낮 | comments 의 "Existing comments" 에 이유가 없음 | "무관한 주석 수정으로 실제 변경이 묻힌다" 추가 |
| 10 | 낮 | 훅 docstring, README, plugin.json 이 Stop 보고(B)를 모름 | 갱신 |

### 제안으로 남긴 것 (판단이 갈림)

| # | 심각도 | 문제 | 고칠 방향 |
|---|---|---|---|
| P1 | 중 | comments 본문이 "알림이 올 때" 절로 시작한다. 스스로 연 모델은 "What a comment says", Style 을 먼저 읽고 싶은데 알림 표를 지나야 한다(약 25줄) | 순서를 "What a comment says, Characters, Style, 알림 처리" 로. 알림 청중은 표 제목만 찾으면 됨. 두 청중 중 어느 쪽을 앞에 둘지는 사용 빈도를 봐야 한다 |
| P2 | 중 | 알림이 범주만 말한다. 문서의 `history marker` 한 범주에 날짜, 경로, 결정 문구, 실측 표지, 변경 서술, 원장 id 6가지가 뭉쳐 모델이 어느 토큰이 걸렸는지 짐작해야 함(알림 문구 길이와 맞바꿈) | 알림에 걸린 토큰을 붙인다. 예: `L24 history marker: "H-973"`. 검사 범주와 패턴은 그대로, 알림 상세만 늘어남 |
| P3 | 낮 | 알림은 "fix the lines you added" 만 말하고 의도적 예외 처리는 스킬에만 있다. 스킬을 안 연 모델은 공개 id 를 억지로 고칠 수 있음 | 알림 끝에 "or leave a deliberate exception and say so" 추가(훅 알림이 길어짐) |
| P4 | 낮 | 두 스킬의 `argument-hint: "[file or note]"` 를 본문이 쓰지 않음(인자가 오면 무엇을 하는지 없음) | 인자 처리를 한 줄 정하거나 필드를 뺀다 |
| P5 | 낮 | description 에 열거가 있음(agent-docs: 측정 표지, 정정 배너 등). audit/24 §4-9 는 원리 한 줄을 권함. 길이는 500 안팎이라 급하지 않음 | 열거를 줄여 400자 안쪽으로. 발동률에 영향을 주므로 `/skill-doctor` 나 트리거 질의로 확인 후 |
| P6 | 낮 | comments 의 "Repo settings"(설정 키 설명)는 알림 처리나 쓰기 중인 모델에겐 거의 불필요 | `references/settings.md` 로 분리(progressive disclosure). 본문 118줄이라 이득이 작다 |
| P7 | 낮 | agent-docs 의 "모델 사이 텍스트는 영어"에 이유가 없다 | 한 절 이유를 추가(audit/24 §4-12 의 근거를 요약). 근거 문장은 내가 새로 지어내지 않고 사용자와 확인 |
| P8 | 낮 | 같은 (파일, 범주)는 한 번만 알려서 두 번째 편집의 같은 위반은 알림이 없다(audit/26 설계). 단 B 의 Stop 보고는 다음 편집부터 그 줄을 "남은 것"으로 센다 | 설계 유지. 보고가 안전망 역할을 하므로 별도 조치 불필요 |

모순 점검 결과: 규칙, 스킬, 훅 사이에서 위 1~4 말고는 찾지 못했다. 범주 이름, 알림 문장 구조, Ref 꼬리 허용, 기호 대체표는 세 곳이 서로 맞는다.

## B. 남은 주석 보고

### 전달 방식 선택

공식 hooks 문서를 확인한 사실:
- Stop 과 SubagentStop 의 `hookSpecificOutput.additionalContext` 는 지원되지만 "대화를 이어 가게 한다". `decision: block` 보다 오류 표시만 약하고 같은 루프 보호(`stop_hook_active`, 연속 8회 상한)를 쓴다. 곧 후보 (a) 는 턴을 늘린다.
- Stop 의 `systemMessage`(공통 필드)는 사용자에게 경고로 보이고, Stop 절은 이것을 버린다고 하지 않는다(Notification, SessionEnd 등은 버린다고 명시).
- 서브에이전트가 끝난 뒤 부모에게 맥락을 넣으려면 Agent 도구의 PostToolUse 가 문서가 권하는 길이다.

| 후보 | 전달 확실성 | 비용 | 소음 |
|---|---|---|---|
| (a) Stop additionalContext | 확실 | 턴 1회 추가(캐시 읽기 + 최종 보고를 다시 씀), 매 Stop | 최종 보고가 두 번 나올 수 있음 |
| (b) 첫 알림에 꼬리 | 추가한 줄이 깨끗하면 안 뜸 | 0 | 수정 직후에 뜸(요구와 반대) |
| (c) 스킬이 report.py 를 돌리라고 지시 | 모델이 스킬을 열고 기억해야 함 | 모델 호출 1회 이상 | 낮음 |
| 선택: Stop systemMessage | 훅이 직접 보임, 모델 순응 불필요 | 모델 호출 0 | 내용이 바뀔 때만 한 줄 |

선택 이유: 비용 0, 턴을 늘리지 않고, 모델이 잊어서 빠지는 일이 없다. 사용자가 최종 보고를 읽는 자리와 같은 시점에 보인다. 알아야 할 사람이 사용자이므로 모델을 거칠 이유가 약하다. 사용자 요청과 다른 점: 모델이 최종 보고에 "쓰는" 것이 아니라 훅이 사용자에게 직접 보인다. 서브에이전트는 따로 보고하지 않아도 되도록 메인 Stop 이 세션의 모든 호출한 쪽 기록을 합친다(서브에이전트가 호출자에게 한 줄 쓰게 하려면 SubagentStop additionalContext 로 턴이 늘어난다). 모델이 직접 쓰는 쪽이 낫다고 판단하면 `report_leftovers` 의 출력만 `hookSpecificOutput.additionalContext` 로 바꾸면 된다.
확인하지 못한 것: 실제 대화형 UI 에서 systemMessage 가 어떻게 그려지는지는 직접 보지 못했다(문서 근거). `claude -p` 로 시험하지 않았다.

### 동작
- PostToolUse: 편집된 파일 전체에서 이번 편집이 추가하지 않은 줄의 문제를 범주별 줄 수로 센다(이력, 기호, 이스케이프, 보이지 않는 문자. 언어 불일치는 파일 다수 기준이라 기존 줄에서는 세지 않는다). `$TMPDIR/claude-conventions/<세션>.left.<main|에이전트>.json` 에 파일별 마지막 편집 기준으로 덮어쓴다. 고치면 빠진다.
- Stop: 모든 기록을 합쳐 파일이 아직 있는 것만, 5개까지 한 줄, 직전 보고와 같으면 침묵. 형식: `손댄 파일에 기존 주석 문제가 남아 있음: a.luau(이력 3, 기호 12), b.rs(기호 4). 정리는 요청하실 때만.`
- 고치지 않고, 기존 주석을 일괄 정리하지 않는 원칙은 그대로다. 알림(추가한 줄)과 이 보고(기존 줄)는 줄이 겹치지 않는다.
- 비용: 파일 전체 렉싱은 원래 하고 있었고 줄 단위 검사가 더해진다. 재생에서 파일당 최대 79ms(훅 제한 10초).

### 재생 빈도
quad 와 table-sim 의 최근 10커밋(병합 제외)을 읽기만 해서 재생했다. 커밋마다 한 세션으로 보고, 커밋이 바꾼 파일 중 훅 대상(코드 확장자 표, 모델용 문서)을 직전 내용과의 차이로 "추가한 줄"을 정해 기록한 뒤 Stop 이 한 줄을 냈는지 센다. 현재 체크아웃에 없는 파일은 빠지므로 하한이다. 스크립트는 `/tmp/conv-replay/replay.py`(저장소에 넣지 않음).

| 저장소 | 보고가 뜬 커밋 | 기록한 파일 | 비고 |
|---|---|---|---|
| quad | 6/10 | 119 | 한 줄에 파일 5개 상한이라 큰 커밋도 한 줄. 이력 57~77, 기호 50~80 같은 큰 파일이 있음 |
| table-sim | 4/10 | 12 | 작은 스크립트(`scripts/sfx/*.py`, `.sh`)는 기호 1~3 |

해석: 기존 주석이 많은 저장소에서는 대략 두 번에 한 번 꼴로 한 줄이 뜬다. 한 세션 안에서는 목록이 바뀔 때만 뜨므로 긴 세션에서 반복되지 않는다. 시끄럽다고 느껴지면 임계(예: 파일당 3줄 이상)나 Stop 대신 세션 끝 한 번만으로 줄일 수 있다. 판단은 사용자에게 맡긴다.

### 테스트
`plugins/qwreey-conventions/tests/test-conventions-check.py` 에 Stop 시나리오 9건 추가(없을 때 침묵, 범주별 줄 수와 형식, 중복 보고 안 함, 추가한 줄은 알림이 맡고 집계 제외, 서브에이전트 기록 합산, 고치면 사라짐, 파일 삭제 시 제외, 모델용 문서 집계, `CONVENTIONS_CHECK=off`).

## 검증
- 플러그인 테스트, `home/.claude/hooks/tests/*`, `claude plugin validate`: 최종 응답에 결과를 적는다.
- 자기 검사: 새로 만들거나 고친 파일을 이 훅에 Write 입력으로 넣어 알림 0건을 확인했다(`/tmp/conv-replay/selfcheck.sh`).
- `conventions-check.py` 는 879줄로 구조 경고선(800줄)을 넘었다. 분리 후보는 남은 주석 보고(`record_leftovers`, `leftover_message`, `report_leftovers`, 약 90줄) 또는 간이 렉서. `python3 -I` 는 형제 모듈을 import 하지 못하므로 `importlib.util` 로 불러야 해서 이번에는 나누지 않았다.
- 새 Stop 보고는 모델에게 가지 않는 사용자 메시지라 `HOOK-MESSAGES.md` 의 harness-hook 표 밖이다. 범위 밖이라 고치지 않았다. 필요하면 정본에 한 줄 추가를 제안한다.
