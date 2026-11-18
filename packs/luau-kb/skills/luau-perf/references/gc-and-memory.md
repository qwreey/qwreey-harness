---
title: "약한 표의 비용, GC 시간, 객체 크기"
description: "약한 키 레지스트리의 생성·조회·GC 비용(포인터 해싱 한 번이라 무시할 만은 범위 한정), __mode=\"k\" 표는 비워져도 칸 배열을 붙잡음(\"ks\" 는 줄어듦), 표·레코드·클로저 객체 크기, 클로저 캐시"
keywords:
  - "약한 표 비용"
  - "weak table cost"
  - "약한 키 레지스트리 비용"
  - "__mode = \"ks\""
  - "__mode k 메모리 안 줄어듦"
  - "객체 크기"
  - "표 메모리 크기"
  - "table memory size"
  - "바이트 수"
  - "GC 시간"
  - "GC 압박"
  - "클로저 캐시"
  - "closure caching"
  - "type(v) == \"table\" 선검사"
  - "collectgarbage(\"count\")"
  - "메모리 고수위"
kind: reference
category: luau/perf/memory
tags: [measured, correction]
last_verified: 2026-11-10
last_confirmed:
  - luau 0.734
  - luau 0.742
---
# gc-and-memory — 약한 표의 비용, GC 시간, 객체 크기

## 이 파일이 답하는 질문
- Q1 약한 키 표(레지스트리)로 객체의 정체성·소속을 매기면 얼마나 드나? 조회만 보면 싸지 않나?
- Q2 살아 있는 객체가 많을 때 약한 표는 GC 시간을 늘리나?
- Q3 약한 표를 비웠는데 메모리가 안 줄어든다. `__mode = "ks"` 는?
- Q4 표·클로저·레코드 하나는 몇 바이트인가?
- Q5 GC 는 언제 진행하나? 누수처럼 보이는데 아닌 경우는?
- Q6 같은 클로저 식이 매번 새 객체를 만드나?

## 목차
- §1 결론
- §2 약한 키 레지스트리의 비용
- §3 `__mode = "k"` 대 `"ks"`
- §4 객체 크기
- §5 GC 진행과 측정
- §6 클로저 캐시
- §7 경계: 의미론은 luau-runtime 에
- §8 정정과 조건 차이

---

## §1 결론
- 약한 키 레지스트리 등록은 문자열 태그 필드보다 생성이 **2.0~2.3 배**, 판정 조회가 1.5~2.3 배, 20만 개 생존 시 전체 GC 가 1.4~1.5 배다. "포인터 해싱 한 번이라 무시할 만"은 조회 한 번의 절대값만 본 말이다.
- 뜨거운 경로에서는 약한 표 조회 앞에 `type(v) == "table"` 을 둔다(원시값이 많으면 0.6 배, native 0.28 배).
- `__mode = "k"` 표는 키가 다 수거되어도 칸 배열을 붙잡는다(2만 키 → 1 MB). `"ks"` 면 줄어든다.
- 같은 3칸 레코드라도 전부 번호 칸 96 B, 번호+이름 112 B, 전부 이름 176 B 다. 이름 필드가 하나라도 있으면 해시부가 따로 할당된다.

## §2 약한 키 레지스트리의 비용
status: verified · last-confirmed: luau 0.742 (0.734 대조) · 근거: `bench/gc-weak.luau`, 후보 S-P36(S-110 병합), Q-089, qwreey-harness .claude/scopes/packs/luau-kb/audit/09 §6 모순 4

| 비교 (기준) | 0.734 `-O1` | 0.742 `-O1` | 0.742 `-O2` | 0.742 native | 원천 |
|---|---|---|---|---|---|
| 작은 객체 20만 개 생성 + `reg[o] = true` (대 `{…, __type = true}`) | 2.26 | 2.03 | 2.06 | 2.06 | ~1.9x(stl 18절, `Arr.Of`, 0.734 `-O1`) |
| 판정 `reg[o]` (대 `o.__type == true`) | 1.61 | 1.49 | 1.49 | 2.28 | "포인터 해싱 한 번, 무시할 만"(quad brand-plan) |
| 원시값 90% 섞인 입력: `type(v) == "table" and reg[v]` (대 `reg[v]` 바로) | 0.61 | 0.60 | 0.61 | 0.28 | Set 0.107 → 0.069 µs(quad, `-O2`) |
| 20만 개 생존 시 `collectgarbage("collect")` 한 번: 약한 키 표 등록 (대 태그 필드) | 1.50 | 1.38 | 1.47 | 1.40 | 2~3.7 배(stl 18절) |

