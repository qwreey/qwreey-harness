# P 2라운드 (opus, 2026-11-11). 받은 보고를 옮겼다(줄바꿈만 정리).

## 1. Q 에게 양보한 것
- **예산 8k / 3k.**
  - 5k 로 잡으면 apply 뒤 값(5.06k)과 같다. 그러면 알림이 늘 켜져 있게 된다.
  - 알림은 현재 상태가 아니라 "커지는 것" 에 걸려야 한다.
- **문구는 실린 경로를 따른다.**
  - 실린 곳에 따라 `loads where installed` 와 `loads into every session` 을 나눈다.
- **`loadcost.py` 는 별도 모듈로 둔다.**
  - 기존 훅 파일을 먼저 나누는 단계는 순서에서 뺀다.
- **archive/ 로 옮기지 않는다.**
  - 대신 첫 줄에 `status:` 를 달고 drafts 를 exclude 한다.
- **frontmatter 는 coderag 3문항 시험 뒤로 미룬다.**
- **사용자 고지 축소.**
  - 고지 #4 와 #5 의 사용자 줄은 버린다.
  - advisor 고지는 턴마다 Stop 한 줄로 묶는다.
- **제안만 하는 것.**
  - harness-doctor 이름
  - 라이브 오탐 2건
  - 프로젝트 CLAUDE.md 신설(실측 뒤)

## 2. 남은 반박
- **서브에이전트 배수.**
  - 공식 sub-agents 문서: Explore·Plan 이 아닌 서브에이전트는 CLAUDE.md 를 싣는다.
  - 그래서 실제 비용은 3.4k x (1 + 서브에이전트 수) 다.
  - 문구에 `and every non-Explore subagent` 를 넣는다.
- **역방향 검사.**
  - `if` 핸들러만으로는 스크립트, home-sync, 브랜치 전환으로 생긴 이동을 놓친다.
  - Stop 에서 색인된 경로를 다시 stat 한다. 비용은 1ms 대로 추정하며, 측정이 필요하다.
- **audit 색인은 기본으로 둔다.**
  - 에이전트 프롬프트가 "먼저 읽으라" 고 준 횟수: .claude/audit/06 4회, 01 4회, 05 3회(1.8~1.95만 토큰).

## 3. 최종 입장
### (a) 예산
- 파일당 3k, 합계 8k.
- MEMORY.md: 공식 절단선(200줄 / 25KB)의 80% 에서 알린다.
- 스킬 설명: 1,536자의 90% 에서 알린다.
- 어느 수치도 준수율 근거는 없다.
  - 3.4k 판과 1.9k 판을 각 N회 돌려 위반 수를 비교해야 정해진다.
  - 비싸므로 지금은 증가 알림으로만 쓴다.

### (b) 큰 파일 읽기
- Q 의 주장은 반만 맞다.
  - 기본 Read 는 25k 에서 `PARTIAL view` 로 끊는다.
  - 그러나 v2.1.296 부터 `allow_large: true` 면 전체를 읽는다. 이 환경의 Read 에도 있다.
  - .claude/audit/18 은 88,884B 로 256KB 보다 작아서, 4.4만 토큰을 한 번에 읽을 수 있다.
- 사용자 줄은 버리고, 모델 줄만 둔다.
  - 조건: `.claude/audit/**.md` 를 allow_large 로 읽거나, 누적 20k 를 넘을 때. 색인이 있을 때만 낸다.
  - 문구: `audit/README.md has a one-line summary per audit; read the section you need.`
- 확인 방법: 세션 jsonl 7개에서 audit Read 를 센다($0).

### (c) 설치 어긋남은 사용자 고지로 둔다
- 근거:
  - 설치된 CLAUDE.md 가 이미 없어진 `second-opinion:audit`/`context` 를 부르라고 매 세션 지시한다.
  - `home-sync status` 는 사용자가 돌릴 때만 보인다.
- 언제 낸다:
  - claude-doctor 가 cwd 인 세션에서만, 첫 Stop 에서만 낸다.
  - 어긋남 집합의 해시가 바뀐 때만 낸다.
  - status 가 500ms 를 넘으면 async 로 돌려 다음 Stop 에 낸다.
- 문구: `설치본이 정본보다 뒤처짐: CLAUDE.md, rules 3, 마이그레이션 0005 (tools/home-sync.sh diff)`

