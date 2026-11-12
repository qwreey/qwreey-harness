# P 1라운드: 모델이 저장소를 읽는 방식에 맞춰 재구성 (opus, 2026-11-11)

메인이 받은 보고를 그대로 옮긴다(줄바꿈 정리만). 숫자는 .claude/audit/28 에서 왔다. 추론은 "(추론)" 으로 표시한다.

## 1. 11개 질문
1. **고정 비용 예산.**
   - non-fork 서브에이전트도 CLAUDE.md 를 싣는다(Explore·Plan 만 뺀다, 공식). 그래서 고정비는 서브에이전트마다 다시 든다.
   - 예산: 사용자 계층 5k, 경고 6k. 현재 4.45k, apply 뒤 5.06k.
   - 목표: 사용자 CLAUDE.md 2.5k, 프로젝트 CLAUDE.md 1.5k, MEMORY 0.8k.
   - 언어는 제안만 한다. home CLAUDE.md 영어판을 `claude -p` 로 한 번 재고(약 $0.03), 줄어드는 폭을 보고 사용자가 고른다.
   - 리뷰어 에이전트는 `omitClaudeMd` 를 검토한다.
2. **보이게 하는 법.**
   - 편집 때: 훅이 추정식으로 보인다.
   - 표: `/q:doctor` 가 추정식으로 내고, `--measure` 를 주면 실측한다(비용 고지).
   - 사용자에게는 예산을 넘는 순간에만 한 줄을 보인다. statusline 은 쓰지 않는다.
   - 상수 2개는 한 모듈에 두고 테스트로 고정한다.
3. **.claude/audit/.**
   - 경로가 곧 id 이므로 옮기지 않는다.
   - `audit/INDEX.md` 를 둔다. 한 줄에 번호, 상태(live, superseded, history), 결론, 지금 정본이 있는 곳을 적는다.
   - 각 파일에 `status:`·`summary:` frontmatter 를 단다.
   - "먼저 읽으라" 에는 INDEX 와 해당 절만 준다.
4. **drafts.**
   - 옮겨짐이 확인된 3개(second-opinion, hooks, session-log)는 사용자 승인 뒤 하나씩 커밋해 `archive/drafts/` 로 `git mv` 한다.
   - 나머지는 HUMAN_TODO 에서 사용자에게 묻는다.
   - 새 초안의 README 첫 줄에는 `status: active|landed:<path>|abandoned` 를 적는다.
5. **역할 분리.**
   - README: 사람용 설치.
   - PLAN: 현재 목표와 열린 결정만 담고 3k 이하로 둔다. 완료된 서술은 `archive/PLAN-2026-11.md` 로 옮긴다.
   - HUMAN_TODO: 한 줄과 링크로 쓰고, 건수는 적지 않는다.
   - TODO.md 는 만들지 않는다. 없는 경로를 읽으라는 프롬프트는 훅이 잡는다.
6. **중복.** 사실마다 정본을 하나만 둔다.
   - 비용 정책: home CLAUDE.md 와 away rationale.
   - advisor 운용: qwreey-advisor README.
   - 마이그레이션: MANIFEST 머리.
   - PLAN §3.8 과 README 는 포인터만 남긴다.
   - 저장소로 옮긴 메모리 2건은 인덱스에서 빼자고 제안한다.
7. **설치 어긋남.**
   - 순서: home-sync diff → 0005 apply → InstructionsLoaded 로그와 `/context` 로 확인.
   - 어긋남은 SessionStart 에서 사용자에게 한 줄로 알린다.
8. **낡은 이름.**
   - 마이그레이션의 rename 목록을 원천으로 삼는다.
   - `/q:doctor` 가 현행 문서에서 찾는다. audit, drafts, handoff, archive 는 뺀다.
   - 일부러 남긴 이름에는 `legacy-name:` 표시를 단다.
   - harness-doctor 제목은 지금 고친다.
9. **위생.**
   - node_modules 는 e9c6bab 에서 처리했다. 히스토리는 다시 쓰지 않는다(14MB, pull 흐름).
   - 말한 범위 밖에서 파일 20개를 넘게 더하거나 지우면 커밋 메시지에 적는다.
   - 빈 `home/.claude/skills/` 는 rmdir 을 제안한다.
10. **자기 위반.**
    - 라이브 오탐 2건은 패턴으로 예외를 둔다.
    - references 17건의 `audit/NN` 꼬리는 frontmatter `sources:` 로 옮긴다.
    - 코드 주석 범주는 재생으로 잰다.
    - conventions-check.py 는 범주 모듈과 진입점으로 나눈다. scan.py 도 나눈다.
    - 임계값은 `.claude/conventions.json` 의 `load_budget`·`entry_tokens` 에 둔다.
