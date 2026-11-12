# 21. 서브에이전트 비용: 고지, 슬롯, 가시화

> 이름 변경(2026-11-11): 사용자 호출 명령은 플러그인 `q` 로 모였다(`/away`→`/q:away`, `/back`→`/q:back`). 스킬은 `plugins/q/skills/{away,back}`. 아래 서술의 옛 위치 `home/.claude/skills/*` 는 이력이다.

- 날짜: 2026-11-10
- 환경: claude 2.1.316, 실측 모델 sonnet 5.5
- 구현 위치: 정본 `home/.claude/` 에 구현했다. 실제 `~/.claude` 에는 아직 반영하지 않았다(`tools/home-sync.sh diff` → `apply`).
- 표기: [문서]는 공식 문서, [실측]은 이번에 로컬에서 재현한 것, [추정]은 근거로 미루어 본 것, [미확인]은 확인하지 못한 것이다.

## 0. 요지

### 사용자 결정 (2026-11-10)
- 막는 비용 가드는 두지 않는다. 비용은 돈을 내는 사용자가 판단한다.
- 사용자가 `/q:away` 로 자리를 비운다고 선언했을 때만 다음을 건다.
  - 전체 예산 상한
  - 동시 슬롯: 슬롯이 차면 "하나가 끝나면 다음" 식으로 직렬화한다.

### 구현
- **attended(기본)**: 아무것도 막지 않는다.
  - 큰 팬아웃이면 warn 으로 "사용자에게 규모를 고지하라"를 낸다.
  - 큰 팬아웃의 기준: 동시 4개 이상, opus 이상 2개 이상, Workflow.
- **away**: `/q:away [예산] [슬롯]` 으로 켠다.
  - 실행 중인 수가 슬롯 이상이면 그 호출만 deny 한다. 사유는 `queue: wait for a running agent to finish, then spawn the next` 이고 level 은 action 이다. 세션은 계속 돈다.
  - 예산을 넘기면(1단계) 슬롯을 1로 줄여 직렬화한다. 메인에는 재고 리마인더를 한 번 준다.
  - 예산의 2배를 넘으면(2단계) 새 서브에이전트와 Workflow 를 모두 거절하고, 메인에게 진척 파일에 상태를 적고 사용자를 기다리라고 한다(§5).
  - `/q:back` 이 비운 동안의 요약을 보여 준다.
- **statusline**:
  - 컨텍스트 %
  - 세션 비용
  - 실행 중인 서브에이전트 수(모델별)
  - away 상태와 쓴 예산
- **CLAUDE.md**: "모델 사용" 절을 넓혀 네 가지를 넣었다.
  - 팬아웃 전에 고지한다.
  - 작은 패스를 여러 번 도는 것을 기본으로 한다.
  - 모델은 작업 크기에 맞춘다.
  - `queue:` 거절은 실패가 아니다.

### 실측 1회 (sonnet)
- 조건: away, 슬롯 2. 서브에이전트 4개를 한 메시지로 띄우게 했다.
- 결과:
  - 2개가 거절됐다.
  - 모델은 완료 알림을 기다렸다가 하나씩 다시 띄웠다.
  - 4개 모두 끝났고, 세션은 한 번도 멈추지 않았다.
  - 이 단계 비용은 약 $0.25 다.

## 1. 사실 확인

### 1.1 훅 입력

#### PreToolUse 의 Agent·Workflow matcher
- [문서] PreToolUse 는 내장 도구 이름 `Agent`, `Workflow` 에 매치된다(hooks 문서 "PreToolUse").

#### Agent 의 `tool_input`
- [문서] `prompt`, `description`, `subagent_type`, `model` 을 받는다.
- [실측] 로컬 트랜스크립트의 Agent 호출 1,079건을 집계했다.
  - 키: `description`, `prompt` 1079 · `subagent_type` 981 · `model` 904 · `run_in_background` 518 · `isolation` 76
  - `model` 은 별칭이다: sonnet 473 · opus 418 · 없음 175 · fable 9 · haiku 4.

#### Workflow 의 `tool_input`
- [실측] 인라인 워크플로는 `{script}` 하나뿐이다. 모델과 에이전트 수는 스크립트 안에 있다.
- [미확인] 저장된 워크플로를 이름으로 부를 때의 입력.

#### 포그라운드 Agent 의 이벤트 순서 [실측]
1. PreToolUse
2. SubagentStart
3. SubagentStop
4. PostToolUse(`status: completed`, `agentId`, `resolvedModel`)

- 한 메시지에 Agent 호출이 여럿이면 PreToolUse 가 약 0.7초 간격으로 차례로 불렸다.

#### 백그라운드 Agent 의 이벤트 순서 [실측]
1. PreToolUse
2. PostToolUse(`status: async_launched`, `agentId`, `resolvedModel`, `outputFile`)
3. SubagentStart
4. (끝나면) SubagentStop

- **백그라운드 서브에이전트가 끝날 때도 SubagentStop 이 발화한다.**

#### Workflow 안의 에이전트 [실측]
- SubagentStart/Stop 을 낸다(`agent_type: "workflow-subagent"`).
- Workflow 의 PostToolUse 는 `status: async_launched`, `taskType: local_workflow` 다.

#### SubagentStart 입력
- [문서] `agent_id`, `agent_type`.
- [문서] 서브에이전트를 막을 수는 없다. 서브에이전트 쪽 맥락만 더할 수 있다.

#### SubagentStop 입력
- [문서] `agent_id`, `agent_type`, `agent_transcript_path`, `last_assistant_message`, `background_tasks`.
- [문서] Claude 가 띄우지 않은 내부 에이전트(prompt suggestion, `/btw`)에도 발화한다. 이때 `agent_type` 은 빈 문자열이다.

