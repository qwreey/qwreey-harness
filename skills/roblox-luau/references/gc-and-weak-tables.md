# gc-and-weak-tables — 약한 표의 의미론, 누수 조건, GC 프로브의 함정

## 이 파일이 답하는 질문
- Q1 weak-key 표의 값이 자기 키를 잡으면 항목이 수거되나? (Luau 에 ephemeron 이 있나?)
- Q2 `__mode = "v"` 표의 키는? `__mode` 를 잘못 쓰면?
- Q3 weak 표 항목이 "어느 날" 사라져 코드가 간헐적으로 실패한다. 왜?
- Q4 "누수다/아니다"를 어떻게 판정하나? 프로브가 스스로 결론을 바꾸는 함정은?
- Q5 Roblox 에서는 `collectgarbage("collect")` 를 못 쓴다. 수거를 어떻게 관찰하나?
- Q6 weak 표를 쓰는 설계에서 피해야 할 모양은?

## 목차
- §1 범위: 이 파일과 luau-perf 의 경계
- §2 ephemeron 이 없다
- §3 weak 모드의 의미: 키·값·오타·구멍·멈춘 코루틴
- §4 GC 시점에 기대는 코드
- §5 누수 판정 절차와 프로브 함정
- §6 Roblox 에서 GC 를 관찰하기
- §7 설계 처방
- 모순 판정 · 정정

---

## §1 범위: 이 파일과 luau-perf 의 경계
- 이 파일은 **의미론과 누수 판정**을 다룬다. 같은 언어 사실(ephemeron 없음)을 luau-perf `gc-and-memory.md` 도 비용 관점에서 한 줄로 적는다. 무엇이 수거되고 무엇이 남는가, 그것을 어떻게 믿을 만하게 재는가.
- **비용**(weak 표의 칸 수가 줄지 않음 `"ks"`, weak-key 레지스트리의 생성·GC 비용, 객체 크기, "GC 는 할당이 있어야 진행" 의 성능 쪽)은 luau-perf 스킬의 `gc-and-memory.md` 가 다룬다.
- §2·§3·§5 의 주장은 순수 Luau 라 luau CLI 로 재현했다(`status: verified`). Roblox VM 도 같은 Luau 의미론을 따른다. 수거 **시점**은 엔진마다 다르다(§4, §6).
- Instance userdata 의 수거·재생성은 엔진 동작이라 `instance-lifecycle.md` §4 에 있다.
- **측정 하네스**(fullgc, 객체 수 판정, 테스트로 고정하는 법)의 정본은 luau-testing 스킬의 `gc-and-time.md` 다. §5 는 누수 **판정**에 필요한 만큼만 요약한다.

## §2 ephemeron 이 없다
status: verified · last-confirmed: luau 0.734, 0.742 (`--@run`) · 근거: `snippets/rbx-gc-no-ephemeron.luau`; luau.org/compatibility "Ephemeron tables"(미지원 목록); quad `.claude/audit/tween-completed-2026-09-21/REPORT.md:25-28`, `docs/quadnomicon/03-luau-memory-topology.md:15-21`; rbvm `.claude/review/2026-10-05-repro/L7_no_ephemeron_signal_leak.luau` · 후보: Q-001, R-22

- Lua 5.2+ 의 weak-key 표는 ephemeron 이라 "값이 키를 잡아도 키가 다른 곳에서 안 잡히면 수거"된다. **Luau 는 그렇지 않다.**
- 그래서 weak-key 표에서 **값이 자기 키를 강하게 잡으면 그 항목은 영원히 남는다.** 잡는 길은 무엇이든 같다.
  - 값 테이블의 필드: `wk[k] = { back = k }` → 50/50 잔존
  - 값 클로저의 업밸류: `wk[k] = function() return k end` → 50/50 잔존
  - 두 weak-key 표가 서로의 키를 가리키는 순환: `A[a] = { other = b }`, `B[b] = { other = a }` → 50/50 잔존
  - 대조군(값이 키를 안 잡음) → 0/50
- 처방: 사설 데이터를 **키 객체 자신**에 두거나, 값에서 키로 가는 참조를 없앤다. 그럴 수 없으면 항목을 명시적으로 지운다(snippet 끝부분: 지우면 수거된다).

mock 흉내: 해당 없음(순수 Luau, CLI 가 같은 VM 이다).

## §3 weak 모드의 의미: 키·값·오타·구멍·멈춘 코루틴
status: verified · last-confirmed: luau 0.734, 0.742 (`--@run`) · 근거: `snippets/rbx-gc-weak-modes.luau`; quad `docs/quadnomicon/03-luau-memory-topology.md:113-117`, `.claude/base/lifecycle-pattern.md:130-131`, `.claude/base/blocker-plan.md:123-127`, `.claude/base/ref-plan.md:155-161`; rbvm `.claude/review/2026-10-05-code-review.md:573-574` · 후보: Q-002, Q-008, R-23

