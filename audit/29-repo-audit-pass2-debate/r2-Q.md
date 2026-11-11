# Q 2라운드 (opus, 2026-11-11). 받은 보고의 요지를 옮겼다.

## 새 실측: 세션 기록 75개(메인과 서브에이전트), 같은 세션에서 같은 파일을 읽은 누적 Read
- (세션, 파일) 406쌍 중 2만 토큰 이상은 66쌍, 1만 이상은 168쌍이다.
- 2만 이상 66쌍은 **전부 서브에이전트**였다. 메인은 0이다.
  - 이 66쌍은 기록 33개에 걸쳐 있다.
  - 그중 claude-doctor/audit 문서가 14건이다.
- 상위 항목:
  - quad typing-limits: 약 7.7만 토큰, 6번에 나눠 읽었다.
  - coderag tech-design
  - audit/08
- 대부분 지식 채굴처럼 읽으라고 시킨 읽기다.
- 토큰은 추정식으로 셌다. 결과에 붙는 줄번호 앞머리도 포함됐다.

## 1. P 에게 양보한 것
- **서브에이전트 배수.** 공식 sub-agents.md 에 따르면 CLAUDE.md 없이 시작하는 것은 Explore, Plan, 그리고 `omitClaudeMd` 를 단 정의뿐이다.
  - 그래서 예산은 합계 5k, 파일당 2.5k 로 한다.
  - 문구는 `every session and every subagent except Explore/Plan`.
- **reviewer 에 `omitClaudeMd`** 를 제안한다(약 3.4k 절약). 다만 reviewer 에게 사용자 규칙이 필요한지 먼저 본다.
- **역방향은 Stop 에서도 다시 확인한다.** 결과는 Stop 사용자 줄에 범주로 붙인다. additionalContext 로 넣으면 턴이 이어지기 때문이다.
- **`audit/INDEX.md` 를 둔다.** 손으로 쓰지 않고 생성한다.
- **설치 어긋남은 사용자에게 고지한다.** 사용자가 두 번 몰랐던 것이 근거다.
- **초안 3개 `git mv`** 는 승인을 조건으로 받는다.

## 2. 남은 반박
- **frontmatter 를 52개에 일괄로 달지 않는다.** 상태는 INDEX 한 곳에만 둔다.
- **PLAN 은 낡은 문장만 고친다.** 나누는 것은 제안으로만 한다.
- **conventions-check 분리는 별도 리팩터링이다.** 다른 작업의 선행 조건으로 두지 않는다.
- 오탐 2건, `sources:` 표기, harness-doctor 이름은 손댈 때 다루거나 제안만 한다.

## 3. 최종 입장
### (a) 예산
| 항목 | 상한 | 근거 |
|---|---|---|
| 상시 합계 | 5k | |
| 상시 파일 | 2.5k | |
| 조건부 rule | 2.5k | 툴킷 저장소에서는 사실상 매 세션 실린다 |
| 스킬 본문 | 5k | 공식 context-window.md: 압축 뒤 스킬마다 5k 까지만 다시 넣는다 |

- 사용자 줄은 이번 세션의 편집이 합계를 넘겼을 때만 낸다(edge).
- 설정: `load_budget: {total: 5000, file: 2500, rule: 2500, skill_body: 5000}`.

### (b) 큰 파일 읽기
- 실시간 고지는 반대한다. 메인은 0건이고 서브에이전트 기록의 약 44% 에 해당해서 소음이 된다.
- 대신 누적 상위 3개를 advisor 와 서브에이전트 비용 기록, 그리고 doctor 에 남긴다.
- 메인에서 한 파일 누적이 2만을 넘으면 Stop 사용자 줄에 범주로 붙인다.

### (c) 설치 어긋남
- 위치: claude-doctor(`home/MANIFEST` 가 있을 때)의 SessionStart systemMessage.
- 기준: `home-sync status` 결과의 해시.
- 빈도: 해시가 바뀌었을 때, 그리고 그대로면 하루 한 번.

### (d) audit 와 CLAUDE.md
- INDEX 는 둔다. frontmatter 는 미룬다. 초안은 승인 뒤 `git mv` 하고, 그 전에는 status 줄을 단다.
- 프로젝트 CLAUDE.md 는 **0.6k 이하, 영어, 포인터만** 으로 받는다.
  - 근거: "먼저 읽으라" 지시에 CLAUDE.md 가 8회, 없는 TODO.md 가 4회 나왔다.
  - 상한은 원장의 세션당 서브에이전트 수로 정한다.

## 4. 오래 방치된 작업
**위치와 출처**
- q 플러그인 hooks.json 에 둔다. 마이그레이션 없이 모든 저장소로 간다.
- 작업 목록: Stop·SubagentStop 의 `background_tasks`.
- 시작 시각: PostToolUse(Bash run_in_background) 기록이나 원장 Start. 없으면 처음 본 시각.
- 진척: 출력 파일 크기와 mtime, `/proc/<pid>/stat` 의 CPU(추론). 서브에이전트는 transcript mtime.

**판정**
| 판정 | 조건 | 비고 |
|---|---|---|
| 멈춤 | 출력이 15분 늘지 않고 CPU 도 그대로 | |
| 오래 실행 | 진척은 있고 2시간을 넘음 | info 1회 |

- monitor 는 뺀다.
- 문턱은 세션 기록 7개의 지속 시간 분포로 확정한다.

**전달**
- 모델: UserPromptSubmit
- 사용자: Stop

**문구**
- 모델:
  ```
  <harness-hook name="stale-work" level="warn">Background shell task-003 (`python3 -m pytest tests/`) has run 2h48m with no new output and no CPU time for 2h40m; it may be waiting on stdin. If it is not intended, stop it with TaskStop and tell the user; if it is, say so in one line.</harness-hook>
  ```
- 서브에이전트: `Subagent <agent_type> <id> has written nothing to its transcript for 45m.`
- 오래 실행(info): `...has run 2h10m and is still producing output. Confirm it is still wanted.`
- 사용자: `백그라운드 셸 1개가 2시간 48분째 출력 없이 멈춰 있음: python3 -m pytest tests/ (모델에게도 알림)`

**중복 제거**
- (세션, task id, 상태)마다 1회 낸다.
- 다시 진척이 있었다가 또 멈추면 다시 낸다.
- 사용자 줄은 집합이 바뀐 Stop 에서만 낸다.

**보지 못하는 것**
- 세션이 쉬는 동안
- nohup, setsid, &, tmux, docker
- 다른 세션의 작업
- 조용한 dev 서버(그래서 문구를 "멈췄거나 대기 중" 으로 한다)
- 출력 없이 CPU 만 쓰는 루프
- `background_tasks` 가 없는 경우
- 포그라운드 Bash 는 10분 timeout 이 있어 해당하지 않는다.

## 5. 순서
0. 실측
   - 50커밋 재생(load)
   - 영어판 크기
   - systemMessage UI
   - 셸 지속 시간 분포
   - Bash tool_response 필드
   - fork agent_type
   - 세션당 서브에이전트 수
1. 낡은 문장 고치기, `conventions.json`
2. INDEX(생성)
3. 추정식, doctor 토큰 열
4. load 범주, InstructionsLoaded
5. 역방향
6. 오래 방치된 작업
7. advisor 비용
8. 어긋남 고지
9. 프로젝트 CLAUDE.md(0.6k)
10. 제안만 하는 것
    - home CLAUDE.md 두 절
    - omitClaudeMd
    - git mv
    - PLAN 나누기
    - 파일 분리