#### Stop·SubagentStop 의 `background_tasks` [실측]
- 부모 세션 범위에서 실행 중인 작업 목록이다.
- 항목: `{id, type: subagent|shell|workflow|monitor…, status, description, agent_type}`.
- subagent 의 `id` 는 `agent_id` 와 같다.
- 멈추는 에이전트 자신도 목록에 아직 `running` 으로 들어 있다.
- 포그라운드 서브에이전트는 목록에 없다.

#### SubagentStop 은 "완료"가 아니라 "턴 끝"이다 [실측, 중요]
- 에이전트 C 의 흐름:
  1. 자기 백그라운드 셸(`sleep 25`)과 Monitor 를 걸었다.
  2. SubagentHandback 을 하고 턴을 끝냈다. 여기서 SubagentStop 이 났다.
  3. 20초 뒤 그 백그라운드 작업 알림으로 다시 깨어났다. 같은 `agent_id` 로 **SubagentStart 가 다시** 났다.
  4. 한 번 더 SubagentStop 이 났다.
- 이 틈에 슬롯 2 인데도 3개가 약 1초 겹쳤다. 아래 §2.4 한계를 본다.

#### 내장 상한 [문서]
- `CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS`(기본 20): 넘으면 Agent 가 `Concurrent subagent limit reached` 로 실패하고 "재시도하지 말라"고 한다.
- 워크플로 동시 실행은 16이다(`CLAUDE_CODE_WORKFLOW_MAX_CONCURRENT_AGENTS`).
- 워크플로가 25개를 넘기거나 예상 150만 토큰을 넘기면 `Large workflow` 경고가 뜬다. 막지는 않는다.
- `-p` 에는 `--max-budget-usd` 가 있다.
- 이 셋은 모두 시작할 때 정하는 정적 값이다. 세션 중에 away 로 바꿀 수 없다. 그래서 훅이 필요하다.

### 1.2 서브에이전트 사용량 수집

#### 트랜스크립트 위치 [실측]
- `~/.claude/projects/<키>/<session>/subagents/agent-<id>.jsonl`
- 각 assistant 줄에 `message.usage` 와 `message.model` 이 있다.
- usage 에는 다음이 들어 있다: `cache_creation.ephemeral_5m/1h_input_tokens`, `speed`, `inference_geo`.

#### 메타 파일 [실측, 비공식]
- `agent-<id>.meta.json` 에는 `agentType`, `toolUseId`, `requestShape`(foreground/background), `model`, `spawnDepth`, `finished` 가 있다.
- 지금 세션에서 `finished` 가 없는 4개가 실행 중인 4개와 정확히 일치했다.
- 복구용 보조 근거로만 쓴다.

#### usage 를 세는 법 [실측]
- 같은 `message.id` 의 줄은 usage 가 모두 같았다(1,655개 id 에서 다른 것 0).
- 그래서 id 당 한 번만 센다.

#### 공식 가격과의 대조 [실측]
- 이 방식으로 계산한 USD 가 CLI 의 `total_cost_usd` 와 일치했다.
  - 프로브: 메인 $0.06253 + 서브 2 × $0.04354 = $0.14962. CLI 는 $0.1496219 였다.
  - 실측 세션: 트랜스크립트 합 $0.3857, CLI 누적 $0.3856.
- 따라서 **세션 비용(`total_cost_usd`)은 서브에이전트를 포함한다.**
- 주의: `-p --resume` 의 `total_cost_usd` 는 재개를 거쳐도 **누적**된다 [실측].

#### SubagentStop 시점의 지연 [실측]
- SubagentStop 이 날 때는 마지막 응답이 아직 트랜스크립트에 없었다.
- 그때 바로 세면 에이전트마다 약 7% 가 빠졌다(4개 모두 $0.003~0.005 차이).
- 원장은 멈춘 지 10분 안의 에이전트를 다음 훅 이벤트마다 이어서 읽는다(`sweep`).

#### 다른 수단
- [문서] PostToolUse(Agent) 의 `totalTokens`/`usage` 는 **마지막 요청 하나**의 값이다. 합계가 아니다.
- [문서] 백그라운드 Agent 의 PostToolUse 에는 usage 가 없다.
- [문서] 서브에이전트 합계는 OTel 카운터(`query_source: subagent`)로도 볼 수 있다. 여기서는 쓰지 않았다.
- [미확인] task-notification 본문의 usage. 이번 세션 트랜스크립트에서 따로 보지 않았다.

### 1.3 statusline 이 받는 JSON [문서]

#### 받는 필드
- `session_id`, `transcript_path`, `model.{id,display_name}`, `workspace.*`
- `cost.{total_cost_usd, total_duration_ms, total_api_duration_ms, total_lines_added/removed}`
- `context_window.{used_percentage, remaining_percentage, context_window_size, current_usage…}`
- `rate_limits.{five_hour,seven_day,spend_limit}`: 구독자에게만 온다.
- `prompt_cache`: 메인 대화에만 해당한다.
- `effort`, `agent.name`, `pr`, `worktree`

#### 서브에이전트 관련 필드
- 서브에이전트 수나 비용 전용 필드는 없다.
- `agent.name` 은 `--agent` 로 띄운 세션의 이름이다. 서브에이전트와는 관계없다.

#### 갱신 시점
- 새 assistant 메시지, `/compact`, 권한 모드 변경 등의 이벤트가 오면 갱신된다. 300ms 디바운스가 있다.
- 메인이 백그라운드 에이전트를 기다리며 쉬면 갱신도 멈춘다. 문서가 이때 `refreshInterval` 을 쓰라고 권한다.

#### `total_cost_usd` 가 서브에이전트를 포함하는가
- 문서는 "/cost 와 같은 합계"라고 한다.
- `-p` 실측으로는 서브에이전트를 포함했다.
- [미확인] 대화형 statusline 에서 직접 확인하지는 않았다. 대화형 UI 를 띄울 수 없었다.

