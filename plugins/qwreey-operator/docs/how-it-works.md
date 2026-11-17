# qwreey-operator 동작 상세

플러그인은 두 가지로 이루어진다: 메인 세션에 넣는 규약(`context/ambient.md`, 서브에이전트에는 모델 줄과 끝맺음 줄을 담은 `context/subagent.md`)과 알림 훅 `delegate-nudge`. 스킬과 에이전트 정의는 없다. 무엇도 막지 않는다.

## 규약 주입
- 훅: `SessionStart`, matcher `startup|resume|clear|compact` → `hooks/ambient.py`. `SubagentStart` → `hooks/ambient.py SubagentStart`.
- `context/ambient.md` 를 `<plugin name="qwreey-operator">…</plugin>` 로 감싸 `additionalContext` 로 낸다. compact 요약 과정에서 규약이 빠질 수 있어 compact 뒤에도 다시 넣는다.
- 태그 끝에 이 세션의 `nonce="…"` 속성을 달고, 같은 이벤트의 규칙 줄을 이 훅이 먼저 맡으면 블록 맨 앞에 싣는다(`hooks/harness_nonce.py`, 규약은 `home/.claude/HOOK-MESSAGES.md` 2번).
- `PreCompact`(manual·auto) → `hooks/ambient.py PreCompact`: 요약기에게 `Omit the <plugin name="qwreey-operator"> block from the summary; it is re-injected after compaction.` 한 줄을 일반 stdout 으로 낸다. compact 뒤에 다시 넣으므로 요약에 남은 사본은 중복이다. 서브에이전트의 compact(`agent_id` 있음)와 규약 파일이 없을 때는 내지 않는다.
- `SessionStart` 는 메인 세션에만 불린다. `SubagentStart` 는 `context/subagent.md`(모델 줄과 끝맺음 줄)만 싣는다. 서브에이전트도 다른 서브에이전트를 띄우므로 모델 규칙은 같이 가야 하고, 넘길 경계·병렬·확인 줄은 메인의 일이라 싣지 않는다. 끝맺음 줄은 자식 에이전트·백그라운드 명령의 결과를 모으고 남은 것을 멈춘 뒤 보고하라는 것이다. 서브에이전트가 "기다리는 중" 으로 끝내면 그 결과를 받을 쪽이 없고, 보고 뒤에 남은 백그라운드 작업은 그 서브에이전트 작업을 끝나지 않은 채로 둔다. 기본 지침(Agent·Bash 도구 설명, 서브에이전트 시스템 프롬프트, SubagentHandback 의 "do everything else first")은 자식과 백그라운드 작업을 거두라고 하지 않는다. fork 는 부모 맥락을 물려받으므로 건너뛴다.
- 파일이 없거나 읽기에 실패하면 아무것도 내지 않는다. 크기는 약 2KB(약 550 토큰).
- `hooks/ambient.py` 은 저장소 `lib/ambient.py` 의 바이트 사본이다(고치지 말고 정본을 고친 뒤 `python3 -I tools/sync-copies.py --apply`). 플러그인마다 다른 것은 `context/ambient.json`(`plugin`, `events`)에 둔다. 끄기 스위치는 없다. SessionStart 훅은 인자 없이 불리므로 이벤트는 입력의 `hook_event_name` 으로 정해진다.

