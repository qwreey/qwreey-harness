---
format: 1
title: 코드 품질 검사의 거짓 긍정 전략(초안)
description: H1 문자열 묶음 중복 등 검사 7종의 신호·기준·알려진 거짓 긍정 부류와 줄이는 법. 5개 저장소 묶음 31개 첫 표지(정밀도 약 77%, 바깥 API 어휘가 오탐의 주류)
status: landed in plugins/qwreey-conventions/rules/code-reuse.md
---
# 거짓 긍정 전략

근거: coderag `.claude/audit/47-coderag-code-quality/README.md` §4.2·§4.3(coderag 표본), 그리고 이 초안의 `probe/sets_probe.py` 를 coderag 329c07a, claude-doctor 3f30892, table-sim d39499c, quad 0c2eef35, VideoSync b963897 에 돌린 결과(`raw/<저장소>[.raw|.mirror].txt`, gitignore. 다시 만들기: `python3 -I probe/sets_probe.py /code/Projects/<저장소> [--raw|--mirror] > raw/<저장소>.txt`).

## 1. 원칙
- **새로 생긴 것만 알린다.** 추가한 줄의 새 묶음이 기존 정의와 겹칠 때만. 기존 중복은 Stop 에서 사용자에게 수만. 저장소 전체 훑기 결과(아래 표의 수)는 알림 수의 상한이지 실제 알림 수가 아니다.
- **신호를 겹친다.** 한 신호(원소 겹침)로 판정하지 않고, 정의 여부, 패키지 경계, 타입/런타임, 경로, 표시를 같이 본다.
- **저장소가 스스로 한 말을 믿는다.** `DEFAULT_` 접두, `@copy-of`, `@dup-ok`, `Canonical copy:`, `reuse.vocab_ok`, `reuse.allow`.
- **알림이지 차단이 아니다.** info 한 줄, 파일당 세션에 최대 2번. 알림에 상대 `파일:줄` 과 공유 원소를 넣어 모델이 읽지 않고도 판단하게 한다. 판단 끝이 "다른 지식" 이면 `@dup-ok` 로 다음 알림을 끈다.
- **켜기 전에 잰다.** 그림자 기록, 모델 표지, (검사, 언어)별 80% 관문(`hook-design.md` §9). OK(맞는 중복) 도 정밀도에서 빼는 쪽으로 센다: 모델에게는 소음이기 때문이다.

## 2. 검사별 표

