---
title: "Roblox 엔진 쪽 비용 기준치와 재는 법"
description: "Studio 실측 엔진 비용 기준치(Instance.new, 속성 대입, GUI 수천 개, TextLabel 매 프레임 갱신, 트윈 5000개, BindableEvent 큰 표, 느린 Async 호출), 라이브 -O2·Studio -O1 기본값, CLI·mock 수치 읽는 법"
keywords:
  - "Instance.new 비용"
  - "속성 대입 비용"
  - "GUI 수천 개 프레임"
  - "TextLabel 매 프레임 갱신"
  - "트윈 수천 개 비용"
  - "BindableEvent 큰 표 비용"
  - "CreateHumanoidModelFromUserIdAsync"
  - "GetProductInfo 지연"
  - "--!optimize"
  - "라이브 최적화 수준"
  - "Studio -O1 라이브 -O2"
  - "MicroProfiler"
  - "CLI 벤치 엔진 비용"
  - "60fps"
kind: reference
category: roblox/perf
tags: [measured, studio, o2]
last_verified: 2026-11-10
---
# perf — Roblox 엔진 쪽 비용 기준치와 재는 법

## 이 파일이 답하는 질문
- Q1 `Instance.new`, 속성 대입, `TweenService:Create():Play()` 는 Studio 에서 대략 얼마나 드나?
- Q2 Part·GUI 를 몇천 개 만들면 프레임이 버티나?
- Q3 BindableEvent 로 큰 표를 보내면 얼마나 드나?
- Q4 느린 엔진 호출(아바타, 메시, 상품 정보)은 얼마나 걸리나?
- Q5 Roblox 라이브·Studio 는 어떤 최적화 수준으로 도나?
- Q6 CLI 벤치 수치를 엔진 비용으로 읽어도 되나?

## 목차
- §1 범위와 조건
- §2 Instance 와 속성
- §3 트윈
- §4 바인더블 인자 복사
- §5 느린 엔진 호출
- §6 최적화 수준(-O)과 native — 미판정
- §7 CLI·mock 수치를 읽는 법
- 모순 판정 · 미판정

---

## §1 범위와 조건
- 순수 Luau 비용(메타테이블, 표, 순회, 클로저, GC 비용, native codegen 일반)은 **luau-perf** 스킬이 다룬다. 이 파일은 엔진 API 와 Studio 에서 잰 것만 둔다.
- 아래 수치는 모두 원천 저장소의 **데스크톱 Studio** 실측이다(`status: described`). 기계 사양이 적혀 있지 않다. 60fps 상한(유휴 프레임 16.6ms)이 걸린 환경이다. 모바일은 아무도 재지 않았다. 절대값보다 **자릿수와 비율**로 읽는다.
- 신호 모드는 비용에 직접 영향이 적지만, 원천이 기록하지 않은 경우 "모드 미기재"로 적었다.
- 엔진 위 실제 비용을 새로 잴 때는 Studio 내장 skill `rbx-perf-profiling`(MicroProfiler), `rbx-scene-analysis`(메모리·Instance 구성)를 쓴다(luau-roblox `studio-mcp.md` §6).

## §2 Instance 와 속성
status: described · last-confirmed: quad 2026-10-22(데스크톱 Studio Play 클라이언트, 모드 미기재, 커밋 `8404d7dd`), table-sim(Studio 0.742, 2026-10) · 근거: quad `.claude/audit/perf-studio-2026-10-22/REPORT.md:21-63`; table-sim `<비공개>`; quad `.claude/base/slot-plan.md:120-123,3342-3343` · 후보: Q-093, T-54, Q-062

| 작업 | 비용 |
|---|---|
| `Instance.new("Frame")` + Size 대입 | 약 7µs, Lua 힙 약 1.7KB/개(±1KB 는 잡음) |
| 엔진 속성 대입 한 번 | 약 1.2µs |
| Frame+TextLabel 1000쌍 직접 생성 / 5000 / 10000 | 14ms / 109ms / 314ms. 첫 프레임 70ms / 438ms / 1101ms. N 에 선형 |
| 같은 트리 부모 지정 / 해체 | 1000쌍 약 40ms / 11ms |
| 장식 없는 Part 2000개 생성 | 118ms(0.078ms/개). 2000개가 정지해 있으면 60fps |
| Instance 1030개(SurfaceGui 202 포함) | 60fps 유지 |
| TextLabel 5000개의 Text 를 매 프레임 갱신 | 엔진만으로 프레임 p50 31.7ms(글자 재배치가 비싸다). 1000개는 16.7ms |