- 모순 4(quad "무시할 만" 대 stl "1.66~1.9 배") 판정: 둘 다 맞다. 조회 한 번은 수 ns 라 대부분의 코드에서 무시할 만하고, **작은 객체를 자주 만드는 경로**와 **살아 있는 객체가 많은 GC** 에서는 비용이 보인다.
- 정체성 판정이 뜨거운 경로에 있으면 상수 문자열 필드(`__type`)가 싸다. 대가: 필드는 `pairs`·`table.clone` 으로 새어 위조를 막지 못한다(stl papers/05-quad-survey.md:68-91, described). 위조 방지가 필요하면 레지스트리, 속도가 필요하면 필드다.

## §3 `__mode = "k"` 대 `"ks"`
status: verified · last-confirmed: luau 0.742 (0.734 동일) · 근거: `snippets/perf-weak-ks-shrink.luau`, `bench/gc-weak.luau`(mem 그룹), 후보 S-P35, Q-004

| 2만 키를 넣었다가 모두 수거된 뒤 표 하나가 남긴 메모리 | 모든 모드(0.734·0.742) | 원천 |
|---|---|---|
| `__mode = "k"` | 1,048,576 B | 40만 종에 +8 MB(stl 32절) |
| `__mode = "ks"` | 0 B | 0 |

- `"k"` 표는 GC 가 항목을 지워도 해시 칸 배열 크기를 유지한다. 종류를 많이 만들었다 버리는 레지스트리·캐시는 `"ks"` 로 둔다.
- 약한 키 표에 넣기만 해도 메모리가 선형으로 느는 것처럼 보일 수 있다(quad: 32 B/사이클). 100 사이클마다 강제 GC 를 끼우면 0 이었다. **누수 판정 전에 강제 GC 대조군**을 먼저 돌린다(Q-004, described).

## §4 객체 크기
status: verified · last-confirmed: luau 0.742 (0.734 동일, 모든 모드 같음) · 근거: `snippets/perf-ctor-slots-memory.luau`, `bench/tbl-ctor-slots.luau`·`bench/mt-create.luau`(mem 그룹), 이 파일 작성 중 측정(`collectgarbage("count")` 차, 1만 개 평균), 후보 S-P37, S-P20

| 값 | 바이트 | 원천 |
|---|---|---|
| 빈 표 `{}` | 48 | — |
| 번호 칸 2개 `{a, b}` (메타테이블 유무 같음) | 80 | 96(MT 부착, stl 1-부절) |
| 번호 칸 3개 `{p, n, v}` | 96 | 96 |
| 번호 2 + 이름 1 `{p, n, value = v}` | 112 | 112 |
| 이름 3 `{value =, prev =, next =}` | 176 | 176 |
| 트리 노드 전부 번호 6칸 | 144 | 144 |
| 트리 노드 번호 3 + 이름 3 | 224 | 224 |
| `table.create(8, 0)` | 176 | 240(n=8, 다른 생성 경로) |
| `table.create(1024, 0)` | 16,432 | 16,496 |
| `{ data = table.create(8, 0), n = 8 }` (안쪽 표로 나눔) | 288 | +112 |
| 원소 하나인 집합 `{[obj] = true}` (키 객체 48 B 제외) | 80 | 96 |
| 반복 변수를 캡처한 클로저 | 48 | — |
| 위 2칸 배열 + 메서드 54 개 복사 | 2,128 | 2,112 |

