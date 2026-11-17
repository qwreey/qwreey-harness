# qwreey-sessions 동작 상세

요약 흐름, 외부 저장소 구조, 알림 표, `session-log` 명령, 설정 키는 [session-log.md](session-log.md) 에 있다. 이 문서는 훅이 어디에 걸리고 무엇을 하는지, compact 처리, 플랫폼, 테스트만 다룬다.

## 구성
- 훅 `scripts/hook.py`: 판단만 한다(stat 몇 번, 작은 JSON 몇 개). 요약은 `setsid -f` 로 분리한 워커(`scripts/cli.py flush`)가 하고, 그 워커가 격리된 `claude -p --model haiku` 를 부른다. 항상 exit 0, 세션을 막지 않는다.
- 훅 `scripts/records_read.py`: 큰 기록 통째 Read 를 막고(PreToolUse), 세션 기록을 읽으면 스냅숏 경고를 붙인다(PostToolUse).
- 스킬: `checkpoint`, `import`, `recall`. 상시로 실리는 것은 이 셋의 설명뿐이고 플러그인 규약 주입(ambient)은 없다.
- 명령 `bin/session-log`: 플러그인이 켜지면 PATH 에 오른다. 없으면 `"${CLAUDE_PLUGIN_ROOT}/bin/session-log"`.

## 이벤트별 동작 (`hooks/hooks.json`)
| 이벤트 | matcher | 하는 일 |
|---|---|---|
| SessionStart | 전부 | startup·clear: 직전 다른 세션의 인계(미해결 등), pending 수, 기록 찾는 법 한 줄. resume: 인계 없음(맥락이 복원됨). compact: 이 세션 기록 경로, 방금 요약된 구간의 사용자 원문·식별자 목록(아래 compact 처리), pending(새 회차라 다시). 전하지 못한 요약 완료 알림, 최근 요약 실패(warn)도 여기서 |
| UserPromptSubmit | 전부 | 요약 완료 알림 전달, 쿨다운 트리거 검사. 프롬프트가 `/handover`·`/qwreey-sessions:checkpoint`·인계 낱말이면 pending |
| PreToolUse | `Bash\|Skill` | `git … commit` 이면 pending(warn, 막지 않음). handover·checkpoint 스킬이면 pending |
| PreToolUse | `Read` | `records_read.py PreToolUse`: 기록을 offset·limit 없이 Read 하는데 `SESSION_LOG_READ_GATE_KB`(32KiB) 이상이면 deny 하고 부분 읽기를 안내(대상과 문구는 session-log.md 알림 표) |
| PostToolUse | 전부 | 요약 완료 알림 전달, 쿨다운 트리거 검사 |
| PostToolUse | `Read\|Grep` | `records_read.py PostToolUse`(인자 없어도 같다): 세션 기록을 읽으면 스냅숏 경고 |
| PreCompact | `manual\|auto` | compact 회차를 올리고, 강제 요약을 띄우고, 요약기에게 남길 것·뺄 것 두 줄(태그 없는 일반 stdout, compact 마다, `SESSION_LOG_COMPACT_INSTRUCTIONS=off` 로 끔)과 회차당 한 번 상기(warn)를 낸다 |
| PostCompact | 전부 | `compact_summary` 를 외부 저장소 `.state/<sid>.compact-<n>.md` 에 남긴다 |
| SessionEnd | 전부 | 강제 요약을 띄운다 |

- 쿨다운 트리거: 마지막 요약에서 `SESSION_LOG_COOLDOWN_MIN`(20분)이 지났고 트랜스크립트가 `SESSION_LOG_GROW_KB`(512KB) 이상 늘었을 때. PreCompact·SessionEnd 는 조건 없이 요약한다.
- 서브에이전트 안에서 불린 훅(입력에 `agent_id`)은 무시한다. 기록과 알림은 메인 세션 것이다.
- `SESSION_LOG_DISABLE`, 비대화형 세션(`CLAUDE_CODE_ENTRYPOINT` 가 `sdk` 로 시작, `SESSION_LOG_RECORD_NONINTERACTIVE` 로 켬), 요약 워커 안(`SESSION_LOG_NESTED=1`)에서는 아무것도 하지 않는다. 단 PreCompact 의 회차 올리기는 이때도 한다.