11. **coderag.**
    - project 계층이 audit, decisions, handoff, archive 를 색인한다. frontmatter 는 status, summary, supersedes, sources.
    - project 계층이 구현됐는지는 coderag M1 진척을 봐야 한다. 그때까지는 INDEX 가 대신한다.

## 2. 베이스라인 훅
새 훅을 만들지 않고 qwreey-conventions 에 `load` 범주로 넣는다(.claude/audit/26 판결).

**범위**
- CLAUDE.md 계층, @import(깊이 4), paths 없는 rules 와 있는 rules
- MEMORY.md(앞 200줄 / 25KB)
- SKILL.md description(1,536자에서 잘림, disable-model-invocation 은 제외)
- 실제로 실린 집합은 InstructionsLoaded 훅(`load_reason`, `parent_file_path`)의 세션 기록을 쓴다. 기록이 없으면 정적 탐색으로 대신한다.

**문턱(토큰)**

| 대상 | 문턱 | 지금 넘는 것 |
|---|---|---|
| 상시 문서 1개 | 2.5k | |
| 상시 합계 | 5k | |
| 조건부 rule | 1.2k | luau-core 2.6k |
| 스킬 본문 | 2.5k | start 3.5k, comments 3.1k, doctor 3.0k |

넘으면 큰 H2 절 1~2개를 나눌 후보로 알린다.

**문구**
```
~/.claude/CLAUDE.md loads into every session and every non-Explore subagent: ~3.4k tokens (+120 this edit); always-loaded total ~5.1k of 5k budget. Check that lines naming files, commands, counts or versions are still true. Split candidates: "코드 리뷰와 second opinion" (~0.7k). Long knowledge belongs in references or coderag (qwreey-conventions:agent-docs).
```
- 조건부 rule 이면 첫 구절을 `loads when *.py,*.ts... are read: ~1.0k tokens` 로 바꾼다.
- 없는 경로가 있으면 `Missing paths: L12 tools/run_opt.sh.` 를 덧붙인다.

**반대 방향(낡은 경로 알림)**
- 세션을 시작할 때 실린 문서의 백틱 경로, 링크, @import 를 색인한다. 그때 존재하던 경로만 기억한다.
- 알리는 때:
  - PostToolUse(Bash) 에서 `mv`·`git mv`·`rm`·`git rm` 의 인자가 색인에 있을 때
  - Stop 에서 존재 여부를 다시 확인했을 때 사라진 것이 있으면
- 문구:
  ```
  PLAN.md no longer exists; ~/.claude/CLAUDE.md L12 still names it. Fix the line, or tell the user if the doc is read-only here.
  ```
- 알리지 않는 경우: 일반 편집, 처음부터 없던 경로, glob, `<...>`, URL.

**토큰 계산**
- 추정식 `1.72 x Hangul + 0.376 x other` 를 쓴다. 오차는 +-8%, 최대 +-12% 다.
- 값 앞에 `~` 를 붙이고 0.1k 단위로 반올림한다.
- 실측은 `/q:doctor --measure` 에서만 한다.

**소음 예산**
- 파일마다 세션의 첫 편집에서만 전문을 낸다. 그 뒤에는 문턱을 넘거나 누적 +10% 가 됐을 때만 낸다.
- 범주 전체로 전문은 3회까지, 그 뒤는 한 줄로 줄인다(약 25토큰).
- 목표는 세션당 약 400토큰 이하다. 50커밋 재생으로 확인한다.

## 3. 사용자 고지 (systemMessage)
모델이 할 일은 additionalContext 로, 사용자가 정할 일은 systemMessage 로 보낸다. advisor 줄을 빼고 세션당 3줄 이하로 낸다. UI 에서 어떻게 보이는지 한 번 확인한다.

1. **advisor 1회의 비용과 시간**
   - 출처: SubagentStop 의 transcript usage(subagent_ledger.usage_usd)와 timestamp. fork 는 run 줄로 식별한다(추론).
   - 언제: 실행마다.
   - 문구: `advisor 검토 1회: 약 $0.42, 3분 10초, 입력 18만 토큰(캐시 92%), 이번 세션 누적 $1.30`
   - 이유: 사용자가 정량 평가를 요청했다. PLAN §3.8 의 가성비 판단을 갱신하는 데 쓴다.
