---
title: "순회 모양별 비용"
description: "숫자 for·ipairs·일반화 for·pairs 순회 비용(메타테이블 배열에서는 절반 아래), 해시 순회 API 는 표를 그대로 내주기, next 삼중항·래퍼 이터레이터 비용, 루프 안 nil 검사와 a.data[i] 끌어올리기, next(t, k) 중간부터 돌기 함정"
keywords:
  - "ipairs 대 숫자 for"
  - "ipairs vs numeric for"
  - "순회 비용"
  - "iteration cost"
  - "일반화 for"
  - "generalized iteration"
  - "pairs 성능"
  - "이터레이터 API 설계"
  - "래퍼 이터레이터 비용"
  - "next 삼중항"
  - "next(t, k)"
  - "중간부터 순회"
  - "필드 인덱싱 끌어올리기"
  - "루프 nil 검사 비용"
  - "FORGPREP_INEXT"
  - "__iter"
kind: reference
category: luau/perf/iteration
tags: [measured, correction]
last_verified: 2026-11-10
last_confirmed:
  - luau 0.734
  - luau 0.742
---
# iteration — 순회 모양별 비용

## 이 파일이 답하는 질문
- Q1 배열을 돌 때 `for i = 1, n`, `ipairs`, `for _, v in t`, `pairs` 중 무엇이 빠른가?
- Q2 메타테이블이 붙은 배열은?
- Q3 해시 표 순회 API 는 어떤 모양으로 내주나(일반화 for, `next` 삼중항, 래퍼 이터레이터)?
- Q4 루프 안의 nil 검사, 필드를 거친 인덱싱(`a.data[i]`)은 얼마나 드나?
- Q5 `next(t, k)` 로 중간부터 돌아도 되나?

## 목차
- §1 결론
- §2 배열 순회
- §3 해시 순회와 이터레이터 API
- §4 루프 안의 작은 비용: nil 검사, 필드 인덱싱
- §5 `next(t, k)` 로 중간부터 돌기
- §6 정정과 조건 차이

---

## §1 결론
- 평범한 배열은 `ipairs`·일반화 for·`pairs` 가 숫자 for 의 `t[i]` 보다 **조금 빠르다**(0.69~0.86x). 메타테이블이 붙은 배열에서는 **절반 아래**(0.42~0.48x)다. 단, 이 셋은 `__index` 를 보지 않고 `ipairs` 는 첫 nil 에서 멈춘다.
- 해시 순회 API 는 **표를 그대로 내준다**(`for k, v in t`). 함수가 돌려준 `next, t` 는 6~8 배, Luau 로 쓴 래퍼 이터레이터는 12~13 배 느리다.
- 뜨거운 루프의 `a.data[i]` 는 루프 밖에서 `local d = a.data` 로 받는다(1.52~1.68x 차).

## §2 배열 순회
status: verified · last-confirmed: luau 0.742 (0.734 대조) · 근거: `bench/iter-forms.luau`(array, mt-array 그룹), `snippets/perf-ipairs-raw.luau`, 후보 S-P06

100만 원소 합. 기준 = 숫자 for `for i = 1, N do s += t[i] end`.

| 순회 | 0.734 `-O1` | 0.742 `-O1` | 0.742 `-O2` | 0.742 `-O2 --codegen` |
|---|---|---|---|---|
| `ipairs(t)` | 0.70 | 0.76 | 0.74 | 0.86 |
| `for _, v in t` | 0.70 | 0.75 | 0.75 | 0.86 |
| `pairs(t)` | 0.69 | 0.74 | 0.74 | 0.86 |
| **메타테이블 붙은 배열** 기준 = 같은 표의 숫자 for | | | | |
| MT 표 `ipairs` | 0.48 | 0.45 | 0.46 | 0.42 |
| MT 표 `for _, v in t` | 0.45 | 0.45 | 0.45 | 0.42 |
| MT 표 콜백(Fold 꼴, 같은 파일 지역 함수) | 2.12 | 2.17 | **1.11** | 1.32 |

- 순회 명령(`FORGPREP_INEXT`/`FORGPREP_NEXT`)은 배열부를 직접 읽는다. 그래서 메타테이블 세금(`metatables.md` §2)을 내지 않는다.
- **의미 차이**: `ipairs` 는 첫 nil 에서 멈춘다. `ipairs`·일반화 for 는 `__index` 를 보지 않는다(`perf-ipairs-raw.luau`). 구멍을 허용하고 길이를 `n` 필드로 들고 있는 컨테이너라면 숫자 for 가 맞다. 그때는 원소를 메타테이블 없는 안쪽 표에 두어 세금을 없앤다.
- 콜백 순회는 `-O2` 에서 지역 함수와 클로저가 인라인되면 1.1 배까지 줄었다. 콜백을 받는 함수가 다른 모듈에 있으면 인라인되지 않는다(`calls-and-closures.md` §3).

## §3 해시 순회와 이터레이터 API
status: verified · last-confirmed: luau 0.742 (0.734 대조) · 근거: `bench/iter-forms.luau`(hash 그룹), 후보 S-P07

