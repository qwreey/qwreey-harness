# roblox-boundary — Roblox 의존 코드를 luau 로 시험하는 경계: 분리, mock, 그리고 mock 이 거짓말하는 곳

## 이 파일이 답하는 질문
- Q1 Roblox API 를 쓰는 코드는 어디까지 순수 luau 로 시험하고 어디부터 Studio 가 필요한가? (D-03)
- Q2 엔진 무관 코어를 어떻게 나누나? CLI 에 없는 `Vector3`, `Enum` 같은 전역은?
- Q3 mock 을 쓸 때 엔진과 결과가 갈리는 대표적인 지점은?
- Q4 Deferred 시그널 배달을 CLI 에서 흉내 낼 수 있나?
- Q5 가짜 Instance 를 테이블로 만들면 무엇을 못 시험하나?

## 목차
- §1 원칙 (D-03): luau 기본, Roblox 의존 부분만 mock, Studio 는 확인용
- §2 세 방법: 코어 분리, mock 주입, fake 객체
- §3 CLI 에 없는 엔진 전역: 로드 시점 참조 금지
- §4 엔진과 mock 이 갈리는 점 목록
- §5 Deferred 배달 심
- §6 fake Instance 의 한계

---

## §1 원칙 (D-03): luau 기본, Roblox 의존 부분만 mock, Studio 는 확인용
status: described (정책) · 근거: claude-doctor `decisions/D-03-runner.md` "사용자 결정 (2026-11-10)", 후보 D-C03·R-47

1. 엔진과 무관한 로직은 Roblox API 없이 짜서 순수 `luau` 스펙으로 돌린다. 이것이 기본이다.
2. Roblox 서비스·환경(`task`, 이벤트, Instance 트리)에 기대는 부분은 **그 부분만** mock 으로 대체해 여전히 `luau` 로 돈다. 항상 Studio 를 부르면 기계적으로 반복 시험할 수 없다.
3. Studio(MCP)는 두 경우에만 쓴다: mock 이 실제와 맞는지 확인할 때, mock 으로 재현할 수 없는 동작(물리, 렌더, 실제 GC·복제)을 볼 때.

mock 작성 패턴, 주입 방법, 충실도 검증 절차는 luau-roblox 스킬 `../../luau-roblox/references/mocks.md`, Studio 에서 확인하는 절차는 `../../luau-roblox/references/studio-mcp.md`, 무엇이 Studio 를 요구하는지의 판정 표는 `../../luau-roblox/references/env-dependence.md` 에 있다. 이 파일은 **테스트 설계 쪽**(경계 긋기, mock 이 틀리는 지점 목록)만 다룬다.

## §2 세 방법: 코어 분리, mock 주입, fake 객체
status: verified (저장소 패턴 읽기, 2026-11-10) · 근거: `table-sim/.claude/conventions.md:96`, `quad/quad-roblox/test/spec.elem.luau:43`, `rbvm/.claude/review/2026-10-05-repro/fake.luau`, 원천 claude-doctor `drafts/gaps/testing.md` §10

| 방법 | 모양 | 비용·한계 |
|---|---|---|
| 엔진 무관 코어 분리 | Roblox API 없는 순수 모듈만 스펙으로 돈다(table-sim `<비공개>`, devplorer `tests/core`) | 가장 싸고 결정적. 엔진 접점은 시험하지 않는다 |
| mock 주입 | 최소 mock(트리, 프로퍼티, 변경 시그널, `IsA` 는 ClassName 비교)을 만들어 전역을 바꿔 끼운다 | `getfenv` 로 주입하면 그 스펙 파일의 `-O2` 인라이닝이 꺼진다(`optimize-levels.md` §4). 생성자 인자·모듈 필드로 주입받는 설계면 피한다 |
| fake 객체 | 수십 줄짜리 가짜 Instance/Signal 과 `task` 대역 | 테이블이라 `typeof` 가 `"table"` 이다(§6) |

## §3 CLI 에 없는 엔진 전역: 로드 시점 참조 금지
status: verified · last-confirmed: luau 0.742 (0.734 동일) · 근거: `snippets/test-cli-runtime-facts.luau`, `devplorer/.claude/conventions.md:53,67`, `tbox/CLAUDE.md:149-154`, `quad/scripts/doc-snippets-runshim.luau:1-12`, 후보 D-C03·Q-118

- `luau` CLI 에는 `task`, `game`, `Instance`, `Vector3`, `CFrame`, `Color3`, `Enum` 이 없다. 공용 모듈이 이 값을 **로드 시점**(모듈 최상위)에 참조하면 CLI 에서 `require` 하는 순간 죽는다. 스니펫이 로드 시점 참조는 `pcall` 이 실패하고 호출 시점 참조는 로드가 되는 것을 보인다.
- 처방: 엔진 값은 호출 시점에 읽는다. 타입 판별은 `typeof(v) == "Vector3"` 문자열 비교로 한다(전역을 건드리지 않음). Enum 조회도 호출 시점으로 미룬다.
- 로드할 때 엔진 서비스를 부르는 모듈(ReflectionService 등)을 거쳐 require 하면 그 위의 모든 모듈이 CLI 에서 시험 불가가 된다. 의존 방향을 엔진 모듈 → 코어 로 둔다.
- 모듈마다 환경(env)을 따로 받는 CLI 성질을 이용해 `getfenv(moduleFn)` 로 그 모듈 env 에 엔진 전역 mock 을 넣는 이음매도 있다. 그러나 모듈 **최상위**에서 엔진 전역을 쓰는 모듈은 이 방법으로도 못 고친다(quad 기록, described).