| 모양 | 결과 |
|---|---|
| `__mode = "v"` 표 | **키는 강하다.** 값만 약하다. 내부 키 객체가 바깥 키를 되참조하면 weak-value 로도 못 피한다 |
| `{ __mod = "k" }`(오타) | 아무 경고 없이 **강한 표**가 된다. 실제 사고가 있었다 |
| 값이 약한 **배열** | 원소가 수거되면 가운데 구멍이 생긴다. `ipairs` 가 일찍 멈추고 `#` 의 경계가 정해지지 않는다. weak 집합은 `{ [obj] = true }` + `__mode = "k"` 로 둔다 |
| 값이 멈춘 코루틴을 잡는 weak-key 항목 | 코루틴 스택의 지역이 키를 잡으면 **고정된다.** `sig:Wait()` 로 멈춘 스레드는 스택에 `self` 를 쥐므로 `맵[sig].WaitList → thread → 스택 → sig` 사슬로 연결이 없어도 100/100 잔존(rbvm) |

- 부수 발견(타입 검사기): `for _ in ipairs(t)` 처럼 루프 변수를 하나만 두면 새 솔버가 "Argument count mismatch. Function expects 2 arguments, but 2 are specified" 를 낸다(0.734·0.742·0.746). 스니펫은 변수 둘로 피했다.

mock 흉내: 해당 없음(순수 Luau).

## §4 GC 시점에 기대는 코드
status: described · last-confirmed: quad 실측(CLI, 2026-09), quad Studio 2026-10-22(Play) · 근거: quad `.claude/base/relate-plan.md:245-250`, `.claude/base/tween-plan.md:690`, `.claude/archive/post-implementation-review/post-implementation-review-round1.md:47`, `.claude/audit/perf-studio-2026-10-22/REPORT.md:12-17` · 후보: Q-009, Q-004, Q-003, S-P51

- weak 항목이 사라지는 때는 GC 가 정한다. 같은 키를 다시 쓰는 코드가 **간헐적으로** 실패한다. weak 캐시의 유일한 강한 앵커를 먼저 치우면, 다음 할당 중(증분 GC 의 원자 단계 포함) 값이 사라진다.
- 처방: **명시적으로 만든 기록은 명시적으로 지운다.** weak 표는 "놓쳐도 되는 캐시"에만 쓴다.
- GC 는 할당이 있어야 진행한다. 유휴 Studio 클라이언트의 `collectgarbage("count")` 가 12초 동안 56MB 그대로였고, 짧게 사는 쓰레기를 할당하자 약 10MB 로 돌아왔다. 할당이 없으면 "안 줄어든다"는 누수 증거가 아니다.
- weak-key 표에 넣기만 해도 CLI 메모리가 항목당 약 32B 씩 선형으로 늘었는데, 100사이클마다 `collectgarbage("collect")` 를 끼우자 0 이 됐다. 누수가 아니라 GC 페이싱 아래의 고수위다. 비용 쪽은 luau-perf `gc-and-memory.md`.

mock 흉내: CLI 의 GC 시점은 Roblox 와 다르다(`env-dependence.md` §2 마지막 행). 시점에 기대는 버그는 CLI 에서 재현되지 않을 수 있다.

## §5 누수 판정 절차와 프로브 함정
status: verified (함정 셋) / described (하네스 절차) · last-confirmed: luau 0.734, 0.742 · 근거: `snippets/rbx-gc-probe-pitfalls.luau`; quad `.claude/audit/round13-e42-gc-sweep/README.md:10-13,92-93`, `.claude/audit/tween-completed-2026-09-21/REPORT.md:25-31,43-44`, `.claude/audit/perf-studio-2026-10-22/REPORT.md:14-17` · 후보: Q-122, Q-123, Q-005, Q-003

판정 절차(CLI, 상세는 luau-testing `gc-and-time.md`):
1. 시나리오를 **별도 함수**에서 만든다. 측정 함수의 지역 변수가 대상을 붙잡아 누수처럼 보이는 일을 막는다.
2. `fullgc()` 는 `collectgarbage("collect")` 를 최소 3회, 카운트 변화가 0.5KB 미만이 될 때까지(최대 12회) 돌린다.
3. 판정은 KB 증분이 아니라 **weak-key 추적자에 남은 객체 수**로 한다. KB 는 weak 표·해시 용량의 고수위 때문에 수백 KB 흔들린다.
4. N=0 기준선과 N 을 같이 잰다. 테스트 하네스·로그 표가 대상을 강하게 쥐지 않는지 본다.

프로브 함정(스니펫으로 재현):
- **포획 변수를 nil 로 지우기.** "다른 참조를 다 지웠다"며 클로저가 잡은 그 지역을 `nil` 로 만들면, 클로저의 업밸류 자체가 비워져 항목이 수거된다. 누수가 없어 보이지만 실험이 틀렸다. 값 클로저가 키를 **따로 복사한 업밸류**로 잡게 하고 바깥 변수만 지운다. quad 의 탐사자 판정 둘("ephemeron 맞다", "Completed 클로저는 안 샌다")이 이 이유로 무효 처리됐다.
- **클로저 캐시.** 업밸류가 반복마다 바뀌지 않는 클로저(`function() end`, `function(v) shared:Set(v) end`)는 Luau 가 캐시해 **반복마다 같은 객체**다. "만든 N 개 중 1개가 남았다"로 보인다. 반복 변수를 잡으면 매번 새 클로저다.