### 1.4 스킬에서 상태를 바꾸는 법 [실측]

#### 치환
- `${CLAUDE_SESSION_ID}`, `${CLAUDE_SKILL_DIR}`, `$ARGUMENTS` 는 치환된다.

#### `` !`명령` `` 주입
- `allowed-tools` 가 없으면 실행되지 않았다. 하네스가 그 줄을 `[run this first, exactly as written, and use its output: `…`]` 로 바꿔 모델에게 넘겼고, 모델이 Bash 로 대신 실행했다.
- 스킬에 `allowed-tools: Bash(python3 ${CLAUDE_SKILL_DIR}/../../lib/subagent_ledger.py *)` 를 넣으면 바로 실행됐다. 출력이 본문에 들어갔다. 이 경우 모델 판단을 거치지 않는다.

### 1.5 모델별 가격 비율

출처: 공식 가격 페이지 https://platform.claude.com/docs/en/about-claude/pricing (2026-11-10 열람).

| 모델 | 입력 | 5분 캐시 쓰기 | 1시간 캐시 쓰기 | 캐시 읽기 | 출력 |
|---|---|---|---|---|---|
| Fable 5.2 | $8 | $10 | $16 | $0.20 | $40 |
| Fable 5.1 | $10 | $12.50 | $20 | $0.25 | $50 |
| **Opus 5.5** | **$4** | $5 | $8 | **$0.20** | **$20** |
| Opus 5 / 4.8 | $5 | $6.25 | $10 | $0.50 | $25 |
| **Sonnet 5.5** | **$2** | $2.50 | $4 | **$0.10** | **$10** |
| Haiku 5.5 (프롬프트 10만 이하) | $0.10 | $0.125 | $0.20 | $0.01 | $0.50 |

#### 비율
- **Opus 5.5 = Sonnet 5.5 × 2.** 입력, 캐시 쓰기와 읽기, 출력 모두 2배다.
- **Fable 5.2 = Opus 5.5 × 2.** 입력과 출력이 2배다. 캐시 읽기만 같다($0.20).
- Fable 5.1 은 Opus 5.5 의 2.5배다. audit/18 이 쓴 $10/$50 이 이것이다.
- Haiku 5.5 는 Sonnet 5.5 의 1/20 이다. 그러나 규칙상 읽기 전용 조사에만 쓴다.

#### 기타 배수와 할증
- Opus 5.5, Sonnet 5.5 의 캐시 읽기는 기본 입력의 0.05배다.
- 4.6 이후 모델(Haiku 5.5 는 빼고)은 100만 컨텍스트 전체를 기본 가격으로 받는다. 장문 할증이 없다.
- fast mode 는 Opus 5.5 기준 $8/$40 으로 2배다.
- `inference_geo=us` 는 1.1배다.

#### 해석
- "작은 모델로 되는가"를 물으면 opus → sonnet 은 **정확히 절반**이다.
- 같은 opus 5개를 sonnet 5개로 바꾸는 것과 opus 5개를 2~3개의 순차 패스로 줄이는 것은 비슷한 크기의 절감이다.
- 세션 맥락이 크면 캐시 읽기가 비용을 지배한다(audit/18 §비용). 이것도 모델 비율대로 2배가 난다.

## 2. 설계

### 2.1 attended 와 away

| | attended (기본) | away (`/q:away` 선언) |
|---|---|---|
| 서브에이전트 호출 | 막지 않음 | 실행 중 ≥ 슬롯이면 **그 호출만** deny(`queue: …`, action). 세션은 계속 |
| 예산 | 없음(보기만) | 넘기면 슬롯 → `HARNESS_AWAY_OVER_SLOTS`(기본 1). 재고 리마인더 warn 1회 |
| 큰 팬아웃 | warn "규모를 사용자에게 고지" (묶음·compact 회차마다 1회) | 슬롯이 대신함(고지 warn 없음) |
| Workflow | warn 고지 | 기본 `idle`: 실행 중 0일 때만 허용 + warn(내부 동시성은 슬롯 밖). `deny`/`allow` 선택 가능 |
| 끝 | - | `/q:back` 이 요약(비운 시간, 쓴 비용, 띄운 수, 줄 세운 수, 예산 초과, 실행 중, 사건)을 보여 주고 끈다 |

- "팬아웃 묶음"은 실행 중 0개에서 시작해 다시 0개가 될 때까지다.
  - 한 메시지에 6개를 띄워도 warn 은 한 번이다.
  - 다음 묶음에서는 다시 낸다.
  - compact 회차가 오르면 같은 묶음 안에서도 다시 낸다(HOOK-MESSAGES 의 dedup 규약).
- attended 에서 warn 은 **호출이 이미 진행된 뒤** 모델에게 보인다(PreToolUse additionalContext). 그래서 "띄우기 전에 고지"는 CLAUDE.md 규칙이 주된 장치이고, 훅은 놓쳤을 때의 보강이다.
  - 띄우기 전에 묻게 하려면 `permissionDecision: ask` 를 써야 한다. 그러면 사용자가 없을 때 멈추므로 쓰지 않았다(사용자 결정).

### 2.2 `/q:away [예산] [슬롯]`, `/q:back`

- `/q:away 15 2`: $15, 슬롯 2. `/q:away $15` 도 같다. `/q:away 8a 3` 은 서브에이전트 8개, 슬롯 3이다.
- 인자를 생략하면 `HARNESS_AWAY_BUDGET_USD`(20)와 `HARNESS_AWAY_SLOTS`(2)를 쓴다.
- `/q:away status`, `/q:away off`(= `/q:back`), `/q:away reset`(카운터 비우기).
- 둘 다 `disable-model-invocation: true` 다. 사용자만 부른다.
- 상태는 `!` 주입으로 스크립트가 직접 바꾼다. 모델은 결과만 전한다.

#### 예산 단위 비교

