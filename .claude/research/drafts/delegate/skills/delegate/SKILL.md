---
name: delegate
description: 다른 모델 계열(Gemini 3.8 Flash `agy`, OpenAI `codex` gpt-6-luna)에게 좁은 질문 하나를 격리해서 맡긴다. 근본 원인 찾기, 지금 틀에서 튀어오르는 검토, 같은 메커니즘의 발견 묶기, 이름의 객관성 검토, 범위를 정한 버그 사냥에 쓴다. 저장소마다 정한 무권한 uid와 worktree에서 돌리고, 결과는 메인이 전부 검증한 뒤에만 반영한다. 리뷰 라운드나 전수 감사에는 쓰지 않는다.
argument-hint: "<agy|codex> <이름> <프롬프트 파일> [--mode worktree|empty] [--ref 커밋]"
---

# delegate — 다른 모델 계열에게 좁은 질문 맡기기

스크립트는 `${CLAUDE_SKILL_DIR}/scripts/delegate.sh`이다. 아래에서는 `D=<그 경로>`로 줄여 쓴다. uid 표는 `registry.tsv`이고, 과제 틀은 `templates/tasks.md`이다.

## 왜, 언제

sonnet과 opus는 같은 베이스에서 증류된 계열이라 어휘와 선택 편향을 공유한다. "외부자 시선"을 지정해도 모델 단위의 경향은 좁혀지지 않는다.

다른 계열의 성향
- **Gemini**: 틀 밖으로 튀어 근본 원인을 짚는 일이 많았다. quad에서 nil 구멍 대거 발견, Context 설계, `q.Out` 부재 지적이 그 예다. 대신 추론 오류, 지어낸 말, 조작 실수가 훨씬 잦다. 어조가 단정적이고, 처방이 성능을 보지 않는다.
- **codex(luna)**: 맥락을 프롬프트에 다 담은 객관 평가(이름)에 싸고 빠르다.

**쓴다**
- 근본 원인
- 틀 밖 의견
- 발견 묶기
- 이름 객관성(세 계열 대조)
- 메커니즘 하나로 범위를 정한 버그 사냥

**쓰지 않는다**
- 리뷰 라운드, 전수 감사, 전수 대조표. 이것들은 Claude 감사자(`/audit`)나 게이트의 몫이다. 2026-11-04 사용자: *"다른 시선 제공자일 뿐 전체 감사에 쓰는 목적은 아니라서"*.
  - 예외는 사용자가 직접 요청한 외부 감사다. 예: quad `external-review-entry.md`.
- 결정을 맡기는 것
- 메인 저장소에 그대로 반영하는 것
- 결정 이력이 필요한 판정을 맥락 없이 맡기는 것

**띄우기 전에** 무엇을 물을지 사용자에게 한 줄로 보인다.

## 비용과 동시 실행

- 기본 상한은 **백엔드마다 한 번에 하나**이고, 모든 저장소를 합쳐 센다(`DELEGATE_MAX_CONCURRENT=1`).
  - 2026-10-20 사용자: *"제미니 하나씩 올려줘. 겹치는거 나오면 토큰 아까워서"*.
  - 사용자가 넉넉하다고 하면 그때 넓힌다. 겹치는 과제 둘로 나누지 말고 한 과제에 우선순위를 적는다.
- agy 모델은 `gemini-3.8-flash-high`만 쓴다. pro는 없는 것으로 친다(사용자 2026-10-02).
- codex는 ChatGPT Plus 구독 쿼터라 작다. 사용량은 사용자가 확인한다. 모델은 `gpt-6-luna`, `--effort medium`.
- 시간 상한은 `--timeout`, 기본 3600초다. Bash `run_in_background`로 돌리고, 끝나면 알림을 받는다.

## 실행

