# quad 세션에게: claude-doctor 가 찾은 사항

claude-doctor 에서 quad 를 읽기 전용으로 조사하다 찾은 것들이다. 반영은 quad 세션이 판단한다.

## 코드
1. **`quad-base/src/Relate.luau:28` 의 `error(…, 3)`**
   - `-O2`(그리고 `--!native`)에서 에러 위치가 틀린 줄을 가리키거나 사라진다.
   - quad 를 `-O2` 로 돌리면 테스트 3개가 실패한다.
   - 근거: `claude-doctor/decisions/D-10` 정정 절, `.claude/archive/research/drafts/gaps/optimize-levels.md`
2. **`scripts/doc-snippets-runshim.luau` 가상 task 큐의 정렬**
   - `table.sort` 는 안정 정렬이 아니다. 그래서 같은 시각 항목이 5개 이상이면 FIFO 순서가 섞인다(luau 0.742 실측).
   - 근거: `luau-kb/skills/roblox-luau/references/mocks.md`

## 문서·주석
3. **Surface 의 "no pcall" 주석**
   - type function 안의 pcall 이 안 되는 것은 luau-lsp 1.69.0 뿐이다. quad 핀인 1.70.1 에서는 이 주석이 틀리다.
   - 근거: `luau-kb/skills/luau-types/references/type-functions.md` §5
4. **`typing-limits.md:69` 의 "`error()` 대신 `print`"**
   - 0.734 이상에서는 필요 없다. `error()` 메시지는 네 판(luau 0.734/0.742, luau-lsp 1.69.0/1.70.1) 모두에서 진단으로 보인다.
5. **`base/architecture.md:783` "새 코드는 `const`"**
   - 게시된 소스는 0줄이라 실태와 맞지 않는다. D-01 은 `const` 사용 가능으로 확정됐다.
6. **보존 지시와 실제 상태가 다르다**
   - 패스스루 type function 뒤에 체이닝이 붕괴한다는 서술은 최소 꼴에서 재현되지 않았다.
   - 실물 `Quad` 가 깨진 원인은 인자 직렬화 실패로 보인다(추정).

## luau-kb 증류에서 나온 정정 (2026-11-10)

luau-kb 가 quad 서술을 재현하거나 더 새 실측·문서와 대조해 보니 틀렸거나 낡은 것들이다.
- 줄 번호는 2026-11-10 에 quad 를 읽기 전용으로 열어 확인했다.
- 근거 경로는 `/code/Projects/claude-doctor/packs/luau-kb/` 기준이다. 스니펫은 `snippets/<ID>`, 벤치는 `bench/` 에 있다.
- 심각도
  - **행동**: 그대로 따르면 코드·테스트·게이트·설계 판단이 틀어진다.
  - **표현**: 결론이나 처방은 맞고 범위·원인·수치·시점만 부정확하다. "이미 정정"은 같은 저장소 안에 고친 기록이 있어 확인만 하면 되는 것이다.
- 위 1·3·4·5·6번과 겹치는 항목은 `(위 n번)` 으로 표시했다.

