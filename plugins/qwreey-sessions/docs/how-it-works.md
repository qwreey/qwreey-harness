# qwreey-sessions 동작 상세

요약 흐름, 외부 저장소 구조, 알림 표, `session-log` 명령, 설정 키는 [session-log.md](session-log.md) 에 있다. 이 문서는 훅이 어디에 걸리고 무엇을 하는지, compact 처리, 플랫폼, 테스트만 다룬다.

## 구성
- 훅 `scripts/hook.py`: 판단만 한다(stat 몇 번, 작은 JSON 몇 개). 요약은 `setsid -f` 로 분리한 워커(`scripts/cli.py flush`)가 하고, 그 워커가 격리된 `claude -p --model haiku` 를 부른다. 항상 exit 0, 세션을 막지 않는다.
- 훅 `scripts/records_read.py`: 세션 기록을 읽을 때 붙는 스냅숏 경고.
- 스킬: `checkpoint`, `import`, `recall`. 상시로 실리는 것은 이 셋의 설명뿐이고 플러그인 규약 주입(ambient)은 없다.
- 명령 `bin/session-log`: 플러그인이 켜지면 PATH 에 오른다. 없으면 `"${CLAUDE_PLUGIN_ROOT}/bin/session-log"`.

## 이벤트별 동작 (`hooks/hooks.json`)
| 이벤트 | matcher | 하는 일 |
|---|---|---|
| SessionStart | 전부 | startup·clear: 직전 다른 세션의 인계(미해결 등), pending 수, 기록 찾는 법 한 줄. resume: 인계 없음(맥락이 복원됨). compact: 이 세션 기록 경로와 pending(새 회차라 다시). 전하지 못한 요약 완료 알림, 최근 요약 실패(warn)도 여기서 |
| UserPromptSubmit | 전부 | 요약 완료 알림 전달, 쿨다운 트리거 검사. 프롬프트가 `/handover`·`/qwreey-sessions:checkpoint`·인계 낱말이면 pending |
| PreToolUse | `Bash\|Skill` | `git … commit` 이면 pending(warn, 막지 않음). handover·checkpoint 스킬이면 pending |
| PostToolUse | 전부 | 요약 완료 알림 전달, 쿨다운 트리거 검사 |
| PostToolUse | `Read\|Grep` | `records_read.py`: 기록을 읽으면 스냅숏 경고, 큰 기록 통째 읽기면 검색 먼저 안내 |
| PreCompact | `manual\|auto` | compact 회차를 올리고, 강제 요약을 띄우고, 회차당 한 번 상기(warn)를 낸다 |
| PostCompact | 전부 | `compact_summary` 를 외부 저장소 `.state/<sid>.compact-<n>.md` 에 남긴다 |
| SessionEnd | 전부 | 강제 요약을 띄운다 |

- 쿨다운 트리거: 마지막 요약에서 `SESSION_LOG_COOLDOWN_MIN`(20분)이 지났고 트랜스크립트가 `SESSION_LOG_GROW_KB`(512KB) 이상 늘었을 때. PreCompact·SessionEnd 는 조건 없이 요약한다.
- 서브에이전트 안에서 불린 훅(입력에 `agent_id`)은 무시한다. 기록과 알림은 메인 세션 것이다.
- `SESSION_LOG_DISABLE`, 비대화형 세션(`CLAUDE_CODE_ENTRYPOINT` 가 `sdk` 로 시작, `SESSION_LOG_RECORD_NONINTERACTIVE` 로 켬), 요약 워커 안(`SESSION_LOG_NESTED=1`)에서는 아무것도 하지 않는다. 단 PreCompact 의 회차 올리기는 이때도 한다.

## 부하
- 자주 도는 경로는 PostToolUse(모든 도구)와 PreToolUse(Bash·Skill)의 짧은 파이썬 실행이다. 모델 호출은 없다.
- `records_read.py` 는 모든 Read·Grep 에서 불리지만 경로를 문자열로 먼저 걸러, 기록 폴더가 아니면 바로 끝난다.
- 요약 비용(haiku)은 세션 길이에 비례하고 세션별 누계는 `session-log status` 의 cost 로 본다. 동시 워커는 `SESSION_LOG_MAX_PARALLEL`(2).

## compact 처리
- "세션당 한 번" 알림의 중복 제거 키는 (session_id, compact 회차, 트리거)다. compact 는 session_id 를 유지하지만 이전 알림을 맥락에서 지우므로 회차가 바뀌면 다시 알린다.
- 회차는 이 플러그인 자기 것(`scripts/compact_epoch.py`, `$TMPDIR/claude-qwreey-sessions-epoch/<sid>`)이고 PreCompact 에서 다른 일보다 먼저 올린다. PreCompact 는 SessionStart(compact)·PostCompact 보다 먼저 불리므로 읽는 쪽은 항상 올라간 값을 본다.
- 메시지 형식과 level 규약: 저장소의 `home/.claude/HOOK-MESSAGES.md`. 문자열은 모두 `scripts/sllib/messages.py`. 태그 끝에 이 세션의 `nonce="…"` 를 달고, SessionStart 에서 규칙 줄을 먼저 맡으면 첫 태그 맨 앞에 싣는다(`scripts/harness_nonce.py`).
- 기록 밖으로 나가는 글(절 요약, 기록 파일, index·pending 설명, 알림 큐, compact 요약, import 사본, 인계)은 쓰는 순간 `sllib/redact.py` 가 nonce 를 지운다: `nonce="<hex>"` 는 `nonce="redacted"`, 규칙 줄은 통째로, 그 세션의 nonce 값 자체도. 세션은 며칠 이어지므로 커밋된 기록의 값이 아직 살아 있을 수 있어서다.

## 플랫폼
- 외부 저장소 잠금에 `fcntl.flock` 을 써서 Windows 에서는 돌지 않는다. Linux·macOS.
- `setsid` 가 없으면 `start_new_session` 으로 분리한다. `python3`(표준 라이브러리만), `claude` CLI, `git`(선택, import 커밋 조회).

## 테스트
```bash
python3 -I plugins/qwreey-sessions/tests/test_session_log.py   # 단위 테스트, 가짜 claude 사용, 비용 0
plugins/qwreey-sessions/tests/e2e.sh [--auto-compact]          # 실제 claude -p 와 haiku 로 훅 전체, 비용 발생
```
