# 분리 계획 시험: stl-luau `src/Collections/Arr.luau`

> 2026-11-10. 읽기 전용 시험 실행이다. stl-luau 저장소에는 아무것도 쓰지 않았다(다른 세션 상주). 계획기: luau-kb `skills/luau-style/scripts/split-plan.py`.
> 명령: `python3 -I split-plan.py /code/Projects/stl-luau/src/Collections/Arr.luau`. 아래 "계획기 출력"은 손대지 않은 원문이다.
> 사용자 결정(D-13, 2026-11-10): `Arr.luau` 는 예외로 두지 않는다. 이 문서는 "어떻게 나눌지" 판단 재료다.

## 핵심 질문: 타입 하나인데 나눌 수 있나

**된다.** `Arr` 는 메타테이블 없는 네임스페이스 함수 모듈이다(파일 머리 "데이터는 엔티티, 함수는 서비스"). 묶음 파일이 `Types` 에서 `Arr<T>`·`Raw<T>` 를 가져와 제네릭 함수를 정의하고 `init` 이 `Kind.Seal({ … })` 표에 재수출하면, 소비자 쪽 제네릭·콜백 검사·`Arr.Sized<<number?>>` 명시 타입 인자가 모두 그대로다(luau-kb `snippets/style-split-types.sh` S1, 0.734·0.742·0.746). 묶음이 생성자를 쓰려고 `init` 을 require 하면 순환이므로(S3) 생성자는 `Ctor` 로 뺀다 — 계획기도 `Ctor` 군집을 따로 냈다.

## 사람이 보기에 그럴듯한가 (스스로 비평)

| 군집 | 판정 |
|---|---|
| `Insert`(원소 추가 + 꺼내기, 196) | 좋음. region 둘이 합쳐졌다 |
| `Ctor`(생성자 region 그대로, 310) | 좋음. S3 때문에 꼭 필요한 조각이다 |
| `Query`(조회 + unchecked + 구멍 다루기, 469) | 좋음. 사용자가 함수를 찾는 길과 같다 |
| `Sort`(정렬 가족, 404) | 좋음 |
| `Shuffle`(복제·구간·순서 바꾸기, 319) | 경계는 맞고 **이름이 약하다** → `Range`/`Reorder` |
| `Stream`(스트림 + 묶기 + 접기 + 계약 구현의 `Get`·`FirstIndex`… 683) | 대체로 맞다. 다만 **계약 구현 위치 함수 다섯(241–280)** 은 `listImpl` 표와 같이 `init` 에 남기거나 `Query` 로 보내는 것이 자연스럽다(작은 region 이라 이웃에 섞였다 — 계획기 한계로 문서화). 묶기(GroupBy 등)는 `HashMap` 을 require 하므로 따로 `Group` 으로 둘 수도 있다 |
| `Core`(toIndex·resolveRange·wrap·newEmpty, 37) | 구조로는 맞다. **성능 주의**: 이 넷은 뜨거운 루프 앞에서 부르는 작은 헬퍼다. 다른 파일로 옮기면 `-O2` 인라인이 사라진다(luau-perf `calls-and-closures.md` §1). stl 은 성능이 계약인 저장소이므로 (a) 각 묶음 파일에 사본을 두고 같음 검사를 붙이거나 (b) 옮긴 뒤 `bench/` 로 재는 것을 사람에게 물을 문항으로 둔다 |

- 군집 사이 간선 7개가 모두 `Core` 로 가고 순환 0, 모듈 상태 0 — **옮기기만으로 나눌 수 있는 가장 쉬운 꼴**이다. 남는 비용은 `Core` 인라인 문제 하나다.
- "반복 블록"(`const data = self.data` 78회 등)은 이 저장소의 성능 관용(지역 캐시)이다. 고치지 않는다(audit/12 §2.5 와 같은 판단). 계획기는 반복을 기계적으로 낼 뿐이라 사람이 거른다.
- 결과 크기: 3,030줄 → 조각 6개(196~683) + Core 37 + init(모으기·계약 표, 약 150줄 예상). 가장 큰 조각도 경고 기준 아래다.
- **알고리즘에 반영한 것**: (1) region 이 있으면 구획 가중치를 높이고(1.0), 닫히지 않은 region(`조회`)은 다음 region 앞에서 끝난 것으로 본다. (2) 셋 이상의 구획에서 부르는 작은 무상태 함수(`newEmpty`)를 군집화 전에 Core 로 뺐다 — 그러지 않으면 생성 헬퍼가 호출자를 모두 끌어당겨 잡동사니 군집이 생겼다. (3) 반환 타입 `Arr<T>` 의 `>` 뒤에 오는 문장 `if` 를 식으로 잘못 읽던 파서 결함을 고쳤다.