### 테스트·에러 위치 (`-O2`)
| # | 원천 경로:줄 | 원래 서술 | 실측 결론 | 근거 | 심각도 |
|---|---|---|---|---|---|
| C01 | `scripts/test.sh:81-84` | 스펙을 `luau "$f"`(기본 `-O1`)로만 돈다 | `luau -O2` 로 돌리면 64/67 이고 3개(`spec.errorutil`, `spec.fallback`, `spec.relate`)가 실패한다. Roblox 문서상 라이브 기본은 수준 2 다 | `skills/luau-testing/references/optimize-levels.md` §5, `opt-cli-level-o1` | **행동** |
| C02 | `quad-base/src/Relate.luau:28-29` | 손으로 센 `error(…, 3)` | `-O2` 에서 사용자 줄을 가리키지 않는다 | `optimize-levels.md` §2, `opt-o2-error-level` | **행동** (위 1번) |
| C03 | `quad-base/test/spec.errorutil.luau:21-23` | 기대 줄을 헬퍼 `curline()`(`debug.info(2, "l")`)로 잰다 | `-O2` 에서 헬퍼가 인라인돼 -1 이 된다. 줄은 사용자 함수 안에서 직접 잰다 | `skills/luau-testing/references/assertions.md` §3, `test-o2-line-probe` | **행동** |
| C04 | `quad-base/test/spec.fallback.luau`(줄 미특정) | traceback 의 함수 이름을 단언한다 | `-O2` 에서 인라인된 함수의 이름 줄이 사라진다. 메시지와 줄로 단언한다 | `optimize-levels.md` §2·§5, `opt-o2-traceback` | **행동** |
| C05 | `quad-base/test/mock.luau:854-858` | `assertBlamesUser` 가 파일 이름과 `/src/` 부재만 본다 | level 이 틀려 같은 파일의 다른 줄을 가리켜도 통과한다 | `assertions.md` §4, `test-blame-filename-only` | **행동** |
| C06 | `docs/quadnomicon/11-static-grepability-and-error-architecture.md:126-128` | 테이블 필드에 담겨 그 필드로 호출되는 함수만 태그할 수 있고, quad 의 모든 태깅 지점이 그 조건을 만족한다 | 인라인되지 않는 것은 **대입으로 만든** 필드(`function M.f`)뿐이다. 테이블 **리터럴** 안에 쓴 필드 함수(`{ f = function … end }`)는 `-O2` 에서 인라인돼 태그가 사라진다. 태깅 지점 중 리터럴 필드가 있는지 확인이 필요하다 | `skills/luau-perf/references/optimizer-and-native.md` §3, `optimize-levels.md` §2, `opt-inline-rules` | **행동** |
| C07 | `scripts/test.sh:33-35` | 맨 `function name()` 은 `GlobalUsedAsLocal` 린트로 드러나므로 그 grep 이 게이트다 | 그 전역을 한 함수 안에서만 쓸 때만 린트가 난다. 모듈 스코프에서 선언하고 여러 곳에서 부르면 타입 진단도 린트도 0건이라 게이트를 지나간다 | `skills/luau-style/references/idioms.md` 정정, `style-bare-function-global` | **행동** |
| C08 | `.claude/archive/post-implementation-review/round14-reflection-plan.md:25` | Roblox 실행 환경의 최적화 수준은 실측이 필요하다(그래서 `-O2` 실패 3건을 두었다) | Roblox 문서 `luau/comments.md` 가 기본값을 Studio 테스트 1, 라이브 게임 2 로 적는다. 그 3건은 라이브 조건의 실패다(엔진 안 실측은 아직 없음) | `skills/roblox-luau/references/perf.md` §6 | 표현 |