| 검사 | 신호 | 기준 | 알려진 거짓 긍정 부류(어디서) | 줄이는 법 |
|---|---|---|---|---|
| H1 문자열 묶음 중복 | 리터럴 묶음의 원소 겹침 | 공유 3개 이상, 또는 2개 + Jaccard 0.5 | 구두점·연산자 묶음 `['-', '.', ':']`(coderag 2묶음) | 원소마다 글자 1개 이상·길이 2 이상. 대가: coderag .claude/audit/47-coderag-code-quality 이 맞다고 본 비교 연산자 묶음도 빠진다 |
| | | | argv 목록 `["git", "rev-parse", ...]`(claude-doctor 3쌍) | `-` 로 시작하는 원소가 있고 8개 이하면 제외. 원소가 9개 이상인 argv(`scan_settings.py` 의 git status) 는 남는다 |
| | | | 인라인 검사끼리 `if tool in ("Edit", "Write", ...)`(claude-doctor) | 한쪽은 정의여야 함 |
| | | | 같은 파일의 정의와 그 부분집합 인라인(`split-plan.py` STOP, `conventions-check.py` DOC_ENTRY) | 같은 파일은 둘 다 정의, 50줄 이상 |
| | | | 바깥 API 의 고정 어휘: Claude Code 도구 이름, CDP 마우스 이벤트, Roblox TweenInfo 필드, API 토큰 필드(5개 저장소 오탐 7개 중 4개) | `reuse.vocab_ok`, 다른 패키지는 양쪽 정의일 때만(probe 에 없는 조건이라 재지 않음), 알림 문구가 "only look alike" 길을 준다. 남는 가장 큰 부류라 그림자에서 따로 센다 |
| | | | 흔한 낱말 `and`·`of`·`the`, `Bottom`·`Left`·`Right` | 처음 판에는 없음. 그림자에서 많으면 저장소 전체에서 여러 묶음에 나오는 원소(문서 빈도)를 가중치에서 낮춘다 |
| | | | Luau 타입 합집합 ↔ 런타임 목록(table-sim 13쌍, 모두 원소 일치) | Luau 는 알리지 않음(끌어낼 수단이 없다). TS 는 N6 로 "끌어내라" |
| | | | 컴포넌트마다 다른 변형 타입(quad `Filled`·`Tonal`, 19쌍이 원소 다름) | 타입끼리는 원소가 같을 때만 |
| | | | 블록 주석·doc 주석 안의 목록(coderag .claude/audit/47-coderag-code-quality `version.rs` 머리 2쌍, quad `FAB.luau` 머리) | 렉서로 주석 제거(probe 는 줄 단위라 못 거름) |
| | | | 시험·스토리·갤러리·벤더 사본(VideoSync `refs/` 1,300쌍, quad `gallery/` 195쌍) | 경로 제외 |
| | | | 이미 표시한 사본(claude-doctor `memory_signals.py` 두 벌) | `Canonical copy:`·`@copy-of` 짝 제외 |
| | | | 코드 옮기기: B 에 붙인 뒤 A 에서 지움 | 막지 않음. 그림자에서 "상대가 같은 턴에 사라짐" 을 세어 크면 Stop 직전 재확인 |
| C1 `@copy-of` 대조 | 표시, 정본 경로·이름, 두 묶음 | 풀리지 않음, 또는 원소가 다름 | 정본이 다른 저장소인데 그 기계에 없음 | 못 풀면 알리지 않고 기록만 |
| | | | 사본이 정본의 의도된 부분집합 | 표시 문법에 `#NAME` 외 선택지를 두지 않는다. 부분집합이면 사본이 아니라 `@dup-ok` |
| C2 정본 편집 | 색인의 역참조 | 바꾼 정의를 가리키는 사본 1개 이상 | 없음에 가깝다(사람이 단 표시만 본다) | - |
| H2 마법 수 중복 | 5자리 이상 정수, 6자리 이상 16진, `\u{..}` | 2개 파일 이상 | 우연히 같은 수 `2000`(coderag .claude/audit/47-coderag-code-quality, 4자리 기준일 때) | 5자리 이상으로, 시험 제외. 그림자만 |
| H3 비슷한 함수 | 식별자 정규화 6-토큰 shingle Jaccard | 0.4 이상 | 0.22 에서 약 70% 가 오탐, 짝 열거형 변환 `kind_str`·`as_str` | 훅 아님. 요청 시 감사 스크립트로, 0.4 이상만 |
| H4 정책 냄새 const | `const NAME: &[&str]` 3개 이상 | - | 21개 중 15-17개가 형식·명세 불변식 | 훅 아님. `DEFAULT_` 규약과 H1 이 같은 것을 더 정확히 잡는다. 이름 필터(`DIRS\|EXCLUDE\|SKIP\|EXTS\|IGNORE`)를 그림자로만 재 볼 수 있다 |
| H5 문자열 분기 > 8 | `match` 문자열 갈래 수 | 8 초과 | 필드마다 다른 대입(`Meta::from_pairs`), 정규식 탐지의 들여쓰기 오산 | 훅 아님. code-structure 규칙 문장 |
| H6 긴 함수 | 비시험 함수 줄 수 | 이번 편집으로 100줄을 넘음 | 렉서·상태 기계·AST 방문(`comments::extract`, `extract_file`), 하위 명령 분기 | 넘는 순간만, 그림자만. 켜면 structure-reminder 에 |
| H7 바퀴 재발명 | 이름·모양(`parse_*`, `walk`, `glob`, `fnv`) | - | 후보 약 10개, 크레이트로 바꿀 것 0(coderag .claude/audit/47-coderag-code-quality) | 훅 금지. 규칙(`why not <library>:` 한 줄)과 검토. 나중에 기계로 할 수 있는 것은 "그 줄이 있나" 존재 검사까지 |

## 3. 첫 표지 집합(묶음 단위)

`probe/sets_probe.py` 기본(걸러낸) 결과의 모든 묶음. TP 는 알림대로 하면 나아지는 것, OK 는 같은 지식이지만 지금이 맞는 것, FP 는 다른 지식. 한 모델(이 초안 작성자)의 판단이고 §9 확인을 거치지 않았다. 경계로 본 것은 `?`.