| 단위 | 장점 | 단점 |
|---|---|---|
| 토큰 | 원자료 그대로 | 캐시 읽기가 대부분이라 숫자가 부풀어 감이 없다. 모델 간 2배 차이를 못 담는다 |
| **추정 USD (API 목록가)** | 모델·캐시 차이를 한 숫자로. CLI `/cost`·statusline `total_cost_usd` 와 같은 척도라 사용자가 이미 아는 감각. 공식 가격표로 재현 가능(위 일치 실측) | 구독 플랜의 실제 한도 소진과는 다르다(구독은 비율대로 깎인다고 [추정]). 가격표가 바뀌면 `PRICES` 를 고쳐야 한다 |
| 에이전트 수 | 미리 정하기 쉽다 | 사용자 지적대로 같은 5개라도 크기가 크게 다르다. 비용을 못 묶는다 |

- **추천: USD.**
  - 무인 세션에서 사용자가 걱정하는 것은 "얼마나 빨리 태우는가"다.
  - 범위는 메인과 서브에이전트를 모두 포함한다. `/q:away` 이후에 쓴 것만 센다.
- 에이전트 수(`8a`)는 보조로 남겼다.
- 구독 사용자에게 더 정확한 척도는 `rate_limits` 의 한도 % 다. 이 값은 statusline 에만 오므로 statusline 이 파일에 적고 훅이 읽는다. 사용자 결정으로 `/q:away 30%`·`30%w`·`30%5h` 를 지원한다(§5-1). 2단계(예산의 2배)에서는 새 서브에이전트·Workflow 를 거절한다(§5-2).

### 2.3 슬롯 직렬화와 카운터

- 원장: `$TMPDIR/claude-subagent-slots/<session_id>.json`.
  - `fcntl` 잠금 아래에서 읽고, 원자적으로 쓴다.
  - compact 회차로 나누지 않는다. 실행 중인 수는 compact 와 무관하기 때문이다.
  - 알림 dedup 키에만 회차를 넣는다.
- **+1 (예약)**: PreToolUse(Agent) 를 허용하면 `reserved[tool_use_id]` 를 만든다. 들어가는 값은 모델 계열, 타입, 백그라운드 여부다.
  - 같은 메시지의 여러 호출이 SubagentStart 전에 연달아 와도 그 사이를 센다.
- **예약 → 실행 중**:
  - 백그라운드는 PostToolUse(`async_launched`, `agentId`)에서 바꾼다. `tool_use_id` 로 정확히 짝지어진다.
  - 포그라운드는 SubagentStart 에서 바꾼다. 짝은 `meta.json` 의 `toolUseId` 로 찾고, 없으면 같은 타입의 가장 오래된 예약으로 찾는다.
  - 워크플로 에이전트는 예약 없이 SubagentStart 에서 실행 중에 더한다.
- **−1**: SubagentStop(`agent_id`) 에서 뺀다. 포그라운드는 PostToolUse(`completed`) 에서도 뺀다. 두 번 빼도 무해하다.
- **비용**: SubagentStop 에서 그 에이전트 트랜스크립트를 offset 부터 이어서 읽는다. 재개된 에이전트를 두 번 세지 않는다.
  - 메인 트랜스크립트는 PreToolUse 와 Stop 에서 이어서 읽는다.
  - 처음 볼 때는 끝에서 시작한다. 긴 세션을 소급해 읽지 않는다.
- 슬롯 판정: `len(실행 중 + 예약) >= 슬롯` 이면 deny 한다.
  - 예산을 넘겼으면 슬롯 대신 `over_slots`(기본 1)를 쓴다.
- 서브에이전트 안에서 하는 중첩 호출도 같은 세션 원장으로 센다. 그 훅은 메인 offset 을 건드리지 않는다.

#### 어긋남 복구

모든 훅 이벤트에서 `live()` 가 아래 근거를 위에서부터 적용한다.

1. **`background_tasks`**: Stop·SubagentStop 이 준다. 공식 필드다.
   - 백그라운드로 표시된 항목이 목록에 없으면 SubagentStop 을 놓친 것으로 보고 뺀다.
   - 띄운 지 10초가 안 된 것은 목록에 아직 없을 수 있으니 남긴다.
2. **`meta.json` 의 `finished: true`**: 비공식, 로컬 실측이다. 포그라운드에도 통한다.
3. **트랜스크립트 mtime**: `HARNESS_SLOTS_STALE_MIN`(30분) 동안 움직임이 없으면 죽은 것으로 본다. 비정상 종료, 크래시, 재부팅에 대비한다.
4. **예약 TTL**: `HARNESS_SLOTS_RESERVE_SEC`(90초) 안에 시작이 오지 않으면 버린다. 다른 훅이 막았거나, 권한이 거절됐거나, 내장 상한에 걸려 실패한 경우다.
5. **수동**: `/q:away reset`.

- 복구한 항목은 원장 `log` 에 이유와 함께 남는다(`recovered`, `why`). 그 마지막 8개를 `/q:back` 이 보여 준다.

### 2.4 한계 (실측 기반)

#### 자기 백그라운드 작업을 남긴 서브에이전트
- §1.1 의 "턴 끝" 문제다. 이런 에이전트는 SubagentStop 뒤에 다시 깨어난다.
- 그 사이 슬롯이 비어 보여 다음 것이 들어가고, 잠깐 슬롯을 넘을 수 있다(실측 1초, 3/2).
- 훅으로는 "턴 끝"과 "완료"를 구별할 공식 필드가 없다.
- 피해: 비용 폭주가 아니라 잠깐 하나가 더 겹치는 정도다. 그래서 받아들였다.
- 고칠 수 있는 방향: SubagentStop 때 `background_tasks` 에 그 에이전트가 만든 셸이나 Monitor 가 남아 있는지 보고 "대기"로 두는 것이다.
  - 그러려면 작업과 에이전트를 연결하는 필드가 필요하다. 지금은 [미확인]이다.

