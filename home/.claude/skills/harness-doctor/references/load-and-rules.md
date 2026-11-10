# 1·2. 상시 로드량과 rules 구성

## 목차
- [1. 상시 로드량](#1-상시-로드량)
- [2. rules 구성](#2-rules-구성)
  - [rules 와 conventions 중복](#rules-와-conventions-중복)

## 1. 상시 로드량

**상시 로드되는 것**(scan이 합산함)
- 상위 디렉터리의 CLAUDE.md
- 프로젝트 `CLAUDE.md`, `.claude/CLAUDE.md`, `CLAUDE.local.md`
- 위 파일들의 `@import` 체인(최대 4홉)
- `paths`가 없는 `.claude/rules/*.md`

scan은 파일을 원문 그대로 센다. 블록 HTML 주석은 주입 전에 빠지므로 실제 로드량은 조금 작을 수 있다.

**기준**
- 공식 권장은 파일당 200줄 미만이다.
- 200K 창에서는 파일당 40,000자가 상한이다. 넘친 뒷부분은 잘린다.
- 우리 목표는 프로젝트 CLAUDE.md 80줄 이하, 사용자 레벨 CLAUDE.md 40줄 이하다(`PLAN.md` §1).
- 상시 로드 합계가 20KB를 넘으면 경고한다(`audit/04` §6의 경험 규칙).
- `@import`는 비용을 줄이지 않는다. 가져온 파일이 통째로 같이 로드된다.

| 코드 | 뜻 |
|---|---|
| `LOAD-IMPORT` | CLAUDE.md가 다른 파일을 import한다. 바이트 수를 같이 보여 준다 |
| `LOAD-OVER200` / `LOAD-CHARS` | 상시 로드 파일 하나가 200줄 또는 40,000자를 넘는다 |
| `LOAD-GOAL` | 루트 CLAUDE.md가 우리 목표 줄 수를 넘는다 |
| `LOAD-TOTAL` | 합계가 20KB를 넘는다 |
| `LOAD-TODOS-DONE` | 상시 로드되는 todos에 취소선이나 '된 것' 절이 있다. D-07이 걸려 있다 |
| `LOAD-ANCESTOR`, `LOAD-HOPS` | 상위 CLAUDE.md가 끼어든다 / import가 4홉을 넘는다 |

**모델이 볼 것**: 상시 로드 문서를 절 단위로 분류한다(`audit/03` §2 범례).
- (a) 상시 CLAUDE.md: 정체성, 넘지 않는 선, 빌드·검사 명령, 지금 상태 1줄, 온디맨드 표
- (b) `.claude/rules/*.md` + `paths`: 특정 파일을 다룰 때만 필요한 규칙
- (c) 자동 호출 스킬 / (d) 사용자 호출 스킬: 절차형 내용(핸드오버, 감사 루프, 리뷰 라운드)
- (e) 툴킷 공유 지식 저장소(luau는 luau-kb): 프로젝트와 무관한 언어·툴체인 지식
- (f) archive: 끝난 경위, 정정 서사, 종결된 마일스톤 규약
- 코드에서 얻을 수 있는 내용(디렉터리 트리, 파일 목록, 버전 표)은 지울 후보다.

**고치는 법**
1. `@import` 줄을 온디맨드 표의 행("무엇이 궁금할 때 → 어디를 볼 것")으로 바꾼다. 파일은 그대로 두고 import만 끊는다.
2. conventions는 위 분류대로 rules, 스킬, archive로 나눈다. 선례는 stl-luau-doctor다(`<doctor>/audit/07-stl-luau-diet.md` §2 분류표).
3. 옮기기 전 원문은 `archive/<이름>-<날짜>.md` 스냅숏으로 남긴다. 옮기기는 삭제가 아니다. 다만 내용을 걷어내는 일이라 승인이 필요하다.
4. 전후 수치를 잰다: `wc -lc`, `LC_ALL=C.UTF-8 wc -m`, scan `--only 1`. 사용자에게는 `/context`로 확인해 보라고 권한다.
5. `LOAD-TODOS-DONE`은 D-07이 미결이다. 고치지 말고 묻는다(`staleness-and-kb.md#d-07`).
6. 실행 중인 세션이 있는 저장소의 재구성은 인계 문서로 넘긴다. 사용자가 원하면 별도 worktree와 브랜치(`doctor/<주제>`)에 초안을 만든다.

## 2. rules 구성

**실측된 로드 동작** (2026-11-10, `PLAN.md` §3.5와 `audit/07` §1)
- `paths`가 있는 rule은 맞는 파일을 Read하거나 Write(새 파일)할 때, 또는 Bash로 `cat`할 때 로드된다. 서브에이전트의 Read에서도 로드된다.
- grep만 해서는 로드되지 않는다. 맞지 않는 파일(`mise.toml`, 루트 `README.md`)을 읽어도 로드되지 않는다.
- `paths`가 없는 rule은 매 세션 항상 로드된다. rules로 옮기기만 하고 paths를 안 달면 비용은 그대로다.
- agy·codex에는 rules가 자동으로 실리지 않는다. GEMINI.md나 AGENTS.md에 "고칠 파일에 맞는 rule을 직접 읽으라"고 적어야 한다.

| 코드 | 뜻 |
|---|---|
| `RULE-PARSE` | frontmatter를 읽을 수 없다 |
| `RULE-NOPATHS` | paths가 없다. 상시 로드된다 |
| `RULE-DEADGLOB` | paths glob에 맞는 파일이 하나도 없다. 로드될 일이 없다 |
| `RULE-BIG` | rule 하나가 4.5KB를 넘는다. 맞는 파일을 읽을 때마다 통째로 실린다 |
| `RULE-DUP` | conventions와 비슷한 줄이 있다(유사도 0.6 이상) |

scan은 glob을 `git ls-files`(추적 파일과 무시되지 않은 새 파일) 기준으로 맞춰 본다. 그래서 생성 파일이나 무시된 파일을 겨냥한 glob은 `RULE-DEADGLOB` 오탐일 수 있다.

**고치는 법**
- `RULE-NOPATHS`: 이 규칙이 필요한 파일 범위를 정해 `paths: ["src/**/*.luau"]`, `paths: ["src/**/*.{ts,tsx}"]`처럼 단다.
  정말 모든 세션에 필요한 1~3줄이라면 CLAUDE.md로 옮기는 안을 낸다.
- `RULE-DEADGLOB`: 폴더가 옮겨졌거나 오타인지 `git log --stat`로 확인한 뒤 glob을 고친다.
  앞으로 생길 폴더를 겨냥한 것이면 그대로 두고 보고만 한다.
- `RULE-BIG`: 명령형 한 줄과 근거 링크 하나 꼴로 줄인다. 근거 서술은 conventions의 '왜'나 스킬 reference로 보낸다.

### rules 와 conventions 중복

사용자 결정(2026-11-10): **규칙의 정본은 rules 하나다.** conventions는 rule 줄이 가리키는 '왜'(근거, 실측, 경위 링크)만 담고 작게 유지한다.

판정 방법
- scan이 짝지은 두 줄(`rule:줄 ↔ conventions:줄`)을 나란히 읽는다.
- 같은 명령(하라/하지 말라)을 두 번 적었으면 중복이다.
- 근거 설명이나 예시만 겹치면 중복이 아니다.
- 유사도 0.6 미만이라 scan이 놓친 중복도 있다. 같은 rule 파일의 나머지 줄을 conventions 해당 절과 대조한다.

고치는 법
- conventions 쪽 명령 문장을 걷는다. 그 자리에는 '왜'와 근거 링크만 남긴다.
- rule 줄 끝의 근거 표기("— conventions '절 이름'")가 여전히 그 절을 가리키는지 확인한다. 절 제목은 유지한다.
- conventions에만 있고 rules에 없는 규칙이 나오면 rules로 옮기는 안을 함께 낸다.
- stl-luau는 이 작업을 그 저장소 세션이 하기로 했다(`<doctor>/handoff/stl-luau.md`). 직접 고치지 않는다.
