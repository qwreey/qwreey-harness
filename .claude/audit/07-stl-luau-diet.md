# 07. stl-luau 다이어트 (P3 시범)

- 작업일: 2026-11-10
- 작업 위치: `/code/Projects/stl-luau-doctor` (worktree, 브랜치 `doctor/diet`). 기준 커밋은 `e77fc03` 이다.
- 원본 `/code/Projects/stl-luau`(`split/class-like`)는 건드리지 않았다. 확인 시점의 원본 HEAD도 `e77fc03` 이었다.
- 수정 범위는 `CLAUDE.md`, `GEMINI.md`, `.claude/**` 뿐이다. `src/`, `tests/`, `scripts/` 는 손대지 않았다.
- push, merge, rebase 는 하지 않았다.

## 1. 전후 수치

| | 전 (`e77fc03`) | 후 (`b0a365e`) |
|---|---|---|
| 매 세션 상시 로드 | CLAUDE.md + @import 3개 = **51,152 B / 363줄 / 30,471자** | CLAUDE.md만 = **4,592 B / 52줄 / 2,853자** |
| 스킬 목록 노출 추가분 | delegate-agy 1개 | 새 스킬 4개의 description 합 +1,240 B (handover는 `disable-model-invocation`이라 목록에 없음) |
| 상시 합계 | 약 51.2 KB | 약 5.8 KB (**-89%**) |
| `src/Collections/*.luau` 를 Read한 세션 | 51.2 KB | 5.8 KB + rules 4개 8,550 B = 약 14.4 KB (-72%) |
| `tests/*.luau` 를 Read한 세션 | 51.2 KB | 5.8 KB + rules 2개 2,713 B |
| `.claude/*.md` 를 Read한 세션 | 51.2 KB | 5.8 KB + `docs.md` 1,415 B |

- 측정 방법: `wc -c -l`, 글자수는 `LC_ALL=C.UTF-8 wc -m`
- 사후에 `doc-check.py` 결과는 ERROR 0, WARN 0 이다. 예산 규칙은 새 구조에 맞게 바꿨다(§6).

### rules 로드 검증 (`claude -p … --model haiku`, worktree 에서 실행)

질문은 "X를 Read 한 번 → 다른 도구는 쓰지 말고, 컨텍스트에 보이는 rule 파일 이름과 첫 제목(# 줄)을 인용하라"였다.

| Read 대상 | 기대 | 결과 |
|---|---|---|
| `src/Collections/HashMap.luau` | luau-style, src-modules, src-containers, src-trait | **4개 모두, 제목까지 정확히 인용** |
| `tests/spec.arr.luau` | luau-style, tests | **2개 정확** |
| `.claude/backlog.md` | docs | **docs 1개.** 스킬 목록: classify-container, delegate-agy, doc-audit, neg-spike, review-round (handover는 숨김, 기대대로) |
| 대조군 `mise.toml` | 없음 | **없음** |
| 대조군 `README.md`(루트) | 없음 | **없음** |

## 2. 분류표 (conventions.md 와 project-context.md)

