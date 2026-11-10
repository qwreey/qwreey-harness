# 실제 출력 예: table-sim(정리 전) vs stl-luau-doctor(정리 후)

> 두 저장소 모두 luau 툴킷 저장소다. scan.py v1(툴킷 분리 전) 출력이라 8번 `TOOL-PIN`이 D-05 목표값과 비교한다. v2부터는 형제 저장소 핀과의 불일치만 낸다(`toolkits/luau.md#툴체인`). 나머지 코드와 판정 방법은 같다.

## 목차
- [만든 방법](#만든-방법)
- [두 결과 비교](#두-결과-비교)
- [모델 판정 예](#모델-판정-예)
- [table-sim scan 출력 (발췌)](#table-sim-scan-출력-발췌)
- [stl-luau-doctor scan 출력 (발췌)](#stl-luau-doctor-scan-출력-발췌)

## 만든 방법

- 2026-11-10, scan.py v1, `python3 -I scan.py <경로>`로 실행했다. 두 저장소 모두 읽기 전용으로 다뤘다.
  - 실행 전후 `.git/index` mtime이 같은 것을 확인했다.
- table-sim은 다이어트 전 구조다(CLAUDE.md + `@import` 3종).
- stl-luau-doctor는 P3 다이어트 초안이다(`claude-doctor/audit/07-stl-luau-diet.md`, 브랜치 `doctor/diet`).
- 원본 stl-luau는 항목 4만 따로 돌려 GEMINI.md 모순 검출을 확인했다(`--only 4`).

## 두 결과 비교

| 항목 | table-sim (정리 전) | stl-luau-doctor (정리 후) |
|---|---|---|
| 집계 | 오류 0, 경고 19, 정보 7 | 오류 0, 경고 12, 정보 9 |
| 1 상시 로드 | **73,610 B / 618줄**, import 3, 200줄 초과 2, 끝난 절 16,962 B (`LOAD-*` 7건) | **4,592 B / 52줄**, import 0 (0건) |
| 2 rules | rules 없음 | 6개 모두 paths 있음. 대신 conventions와 중복 후보 18줄(`RULE-DUP` 6건) |
| 3 스킬 | quad-ui-dev 604줄, 목차 없는 reference 3개 | 형식 문제 0. delegate-agy 부작용 낌새 1 |
| 4 낡음 | 날짜 기준 서술 4파일, 기준 날짜 2종, 날짜 태그 과다 2 | 0. 원본 stl-luau에서는 `GEMINI.md:24` `STALE-SUPERSEDED` 1건이 잡혔고, 초안에서는 사라졌다 |
| 5 luau-kb | 0 | 표시 23곳, 표시 없는 후보 2파일 |
| 6 복제본 | 훅 이중 등록, 훅 사본이 정본과 다름, quad-ui-dev 사본 표류, typedefs 같음 | delegate-agy가 quad·tbox 사본과 다름 |
| 7 설정 | push deny(정보) | worktrees를 로컬 exclude로만 무시(정보) |
| 8 툴체인 | 0.734 / 1.69.0. "형제와 같은 값" 주석이 거짓 | 0.742 / 1.70.1(D-05 목표와 같음). stylua "tbox/quad와 같은 설정" 주석이 거짓 2곳 |
| 9 worktree | 첫 실행 때 agy가 실행 중인 `table-sim-agy/trial-query`을 `WT-ACTIVE`로 판정했다. 다시 돌렸을 때는 이미 지워져 0건 | `stl-luau-scratch/no-self-return/wt` 정리 후보 1(미병합 커밋 1) |

**해석**
- 다이어트가 겨냥한 항목(1 상시 로드, 4 낡음)은 정리 전에만 나오고 정리 후에는 사라진다. 검사가 구조 차이를 가려낸다.
- 정리 후 쪽에서만 나오는 `RULE-DUP`은 다이어트가 남긴 숙제와 맞아떨어진다. `handoff/stl-luau.md`가 "초안은 아직 두 곳에 중복이 있다"고 적은 바로 그것이다.
  rules를 만든 저장소에서만 의미가 생기는 검사라는 점도 드러난다.
- 6~8번은 다이어트 범위(`.claude` 문서) 밖이다. 그래서 두 저장소 모두 남아 있다. 저장소 고유 문제를 따로 잡는다는 뜻이다.

## 모델 판정 예

scan 결과는 후보다. 원문을 읽고 판정한 예를 든다.

| scan 결과 | 원문 대조 | 판정 |
|---|---|---|
| `RULE-DUP` `src-containers.md:12 ↔ conventions.md:126` (0.94) | 둘 다 "새 균형 방식은 `src/Trees/`에 파일 하나 + `const _balance…`" | **중복**. conventions 쪽 문장을 걷고 '왜'만 남긴다 |
| `RULE-DUP` `docs.md:8 ↔ conventions.md:9` (0.66) | conventions 쪽은 "언어 규칙은 루트 CLAUDE.md '언어'"라는 포인터뿐이다 | **중복 아님** |
| `RULE-DUP` `src-modules.md:17 ↔ conventions.md:31` (0.62) | conventions 쪽에 `At`·`IndexOf`·`CountBelow` 어휘가 더 있다 | **중복이자 누락**. 빠진 어휘를 rule로 옮기는 안도 낸다 |
| `SKILL-SIDEFX` delegate-agy (`setpriv`) | 별도 uid로 agy를 띄우고 worktree를 만든다 | **판단이 갈림**. 사용자에게 묻는다(사용자 전용으로 할지) |
| `TOOL-CLAIM` table-sim `mise.toml:3` | "핀은 형제(quad·tbox·stl-luau)와 같은 값"이라는데 stl은 0.742 / 1.70.1이다 | **참**(`decisions/README.md` 낡은 서술 목록과 같다). 이유 중심으로 다시 쓰는 안을 낸다 |
| `LOAD-TODOS-DONE` table-sim | "된 것" 절 16,962 B | **D-07 질문**. 고치지 않는다 |
| `DRIFT-HOOKDUP` table-sim | 사용자 레벨 heavy-proc-guard가 실제 `~/.claude`에 이미 등록돼 있다 | **고칠 안**: 프로젝트 settings의 hooks 항목을 걷는다(승인 필요). 훅 파일 삭제는 HUMAN_TODO로 |

이 상태에서 stl-luau 계열은 세션이 있다(`SESSION-SIBLING`, 원본 stl-luau에서 pid 19344).
그래서 고칠 안은 모두 `인계`로 분류하고 `handoff/stl-luau.md`에 덧붙인다.

## table-sim scan 출력 (발췌)

```
- 집계: 오류 0, 경고 19, 정보 7
| CLAUDE.md                  | root   |  49 |  3,896 |
| .claude/conventions.md     | import | 202 | 19,965 |
| .claude/project-context.md | import | 107 |  9,171 |
| .claude/todos.md           | import | 260 | 40,578 |
| 합계                        |        | 618 | 73,610 |
경고 LOAD-IMPORT x3, LOAD-OVER200 x2 (conventions 202줄, todos 260줄), LOAD-TOTAL
경고 LOAD-TODOS-DONE  .claude/todos.md  끝난 절 16,962 B. D-07 미결
경고 SKILL-LINES      quad-ui-dev/SKILL.md 604줄
경고 SKILL-TOC        code-recipes.md 357줄 / rules-and-invariants.md 122줄 / v1-migration.md 124줄
경고 STALE-DATED      CLAUDE.md:7 "[2026-10-12 밤 기준] 시제품 단계" (29일) 외 3파일
정보 STALE-MISMATCH   conventions=10-11, project-context=10-12, todos=10-12, CLAUDE=10-12
정보 STALE-DATETAGS   HUMAN_TODO.md 12개, conventions.md 10개
경고 DRIFT-HOOK       .claude/hooks/heavy-proc-guard.py 가 정본과 다름
경고 DRIFT-HOOKDUP    settings.json PreToolUse heavy-proc-guard 를 사용자 레벨도 등록
경고 DRIFT-SKILLCOPY  quad-ui-dev ≠ quad/docs/skills/quad-ui-dev/SKILL.md
정보 DRIFT-TYPEDEFS   typedefs/globalTypes.d.luau = luau-kb 정본
정보 SET-PUSHDENY     Bash(git push:*)
경고 TOOL-CLAIM       mise.toml:3 stl-luau(luau 0.734≠0.742, lsp 1.69.0≠1.70.1); quad(lsp 1.69.0≠1.70.1)
정보 TOOL-PIN         luau=0.734, luau-lsp=1.69.0, stylua=2.5.2 (D-05 목표와 다름)
(첫 실행) 정보 SESSION-SIBLING / WT-ACTIVE  table-sim-agy/trial-query — antigravity 실행 중, 마지막 활동 0.1시간 전
```

## stl-luau-doctor scan 출력 (발췌)

```
- 집계: 오류 0, 경고 12, 정보 9
| CLAUDE.md | root | 52 | 4,592 |   ← 상시 로드는 이것뿐
정보 SESSION-SIBLING  /code/Projects/stl-luau 에 claude(pid 19344)
경고 RULE-DUP x6      docs 1, luau-style 2, src-containers 5, src-modules 4, src-trait 3, tests 3 (줄)
경고 SKILL-SIDEFX     delegate-agy (setpriv)
정보 KB-MARK          luau-kb 후보 표시 23곳 (conventions.md:40, 42, 70 …)
정보 KB-CAND          question.md 6줄, todos.md 4줄
경고 DRIFT-SKILLCOPY  delegate-agy ≠ tbox / quad 사본
정보 DRIFT-DELEGATE   skills/delegate-agy, tools/agy-delegate.sh
정보 SET-WTIGNORE     stl-luau/.git/info/exclude 로만 무시(clone 에는 없음)
경고 TOOL-CLAIM       mise.toml:24, stylua.toml:1 "tbox/quad 와 같은 설정" — tbox 는 Spaces+Input, quad 는 파일 없음
정보 TOOL-CLAIM       mise.toml:1 "quad 구성을 따릅니다" — quad luau 0.734
정보 TOOL-PIN         0.742 / 1.70.1 / 2.5.2 = D-05 목표
경고 WT-CANDIDATE     stl-luau-scratch/no-self-return/wt (proto/no-self-return, 23시간 무활동, 미병합 커밋 1)
(원본 stl-luau --only 4) 경고 STALE-SUPERSEDED GEMINI.md:24 질문 AB 를 확정처럼 적음 ↔ conventions.md:36 "AB 규칙은 뒤집혔다"
```