2. **상시 로드 예산 초과**
   - 언제: 넘는 순간, 세션당 한 번.
   - 문구: `상시 로드 문서가 예산을 넘음: 약 5.6k / 5k 토큰(~/.claude/CLAUDE.md +600), 나눌 후보는 모델에 전달함`
3. **설치본이 정본보다 뒤처짐**
   - 출처: home-sync status. claude-doctor 의 SessionStart 에서, 내용이 바뀌었을 때만.
   - 문구: `설치본이 정본보다 뒤처짐: CLAUDE.md, rules 3개, 마이그레이션 0005, tools/home-sync.sh diff 로 확인`
4. **실린 문서의 복잡성**
   - 출처: InstructionsLoaded 와 추정식. 첫 Stop 에서, 집합이 바뀌었을 때만.
   - 문구: `이 저장소 상시 로드: 약 5.1k 토큰, 파일 4개(CLAUDE.md 3.4k), 조건부 rules 최대 +2.6k`
5. **큰 파일 통째 읽기**
   - 조건: offset 없는 Read 가 20k 토큰을 넘을 때. 세션당 2회까지.
   - 문구: `모델이 .claude/audit/18 전체를 읽음(약 4.4만 토큰): 색인으로 답이 안 됐는지 볼 만함`
   - 모델에게는 따로 INDEX 나 절 단위로 읽으라고 안내한다.

## 4. 목표 구조
```
CLAUDE.md      NEW project entry <=1.5k tok: where each fact lives, read-first = audit/INDEX.md
README.md      human install guide        PLAN.md     current goals + open decisions (<=3k tok)
HUMAN_TODO.md  user actions, one line + link
home/ plugins/ tools/ decisions/ handoff/ intake/   unchanged
audit/         paths unchanged; + INDEX.md; status/summary frontmatter
drafts/        active drafts only, README status line
archive/       landed or abandoned drafts, PLAN snapshots; not read unless asked
```
순서. 각 단계는 커밋 하나이고 revert 할 수 있다.
0. 실측: 50커밋 재생, 영어판 크기, systemMessage UI
1. INDEX 와 frontmatter
2. 프로젝트 CLAUDE.md
3. conventions-check.py 분리
4. load 범주
5. advisor 고지
6. 승인받은 drafts 를 git mv 한다(들어오는 인용을 grep 한 뒤)
7. PLAN 스냅숏과 축약
8. 중복을 포인터로 바꾼다
9. home CLAUDE.md 축약은 제안만 한다

## 5. 다른 저장소로 옮겨 가는 것
- 훅: load 범주와 반대 방향 검사는 qwreey-conventions 에, advisor 비용 고지는 qwreey-advisor 에 넣는다.
- `/q:doctor`: 로드 비용 표, 없는 경로, 낡은 이름, landed 초안, INDEX 누락을 본다.
- 스킬(agent-docs): 무엇이 언제 실리는지, 예산, 나눌 곳, coderag 로 옮기는 기준, 원장 frontmatter 규약을 담는다. luau-kb 와 quad `.claude/base/` 에 쓸 수 있다.
- 저장소별 임계값: `.claude/conventions.json`.
- 이 저장소에만 해당: archive, PLAN 분리, 이름, scan.py, node_modules.

## 6. 실패 지점과 Q 공격
**P 안의 실패 지점**
- 추정식 상수가 토크나이저에 묶여 있다.
- 알림이 피로를 부르면 모델이 무시한다.
- 프로젝트 CLAUDE.md 가 또 하나의 중복이 되고 상시 비용 1.5k 를 더한다.
- INDEX 가 낡을 수 있다.
- InstructionsLoaded 가 AGENTS.md 모드에서 발화하지 않는다.
- 훅이 커진다.

**Q 의 가장 강한 주장**
- 지금 흐름은 돌아간다. 옮기면 수십 건의 인용이 깨지고, 새 stale 이 생긴다.
- 고정비 5k 는 1M 창의 0.5% 다. audit 를 통째로 읽는 일은 가끔이고 프롬프트로 피할 수 있다.

**반박**
- audit 는 옮기지 않는다. 옮기는 것은 승인받은 초안 3개뿐이다.
- 5k 는 서브에이전트마다 다시 든다. 공식 문서도 길이가 준수를 떨어뜨린다고 적는다.
- 최소 변경이 이미 낡은 문장을 만들었다: PLAN, HUMAN_TODO, README 의 겹친 구절, 없는 TODO.md 를 읽으라는 지시 4건.
- .claude/audit/18 을 통째로 한 번 읽으면 4.4만 토큰으로 상시 로드의 약 9배다.
- 사용자가 베이스라인 훅을 명시적으로 요청했다.