### 타입·type function
| # | 원천 경로:줄 | 원래 서술 | 실측 결론 | 근거 | 심각도 |
|---|---|---|---|---|---|
| C09 | `.claude/base/typing-limits.md:421`, `:72`; `.claude/audit/type-store-index-keyof/REPORT.md:24-28` | type function 은 바깥 타입 별칭을 참조하지 못해 구조를 통째로 중복해야 한다 | 참조할 수 있다(제네릭 별칭은 `Box(t)` 로 호출). 안 되는 것은 바깥 **지역 변수**다. 다른 모듈의 별칭은 지역 별칭으로 받아 쓴다 | `skills/luau-types/references/type-functions.md` §5, `tf-env-outer-alias-ok`, `tf-cross-module.sh` M5 | **행동** |
| C10 | `.claude/base/typing-limits.md:1161` (8.22) | `types.optional` 은 없다 | 있다(`Opt<number>` → `number?`) | `type-functions.md` §5, `tf-env-outer-alias-ok` | **행동** |
| C11 | `.claude/base/typing-limits.md:1115-1117` (8.18 제목); `type-version-check/src/init.luau:142-143`; `quad-roblox-types/src/Surface/init.luau:15-16`; `.claude/base/surface-plan.md:38` | type function 안에서는 `pcall` 을 쓸 수 없다. 그래서 멤버 하나가 죽으면 클래스 표면 전체가 `never` 다 | luau-lsp **1.69.0 만** 그렇다. quad 핀인 1.70.1 과 luau 0.734·0.742 는 `pcall` 이 되고 `parameters()` 같은 `types` API 에러도 잡는다 | `type-functions.md` §5, `tf-env-pcall-available` | **행동** (위 3번) |
| C12 | `.claude/base/typing-limits.md:69`; `.claude/luau-test/done/23-type-quadtypes-checkversion-addplugin.luau:16-18`; `type-version-check/src/init.luau:127-129`; `quad-types/src/init.luau:272-273` | `error()` 를 쓰면 type function 이 실패로 버려져 진단이 안 뜬다. `print` + `never` 만 보인다 | 네 판(luau 0.734·0.742, luau-lsp 1.69.0·1.70.1) 모두 `error()` 메시지가 보인다. 다만 never 불일치가 덧붙고 호출마다 반복되므로 `print` + `never` 가 더 깔끔하다는 권고는 유효하다 | `type-functions.md` §5, `tf-diag-error-vs-print` | 표현 (위 4번, `.claude/base/decisions/README.md` 낡은 서술 6번째 줄) |
| C13 | `.claude/base/typing-limits.md:1119-1121`, `:1160`; `quad-base/test/spec.versioncheck.luau:10-17` | 수출 type function 은 프라이밍해야 평가된다. spec 의 "pcall 때문에 평가 안 됨" | 1.69.0 + 모든 FFlag 일 때만이다. 1.70.1 은 프라이밍 없이 평가한다. 프라이밍은 해가 없으니 1.69.0 지원 동안 둬도 된다. spec 설명은 낡았다 | `type-functions.md` §5, `skills/luau-types/references/type-functions-limits.md` X1, `tf-cross-module.sh` M1–M3 | 표현 |
| C14 | `.claude/base/typing-limits.md:461-524` (§6); `.claude/luau-test/done/23-…luau:23-29`; `quad-types/src/init.luau:919` | 패스스루만 해도 이후 제네릭 self 체이닝이 조용히 깨진다 | 다섯 꼴 × 네 판에서 재현되지 않았다. 실물 `Quad` 를 패스스루하면 직렬화 실패(S1, `CheckReservedKeys<keyof<T>>`)로 `AddPlugin` 키가 사라진다. 원인은 이력이 아니라 직렬화로 보인다(추정) | `type-functions.md` §5, `tf-passthrough-chaining`, `tf-serialize-unsupported-arg` | **행동** (위 6번. 설계 회피의 근거가 바뀐다) |
| C15 | `.claude/base/typing-limits.md:1055-1058` (8.14) | `<U>(self: Ref<U?>) -> U` 로는 nil 을 벗길 수 없다 | 메소드 제네릭이면 맞다. 자유 함수 `unwrap<U>(r: Ref<U?>): U` 는 된다 | `type-functions.md` §5, `tf-noalt-stripnil` | 표현 (범위) |
| C16 | `.claude/base/quad-types-plan.md:263-267`; `.claude/luau-test/done/23-…luau:27-29` | (plan) 주석만으로 평가된다 / (test 23) 필드를 참조해야 평가된다 | 둘 다 부분적이다. 값이나 캐스트가 대조되는 주석은 평가되고, `any` 를 대입한 주석은 평가되지 않는다 | `type-functions.md` §5, `tf-diag-eval-sites` | 표현 |
| C17 | `.claude/base/typing-limits.md:944-951` (8.10) | `index<>` 로 만든 파라미터는 연산자 앞에서 `unknown` 이다 | 최소 꼴(기본 한도)에서 재현되지 않았다. `test.sh` 의 플래그 조건일 수 있다. 재현 파일이 있으면 알려 달라 | `type-functions.md` §5 (B4) | 표현 (확인 요청) |
| C18 | `.claude/research/kit-packaging-plan.md:73` | 교집합 타입 `q` 의 메서드로 부른 `q:GetOrCreate` 가 `any` 를 돌려준다 | 교집합 탓이 아니다. 제네릭 메서드의 `self: any` 가 조건이다. `self` 를 그 타입으로 적은 메서드는 교집합에서도 검사된다 | `skills/luau-types/references/solver-limits.md` §7, `solver-generic-method-self-type` | **행동** (고치는 법이 다르다) |
| C19 | `.claude/research/kit-packaging-plan.md:91` | 서로 다른 선언의 제네릭 함수는 글자가 같아도 같지 않다 | 최소 꼴 `local g2: <U>(U) -> U = g1` 은 통과한다. 실패는 `self` 재귀가 든 큰 타입 사본 둘 사이에서 났다. 조건은 아직 확정하지 못했다 | `solver-limits.md` §7 | 표현 (조건 미확정) |

### require
| # | 원천 경로:줄 | 원래 서술 | 실측 결론 | 근거 | 심각도 |
|---|---|---|---|---|---|
| C20 | `.claude/base/project-setup-plan.md:112-142`, `:339-348`; `.luaurc:6-9` | 커스텀 alias 는 luau CLI 런타임에서 `could not jump to alias` 로 실패한다. 편집기 전용이다 | 관측은 맞지만 원인은 alias 값에 `./` 가 없는 것이다. `"./quad-base/src"` 로 쓰면 luau 0.734·0.742 런타임과 `luau-analyze` 가 모두 푼다 | `skills/roblox-luau/references/require-and-modules.md` §3, `skills/luau-verify/references/checkers.md` §7, `rbx-require-cli.sh` Q6·Q11 | **행동** |
| C21 | `.claude/base/project-setup-plan.md:171-176`; `scripts/relink.sh:4-6` | 잘못된 require 경로·symlink 를 `luau-analyze` 가 `Unifiable<Error>` 로 떨궈 0 진단으로 통과한다 | `--!strict` 파일이면 `Unknown require: unsupported path` 가 난다. 0 진단은 nonstrict 이거나, `./` 가 다른 실제 파일로 풀리거나, luau-lsp(symlink 를 따라감)일 때다. 처방(런타임 require 게이트)은 같다 | `checkers.md` §7, `rbx-require-cli.sh` Q8·Q11 | 표현 |