#### Workflow
- 워크플로 안의 에이전트는 SubagentStart 를 막을 수 없다. 그래서 슬롯 밖이다.
- away 의 기본값 `idle` 은 "다른 것이 돌지 않을 때만 시작"이다.
- 진행 중에는 그 에이전트들도 실행 중으로 세므로, 다른 Agent 호출을 줄 세운다.

#### 예산은 사후 판정이다
- 실행 중인 에이전트가 쓰는 비용은 그 에이전트가 멈춘 뒤에 들어온다.
- 슬롯 2 에서 마지막 둘이 크면 예산을 그만큼 넘을 수 있다.
- 사용자 결정("상한에 닿기 전에 눈치채고 멈출 기회")과 맞게, 넘긴 뒤에는 직렬화로 속도를 늦춘다.

#### 모델 추정
- `model` 을 생략하면 상속으로 본다. 상속 모델은 메인 트랜스크립트 끝에서 읽는다.
- 사용자 정의 에이전트는 frontmatter 의 `model` 로 판정한다.
- 내장 Explore 등의 기본 모델은 [미확인]이라 상속으로 친다.
- 이 값은 attended 의 "opus 이상" 판정에만 쓴다. 비용은 트랜스크립트의 실제 모델로 센다.

#### 가격표
- 모르는 모델은 0 으로 센다. statusline 에는 CLI 의 `total_cost_usd` 를 그대로 보여 주므로 그쪽은 정확하다.

### 2.5 문턱값 덮어쓰기

우선순위: 환경 변수 > 저장소 `<repo>/.claude/harness.env` > `~/.claude/harness.env` > `lib/subagent_ledger.py` 의 `CFG_DEFAULTS`.

| 키 | 기본 | 뜻 |
|---|---|---|
| `HARNESS_SUBAGENT_SLOTS` | on | off 면 훅이 아무것도 하지 않음 |
| `HARNESS_FANOUT_WARN_CONCURRENT` | 4 | attended: 이 호출로 동시 N개 이상이면 warn |
| `HARNESS_FANOUT_WARN_BIG` | 2 | attended: opus 이상 동시 N개 이상이면 warn |
| `HARNESS_FANOUT_WARN_WORKFLOW` | on | attended: Workflow 마다 warn |
| `HARNESS_AWAY_BUDGET_USD` | 20 | `/q:away` 예산 기본 |
| `HARNESS_AWAY_SLOTS` | 2 | `/q:away` 슬롯 기본 |
| `HARNESS_AWAY_OVER_SLOTS` | 1 | 예산 초과 뒤 슬롯 |
| `HARNESS_AWAY_WORKFLOW` | idle | away 중 Workflow: idle / deny / allow |
| `HARNESS_SLOTS_STALE_MIN` | 30 | 이만큼 조용하면 죽은 것으로 |
| `HARNESS_SLOTS_RESERVE_SEC` | 90 | 예약 TTL |

- 저장소 파일은 위 접두(`HARNESS_SUBAGENT_`, `HARNESS_FANOUT_`, `HARNESS_AWAY_`, `HARNESS_SLOTS_`)의 키만 덮어쓸 수 있다.
  - 저장소가 `HARNESS_HEAVY_WRAP` 같은 다른 하네스 값을 바꾸지 못하게 하려는 것이다. 테스트로 확인했다.
- 예: quad 처럼 속도가 필요할 때 부분별로 나누는 저장소는 `HARNESS_FANOUT_WARN_CONCURRENT=6` 으로 둔다.

### 2.6 statusline

- 출력 예: `Opus ctx 34% · $12.40 · agents 2 (opus 1, sonnet 1) · AWAY $3.10/$15 slots 2 queued 1`
  - 예산을 넘기면: `AWAY OVER $16.20/$15 slots 1`.
- 읽기만 한다. 잠금을 잡지 않는다.
- 단위 테스트 기준으로 한 번에 150ms 미만이다(파이썬 기동 시간이 대부분).
- `refreshInterval: 10` 을 쓴다. 메인이 기다리는 동안에도 실행 중인 수가 갱신되게 하려는 것이다(문서 권고).
- 사용자가 실제 `/code/.claude/settings.json` 에 `statusLine` 을 둔 적이 없음을 확인했다. 그래서 새로 넣었다. 덮어쓰기는 없다.
  - jq 병합에서도 `.statusLine // {…}` 로 기존 값이 이기게 했다.

### 2.7 CLAUDE.md (정본, 45줄 → 48줄)

- "모델 사용" 절을 "모델 사용과 서브에이전트 비용" 으로 넓혔다.
- 기존 두 줄에 세 줄을 더했다.
  - 모델은 작업 크기에 맞춘다(목록가 Opus 5.5 = Sonnet 5.5 의 2배).
  - 작은 패스를 여러 번 도는 것이 기본이다. 근거 둘: 같은 코드를 중복해서 읽는다. 고친 코드도 결국 리뷰를 한 번 더 돈다.
  - 2개 이상을 띄우거나 Workflow 를 쓰기 전에 사용자에게 한 줄로 고지한다(개수, 모델, 이유, 예상 규모).
  - `/q:away` 상태에서 `queue:` 거절은 실패가 아니다.
- "코드 리뷰" 절의 병렬 수 문장은 위의 "작은 패스" 기본을 가리키게 바꿨다. 중복을 없애려는 것이다.

## 3. 구현 (정본 `home/.claude/`)