- **변화가 없으면 프레임당 비용은 0 이다.** 마운트 뒤 정상 상태 120프레임은 유휴와 같았다.
- 글자 갱신은 개수에 비례해 레이아웃 비용이 붙는다. 수천 개 라벨을 매 프레임 바꾸지 않는다.
- `Parent = nil` 뒤 `Destroy()` 가 바로 `Destroy()` 보다 비싸다는 서술이 있다. 벤치는 없다.
- `QueryDescendants` 는 깊이 200·결합자 4개까지 0.02ms 이하였다(`instance-api.md` §6).
- 측정 함정: 유휴 클라이언트의 힙은 할당이 없으면 줄지 않는다. 힙 수치는 짧은 쓰레기를 할당(churn)한 뒤의 최저값으로 잰다. 시나리오 빌드는 별도 함수로 뺀다(`gc-in-roblox.md` §2, 프로브 함정 luau-runtime `gc-and-weak-tables.md` §5).

mock 흉내: 해당 없음. mock 위 CLI 수치에는 엔진 호출 비용이 빠져 있다(§7).

## §3 트윈
status: described · last-confirmed: quad 2026-10-22(데스크톱 Studio Play, 모드 미기재) · 근거: quad `.claude/audit/perf-studio-2026-10-22/REPORT.md:44-52` · 후보: Q-093

| N | `TweenService:Create():Play()` 전체 | 도중 교체(새 목표) | 도는 동안 프레임 p50·p95 |
|---|---|---|---|
| 1000 | 2.4ms | 2.3ms | 16.6·17.3ms |
| 5000 | 12.6ms | 13.1ms | 16.5·20.5ms |

- 트윈이 도는 동안의 보간은 엔진이 하므로 Lua 쪽 프레임 비용이 거의 없다. 5000개에서는 한 프레임이 250~350ms 로 튀는 일이 엔진만으로도 있었다.
- 트윈 동작(통지, 수명)은 `tween-and-animation.md`.

mock 흉내: 해당 없음. mock Tween 은 보간을 하지 않는다.

## §4 바인더블 인자 복사
status: described · last-confirmed: devplorer 2026-10-20(Studio Edit, 플러그인 문맥, 잡음 큼) · 근거: devplorer `.claude/review/2026-10-20-bindable-watch.md:93-104` · 후보: D-R03

- `BindableEvent:Fire` 는 처리기마다 인자 표를 새로 복사한다(roblox-net `remotes-and-replication.md` §3). 2만 항목 표를 Fire 하면 1회 약 14ms, 처리기가 하나 늘 때마다 2~4ms 가 더 든다. 작은 인자 2000회는 1.9ms.
- 바인더블에는 크기 상한이 없다. 큰 표를 자주 보내는 설계는 피하고, 같은 VM 안이면 모듈 함수 호출로 넘긴다.
- Actor 메시지도 호출마다 전체 복사다(`parallel-luau.md` §5, 수치 없음).

mock 흉내: 아니오. Lua mock 바인더블은 보통 표를 복사하지 않고 그대로 넘겨, 비용도 별칭 차이도 재현하지 않는다(roblox-net `remotes-and-replication.md` §3).

## §5 느린 엔진 호출
status: described · last-confirmed: table-sim 2026-10(Studio 0.742 Play) · 근거: table-sim `<비공개>` · 후보: T-22, T-23, T-24, T-28, T-31

| 호출 | 걸린 시간 |
|---|---|
| `Players:CreateHumanoidModelFromUserIdAsync` | 1.06~1.32초(Description 캐시 뒤 0.02초) |
| `AssetService:CreateMeshPartAsync(Content.fromUri(id))` | 0.64초 |
| 서버 `MarketplaceService:GetProductInfo` | 350~600ms |
| 캐릭터 `Model:ScaleTo(5)` | 0.6ms |
| `RenderPriority.Camera+5` 에서 로컬 파트 6개 배치 | 16µs/프레임 |

- `…Async` 호출은 양보하고 실패할 수 있다. 화면 흐름에 넣을 때는 시한과 pcall 을 둔다(`tasks-and-threads.md` §6). 자세한 동작은 roblox-world `world-and-physics.md`.

mock 흉내: 해당 없음. 스텁은 즉시 돌려주므로 대기 시간을 재현하지 않는다.