---

## 계획기 출력

### (계획기 제목) `/code/Projects/stl-luau/src/Collections/Arr.luau` (3030줄)

- 분석 범위: 최상위(94–3030줄)
- 함수 146개(공개 119), 타입 선언 56줄, 상태 0개, 상수 14개, require·서비스 8개, 구획 16개(region)
- 군집 6개 + 공용 헬퍼 4개(37줄). 나누면 군집 사이 require 7개, 순환 0묶음.

## 1. 응집 군집 (후보 파일)

| 후보 파일 | 줄 | 함수 | 공개 | 원래 구획 | 줄 범위 | 쓰는 상태 |
|---|---|---|---|---|---|---|
| `Arr/Insert.luau` | 196 | 13 | 12 | 원소 추가 | 200–217, 877–1013, 1022–1072 | - |
| `Arr/Ctor.luau` | 310 | 11 | 9 | 생성자 | 229–239, 2640–2950 | - |
| `Arr/Stream.luau` | 683 | 42 | 36 | 스트림 | 241–280, 1903–2430, 2453–2560, 2569–2622 | - |
| `Arr/Query.luau` | 469 | 33 | 33 | 조회 | 291–623, 663–735, 779–871 | - |
| `Arr/Shuffle.luau` | 319 | 23 | 19 | 순서 바꾸기 | 1078–1235, 1244–1429 | - |
| `Arr/Sort.luau` | 404 | 20 | 10 | 정렬 가족 | 1470–1897 | - |
| `Arr/Core.luau` (공용 아래층) | 37 | 4 | - | - | - | - |

- **Insert** (이름 근거: 구획): resolveInsertPos, PushBack, PushBackMany, PushBackArray, PushFront, PushFrontMany, PushFrontArray, Insert, InsertMany, InsertArray, PopBack, PopFront, SwapRemove
- **Ctor** (이름 근거: 구획): checkLength, Of, Sized, Adopt, FromTable, countReturns, FromIter, FromFunc, Concat, Range, isArr
- **Stream** (이름 근거: 구획): checkSize, isArrRaw, Get, FirstIndex, LastIndex, NextIndex, PrevIndex, Map, MapInplace, Filter, Retain, Partition, leadingCount, TakeWhile … 외 28
- **Query** (이름 근거: 구획): At, Set, Len, Empty, Iter, Unpack, ToTable, Join, Equal, Count, Find, FindLast, IndexOf, LastIndexOf … 외 19
- **Shuffle** (이름 근거: 낱말(약함); 다른 후보 SortInplaceUnchecked, Sort, Range): Clone, Clear, Fill, Slice, SliceInplace, Erase, EraseInplace, Splice, SpliceInplace, reverseRange, ReverseInplace, Reverse, rotateRange, RotateInplace … 외 9
- **Sort** (이름 근거: 구획): defaultLess, gatherValues, writeBack, insertionSortRange, mergeSortRange, stableSortBuffer, checkSelectArgs, sortRangeFallback, selectRange, StableSort, StableSortInplace, sortByInto, SortBy, SortByInplace … 외 6
- **Core**(셋 이상의 군집이 부르는 작은 무상태 함수 — 다른 파일들이 require 하는 아래층. init 에 두면 순환이 된다): toIndex, resolveRange, wrap, newEmpty

## 2. 군집 사이 간선 (나눈 뒤의 require)

| 부르는 쪽 → 불리는 쪽 | 호출 쌍 | 넘는 이름 |
|---|---|---|
| Stream → Core | 19 | newEmpty, resolveRange, toIndex, wrap |
| Shuffle → Core | 19 | resolveRange, toIndex, wrap |
| Ctor → Core | 9 | newEmpty, toIndex, wrap |
| Sort → Core | 8 | toIndex, wrap |
| Query → Core | 7 | resolveRange, toIndex, wrap |
| Insert → Core | 2 | toIndex |
| Ctor → Stream | 1 | isArrRaw |

## 3. 순환 위험

- 없음. 군집 사이 호출이 한 방향이다.

## 4. 전방 선언

- 없음

## 5. 공유 상태를 어디로

- 없음 (상태 없는 모듈 — 옮기기만으로 나눌 수 있다)

## 6. "옮기기만" 커밋 순서