### GC·weak 표
| # | 원천 경로:줄 | 원래 서술 | 실측 결론 | 근거 | 심각도 |
|---|---|---|---|---|---|
| C22 | `.claude/base/brand-plan.md:147-150` | 레지스트리 방식의 성능 차는 무시할 만하다 | 조회 한 번의 절대값만 맞다. 태그 필드 대비 0.742 에서 등록 2.0~2.3배, 판정 1.5~2.3배, 20만 개 생존 시 전체 GC 1.4~1.5배다. 작은 객체를 자주 만드는 경로에서는 보인다 | `skills/luau-perf/references/gc-and-memory.md` §2, `bench/gc-weak.luau` | 표현 (범위) |
| C23 | `.claude/audit/tween-completed-2026-09-21/probe-log.md:62-68` (Test 7) | weak-key 표가 ephemeron 처럼 수거된다 | 포획 업밸류를 비운 프로브 결함이다. Luau 는 ephemeron 이 아니다 | `skills/roblox-luau/references/gc-and-weak-tables.md` §2·§5, `rbx-gc-no-ephemeron`, `rbx-gc-probe-pitfalls` | 표현 (같은 폴더 `REPORT.md:9,27` 이 이미 무효 처리) |

### 엔진 동작 (시그널·수명·트윈·GUI)
| # | 원천 경로:줄 | 원래 서술 | 실측 결론 | 근거 | 심각도 |
|---|---|---|---|---|---|
| C24 | `.claude/base/slot-plan.md:3390` | `Parent` 대입은 `ChildAdded`/`DescendantAdded` 를 동기 발화시킨다 | Immediate 모드에서만이다. Deferred 에서는 다음 재개 지점에 배달된다 | `skills/roblox-luau/references/signals-and-events.md` 정정, Roblox 문서 deferred.md | **행동** |
| C25 | `.claude/archive/surveys/2026-08-06-pre-implementation-audit.md:218` | `Destroying` 발화 순서는 비결정적이다 | Deferred 0.742 에서 역순으로 관측됐다(보장은 없음) | `signals-and-events.md` 정정, rbvm `engine-behavior.md:46` | 표현 (아카이브) |
| C26 | `.claude/base/event-plan.md:84-85` | (옛 헤더) 엔진은 `Connect(비함수)` 에서 raise 한다 | 던지지 않고 경고만 남긴다 | `signals-and-events.md` 정정 | 표현 (`:84-85` 가 이미 정정. 옛 헤더 문구가 다른 곳에 남았는지만 확인) |
| C27 | `.claude/archive/post-implementation-review/post-implementation-review-round9.md:30` | mock 헤더: `task.cancel` 은 죽은 스레드에 에러 | 에러 없는 no-op 이다 | `skills/roblox-luau/references/tasks-and-threads.md` 정정 | 표현 (`H-514` 로 이미 지적. mock 헤더에 반영됐는지 확인) |
| C28 | `.claude/base/ref-plan.md`(옛 서술) | `coroutine.resume` 에러는 나중에 난다 | `(false, err)` 를 돌려주고 삼킨다 | `tasks-and-threads.md` 정정, `style-coroutine-resume-swallows` | 표현 (`ref-plan.md:314` `H-170` 이 이미 정정) |
| C29 | `.claude/base/lifecycle-pattern.md:150-152` | 이미 죽은 Tween 에 `:Cancel()` 하면 그냥 에러가 난다 | 던지지 않는다. 결론(Destroy 때 teardown 이 필요 없다)은 그대로다 | `skills/roblox-luau/references/tween-and-animation.md` 정정 | 표현 |
| C30 | `.claude/archive/post-implementation-review/post-implementation-review-round12.md:10`; `.claude/base/ui-shorthand-plan.md:303-304` | 연결이 먼저 끊겨 `Completed` 에 닿지 않는다 / 파괴된 인스턴스 위 트윈은 삭제된다 | 끝까지 돌고 `Completed(Completed)` 를 발화하며 연결도 유지된다 | `tween-and-animation.md` 정정 | 표현 (둘 다 `H-593` 이 이미 정정) |
| C31 | `.claude/research/tween-callback-structure.md:29` | 통지 대기 창이 있으니 `PlaybackState` 를 직접 읽어라 | 그 창은 관측되지 않았다. `Completed` 로 판정한다 | `tween-and-animation.md` 정정 | **행동** |
| C32 | `.claude/base/tween-plan.md:548` | 트윈 인스턴스는 재사용할 수 없다 | 완료 뒤 다시 `Play` 할 수 있었다(관측, 재측 권장) | `tween-and-animation.md` 정정, .claude/audit/08 Q-037 | 표현 |
| C33 | `.claude/base/lifecycle-pattern.md:278-285` | Instance userdata 의 수거·재생성은 미실측이다 | 2026-09-01 Studio 에서 1 GC 사이클 만에 수거됐고, 다시 얻으면 다른 userdata 였다 | `skills/roblox-luau/references/instance-lifecycle.md` 정정, quad `.claude/audit/spike10-full-run-2026-09-01.md:35` | 표현 |
| C34 | `.claude/feedback/consumer-kits-studio-qa-2026-10-07.md:285`; 커밋 `9bb7bfa3` 메시지 | 모달 면에 `Active = true` 를 주면 아래 스크림으로 가는 빈 곳 누름을 막는다 | 막지 못한다. `Active` 는 3D 입력만 막는다. GuiButton 싱크가 필요하다 | `skills/roblox-luau/references/gui-and-input.md` §1·정정 | **행동** (같은 파일 `:316`, `:392-411` 이 재측함. 커밋 메시지는 고칠 수 없으니 참고만) |
| C35 | `.claude/base/onchange-plan.md:50-52` | 붙인 직후 `AbsolutePosition` 같은 파생 프로퍼티는 계산돼 있다는 보장이 없다 | Immediate 구성에서는 그 자리에서 계산됐다. Deferred 는 미측정이라 "조건부"로 고친다 | `gui-and-input.md` 정정, quad `.claude/audit/kit-studio-2026-10-15/REPORT.md:45` | 표현 |
| C36 | `.claude/base/architecture.md:783` | 새 코드는 `const` 를 쓴다 | 게시된 소스에 `const` 가 0줄이라 실태와 맞지 않는다. D-01 은 "써도 된다, 한 파일 안에서 섞지 않는다"로 확정됐다 | claude-doctor `.claude/base/decisions/D-01-const.md` | 표현 (위 5번, `.claude/base/decisions/README.md` 낡은 서술 8번째 줄) |