## §6 최적화 수준(-O)과 native
status: described (문서 판정, 엔진 안 실측 없음) · last-confirmed: Roblox 문서 `luau/comments.md` "Comment directives" 절(56–78행, creator-docs ccc2b01d9bf8, `roblox_docs.py get luau/comments.md#comment-directives` 로 2026-11-10 재확인. 이전 표기 "Script directives" 는 절 이름이 틀렸다) · 근거: 그 문서; stl-luau-doctor `.claude/papers/05-quad-survey.md:110`, `.claude/conventions.md:136`; quad `.claude/archive/post-implementation-review/round14-reflection-plan.md:25`, `docs/quadnomicon/11-static-grepability-and-error-architecture.md:126-129`; Roblox 문서 `luau/native-code-gen.md`(2026-11-10) · 후보: S-116, Q-088, qwreey-harness .claude/scopes/packs/luau-kb/audit/09 §6 #2

- **Roblox 문서가 기본값을 적어 둔다**: `--!optimize` 지시어 설명에 "1 enables basic optimizations (default in Studio testing)", "2 enables further optimizations (default in live games)"(`/docs/en-us/luau/comments.md`, 2026-11-10). stl 의 "라이브 `-O2`, Studio `-O1`" 은 이 문서와 맞고, quad 의 "실측 필요"는 문서로 닫힌다. 엔진 안에서 직접 잰 기록은 아직 없다(아래 절차).
- 문서는 "Exact optimizations aren't published and are subject to change" 라고 덧붙인다. CLI `-O2` 의 인라인 규칙이 엔진과 같다는 것은 가정이다.
- 이것이 중요한 이유: `-O2` 는 지역 함수 호출을 인라인해 `debug.info` 스택과 `error(msg, level)` 의 위치를 바꾼다(luau CLI 실측, 경우별 표는 luau-testing `optimize-levels.md` §2). Studio 에서 통과한 에러 위치 테스트가 라이브에서 달라질 수 있다.
- `--!native`/`@native` 는 최적화 수준 2 를 강제한다(CLI 실측, luau-perf `optimizer-and-native.md` §2·§6). Roblox 문서는 "동작은 같고 성능만 다르다"고 한다.
- 처방(판정 전): 에러 위치·스택 걷기에 기대는 코드는 `-O1` 과 `-O2` 둘 다에서 맞게 짠다. 손으로 센 `error(msg, 2)` 를 라이브러리에서 쓰지 않는다(D-10).

## §7 CLI·mock 수치를 읽는 법
status: described · 근거: quad `.claude/audit/perf-cli-2026-09-26/REPORT.md:3-5`, `.claude/audit/round14-principle-audit/expensive-checks.md:5` · 후보: Q-094

- mock 위 CLI 비율은 엔진 호출 비용이 빠진 만큼 **상한**으로 읽는다. "라이브러리 오버헤드가 3배" 는 엔진 호출이 들어가면 줄어든다(위 §2 에서 Lua 쪽 빌드가 엔진 직접의 3~6배여도 부모 지정·해체는 같았다).
- 타이밍 반복과 호출 세기를 같은 카운터로 하면 카운트가 반복 수만큼 불어난다. 따로 잰다. 측정 커밋 sha 를 같이 적는다.

---

## 모순 판정

| # | 내용 | 판정 |
|---|---|---|
| qwreey-harness .claude/scopes/packs/luau-kb/audit/09 §6 #2 | 라이브 Roblox 최적화 수준: stl "라이브 -O2, Studio -O1" 대 quad "미실측" | **판정(문서)**: stl 이 맞다. `luau/comments.md` 가 Studio 테스트 1, 라이브 2 를 기본값으로 적는다. 엔진 안 인라인 동작의 실측 확인은 아래 절차로 남긴다 |

## 미판정
- **라이브·Studio 의 최적화 수준(엔진 안 실측 확인).** 문서 기본값(Studio 1, 라이브 2)이 인라인 동작으로도 보이는지 확인하는 절차:
  1. ModuleScript 에 `local function inner() return debug.info(2, "n") end` 와 `local function outer() return inner() end` 를 두고 `outer()` 의 결과를 돌려준다. 같은 파일을 luau CLI 에서 `-O1`, `-O2` 로 돌려 두 결과(인라인되면 프레임 이름이 달라진다)를 기준으로 삼는다. 더 확실한 신호는 `error("x", 2)` 를 부르는 지역 함수의 보고 줄이다.
  2. Studio Edit(`execute_luau`)과 Play(Server, Client)에서 같은 모듈을 require 해 결과를 `return` 한다.
  3. 게시한 플레이스의 라이브 서버에서 같은 모듈을 돌려 결과를 `print` 하고 Developer Console(F9, 서버 출력)로 읽는다.
  4. 세 결과를 CLI 기준과 비교해 Studio·라이브의 수준을 적는다. 날짜와 Studio 버전을 붙인다.
- **모바일 기기의 §2 기준치.** 기기가 없어 아무도 재지 않았다.
