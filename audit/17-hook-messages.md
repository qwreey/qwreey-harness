# 17. 훅 메시지 형식 실측과 규약

날짜 2026-11-10, claude 2.1.316, sonnet. 규약 본문: `home/.claude/HOOK-MESSAGES.md`.

## 1. 실측: 하네스가 훅 출력을 어떤 모양으로 넣는가
방법: `/tmp/hookfmt` 에 마커(`MARK_*_XYZ`)를 내는 훅을 걸고 `claude -p --setting-sources project` 로 실행한 뒤, 트랜스크립트의 `attachment.rendered` 와 `api-request-blob`(실제 API 페이로드)을 비교하고, 모델에게 마커 앞뒤 글자를 그대로 인용시켜 교차 확인했다.

| 출력 종류 | 모델에게 들어가는 모양 | 위치 |
|---|---|---|
| Pre/PostToolUse `additionalContext` | `PreToolUse:Bash hook additional context: <텍스트>` (여러 훅이면 `\n\n` 로 이어 한 덩어리) | 도구 결과 뒤 별도 system 위치 |
| PreToolUse deny `permissionDecisionReason` | tool_result(`is_error`) `PreToolUse:Bash hook error: <사유>`, 모델 인용은 `<error>…</error>` 로 감싸짐 | 도구 결과 |
| Pre/PostToolUse 일반 stdout | **모델에게 안 감.** `hook_success` 첨부(기록용)로만 남음 | - |
| SessionStart `additionalContext` | `SessionStart hook additional context: <텍스트>` | system 프롬프트 앞부분(사용자 턴 쪽으로 인용됨) |
| UserPromptSubmit `additionalContext` | `UserPromptSubmit hook additional context: <텍스트>` | 첫 사용자 턴 안의 일반 텍스트 |
| SessionStart / UserPromptSubmit 일반 stdout | `SessionStart:startup hook success: <텍스트>` / `UserPromptSubmit hook success: <텍스트>` | 같음 |
| PreCompact stdout | `-p --resume "/compact"` 에서 불리는 것만 확인(모델 노출 모양은 미확인) | - |

핵심 발견: 트랜스크립트의 `rendered` 에는 `<system-reminder>\nPreToolUse:Bash hook additional context: …\n</system-reminder>` 로 보이지만, 실제 API 페이로드(`api-request-blob`)와 모델 인용에는 **`<system-reminder>` 가 없다.** 모델이 "XML 태그가 마커를 감싸고 있지 않다"고 직접 답했다. 즉 태그 없는 평문 접두 한 줄이라 사용자 입력과 구분이 약하다. 그래서 우리가 `<harness-hook>` 태그로 감싸고, 배경은 CLAUDE.md 에 둔다.

발췌(`~/.claude/projects/-tmp-hookfmt/*.jsonl`):
```
attachment.type=hook_additional_context  rendered: "<system-reminder>\nPreToolUse:Bash hook additional context: MARK_PRE_CTX_XYZ\n</system-reminder>"
api-request-blob role=system: "PreToolUse:Bash hook additional context: MARK_PRE_CTX_XYZ\n\nPostToolUse:Bash hook additional context: MARK_POST_CTX_XYZ"
user tool_result is_error: "PreToolUse:Bash hook error: MARK_PRE_DENY_REASON_XYZ"
attachment.type=hook_success stdout 'MARK_PRE_PLAIN_STDOUT_XYZ\n'   (모델 인용에 없음)
```

### 하네스가 쓰는 관례(기존 트랜스크립트 표본과 이 세션의 리마인더)
- 태그는 `<system-reminder>`. 첫 줄에 출처("Contents of … CLAUDE.md", "Attribution …")를 밝히고, 훅이 아닌 하네스 본체 리마인더만 이 태그를 쓴다.
- 훅 출처는 `<이벤트>[:도구] hook additional context:` 접두로만 표시된다.

### 실측으로 만든 임시 프로젝트 키(지우지 않음)
`~/.claude/projects/` 아래(`/code/.claude/projects/`): `-tmp-hookfmt`, `-tmp-cmp`, `-tmp-effect-bypass-1`, `-tmp-effect-bypass-2`, `-tmp-effect-struct-h1`, `-tmp-effect-struct-h2`, `-tmp-effect-struct-w1`, `-tmp-effect-struct-w2`.

## 2. 규약
`HOOK-MESSAGES.md` 참고. 요약: 영어·짧게, `<harness-hook name="…">…</harness-hook>` 로 감쌈, 배경은 CLAUDE.md "훅 메시지" 2줄 이하, deny 사유도 동일, 모델에게 보일 말은 JSON additionalContext 로(Pre/Post 일반 stdout 은 안 감), dedup = session_id + compact 회차.

## 3. 적용과 전후 토큰
대상: `heavy-proc-guard`(deny 사유), `bash-bypass-reminder`, `structure-reminder`. 의미는 유지했다. 구조 변경: 접두 `[name]` 대신 태그.
토큰은 대표 메시지 6건(guard, bypass 2, structure 3)을 한 프롬프트에 넣고 `claude -p` usage 의 입력 토큰 합에서 기준 프롬프트를 뺀 값이다.

| | 바이트 | 토큰 |
|---|---|---|
| 전(한국어) | 2739 | 1289 |
| 후(영어+태그) | 2731 | 1023 |

