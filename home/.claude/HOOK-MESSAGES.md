# 훅 메시지 규약 (모델에게 들어가는 텍스트)

MANIFEST 대상 아님. 근거 실측: `audit/17-hook-messages.md`. 세션 기록 플러그인 등 새 훅도 이 규약을 따른다.

## 규칙
1. **영어, 짧게.** 모델이 읽고 행동을 바꾸는 텍스트(additionalContext, deny 사유)는 영어. 문서·주석·사용자 대상 안내는 한국어.
2. **감싼다.** 본문 전체를 `<harness-hook name="<훅 이름>" level="<info|warn|action>">\n…\n</harness-hook>` 한 덩어리로 감싼다. `[hook-name]` 접두는 쓰지 않는다.
   - 실측: 하네스는 additionalContext 를 `<system-reminder>` 로 감싸지 **않고**(트랜스크립트 `rendered` 에만 있음), `PreToolUse:Bash hook additional context: ` 접두만 붙여 system 위치로 넣는다. SessionStart·UserPromptSubmit 은 사용자 턴 안에 일반 텍스트로 붙는다. 그래서 우리 태그가 필요하다.
3. **배경 설명(위상과 level 뜻, 3줄 이내)의 출처는 q 플러그인 주입이다**(`plugins/q/context/ambient.md`, SessionStart·SubagentStart 훅이 `<plugin name="q">` 로 감싸 영어 그대로 싣는다. 사용자 CLAUDE.md 에는 없다). 위상(사용자가 설치한 상시 규약, 반드시 다룸)과 level 뜻이 거기 있다. q 를 끄면 이 배경도 같이 빠진다. 태그 안에서 반복하지 않는다. 끄기: `HARNESS_Q_AMBIENT=off`. 세션 중간에 q 를 켠 경우는 UserPromptSubmit 이 (세션, compact 회차)당 한 번 보충하고, 중간에 끄면 이미 실린 맥락은 남는다(한계).
4. 본문은 지시가 아니라 **관찰 + 권고**로 쓴다(무엇이 일어났는지, 왜 중요한지, 할 일). 의미 없는 인사·반복 금지.
5. **deny 사유** (`permissionDecisionReason`)도 같은 태그로 감싼 영어. 모델에게는 `<error>PreToolUse:Bash hook error: …</error>` 도구 결과로 들어간다.
6. PreToolUse/PostToolUse 의 **일반 stdout 은 모델에게 가지 않는다**(실측). 모델에게 보일 말은 JSON `additionalContext` 로 낸다.

## 긴급도 level
참고 정보로만 보이면 모델이 흘려 넘기므로, 모든 훅 메시지는 `level` 로 얼마나 다뤄야 하는지 밝힌다. 사용자 지시는 아니되 반드시 검토한다.

| level | 모델이 할 일 | 배정 기준 |
|---|---|---|
| `info` | 판단에 반영. 언급 불필요 | 지금 행동을 바꿀 필요는 없는 사실·맥락. 예: 유효한 예외 사유 안내, 폴더 묶기 제안 |
| `warn` | 다음 행동 전에 다룬다. 응답에 한 줄로 언급(따랐는지, 안 따른 이유) | 따르지 않으면 규약을 놓칠 가능성이 있고 되돌릴 수 있는 일. 예: 800줄 초과, 셸 우회 쓰기, 해당 rules 미열람 |
| `action` | 진행 전에 반드시 처리. 사용자 확인이 필요하면 묻고 기다린다 | 건너뛰면 해를 끼치거나 되돌리기 어려운 일, 사용자 결정이 필요한 일. 예: 1,500줄 초과 파일에 기능 추가 전 분리안 질문 |

- 한 태그에 알림이 여럿이면 가장 높은 level 을 단다(info < warn < action). 본문이 어느 알림이 어떤 level 인지 드러나게 쓴다.
- **deny** 는 하네스가 이미 막으므로 `action`(고정)을 단다. 모델이 재시도 방법을 반드시 따라야 하기 때문이다.
- 모델에게 아무것도 내지 않는 훅(예: `rearm-on-compact`)은 해당 없음.
- 과잉 반응 금지: `info` 때문에 작업을 멈추지 않는다. level 은 하네스가 정하며 모델이 올리거나 내리지 않는다.