mock 흉내: 해당 없음.

## §6 Roblox 에서 GC 를 관찰하기
status: described · last-confirmed: 문서 `globals/LuaGlobals.md` collectgarbage(last_updated 2026-11-10); quad 2026-09-01·09-08·09-21 Studio, rbvm 0.742(2026-10-13, Deferred) · 근거: 문서 "Roblox's Luau sandbox only allows the count option"; quad `.claude/audit/tween-completed-2026-09-21/infinite-tween-probe.md:10-12`, `.claude/audit/spike10-full-run-2026-09-01.md:12-14`, `.claude/audit/round8-studio-2026-09-08.md:11`; rbvm `.claude/design/engine-behavior.md:47` · 후보: Q-011, R-18

- Roblox 의 `collectgarbage` 는 `"count"` 만 받는다(문서, deprecated 표시, `gcinfo()` 를 권한다). Studio MCP 실행 스레드에서도 `"collect"` 는 `use gcinfo() instead` 로 거부됐다.
- 관찰법: **할당 압박 + 프레임 넘기기.** 에포크마다 `table.create(5000)` 을 20번 할당하고 `task.wait(0.05)` 한다. weak 표 canary 가 비면 수거된 것이다. 실측상 2~3 에포크(1초 미만)에 비었다. rbvm 은 Instance 20개가 5프레임 만에 수거됐다.
- 결과는 "N 에포크 안에 수거됨/안 됨"으로 적는다. 대조군(수거돼야 하는 것)이 같은 에포크 안에 수거되는지 같이 본다. tween-completed 실측은 대조군 8 에포크, 누수 후보 150 에포크 잔존으로 판정했다.

mock 흉내: 해당 없음. CLI 에서는 `collectgarbage("collect")` 로 바로 본다.

## §7 설계 처방
status: described · 근거: quad `.claude/base/relate-plan.md:121,140-151`, `.claude/audit/round13-e42-gc-sweep/README.md:42`, `.claude/archive/v2-initial-implementation/pre-implementation-handtrace-round7.md:2453-2458`, `.claude/archive/question-resolved.md:1495`; rbvm `.claude/review/2026-10-05-code-review.md:571-584` · 후보: Q-006, Q-007, Q-002, R-22

- **함수를 키로 쓰는 dedup·레지스트리 표**: 인라인 클로저가 바깥 모듈을 잡으면 그 모듈이 영원히 산다(잡는 경우 50/50 잔존, 안 잡는 경우 0/50). 키 함수는 모듈 수준 함수로 둔다.
- **반응형·옵저버 그래프**: 구독자를 weak 로 담는다면 하류 → 상류 참조는 강하게 둔다. 아니면 중간 파생 노드가 수거돼, Observer 가 레지스트리에 살아 있는데도 에러 없이 다시는 발화하지 않는다(실측: 발화 0, 구독자 0).
- **두 weak 표를 잇는 설계**: 값이 다른 표의 키를 가리키면 §2 의 순환 누수다. 한쪽을 강한 표 + 명시 정리로 바꾼다.
- Instance 를 weak 키로 쓰는 표는 엔진이 userdata 를 재생성해 항목이 미아가 될 수 있다(`instance-lifecycle.md` §4–5).

mock 흉내: 해당 없음.

---

## 모순 판정

| # | 내용 | 판정 |
|---|---|---|
| audit/09 §6 #4 | weak-key 레지스트리 비용: quad "포인터 해싱 한 번, 무시할 만" 대 stl "생성 1.66~1.9배, 풀 GC 2~3.7배" | **판정**: 조건 차이. quad 는 **조회** 비용만 말했고 그 범위에서는 맞다(stl 도 조회 경로는 같다고 잰다). 등록·GC 비용은 stl 실측이 반례다. 수치는 luau-perf `gc-and-memory.md` 몫 |
| audit/08 Q-001 비고 | 탐사자 "Luau weak 표는 ephemeron 이다" 대 실측 "아니다" | **판정**: 탐사자 프로브가 포획 업밸류를 nil 로 지운 결함(§5). 이 저장소가 0.734·0.742 로 재현했다(§2) |

## 정정

| 원천 경로:줄 | 틀리거나 낡은 서술 | 맞는 것 | 근거 |
|---|---|---|---|
| quad `.claude/audit/tween-completed-2026-09-21/probe-log.md`(탐사자 1~6, 7·8 판정) | weak-key 표가 ephemeron 처럼 수거된다 | 포획 업밸류를 비운 프로브 결함. Luau 는 ephemeron 이 아니다 | `rbx-gc-no-ephemeron.luau`, `rbx-gc-probe-pitfalls.luau` (원천 REPORT 가 이미 무효 처리, 확인용) |
| quad audit/08 Q-011 비고 | `collectgarbage("collect")` 가 일반 스크립트에서도 막혔는지 범위 재확인 필요 | Roblox 샌드박스 전체에서 `"count"` 만 허용(문서) | 문서 `globals/LuaGlobals.md` |
