# second-opinion:fresh-advisor 설계 (옛 이름 audit) 근거와 측정

SKILL.md 에서 옮겨 온 내용이다(지시가 아니라 근거).

## 왜 이 스킬인가 (audit/18)
- 같은 묶음의 `second-opinion:inherit-advisor`(옛 context)는 대화를 이어받아 흐름에서 놓친 것을 보고, 이 스킬은 diff 와 주장을 반증한다(`audit/18` §9, §11: 둘이 잡는 문제는 거의 겹치지 않았다).
- advisor 는 대화 전체를 받아 맥락은 정확하지만 메인 관점에 끌려가고, 언제 부를지가 모델 판단이라 예측이 안 되며, Opus 5 이상 advisor 의 조언은 암호화돼 사용자가 읽을 수 없다(`audit/18` §1). 이 스킬은 그 반대편이다.
- 내장 advisor 도구는 가격 대비 효용이 이 스킬보다 낮아 평소에 쓰지 않는다. 사용자가 요청할 때만 쓴다(`audit/18` §3.3).
- 잘 잡는 것: 재현되는 구현 버그, 정본·설치본 차이, 말한 것과 한 것의 차이. 잘 못 잡는 것: 대화에만 있던 맥락(병행 작업 영향, 미결 질문)은 `second-opinion:inherit-advisor`.

## 브리프 규칙의 근거
- 병행 작업을 "범위 밖"으로 적지 않는다: §9 재현에서 리뷰어가 병행 작업 쪽 위험을 놓친 직접 원인이었다.
- 사용자 요구의 내 요약과 내 결론의 근거 설명을 넣지 않는 이유는 앵커링을 피하기 위해서다. 리뷰어가 원문을 직접 본다.

## 비용 [실측, §9.4]
- 리뷰어는 새 컨텍스트라 메인의 캐시를 쓰지 못한다. 대신 맥락이 메인 길이와 무관하다(첫 쓰기 약 6만 토큰: 시스템 + 브리프).
- 비용은 도구 턴 수가 정한다. §9 에서 opus 21~29턴 $0.96~1.17(200초 안팎), sonnet 16턴 $0.42(103초). 1회 opus $1.0~1.2, sonnet 약 $0.4, 2~3분.
- 그래서 촘촘하게 부르는 용도가 아니다. 작업 단위당 `done` 한 번이 기본이다.

## 측정 도구
- 검토 효과: `review-ledger.py stats` - 종류·검토자·트리거별 발견, 채택률, "발견 없음" 비율. 채택률이 낮은 트리거는 임계를 올리거나 끈다.
- advisor 와 비교: `advisor-stats.py --all` - advisor 호출 수, 결과 종류, 토큰, API 환산 비용, 직후 메인 반응.

## 비용 수치 (SKILL.md 에서 이동)
- opus 1회 약 $1, sonnet 약 $0.4, 2~3분. 작업 단위당 `done` 한 번.

## 한계: 여러 세션이 한 작업 트리를 쓸 때
- 알림 훅(`hooks/second-opinion-nudge.py`)의 diff 계산(`git diff HEAD` 의 줄 수와 해시)은 세션을 가르지 못한다. 다른 세션이 같은 트리에서 고친 줄도 임계와 dedup 해시에 들어간다. 그래서 알림이 내 변경이 아닌 줄 때문에 울리거나, 다른 세션의 변경 때문에 해시가 바뀌어 다시 울릴 수 있다.
- 리뷰어 쪽 완화: 브리프에 "Files I changed" 를 넣고, 리뷰어는 목록 밖 변경을 발견이 아닌 맥락으로 다룬다(`agents/reviewer.md`).
- 스크래치(`/tmp/claude-audit/<session_id>/<agent_id>/`)도 세션·리뷰어별로 갈라서, 같은 머신의 여러 리뷰어와 같은 세션의 여러 리뷰어가 서로의 프로브를 덮어쓰지 않게 했다. 가드는 훅 입력의 `session_id`·`agent_id` 로 하위 폴더를 정한다.

## 중첩 호출: 누가 리뷰어를 불렀나
- 서브에이전트도 서브에이전트를 띄울 수 있어(깊이 3), 일꾼이 리뷰어를 부르거나 메인과 동시에 부를 수 있다. 서브에이전트 안의 훅 입력에도 부모와 같은 `session_id` 가 들어오고 구별은 `agent_id`·`agent_type` 뿐이다.
- 부모를 알려 주는 필드는 없다. `claude -p` 로 일꾼(general-purpose)이 Explore 를 띄우게 하고 훅 입력을 덤프해 확인했다. SubagentStart/Stop 에는 session_id, transcript_path(항상 메인 것), agent_id, agent_type 만 있고, agent_transcript_path 는 평평한 `subagents/agent-<id>.jsonl` 이라 경로로 부모를 알 수 없다. 서브에이전트 안의 PreToolUse(Agent)에는 agent_id 가 있고 메인의 것에는 없다.
- 그래서 `hooks/track-reviewer.py` 가 PreToolUse(Agent, `second-opinion:reviewer`)에서 호출자(main/subagent)를 세션별 대기열에 넣고, SubagentStart 에서 꺼내 `agent_id → 호출자` 로 짝짓는다. nudge 는 SubagentStop 에서 호출자가 subagent 가 아닐 때만 last-review 를 쓴다.
- 한계: 같은 세션에서 둘 이상이 거의 동시에 리뷰어를 띄우면 대기열 순서와 시작 순서가 어긋나 호출자가 뒤바뀔 수 있다. 거부된 호출이 남긴 대기열 항목은 120초 뒤 버린다. 짝을 못 찾으면 호출자를 알 수 없음으로 두고 main 으로 센다(예전 동작).
- 이 전에는 nudge 가 agent_id 가 있는 입력을 맨 앞에서 버려서, 실제 SubagentStop(agent_id 는 끝난 리뷰어 자신의 것)에서는 last-review 가 한 번도 쓰이지 않았다. 이제 SubagentStop 을 그보다 먼저 처리한다.
- ledger 의 `--caller main|subagent` 는 선택이고, 없는 옛 기록도 stats 가 읽는다(`caller / -`).

## 통계 도구 (SKILL.md 에서 이동)
- `review-ledger.py stats`: 종류·검토자·트리거별 발견, 채택률, "발견 없음" 비율. `advisor-stats.py --all`: advisor 호출과 비용. `user-asks.py`: 사용자 원문 추출.