| 파일 | 내용 |
|---|---|
| `lib/subagent_ledger.py` | 원장(잠금·상태), 가격표, 트랜스크립트 스캔, 복구 `live()`, `sweep()`, 설정 병합, `/q:away`·`/q:back` CLI |
| `hooks/subagent-slots.py` | PreToolUse(Agent\|Workflow), PostToolUse(Agent), SubagentStart, SubagentStop, Stop 을 한 파일에서 처리. 예외는 삼키고 막지 않음 |
| `statusline/harness-status.py` | 위 2.6 |
| `skills/away/SKILL.md`, `skills/back/SKILL.md` | 사용자 호출 전용, `!` 주입 + `allowed-tools` |
| `hooks/tests/test-subagent-slots.py` | 55개 |
| `settings.json` | 위 다섯 훅과 `statusLine` 을 jq 로 **추가만** 했다(diff 는 +58줄, −0). `autoMode` 유지 |
| `MANIFEST`, `harness.env`(주석 키), `HOOK-MESSAGES.md`(배정 표), `CLAUDE.md` | 등록과 문서 |

함께 고친 버그: `structure-reminder` 의 "이번 세션 +300줄 성장" 알림.
- 증상: compact 회차가 오르면 알림이 사라졌다.
- 원인: 성장 기준 줄 수를 회차 키 아래에 저장했다.
- 수정: 기준점을 `<sid>.base.json` 에 session_id 단위로 옮겼다. 알렸는지 여부만 회차 단위로 남겼다.
- 회귀 테스트(`test-compact-rearm.py`): compact 전에 +200줄, 회차를 올린 뒤 +150줄이면 `grew 900 -> 1250` 이 나와야 한다.
  - HEAD 버전에서는 FAIL, 수정본에서는 PASS 임을 확인했다.

## 4. 테스트와 실측

### 단위 테스트 (`python3 -I hooks/tests/test-subagent-slots.py`): 102/102 (§5 의 한도 %·2단계 44개, 중첩 dedup 3개 포함)
- 가격 계산
  - sonnet 5.5 의 캐시 쓰기, 읽기, 출력
  - opus 5.5 = 2 × sonnet 5.5
  - fast mode 2배
  - 모르는 모델은 0
- 같은 id 를 한 번만 세는지, 이어 읽기와 경계
- attended
  - 3개는 조용하다. 4번째에 warn 이 난다. 5번째는 dedup 된다.
  - 묶음이 끝난 뒤 opus 2개면 warn 이 난다.
  - compact 회차가 오르면 다시 난다.
  - Workflow 는 warn 만 내고 deny 하지 않는다.
  - 저장소 설정이 문턱을 낮춘다. 다른 키는 덮어쓰지 못한다.
- away
  - 슬롯 2 에서 3번째 호출은 `queue:` 로 거절된다(level action, 사유 앞부분 일치).
  - 하나가 끝나면 다음 것이 통과한다.
  - Workflow 는 idle 규칙대로 거절된다.
- 예산 소진
  - USD: 초과하면 슬롯이 1이 된다. 실행 중 0개면 허용하면서 재고 warn 을 한 번만 낸다.
  - 에이전트 수(`2a`)
- `/q:back` 의 요약 내용과 꺼짐, 그 뒤 attended 복귀
- statusline 의 문자열, 속도, 빈 입력
- 카운터 복구
  - `background_tasks` 누락, meta finished, 30분 정지, 예약 TTL, 수동 reset, 로그 사유
- 포그라운드 흐름
  - 시작에서 예약이 소비된다.
  - Stop 과 PostToolUse 가 겹쳐도 비용을 한 번만 센다.
- workflow-subagent 를 실행 중으로 센다.
- SubagentStop 뒤에 늦게 쓰인 줄을 sweep 한다.
- 메인 트랜스크립트를 소급하지 않는다. 상속 모델을 opus 로 판정한다. 중첩 호출이 메인 offset 을 지킨다.
- off 스위치, 깨진 입력, 다른 도구 무시

### 다른 회귀 테스트
- `test-compact-rearm.py` 20/20, `test-structure-reminder.py` 72/72.

### home-sync
- `CLAUDE_HOME=<임시>` 로 `apply` 했다.
  - 새 파일 5개를 포함해 모두 복사됐다(`skills/away`, `statusline/` 디렉터리 생성).
  - status 는 전부 같음, 고아 없음이었다.
  - 두 번째 apply 는 변경 0 이었다.
- 임시 settings 에 정본에 없는 키를 넣으면 메인이 넣은 가드가 중단(exit 2)했다.

### 실측 1: 프로브 (sonnet)
- 포그라운드 2개, 백그라운드 2개, Workflow 1개를 띄워 훅 입력을 기록했다. §1.1 의 순서와 필드가 여기서 나왔다.
- 비용은 $0.15 와 $0.24 였다.

### 실측 2: away 줄 세우기 (sonnet)
- 과정:
  1. `/q:away 5 2`
  2. "4개를 한 메시지로 띄워라"
  3. `/q:back`
- 4개 PreToolUse 중 C 와 D 가 거절됐다(`queued` 2).
- 모델은 같은 호출을 바로 다시 하지 않았다. 완료 알림 뒤에 C 를, 다음 완료 알림 뒤에 D 를 띄웠다. 추가 거절은 없었다.
- 4개 모두 보고했고 세션은 끝까지 진행됐다(exit 0).
- 동시 실행은 계속 2개 이하였다. 예외는 §2.4 의 1초 겹침 한 번이다.
- `/q:back`(`!` 주입) 결과: 비운 4분, $0.31 / $5, 4개 띄움, 2회 줄 세움, 예산 초과 아님.
- 원장의 서브 비용 $0.21 은 트랜스크립트 합 $0.23 보다 작았다. SubagentStop 시점 지연 때문이다. `sweep` 을 추가해 고쳤고 단위 테스트로 확인했다.
- 비용(CLI 누적): $0.40.

### 만든 임시 프로젝트 키
- `~/.claude/projects/-tmp-sa-probe-proj`
- `~/.claude/projects/-tmp-sa-live-proj`
- 임시 디렉터리 `/tmp/sa-probe`, `/tmp/sa-live`, `/tmp/ccdocs` 도 남아 있다.