### 규약 다섯 줄의 내용
1. 넘길 경계: 코드 파일 3개 이상, 새 줄 약 150 이상, 다른 코드·문서를 많이 읽는 구현은 백그라운드 서브에이전트(fork 가 아닌 새 에이전트)로. 설계가 정해져 파일이나 구조화된 지시문으로 적힌 뒤에 넘긴다. 설계가 가능한지 판가름하는 프로브는 메인이 사용자와 한다(시험 대상이 메인의 가정이라서). 작은 수정, 방금 내린 결정, 문서·설정, 중간에 사용자 답이 필요한 일도 메인에 둔다.
2. 병렬: 독립된 경계(백엔드·프론트엔드, 별개 모듈)마다 하나씩 동시에. 한 부분이 다른 부분의 결과를 필요로 할 때만 잇는다. 한 부분 안에서는 새 에이전트보다 같은 에이전트를 작은 단계로 이어 쓴다(결과 검토 → 사용자 결정이나 구체적 반례 전달 → SendMessage 로 재개; 읽은 것을 유지하고 캐시는 약 한 시간). 다만 재개할 때마다 그 에이전트의 맥락 전체를 다시 읽으므로, 맥락이 약 20만 토큰을 넘었거나 다음 단계에 읽은 것이 별로 필요 없으면 짧은 지시로 새 에이전트에 넘긴다(완료 알림에 토큰 수가 나온다. 2026-11 delegate 드라이버 작업에서 한 구현자가 53만 토큰까지 자란 일이 계기). 사용자가 동시 상한을 정했거나 언급했으면 따른다. 무엇을, 몇 개, 어떤 모델, 예상 크기를 한 줄로 알린다.
3. 서브에이전트 모델: haiku 는 읽기 전용 조사만, 쓰기·실행·판단·검토·실측은 sonnet 이상(일 크기에 맞게). 수행자는 opus 기본. sonnet 은 가볍고 완전히 정해졌으며 틀려도 싸고 금방 보이는 일에만, 보안·이론이 무거운 코드에는 쓰지 않는다.
4. 지시문에 더할 것: 사용자 원문 인용, 테스트 명령이 든 완료 기준, 바뀐 파일·테스트 출력·미결 질문 보고(모호함을 몰래 정하지 않게). 메인이나 다른 서브에이전트가 그동안 같은 파일을 만질 수 있으면 `isolation: "worktree"` 로 띄운다. 이때 수행자는 자기 worktree 브랜치에 커밋하고, 메인이 그 브랜치를 병합한 뒤 worktree 를 지운다. 그 밖에는 수행자가 커밋하지 않는다.
5. 확인: 다시 하지 않고 확인한다. 수행자의 테스트를 다시 돌리고 보고를 완료 기준과 대조하며, 보고가 모호하거나 테스트가 닿지 않는 곳만 파일을 연다. 크거나 위험한 diff 는 새 리뷰어 서브에이전트에게 보이고, 각 발견은 재현한 뒤에 다룬다. 커밋은 메인이 한다.

### 일부러 넣지 않은 것
Claude Code 의 기본 지침이 이미 다루는 것은 반복하지 않는다: 지시문의 기본 항목(목표, 이미 배제한 것, 읽을 파일), 백그라운드 실행과 완료 알림, SendMessage 사용법, 언제 서브에이전트를 쓰는지에 대한 일반론. 규약은 그 위에 이 하네스가 정한 경계·모델·검증만 더한다.

## 알림 훅 `delegate-nudge`
- 등록: `PostToolUse`(matcher `*`)와 `UserPromptSubmit` → `hooks/delegate-nudge.py`. 모델을 부르지 않는다. 쓰기·Bash·Agent 류가 아닌 도구 호출은 상태 파일도 열지 않고 끝난다.
- 대상: 메인 세션만(입력에 `agent_id` 가 있으면 건너뜀).
- 세는 것:
  - `Edit`·`Write`·`MultiEdit`·`NotebookEdit` 의 대상 경로.
  - Bash 가 쓰는 경로: `>`·`>>` 리다이렉트(헤레독 `cat > f` 포함), `tee`, `sed -i`. 따옴표 안의 `>` 와 헤레독 본문은 보지 않는다. 정규식이라 거칠고 우회될 수 있다.
  - 제외: 확장자 `md json toml yaml yml txt log out csv lock tmp`, 확장자 없는 경로, `/tmp`·`$TMPDIR` 아래, `/dev/`.
