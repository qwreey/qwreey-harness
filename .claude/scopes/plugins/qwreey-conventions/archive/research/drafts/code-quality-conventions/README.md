---
format: 1
title: 코드 품질 규약 초안(하드코딩, 중복, 바퀴의 재발명, 단순화)
description: qwreey-conventions 에 넣을 새 rule code-reuse(정책 값 판별, 구현 하나, @copy-of 사본, 라이브러리 이유 줄)와 스킬, 문자열 묶음 중복 훅 reuse-check 설계(그림자 먼저, 80% 관문). 첫 표지 30개 정밀도 약 77%
status: landed in plugins/qwreey-conventions/rules/code-reuse.md
---
# 코드 품질 규약 초안

`plugins/qwreey-conventions` 에 설치했다(rule `code-reuse`, 스킬 `code-reuse`, 훅 `reuse-check`, 문구 토론은 `.claude/scopes/plugins/qwreey-conventions/audit/48-code-reuse-debate/`). 설치된 모양과 다른 부분(rule 본문, 알림 문구, H2·H6 제외, 훅 파일 배치)은 설치본이 맞고, 이 폴더는 근거와 이력이다. 고치지 않는다. 근거는 `.claude/audit/47-coderag-code-quality/README.md`(coderag 의 하드코딩·중복·재발명·단순화, 기계 검사 7종의 정밀도)와 이 폴더의 `probe/`(5개 저장소에서 다시 잰 H1).

사용자: "const ... 로써 하드코딩을 하는 부분이 꽤나 있는데 … 이런 하드코딩도 사실 좋은건 아니라서, 컨벤션 상 훅이나 룰로 무언가 도움이 되는게 생겨야하나 싶은 부분", "바퀴의 재발명, 단순화 실패, 중복성, 하드코딩 이런것에 대한 컨벤션도 생각해볼 부분인것 같아. 이런걸 잡는다 하면 거짓 긍정 같은 상황도 어떻게 줄일 수 있냐 전략이 필요하기도 하고", "규약에 대한 초안을 짜둬도 좋고".

## 파일

| 파일 | 설치 위치 | 내용 |
|---|---|---|
| `rules/code-reuse.md` | `plugins/qwreey-conventions/rules/` | 규칙(영어, 34줄): 정책 값 판별, 구현 하나, `@copy-of`, 라이브러리와 직접 구현, 단순화 |
| `skills/code-reuse/SKILL.md` | `plugins/qwreey-conventions/skills/` | 알림을 받았을 때 순서, 표시 문법, 정책/불변식 표, 라이브러리 고르는 절차, 저장소 설정 |
| `hook-design.md` | (훅 `hooks/reuse-check.py` 의 설계) | 돌리는 검사, 입력, 언어별 추출, 색인과 비용 예산, 판정, 알림 문구 원문, 예외, 턴 끝 보고, 그림자 기록과 관문 |
| `fp-strategy.md` | - | 검사별 신호·기준·거짓 긍정 부류·줄이는 법, 첫 표지 집합 |
| `probe/sets_probe.py` | - | H1 의 간이판. 저장소 전체 묶음과 걸린 시간. `raw/` 는 gitignore |

`rules/`·`skills/` 의 두 파일은 설치될 모양 그대로라 기록 frontmatter(`format`, `title`) 가 없다. coderag 의 기록 lint 가 이 둘에 경고를 내는 것은 그 때문이다.

## 정한 것과 이유

- **새 rule `code-reuse` + 스킬, code-structure 확장 아님.** code-structure 는 길이·폴더·분리 방법이고 짝 훅이 structure-reminder 다. 이 주제는 짝 훅(reuse-check)과 알림 처리 절차가 따로라, rule 을 나눠야 알림이 한 파일을 가리키고 `rules_exclude: ["code-reuse"]` 로 따로 끌 수 있다. 두 rule 의 `paths` 가 같아 주입 비용은 합쳐도 나눠도 같다. 겹침은 옮겨 없앤다: code-structure `## Data` 의 마지막 줄을 아래처럼 바꾼다.
  ```diff
  -- A copied file records its source path, and a check verifies it still matches the source.
  +- Copies, of files or of values, and how they are marked: see code-reuse.
  ```
  문자열 분기 8갈래는 code-structure 에 두고 code-reuse 가 가리키기만 한다. 긴 함수는 지금 어느 규칙에도 없어 code-reuse `## Simplification` 에 한 줄 둔다.