1. **과제를 쓴다.** `templates/tasks.md`에서 틀을 골라 스크래치에 채운다. 머리말(작업 환경 규칙)은 스크립트가 붙인다. 머리말에 들어가는 것:
   - worktree 밖 쓰기 금지
   - git 변경 명령 금지
   - ulimit와 exit code 판정
   - 실측/추정 구분
   - 기준 커밋 직접 확인
   - 제안은 결정이 아님

   과제에는 다음을 넣는다.
   - **읽을 정본을 경로로 준다.**
   - **어디서 튀어오르길 원하는지 적는다.**
   - **반증 가능한 근거(파일:줄, 실행 출력)를 요구한다.**
   - 틀을 깨고 싶으면 앞선 리뷰의 분류표를 주지 않는다. 주면 그 분류에 고정된다(stl-luau 첫 과제의 교훈).
2. **띄운다.** worktree는 **커밋된** `--ref`(기본 HEAD)에서 뜬다. 과제가 볼 변경은 먼저 커밋한다.
   ```bash
   $D run agy  <이름> <프롬프트> [--ref <커밋>]           # 저장소는 현재 디렉터리로 찾는다(--repo 로 지정 가능)
   $D run codex <이름> <프롬프트> --mode empty           # 맥락을 다 담은 프롬프트. 코드는 `nl -ba`로 줄 번호를 붙여 넣는다
   ```
   - 저장소가 중앙 표에 없으면 거부된다. `$D register <경로>`로 다음 빈 uid를 받는다. 이 일은 사용자에게 알리고 한다.
   - 모드
     - agy는 기본 `worktree`, codex는 기본 `empty`
     - **codex worktree 모드는 거부된다.** 무권한 uid에서 codex 샌드박스(bubblewrap)가 namespace를 못 만들어 셸이 하나도 돌지 않는다(2026-11-10 table-sim 시범, `trial-2026-11-10.md`). 샌드박스를 끄는 `DELEGATE_CODEX_SANDBOX=danger-full-access`는 사용자 결정이다.
     - agy empty 모드는 **미검증**이라 경고가 뜬다. 답은 stdout에서 보고서로 복사된다. 처음 쓸 때 결과를 같이 확인한다.
3. **읽는다.** 끝나면 스크립트가 경로를 찍는다.
   - 보고서
     - agy worktree: `<작업공간>/<이름>/REPORT.md`
     - 그 밖: `.delegate/report.md`
   - `.delegate/guard.txt`: exit, 메인 저장소 변경 여부, worktree HEAD, worktree에서 고친 파일
   - 필요하면 `.delegate/stdout.txt`
4. **검증하고 반영한다** (아래 절).
5. **보존하고 지운다.**
   ```bash
   $D collect agy <이름>     # <작업공간>/runs/<날짜>-<이름>/ 에 prompt·report·guard·stdout·meta·diff.patch
   $D remove  agy <이름>     # worktree 와 과제 HOME 삭제. collect 전이면 거부(버리려면 --discard)
   ```
   - 쓸 만한 보고서는 프로젝트 `.claude/audit/<backend>/<날짜>-<이름>.md`로 옮겨 커밋한다. 이때 머리에 메인 검증 결과를 붙인다(stl-luau `audit/agy/2026-10-02-hunt.md` 꼴). `runs/`는 저장소 밖 보존 기록이라 근거로 인용하지 않는다(→ 명명 규약).
6. **남은 것을 본다.** `$D list --all`, `$D gc --all`(미리보기), `$D gc --all --apply`.
   - gc가 지우는 것: collect된 작업공간, 주인 없는 HOME, 옛 공유 `.home`. 그 작업공간 안에서 도는 프로세스가 있으면 건너뛴다.
   - gc가 건드리지 않는 것: 옛 스크립트 작업공간, 옛 codex 기록, collect 안 한 결과. 이것들은 목록만 보인다.

## 결과를 받아들이는 절차 (검증 후 반영)

