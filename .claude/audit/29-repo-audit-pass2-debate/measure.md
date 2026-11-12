# 0단계 실측 (2026-11-11)

스크립트와 덤프는 저장소 밖 `/tmp/m29/` 에 있다. 표시는 **실측** 또는 **추정**이다. 모델 호출 비용은 합계 약 $0.25로, 예산($0.05)을 넘었다. 원인: 항목 3·8 의 `claude -p` 가 사용자 CLAUDE.md 와 도구 정의를 모두 실어 한 번에 $0.06~0.13 이 들었다. 항목 7 은 `--system-prompt --tools ""` 라 호출당 약 $0.002~0.01.

## 1. load 범주 규칙을 최근 50커밋에 재생 (실측 + 규칙은 흉내)
- 규칙: 상시 파일 = 루트 CLAUDE.md/AGENTS.md, 경로 조건 없는 rules. 조건부 rule = paths 있는 rules. 스킬 본문 = SKILL.md. drafts 와 docs 는 제외. 단위는 (커밋, 파일). 한 커밋을 한 세션으로 본다. 토큰은 추정식. 홈 CLAUDE.md 3,389 를 합계에 더했다(.claude/audit/28 실측값).
- 모델 알림(파일의 세션 첫 편집마다 한 번): claude-doctor 50커밋 중 20커밋에서 57건(rules·SKILL, 넘음 0건). quad 0건(50커밋 안에 CLAUDE.md 를 고친 커밋이 없다). luau-kb 28커밋 중 22커밋에서 66건(상시 AGENTS.md 6.9k 와 rules/README 2.4k 가 있어 파일 예산 초과가 10건).
- `home/.claude/CLAUDE.md`(claude-doctor 에서 13커밋이 고침, 크기 1.7k->3.6k): 파일 예산 2.5k 를 넘은 상태로 고친 것이 8건. 이 파일이 모델 알림의 주 소음원이 된다(의도된 압력).
- 사용자 줄: 합계(5k)를 이번 편집이 넘는 edge 는 세 저장소 모두 0건. 파일 예산을 새로 넘은 edge 는 luau-kb 3건(rules/luau-core.md 1.4k->2.5k 포함). 현재 합계는 quad 5.6k(CLAUDE.md 2.2k + 홈), luau-kb 12.7k(AGENTS.md 6.9k + rules/README 2.4k + 홈)로 이미 넘었으므로 edge 는 거의 뜨지 않는다. claude-doctor 는 홈 3.4k + 새 CLAUDE.md 0.4k = 3.8k.
- 한계: 재알림 규칙(+0.5k)은 상한만 셌다(claude-doctor 7, luau-kb 12). 메모리 인덱스·스킬 목록(1.7k)은 합계에 넣지 않았다. 넣으면 apply 직후 이미 5.06k 라 합계 edge 는 더 안 뜬다.

## 2. 백그라운드 셸 지속 시간 (실측)
- `~/.claude/projects/**/*.jsonl` 404개 `Bash run_in_background` 중 완료 알림이 있는 396개(completed 376, failed 17, killed 3). 시작은 tool_use 시각, 끝은 task-notification enqueue 시각.
- 분포: 중앙값 5.4분, p75 15분, p90 30분, p95 30분, p99 64분, 최대 20.6시간. 5분 초과 204, 15분 초과 122, 20분 초과 86, 30분 초과 41, 1시간 초과 5, 2시간 초과 2.
- 정확히 1,800초에 끝난 것이 30개(타임아웃으로 보임). 긴 것의 상당수는 agy-delegate(출력이 끝에 한꺼번에 나오는 조용한 작업)와 `until ... sleep` 감시 루프라, "진척 없음 15~20분" 문턱은 이들에서 오탐이 날 수 있다.
- 미완료 알림 8건(서브에이전트 세션 위주).
- **2h48m 사례: 기록에서 찾지 못했다**(이 세션의 jsonl 에는 120초 초과로 자동 백그라운드된 task bdzpzcfwj 가 3.4분 만에 TaskStop 된 것 하나뿐이고, 알림 기록이 없다). 그래서 실제 걸린 시간은 잴 수 없다. **추정**: 출력 0, CPU 0 으로 가정하면 "진척 없이 15~20분, 나이 30분 이상" 규칙은 나이 조건 때문에 **약 30분**에 걸린다.
- 참고: 포그라운드 Bash 가 120초를 넘으면 `run_in_background` 없이도 백그라운드로 옮겨진다("moved to the background (ID: …)"). 이 경로의 task 도 `background_tasks` 에 들어갈 것이다(추정).