## §4 엔진과 mock 이 갈리는 점 목록
status: described (각 행의 엔진 쪽은 원천의 Studio 실측, mock 쪽은 원천 코드) · 근거: `quad/.claude/archive/post-implementation-review/post-implementation-review-round11.md:107-109`, `round8.md:343-351`, `quad/.claude/audit/studio-docs-2026-09-10.md:81-89`, `quad/.claude/qa-request/post-implementation-review-round13.md:89,181-182`, `quad/.claude/base/onchange-plan.md:56-57`, 후보 Q-120·Q-023·Q-026·Q-027·Q-035

mock 은 쓰는 사람이 상상한 엔진이다. 원천에서 실제로 엔진과 갈렸던 곳:

| mock 의 흔한 동작 | 엔진(Studio 실측) |
|---|---|
| 같은 값을 대입해도 변경 시그널을 쏜다 | 현재 값과 같으면 `Changed`·`GetPropertyChangedSignal` 모두 0회 |
| `Connect` 에 함수 아닌 값을 주면 던진다(또는 아무 값이나 받는다) | 던지지 않고 연결을 돌려주며 콘솔 경고만 남긴다 |
| Parent setter 가 순환·파괴 뒤 쓰기를 막지 않는다 | 순환은 에러, 파괴된 것은 잠긴다 |
| 리스너가 던지면 발화 원인 쪽으로 전파하고 나머지 리스너를 건너뛴다 | 리스너마다 격리, 다른 리스너는 돈다. Deferred 에서는 대입한 쪽으로 전파되지 않는다 |
| mock Tween 이 `.Instance` 를 Lua 필드로 쥐어 누수처럼 보인다 | 실물 Tween 의 `.Instance` 는 Lua 그래프에 잡히지 않는다 |
| 시그널을 동기로 즉시 배달 | Deferred(신규 place 기본)는 다음 재개점에 배달(§5) |
| 시계를 직접 읽음(`os.clock`) | 실기기 `task.wait` 는 ±0.02초 지터 → 시계는 주입한다(`gc-and-time.md` §3) |

관리법: 이런 차이는 **목록으로 남기고**, 결과가 mock 의 가정에 기대는 테스트에는 "Studio 확인 후보" 표시를 단다. 엔진 쪽 사실의 근거와 갱신은 roblox-engine·roblox-net·roblox-world 스킬이 맡는다.

## §5 Deferred 배달 심
status: verified (심의 성질) / described (엔진과의 일치) · 근거: `snippets/test-deferred-shim.luau`(`--@run-opt=2`), `quad/.claude/audit/round13-e79-deferred-signals/README.md:1-30`, 후보 Q-030·Q-018·Q-019

- 동기 mock 은 Deferred 엔진과 결과가 갈리는 버그를 숨긴다. 같은 mock 위에 **지연 배달 심**을 얹어 두 모드로 같은 시나리오를 돌리면 차이가 드러난다.
- 심의 규칙(원천 설계, Studio 실측을 흉내 냄): `Fire` 는 연결별 큐에 적재, `flush()` 가 FIFO 로 비움(flush 중 새 발화는 같은 flush 뒤에 붙음), 같은 값 대입은 발화 안 함, 명시 `Disconnect` 는 대기분을 버림, `Destroy` 로 끊긴 연결의 대기분은 1회 배달, 리스너 에러는 격리, 콜백은 배달 시점의 현재 값을 읽음.
- 스니펫이 보이는 대표 차이: 한 프레임에 `"hello"` → `"world"` 를 쓰면 동기 mock 의 콜백은 두 값을 차례로 보고, 지연 심은 두 번 모두 `"world"` 를 본다. 원천은 이 방법으로 "같은 프레임 두 엔진 쓰기 중 뒤의 것이 유실"되는 동작 차이를 찾았다.
- **심의 결과는 엔진 실측이 아니다.** 원천 파일 머리도 그렇게 경고한다. 심이 찾은 차이는 Studio 에서 확인할 후보 목록으로 넘긴다.

## §6 fake Instance 의 한계
status: described · 근거: `rbvm/.claude/review/2026-10-05-sibling-repos.md:111-113`, `rbvm/.claude/review/2026-10-05-code-review.md:67,615,710`, `rbvm/.claude/review/2026-10-05-repro/fake.luau:2`, 후보 R-47

- 테이블로 만든 가짜 Instance 는 `typeof(x)` 가 `"table"` 이라 `typeof(x) == "Instance"` 분기를 타지 못한다. `type(userdata)` 에 기대는 경로는 아예 다른 길로 간다. 원천의 리뷰 1라운드는 이 차이 때문에 거짓 결론을 냈다가 4라운드에서 정정했다.
- `newproxy` userdata 로 흉내 내면 `type` 은 맞출 수 있지만 `typeof` 의 `"Instance"` 는 만들 수 없다. 근본 처방은 §1 의 분리다: 순수 로직은 CLI, 엔진 판별 경로는 Studio.