- 문턱: 한 턴(사용자 입력 사이)에 코드 쓰기 12회 또는 서로 다른 코드 파일 8개. 넘으면 그 턴에 한 번 알린다.
- 리셋: `UserPromptSubmit`, 그리고 `Agent`·`Task`·`Workflow` 호출. 즉 "서브에이전트를 부른 뒤부터" 다시 센다.
- 이월: 직전 턴이 문턱을 넘었고 그 뒤 Agent 류 호출이 없었으면, 다음 `UserPromptSubmit` 에서 "이어지는 작업이고 구현이 많이 남았으면 넘기기를 고려하라" 는 알림을 한 번 낸다.
- 메시지: 영어, `<harness-hook name="delegate-nudge" level="info" nonce="…">`. 관찰과 권고만 쓰고 따르지 않아도 되는 경우(거의 끝남, 중간에 사용자가 필요함)를 함께 적는다. 규약은 `home/.claude/HOOK-MESSAGES.md`.
- 상태: `$TMPDIR/claude-qwreey-operator/<session_id>.json`(세션당 작은 파일 하나). 턴 단위라 compact 회차는 쓰지 않는다.
- 설정(환경 변수):
  - `HARNESS_OPERATOR_NUDGE=off`(`0`, `no` 도 같음, 옵션 `harness_operator_nudge`): 알림 끔. 환경 변수가 이기고, 없으면 설정 층(사용자 harness.env < 플러그인 옵션 < 저장소 < 저장소 local). 셀 만한 호출(쓰기 도구, Bash, 리셋 도구, UserPromptSubmit)에서만 층을 읽는다.
  - `HARNESS_OPERATOR_NUDGE_WRITES`(기본 12), `HARNESS_OPERATOR_NUDGE_FILES`(기본 8). 1 미만은 1, 숫자가 아니면 기본값.
- 어떤 실패도 조용히 exit 0 한다.

## 끝맺음 훅 `subagent-bg-tasks`
- 등록: `SubagentStop` → `hooks/subagent-bg-tasks.py`. 모델을 부르지 않는다. 메인의 Stop 에는 등록하지 않는다.
- 왜: 끝맺음 줄(`context/subagent.md`)이 있어도 서브에이전트가 자기 백그라운드 셸이나 자식 에이전트를 돌려 둔 채 보고를 마친 일이 있었다(`until ! pgrep -f …` 대기 루프가 3시간 넘게 남음). 보고 뒤에는 그 작업을 거둘 쪽이 없다.
- 대상: 입력의 `background_tasks` 가운데 `status` 가 `running` 이고 `type` 이 `monitor` 가 아니며 `id` 가 자기 `agent_id` 가 아니고, 그 `id` 가 서브에이전트 트랜스크립트(`agent_transcript_path`)의 tool_result 글에 나오는 것. 이 목록은 세션 전체의 것이라 메인이 띄운 셸과 그 서브에이전트 자신도 들어 있고 주인을 밝히는 필드가 없어서다. 서브에이전트가 띄운 셸의 id 는 Bash 결과 `Command running in background with ID: <id>` 에 나온다. 트랜스크립트를 못 읽으면 알리지 않는다. monitor 는 q 의 stale-work 와 같은 이유로 뺀다.
- 쓸모가 있는 곳: 백그라운드(`run_in_background`) 서브에이전트. 포그라운드 서브에이전트의 백그라운드 셸은 Claude Code 가 최종 답에서 끝낸다(Bash 결과에 `it is terminated when you give your final response` 라고 적힌다). 백그라운드 서브에이전트의 셸은 결과가 `You will be notified when it completes` 이고, 서브에이전트가 끝난 뒤에도 메인의 Stop `background_tasks` 에 running 으로 남는다. 포그라운드에서는 알림이 결과를 거둘 기회를 준다.
- 내는 것: `hookSpecificOutput.additionalContext` 에 `<harness-hook name="subagent-bg-tasks" level="warn" nonce="…">`. 작업마다 `- <type> <id>: "<설명 80자까지>"` 한 줄, 그리고 결과를 거두거나 TaskStop 으로 멈추라(지시문이 두라고 했으면 둠), 그다음 최종 보고를 다시 온전히 내라(호출한 쪽은 마지막 메시지만 받는다). 이 출력은 끝나던 서브에이전트에게 새 턴으로 들어가고 메인에게는 가지 않는다. 메인은 다시 낸 보고를 받는다.
- 통과(`home/.claude/HOOK-MESSAGES.md` 의 Stop 규칙): `stop_hook_active`, 마지막 답이 비었거나 오류·한도 알림(`lib/harness_texts.py` 의 `STOP_ERROR` 영역 사본), `agent_id`·`session_id` 없음, 남은 작업 없음, 끄기 스위치, 어떤 실패든(fail-open, exit 0). 마지막 답이 질문이어도 낸다: 서브에이전트의 질문은 보고에 실려 호출한 쪽에 가고 다시 쓰는 보고에도 남는다.
- 한 번: `compact_epoch.state_path("qwreey-operator", "claude-qwreey-operator-subagent-bg", session_id, agent_id)` 파일을 O_EXCL 로 만든 호출만 낸다. 이 플러그인은 자기 회차를 올리지 않으므로 사실상 (세션, 서브에이전트)마다 한 번이다.
- 끄기: `HARNESS_OPERATOR_SUBAGENT_BG=off`(`0`, `no` 도 같음, 옵션 `harness_operator_subagent_bg`). 환경 변수가 이기고, 없으면 설정 층(사용자 harness.env < 플러그인 옵션 < 저장소 < 저장소 local)을 본다. 저장소가 꺼도 되는 스위치라 사용자 전용 키가 아니다.
- 실측(Claude Code 2.1.316, sonnet, `claude -p` 세 번, 합계 약 $0.23):
  - SubagentStop 입력 키: `agent_id`, `agent_transcript_path`, `agent_type`, `background_tasks`, `cwd`, `effort`, `hook_event_name`, `last_assistant_message`, `permission_mode`, `prompt_id`, `session_crons`, `session_id`, `stop_hook_active`, `transcript_path`. 메인 Stop 은 `agent_*` 세 키가 없다.
  - `background_tasks` 항목: 셸은 `{id, type: "shell", status, description, command}`, 서브에이전트는 `{id, type: "subagent", status, description, agent_type}`. 시작 시각, 주인, pid 는 없다.
  - 메인 셸 하나와 서브에이전트 셸 하나가 돌 때 SubagentStop 목록에 둘 다 있었다. 백그라운드 서브에이전트일 때는 그 서브에이전트 자신(`type: "subagent"`)도 있었다.
  - 알림을 받은 서브에이전트는 한 턴 더 돌아 보고를 다시 냈고, 두 번째 SubagentStop 은 `stop_hook_active: true` 로 와서 훅이 통과했다(세 번 모두 정확히 한 번). 지시문이 "시작만 하라" 였을 때는 셸을 멈추지 않고 그 이유를 보고에 적었다.