1. `Arr.luau` → `Arr/init.luau` 로 접는다(바깥 require 경로 그대로).
2. 공용 아래층 함수 4개를 `Arr/Core.luau` 로 옮긴다(init 이 아니라 여기를 다른 조각이 require 한다).
3. 옮기기만: **Insert** (196줄, 함수 13) → `Arr/Insert.luau`. require: Core. init 이 공개 12개를 재수출
4. 옮기기만: **Stream** (683줄, 함수 42) → `Arr/Stream.luau`. require: Core. init 이 공개 36개를 재수출
5. 옮기기만: **Query** (469줄, 함수 33) → `Arr/Query.luau`. require: Core. init 이 공개 33개를 재수출
6. 옮기기만: **Shuffle** (319줄, 함수 23) → `Arr/Shuffle.luau`. require: Core. init 이 공개 19개를 재수출
7. 옮기기만: **Sort** (404줄, 함수 20) → `Arr/Sort.luau`. require: Core. init 이 공개 10개를 재수출
8. 옮기기만: **Ctor** (310줄, 함수 11) → `Arr/Ctor.luau`. require: Stream, Core. init 이 공개 9개를 재수출
9. 이음매 감사(옮긴 상태가 값으로 묶였나, 정리 누락, 순서)와 문서의 옛 `파일:줄` 갱신.

## 8. 반복 블록 (고치기 커밋 후보 — 옮긴 뒤에)

- 11회 (921, 967, 1039, 1133, 1170, 1216 …줄): `const self = arr :: Raw<T> ⏎ const data = self.data ⏎ const len = self.n`
- 10회 (497, 514, 535, 561, 582, 603 …줄): `for idx = N, self.n do ⏎ const item = data[idx] ⏎ if item ~= nil then`
- 4회 (364, 824, 846, 2075줄): `local count = N ⏎ for idx = N, len do ⏎ const item = data[idx]`
- 4회 (889, 933, 980, 2416줄): `const self = arr :: Raw<T> ⏎ const data = self.data ⏎ const count = select("S", ...)`
- 4회 (1144, 2033, 2102, 2152줄): `for idx = count + N, len do ⏎ data[idx] = nil :: any ⏎ self.n = count`
- 3회 (301, 317, 1058줄): `if idx ~= idx then ⏎ Common.raise("S") ⏎ const len = self.n`
- 같은 머리 줄 78회: `const data = self.data`
- 같은 머리 줄 45회: `const len = self.n`
- 같은 머리 줄 34회: `const self = arr :: Raw<T>`
- 같은 머리 줄 27회: `const item = data[idx]`
- 같은 머리 줄 17회: `if item ~= nil then`

## 9. 참고: 이름 가족과 구획

- 접미 `inplace` 21개: CompactInplace, ConcatInplace, DedupInplace, DropWhileInplace, EraseInplace, FillHolesInplace, FlatInplace, FlatmapInplace … 외 13
- 접두 `sort` 8개: SortBy, SortByInplace, SortInplace, SortInplaceUnchecked, SortUnchecked, sortByInto, sortInto, sortRangeFallback
- 접미 `range` 7개: insertionSortRange, mergeSortRange, resolveRange, reverseRange, rotateRange, selectRange, shuffleRange
- 접두 `push` 6개: PushBack, PushBackArray, PushBackMany, PushFront, PushFrontArray, PushFrontMany
- 접미 `unchecked` 6개: MaxUnchecked, MinUnchecked, ProdUnchecked, SortInplaceUnchecked, SortUnchecked, SumUnchecked
- 접미 `index` 5개: FirstIndex, LastIndex, NextIndex, PrevIndex, toIndex
- 접두 `check` 4개: checkGroupKey, checkLength, checkSelectArgs, checkSize
- 접미 `into` 4개: dedupInto, sortByInto, sortInto, uniqueInto
- 구획 16개: 내부 헬퍼(168–261); 계약 구현 (List)(263–282); 조회(284–624); ⚠️ unchecked 계열 — 안전을 포기하고 고르는 것(625–737); 구멍 다루기(739–873); 원소 추가(875–1015); 원소 꺼내기(1017–1074); 복제·비우기·채우기(1076–1107); 구간 잘라내기·지우기·치환(1109–1237); 순서 바꾸기(1239–1431); 정렬 가족(1433–1899); 스트림(1901–2432); 묶기 — 키로 맵에 모으기 (M4, 2026-10-07 → 목적지 인자 2026-10-13)(2434–2562); 접기 (Fold 네 갈래)(2564–2624); 타입(2626–2634); 생성자(2636–2952)