1. **모든 주장을 메인이 직접 확인한다.** 첫 과제들에서 실제로 틀린 것:
   - 기준 커밋을 입력 문서에서 옮겨 적음
   - 실측 결과를 거꾸로 인용함
   - 인용 위치가 반대였음
   - 하지 않은 테스트를 "실측"으로 표시함
   - 이미 닫힌 문항을 열린 것으로 셈
   - 코드 들여쓰기를 바꿔 인용함
2. **재현 먼저.** 결함 주장은 메인이 재현 테스트를 먼저 쓴 뒤 고친다. 재현이 안 되면 "외부 주장, 메인 미재현"으로만 남긴다.
3. **처방은 다시 잰다.** 수정안이 맞아도 비용을 보지 않는다. 예: `FromIter` 수정안이 2.1배 느렸음. 핫 경로면 메인이 측정한다.
4. **새 필드·이름·메커니즘·규약은 사용자 문항이다.** 증상만 확실하면 "증상 확정, 처방 미정"으로 둔다. 기존 사용자 인용문 옆에 외부 제안을 붙이지 않는다.
5. **보고할 때 가른다.** "Gemini(또는 codex)가 주장한 것", "메인이 확인한 것", "사용자가 결정할 것"을 섞지 않는다. 원장에는 `/audit`과 같은 확인 칸을 쓴다.
6. worktree에서 고친 파일(`diff.patch`)은 참고용이다. 그대로 적용하지 않는다.

## 격리 — 무엇이 지켜 주나

| 줄 | 장치 | 근거 |
|---|---|---|
| 1 | 저장소마다 다른 무권한 uid로 `setpriv`. worktree, `.git/worktrees/<id>`, 과제 HOME만 그 uid 소유 | `agy --sandbox`와 codex read-only는 cwd 밖 접근을 막지 못했다(quad 2026-10-02/03 실측). `unshare -m`은 권한이 없다 |
| 2 | 메인 작업 트리와 `.git/objects`에 쓰기 불가 → 커밋 불가 → push할 것 없음. pre-push 훅이 한 번 더 막음 | `doctor`가 "uid 는 메인 작업 트리에 못 씀"을 검사 |
| 3 | 환경을 비우고(`env -i`) PATH는 저장소 핀 도구 + `/usr/bin:/bin`(Studio 도구가 있는 `/usr/local/bin` 제외) | table-sim판. `env -i`는 2026-11-10 시범에서 agy·codex 모두 정상. 문제가 생기면 `DELEGATE_KEEP_ENV=1` |
| 4 | `choom -n 1000`: OOM이 나면 claude보다 먼저 죽음 | agy 안의 Bash는 PreToolUse 훅이 못 본다 |
| 5 | 실행 전후 메인 저장소 HEAD와 status 비교 → guard.txt | 메인이나 사용자가 그 사이 작업했으면 CHANGED가 정상이다 |
| 6 | 비밀 파일(`~/.claude/.credentials.json`, `.git-credentials`, `.ssh`)을 그 uid가 못 읽음 | `doctor`가 검사(table-sim 2026-10-12 실측과 같은 항목) |

- 도는 중에 `delegate.sh`를 고쳐도 된다. 스크립트가 자기 사본으로 다시 실행되기 때문이다. 옛 스크립트는 고치면 깨졌다(stl-luau 2026-10-02).
- codex는 bubblewrap이 PATH에 없어 내장판을 쓴다는 경고를 낸다. empty 모드에서는 셸을 쓰지 않으니 무해하다.
- agy HOME에는 인증·설정만 넘긴다(사용자의 다른 agy 대화 기록은 지운다. **미검증** — 인증이 안 통하면 `DELEGATE_AGY_FULL_HOME=1`).
- agy는 프로브를 worktree가 아니라 HOME의 `brain/<대화>/scratch/`에 만든다. guard의 worktree 변경 목록에 안 잡히므로 collect가 `runs/<…>/agy/`에 따로 남긴다.
