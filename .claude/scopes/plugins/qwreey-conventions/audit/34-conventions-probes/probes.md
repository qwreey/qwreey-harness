# 34 qwreey-conventions 프로브 (Claude Code 2.1.316)

상태: 프로브만, 구현 없음. 총비용 약 $0.9 (sonnet, 11회). 재현 자료는 `/tmp/probe-conv/` (플러그인 `plug/`, 실행 `run.sh`, 훅 덤프 `*.log`).

공통 실행: `choom -n 1000 -- timeout 300 claude -p "<프롬프트>" --model sonnet --plugin-dir /tmp/probe-conv/plug --output-format stream-json --verbose --permission-mode acceptEdits --allowedTools <...> </dev/null` (환경변수 `PROBE_MODE=rule|lang|none`). 훅은 `plug/hooks/h.py` 하나: 모든 이벤트의 필드·환경·트랜스크립트 꼬리를 덤프하고, 모드에 따라 주입/거부/차단.

## 기능 1: 규칙 주입

| 프로브 | 조건 | 결과 | 판정 | 비용 |
|---|---|---|---|---|
| R1 | Read 후 PostToolUse additionalContext 로 규칙 주입, 이어서 Edit 로 함수 추가 | `# rule-probe` 를 붙임. 트랜스크립트에 `PostToolUse:Read hook additional context: RULE ...` 가 system 블록으로 Edit 앞에 있음 | 통과 | 0.069 |
| R2 | 위와 같음, general-purpose 서브에이전트 안에서 | PostToolUse 가 `agent_id`, `agent_type=general-purpose` 와 함께 발화. 주입이 서브에이전트에 도달해 준수(깨끗한 파일로 재실행해 확인; 첫 실행은 파일에 이미 주석이 있어 교란) | 통과 | 0.116+0.118 |
| R3 | 기존 Read 없이 새 .py Write, PreToolUse 가 1회 deny(이유에 규칙) | 도구 결과에 `PreToolUse:Write hook error: Blocked once: ...` 로 보임. 모델은 포기·질문 없이 곧바로 규칙을 넣어 Write 재시도, 성공 | 통과 | 0.069 |
| R4 | 같은 규칙을 프로젝트 `.claude/rules/probe.md`(paths) 로 | R1 과 같이 준수 | 대조 동일 | 0.069 |

- 서브에이전트의 PostToolUse/PostToolBatch 에는 `agent_id` 가 있고 메인 것에는 없다. 서브에이전트 자신의 트랜스크립트는 `<session>/subagents/agent-<id>.jsonl` 에 따로 있다.
- deny 문구는 사용자 화면에 "hook error" 로 보일 수 있다(모델은 문제없이 처리).

## 기능 2: 언어 드리프트

| 프로브 | 결과 | 판정 | 비용 |
|---|---|---|---|
| L1 | Stop 의 `decision: block`: 두 번째 Stop 에서 `stop_hook_active=true`. 사유가 `user` 메시지(`isMeta=true`, "Stop hook feedback:\n<reason>")로 들어가고 새 assistant 메시지로 재작성(원 답변 위치를 덮어쓰지 않고 이어짐). 트랜스크립트에는 `system/stop_hook_summary` 가 둘. 영어로 시킨 답은 한국어로 다시 씀. 단 모델이 "(참고: 영어로 요청하셨지만 ... 한국어로 다시 적었습니다)" 를 덧붙임: 사유가 사용자에게 새어 나옴 | 통과, 사유에 "이 알림을 언급하지 말 것" 필요 | 0.093+0.096 |
| L2 | PostToolUse 시점 트랜스크립트 기록은 비동기라 지연: 같은 도구 호출의 직전 text/tool_use 가 있을 때도 없을 때도 있음(첫 Read 는 프롬프트만, 3번째 Bash 는 자기 text 가 없음). 그러나 한 호출 뒤(다음 PostToolUse 나 Stop)에는 항상 있음. Stop 시점에는 마지막 assistant 메시지만 없음 | 부분 통과: 오프셋 방식 (b)는 한 걸음 늦게 동작. 마지막 답변은 Stop 의 `last_assistant_message` 로 | 0.069+0.07 |
| L3 | PostToolBatch 존재. 필드: session_id, transcript_path, cwd, prompt_id, permission_mode, effort, hook_event_name, `tool_calls[{tool_name, tool_input, tool_use_id, tool_response}]`. 병렬 Read 2개: PostToolUse 2회 후 PostToolBatch 1회(tool_calls 2개). 단일 도구: PostToolUse 1회 후 Batch 1회. 서브에이전트에서도 `agent_id` 포함 발화. 모델 호출 직전(다음 턴 직전)의 배치 단위 | 통과 | 0.06 |
| L4 | `CLAUDE_PLUGIN_DATA` 는 훅 환경에 있음: `--plugin-dir` 일 때 `/code/.claude/plugins/data/probe-inline` (`<플러그인명>-inline`; 마켓 설치는 `<이름>-<마켓>`). 스킬 본문의 `${CLAUDE_PLUGIN_DATA}` 는 치환됨. Bash 도구 환경에는 없음(`echo $CLAUDE_PLUGIN_DATA` 빈 값) | 훅·스킬 본문 가능, Bash 불가 | 0.058 |
| L5 | 생략(예산) | - | - |

Stop 페이로드 필드: background_tasks, cwd, effort, hook_event_name, last_assistant_message, permission_mode, prompt_id, session_crons, session_id, stop_hook_active, transcript_path.

## 부작용

- 실행기가 `/code/.claude/plugins/data/probe-inline/`(빈 디렉터리)과 `/code/.claude/projects/-tmp-probe-conv-*` 를 만들었다. 에이전트가 쓴 것이 아니라 런타임이 만든 것. 필요하면 사용자가 삭제(HUMAN_TODO 후보).