### (d) 색인
- `audit/README.md` 를 기본으로 둔다.
  - 한 줄에 번호, 제목, `status: live|superseded by N|history`, 결론이 있는 곳을 적는다.
- 각 파일 첫 줄 `status:` 는 drafts 와 같은 규약으로 한다.
- frontmatter 와 이동은 없다.
- 색인 누락은 `/q:doctor` 가 잡는다.

## 4. 오래 방치된 백그라운드 작업
### 데이터
- Stop·SubagentStop 입력의 `background_tasks`(공식: id, type, status, description, command). 시작 시각은 없다.
- 시작과 진척: `/tmp/claude-<uid>/<slug>/<sid>/tasks/<id>.output` 의 생성 시각, 크기, mtime.
  - 비공식 경로이고 로컬에서만 확인했다.
  - 없으면 상태 파일의 first_seen 으로 대신한다.
- 서브에이전트: `subagents/agent-<id>.jsonl` 의 mtime.
- 선택: `/proc` 의 자손 CPU 증분(추론).

### 문턱
| 대상 | 상태 | 조건 |
|---|---|---|
| 셸 | `idle` | 30분 이상이고 출력이 20분 넘게 그대로 |
| 셸 | `long` | 2시간 이상(출력과 무관) |
| 서브에이전트 | `silent` | transcript 가 `HARNESS_SLOTS_STALE_MIN` 넘게 그대로 |

- 30분과 2시간은 공식 무인 세션의 기본값과 최대값에 맞췄다.
- Monitor 는 뺀다.

### 멈춤과 오래 도는 작업 구분
- 출력이 늘면 실행 중이다. `long` 에서만 알린다.
- 출력이 그대로이고 CPU 증분이 0 이면 `idle (likely waiting on input)` 이다.
- `dev|serve|watch|--watch|tail -f` 꼴이면 서버로 보고 `long` 에서만 알린다.
- 모두 질문 형태로 쓴다.
- 2h48m 사례는 30분에 걸렸을 것이다(추론).

### 전달
- 모델: 다음 UserPromptSubmit 의 additionalContext.
- 사용자: 감지한 Stop 의 systemMessage.
- Stop `decision` 은 쓰지 않는다.

모델 문구:
```
<harness-hook name="stale-tasks" level="warn">Background shell task b7x2 has run 2h48m with no new output for 2h40m: "python3 plugins/q/tests/run.py". If it is not still needed, stop it with TaskStop; if it is intended, tell the user in one line.</harness-hook>
```

사용자 문구:
```
백그라운드 작업이 멈춘 듯함: 셸 1개, 2시간 48분째 출력 없음("python3 …/run.py"). /tasks 에서 확인·중지
```

### 중복 억제
- (task id, 상태)마다 한 번 낸다. 상태는 idle → long → 4h 로만 올라간다.
- 같은 턴에 여러 개면 한 줄로 묶는다.
- 사용자 줄은 세션당 3번까지 낸다.
- 작업이 끝나면 기록을 지운다.

### 훅이 못 보는 것
- 세션이 쉬는 동안. 다음 프롬프트 때에야 알린다.
- 다른 세션의 작업, `nohup &`·`setsid` 로 띄운 것.
- 포그라운드 Bash 안에서 멈춘 것.
- 출력을 계속 내는 무한 루프.
- `background_tasks` 배열이 없는 경우.
- status 값 목록(문서에 없다).

## 5. 받아들일 수 있는 순서
0. 실측($0~0.03):
   - 50커밋 재생
   - audit Read 집계
   - 2h48m 재생
   - systemMessage UI
   - home-sync status 시간
   - 영어판 CLAUDE.md
1. 낡은 진술 고치기
2. drafts exclude, status 줄
3. 추정식 두 벌, doctor 토큰 열
4. InstructionsLoaded, `loadcost.py`(3k/8k, 배수 문구)
5. 역방향(`if` 4개 + Stop stat)
6. advisor 턴 비용 줄
7. stale-tasks
8. `audit/README.md` 색인, status 줄
9. 어긋남 고지(0단계 시간 측정 뒤)
10. 제안만 하는 것:
    - CLAUDE.md 두 절(약 1.5k)
    - 영어판
    - harness-doctor 이름
    - 메모리 인덱스
    - 프로젝트 CLAUDE.md
    - coderag frontmatter