## 5. 사용자 결정 (2026-11-10 반영)

1. **예산 단위는 사용자 요금제에 맞춘다. [결정, 구현됨]**
   - 비개발자는 USD 를 체감하지 못하고 "한도 다 썼다" 로 체감한다. 구독자가 많다.
   - 인자:
     - `/q:away $5`: USD(API 목록가 환산)
     - `/q:away 30%`: 쓸 수 있는 창 중 가장 빡빡한 쪽 기준으로, 지금부터 30%p 를 더 쓸 때까지
     - `/q:away 30%w`, `/q:away 30%5h`: 창을 명시(주간, 5시간)
     - `/q:away 6a`: 에이전트 수
     - 인자 없음: statusline 이 한도 값을 보낸 적이 있으면 `HARNESS_AWAY_BUDGET_PCT`(30), 없으면 USD 기본값(20)과 `[plan-unknown]` 표지.
   - 5시간 창이 없는 요금제(예: 울트라)는 `rate_limits` 에 `five_hour` 가 없을 수 있다. 있는 창만 추적한다.
   - **한도 % 출처 [문서: code.claude.com/docs/en/statusline]**
     - statusline 입력 JSON 의 `rate_limits.five_hour` / `rate_limits.seven_day` 에 `used_percentage`(0~100)와 `resets_at`(epoch 초)이 있다.
     - claude.ai Pro/Max/Ultra 구독자에게만 오고, 세션의 첫 API 응답 이후에 온다. 창마다 따로 빠질 수 있고, `resets_at` 이 지나면 그 창은 사라진다.
     - 앱 게이트웨이 사용자용 `spend_limit` 도 있다(`used_percentage`, 선택으로 `used_usd`·`limit_usd`). 이번에는 쓰지 않았다.
     - 훅 입력에는 없다. [미확인] `/usage`·응답 헤더·로컬 파일에서 읽는 방법은 찾지 못했다(문서에 없다).
     - 로컬 2.1.316 `-p` 실측은 하지 않았다(statusline 이 `-p` 에서 돌지 않을 수 있어 문서 우선).
   - **구조**: statusline 스크립트가 `rate_limits` 를 `$TMPDIR/claude-subagent-slots/<sid>.limits.json`(`{five_hour:{p,r}, seven_day:{p,r}, t}`)에 적고, 훅이 그것을 읽는다. 값이 없으면 파일을 덮지 않는다.
   - **계산**:
     - `/q:away` 시점에 창마다 기준점(`start`)과 남은 여유(`room = 100 - 시작값`)를 기록한다.
     - 1단계 문턱 = `min(N, room)`: 남은 여유가 N 보다 작으면 한도 100% 가 문턱이다.
     - 증가분 = `acc + (last - start)`.
     - `resets_at` 이 60초를 넘겨 바뀌면 창이 리셋된 것이다. 그때까지의 증가분을 `acc` 에 쌓고 새 창을 0 에서 센다(문턱은 N 으로 복구). 60초 안의 흔들림은 리셋이 아니다.
     - 창을 지정하지 않으면 어느 창이든 먼저 문턱에 닿으면 도달로 본다(보통 5시간 창).
   - **값이 오래됐을 때**: statusline 이 `HARNESS_AWAY_LIMITS_STALE_MIN`(10)분 넘게 갱신하지 못하면(대화형이 아님, 닫힘 등) 마지막 증가분은 유지하고, 모자란 부분은 USD 가드(`HARNESS_AWAY_BUDGET_USD`, 기본 20)로 메운다. 상태줄에 `(stale)` 이 붙는다.
   - **요금제 감지**: `rate_limits` 가 왔다는 사실이 구독자 신호다. 못 받으면(비구독, `-p`, 첫 응답 전) USD 로 켜고 `[plan-unknown]` 을 출력한다. 스킬이 사용자에게 한 번 묻고, `harness.env` 에 `HARNESS_AWAY_PLAN=pct|usd` 를 적도록 제안한다(대신 쓰지 않는다).
   - [미확인] 메인이 쉬면서 서브에이전트만 도는 동안 `rate_limits` 가 갱신되는지(서브에이전트 응답이 값을 바꾸는지). 안 바뀌면 그 구간의 % 증가분이 늦게 잡힌다. 실 사용에서 `/q:back` 요약의 USD 와 %p 를 대조해 본다.