토큰 -21%(-266). 영어가 같은 의미를 짧은 토큰으로 담는다(바이트는 비슷). 태그 오버헤드 포함. 한국어 문구가 길어지지 않은 건 `struct-hard` 처럼 영어가 더 길어진 항목이 있기 때문이다(전 606B → 후 717B이나 토큰은 합계로 감소).

테스트: structure-reminder 69/69(기대 문자열 갱신 + 모든 출력이 태그로 감싸졌는지 검사 추가), heavy-proc-guard·bash-bypass-reminder 는 파이프로 6건 출력 확인(`/tmp/capture.py`), 새 `test-compact-rearm.py` 16/16.

## 4. 효과 실측 (sonnet, 각 2회, 프로젝트 CLAUDE.md 에 배경 2줄 포함, 훅만 정본)
- bash-bypass-reminder: `--!strict` 가 rules 로만 지정된 재고 모듈 과제를 셸 heredoc 으로 만들게 함. **2/2 준수**(이전 haiku 0/2 → 2/2 와 같은 결과). 한 회는 최종 보고에 "`.claude/rules/luau-core.md` 규칙에 맞춰 `--!strict` 를 넣었다"고 적음. 훅을 사용자 지시로 착각한 흔적 없음.
- structure-reminder: 1495줄 파일에 함수 3개 추가(hard 발동) 2회 — 둘 다 끝에 "하네스 훅이 분할안을 먼저 제안하라고 알려 왔다 / 훅 지침"이라고 출처를 훅으로 밝히고 분리안 제안을 제시. 795줄(warn) 2회 — 둘 다 분리 후보를 한 줄로 보고. 4/4, 사용자 지시로 오인한 사례 없음.

## 5. compact 와 dedup
실측(`/tmp/cmp`, `--resume <id> "/compact"`): session_id 유지. 호출 순서 PreCompact(trigger=manual) → SessionStart(source=compact) → PostCompact. 모두 불린다. 이후 turn 도 같은 session_id.
처리: `lib/compact_epoch.py`(회차 상태·`state_path`), `hooks/rearm-on-compact.py`(SessionStart matcher `compact` 에서 회차 +1), settings.json 에 등록, MANIFEST 에 두 파일 추가, bypass·structure 훅의 상태 키를 (session_id, 회차) 로 변경. 사용법은 HOOK-MESSAGES.md.
한계: 자동 compact 가 같은 이벤트를 내는지는 직접 확인하지 못했다(수동 /compact 만). 회차가 오르면 structure-reminder 성장 기준점도 새로 잡힌다.

## 6. 같은 규약을 적용해야 할 다른 훅(고치지 않음)
- coderag 플러그인의 hooks (`/code/Projects/coderag` 쪽 hooks/)
- luau-kb 의 훅(있다면 `luau-kb/hooks/`)
- 세션 기록 플러그인(`plugins/session-log/`) — 규약 문서와 `compact_epoch.py` 사용
- 사용자 레벨에 현재 설치된 옛 `~/.claude/hooks/*`(한국어 판)는 `tools/home-sync.sh apply` 로 정본이 반영될 때까지 그대로이고, 새 settings.json 의 SessionStart compact 훅도 apply 후에 켜진다.

## 7. 긴급도 level 도입과 재실측 (2026-11-10)
사용자 지적: "참고 정보"로만 두면 모델이 별 생각 없이 넘긴다. 사용자 지시는 아니되 반드시 검토하게 하고 긴급도를 달자. 규약: `HOOK-MESSAGES.md` "긴급도 level". 태그는 `<harness-hook name="…" level="info|warn|action">`, CLAUDE.md "훅 메시지"는 위상(사용자가 설치한 상시 규약, 반드시 읽고 따르거나 이유를 밝힘)과 level 뜻 3줄.

배정: heavy-proc-guard deny=action / bash-bypass 셸 쓰기·rules 안내=warn, 인터프리터=info / structure 1,500 초과=action, 800 초과·성장·잘못된 예외=warn, 유효한 예외 사유·접두 묶음=info / rearm-on-compact 출력 없음. 한 태그에 여럿이면 최고 level.
테스트: structure 72/72(level 검사 3건 추가), compact 18/18(level 검사 2건 추가).

재실측(sonnet, 같은 과제·같은 저장소 모양, 각 2회; 새 문구는 `/tmp/lvx/effect`, 임시 키 `-tmp-lvx-effect-*`):
| 항목 | 전 | 후 |
|---|---|---|
| (a) 다룸 | 6/6 | 6/6 |
| (b) warn 에서 응답 한 줄 언급(structure warn 2 + bypass 2) | structure 2/2, bypass 1/2 | 4/4 (모두 훅 출처 명시, bypass 는 rules 를 읽은 뒤 고침) |
| (c) action 에서 진행 전 처리(1,500 초과 2회) | 0/2 질문. "원하시면 분리안을 만들어 드리겠다"고 끝냄 | 2/2. 추가 편집을 멈추고 분리 계획기로 구체적 분리안을 만들어 "진행할까요?"로 질문 |
| (d) 혼동·과잉 | 없음 | 사용자 지시로 오인 0/6. 작업을 멈춘 info 없음. 단 읽기 전용 계획기를 python3 로 돌려 뜬 info 를 2/2 회 최종 보고에 굳이 언급(소음) |
한계: 각 2회, 훅이 PostToolUse 라 action 은 "편집 뒤, 다음 행동 전"에 처리됨(편집 자체는 막지 않음).