- **훅은 H1(문자열 묶음 중복) 하나와 사본 검사 둘.** audit/47 에서 쓸 만한 정밀도는 H1(약 90%)과 H2(약 75%)뿐이었고, 함수 길이·문자열 분기·재발명은 규칙과 검토의 몫이다. 사본 검사(C1 표시 대조, C2 정본 편집 시 사본 목록)는 사람이 단 표시만 보므로 처음부터 켠다.
- **그림자 먼저.** 5개 저장소 묶음 30개에 이 초안이 표지를 붙여 보니 정밀도 77%(경계를 오탐으로 치면 70%)로 관문 80% 근처다. 남는 오탐의 대부분은 바깥 API 의 고정 어휘(Claude Code 도구 이름, CDP 이벤트, TweenInfo 필드)다. 걸러내기 전과 비교하면 묶음 수가 74개에서 32개로 줄었다(`fp-strategy.md` §3).
- **라이브러리 이유는 표시가 아닌 한 줄 문장 `why not <library>: <reason>`.** H7 은 기계로 잡을 수 없으므로(audit/47: 후보 10개 중 바꿀 것 0) 훅 대상이 아니다. 접두를 고정해 둬서 나중에 존재 검사를 붙일 수 있다.
- **status 는 `active; draft, not installed`.** 기록 규약의 상태 어휘에 `draft` 가 없어서, 같은 폴더의 다른 초안(`drafts/agents/`)처럼 썼다.
- **정책 값 판별 문장은 audit/47 §2.2 의 것을 그대로**(두 프로젝트가 다른 값을 원할 수 있고, 대상 저장소 내용에 대한 판단인가). 생태계 이름이 든 목록은 팩으로, `DEFAULT_` 접두는 덮어쓰기가 있을 때만(coderag 의 `DEFAULT_` const 5개가 모두 실제로 덮어쓰기가 있다).

## 시험 계획

`plugins/qwreey-conventions/tests/test-reuse-check.py`, 지금 시험들과 같은 방식(임시 저장소에 파일을 만들고 PostToolUse JSON 을 stdin 으로, `TMPDIR` 격리).

| 묶음 | 경우 |
|---|---|
| 알림(언어마다) | Rust `const` 두 crate, Python 모듈 상수, Luau 테이블, TS 배열이 다른 파일의 정의와 공유 3개 이상 → N1. 다른 플러그인 루트 → N2 |
| 안 알림 | 구두점 묶음, argv 목록, 인라인끼리, 같은 파일 50줄 안·인라인 부분집합, 시험·stories·gallery·refs 경로, 블록 주석과 doc 주석 안, 생성물 머리, 다시 편집했지만 원소가 같은 묶음, Luau 타입 ↔ 목록 거울, 원소가 다른 타입끼리, `vocab_ok`, `allow` |
| 표시 | `@dup-ok` 사유 있음(조용), 사유 없음·"later"(알림 + N5), `@copy-of` 같음(조용), 원소 다름·경로 없음(N4), 정본 편집(N3), 형제 저장소 경로를 못 풂(조용, 기록만), `Canonical copy:` 짝 |
| TS | 합집합 타입 ↔ 같은 원소 배열 → N6 |
| 도구 입력 | Edit, MultiEdit, Write 새 파일, Write 덮어쓰기(`originalFile`), `structuredPatch` 만 있는 Write |
| 중복 억제 | 같은 (파일, 상대) 두 번째 편집은 조용, 파일당 2번 상한, compact 회차 뒤 다시 |
| 모드 | `REUSE_CHECK=off`, `shadow`(출력 없음, jsonl 한 줄), `on`, `CONVENTIONS_CHECK=off` |
| 턴 끝 | 추가하지 않은 중복이 `중복 N` 으로 남은 주석 보고 한 줄에 합쳐짐, 고치면 사라짐 |
| 예산 | 색인 없는 저장소에서 첫 실행이 300 ms 에서 끊기고 다음 실행이 이어 만듦(시각 주입으로 결정적으로), 5,000 파일 초과 시 패키지 범위 |
| 회귀 표본 | `fp-strategy.md` §3 의 TP·FP 를 최소 재현 파일로 옮긴 경우 10개(예: `memory_signals` 사본, `STOP` 부분집합, 도구 이름, `SKIP_PARTS` 류) |