## 3. 훅 입력 필드 (실측, `claude -p` sonnet, `--settings` 로 덤프 훅)
- **Stop / SubagentStop 모두 `background_tasks` 가 있다.** 배열 원소 필드: shell 은 `id`, `type: "shell"`, `status: "running"`, `description`, `command`. subagent 는 `id`, `type: "subagent"`, `status`, `description`, `agent_type`. 시작 시각, pid, 출력 경로, 크기는 **없다**. 그 밖의 Stop 필드: `session_id, transcript_path, cwd, prompt_id, permission_mode, effort, stop_hook_active, last_assistant_message, session_crons`. SubagentStop 은 추가로 `agent_id, agent_type, agent_transcript_path`.
- 백그라운드 작업이 도는 중에도 Stop 이 여러 번 온다(작업이 끝나 알림이 오면 새 턴과 새 Stop). 마지막 Stop 은 `background_tasks: []`.
- Bash `run_in_background` 의 PostToolUse `tool_response`: `{stdout:"", stderr:"", interrupted:false, isImage:false, noOutputExpected:false, backgroundTaskId:"<id>"}`. `tool_input` 에 `run_in_background: true`. Agent 쪽은 `{isAsync, status:"async_launched", agentId, outputFile, canReadOutputFile, canContinueAgent, ...}`.
- 함의: 시작 시각은 PostToolUse 때 직접 기록해야 한다. 출력 파일 경로는 `/tmp/claude-<uid>/<프로젝트>/<session>/tasks/<id>.output` 꼴(알림 본문에서 확인, 추정으로 조립 가능). 서브에이전트는 `agent_transcript_path` 가 없는 Stop 쪽 목록 원소로는 얻지 못하므로 `agents/agent-<id>.jsonl` 로 조립한다.

## 4. fork 의 `agent_type` (부분 확인)
- 서브에이전트 `*.meta.json` 에서 fork 30개는 `agentType: "fork"`, `isFork: true`, `parentAgentId`. 이 값은 transcript 메타이고, **SubagentStart/Stop 훅 입력의 agent_type 으로는 실측하지 못했다**(그 입력에서는 general-purpose 만 봤다). 훅 쪽 값은 **미확인**. 원장(`~/.local/state/claude-second-opinion/ledger.jsonl`)은 리뷰 기록 2건뿐이라 agent_type 이 없다.

## 5. 세션당 서브에이전트 수 (실측, `subagents/*.meta.json`)
- 메인 세션 295개 중 서브에이전트를 쓴 것 33개. 전체 기준 평균 4.4, 중앙값 0, p90 1, 최대 662(quad). 쓴 세션만: 평균 39.7, 중앙값 2, p90 66, 최대 662. claude-doctor 7개 세션: 평균 17.6, 중앙값 0, 최대 122(이 세션).
- 유형: general-purpose 1088, quad-doc-auditor 155, fork 30, Explore 25, second-opinion:reviewer 4. 평균이 극단값에 끌려 가므로 CLAUDE.md 의 서브에이전트 배수 비용은 중앙값(0~2) 기준으로 어림하는 것이 맞다.

## 6. `tools/home-sync.sh status` (실측)
- 3회 0.769, 0.766, 0.772초(`timeout 60`, `</dev/null`, rc 0). SessionStart 에서 불러도 부담이 없다. 출력은 22줄: 모든 항목 "같음", settings "4/4 적용", "고아 없음", 켠 플러그인 모두 설치됨(해시를 만들 수 있는 안정적 출력).

## 7. 영어판 크기 (실측)
- 방법: .claude/audit/28 과 같다(`claude -p ok --model sonnet --system-prompt <내용> --tools "" --setting-sources ""`, 기준선 509 를 뺌). 번역은 직접 했다(구조·표·"Compact instructions" 포함, 값은 보존).
- 한글판(home/.claude/CLAUDE.md, 7,106B) **3,389 토큰**(.claude/audit/28 값과 일치). 영어판(6,832B) **2,394 토큰**. 차이 -995 토큰, 한글판의 -29%.
- 상시 합계에서 호출당 약 1k 토큰, 서브에이전트 배수까지 곱하면 더 줄어든다. 번역본은 저장하지 않았다(`/tmp/m29/home-en.md`, 저장소 밖).

## 8. systemMessage 표시 (부분 확인)
- `claude -p --output-format stream-json --verbose` 에서 SessionStart 훅의 `{"systemMessage": ...}` 는 `{"type":"system","subtype":"hook_response","hook_event":"SessionStart", "output": "<원문 JSON>", "stdout": ...}` 로 나온다. 별도의 systemMessage 이벤트는 없다. Stop 훅의 hook_response 는 이 짧은 실행의 스트림에 나오지 않았다(-p 에서 끝 알림이 생략되는 것으로 보임, 미확인).
- **대화형 UI 에서 어떻게 보이는지: 사용자 확인 필요.**