## 부하
- 자주 도는 경로는 PostToolUse(모든 도구)와 PreToolUse(Bash·Skill)의 짧은 파이썬 실행이다. 모델 호출은 없다.
- SessionStart(compact) 의 닻은 트랜스크립트를 한 번 바이트로 훑고(경계 줄만 JSON 으로 푼다) 구간만 JSON 으로 푼다. 페이지 캐시에 있는 116MB 트랜스크립트에서 훅 전체가 약 0.14초다.
- `records_read.py` 는 모든 Read·Grep 에서 불리지만 경로를 문자열로 먼저 걸러, 기록 폴더가 아니면 바로 끝난다. 파일 크기(stat)는 기록 경로일 때만 본다. 오류가 나면 막지 않고 통과한다.
- 요약 비용(haiku)은 세션 길이에 비례하고 세션별 누계는 `session-log status` 의 cost 로 본다. 동시 워커는 `SESSION_LOG_MAX_PARALLEL`(2).

## compact 처리
- "세션당 한 번" 알림의 중복 제거 키는 (session_id, compact 회차, 트리거)다. compact 는 session_id 를 유지하지만 이전 알림을 맥락에서 지우므로 회차가 바뀌면 다시 알린다.
- 회차는 이 플러그인 자기 것(`scripts/compact_epoch.py`, `$TMPDIR/claude-qwreey-sessions-epoch/<sid>`)이고 PreCompact 에서 다른 일보다 먼저 올린다. PreCompact 는 SessionStart(compact)·PostCompact 보다 먼저 불리므로 읽는 쪽은 항상 올라간 값을 본다.
- 메시지 형식과 level 규약: 저장소의 `home/.claude/HOOK-MESSAGES.md`. 문자열은 모두 `scripts/sllib/messages.py`. 태그 끝에 이 세션의 `nonce="…"` 를 달고, SessionStart 에서 규칙 줄을 먼저 맡으면 첫 태그 맨 앞에 싣는다(`scripts/harness_nonce.py`).
- compact 뒤 닻(`scripts/sllib/anchors.py`): SessionStart(compact) 가 방금 요약된 구간을 트랜스크립트에서 다시 읽어 기록 가리킴 바로 뒤에 넣는다. CC 요약은 긴 구간에서 오류 문구, 경로, 사용자 원문 같은 정확한 값을 잃기 때문이다. 모델 호출은 없다.
  - 구간: 직전 compact 경계(없으면 파일 처음)부터 이번 경계까지. 훅은 새 경계가 파일에 쓰이기 전에 도는 일이 많아서, 마지막 경계 뒤에 대화(어시스턴트 응답, 사람 발화)가 있으면 그 경계부터 파일 끝을 구간으로 본다. 경계가 원문 그대로 남긴 꼬리(`preservedSegment`)는 시작 경계 것은 넣고, 끝 경계가 이미 쓰였으면 그 꼬리(`preservedMessages`)는 맥락에 남아 있으므로 뺀다. 끝 경계가 아직 없으면 그 꼬리를 알 수 없어 마지막 몇 발화가 CC 가 남긴 원문과 겹칠 수 있다.
  - A 사용자 원문(오래된 것부터, `L<줄>` 표시): 사람이 친 발화, 작업 중 큐에 넣은 프롬프트, 인자 있는 슬래시 명령(`/name args`), `!` 셸 입력, AskUserQuestion 답. 뺌: task-notification, 서브에이전트 보고·다른 세션 메시지(peer), 플러그인이 대신 낸 프롬프트(plugin, 데스크 답 등. 그 안의 id 는 B 에 센다), isMeta, local-command 출력과 caveat, 인자 없는 내장 명령, system-reminder, 중단 표시, 큐 중복(최근 8개 안의 같은 글).
  - 길이: 한 발화는 1,500자까지(앞 2/3 와 뒤 1/3 을 남긴다: 붙여 넣은 글 앞뒤에 요청이 있는 일이 많다). 남는 예산 안에서 모든 발화를 같은 상한으로 고르게 줄이고 짧은 발화는 그대로 둔다. 상한이 120자 아래로 내려가야 하면 오래된 발화부터 빼고 `(+N earlier messages omitted, before L<n>)` 한 줄을 둔다. 새 발화가 지금 하는 일과 열린 요청을 담고, 뺀 발화는 줄 번호로 트랜스크립트에서 찾을 수 있어서다.
  - B 식별자: 바뀐 파일(Edit·Write·MultiEdit·NotebookEdit 경로와 Bash 의 `>`·`>>`·`tee` 대상, 저장소 안 경로를 먼저), 커밋 명령 결과의 해시와 첫 줄(`[branch hash] msg` 와 함께 돌린 `git log --oneline` 의 `hash msg`), 도구 오류 첫 줄(`Exit code N` 이면 마지막 줄을 붙인다), 사용자·어시스턴트 글의 `D<n>`·`audit <n>`·`.claude/...` 경로(많이 나온 것부터, Claude Code 설정 폴더 제외). 메인 세션의 도구 호출만 본다: 서브에이전트가 고친 파일과 만든 커밋은 서브에이전트 트랜스크립트에 있어 빠진다.
  - C 검색 요령 한 줄: CC 요약 끝에 트랜스크립트 경로가 이미 있으므로 경로는 다시 주지 않고, JSONL 줄이 길어 Grep 이 생략하니 `.{0,120}KEYWORD.{0,120}` 같은 묶은 패턴이나 `-o` 를 쓰고 offset/limit 로 Read 하라고만 쓴다.
  - 예산: 출력 전체(규칙 줄, 기록 가리킴, pending 포함) `SESSION_LOG_COMPACT_ANCHORS_CHARS`(8000)자, 최대 9,000자. CC 는 10,000자 넘는 훅 출력을 미리보기로 바꾼다. B 는 몫(파일 16%, 커밋 14%, 오류 12%, id 8%) 안에서 항목 단위로 자르고 남는 것을 A 가 쓴다. 넘치면 닻을 뺀다.
  - 넣기 전에 글마다 자격 증명 마스킹(`extract.mask`), nonce 지우기(`redact.py`), `<`·`>` 무력화를 거친다. 인용된 훅 태그는 데이터로 남는다. 사용자 글은 공백만 한 칸으로 줄이고 그대로 둔다.
  - 실패(트랜스크립트 없음, 깨진 줄, 예외, 4초 초과)하면 닻만 빠지고 나머지는 그대로 나간다. 예외는 외부 저장소 `hook-errors.log` 에 남는다. 끄기 `SESSION_LOG_COMPACT_ANCHORS=off`.