시간은 단언하지 않고 재서 보고한다(기계마다 다르다). conventions-check 의 렉서를 옮기는 커밋에서는 기존 `test-conventions-check.py` 가 그대로 통과해야 한다.

## 들이는 순서

1. 열린 질문에 답을 받고, 규칙 문구를 토론으로 확정한다.
2. rule `code-reuse` 와 스킬을 먼저 넣고, code-structure 의 사본 줄을 옮긴다(훅 없이도 쓸모가 있다). 플러그인 README 표에 rule·스킬·훅 줄.
3. 옮기기만: conventions-check.py 의 렉서를 `hooks/conv_lex.py` 로(지금 874줄, 경고 기준 초과).
4. `hooks/reuse-check.py` 를 그림자 기본으로 넣고 시험. C1·C2 만 켬. 판 올림, `home-sync.sh` 쪽 변경이 있으면 사용자가 `diff`·`apply`.
5. 그림자 한 주 이상. 표지는 모델(sonnet 이상)이 붙이고 20% 를 다른 맥락 검토자가 다시 붙인다(`hook-design.md` §9).
6. (검사, 언어)별로 기록 30개 이상·80% 이상이면 그 언어를 켠다. 못 미치면 `fp-strategy.md` 의 줄이는 법을 하나씩 더하고 다시 그림자.
7. 켠 뒤 2주에 정밀도와 "알림 뒤 모델이 한 일" 을 다시 보고, 70% 밑이면 그림자로 되돌린다.

## 열린 질문

1. 이름과 자리: 새 rule·스킬 이름 `code-reuse`, 훅 `reuse-check`, 표시 `@copy-of`·`@dup-ok` 로 괜찮은지. 그리고 code-structure 의 사본 줄을 이쪽으로 옮기는 것.
2. 따로 설치되는 패키지 사이의 중복: claude-doctor 에서 맞은 묶음 8개는 대부분 플러그인 경계를 넘는다(공용 lib 를 import 할 수 없음). 이것을 "사본으로 표시하고 대조 시험" 문구(N2)로 알릴지, 같은 패키지 안만 알릴지.
3. Luau 타입 합집합과 런타임 목록이 같은 원소를 두 번 적는 경우(table-sim 13쌍, 지금은 모두 일치): 알리지 않는 것(초안)으로 둘지, "옆에 두라" 고 알릴지, 어긋날 때만 알릴지.
4. 켜는 판단: 모델 두 맥락의 표지 일치와 80% 관문만으로 켤지, 켜기 전에 표본 10개쯤을 직접 보실지.
5. 사본 표시 통일: 파일 사본의 머리 `Canonical copy:`(지금 `tools/tests/test-vendored-copies.py` 가 읽음)와 값 사본의 `@copy-of` 를 하나로 합칠지, 둘 다 둘지(초안은 둘 다 인정).

## 이 초안 밖에 남긴 것

- `.claude/research/README.md` 색인에 이 폴더 줄을 더하는 일(이 폴더 밖이라 건드리지 않았다).
- coderag 쪽 고칠 순서는 audit/47 §3 에 있고 이 초안과 별개다. 규약과 coderag 는 잇지 않는다(PLAN 의 사용자 결정)는 전제라 훅은 coderag 를 부르지 않는다.