| 저장소(언어) | 묶음(공유 원소 예) | 위치 | 표지 |
|---|---|---|---|
| coderag (Rust) | 닫힌 상태 `archived`·`landed`·`rejected` | mdfm `lib.rs:32`, core `coderef.rs:401`, cli `hook.rs:52` | TP |
| | 기록 폴더 `base`·`plan`·`research`·`audit` | mdfm `lib.rs:27`, core `records.rs:88-133` | TP |
| | 메타 키 `status`·`review_after`·`superseded_by` | core `meta.rs:140`, mdfm `meta_line.rs:6`, provider `main.rs:48` | TP |
| | 확장자 `js`·`ts`·`tsx` | `comments.rs:87`(렉서 표), mdfm `refs.rs:63`(참조 대상) | FP(용도가 다름) |
| claude-doctor (Python) | 건너뛸 폴더 `.venv`·`__pycache__`·`build` | 5개 파일 | TP |
| | web 확장자, 생성물 접미사 | `structure-reminder.py:59-60`, `toolkits/web.py`, `structure-scan.py` | TP, TP |
| | 같은 종류 폴더 `assets`·`gallery`·`spec` | `structure-reminder.py:70`, `structure-scan.py:29` | TP |
| | 인터프리터 `deno`·`luau`·`lune` | 5개 파일 | TP |
| | 알림 수준 `info`·`warn`·`action` | `sllib/messages.py:12` 외 2 | TP |
| | 명령 앞 래퍼 `env`·`exec`·`nice` | 4개 파일 | TP |
| | 쓰기 명령 `chmod`·`mv`·`rm` | `wslib.py:17-18`, `auditor-readonly-guard.py` | TP |
| | 도구 이름 `Edit`·`Write`·`MultiEdit` | 5개 파일 | OK(바깥 어휘; 같은 플러그인 q 안의 두 곳은 TP 로 볼 여지) |
| | 도구 이름 `Glob`·`Grep`·`Read` | `extract.py:66`, `workspace_gate.py:30` | OK |
| | 지시 문서 `AGENTS.md`·`CLAUDE.md` | `scan_settings.py:182`(git argv), `scan_stale.py:38` | FP(argv 거르기 실패) |
| | 영어 불용어 `and`·`of`·`the` | `split-plan.py:43`, `:789` | FP |
| | `memory_signals.py` 두 벌 | 정본과 사본 | 제외(표시된 사본, 훅은 알리지 않음) |
| table-sim (Luau) | 같은 타입 두 번 `coin`·`stick`·`back` | `<비공개>`, `Types.luau:82` | TP |
| [비공개 프로젝트 세부 생략]
| quad (Luau, Python) | `native*` 메서드 이름 | `LifetimeHandle.luau:264`, `scripts/doc-coverage.py:32` | TP(스크립트가 코드를 따라가야 함) |
| | 단계 `Begin`·`Move`·`End` 인라인 타입 | devui `Decoration.luau:265`, `Manager.luau:2425` | TP? |
| | 버튼 변형 `Elevated`·`Filled`·`Tonal`(원소 같음) | `Button/Group.luau:110`, `Button/Split.luau:94` | TP |
| | TweenInfo 필드 `Time`·`RepeatCount` | `Tween.luau:81`, `TweenOptions.luau:10` | OK(바깥 어휘, 다른 부분집합) |
| | 문서 절 `overview`·`how-to`·`reference` | `sync-docs.py:40`, `watch-docs.py:15` | TP |
| | 패키지 경로 `quad-base/src` 외 | `error-codes.py:23`, `type-surface-check.py:81` | TP(정책 값) |
| | kit 폴더 `gallery`·`src`·`stories` | `check-kit-surface.py:71`, `publish.py:276` | TP? |
| | 패키지 이름 `quad-error`·`quad-types` | `check-version.py:36`, `publish.py:116-460` | TP(정책 값) |
| | 역할 색 `Primary`·`Secondary` | `FAB.luau:11`(블록 주석 안) | 제외(probe 의 주석 거르기 한계, 훅 렉서는 거른다) |
| VideoSync (TS) | 미디어 이벤트 `play`·`pause`·`seeked` | `adapter/html5.ts:7`, `adapter/types.ts:82`(합집합), `engine.ts:753` | TP(N6: 타입을 목록에서 끌어낼 수 있다) |
| | 사용자 활성화 이벤트 `keydown`·`pointerdown` | `gestures.ts:19`, `panel.ts:225` | TP |
| | 서술자 필드 `hosts`·`identity` | `adoption.ts:198`, `descriptor.ts:35` | TP |
| | CDP 마우스 이벤트 | `harness/browser/probe-*.mjs` | OK(바깥 어휘) |

합계(제외 2개 빼고 30개): TP 23(경계 2 포함), OK 4, FP 3. 정밀도 77%, 경계를 FP 로 치면 70%. 언어별: Rust 3/4, Python 8/12, Luau 2/2(table-sim)·7/8(quad, Python 스크립트 포함), TS 3/4. 걸러내기 전(`--raw`) 묶음 수는 coderag 7, claude-doctor 22, table-sim 10, quad 28, VideoSync 7 이고 걸러낸 뒤 4, 13, 2, 9, 4.

coderag .claude/audit/47-coderag-code-quality 은 coderag 7861ce8 에서 쌍 단위 약 90% 를 쟀다. 그 뒤 coderag 가 C6 의 상태·근거 어휘를 mdfm const 참조로 바꿔(`meta.rs:16-17`) 그 쌍이 사라졌고, 묶음 단위로 세면 이번 값이 된다. 어느 쪽이든 80% 관문 근처라 그림자 먼저가 맞다. TP 가 아닌 7개 중 4개가 바깥 API 어휘다.