- 기록 밖으로 나가는 글(절 요약, 기록 파일, index·pending 설명, 알림 큐, compact 요약, import 사본, 인계)은 쓰는 순간 `sllib/redact.py` 가 nonce 를 지운다: `nonce="<hex>"` 는 `nonce="redacted"`, 규칙 줄은 통째로, 그 세션의 nonce 값 자체도. 세션은 며칠 이어지므로 커밋된 기록의 값이 아직 살아 있을 수 있어서다.

## 플랫폼
- 외부 저장소 잠금은 `scripts/sllib/file_lock.py`(POSIX `fcntl.flock`, Windows `msvcrt.locking`)다. Linux·macOS·Windows.
- 워커 분리: `setsid -f`, 없으면 `start_new_session`. Windows 는 `DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP`(작업 객체가 허락하면 `CREATE_BREAKAWAY_FROM_JOB` 도)로 띄운다. `python3`(표준 라이브러리만), `claude` CLI, `git`(선택, import 커밋 조회).

## 테스트
```bash
python3 -I plugins/qwreey-sessions/tests/test_session_log.py   # 단위 테스트, 가짜 claude 사용, 비용 0
python3 -I plugins/qwreey-sessions/tests/test_anchors.py       # compact 뒤 닻(합성 트랜스크립트), 비용 0
plugins/qwreey-sessions/tests/e2e.sh [--auto-compact]          # 실제 claude -p 와 haiku 로 훅 전체, 비용 발생
```