### 현재 배정
| 훅 | 알림 | level |
|---|---|---|
| heavy-proc-guard | deny(choom 래핑 요구) | action |
| bash-bypass-reminder | 셸로 파일 변경(sed -i, 리다이렉트 등) | warn |
| | 해당 rules 파일 안내 | warn |
| | 인터프리터로 읽기·수정 | info |
| structure-reminder | 강제 한도(1,500) 초과 | action |
| memory-placement | auto memory 에 저장소 지식으로 보이는 내용을 씀(경로·명령·규약 신호) | warn |
| | 경고 한도(800) 초과, 세션 성장, 잘못된 예외 사유, 폴더 파일 과다 | warn |
| | 유효한 예외 사유 안내, 접두 묶음 제안 | info |
| rearm-on-compact | (출력 없음) | - |
| subagent-slots | away 중 슬롯이 차서 deny(사유 `queue: wait for a running agent to finish, then spawn the next`) | action |
| | away 예산 도달(1단계) → 직렬화 + 재고 리마인더(compact 회차·away 선언마다 한 번) | warn |
| | away 예산 2배(2단계) → 새 Agent·Workflow deny(`halt: …`; 전체 지시는 회차·away 선언마다 한 번, 이후 짧게) | action |
| | attended 큰 팬아웃(동시 4+, opus 이상 2+, Workflow) → 사용자에게 규모 고지(팬아웃 묶음·회차마다 한 번) | warn |
| | away 중 메인 단독 작업: 예산 도달(1단계) → 재고 리마인더(PostToolUse 모든 도구, 회차·away 선언마다 한 번) | warn |
| | away 중 메인 단독 작업: 예산 2배(2단계) → `halt:` 진척 기록 후 대기(같은 경로, 한 번. 강제 중단 없음) | action |
| workspace-gate | (q 플러그인 `scripts/workspace_gate.py`, audit/31) 이 세션의 저장소가 아닌 `HARNESS_WORKSPACE/<X>` 에 쓰기(Edit·Write·MultiEdit·NotebookEdit, 쓰기로 분류된 Bash)를 q:workspace 스킬 로드 전에 시도 → deny(`Load the q:workspace skill (Skill tool), then retry`; 로드 표시는 세션·agent_id·compact 회차 단위). 예외는 통과, `HARNESS_WORKSPACE_GATE=off` 로 끔 | action |
| | 형제 저장소 읽기(Read·Grep·Glob, 그 밖의 Bash) → compact 회차마다 한 번 규칙과 스킬 포인터 | warn |
| qwreey-conventions | (플러그인 `qwreey-conventions`. 예전 user-level `comment-hygiene` 훅을 대체한다. 같은 마이그레이션 0005 apply 에서 옛 훅을 빼고 플러그인을 켠다) 추가한 코드 주석 줄에 작업 이력·키보드로 치지 않는 문자·이스케이프·보이지 않는 문자·언어 불일치가 있거나, 모델용 문서 줄에 이력 표지가 있음. 파일·범주별 줄 번호와 글자·대체를 한 줄로(파일마다 범주당 회차당 한 번) | info |
| qwreey-advisor | (플러그인 `qwreey-advisor`, 옛 이름 second-opinion) 임계 이상 커밋·같은 실패 2회·high 등급 계획 검토 알림. 이름이 바뀌어도 상태 경로(`claude-second-opinion`)는 기존 기록과 이어지게 그대로 둔다 | warn |
|   (이중 구조) | 메인의 말 고지는 CLAUDE.md 가 2개부터, 훅 warn 은 4개부터다. 의도된 설계: 훅은 메인이 고지를 놓쳤을 때의 보강이라 일부러 더 늦게 울린다(둘 다 2면 warn 이 잦아 무뎌진다). `audit/21` §5-3 | - |
| | away 중 허용된 Workflow(내부 동시성은 슬롯 밖) | warn |

### 권장 배정: 세션 기록 플러그인(`plugins/q/` 의 session-log 훅)과 이후 새 훅
- pending(요약 안 된 세션) 알림: `warn`
- pending 개수나 경과 기간이 임계를 넘으면: `action`
- 요약 완료 알림: `info`
- 구현은 이 문서의 표를 따른다. 훅 코드 예: `hooks/structure-reminder.py` 의 `Note`·`top_level`.

## dedup 단위 = session_id + 호출한 쪽(agent_id 또는 main) + compact 회차
"세션당 한 번" 알림은 session_id 만 키로 쓰면 안 된다. `/compact` 는 session_id 를 유지하는데 요약 과정에서 이전 알림이 맥락에서 사라진다(실측).
- 공용 함수: `~/.claude/lib/compact_epoch.py` (정본 `home/.claude/lib/compact_epoch.py`)
  - `state_path(namespace, session_id, agent_id=None)` → `$TMPDIR/<namespace>/<sid>.c<회차>[.a<agent_id>].json`. 디렉터리도 만든다.
  - 서브에이전트 안의 훅도 부모의 session_id 를 받는다. 입력의 `agent_id` 를 꼭 넘겨야 서브에이전트가 메인의 "한 번" 알림을 쓰지 않는다(`audit/21` §5-6).
  - `epoch(session_id)`, `bump(session_id)`.
- 회차는 `hooks/rearm-on-compact.py` 가 SessionStart(matcher `compact`)에서 올린다(settings.json 에 등록됨). 실측: compact 때 PreCompact → SessionStart(source=compact) → PostCompact 가 모두 불리고 session_id 는 같다.
- 사용(경로로 모듈 적재, harness_env 와 같은 방식):
  ```python
  spec = importlib.util.spec_from_file_location("compact_epoch", home / "lib" / "compact_epoch.py")
  ce = importlib.util.module_from_spec(spec); spec.loader.exec_module(ce)
  state_file = ce.state_path("claude-my-hook", data["session_id"], data.get("agent_id"))
  ```
  구현 예: `hooks/bash-bypass-reminder.py` 의 `dedup_path`. lib 가 없으면 session_id 키로 되돌아간다.
- 테스트: `hooks/tests/test-compact-rearm.py`.
- 참고: 회차가 오르면 structure-reminder 의 "이번 세션 성장" 기준점도 새로 잡힌다.
