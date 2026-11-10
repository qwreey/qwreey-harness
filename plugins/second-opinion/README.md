# second-opinion

정해진 시점에 받는 독립 검토 두 갈래. 근거와 실측은 claude-doctor `audit/18-second-opinion.md` §9·§11·§12.

| 구성 | 이름 | 하는 일 |
|---|---|---|
| 스킬 | `second-opinion:context` | 대화를 이어받은 fork 를 "독립 검토자"로 돌려 세워, 흐름에서 놓친 것·숨은 전제·방금 끝낸 설계의 반례를 묻는다. 전환점마다. 1회 약 $0.5~0.6(30만 토큰 맥락, opus) |
| 스킬 | `second-opinion:audit` | 새 컨텍스트 리뷰어에게 짧은 브리프만 주고 diff·주장을 반증하게 한다. 커밋·완료 전, 같은 실패 2회, 구현 검증. opus 약 $1, sonnet 약 $0.4 |
| 에이전트 | `second-opinion:reviewer` | audit 의 읽기 전용 리뷰어(기본 opus, 호출 때 model 로 낮춘다) |
| 에이전트 | `second-opinion:other-frame` | context 의 선택 경로. `ask-other-frame.py` 가 이 본문을 다른 시스템 프롬프트로 써서 대화 사본을 읽힌다 |
| 훅 | `hooks/second-opinion-nudge.py` | 같은 실패 2회, 임계 이상 커밋(기본 high 40줄·mid 200줄)에서 검토를 권한다. 막지 않는다. 서브에이전트 안에서는 조용하다 |
| 훅 | `hooks/readonly-for-reviewers.py` | 위 두 에이전트에게만 읽기 전용 가드(`auditor-readonly-guard.py`)를 건다 |

advisor 는 평소에 쓰지 않는다. 가격 대비 효용이 diff 기반 리뷰보다 낮다. 선택이며 사용자가 요청할 때만 쓴다.

## 설치

```bash
claude plugin marketplace add /code/Projects/claude-doctor   # claude-doctor-market
claude plugin install second-opinion@claude-doctor-market
```

훅은 설치하는 순간부터 모든 세션에서 돈다(플러그인 훅은 스킬 사용과 무관하게 등록된다).

## 설정 (선택)

훅과 스킬은 claude-doctor 하네스의 `~/.claude/harness.env` 와 `~/.claude/lib/` 를 쓴다(`$CLAUDE_CONFIG_DIR` 가 있으면 그 아래). 없으면 기본값으로 돈다.

| 키 | 기본 | 뜻 |
|---|---|---|
| `HARNESS_REVIEW_TIERS` | 없음 | `저장소=high|mid|low|off` 목록. 저장소 이름은 git common dir 의 부모 이름 |
| `HARNESS_REVIEW_DEFAULT` | `mid` | 목록에 없는 저장소의 등급 |
| `HARNESS_REVIEW_LINES` | `high=40 mid=200 low=0` | done 알림 임계(추가+삭제 줄, 0 = 끔) |
| `HARNESS_REVIEW_FRESH_MIN` | `90` | 이 시간(분) 안에 리뷰어가 끝났으면 다시 알리지 않는다 |
| `HARNESS_REVIEW_STOP` | 빈 값 | `1` 이면 커밋 안 된 큰 diff 로 턴을 끝낼 때도 알린다 |
| `HARNESS_REVIEW_PLAN` | 빈 값 | `deny`·`warn` 이면 high 등급 ExitPlanMode 에서 계획 검토를 요구한다 |

- 하네스 lib 가 없으면 dedup 상태는 `$TMPDIR/claude-second-opinion/` 에 세션 단위로 둔다(compact 회차 구분 없음).
- 원장은 `${XDG_STATE_HOME:-~/.local/state}/claude-second-opinion/ledger.jsonl`.

## 알아 둘 것

- 플러그인 에이전트는 frontmatter 의 `hooks`·`permissionMode`·`mcpServers` 를 무시한다. 그래서 읽기 전용 가드는 에이전트 파일이 아니라 플러그인 `hooks/hooks.json` 의 PreToolUse 에 있고, 입력의 `agent_type` 으로 이 플러그인의 검토자만 고른다.
- fork 는 메인과 같은 모델로만 돈다. 메인이 방금 응답한 직후(캐시가 따뜻할 때) 부른다. 캐시가 식었으면 맥락 전체를 다시 써서 30만 토큰에서 opus 약 $1.5 가 더 든다.
- 리뷰어 보고는 요약하지 않고 그대로 사용자에게 보인다.

## 테스트

```bash
python3 -I tests/test-second-opinion-nudge.py        # 훅 알림(claude-doctor 정본 home/.claude/lib 를 복사해 쓴다)
python3 -I tests/test-readonly-for-reviewers.py      # 검토자 읽기 전용 가드 선택
```