## 분리 계획: `kits/roblox-devui/src/Window/Manager.luau` (2026-11-10)
전체 근거와 계획기 원문: claude-doctor `.claude/research/drafts/split-plans/quad-Manager.md`. 읽기 전용 시험이며 quad 에는 쓰지 않았다.
- 3,352줄 중 약 2,800줄이 `build(q)` → `Manager.new()` **한 함수의 본문**이다(지역 함수 83개, 지역 상태 20여 개). 계획기는 6군집(`Import`·`Focus`·`Member`·`Floor`·`OnPress`·`JudgeOver`) + `Core` 로 나눈다. 사람 분석 5묶음 중 3묶음(저장·분할·창 관리)이 대응하고 도킹·탭은 경계가 다르다.
- **옮기기만으로는 안 된다.** 상태가 인스턴스마다라 모듈 수준 `State.luau` 로 못 옮긴다. 먼저 상태 표(`ctx`)로 꺼내 함수에 넘기는 단계가 필요하다(군집 사이 공유 상태 13개, 순환 1묶음, 끊을 간선 4개·15호출쌍). 한 게임 저장소의 화면 모듈이 이 단계를 건너뛰어 다시 자랐다.
- `Register`(500줄, 안쪽 함수 11)는 파일을 나눈 뒤에도 단계별 함수로 따로 쪼개야 한다(`--scope Register`).
- 결과 폴더 예: `Window/Manager/{init, Arrange, Drop, Persist, Tabs, Focus, Core}` (quad 의 "가족 접기" 관례).
- D-13 확정(2026-11-10): 파일 길이 800줄 경고·1,500줄 강제(테스트는 두 배)이나 **알림만 하고 막지 않는다**. 확실한 사유를 기록하면 기준을 넘는 예외도 가능하다. 계획기는 `python3 -I /code/Projects/claude-doctor/packs/luau-kb/skills/luau-style/scripts/split-plan.py <파일.luau> [--target 400] [--max 800] [--scope 함수이름] [--json]` (읽기 전용, 표준 라이브러리만).