## 수치의 근거
출처: 저장소의 `.claude/scopes/plugins/qwreey-operator/research/drafts/main-delegate-evidence.md`(메인 세션 5개, 서브에이전트 1,379개 트랜스크립트 실측).
- 100줄당 비용(500~2000줄 구간): 메인 직접 $0.63, opus 서브 $0.60, sonnet 서브 $0.19. 돈은 sonnet 으로 내릴 때만 크게 준다. 100~500줄 구간은 opus 서브 1.36 대 메인 1.62 로 역시 비슷하다.
- 대화: 메인이 직접 코딩하는 턴에는 사용자가 작업 중에 끼어드는 빈도가 시간당 0.77건, 위임 턴은 0.27건이다. 메인이 실행 중이라 의논이 이어지지 않는 것이 실제 불편이다.
- 문턱: 910턴 시뮬레이션에서 쓰기 12회는 턴의 3%에서 울리고 오탐 33%(알린 뒤 남은 작업 중앙 30라운드, $4, 12분), 파일 8개는 7%·37%. 3~8회 같은 낮은 문턱은 오탐이 50% 안팎이고, 줄 수·맥락 크기·테스트 횟수 단독 조건은 편집 수보다 낫지 않았다.
- 경계 3파일·150줄: 코드 편집이 있는 턴의 p75 가 8회·309줄이고, 이 구간부터 서브 단가가 불리하지 않다.

## 플랫폼
훅은 표준 라이브러리만 쓰는 Python 3 이라 OS 와 무관하다(Windows 는 Python 3 설치 필요).

## 테스트
```bash
python3 -I plugins/qwreey-operator/tests/test_delegate_nudge.py
```
합성 stdin 으로 문턱, 턴당 한 번, 리셋, 이월, 제외 경로, 끄기, 규약 주입을 검사한다. `TMPDIR` 을 임시 폴더로 바꿔 돌리므로 실제 상태 파일을 건드리지 않는다.