키 1000 개 표를 300 번 돎. 기준 = `for k, v in t`.

| 순회 | 0.734 `-O1` | 0.742 `-O1` | 0.742 `-O2` | 0.742 native | 원천(stl 27절, `-O2`) |
|---|---|---|---|---|---|
| `pairs(t)` | 1.04 | 1.01 | 1.02 | 1.01 | — |
| `for k, v in next, t` (리터럴) | 1.00 | 1.02 | 0.96 | 1.00 | 같음(28절) |
| 함수가 돌려준 `next, t` | 6.41 | 6.86 | 6.20 | 7.83 | 약 5x |
| Luau 래퍼 클로저(`next` 를 감쌈) | 13.3 | 12.3 | 11.9 | 13.6 | 약 9x |

- `pairs(t)` 와 리터럴 `next, t` 는 컴파일러가 알아보고 일반화 for 와 같은 빠른 경로를 쓴다. `next` 를 **값으로 돌려받으면** 그 경로를 놓친다.
- 순회 API 는 (1) 표를 그대로 내줄 수 있는지 먼저 본다, (2) 안 되면 `__iter` 나 메서드가 표를 돌려주게 한다, (3) 클로저 이터레이터는 마지막이다.
- 타입 측면(교집합 컨테이너에서 메서드 이터레이터의 루프 변수 타입)은 luau-types 가 다룬다(후보 S-P50).

## §4 루프 안의 작은 비용: nil 검사, 필드 인덱싱
status: verified · last-confirmed: luau 0.742 (0.734 대조) · 근거: `bench/iter-forms.luau`(array, hoist 그룹), 후보 S-P16, S-P28

| 비교 | 0.734 `-O1` | 0.742 `-O1` | 0.742 `-O2` | 0.742 native | 원천 |
|---|---|---|---|---|---|
| `local v = t[i]; if v ~= nil then` 추가 | 1.14 | 1.19 | 1.17 | **0.94** | 1.13x(6절, 0.734 `-O1`) |
| `a.data[i]` 를 그대로(대 `local d = a.data`) | 1.63 | 1.65 | 1.68 | 1.52 | 1.43x(57절, 0.742 `-O2`, 1024개) |

- nil 검사는 인터프리터에서 14~19%, native 에서는 사실상 공짜였다. 구멍 안전성을 버릴 만한 값이 아니다.
- 필드 인덱싱은 매 반복 `GETTABLEKS` 하나를 더한다. 모든 모드에서 1.5 배 넘게 차이 나므로 늘 밖으로 뺀다. 원천보다 큰 것은 이번 측정의 내부 루프가 더 짧고(1024) 일이 가벼워서다.

## §5 `next(t, k)` 로 중간부터 돌기
status: verified · last-confirmed: luau 0.742 (0.734 동일) · 근거: `snippets/perf-next-from-hash-key.luau`, 후보 S-P34, stl-luau-doctor/.claude/base/perf-measurements.md:570-573

- `next(t, k)` 는 내부 순서에서 `k` 다음부터 돈다. 내부 순서는 배열부(번호 순) 다음 해시부(해시 순)다.
- 그래서 `k` 가 **해시부에** 있으면 그 앞에 놓인 키는 `k` 보다 커도 건너뛴다. 원천은 무작위 대조 5000 건 중 954 건이 틀렸다. 스니펫은 키 `{50, 60, 5, 70, 80, 90, 100}` 에서 `next(t, 5)` 가 5 보다 큰 키 6 개 중 1 개만 본다.
- `k` 가 배열부에 있으면(1..k 가 채워져 있으면) 그 뒤의 키를 모두 본다(대조군).
- "길이 밖 키만 지우기" 같은 일은 전체 순회로 한다. 전체 순회는 복사 비용과 비슷하다(원천 20절: 100만에서 빈 순회 2.3 ms).

## §6 정정과 조건 차이
| 원천 | 원래 서술 | 이번 측정 | 처리 |
|---|---|---|---|
| stl perf 3절 (`perf-measurements.md:60-72`) | "`ipairs` 0.39x 가 가장 빠르다" | 메타테이블 붙은 배열에서는 0.42~0.48x(같은 방향). **평범한 배열에서는 0.69~0.86x** 로 차이가 작다 | 조건 명시: 0.39x 는 MT 세금이 섞인 값이다 |
| stl perf 3절 | 메서드 이터레이터·`__iter` 2.86~2.89x, Fold 2.54x | 콜백(Fold 꼴)은 `-O1` 2.12~2.17x, `-O2` 1.11x | 조건 명시: `-O2` 인라인이 콜백 비용을 걷어낼 수 있다(같은 모듈일 때만) |
| stl perf 6절 | nil 검사 1.13x | 인터프리터 1.14~1.19x, native 0.94x | native 조건 추가 |
| stl perf 27절 | next 삼중항 약 5x, 래퍼 약 9x | 6.2~7.8x, 11.9~13.3x | 같은 방향, 이번이 더 큼(측정 모양 차이) |