| 원래 절 | 분류 | 가는 곳 |
|---|---|---|
| conventions 머리말 | 재작성 | "온디맨드 상세·근거" 선언, rules/skills 안내, luau-kb 표시 설명 |
| 언어 | (a) | `CLAUDE.md` "언어" |
| 네이밍 | (b) | `rules/src-modules.md` "이름" 4줄. 상세 표는 conventions에 남김 |
| 데이터와 모듈: BI 전환 | (a)+(b) | `CLAUDE.md` "지금 상태" 1줄과 `rules/src-modules.md` "전환 중" 4줄. conventions는 정한 것 / 어디까지 왔나 / 정하지 않은 것으로 다시 씀 |
| 데이터와 모듈: AB "⭐ 예외 없음" 문단 | (e) | `archive/conventions-2026-11-10.md`(전문 스냅숏). 살아 있는 문서에는 "옛 꼴(아직 안 옮긴 컨테이너)"과 포인터만 남김 |
| 데이터와 모듈: 모듈 패턴, 토큰, 칸, 팬텀, 빌린 참조 | (b) | `rules/src-modules.md` "모듈과 값" |
| 트레이트 | (b) | `rules/src-trait.md` 9줄 ("걷기 전까지의 규칙"이라고 명시) |
| 타입 작성, 문법과 포맷 | (b)+(d) | `rules/luau-style.md`(paths `**/*.luau`) |
| 인자와 값의 규약 | (b)+(d) | `rules/src-modules.md` |
| 컨테이너 | (b)+(d) | `rules/src-containers.md` |
| 에러 | (b)+(d) | `rules/src-modules.md` "에러". raise 줄 단언은 `rules/tests.md` |
| 성능 | (b)+(d) | `rules/src-modules.md` "성능" 2줄 |
| 테스트 (규칙) | (b) | `rules/tests.md` |
| 테스트 (실행 상한) | (a) | `CLAUDE.md` "넘지 않는 선" |
| 테스트 (돌연변이, 음성 대조군 절차) | (c) | `skills/review-round`, `skills/neg-spike` |
| 리뷰 전체 | (c) | `skills/review-round`. agy 줄은 `CLAUDE.md`와 `delegate-agy`. 경위("BD 9라운드…")는 (e) 스냅숏에만 남김 |
| 커밋 | (a) | `CLAUDE.md` "넘지 않는 선" |
| 문서 관리 | (b)+(c) | `rules/docs.md`, `skills/doc-audit`, `skills/handover` |
| project-context: 이게 뭔가, 실행 환경 | (a) | `CLAUDE.md` 정체성과 "명령" 표 |
| project-context: 모듈 구조, 게이트, 모듈 현황 | 온디맨드 | 파일은 그대로 두고 import만 끊음. 모듈 구조의 AB 단언은 BI 상태로 고치고 `Class.luau` 추가 |
| todos | 온디맨드 | import를 끊고 `CLAUDE.md`에 "지금 할 일은 `.claude/todos.md`" 한 줄. 본문은 고치지 않음(원본 세션과 충돌 방지). 머리말 1줄만 수정 |
| CLAUDE.md 메타 문단 ("quad 구조를 작게 옮긴 것") | 삭제 | 행동에 영향이 없다 (04 감사 #6) |
| CLAUDE.md 온디맨드 표 15줄 + 참고 자료 표 7줄 | 축소 | 스킬이 대신하는 줄(delegate-agy 등)을 빼서 7줄로. 참고 자료는 한 문단으로 |

conventions.md(34.5 KB)는 지우지 않았다. rules의 각 줄이 가리키는 **상세·예외·근거 문서**로 남겼다. rule은 "명령형 한 줄 + 근거 하나"로 썼고, 근거는 conventions의 절, 질문 ID, `spikes/N` 중 하나다.

## 3. 만든 rules (모두 paths 조건부, paths 없는 rule은 0개)

| 파일 | paths | 크기 |
|---|---|---|
| `.claude/rules/luau-style.md` | `**/*.luau` | 1.3 KB / 10줄 |
| `.claude/rules/src-modules.md` | `src/**/*.luau` | 3.6 KB / 31줄 |
| `.claude/rules/src-containers.md` | `src/{Collections,Node,Trees,Algorithms}/**/*.luau` | 1.8 KB / 11줄 |
| `.claude/rules/src-trait.md` | `src/Trait/**`, `src/Traits/**`, `src/Collections/**` (`*.luau`) | 1.8 KB / 9줄 |
| `.claude/rules/tests.md` | `tests/**/*.luau`, `scripts/**`, `.claude/audit/arr-type-redesign/spikes/**/*.luau` | 1.4 KB / 8줄 |
| `.claude/rules/docs.md` | `.claude/**/*.md`, `CLAUDE.md`, `GEMINI.md` | 1.4 KB / 9줄 |

## 4. 만든 skills

| 스킬 | 내용 | 호출 |
|---|---|---|
| `.claude/skills/neg-spike/SKILL.md` | 음성 대조군 작성 → `spike-expectations.tsv` → `spike-diff.py` → `check.sh` | 모델과 사용자 모두 |
| `.claude/skills/review-round/SKILL.md` | 라운드 운영, 결함 0이 두 번이면 실제 프로그램 작성으로 전환, 리뷰 기준 밖, 돌연변이 안전 수칙(`mutate.sh`, 상한, 종료 코드) | 모델과 사용자 모두 |
| `.claude/skills/classify-container/SKILL.md` | BI 전환 절차(`classify.py --dry`, 손으로 할 것), research/class-like t1~t9와 2-2절의 타입 함정 표, 열린 것 | 모델과 사용자 모두 |
| `.claude/skills/doc-audit/SKILL.md` | `doc-check.py`, "어디에 두나" 표(CLAUDE.md / rules+paths / skills / conventions / archive), 상시 로드 재는 법 | 모델과 사용자 모두 |
| `.claude/skills/handover/SKILL.md` | todos·question·archive 갱신 → 감사 → 커밋 | **`disable-model-invocation: true`** (커밋을 만듦) |
| (기존) `delegate-agy` | 변경 없음 | |

## 5. (d) luau-kb 후보 — `conventions.md`에 `<!-- luau-kb 후보 -->` 23곳

라이브러리 없이 재현되거나 Luau 버전에만 의존하는 사실들이다. 삭제하지 않았다.

| # | 사실 | 05 지도 분류 |
|---|---|---|
| 1 | `"__type"`을 업밸류 상수 대신 리터럴로 쓰면 상수 접기가 되어 생성이 7~11% 빨라진다 | 성능 |
| 2 | `__call` 콜러블 네임스페이스를 거치면 제네릭 생성자가 타입 인자를 잃는다 | 타입 |
| 3 | 트레이트 객체 타입에 인덱서를 두면 `X.Of<<…>>`가 함수가 아니게 된다. 오버로드(`&`) 안의 상류 결함으로 0건 | 타입 |
| 4 | 정의와 사용이 같은 파일이면 제네릭 칸 실수가 0건이다. `do … end`로 감싸서 피한다 (선언 순서 누수) | 타입 |
| 5 | 제네릭 함수 몸통이 타입 변수로 검사되지 않는다 (`Subtyping.cpp:830`) | 타입 |
| 6 | 가변인자 함수(`math.max`)를 콜백으로 넘기면 위치 인자까지 값으로 받는다 | 일반 Lua |
| 7 | 명시 타입 인자 `f<<T>>`로 제네릭을 푼다 | 타입 |
| 8 | 맨 람다 콜백: 몸통이 산술이면 에러이고, 0.734까지는 결과가 자유 타입이었다 (`spikes/54`·`57`) | 타입 |
| 9 | 콜백의 다른 인자에 `T`를 넣으면 주석 상한이 소실된다 (`spikes/52`). **혼합**: `ArrView<unknown>` 설계는 프로젝트 고유 | 타입/혼합 |
| 10 | `type function` 함정 ①②③ (바깥 로컬, 제네릭 self 체이닝, 진단 노출 버전차) | 타입 |
| 11 | `local const x = 1`은 전역 대입이 된다 | 문법 |
| 12 | `-- stylua: ignore`는 정확히 그 글자여야 먹는다 | 도구 |
| 13 | stylua 2.5.2가 `const` 뒤 `;(`의 `;`를 지운다 | 도구 |
| 14 | `#`·`table.clone`·`table.freeze`는 겉표에만 작용하고, 구멍 있는 배열은 해시 부분으로 가서 순서가 비약속이다 | 일반 |
| 15 | \|a\| > 2^53에서는 `%`가 틀린다. `math.fmod`를 쓴다 | 일반 |
| 16 | 반환이 `()`인 제네릭을 `pcall`에 바로 넘기면 타입 인자가 안 풀린다 | 타입 |
| 17 | 배열을 앞에서부터 `nil`로 비우면 해시 부분으로 가서 1.7배 느려진다 | 성능 |
| 18 | 노드: 번호 칸 대비 이름 필드는 2.3배, 나중 대입은 3배 느리다 (줄 전체는 프로젝트 계약과 섞여 있음) | 성능/혼합 |
| 19 | `error(msg, level)`은 -O2 인라인에서 틀린다 | 런타임 |
| 20 | 줄 번호를 헬퍼로 재면 -O2에서 인라인되어 틀린다 | 런타임 |
| 21 | 벤치마크는 실제 호출 형태로 여러 번 재서 최소값을 쓴다 | 성능 방법론 |
| 22 | `table.move`/`table.create` 벌크 처리, `table.pack` 대신 `select` 루프(1.6~2.3배) | 성능 |
| 23 | 뜨거운 루프에서는 모듈 함수를 지역에 받아 부른다 | 성능 |

`rules/docs.md`에는 "일반 Luau 지식은 후보 표시를 달고 길게 새로 쓰지 않는다. 정본은 `/code/Projects/claude-doctor/packs/luau-kb`(준비 중)" 한 줄을 넣었다.

## 6. 그 밖에 바꾼 것

- **BI 반영**
  - conventions "데이터와 모듈"은 정한 것 / 어디까지 왔나 / 아직 정하지 않은 것으로 나눴다.
    - 어디까지 왔나: `Class.New`를 쓰는 HashMap, TreeMap, FlatMap만 옮겨졌다(코드로 확인).
    - 아직 정하지 않은 것: 토큰 흡수 시점, 부분 타입 인터페이스의 이름과 범위.
  - conventions "트레이트" 머리에 "걷기 전까지의 규칙"이라고 적었다.
  - GEMINI.md "확정된 결정"에서 AB·BD를 빼고 "지금 전환 중인 것" 절을 새로 만들었다. 근거는 `archive/question-resolved.md` BG·BI 원문과 `research/class-like/README.md`, `src/Class.luau` 머리다.
- **`doc-check.py`**
  - 콜론 메서드를 "없어진 이름"으로 보던 STALE 줄을 걷었다. BI 이후로는 오탐이 된다.
  - 예산을 CLAUDE.md 6000 B / 80줄 + paths 없는 rule로 바꿨다.
  - 새 경고: `@import`, rule의 paths 누락, rule 하나 4.5 KB 초과. 대상에 `rules/`를 추가했다. 경고 두 종류는 임시 파일로 실제 발화를 확인했다.
- **`.claude/README.md`, `archive/README.md`**: "실리나" 열을 갱신하고 rules·skills 목록과 새 스냅숏을 색인했다.

커밋 (`doctor/diet`, 7개):

| 커밋 | 내용 |
|---|---|
| `668a37b` | archive 스냅숏 |
| `a7100ce` | BI 반영 |
| `06ec80e` | 스킬 |
| `62fdb8b` | rules |
| `283db18` | conventions 재편과 luau-kb 표시 |
| `ccb86d8` | CLAUDE.md, import 끊기, README, doc-check 예산, GEMINI 소스 문단 |
| `b0a365e` | rule에서 모듈 목록 제거 |

## 7. 사용자 판단이 필요한 것

1. **규약을 둘로 둘지.** 지금은 rules(짧은 판)와 conventions(상세)가 같은 규칙을 두 번 적는다. 규칙을 바꿀 때 두 곳을 고쳐야 하고, `rules/docs.md`와 `doc-audit`가 이를 상기시킨다. 대안은 conventions를 없애고 상세를 rules로 옮기는 것이다. 다만 그러면 src 작업 때 실리는 양이 다시 커진다.
2. **BI의 미정 사항.** 토큰(`__type`)을 클래스 흉내에 언제 흡수할지, 컬렉션 트레이트를 걷은 뒤 부분 타입 인터페이스의 이름과 범위를 어떻게 할지. 또 BI가 적은 순서(① 폴더 가르기 → ② 클래스 꼴)와 실제 진행(가르기 전에 클래스 꼴 3개)이 다르다. 문서에는 사실 그대로 적었다.
3. **todos.md 본문이 BI 이전(2026-11-09, BG까지)에 머물러 있다.** 원본 세션과 충돌을 피하려고 본문을 고치지 않았다. 원본 세션이 갱신해야 한다.
4. **`review-round`를 모델이 부를 수 있게 둘지.** 서브에이전트 다수와 돌연변이를 띄우는 절차다. 지금은 모델 호출을 허용했다. `handover`만 사용자 전용이다.
5. **project-context "모듈 구조" 트리는 코드에서 얻을 수 있다** (04 감사 #3). 온디맨드로 바뀌어 비용 문제는 사라졌다. 지울지 결정이 필요하다.
6. **35 KB 스냅숏(`archive/conventions-2026-11-10.md`)을 계속 둘지.** git 이력과 중복이지만 이 저장소의 관례(11-04 스냅숏)를 따랐다.
7. **ulimit은 여전히 문서 경고뿐이다** (04 감사 #8). `settings.json`과 heavy-proc-guard 훅은 범위 밖이라 손대지 않았다.
8. **agy는 rules가 자동으로 안 실린다.** GEMINI.md에 "고칠 파일에 해당하는 rule을 직접 읽으라"고 적었다. 위임 스크립트가 과제 프롬프트에 rules 경로를 넣게 할지는 따로 정해야 한다.

## 8. 원본 브랜치(`split/class-like`)와 병합할 때 예상되는 충돌

두 브랜치의 기준은 같다(`e77fc03`). 원본 세션이 BI 작업을 이어 가면서 아래 파일을 고칠 가능성이 높다.

| 파일 | 충돌 가능성 | 이유와 대응 |
|---|---|---|
| `.claude/conventions.md` | **높음** | BI 절(36~39줄)과 리뷰·문서 관리 절을 크게 바꿨다. 대응: 원본 쪽 판을 받은 뒤 `283db18`과 `a7100ce`의 변환(절 → 스킬 포인터, 23곳 표시, BI 3단 구조)을 다시 적용한다 |
| `.claude/tools/doc-check.py` | **높음** | STALE 목록의 마지막 줄을 지우고 BUDGET 블록을 바꿨다. 원본이 STALE 끝에 줄을 더하면 충돌한다. 대응: 양쪽을 다 살린다 |
| `GEMINI.md` | 중간 | "확정된 결정" 절을 재구성했다. 원본이 BI를 따로 반영했으면 겹친다 |
| `.claude/project-context.md` | 중간 | 머리말, 모듈 구조 첫 문단, 트리에 `Class.luau` 추가, 검증 절 끝줄을 바꿨다 |
| `CLAUDE.md` | 중간 | 전면 재작성했다. 원본이 온디맨드 표에 줄을 더하면 충돌한다. 대응: 새 줄은 스킬이나 온디맨드 표로 옮긴다 |
| `.claude/README.md`, `archive/README.md` | 낮음~중간 | 표 행이 인접한다 |
| `.claude/todos.md` | 낮음 | 머리말 3줄째 한 줄만 바꿨다 |
| 새 파일 (`rules/*`, `skills/{neg-spike,review-round,classify-container,doc-audit,handover}`, `archive/conventions-2026-11-10.md`) | 없음 | 원본에 같은 이름이 생기지 않는 한 충돌하지 않는다 |

**의미 충돌**(텍스트 충돌은 없어도 생기는 것):
- 원본 세션이 conventions에 새 규칙을 더해도 rules에는 반영되지 않는다.
- 옮긴 모듈 목록("HashMap·TreeMap·FlatMap")이 4곳에 적혀 있다: CLAUDE.md, conventions, GEMINI, project-context. 클래스 꼴이 늘면 함께 고쳐야 한다. `classify-container` 5단계와 `handover` 3단계가 이를 상기시킨다.
- 원본이 CLAUDE.md에 `@import`를 다시 넣으면 `doc-check.py`가 경고한다.

권장 병합 순서: 원본 세션이 한 단락 끝낸 시점에 `doctor/diet`를 그 위로 rebase하고, conventions·doc-check는 손으로 다시 적용한다. 원본 세션에 알려야 할 것은 rebase나 merge를 하지 않았다는 점과 위의 표다.