- 배열부 칸은 16 B, 해시부 칸은 32 B 꼴이고 둘 다 2의 거듭제곱으로 잡힌다. 이름 필드가 하나라도 있으면 해시부가 따로 할당된다(할당 둘).
- 값 칸에 `true` 대신 원소 자신을 넣어도 메모리는 같다(S-P37 원천).
- 원천과 다른 행(MT 부착 96 → 80, `table.create(8)` 240 → 176, 집합 원소 하나 96 → 80)은 측정한 표의 모양·생성 경로 차이로 보인다. 상대 순서는 같다.

## §5 GC 진행과 측정
status: described(Studio) / verified(CLI 측정 규칙) · 근거: quad/.claude/audit/perf-studio-2026-10-22/REPORT.md:12-17, 후보 S-P51(Q-003), Q-011, Q-122, Q-123

- 힙 수치는 churn 뒤 **최저값**으로 적는다. 벤치 하네스도 이전 결과를 놓고 collect 한다(`bench/lib/bench.luau`).
- `luau-analyze` 는 `collectgarbage` 를 모른다. 타입 검사를 받는 스니펫에서는 `(_G :: any).collectgarbage` 로 꺼낸다.
- 누수 판정 하네스(`fullgc`, 객체 수 판정, 측정 함수 분리, 프로브 함정)의 정본은 luau-testing `../../luau-testing/references/gc-and-time.md` §1–§2 다.
- "GC 는 할당이 있어야 진행한다"(유휴 Studio 힙 56 MB 고정 → 할당 뒤 약 10 MB)와 Roblox 샌드박스의 `collectgarbage` 가 `"count"` 만 받는 점은 luau-runtime `../../luau-runtime/references/gc-and-weak-tables.md` §4(언어 규칙)와 roblox-engine `../../roblox-engine/references/gc-in-roblox.md` §1–2(Roblox 관찰)가 정본이다.

## §6 클로저 캐시
status: verified · last-confirmed: luau 0.742 (0.734 동일) · 근거: `snippets/perf-closure-cache.luau`, 후보 Q-005, Q-006

- 업밸류가 반복마다 바뀌지 않는 클로저 식(`function() return shared end`, `function() end`)은 반복마다 **같은 함수 객체**다. 할당이 없다. 반복 변수를 캡처하면 매번 새 객체다.
- GC 잔여를 세는 측정에서 "1개 남음"으로 보이는 원인이다.
- 함수를 키로 쓰는 레지스트리의 수명 함정(인라인 클로저가 바깥 모듈을 캡처하면 영구 잔존)은 luau-runtime `../../luau-runtime/references/gc-and-weak-tables.md` §7.

## §7 경계: 의미론은 luau-runtime 에
- ephemeron 없음(값이 키를 가리키면 영구 잔존), `__mode = "v"` 의 키는 강함, `__mode` 오타, 약한 값 배열의 구멍, 멈춘 코루틴이 잡는 키, GC 시점에 기대는 코드: luau-runtime `../../luau-runtime/references/gc-and-weak-tables.md` §2~§4(스니펫 `rbx-gc-no-ephemeron.luau`, `rbx-gc-weak-modes.luau`). 순수 Luau 의미론이지만 그쪽이 정본이다.
- Instance userdata 의 수거와 재생성: roblox-engine `../../roblox-engine/references/instance-lifecycle.md`.

## §8 정정과 조건 차이
| 원천 | 원래 서술 | 이번 측정 | 처리 |
|---|---|---|---|
| stl perf 18절 (`perf-measurements.md:504-525`) | 20만 생존 시 풀 GC 2~3.7 배 | 1.38~1.50 배(네 모드) | 같은 방향, 크기 축소. 원천은 실제 컨테이너(필드 여럿)였다 |
| quad brand-plan.md:147-150 | 약한 표 조회는 "포인터 해싱 한 번, 무시할 만" | 조회 1.5~2.3 배, 등록 2.0~2.3 배 | 범위 한정: 조회 한 번의 절대값만 맞다 |
| stl perf 1-부절·10-부절 등(S-P37) | MT 부착 작은 배열 96 B, `table.create` n=8 240 B | 80 B, 176 B | 수치 정정(모양 차이), 순서는 같음 |