2. **예산 초과는 2단계. [결정, 구현됨]**
   - 1단계(예산 도달): 지금처럼 슬롯을 1로 줄이고 재고 리마인더를 한 번 낸다.
   - 2단계(예산의 `HARNESS_AWAY_STAGE2_MULT`=2 배): 새 Agent 와 Workflow 를 모두 deny 한다(`halt: …`, level=action).
     - 첫 거절(compact 회차·away 선언마다 한 번)에 전체 지시를 준다: 진척 파일(또는 세션 메모)에 한 일, 실행 중인 것, 다음, 사용자 결정 필요를 적고 사용자를 기다린다.
     - 이후 거절은 짧은 한 줄이다.
   - **메인을 강제로 끊는 장치는 넣지 않았다.** 지시와 서브에이전트 차단만 한다. 강제 중단이 필요하면 제안이다: Stop 훅에서 `decision`/`continue:false` 를 쓰는 방법이 있으나, 메인의 진행 중인 작업을 잃을 수 있어 사용자 판단으로 남긴다.
   - 한계: 메인이 서브에이전트를 더 부르지 않고 직접 일하면 2단계 안내를 받을 계기가 없다(훅이 낼 수 있는 곳은 PreToolUse 뿐). 메인 자체의 소모는 막지 않는다. 이것이 의도다.
   - **[확정(2026-11-11 사용자) — 메인 단독 작업 때도 안내, 구현됨]** 위 한계를 메우기로 했다. 강제 중단은 넣지 않는다.
     - 방식: `subagent-slots.py` 를 PostToolUse **모든 도구**(`matcher: "*"`, 기존 `Agent` 항목을 대체)에 등록했다. 별도 파일이 아니라 같은 파일에 둔 이유는 `notes` 키(`stage2:main`·`over:main`)와 원장 잠금·판정(`away_check`)을 `pre_agent`·`stage2_deny` 와 공유해서, 메인이 이미 받은 안내를 Agent 거절에서 또 받지 않게 하려는 것이다(이미 받았으면 거절은 짧은 한 줄).
     - 2단계: 메인(agent_id 없음)에게 level=action `halt: …`(진척 파일에 상태를 적고 사용자를 기다려라, 작은 단계는 마쳐도 되나 큰 새 작업은 시작하지 마라)를 (호출한 쪽, compact 회차, away 선언)당 한 번. 서브에이전트 안의 호출에는 내지 않는다.
     - 1단계(over): **같은 경로로 메인 단독에게도 준다**(level=warn, 한 번). 이유: 예산에 도달했다는 사실은 서브에이전트를 부르지 않는 메인에게도 "남은 일이 지출 값어치가 있는가"를 다시 보게 하는 정보이고, 2단계까지 아무 신호가 없다가 갑자기 halt 를 받는 것보다 낫다. 문구는 서브에이전트 직렬화(슬롯 1)와 보고에 언급하라는 것을 같이 담아 Agent 경로의 1단계 리마인더를 대체한다(같은 `over:main` 키라 중복되지 않는다).
     - 메인 소모 파악: 이 경로가 `account_main` 으로 메인 트랜스크립트 증분을 읽는다(15초에 한 번, `MAIN_EVAL_SEC`). 이전에는 Stop·Pre(Agent) 때만 읽어, 한 턴이 길게 이어지면 over2_at 이 늦게 찍혔다.
     - 비용: away 가 아니거나 상태 파일이 없으면 json 도 적재하지 않고 원문에서 session_id 만 뽑아 상태 파일의 `"on": true` 만 확인해 종료한다. 실측(로컬, python 3.14, 호출 40회 평균): 빈 `python3 -I -c pass` 8.2 ms, 이 훅의 not-away 11.4 ms(**순수 추가 약 3 ms**). 최적화 전 단순 구현은 25.5 ms 였다(json·re·importlib·pathlib 적재가 약 14 ms). away 켜진 동안은 원장 적재·잠금·쓰기로 호출당 약 26 ms. 테스트(`test-subagent-slots.py`)가 not-away 추가분 < 10 ms 를 확인한다.
     - 테스트: `test-subagent-slots.py` 102 → 120(메인 단독 18개: 1·2단계 한 번씩, 회차 재안내, agent_id 제외, /q:away 이전 지출 제외, Agent 거절 단축형, 끄기 스위치, 지연).
   - `/q:back` 요약에 1·2단계 도달 여부와 시각이 들어간다. statusline 은 `AWAY OVER …` / `AWAY HALT …` 로 보인다.
3. **고지 문턱의 이중 구조는 의도된 설계다. [결정, 코드 변경 없음]**
   - 메인의 말 고지: CLAUDE.md, 서브에이전트 2개 이상 또는 Workflow 전에 한 줄.
   - 훅 warn: 동시 4개, opus 이상 2개, Workflow. 메인이 고지를 놓쳤을 때의 보강이다.
   - 둘을 2로 맞추면 warn 이 잦아져 무뎌진다. 그래서 일부러 다르게 둔다(`HOOK-MESSAGES.md` 에도 적었다).
4. **away 중 Workflow: `idle` 유지. [결정]** 실행 중 0개일 때만 허용하고, 2단계에서는 `HARNESS_AWAY_WORKFLOW=allow` 여도 거절한다.
5. **실제 반영**
   - `tools/home-sync.sh diff` 로 검토한 뒤 `apply` 한다.
   - statusLine 은 새로 생긴다. 다른 statusline 을 쓰고 싶으면 정본의 `statusLine` 을 지운다.
   - 이번 변경 테스트: `test-subagent-slots.py` 102개(기존 55 + 한도 %·2단계 44 + 중첩 dedup 3), `test-compact-rearm.py` 26개(+6).

6. **dedup 키에 호출한 쪽을 넣었다. [버그 수정]**
   - 서브에이전트 안에서 도는 훅도 부모의 `session_id` 를 받는다. 구분 필드는 `agent_id`(와 `agent_type`)다 [문서: hooks 공통 입력 필드 "tool events such as PreToolUse and PostToolUse fire … the input carries the agent_id and agent_type"]. 로컬 `/tmp/sa-probe` 덤프에는 서브에이전트 안 도구 훅이 없어 실측으로는 확인하지 못했다. 서브에이전트 이벤트(SubagentStart/Stop)의 `agent_id` 만 실측됐다.
   - 이전 키 `(session_id, compact 회차)` 에는 구분이 없어, 서브에이전트가 "회차당 한 번" 알림을 먼저 쓰면 메인이 못 받았다(반대도 같다).
   - 수정: `lib/compact_epoch.py` 의 `state_path(namespace, session_id, agent_id=None)` 가 `<sid>.c<회차>[.a<agent_id>].json` 을 낸다. bash-bypass-reminder·structure-reminder 가 `data.get("agent_id")` 를 넘긴다. subagent-slots 의 `notes` 키(`fanout:`·`over:`·`stage2:`)에도 호출한 쪽을 넣었다.
   - 남은 것: structure-reminder 의 성장 기준점(`.base.json`)은 세션 단위라 메인·서브가 공유한다. 파일별 기준점이라 알림을 가로채진 않지만, 서브가 먼저 쓴 파일의 기준은 서브의 첫 편집 시점이 된다. 필요하면 후속으로 정한다.
