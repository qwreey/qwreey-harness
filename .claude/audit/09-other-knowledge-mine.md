# 09. quad 밖 저장소의 일반 Luau/Roblox 지식 채굴 — luau-kb 이전 후보

감사일 2026-11-10. 읽기 전용(원천 저장소는 아무것도 고치지 않음). 범위: stl-luau(정리판 `stl-luau-doctor`), rbvm, table-sim, devplorer, tbox, moonwave-luau·mrow, vitrine·VideoSync·LaftelDiscordRpc. quad 는 제외하되 모순 대조에만 썼다.

- **제외한 것**: type function 지식, Roblox mock·Studio MCP 사용법(다른 에이전트 담당), luau-kb 에 이미 있는 것(`luau-types`·`luau-verify` 두 스킬), 저장소 고유 설계. 단 설계의 근거가 된 일반 사실은 넣었다.
- **판정 질문**은 셋이다: ① 저장소 없이 최소 재현되는가 ② 결론이 Luau 버전이나 엔진에만 의존하는가 ③ 다른 프로젝트에도 적용되는가. 셋 다 예면 `일반`, 일부만 예면 `반일반`, 모두 아니면 `고유`.
- **수집 방법**: 저장소별 탐사 에이전트 5개가 문서를 읽었다. 이 문서의 표는 그 결과를 합치고, 저장소 사이 중복을 한 행으로 병합한 것이다(§5 병합표). 줄 번호는 에이전트가 grep 으로 확인했다. 아래 두 가지는 내가 직접 소스로 다시 확인했다(★ 표시).
  - ★1 Luau 0.742 소스 `/code/Projects/stl-luau/refs-ignoreme/luau/VM/src/lvmexecute.cpp:779,809,836,864`: 정수 키 `GETTABLE`/`SETTABLE`/`GETTABLEN`/`SETTABLEN` 의 빠른 경로가 모두 `!h->metatable` 을 조건으로 건다. 이것이 S-P01 "메타테이블이 붙으면 `t[i]` 가 느리다"의 원인이다.
  - ★2 같은 소스의 `CLI/src/Analyze.cpp:434`: `luau-analyze --fflags=` 옵션이 있다. 그래서 luau-kb `luau-types/references/recursion-and-limits.md:75` 의 "luau-analyze CLI 에는 플래그 옵션이 없다"는 틀렸다(§6 모순 1).

## 0. 원천 경로 약어

표 셀을 줄이려고 원천 칸의 앞부분을 다음 약어로 줄였다. 합칠 때는 약어를 그대로 펼쳐 쓰면 된다.

| 약어 | 펼친 경로 |
|---|---|
| `stl:` | `/code/Projects/stl-luau-doctor/.claude/` |
| `perf:` | `/code/Projects/stl-luau-doctor/.claude/base/perf-measurements.md` |
| `bench:` | `/code/Projects/stl-luau/bench-ignoreme/` (perf 문서가 가리키는 벤치. doctor worktree 에는 없음) |
| `rbvm:` | `/code/Projects/rbvm/.claude/` |
| `rbvm-cr:` | `/code/Projects/rbvm/.claude/review/2026-10-05-code-review.md` |
| `rbvm-sib:` | `/code/Projects/rbvm/.claude/review/2026-10-05-sibling-repos.md` |
| `rbvm-eb:` | `/code/Projects/rbvm/.claude/design/engine-behavior.md` |
| `ts:` | `table-sim/<비공개>` |
| `dv:` | `/code/Projects/devplorer/.claude/` |
| `dvr:` | `/code/Projects/devplorer/.claude/review/` |
| `dvf:` | `/code/Projects/devplorer/.claude/feedback/quad-upstream-2026-10-20.md` |
| `dvf21:` | `/code/Projects/devplorer/.claude/feedback/quad-upstream-2026-10-21.md` |
| `tbox:` | `/code/Projects/tbox/` |
| `tbox-cr:` | `/code/Projects/tbox/docs/code-review-2026-10-05.md` |
| `mrow-rv:` | `/code/Projects/mrow/review/REVIEW.md` |
| `mw:` | `/code/Projects/moonwave-luau/.claude/` |
| `vs:` | `/code/Projects/VideoSync/` |
| `quad:` | `/code/Projects/quad/.claude/` |
| `kb:` | `/code/Projects/luau-kb/skills/` |

---

## 1. perf-measurements.md 절 단위 정리 (특별 요청)

### 1-1. 공통 측정 조건과 재현 스크립트

**공통 조건**
- 머리말(`perf:8-9`): Luau `0.734`(2026-09-22), 여러 번 재서 **최소값**을 쓰고, 래퍼 클로저 없이 루프에서 직접 호출했다.
- 18절(`perf:488-489`): "따로 적지 않았으면 `-O1` 인터프리터".
- 아래 표의 **상속** = 0.734 · `-O1` · 최소값 · native 아님.
- 15절부터는 대부분 `-O2` 를 따로 적었다.
- Luau 버전을 적은 절은 57절(0.742) 하나뿐이다. 58~60절은 버전을 적지 않았다.
- native(`--codegen`)를 잰 절은 **18절 하나**다.

**재현 스크립트 위치**
- 문서의 `bench-ignoreme/*.luau` 는 doctor worktree 에 **없다**. 실물은 형제 저장소 `/code/Projects/stl-luau/bench-ignoreme/` 에 있다.
- `spikes/NN` 은 `stl:audit/arr-type-redesign/spikes/` 로 옮겨졌다.
- `research/…` 벤치는 `stl:research/{class-like,tree-join,tree-size,trait-rebuild,trait-numbered}` 에 있다. `trait-struct` 는 README 뿐이다.
- 그 밖은 `/code/Projects/stl-luau-scratch/{arr-split,sorted-rank}` 에 있다.
- **1~21절은 재현 스크립트 위치가 문서에 적혀 있지 않다.** 이전할 때 새로 써야 한다.

### 1-2. 절별 표

분류: 일반 / 반일반 / 고유. "→ID" 는 §2 표의 후보 행이다.

| 절 | 제목 | 줄 | 결론(수치) | 조건 | 재현 스크립트 | 분류 → ID |
|---|---|---|---|---|---|---|
| 0 | 머리말 | 1–11 | 원장. 재는 법 | 0.734, 최소값 | — | 일반(방법) → S-P45 |
| 1 | MT 가 있으면 인덱싱 1.59배 | 13–27 | 200만 합 0.0086→0.0136s. 빈 MT·`__index`·freeze·`rawget` 모두 1.59x | 상속 | 미기재 | 일반 → S-P01 |
| 1-부 | MT 를 버릴 수 없다 | 28–39 | 메소드 54개 복사 시 생성 20.4배, 메모리 22배(96 vs 2112B) | 상속 | 미기재 | 반일반 → S-P05 |
| 2 | `table.move` 는 MT 무관 | 40–55 | 100만 복사: 손 루프 7.6x(MT 없음)/14.3x(MT) 느림 | 상속 | 미기재 | 일반 → S-P03 |
| 3 | 순회 | 56–73 | ipairs 0.39x, `for i=1,n` 1.00, `:Iter()` 2.89, `__iter` 2.86, Fold 2.54 | 상속 | 미기재 | 반일반 → S-P06 |
| 4 | `arr:Iter()` 교집합 타입 유지 | 74–92 | 메소드가 삼중항을 돌려주면 for-in 타입이 산다 | 0.734 타입 검사 | spikes/37 있음 | 반일반(타입) → S-P50 |
| 5 | 정렬 비교자 | 93–107 | 비교자 없음 0.22x, 불리언 1.00, 3방향 래퍼 1.82x | 상속 | 미기재 | 일반 → S-P10, S-P11 |
| 6 | nil 구멍 검사 | 108–121 | `if v ~= nil` 1.13x | 상속 | 미기재 | 일반 → S-P16 |
| 7 | 앞선 세션(09-21) | 122–133 | 가변인자 +8.2%/+12.6%, select vs pack "1.6~2.3배"(방향 모호), 콜백 2.54x | 500만×3 | 미기재 | 일반 → S-P08, S-P09 |
| 8 | Set 을 Map 위에 | 134–155 | 안쪽 표 직접 1.17x, 공개 API 1.85x | 상속 | 미기재 | 고유 |
| 9 | 정렬 병합 vs 해싱 | 156–179 | Union 5.9배, Has 23.4배, FromList 50배 느림 | 상속 | 미기재 | 반일반 → S-P14 |
| 9-부 | 벌크 생성자 | 180–189 | 정렬 컨테이너에 하나씩 Add 2만 = 7.5x | 상속 | 미기재 | 반일반 → S-P14 |
| 10 | 힙 O(n) vs O(n log n) | 190–206 | N 과 무관하게 1.68~1.86배 일정 | 상속 | 미기재 | 일반 → S-P15 |
| 10-부 | 그 밖 | 207–213 | PushPop 1.78배, top-100 힙 1.66배 빠름 | 상속 | 미기재 | 반일반 → S-P15 |
| 11 | checked/unchecked | 214–234 | Max 1.83x 등 | 콜론 호출 | 미기재 | 고유(낡음 → 17절) |
| 11-부 | SortUnchecked 조용히 틀림 | 235–246 | table.sort 가 `#` 를 봐 구멍 뒤가 잘림 | — | 미기재 | 반일반 → S-P33 |
| 12 | 구멍 정리 후 unchecked | 247–284 | k=1 이면 0.87x | 09-30 재측 | 미기재 | 고유 |
| 13 | `Fut` 한 번의 값 | 285–304 | 호출 0.012µs, pcall 0.037, 코루틴 생성+resume 0.174 | 10만×5 | 미기재 | 반일반 → S-P30 |
| 13-2 | 정확성 수정 뒤 | 305–322 | AndThen 0.60→0.95µs | 3회 | 미기재 | 고유 |
| 14 | 호출 모양 | 323–342 | `a:Len()` 1.00, `Arr.Len(a)` 0.82, local 0.64, `a.n` 0.24 | 500만, 상속 | spikes/49 있음 | 일반 → S-P04 |
| 15 | 정렬 가족 | 343–366 | 병합 1.43x, 정렬된 입력 0.10x, quickselect 0.15x, top-k 0.05~0.14x | -O2, 9회 | 미기재 | 일반 → S-P11 |
| 15-2 | M2 실제 구현 | 367–395 | SortBy: 싼 키 1.53x 손해, 비싼 키 4.01→1.97 | -O2, 7회 | 미기재 | 반일반 → S-P12 |
| 15-3 | 선택의 병적 입력 | 396–421 | 끝점 중앙값셋은 O(n²). 사분위 후보 + 예산 폴백이면 0.12x | -O2 | 미기재 | 일반 → S-P13 |
| 16 | MT 를 아예 없애면 | 422–446 | 읽기 0.63x, 쓰기 0.58x, Sum 0.69 | -O2, 9회 | 미기재 | 일반 → S-P02 |
| 16-2 | M0 적용 후 | 447–468 | 쓰기 0.57, 읽기 0.70, 래퍼 구조 0.98~1.01 | -O2, 9회 | 미기재 | 반일반 → S-P02 |
| 17 | `#` 검사 비용 | 469–485 | `#` 한 번 ~90ns(O(log n)) | -O2, 9회 | 미기재 | 반일반 → S-P33 |
| 18 | 컴파일 모드별 | 486–526 | MT 세금: -O1 1.60x, -O2 1.66~1.81x, codegen 1.96~2.00x. 약한 키 레지스트리: 생성 1.66~1.9x, GC 2~3.7배 | 모드 명시, 9회×3 | 미기재(quad 탐사) | 일반 → S-P01, S-P36 |
| 19 | FromIter 반환 개수 | 527–558 | 원소마다 select("#") 2.1x. 구멍에 nil 을 바로 넣으면 생성 9.5배 | -O2, 11/15회 | 미기재 | 일반 → S-P08, S-P17 |
| 20 | n 밖 비우기 | 559–574 | `next(raw,len)` 이 해시에 있는 앞 키를 건너뜀(954/5000) | -O2, 11회 | 미기재 | 반일반 → S-P34 |
| 21 | 트레이트 타입 토큰 | 575–606 | 모듈 변수 키는 상수 접기 불가 → 생성 7~11% 느림. 키 이름 ±5% | -O2 | 미기재 | 반일반 → S-P24, S-P25 |
| 22 | M3 새 함수 | 607–621 | Contains vs Some(클로저) 0.34 | -O2, 7회 | `bench:m3.luau` | 반일반 → S-P10 |
| 23 | Retain 크기 검사 | 622–641 | 검사 10~16% | -O2, 15회 | `bench:retain.luau` | 고유 |
| 24 | Deque 표현 | 642–669 | 두 인덱스 큐 26.1 vs 링 8.65ms. 음수 키 → 해시 | -O2, 9회 | `bench:deque-repr*` | 반일반 → S-P18 |
| 25 | Keys/Values 한 번에 | 670–692 | 0.78~0.88x | -O2, 25회 | `bench:algo-keys` | 고유 |
| 26 | nil·NaN 키 검사 | 693–716 | 조밀 숫자 키 Set 1.09~1.10x | -O2+-O1, 31회 | `bench:key-check` | 반일반 → S-P16 |
| 27 | HashMap.Iter | 717–741 | Luau 래퍼 1.00 → next 삼중항 0.54~0.73 → 테이블 반환 0.11~0.18 | -O2, 25회 | `bench:hash-iter*` | 일반 → S-P07 |
| 28 | 컬렉션 트레이트·Iter | 742–779 | table.create 선할당 0.45→0.33us. `in next, t` = `in t` | -O2, 25회 | `bench:algo-keys-*` | 반일반 → S-P07, S-P48 |
| 29 | HashSet.Iter | 780–801 | 원소→원소 저장이면 순회 0.10~0.18x | -O2, 25회 | `bench:set-iter*` | 반일반 → S-P37 |
| 30 | 정렬 배열 vs 노드 트리 | 802–824 | 넣기: 100개 0.65배, 10만 5.1배 느림 | -O2 | `bench:treemap-vs-nodes` | 반일반 → S-P40 |
| 31 | 트레이트 기본 구현 | 825–853 | 손 루프의 1.65~1.87x | -O2, 21회 | `bench:list-algo` | 고유 |
| 32 | 트레이트 빗나감 경로 | 854–872 | `__mode="k"` 는 줄지 않음(+8MB), `"ks"` 면 0 | -O2, 15회 | `bench:trait-miss` | 고유(+일반 GC) → S-P35 |
| 33 | 묶기 목적지 | 873–889 | size 필드 매번 갱신 1.16~1.18x | -O2, 15회 | `bench:groupby-dest` | 고유 → S-P48 |
| 34 | 노드 모양 | 890–909 | 번호 칸 순회 0.55~0.67x. 번호 칸을 나중에 대입하면 3배 | -O2, 15회 | `bench:node-shape` | 일반 → S-P19 |
| 35 | 원형 vs 연결 덱 | 910–932 | 원형이 1.4~1.7배 빠름 | -O2, 15회 | `bench:deque-kinds` | 반일반 → S-P41 |
| 36 | Join 위 균형 트리 | 933–963 | 공유 Join 2.0~2.2배. 벤치 함정(같은 키) | -O2 | `stl:research/tree-join` | 반일반 → S-P46 |
| 37 | RB vs AVL vs 정렬 배열 | 964–1000 | 섞인 넣고 빼기는 노드 4~13배 우세. GC 로 2배 흔들림 | -O2 | `bench:redblack` | 반일반 → S-P40, S-P42, S-P38 |
| 37-2 | 같은 표면 | 1001–1017 | TreeMap 조회 0.6~0.67x | -O2 | `bench:treemap-surface` | 고유 |
| 38 | 전부 번호 칸 노드 | 1018–1035 | 만들기 0.44x, 224→144B, 해시 필드 하나면 할당 둘 | -O2, 15회 | `bench:node-shape2` | 일반 → S-P20 |
| 38-2 | 접근 함수 경유 | 1036–1061 | `n.value` 5.1, `n[1]` 4.7, 다른 모듈 접근 함수 12.7ns | -O2, 21회 | `bench:node-accessor` | 일반 → S-P21 |
| 38-3 | 바꾼 뒤 | 1062–1082 | 트리 넣기 0.5~0.8 | -O2 | 같은 벤치 | 고유 |
| 39 | 숫자 토큰·함수 번호 | 1083–1112 | 테이블 키 14.8 vs 숫자 키 9.1ns. `impl.X` 3.9 vs `impl[1]` 3.5 | -O2, 21회 | `bench:trait-array` | 일반 → S-P21, S-P23 |
| 40 | 트리 순회자·큐 | 1113–1142 | 순회자 경유 1.3~1.6x. 앞을 nil 로 비우는 큐 1.7x | -O2, 7회, ±30% | `bench:traverse` | 반일반 → S-P18, S-P43 |
| 41 | Heap sift 를 옮김 | 1143–1160 | 루프가 있는 함수는 인라인 안 됨 | -O2 | `bench:heap-complete` | 반일반 → S-P26 |
| 42 | LinkedDeque 도구화 | 1161–1177 | 1.13~1.24x | -O2, 15회 | `bench:linked-position` | 고유 |
| 43 | 노드식 vs 배열식 힙 | 1178–1194 | 노드식 넣기 6.2~6.5x | -O2, 9회 | `bench:complete-node` | 반일반 → S-P41 |
| 44 | 함수 번호 재측(다형) | 1195–1226 | 표를 번갈아 보면 `t.Name` 6.5 vs `t[i]` 4.6ns | -O2, 11회 | `bench:trait-fn-number` | 일반 → S-P22 |
| 45 | 부분 크기 칸 시제품 | 1227–1256 | 넣기 1.1~1.3 | -O2 | `stl:research/tree-size` | 고유 |
| 46 | Eytzinger 배치 | 1257–1282 | 찾기 0.64~0.76x, 순서 순회 4.6~6배 느림 | -O2, 9회 | `bench:eytzinger` | 일반 → S-P39 |
| 47 | FlatMap 구조 도구 | 1283–1304 | 호출 하나 10~15ns | -O2, 15회 | `bench:flatmap-structure` | 반일반 → S-P29 |
| 48 | Stack 트레이트 비용 | 1305–1328 | 감싸는 한 겹 13~17ns. 미리 꺼낸 함수 = 직접 | -O2, 15회 | `bench:stack-trait` | 반일반 → S-P29 |
| 49 | SplitOff·Join | 1329–1362 | 가운데를 가르면 3ms | -O2, 7회 | `bench:split-join` | 고유(59절로 낡음) |
| 50 | 트레이트 재설계 시제품 | 1363–1420 | 진입점 +40 → +26ns | -O2, 15회 | `stl:research/trait-rebuild` | 고유 |
| 51 | 진입점 펼침 | 1421–1440 | 다른 모듈 호출 하나를 덜면 9~15ns | -O2, 15회 | `bench:entry-inline` | 반일반 → S-P29 |
| 52 | 미리 짓기·다시 짓기 | 1441–1462 | require 시간 비교는 같은 경로에서 | -O2, 15회 | `bench:entry-inline` | 반일반(방법) → S-P46 |
| 53 | 숫자 토큰 진입점 | 1463–1493 | 가변인자 1.5~2ns/호출. 상수 아닌 이름 +1.5~3ns | -O2, 15회 | `stl:research/trait-numbered` | 반일반 → S-P08, S-P24 |
| 54 | 새 시스템 진입점 | 1494–1510 | 가변인자는 원인 아님(±2ns) | -O2 | 미기재 | 고유(53절과 충돌) |
| 55 | A→B 변환자 | 1511–1532 | 지역 함수 인라인 0ns. 필드 8.1, rawget 11.5ns. 클로저 +5~8ns | -O2, 500만×5 | 미기재 | 일반 → S-P26, S-P27, S-P32 |
| 56 | 칸 읽기 전용 공개 | 1533–1552 | `a[i]` 5.5, Get 15.1ns. `::` 캐스트 0 | -O2, 5회 | README 뿐 | 반일반 → S-P31 |
| 57 | Arr 칸을 안쪽 표로 | 1553–1600 | 안쪽 표를 지역으로 안 받으면 1.43x. `{...}`(1024 인자) 1.12x | **0.742** -O2, 7회×3 | `stl-luau-scratch/arr-split/bench` | 반일반 → S-P28, S-P09, S-P19 |
| 58 | ECS 1만 엔티티 | 1601–1614 | 해시 1.44 vs 엔티티마다 dispatch 2.60ms | -O2, 버전 미기재 | `arr-split/programs` | 고유 → S-P44 |
| 59 | 순위·역순 순회 | 1615–1684 | 스택 부분 트리 세기 20~25ns/노드 vs 40~70 | -O2 | `stl-luau-scratch/sorted-rank` | 고유(일부 반일반) → S-P43 |
| 60 | 메타테이블 객체 | 1685–1698 | `o.n`·`o.data[i]` 는 MT 무관. 생성 +14~21ns. 메서드 27.4 / 모듈 함수 24.1 / 지역 20.6ns | -O1/-O2, 버전 미기재 | `stl:research/class-like/bench*.luau` | 일반 → S-P02, S-P04, S-P05 |

**정리**
- 일반 절은 약 25개다(1,2,5,6,7,10,14,15,15-3,16,18,19,27,34,38,38-2,39,44,46,55,60 등). 반일반은 약 20개, 고유는 약 15개다.
- 1698줄 가운데 이전할 실질은 약 400줄 분량이다. 표 §2 의 S-P01~S-P51 이 그 압축본이다.

### 1-3. luau-perf references 분할안

| reference | 담을 후보 | 분량 | 메모 |
|---|---|---|---|
| `SKILL.md` | 색인과 규칙 한 줄씩. "수치 대부분은 0.734 `-O1`, 배포는 `-O2`(+native)" 경고 | 50줄 | 증상→파일 라우팅 표 |
| `metatables.md` | S-P01, S-P02, S-P05, S-P32, S-P04 교차참조, S-135(메타메소드 규약) | 100줄 | ★1 소스 근거를 함께 싣는다. 모드별 표(18절)도 넣는다 |
| `tables.md` | S-P03, S-P17, S-P18, S-P19, S-P20, S-P21, S-P23, S-P33, S-P34, S-P48, S-102·D-R34 병합분 | 180줄 | 가장 큰 파일. 배열부/해시부 성장 규칙, 생성자, 메모리 |
| `iteration.md` | S-P06, S-P07, S-P16, S-P28 | 80줄 | 일반화 순회 > next 삼중항 > 래퍼 |
| `calls-and-closures.md` | S-P04, S-P08, S-P09, S-P10, S-P27, S-P29, S-P30, S-P44 | 130줄 | 가변인자·클로저·dispatch |
| `strings.md` (신설) | M-04, M-05, D-R28(+T-48) | 60줄 | `..=` O(n²), gmatch 기준선, 패턴 역추적 |
| `optimizer-and-native.md` | S-P22, S-P24, S-P26, S-P31, S-P49, M-06, S-P01 의 codegen 줄 | 90줄 | native 실측이 18절과 M-06 뿐이라 얇다 → **재측 과제 목록**을 둔다 |
| `gc-and-memory.md` | S-P35, S-P36, S-P37, S-P51, (R-22·R-23 은 luau-style/weak-tables 와 교차참조) | 70줄 | "GC 는 할당이 있어야 진행"(S-P51) 포함 |
| `algorithms-and-structures.md` | S-P11~S-P15, S-P39~S-P43, M-08 | 150줄 | 반일반이 많다 → 결론만 남기고 수치는 원천 링크로 |
| `benchmarking-method.md` | S-P25, S-P38, S-P45(+S-122·M-07), S-P46, S-P47 | 90줄 | 래퍼 금지, 최소값, 프로세스 반복, 같은 경로 require, `-O1`/`-O2`/codegen 모두 |
| (roblox-luau 쪽) `perf.md` | D-R03, T-54 | 30줄 | Studio 실측(바인더블 복사 비용, Part 생성 비용) |

- **분할 원칙**: "무엇을 바꿀까"(구조) 4개 + "어떻게 실행되나"(최적화기·GC) 2개 + "어떻게 재나"(방법) 1개 + 알고리즘 1개. SKILL.md 의 라우팅 표에서 질문 → 파일로 연결한다.
- **이전 전 선행 과제**
  - S-P01·S-P03~S-P06·S-P30 은 0.734 `-O1` 에서만 쟀다. 이 6개를 0.742 와 `-O2`/`--codegen` 에서 재측한다.
  - 1~21절 벤치 스크립트를 luau-kb `snippets/perf/` 로 새로 쓴다(문서에 위치가 없다).

---

## 2. 후보 표

열 정의는 공통 형식을 따른다. 병합된 ID 는 §5 에 있다(ID 번호에 빈칸이 있는 이유).

| ID | 주제 | 주장 한 줄 | 원천(경로:줄) | 검증 | 일반/고유 | 대상 스킬/reference | luau-kb 중복 | 비고 |
|---|---|---|---|---|---|---|---|---|
| S-P01 | perf | 메타테이블이 붙은 테이블 **자신의 정수 키 칸** `t[i]` 읽기·쓰기는 MT 가 있기만 해도 느리다: -O1 1.59~1.60x, -O2 1.66~1.81x, `--codegen -O2` 1.96~2.00x. 빈 MT·`__index`·freeze·`rawget` 모두 같다 | perf:15-26, perf:492-502; stl:papers/08-trait-retrospective.md:30; stl:base/architecture.md:296 | 실측 | 일반 | luau-perf/metatables.md | 없음 | 0.734, 200만 합, 9회×3. ★1 소스 확인: 0.742 `lvmexecute.cpp:779,809,836,864` 의 빠른 경로가 `!h->metatable` 을 요구한다. 0.742 실측 재측은 없음 [정정: 유지. "`rawget` 도 못 피한다" 그대로 — `.claude/handoff/stl-luau-corrections.md`] |
| S-P02 | perf | 상수 문자열 필드(`o.n`)와 MT 없는 안쪽 표를 거친 읽기(`o.data[i]`)는 MT 영향이 0이다. 원소를 MT 없는 안쪽 표에 두면 세금이 사라진다. 원소가 겉표에 직접 사는 구조만 MT 제거 이득이 크다(쓰기 0.57x, 읽기 0.63~0.70x), `{data,size}` 래퍼는 0.98~1.01x | perf:1689-1698, perf:430-445, perf:452-467; stl:research/class-like/README.md:12,15 | 실측 | 일반 | luau-perf/metatables.md | 없음 | -O2. S-P01 의 적용 범위를 한정한다(모순 아님) |
| S-P03 | perf | `table.move` 는 메타메서드를 보지 않고 C 에서 복사한다. 100만 복사에서 손 루프가 7.6x(MT 없음)/14.3x(MT) 느리다. 벌크는 `table.move`·`table.create` | perf:44-54; stl:conventions.md:148 | 실측 | 일반 | luau-perf/tables.md | 없음 | 0.734 -O1. 재측 필요 |
| S-P04 | perf | 호출 모양: `obj:M()` 1.00 / `Mod.M(obj)` 0.82 / `local M` 0.64(0.734). 재측: 메서드 27.4~28.1, 모듈 함수 24.1~25.4, 지역 20.6~20.8ns. -O1=-O2. 뜨거운 루프에서는 `local F = M.F` | perf:327-336, perf:1696-1698; stl:conventions.md:149; stl:research/class-like/README.md:13-14 | 실측 | 일반 | luau-perf/calls-and-closures.md | 없음 | 메서드 웃돈이 14절은 18%, 60절은 12%(모순 표 19). `stl:audit/arr-type-redesign/spikes/49` |
| S-P05 | GC·수명 | 생성: `{n=0,data={}}` 50ns 에 setmetatable 을 붙이면 +14~21ns. 메소드 54개를 인스턴스에 복사하면 생성 20.4배, 메모리 22배(96 vs 2112B) → 작은 객체가 많으면 MT 방식 | perf:30-36, perf:1694, perf:459, perf:466-467; tbox:docs/redesign-precedents.md:13,33-34 | 실측 | 일반 | luau-perf/metatables.md | 없음 | tbox 는 stl 수치를 인용(X-21 병합) |
| S-P06 | perf | MT 컨테이너 200만 순회: `ipairs` 0.39x < `for i=1,n` 1.00 < 콜백 Fold 2.54x < 메소드 이터레이터·`__iter` 2.86~2.89x | perf:60-72, perf:130 | 실측 | 반일반 | luau-perf/iteration.md | 없음 | MT 세금이 섞인 비교다. 평범한 테이블의 ipairs vs 숫자 for 는 미측정 |
| S-P07 | perf | 일반화 순회 `for k,v in t` 는 `next` 를 감싼 Luau 래퍼보다 약 9배, 함수가 돌려준 `next,t` 삼중항보다 약 5배 빠르다(1000개 29.0→15.9→3.2µs). `in next, t` 리터럴은 `in t` 와 같고, `next` 를 값으로 넘기면 느리다. 순회 API 는 표를 그대로 내줄 수 있는지 먼저 본다 | perf:723-736, perf:766-771; stl:archive/question-resolved.md:986-988,1660-1670; stl:papers/04-surface-gaps.md:147 | 실측 | 일반 | luau-perf/iteration.md | 없음 | -O2, 25회. `bench:hash-iter*.luau` |
| S-P08 | perf | 가변인자 비용: `(self, first, ...)` +8.2%, `(self, ...)` +12.6%, 전달 1.5~2ns/호출. 원소마다 `select("#",...)` 헬퍼를 부르면 루프가 2.1x → 한 번만 센다. 가변 편의를 고정 경로에 합치면 단일 호출이 8~13% 느려진다 | perf:124-128, perf:529-540, perf:1491; stl:archive/conventions-2026-11-04.md:582-603 | 실측 | 일반 | luau-perf/calls-and-closures.md | 없음 | 54절(perf:1508)의 "원인 아님 ±2ns" 와 충돌(잡음 경계) |
| S-P09 | perf | `{...}` 는 인자 32개까지 `table.pack` 보다 빠르나(0.80~0.99x) 1024 인자에서는 1.12x 느리다. `table.pack` 은 `n` 을 남긴다. 7절의 "select 루프 vs table.pack 1.6~2.3배 빠름" 은 방향이 모호하고, 인자가 많으면 `select(i, ...)` 루프는 O(n²) | perf:1589, perf:129; stl:conventions.md:148 | 실측 | 반일반 | luau-perf/calls-and-closures.md | 없음 | 0.742 -O2. 7절은 재측 필요 |
| S-P10 | perf | 원소마다 클로저 콜백: `Some(a, function(v) return v==x end)` 대비 직접 루프 0.34x. 3방향 비교자를 불리언으로 감싸 `table.sort` 에 넘기면 1.82x. 순회자 경유 중위 순회는 손 `Next` 의 1.3~1.6x | perf:614-619, perf:97-104, perf:1136-1137; stl:base/architecture.md:232-234 | 실측 | 일반 | luau-perf/calls-and-closures.md | 없음 | 5절은 -O1, 22·40절은 -O2 |
| S-P11 | perf | `table.sort` 는 비교자가 없으면 있을 때의 0.22~0.27x. 순수 Luau 안정 병합 정렬 1.43~1.44x(정렬된 입력 0.10x), quickselect 0.15~0.18x, 힙 top-k 0.05~0.14x(기준 sort(lt)) | perf:97-104, perf:350-365, perf:374-379 | 실측 | 일반 | luau-perf/algorithms-and-structures.md | 없음 | -O2, 10만, 7~9회 |
| S-P12 | perf | 키 정렬: 키가 필드 읽기면 decorate(SortBy)가 1.53x 손해, `string.lower` 처럼 비싸면 4.01→1.97x 로 이득 | perf:381-392 | 실측 | 일반 | luau-perf/algorithms-and-structures.md | 없음 | -O2 |
| S-P13 | perf | quickselect 의 중앙값셋을 끝점으로 고르면 "정렬 + 끝에 최솟값" 입력에서 O(n²)(n=16000 1.4s). 1/4·1/2·3/4 후보 + 2·log₂n 예산 폴백(table.sort)이면 0.12x. McIlroy 적대자 751n→70n | perf:398-420 | 실측 | 일반 | luau-perf/algorithms-and-structures.md | 없음 | -O2 |
| S-P14 | perf | C 해싱이 Lua 비교자로 하는 정렬 병합을 이긴다(10만 Union 5.9배, Has 23.4배, FromList 50배). 정렬 배열에 하나씩 넣기는 O(n²)(2만 개 7.5x) → 일괄 정렬해 짓는다 | perf:162-178, perf:182-188 | 실측 | 반일반 | luau-perf/algorithms-and-structures.md | 없음 | 0.734 -O1 [정정: 정렬 병합이 해시보다 느리다는 결론은 원소마다 클로저 비교자·레코드 할당이 있는 컨테이너 연산에 한정. 이미 정렬된 정수 배열 병합은 해시의 0.27~0.38배 — `.claude/handoff/stl-luau-corrections.md` S01, `luau-kb/skills/luau-perf/references/algorithms-and-structures.md` §2·§8] |
| S-P15 | perf | 힙 짓기 O(n) vs Push 반복 O(n log n): 무작위 입력에서는 N 과 무관하게 1.7배로 일정하다(평균 sift-up 깊이가 상수). PushPop 1.78배, top-100 은 힙이 전체 정렬보다 1.66배 빠르다 | perf:194-212 | 실측 | 일반 | luau-perf/algorithms-and-structures.md | 없음 | 0.734 -O1 |
| S-P16 | perf | 뜨거운 루프의 nil 검사 `if v ~= nil` 1.13x. 조밀 숫자 키 Set 의 nil/NaN 검사 1.09~1.10x, 해시 경로에서는 잡음에 묻힌다 | perf:112-119, perf:699-710 | 실측 | 일반 | luau-perf/iteration.md | 없음 | 6절 -O1, 26절 -O2 |
| S-P17 | perf | 배열을 채우며 구멍 자리에 nil 을 바로 대입하면 배열부가 자라지 못해 뒤 원소가 해시로 간다: 구멍 1/2 에서 생성 9.5배, 이후 인덱싱 4.5배(45.7 vs 10.1ms). 자리표시자로 채우고 마지막에 nil 로 바꾼다 | perf:542-557 | 실측 | 일반 | luau-perf/tables.md | 없음 | -O2, 15회 |
| S-P18 | perf | 배열부 크기는 늘어날 때 채워진 비율로 정해진다. 그래서 앞에서 nil 로 비워 가는 배열 큐는 1.7x, 인덱스가 계속 커지는 두 인덱스 큐는 링 버퍼의 3배(26.1 vs 8.65ms), 음수 키 PushFront 는 해시로 가서 2.5배. `table.remove(t,1)` 은 O(n)(용량 10만에 30만 개 넣기 4.7초). 처방: head 번호만 올리기 / 링 버퍼 | perf:1138-1141, perf:644-653; stl:conventions.md:128; stl:base/architecture.md:199; dvr:2026-10-19-shared-specs.md:105; dvr:2026-10-19-client-code.md:116-120 | 실측 | 일반 | luau-perf/tables.md | 없음 | -O2. S-102·D-R34 병합 |
| S-P19 | perf | 번호 칸은 테이블 생성자에 같이 적는다. `{value=v}` 뒤에 `node[1]=…` 를 대입하면 만들기가 3배(21.3 vs 6.8ms) → `{prev, nil, value=v}` 처럼 자리를 잡는다. 생성자 한 번이 `table.create` 후 대입보다 0.69~0.93x | perf:898-906, perf:1585; stl:conventions.md:129 | 실측 | 일반 | luau-perf/tables.md | 없음 | -O2. 57절 0.742 |
| S-P20 | perf | 레코드를 전부 배열 칸으로 쓰면 이름 필드 대비 트리 노드(6칸) 만들기 0.44x, 메모리 224→144B, 접근 0.69x. 이름 필드가 하나라도 있으면 해시부가 따로 할당돼 할당이 둘이 된다(만들기 2.3배, 메모리 1.56배) | perf:1024-1031, perf:898-904; stl:base/architecture.md:207-209 | 실측 | 일반 | luau-perf/tables.md | 없음 | -O2, 20만 노드. S-103 병합 |
| S-P21 | perf | 단건 접근: 상수 문자열 필드 `n.value` 5.1ns ≈ `n[1]` 4.7ns(`impl.X` 3.9 vs `impl[1]` 3.5, 인라인 캐시). 다른 모듈의 접근 함수를 거치면 12.7ns(2.5배) | perf:1042-1057, perf:1096-1105 | 실측 | 일반 | luau-perf/tables.md | 없음 | -O2, 21회 |
| S-P22 | perf | 상수 키 필드 인라인 캐시는 명령어 자리마다 하나다. 한 자리가 칸 배치가 다른 표들을 번갈아 보면 `t.Name` 6.5ns vs `t[i]` 4.6ns(1.4배). 표 하나면 키 162개에서도 0.4ns 차 | perf:1204-1222 | 실측 | 일반 | luau-perf/optimizer-and-native.md | 없음 | -O2, 11회. `bench:trait-fn-number.luau` |
| S-P23 | perf | 해시 조회 키 종류: 테이블 키 14.8ns vs 숫자 키 9.1ns | perf:1096-1099, perf:1103 | 실측 | 일반 | luau-perf/tables.md | 없음 | -O2 [정정: 숫자 키가 싼 것은 배열부 정수 키(0.49~0.76배)만. 해시부 정수·실수 키는 테이블 키보다 1.16~1.43배 느리다 — `.claude/handoff/stl-luau-corrections.md` S04, `luau-kb/skills/luau-perf/references/tables.md` §8] |
| S-P24 | perf | 상수 접기: 다른 모듈에서 받은 상수(`const K = M.K`, `Trait.TYPE_KEY`)로 `t[K] = v` 하면 상수 키 명령을 못 써 생성이 7~11% 느리다 → 리터럴이나 같은 파일의 리터럴 지역 상수로 적는다. 상수가 아닌 이름의 문자열 조회는 1.5~3ns 더 든다 | perf:597-600, perf:1488-1489; stl:conventions.md:42; stl:base/architecture.md:172,209 | 실측 | 일반 | luau-perf/optimizer-and-native.md | 없음 | -O2. "재대입 없는 리터럴 초기화 지역만 접는다" 는 원리는 스니펫으로 확인 필요. S-101 병합 |
| S-P25 | perf | 키 이름만 바꿔도 해시 칸 배치가 바뀌어 같은 모양의 생성 시간이 ±5% 흔들린다. 고르게 나은 이름은 없다 | perf:601-605 | 실측 | 반일반 | luau-perf/benchmarking-method.md | 없음 | 해석 주의용 |
| S-P26 | perf | -O2 인라인: 같은 모듈의 루프 없는 지역 함수는 인라인돼 0ns. 다른 모듈의 함수와 루프가 있는 함수는 인라인되지 않는다 → 같은 파일에 둔 흉내 함수로 벤치하면 비교가 틀어진다 | perf:1518, perf:1530, perf:1157-1158, perf:1424, perf:1696 | 실측 | 일반 | luau-perf/optimizer-and-native.md | 없음 | S-116(에러 level)의 원인과 같은 메커니즘 |
| S-P27 | perf | 업밸류로 값을 든 클로저 판이 지역 함수 판보다 5~8ns 비싸다(16.4 vs 8.1ns). 벤치 루프에서 한쪽만 업밸류로 읽으면 0.77x 같은 거짓 차이가 난다 | perf:1519-1531, perf:1599 | 실측 | 일반 | luau-perf/calls-and-closures.md | 없음 | -O2 [정정: `-O1` 에서는 차이 없음(0.95~0.97). `-O2` 3.5배·native 6.3배는 지역 함수가 인라인된 결과. 결론(한쪽만 업밸류면 거짓 차이)은 유지 — `.claude/handoff/stl-luau-corrections.md` S07, `luau-kb/skills/luau-perf/references/calls-and-closures.md` §7] |
| S-P28 | perf | 필드를 거친 인덱싱은 루프 밖에서 지역으로 받는다. `a.data[i]` 를 그대로 쓰면 1.43배(1024개 6247 vs 4356ns) | perf:1584, perf:1587 | 실측 | 일반 | luau-perf/iteration.md | 없음 | 0.742 -O2 |
| S-P29 | perf | 함수를 한 겹 감싸면 호출당 13~17ns, 호출 하나를 더하면 10~15ns. 테이블에서 함수를 루프 밖에서 미리 꺼내 두면 직접 호출과 같다(59.7 vs 59.8ns) | perf:1310-1321, perf:1299, perf:1405-1407 | 실측 | 일반 | luau-perf/calls-and-closures.md | 없음 | -O2, 15회 |
| S-P30 | perf | 평범한 함수 호출 0.012µs, `pcall` 0.037µs, `coroutine.create`+`resume` 0.174µs | perf:289-293 | 실측 | 일반 | luau-perf/calls-and-closures.md | 없음 | 0.734 -O1, 10만×5 |
| S-P31 | perf | 타입 캐스트 `::` 의 런타임 비용은 0이다(22.2~24.2 → 22.3~23.5ns, 잡음 안) | perf:1550-1551 | 실측 | 일반 | luau-perf/optimizer-and-native.md | 없음 | -O2. 단 R-12(다중 반환 절단)는 의미가 바뀌는 별개 문제 |
| S-P32 | perf | `rawget` 은 호출 비용이 있어 필드 읽기보다 비싸다(`v.__type` 8.1ns, `rawget` 11.5, `type()`+`rawget` 14.6). MT 정수 칸 세금도 못 피한다 | perf:1519-1521, perf:25-26, perf:1094 | 실측 | 일반 | luau-perf/metatables.md | 없음 | -O2 |
| S-P33 | runtime·엔진 | `#` 는 O(log n), 20만 배열에서 약 90ns. `table.sort`·`insert`·`concat` 은 n 이 아니라 `#` 범위를 본다(구멍 뒤 잘림·밖 값 섞임) | perf:471-480, perf:241 | 실측 | 일반 | luau-perf/tables.md | 일부(kb:luau-types/references/solver-limits.md §3 의 `#` 경계 줄) | perf:244-245 정정 꼬리표는 라이브러리 동작 쪽 이야기다 [정정: `#` 는 경계 캐시가 맞으면 사실상 O(1)(필드 읽기의 0.83~1.03배), 경계가 바뀌는 쓰기를 끼우면 2.0~2.5배. 90ns 는 캐시 빗나감 — `.claude/handoff/stl-luau-corrections.md` S06, `luau-kb/skills/luau-perf/references/tables.md` §8] |
| S-P34 | runtime·엔진 | `next(t, k)` 로 중간부터 순회하면 k 가 해시부에 있을 때 그 앞 키를 건너뛴다(무작위 5000건 중 954 오답). 키 전체를 빈 순회만 해도 복사 비용과 같다 | perf:570-573 | 실측 | 일반 | luau-perf/tables.md | 없음 | -O2 |
| S-P35 | GC·수명 | 약한 키 표 `__mode="k"` 는 많이 넣었다 버려도 칸 수가 줄지 않는다(40만 종 +8MB/+32MB). `"ks"`(shrinkable)면 0 | perf:869-871 | 실측 | 일반 | luau-perf/gc-and-memory.md | 없음 | 리뷰어 실측 |
| S-P36 | GC·수명 | 약한 키 레지스트리로 정체성을 매기면 작은 객체 생성 경로가 1.66~1.9배, 20만 개가 살아 있을 때 풀 GC 가 2~3.7배. 조회 경로는 같다. 비공개 센티넬 키는 `pairs`·`table.clone` 으로 새어 위조를 막지 못한다 | perf:504-525; stl:papers/05-quad-survey.md:68-91 | 실측 | 반일반 | luau-perf/gc-and-memory.md | 없음 | -O1. quad brand-plan 과 관점 차(모순 표 4). S-110 병합 |
| S-P37 | GC·수명 | gcinfo 기준 크기: 빈 MT 를 붙인 작은 배열 96B, `{[T]=true}` 원소 1개 96B, 평탄 배열 n=0 112B / n=8 240B / n=1024 16496B, 안쪽 표로 나누면 +112B, 6칸 노드 144B. 값 칸에 `true` 대신 원소를 넣어도 메모리는 같다 | perf:35, perf:151-154, perf:1592-1597, perf:1244, perf:795-796 | 실측 | 반일반 | luau-perf/gc-and-memory.md | 없음 | 0.734·0.742 혼재 |
| S-P38 | perf | 노드 할당이 많은 벤치는 GC 시점 때문에 실행마다 2배까지 흔들린다 → 비율은 같은 실행 안에서만 본다. 흩어진 노드 순회는 ±30%, 흩어진 순서로 지은 트리는 정렬로 지은 트리의 3~4배 | perf:997-998, perf:1115-1117, perf:1651 | 실측 | 일반 | luau-perf/benchmarking-method.md | 없음 | -O2 |
| S-P39 | perf | Eytzinger(완전 이진) 배치 탐색은 정렬 배열 이분 탐색의 0.64~0.76x(N=100만 616→393ns), 순서 순회는 4.6~6배 느림 | perf:1265-1281 | 실측 | 일반 | luau-perf/algorithms-and-structures.md | 없음 | -O2 |
| S-P40 | perf | 정렬 배열(`table.move` 로 밀기) vs 노드 균형 트리: 무작위 넣기는 수천 이하에서 배열이 빠르지만(100개 0.65배) 1만 1.42배, 10만 5.1배 느리고, 넣고 빼기가 섞이면 10만에서 13배. 순서대로 넣기·일괄 짓기·순회는 배열이 우세 | perf:808-823, perf:972-999, perf:1005-1016 | 실측 | 반일반 | luau-perf/algorithms-and-structures.md | 없음 | -O2 |
| S-P41 | perf | 양끝 연산은 링 버퍼 덱이 연결 리스트 덱보다 1.4~1.7배 빠르다(노드 할당 비용). 배열 힙이 노드 힙보다 넣기 6.2~6.5배 빠르다 | perf:914-927, perf:1080, perf:1183-1186 | 실측 | 반일반 | luau-perf/algorithms-and-structures.md | 없음 | -O2 |
| S-P42 | perf | 레드블랙 vs AVL: 무작위 넣기 0.85~1.0, 오름차순은 AVL 이 0.7~0.9 로 우세, 잇기는 AVL 4.0 vs RB 7.5µs | perf:994-996, perf:1347-1348 | 실측 | 반일반 | luau-perf/algorithms-and-structures.md | 없음 | -O2 |
| S-P43 | perf | 트리 순회: 부모 칸 따라가기 = 명시적 스택 = 재귀+콜백. 부분 트리를 명시적 스택으로 통째 세면 20~25ns/노드 vs 이웃 따라가기 40~70ns | perf:1121-1135, perf:1633-1638 | 실측 | 반일반 | luau-perf/algorithms-and-structures.md | 없음 | -O2 |
| S-P44 | perf | 동적 dispatch(구현 표 조회 + 간접 호출)는 직접 호출보다 +30~44ns(1.9~2.3배). 원소마다 간접 호출을 거친 순회는 직접 인덱싱의 2.5~2.8배. ECS 1만 엔티티에서 엔티티마다 dispatch 하면 프레임 1.44→2.60ms. 조회를 루프 밖으로 빼면 직접과 같다 | perf:929-931, perf:776-778, perf:1605-1613; stl:base/container-design-notes.md:74-78; stl:papers/07-trait-defaults-and-nodes.md:89-102 | 실측 | 반일반 | luau-perf/calls-and-closures.md | 없음 | -O2. "Luau 제네릭은 지워져 정적 디스패치가 없다" 는 원리 서술 동반. S-106 병합 |
| S-P45 | perf | 재는 법: 래퍼 클로저 없이 실제 호출 모양으로 루프에서 직접, 여러 번 재 최소값, 전·후를 번갈아, 프로세스 여러 번(7회×3), 모드 명시(CLI 기본 -O1 / Roblox 배포 -O2 / codegen). 시행 사이 `collectgarbage("collect")`. 격리 마이크로벤치에서 이긴 변경이 실제 코드에서 8~20% 느려진 사례가 있다 | perf:8-9, perf:488-502, perf:1555; stl:conventions.md:147; mrow-rv:832,856-862 | 실측 | 일반 | luau-perf/benchmarking-method.md | 없음 | S-122·M-07 병합. "Roblox 배포 -O2" 는 서술(모순 표 2) |
| S-P46 | perf | 벤치 함정: require 시간은 두 사본을 같은 경로에 두고 비교한다(경로 탓 3ms 차). 같은 키로 split 을 반복하면 그 노드가 뿌리가 돼 O(1) 로 보인다. "생성 시간 빼기" 는 흔들려 결론을 낼 수 없다 | perf:1459-1461, perf:961-962, perf:634-636 | 실측 | 일반 | luau-perf/benchmarking-method.md | 없음 | — |
| S-P47 | perf | 차수만 보고 "훨씬 빠르다" 고 쓰지 않는다. O(n+m) 정렬 병합이 해시에 5.9~50배 지고, O(n) 힙 짓기는 상수 1.7배다. 이 런타임에서는 C 로 내려가는 쪽이 거의 늘 이긴다 | perf:169-172, perf:204-205 | 실측 | 반일반 | luau-perf/benchmarking-method.md | 없음 | 원칙 [정정: S-P14 와 같음. "C 로 내려가는 쪽이 늘 이긴다"는 과일반화 — `.claude/handoff/stl-luau-corrections.md` S01] |
| S-P48 | perf | 결과 크기를 알면 `table.create(n)` 으로 미리 잡는다(N=10 에서 0.45→0.33µs, 크면 차이 없음). 크기 필드를 원소마다 올리기보다 지역으로 세고 한 번 쓰는 쪽이 1.16~1.18배 빠르다 | perf:757-758, perf:768, perf:884-886 | 실측 | 반일반 | luau-perf/tables.md | 없음 | -O2 |
| S-P49 | perf | fastcall 은 내장 라이브러리 함수만 받는다. `buffer.*` 등이 네임스페이스 함수인 이유에는 인덱싱 속도도 있다 | perf:424-426, perf:441 | 서술 | 반일반 | luau-perf/optimizer-and-native.md | 없음 | 사용자 발언 기반, 미측정 |
| S-P50 | 기타 | (타입) 교집합 타입 컨테이너에서도 메소드가 이터레이터 삼중항을 돌려주면 for-in 루프 변수 타입이 산다(인덱서·`__iter` 경유는 잃음). 이터레이터는 `(number, T)` 로 선언하고, `(number?, T?)` 면 옵셔널이 된다 | perf:76-91 | 실측 | 반일반 | luau-types/(신설) iteration-typing.md | 없음 | 0.734. `stl:audit/arr-type-redesign/spikes/37`. 0.742 재확인 필요 |
| S-P51 | GC·수명 | Luau GC 는 할당이 있어야 진행한다. 유휴 클라이언트 힙이 12초간 56MB 그대로였고, 짧은 쓰레기를 할당하자 약 10MB 로 돌아왔다. 힙 측정은 churn 뒤 최저값으로 하고, 빌드는 별도 함수로 한다(지역 변수가 붙잡음) | quad:audit/perf-studio-2026-10-22/REPORT.md:14-17 | 실측 | 일반 | luau-perf/gc-and-memory.md | 없음 | Studio Play. quad 출처지만 stl 에 없는 보완 사실이라 넣었다 |
| S-111 | runtime·엔진 | 가변인자 내장 함수(`math.max`, `bit32.bor`)를 `(값, 위치, 뷰)` 로 부르는 콜백 자리에 그대로 넘기면 위치·뷰까지 인자로 먹어 결과가 틀리거나 라이브러리 줄에서 에러가 난다. 타입 검사로는 못 막는다 → 람다로 감싼다 | stl:conventions.md:77; stl:base/trait-system.md:90; stl:rules/src-trait.md:17 | 실측 | 일반 | luau-style/callbacks.md | 일부(kb:luau-types/references/variance.md §6 파라미터 수 서브타이핑이 타입 쪽 뿌리) | 재현 `stl:audit/arr-type-redesign/spikes/64`. 한 줄 재현 가능 |
| S-112 | runtime·엔진 | 구멍 있는 배열은 칸이 해시부로 갈 수 있어 `for … in` 순서가 약속되지 않는다. `for _, v in t` 는 `n`·`__type` 같은 문자열 키도 돌고 strict 에서 진단이 0건이다. `#` 는 아무 구멍 경계나 돌려준다 → 순서가 필요하면 명시 길이의 숫자 루프 | stl:conventions.md:100; stl:archive/question-resolved.md:74,1772; stl:archive/conventions-2026-11-04.md:322-326 | 실측 | 일반 | luau-style/tables.md | 일부(kb:luau-types/references/solver-limits.md §3) | 순서 비약속은 서술이라 재현 스니펫이 필요. X-15 와 같은 reference |
| S-113 | runtime·엔진 | `table.clone`·`table.freeze` 는 모두 얕다(안쪽 표는 공유되고 여전히 바꿀 수 있다). `{ n, data }` 래퍼에 `#` 를 쓰면 0 이다 | stl:conventions.md:100; dvr:2026-10-19-shared-specs.md:99; dvr:2026-10-20-action-check.md:119,132 | 실측 | 일반 | luau-style/tables.md | 없음 | D-R33 병합 |
| S-114 | runtime·엔진 | `a % b` 는 \|a\| > 2^53 에서 틀린다(`math.fmod` 에 음수 보정). `table.create` 의 길이 상한은 2^26 | stl:conventions.md:109; stl:archive/conventions-2026-11-04.md:500-503 | 실측 | 일반 | luau-style/numbers.md | 없음 | `%` 쪽은 서술이라 재현 필요. 2^26 은 버전 의존 가능 |
| S-115 | runtime·엔진 | `t[nil]=v` 와 `t[0/0]=v` 는 원시 에러("table index is nil"/"is NaN")로 그 줄을 가리키고, 조회는 `nil` 이다. NaN 은 `==` 로 못 찾는다. 키에서 `0` 과 `-0` 은 같다. `math.floor(math.huge)==math.huge` 라서 `x==floor(x)` 정수 검사를 ±inf 가 통과한다 → 2^53 상한과 inf 를 따로 막는다 | stl:archive/question-resolved.md:747-748,755,915-917; stl:conventions.md:110; dvr:2026-10-19-server-security.md:205-223,350; dvr:2026-10-20-actions-security.md:127 | 실측 | 일반 | luau-style/numbers.md | 없음 | luau CLI. D-R05 병합. X-14(NaN 비교)와 같은 reference |
| S-116 | 에러 | 손으로 센 `error(msg, 2\|3)` 의 level 은 -O2 인라인에서 틀린다. 어느 헬퍼가 인라인될지는 휴리스틱이라 함수마다 다르고, -O1 만 돌리는 테스트는 못 본다. 해법: `debug.info` 로 스택을 걸어 "등록된 라이브러리 파일이 아닌 첫 프레임" 에서 던진다(모듈마다 `debug.info(1,"s")` 로 소스 등록). 로컬 직접 호출은 인라인되고 테이블 필드 경유만 프레임이 남는다 | stl:conventions.md:136; stl:papers/05-quad-survey.md:100-128; stl:archive/conventions-2026-11-04.md:512-518; rbvm-sib:215-219 | 실측 | 일반 | luau-style/errors.md | 없음 | luau CLI -O1 vs -O2. R-44 병합. "라이브 Roblox 는 -O2" 는 서술(모순 2) |
| S-117 | 에러 | `error(msg, 0)` 으로는 새 에러와 되던지기를 구분할 수 없다. `pcall(f, …)` 로 Luau 함수를 C 가 바로 부르면 level 2 위치가 없어 줄 정보가 사라진다 | stl:archive/conventions-2026-11-04.md:525-526,538-539; stl:conventions.md:140 | 실측 | 일반 | luau-style/errors.md | 없음 | R-11(되던질 때 `error(msg,0)`)과 같은 reference |
| S-118 | 테스트 | 에러 테스트는 메시지와 정확한 사용자 줄을 같이 단언한다(메시지만 보면 level 이 틀려도 통과한다는 것을 돌연변이로 확인). 기대 줄은 그 자리에서 `debug.info(1,"l")+1` 로 잰다(헬퍼도 -O2 에서 인라인됨). 테스트는 -O1 과 -O2 를 둘 다 돌린다 | stl:conventions.md:140; stl:rules/tests.md:14; stl:project-context.md:59; stl:archive/conventions-2026-11-04.md:530-541 | 실측 | 일반 | luau-testing/error-tests.md | 없음 | raise 자리 23곳 전수 돌연변이 기록 |
| S-119 | 테스트 | 프레임워크 없는 테스트: `assert(cond, "기대·실제가 든 메시지")` + `print("PASS")`, 절마다 `do … end` 로 지역 격리, exit code 로 판정, 러너는 순수 `luau` CLI. lune 을 안 쓰는 이유(const 못 읽음, 타입 미추종, 방치) | stl:base/architecture.md:15-22,64-77; stl:conventions.md:155; stl:rules/tests.md:8 | 사용자결정 | 반일반 | luau-testing/style.md | 일부(kb:luau-verify/references/tooling.md §2 러너 정책) | lune 이 const 를 못 읽는 원인은 M-02(번들 Luau 0.709) |
| S-121 | 테스트 | 경계 케이스(빈 것·한 개·뒤집힌 구간·범위 초과·음수)를 모두 고정하고, 눈에 안 보이는 것은 무작위 대조 수백 회(이분↔선형, 힙↔정렬). 키·값·위치는 서로 다른 값(`10,20,30`). 복잡도 주장은 시간 대신 비교 횟수 카운터로 고정한다 | stl:conventions.md:158-160; stl:papers/05-quad-survey.md:241-246 | 사용자결정 | 반일반 | luau-testing/practices.md | 없음 | 조용히 clamp 하는 Lua API 에서 특히 필요 |
| S-123 | 모듈·require | luau CLI 에서 `init.luau` 는 폴더 자신이다. `Foo/init.luau` 안에서 폴더 안 형제는 `@self/Bar`, 폴더 밖 형제는 `./Types`. 일반 파일은 자기 디렉터리 기준이고, 일반 파일에서 `@self/x` 는 항상 실패한다. `require("./src")` 는 `src/init.luau` 를 로드하고 `@self` 는 `.luaurc` 없이 동작한다. `X.luau`→`X/init.luau` 로 바꿔도 경로가 유지된다 | stl:base/architecture.md:37-57,312-335; stl:audit/container-contracts/module-split/README.md:46-54; tbox:CLAUDE.md:95-117; mw:conventions.md:66-70; mw:base/architecture.md:97,114-123; mrow-rv:1159-1172 | 실측 | 일반 | luau-style/modules-require.md | 일부(kb:luau-verify/references/tooling.md:46 lune 차이만) | luau 0.734, luau-lsp, lute 1.0.0 공통. quad 도 같음(quad:session-summary.md:1545-1548). X-01 병합. lune 0.8.9 는 반대였다 |
| S-124 | 모듈·require | `@self` 대신 `./` 를 잘못 쓴 require 는 `luau-analyze` 진단이 0건이고(타입이 `Unifiable<Error>` 로 샘) 런타임에서만 터진다 → require 를 고친 변경은 실제로 한 번 require 하는 런타임 게이트를 둔다 | stl:base/architecture.md:322-329; mw:conventions.md:73-74; mw:base/migration-plan.md:133 | 실측 | 일반 | luau-verify/checkers.md | 없음 | X-05 병합. 정적 검사만 돌리는 하네스에 치명적 |
| S-125 | 모듈·require | `.luaurc` 의 일반 alias 는 편집기 전용이고 luau CLI 런타임 require 에서는 동작하지 않는다(예약 alias `@self` 만 동작) | stl:base/architecture.md:48-52 | 실측 | 반일반 | luau-style/modules-require.md | 없음 | **낡음 의심**: 2026-08 측정(quad 기록 이식). 0.742 로 재측 필요 |
| S-126 | 툴체인 | luau CLI 와 lute 1.0.0 의 require-by-string 은 심볼릭 링크를 따라가지 않는다(`could not resolve child component`). 그래서 pesde 워크스페이스 링크 위에서는 제자리 실행이 안 되고 `cp -rL` 사본에서 돌린다. Rojo(sourcemap·build)는 링크를 따라간다 | stl:base/architecture.md:337-341; tbox:CLAUDE.md:63-70; mw:conventions.md:72; mw:base/architecture.md:121; quad:session-summary.md:1553-1556 | 실측 | 일반 | luau-verify/toolchain.md | 없음 | X-03 병합. "보안상 일부러" 라는 이유는 서술 |
| S-127 | 툴체인 | luau CLI 표준 라이브러리에는 `io`·`fs`·`warn` 이 없다. 실패하면 exit 1. 그래서 픽스처는 `return [==[…]==]` 모듈로 구워 넣고, 출력 비교는 셸이 한다 | stl:base/architecture.md:9-13,24-34; mw:base/architecture.md:110-112; mw:conventions.md:104-105 | 실측 | 일반 | luau-testing/cli-fixtures.md | 일부(kb:luau-verify/references/tooling.md §2) | M-17 병합. 버전 미기재(2026-08) |
| S-128 | 툴체인 | `luau-analyze src tests` 처럼 함께 주면 tests 가 require 한 src 파일이 두 경로(`src/X.luau` 와 `./src/X.luau`)로 중복 보고된다 → 건수를 셀 때 경로를 정규화한다 | stl:base/architecture.md:111-114 | 실측 | 일반 | luau-verify/checkers.md | 없음 | 음성 대조군 건수 비교에 직접 영향 |
| S-129 | 툴체인 | luau CLI 는 실험적이지 않은 `Luau*` 플래그를 모두 켠다(그래서 Studio·luau-lsp 와 판정이 다를 수 있다). `luau-analyze --fflags=` 로 불리언 플래그는 바꿀 수 있으나 정수 한도는 못 바꾼다 | stl:research/luau-source/README.md:59-60; stl:research/class-like/README.md:57; stl:papers/05-quad-survey.md:189-190 | 실측 | 일반 | luau-verify/checkers.md | **모순**(kb:luau-types/references/recursion-and-limits.md:75 "플래그 옵션이 없다") | ★2 0.742 `CLI/src/Analyze.cpp:434` 에 `--fflags=` 존재 확인 → luau-kb 정정 대상 |
| S-130 | 스타일·관용 | stylua `-- stylua: ignore` 는 주석 전체가 정확히 그 글자여야 먹는다(뒤에 설명을 붙이면 무시). 블록은 `-- stylua: ignore start` / `end` | stl:conventions.md:94; stl:archive/conventions-2026-11-04.md:569-571; quad:research/kit-packaging-plan.md:36 | 서술 | 일반 | luau-style/formatting.md | 없음 | stylua 2.5.2. 재현 스니펫 필요 |
| S-131 | 스타일·관용 | `(` 로 시작하는 문장(`;(f :: T)(x)`)은 앞 문장이 `const` 선언이면 stylua 2.5.2 가 모호함을 가르는 `;` 를 지워 파싱 에러를 만든다. 처방: 지역으로 받아 부른다(`const f = x :: T; f(1)`) | stl:conventions.md:95; stl:archive/question-resolved.md:1764-1768; stl:archive/conventions-2026-11-04.md:572-575 | 실측 | 일반 | luau-style/formatting.md | 없음(kb:luau-verify/references/tooling.md §4 는 `f<<T>>` 만) | 조용한 버그가 아니라 에러로 드러남 |
| S-132 | 동시성 | luau CLI 메인 스레드는 `coroutine.isyieldable()` 이 참인데, 거기서 yield 하면 `pcall` 로도 못 잡는 크래시가 난다 → 대기는 직접 만든 코루틴 안에서만 | stl:papers/01-fut.md:11-16 | 실측 | 일반 | luau-style/coroutines.md | 없음 | R-13(C-call 경계) 과 같은 reference |
| S-133 | 동시성 | 즉시 실행 스케줄러로 콜백 사슬을 재귀 resume 하면 약 198단에서 "C stack overflow" 가 난다 → 큐(트램펄린)로 펴고, 트램펄린에 상한을 둔다(잡이 잡을 넣으면 영원히 돈다) | stl:papers/01-fut.md:25-32; stl:papers/05-quad-survey.md:223-225 | 실측 | 일반 | luau-style/coroutines.md | 없음 | C 호출 깊이 한도(LUAI_MAXCCALLS≈200 추정). Lua 호출 한도 M-03(20000)과 구분 |
| S-134 | 동시성 | 순수 luau 에는 `task.spawn`/`defer` 도 이벤트 루프도 없다 → Promise 류는 스케줄러를 주입받고(기본 즉시, Roblox 는 `task.defer`), 타이머는 주입이 없으면 에러. 테스트는 결정적 스케줄러와 가상 시계. `pcall` 로 거절을 처리하면 스택이 사라지고 `xpcall` 이 보존한다 | stl:papers/01-fut.md:45-82; stl:papers/05-quad-survey.md:209-217,226-227 | 사용자결정 | 반일반 | luau-style/coroutines.md | 없음 | quad provider 층과 같은 결론 |
| S-135 | runtime·엔진 | 메타메소드 규약: `__eq` 는 두 피연산자가 같은 종류(둘 다 표 또는 둘 다 userdata)이고 메타메소드가 같을 때만 불린다(`1.0==1`). `__index` 는 함수보다 테이블을 가리킬 때 싸다. `__metatable` 로 잠긴 표를 `for … in` 으로 돌면 숨은 `__call`·`__iter` 를 따라간다. `__gc` 는 쓸 수 없다 | stl:base/architecture.md:294-304; stl:base/container-design-notes.md:279-283; stl:archive/question-resolved.md:519,977-981; dvr:2026-10-20-action-check.md:126 | 서술 | 일반 | luau-perf/metatables.md | 없음 | D-R36 병합. `__gc` 문구("Roblox 에서 비활성")는 Luau 자체 미지원인지 확인 필요 |
| S-136 | 기타 | (타입) 콜러블 네임스페이스(`__call` 이 있는 모듈 표)를 거친 생성자는 제네릭 타입 인자를 잃고 모듈 필드 오타도 못 잡는다 → `M.New` 네임스페이스 함수로 | stl:conventions.md:40; stl:base/architecture.md:300; stl:archive/question-resolved.md:1716-1720 | 실측 | 일반 | luau-types/generics.md | 일부(kb:luau-types/references/generics.md §3, unions-singletons.md §7) | 새 것은 "추론에서도 잃음", "오타 미검출" |
| S-137 | 기타 | (타입) 반환이 `()` 인 제네릭 함수를 `pcall(f, …)` 에 바로 넘기면 타입 인자가 풀리지 않는다 → 람다로 감싼다 | stl:conventions.md:114; stl:audit/review-trait-2026-10-21-bd/REPORT.md:11; stl:archive/question-resolved.md:1332 | 실측 | 일반 | luau-types/generics.md | 없음 | 0.742 무렵. 최소 재현 파일 없음 |
| S-138 | 기타 | (타입) 제네릭 몸통 무검사 결함은 몸통을 구체 불투명 "탐침 타입"(`{ read __probeA: true }`)으로 쓰면 피한다. 0.739 의 땜질 `LuauSoundGenericMismatches` 는 기대 타입이 정확히 `T` 일 때만 듣는다(return·대입·비제네릭 호출 인자. 지역 초기화와 `T?` 제외) | stl:conventions.md:75; stl:base/trait-system.md:77; stl:research/luau-source/README.md:14-17,55-78,86-89 | 실측 | 일반 | luau-types/generics.md(§6 보강) | 일부(kb:luau-types/references/generics.md §6 원인만) | 0.742 소스(`8387cfb`) |
| S-139 | 기타 | (타입) 제네릭 함수 필드를 담은 표 리터럴을 인자·return·대입 자리에 두면 읽기·쓰기 필드 불변 비교 실패가 Subtyping 캐시에 남아 같은 모듈 뒷줄의 멀쩡한 비교까지 실패시킨다(거짓 양성). 받는 타입 필드를 `read` 로 적거나 주석 단 지역에 먼저 담는다. 원인 줄이 아닌 곳에 에러가 보이면 의심한다 | stl:audit/luau-solver-issues/DRAFTS.md:194-202; stl:research/luau-source/README.md:18-21,95-130 | 실측 | 일반 | luau-types/solver-limits.md | 없음 | 0.742, 두 줄 패치로 소거 확인. 상류 미보고 |
| S-140 | 기타 | (타입) 캐스트 `x :: T` 는 두 타입의 교집합이 비어 있지 않은지만 본다. 함수 타입끼리는 늘 통과한다 | stl:research/luau-source/README.md:125 | 실측 | 일반 | luau-types/solver-limits.md | 일부(kb:luau-types/references/generics.md §3 "캐스트는 검사를 끈다") | `TypeChecker2.cpp:3256-3262` |
| S-141 | 기타 | (타입) 인덱서 없는 갈래가 든 유니온(`{ read [number]: number } \| { read n: number }`)을 `for … in` 으로 돌면 진단 0건, 루프 변수 타입도 안 본다(갈래 하나면 "Cannot iterate…") | stl:audit/luau-solver-issues/DRAFTS.md:236-247 | 실측 | 일반 | luau-types/solver-limits.md | 없음 | 0.742. 미보고 |
| S-142 | 기타 | (타입) `type T1<V> = { x: V, y: V? }` 에 `T1<number?>` 를 넘기면 V 를 추론하지 못한다. `read y: V?` 면 통과한다. 클래스 인스턴스 타입의 메서드 칸도 `read F: (self: any, …)` 로 | stl:audit/luau-solver-issues/DRAFTS.md:271-283; stl:research/class-like/README.md:31-37 | 실측 | 일반 | luau-types/variance.md | 없음 | 0.742 |
| S-143 | 기타 | (타입) 큰 모듈 표를 `any` 매개변수 함수에 넘기면 "Code is too complex" 가 난다. 걸음 수가 제네릭 함수 수 × 메서드 수에 비례해 `LuauTypeInferIterationLimit`(2만)을 넘는다. `unknown` 매개변수·`:: any`·`print(M)` 에서는 안 난다 | stl:audit/luau-solver-issues/DRAFTS.md:285-293; stl:research/class-like/README.md:53-60 | 실측 | 일반 | luau-types/recursion-and-limits.md | 일부(kb:luau-types/references/recursion-and-limits.md §5·§6) | 새 사실은 `any` 매개변수 조건과 F×M 원인 |
| S-144 | 기타 | (타입) 원소 타입을 바꾸는 메서드(`Map: <U>(self: Arr<T>, …) -> Arr<U>`)를 인스턴스 타입에 적으면 정의 줄은 조용히 통과하고 반환이 `*error-type*` 이 되어 결과를 쓰는 줄의 검사가 꺼진다 | stl:research/class-like/README.md:24-26 | 실측 | 일반 | luau-types/recursion-and-limits.md | 일부(§1 비균일 재귀) | 이슈 #2380 과 같은 뿌리인지 확인 |
| S-145 | 기타 | (타입) 유니온 자리 제네릭은 인자가 유니온 갈래와 같은 별칭일 때만 풀린다. 구조만 같으면 `unknown`. 유니온 매개변수에는 표 리터럴의 기대 타입이 내려가지 않는다 | stl:base/typing-limits.md:371-386 | 실측 | 일반 | luau-types/unions-singletons.md | 없음 | 0.742 |
| S-146 | 기타 | (타입) ① 명시 타입 인자를 일부만 주면 솔버 내부 에러 → 제네릭 순서가 곧 공개 표면 ② `table.freeze({…})` 결과의 필드 타입은 `read` ③ `never` 를 돌려주는 호출 뒤를 함수 끝으로 보지 않는다 → `return raise(…)` | stl:base/trait-system.md:34,44; stl:archive/conventions-2026-11-04.md:542-543 | 실측 | 일반 | luau-types/generics.md | 없음 | 각각 최소 스니펫 필요(①③ 서술 성격) |
| R-01 | Roblox API | 시그널 userdata 는 접근마다 새로 생긴다. 하나를 쥔 채 다시 읽어도 `rawequal(p.ChildAdded, p.ChildAdded)` 는 false(`==` 는 `__eq` 로 true). `GetPropertyChangedSignal("Name")` 도 같다. 그래서 시그널을 테이블 키·캐시 키로 못 쓴다 → (Instance, 이벤트 이름)으로 잡는다 | rbvm-eb:22-24; rbvm-cr:15-17,540-551 | 실측 | 일반 | roblox-luau/signals.md | 없음 | [Studio 0.742, Deferred]. 이 키로 캐시하면 한 번도 적중하지 않는다(52번 읽자 영구 연결 52개). `rbvm:design/gc-and-lifecycle.md:87-91` 의 전제가 이 실측으로 틀림 |
| R-02 | Roblox API | `typeof(signal)` 은 `RBXScriptSignal`, `tostring` 은 `Signal ChildAdded`. 레거시 소문자 `signal:connect`, `conn:disconnect()`, `signal:wait` 가 아직 동작한다(creator-docs yaml 에는 없음) | rbvm-eb:25-26; rbvm-cr:504-509 | 실측 | 일반 | roblox-luau/signals.md | 없음 | [Studio 0.742, Deferred]. 래퍼 Signal 이 별칭까지 맞출지 판단 근거 |
| R-03 | Roblox API | A, B, C 순서로 Connect 하고 Fire 하면 C, B, A(연결 역순)로 불린다. Destroying 핸들러 둘도 2→1 | rbvm-eb:27,46; rbvm-cr:20 | 실측 | 반일반 | roblox-luau/signals.md | 없음 | [Studio 0.742, Deferred]. 문서 보장이 아니므로 "의존 금지" 경고와 함께. quad 는 "비결정적"으로 적음(모순 9) |
| R-04 | Roblox API | 핸들러가 자기 연결을 Disconnect 해도 같은 발화의 나머지 핸들러는 모두 불린다. 발화 중 Connect 한 핸들러는 이번 발화에서 안 불리고 다음 발화에서 맨 먼저 불린다 | rbvm-eb:28-29 | 실측 | 일반 | roblox-luau/signals.md | 없음 | [Studio 0.742, Deferred] |
| R-05 | Roblox API | `Once` 핸들러 안에서 `conn.Connected` 는 이미 false 다(엔진이 부르기 전에 끊는다) | rbvm-eb:30; rbvm-cr:449-451 | 실측 | 일반 | roblox-luau/signals.md | 없음 | [Studio 0.742, Deferred] |
| R-06 | 동시성 | 순수 Lua Signal 구현의 흔한 결함: ① 연결 목록을 라이브로 순회하며 `table.remove` 하면 자기 연결을 끊은 핸들러 다음 것이 빠지고(A,B,C→A,C), 자기 재연결 시 Fire 가 끝나지 않는다 ② 발화 중 대기 중인 Once 를 끊으면 Fire 가 에러로 멈춰 Wait 대기자를 못 깨운다. 처방: `table.clone` 스냅샷을 돌고 호출 직전 생존 확인 | rbvm-cr:144-166; rbvm:review/2026-10-05-repro/B1_self_disconnect_skip.luau:1; rbvm:review/2026-10-05-repro/B2_once_disconnect_in_fire.luau:1-2 | 실측 | 일반 | roblox-luau/signals.md | 없음 | luau CLI 재현. 엔진의 올바른 동작은 R-04 |
| R-07 | Roblox API | 스크립트에서 `workspace.SignalBehavior` 를 읽을 수 없다. Deferred 인지는 `BindableEvent:Fire()` 직후 핸들러가 이미 돌았는지로 판정한다 | rbvm-eb:14-15 | 실측 | 일반 | roblox-luau/signals.md | 없음 | [Studio 0.742]. T-14(스트리밍 속성도 못 읽음)와 같은 패턴 |
| R-08 | 동시성 | `task.spawn(th)` 는 넘긴 thread 를 그대로 돌려준다(`rawequal` true). `task.spawn(123)` 은 즉시 에러. `task.cancel(죽은 thread)` 는 에러 없음 → task 래퍼가 원래 thread 를 안 돌려주면 `task.cancel(task.spawn(th))` 가 안 먹는다 | rbvm-eb:31-33; rbvm-cr:320-326 | 실측 | 일반 | roblox-luau/threads.md | 없음 | [Studio 0.742, Deferred] |
| R-09 | 동시성 | `task.defer` 콜백 안에서 다시 `task.defer` 하면 hop 이 둘이 되어 `defer(A); defer(B); 래퍼(C); defer(D)` 가 A B D C 순서가 된다. 돌려받은 thread 를 cancel 해도 안쪽 defer 가 이미 예약돼 f 가 돈다 | rbvm-cr:313-318 | 실측 | 반일반 | roblox-luau/threads.md | 없음 | 가짜 스케줄러 재현. Studio 미확인 |
| R-10 | 에러 | 직접 `coroutine.resume(th)` 로 재개한 스레드의 에러는 아무 출력 없이 사라진다(다음 yield 까지 재개한 쪽 스택에서 돈다) → 엔진이 재개하게 `task.spawn(th, ...)` 를 쓰거나, 결과를 확인해 `warn(debug.traceback(th, err))` | rbvm-cr:168-185; rbvm:review/2026-10-05-repro/B3_wait_error_swallowed.luau:1 | 실측 | 일반 | roblox-luau/threads.md | 없음 | luau CLI. "task.spawn 은 엔진이 보고" 쪽은 Studio 확인 필요(rbvm-cr:185) |
| R-11 | 에러 | `pcall(coroutine.wrap(function() error("boom") end))` 는 `false, "<위치>: boom"` 으로 위치가 한 번만 붙는다. 래퍼가 `error(result[2])` 로 다시 던지면 위치가 또 붙는다 → 되던질 때는 `error(msg, 0)` | rbvm-eb:34; rbvm-cr:198-203 | 실측 | 일반 | luau-style/errors.md | 없음 | 엔진 쪽 [Studio 0.742], 래퍼 쪽 CLI |
| R-12 | 기타 | 타입 단언 `expr :: T` 가 붙은 호출식은 괄호처럼 값 하나로 잘린다. `return table.unpack(r,1,r.n) :: any` 는 값 1개만 돌려주는데 타입 검사는 통과한다 → 함수 쪽을 캐스팅한다 `(table.unpack :: any)(r,1,r.n)` | rbvm-cr:187-196; rbvm:review/2026-10-05-repro/B4_cast_truncates.luau:1-2 | 실측 | 일반 | luau-style/pitfalls.md | 없음 | luau CLI, 2줄 재현. 실제로 에러 메시지까지 nil 이 됨 |
| R-13 | 동시성 | `table.sort` 비교자처럼 yield 할 수 없는 문맥에서 Wait 류를 부르면 `attempt to yield across C-call boundary`. 그런데 "먼저 연결·워커를 등록하고 그다음 yield" 하는 구조면 등록이 남아 나중에 엉뚱한 값을 주입한다 → 등록 전에 `coroutine.isyieldable()` 확인 | rbvm-cr:286-295 | 실측 | 반일반 | luau-style/coroutines.md | 없음 | 가짜 Instance 위 재현 |
| R-14 | GC·수명 | `part:Destroy()` 직후 같은 흐름에서는 Destroying 핸들러가 아직 안 돌았고 `task.wait()` 뒤에 돈다. 반면 그 Instance 의 모든 연결의 `Connected` 는 Destroy 안에서 동기로 false 가 된다 → 생존 판정은 플래그보다 `conn.Connected`. 연결이 끊겨도 큐에 들어간 Destroying 배달 1회는 돈다 | rbvm-eb:40-41; rbvm-cr:529-533; rbvm-sib:194-204 | 실측 | 일반 | roblox-luau/lifecycle.md | 없음 | [Studio 0.742, Deferred]. quad H-291 과 일치. Immediate 미측정 |
| R-15 | GC·수명 | 부모 Model 을 Destroy 하면 자식의 Destroying 핸들러 안에서 `child.Parent` 는 이미 nil 이다. "Destroying 시점에 계층이 온전하다" 는 Deferred 에서 틀렸다 | rbvm-eb:45; rbvm-cr:21 | 실측 | 일반 | roblox-luau/lifecycle.md | 없음 | [Studio 0.742, Deferred]. rbvm-cr:590 원래 서술을 정정. quad mock 가정과 다름(모순 10) |
| R-16 | Roblox API | 파괴된 Instance 의 `.Name`·`.Parent` 는 그대로 읽힌다(`"Part"`, `nil`). `.Parent = workspace` 는 `The Parent property of Part is locked, current parent: NULL…` 에러 | rbvm-eb:42-43; dvr:2026-10-20-bindable-watch.md:116-127 | 실측 | 일반 | roblox-luau/lifecycle.md | 없음 | [Studio 0.742, Deferred] |
| R-17 | GC·수명 | 파괴된 Instance 에 `Destroying:Connect`·`Changed:Connect` 를 해도 성공하고 `Connected == true` 지만 영원히 안 울리고 끊기지도 않는다. 엔진 API 에는 깔끔한 "파괴됨" 판정이 없다 → 파괴된 것을 감싸면 연결·클로저가 샌다 | rbvm-eb:44; rbvm-cr:535-538; rbvm-sib:205-206 | 실측 | 일반 | roblox-luau/lifecycle.md | 없음 | [Studio 0.742, Deferred]. quad H-293·H-548 과 같음 |
| R-18 | GC·수명 | Lua 쪽 강참조 없이 weak 맵에만 있는 Instance userdata 는 Destroy 뒤 수거된다(할당 부하 + `task.wait()` 5프레임 만에 20/20). RBXScriptSignal userdata 도 아무도 안 쥐면 수거되고 다시 얻으면 새 주소다. Roblox 에서는 `collectgarbage("collect")` 를 못 쓰므로 프레임을 넘기며 할당 부하로 관찰한다 | rbvm-eb:47; rbvm-cr:559-569; rbvm:design/gc-and-lifecycle.md:87-91 | 실측 | 일반 | roblox-luau/gc.md | 없음 | [Studio 0.742, Deferred]. quad(audit/README.md:21)와 일치 |
| R-19 | GC·수명 | 수명 묶기 패턴: hold 테이블(`{obj, inst, conn}`)을 캡처한 클로저를 `inst.Destroying`(또는 절대 안 울리는 `GetPropertyChangedSignal("ClassName")`)에 연결해 두면 Lua 객체가 Instance 생존 동안 산다. Destroy 가 연결을 끊는 순간 사슬이 풀린다 | rbvm:design/gc-and-lifecycle.md:24-53; rbvm-sib:202-204; rbvm-cr:674-675 | 서술 | 반일반 | roblox-luau/lifecycle.md | 없음 | quad LifetimeHandle 과 같은 패턴. 한계: Destroy 이후 불성립(R-18), Destroy 없이 버린 Instance 누수(R-21) |
| R-20 | GC·수명 | 클로저는 본문이 실제로 참조하는 local 만 업밸류로 캡처한다. 앵커 테이블을 쥐게 하려면 `nop(gcHold)` 같은 참조가 필요하다. "안 쓰는 줄" 로 보여 지우면 타입 검사는 통과하지만 GC 사슬이 조용히 깨진다 | rbvm:design/gc-and-lifecycle.md:46-53,147-154 | 서술 | 일반 | luau-style/closures.md | 없음 | 언어 의미론. 재현 스니펫 쉬움 |
| R-21 | GC·수명 | Destroy 없이 `Parent = nil` 만 하고 버린 Instance 는 연결된 클로저가 Instance 를 잡고 있으면 회수되지 않는다. 엔진이 만들고 Destroy 하지 않는 Tween·AnimationTrack·InputObject 에 연결해도 같다 | rbvm-cr:518-527; dvr:2026-10-20-bindable-watch.md:116-127 | 서술 | 반일반 | roblox-luau/lifecycle.md | 없음 | Studio 확인 방법이 원문에 있음(rbvm-cr:527). D-R17(Destroying 은 Destroy 에서만) 병합 |
| R-22 | GC·수명 | Luau 의 weak-key 테이블은 ephemeron 이 아니다. 값이 자기 키를 강하게 참조하면 엔트리가 GC 를 넘어 산다(`wk[k] = {back = k}`). 두 weak-k 맵의 값이 서로의 키를 가리키는 순환도 영구 누수(100/100 잔존, 대조군은 수거) | rbvm-cr:571-584; rbvm:review/2026-10-05-repro/L7_no_ephemeron_signal_leak.luau:1-3,14-17 | 실측 | 일반 | luau-style/weak-tables.md | 없음 | luau CLI `collectgarbage`. Lua 5.2+ 상식과 반대. 처방: 사설 데이터를 객체 자체에 둔다 |
| R-23 | GC·수명 | `:Wait()` 로 멈춘 스레드는 스택에 `self` 를 쥔다. 그래서 `맵[sig].WaitList → thread → 스택 → sig` 경로로 weak-k 엔트리가 고정된다(Connection 이 없어도 100/100 잔존) | rbvm-cr:573-574; rbvm:review/2026-10-05-repro/L7_no_ephemeron_signal_leak.luau:19-21 | 실측 | 일반 | luau-style/weak-tables.md | 없음 | luau CLI. R-22 의 변형 |
| R-24 | 기타 | `__mode="v"` 배열에서 GC 가 만든 구멍에 `table.insert` 해도 안전하다(`t[#t+1]` 은 항상 nil). 일반화 반복은 해시부까지 돈다 | rbvm-cr:676 | 서술 | 일반 | luau-style/weak-tables.md | 없음 | 실행 기록 없음 |
| R-25 | 기타 | `table.pack` + `.n` + `table.unpack(t, 1, t.n)` 이면 nil 구멍이 보존된다(`Fire(1, nil, 3, nil)` → n=4) | rbvm-cr:677 | 실측 | 일반 | luau-style/varargs.md | 없음 | 잘 알려진 관용. 우선순위 낮음 |
| R-26 | 기타 | `table.freeze` 된 테이블이라도 없는 키에 대입하면 readonly 검사보다 메타테이블 `__newindex` 가 먼저 불린다(빈 frozen 테이블도) | rbvm-cr:686,711 | 실측 | 일반 | luau-perf/metatables.md | 없음 | luau CLI. frozen 프록시로 쓰기를 가로챌 수 있다는 근거 |
| R-27 | 기타 | ① `for k, v in f` 에서 f 가 함수면 iterator 로 호출된다(인자 nil, 부작용) ② `__metatable` 보호 테이블에 `table.clone` 은 `table has a protected metatable` 에러 ③ frozen 테이블 쓰기는 `attempt to modify a readonly table` → 테이블을 도는 함수는 루트 값 타입부터 확인 | rbvm-cr:366-374 | 실측 | 일반 | luau-style/pitfalls.md | 없음 | 리뷰어 재현 |
| R-28 | 기타 | 테이블 변환기·순회기에 visited 집합이 없으면 OOP 관용구 `M.__index = M` 하나로도 끝나지 않는다(10만 회 가드). 공유 서브테이블은 두 번 처리된다 → visited 맵(원본→변환본) | rbvm-cr:213-222; rbvm:review/2026-10-05-repro/B7_cycle.luau:1 | 실측 | 반일반 | luau-style/tables.md | 없음 | luau CLI |
| R-29 | 기타 | `table.sort` 는 안정 정렬이 아니다. thread·테이블 키 해시 테이블을 `for k in t` 로 돌면 삽입 순서가 아니라 해시 순서다(12개 → 7 6 3 4 9 …) → 순서가 필요하면 큐 배열 | rbvm-cr:299,420-428; rbvm:design/known-issues.md:100-103 | 실측 | 일반 | luau-style/tables.md | 없음 | 해시 순서는 재현, sort 쪽은 서술. M-16(같은 입력이면 결정적)과 양립 |
| R-30 | Roblox API | `GetFullName()` 은 DataModel 을 빼고 돌려준다(`Workspace.X.Deep`). `game:GetFullName()` 은 플레이스 이름. `tostring(inst)` 은 `Name` | rbvm-eb:53-54; rbvm-cr:443-447 | 실측 | 일반 | roblox-luau/instance-api.md | 없음 | [Studio 0.742, Deferred] |
| R-31 | Roblox API | `FindFirstDescendant` 를 부르면 `FindFirstDescendant is not enabled` 에러(비활성 API). `QueryDescendants` 는 실재한다 | rbvm-eb:55,62; rbvm-cr:229 | 실측 | 일반 | roblox-luau/instance-api.md | 없음 | [Studio 0.742]. 엔진 업데이트로 바뀔 수 있음. D-R24 와 같은 reference |
| R-32 | Roblox API | `FindFirstChild(123)` 은 이름 `"123"` 자식을 찾는다(문자열 강제 변환). `FindFirstChild(nil)`·`WaitForChild(nil, 0.1)` 은 `Argument 1 missing or nil` | rbvm-eb:56-57; rbvm-cr:483 | 실측 | 일반 | roblox-luau/instance-api.md | 없음 | [Studio 0.742, Deferred] |
| R-33 | Roblox API | `FindFirstChildOfClass("Folder", true)` 는 2번째 인자를 무시한다(재귀하지 않는다) | rbvm-eb:58; rbvm-cr:600 | 실측 | 일반 | roblox-luau/instance-api.md | 없음 | [Studio 0.742]. `FindFirstChild(name, true)` 와 헷갈리기 쉬움 |
| R-34 | Roblox API | `x:IsDescendantOf(nil)` 은 **true**, `x:IsAncestorOf(nil)` 은 false | rbvm-eb:59-60 | 실측 | 일반 | roblox-luau/instance-api.md | 없음 | [Studio 0.742]. 직관과 반대 |
| R-35 | Roblox API | `#inst` 는 `attempt to get length of a Instance value` 에러. deprecated 소문자 별칭(`children`, `getChildren`, `findFirstChild`, `isDescendantOf`)은 전부 동작. `p.Destroy == p.Destroy` 는 `rawequal` 로도 true(메서드 캐시) | rbvm-eb:61,63,66 | 실측 | 일반 | roblox-luau/instance-api.md | 없음 | [Studio 0.742] |
| R-36 | Roblox API | `WaitForChild("Nope", 0.3)` 은 0.33초 뒤 nil. timeout 을 주면 무한 대기 경고가 없고, 없을 때 경고는 5초 뒤(문서) | rbvm-eb:64; rbvm-cr:435-441; rbvm:design/known-issues.md:116-121 | 실측 | 일반 | roblox-luau/instance-api.md | 없음 | nil 반환만 [Studio 0.742] 실측. 경고 시점은 문서 서술 |
| R-37 | Roblox API | 순환이 되는 Parent 대입은 `…would result in circular reference` 에러 | rbvm-eb:65 | 실측 | 일반 | roblox-luau/instance-api.md | 없음 | [Studio 0.742] |
| R-38 | Roblox API | 점 표기·`["…"]` 인덱싱 모두 같은 이름 자식보다 멤버(속성·메서드)가 우선한다(`inst.Parent`) → 자식은 `:FindFirstChild`. 둘 다 없으면 `X is not a valid member of Folder "Name"`. `FindFirstAncestor*`·`IsDescendantOf` 는 자기 자신을 빼고 본다 → 이름 판정은 이름 편집으로 우회되니 시작 때 잡은 참조로 `IsDescendantOf`. `GetChildren`/`GetDescendants` 순서는 문서 보장이 없다 | rbvm-cr:682-683,687; rbvm-eb:93; dvr:2026-10-19-shared-specs.md:32-35; dvr:2026-10-19-server-edit.md:85-104; dvr:2026-10-20-recorder-depth.md:70-71 | 실측 | 일반 | roblox-luau/instance-api.md | 없음 | 멤버 우선은 devplorer 실측, 나머지는 서술. D-R14·D-R25·D-R51 병합 |
| R-39 | 모듈·require | Studio 문자열 require 는 경로가 `./`, `../`, `@` 로 시작해야 한다(`"Sibling"` 은 `require path must start with a valid prefix`). 없는 모듈은 기다리지 않고 **즉시** `could not resolve child component` 에러. ModuleScript 안에서 `./X` 는 형제, `@self/X` 는 자식, `@game/...` 은 절대 경로 | rbvm-eb:68-77; rbvm-cr:464-471 | 실측 | 일반 | roblox-luau/require.md | 일부(kb:luau-verify/references/tooling.md:46) | [Studio 0.742]. CLI 규칙(S-123)과 결과가 대응. `rbvm:design/architecture.md:208-209` "접두사 없으면 형제 기준" 은 rbvm 구현 서술일 뿐 |
| R-40 | 모듈·require | Studio require 의 관대한 쪽: 끝 슬래시 `"./Sibling/"`, 빈 세그먼트 `".//Sibling"` 은 성공. `"./"` 자체는 에러. 모르는 alias 는 `@foo is not a valid alias`. alias 는 대소문자를 가리지 않는다(`@Self/Child` 성공) | rbvm-eb:76-80 | 실측 | 일반 | roblox-luau/require.md | 없음 | [Studio 0.742]. 같은 입력의 CLI 동작은 미측정 |
| R-42 | GC·수명 | 스크립트가 Destroy 되거나 Disabled 되면 그 스크립트가 만든 연결이 끊긴다(확인되지 않은 기억) | rbvm-cr:596-597; rbvm-eb:95 | 서술 | 반일반 | roblox-luau/lifecycle.md | 없음 | Play 모드 확인 필요. 확인 시나리오가 원문에 있음 |
| R-45 | 모듈·require | pesde 는 의존 패키지마다 사본을 줄 수 있어 모듈 수준 전역 weak-key 맵이 조용히 둘로 갈라진다 | rbvm-sib:224-227 | 서술 | 반일반 | luau-style/modules-require.md | 없음 | 추정. 원 출처 quad-error 설계 노트 |
| R-47 | 테스트 | 가짜 Instance 를 테이블로 만들면 `typeof` 가 `"table"` 이라 `typeof(x) == "Instance"` 분기를 못 탄다. `type(userdata)` 에 기댄 경로에서 거짓 결론까지 냈다 → 흉내에는 `newproxy` userdata 가 필요하고, 근본적으로는 CLI(순수 로직)와 Studio(엔진 의존)를 나눈다 | rbvm-sib:111-113; rbvm-cr:67,615,710; rbvm:review/2026-10-05-repro/fake.luau:2 | 실측 | 일반 | luau-testing/cli-vs-roblox.md | 없음 | mock 제작법이 아니라 mock 충실도의 한계. 리뷰 1라운드 주장을 4라운드에 정정한 실례 |
| R-48 | 테스트 | luau CLI 에서는 `(_G :: any).collectgarbage("collect")` 로 weak 테이블 정리를 검증할 수 있다. 단 Roblox GC 와 같다는 보장이 없으니 "순수 Lua 수준" 으로 표시한다 | rbvm-sib:120-122; rbvm-cr:568 | 서술 | 일반 | luau-testing/gc.md | 없음 | Roblox 에서는 R-18 방식으로 관찰 |
| R-49 | 툴체인 | `luau-lsp analyze` 는 Roblox globalTypes 와 sourcemap 이 **둘 다** 있어야 의미 있다(없으면 `Unknown type 'Instance'` 도배). 2025-11자 globalTypes 는 luau-lsp 1.69.0 이 못 읽었다(`SyntaxError: Expected ':' … got 'Enum'`) → 정의 파일을 lsp 버전에 맞춰 받고 `main` 에서 받지 않는다 | rbvm:tools/check.sh:8-14,49-53,63-68; rbvm-cr:653 | 실측 | 일반 | luau-verify/checkers.md | 일부(kb:luau-verify/references/checkers.md:44-46,82; toolchain.md:50) | 새 사실은 버전 불일치 시 파싱 에러 문구 |
| R-50 | 툴체인 | 게이트를 `luau-lsp … \|\| true` 뒤 출력에서 `TypeError\|SyntaxError` 를 grep 해 판정하면 exit code 와 린트를 무시한다 → exit code 로 판정하고 실패를 누적해 `exit $fail` | rbvm:tools/check.sh:63-76; rbvm-cr:653; rbvm-sib:250-252 | 서술 | 일반 | luau-verify/checkers.md | 일부(kb:luau-verify/references/negative-controls.md) | mrow·quad 에 grep 판정이 SyntaxError 를 놓친 사례(2차 인용) |
| R-51 | 기타 | (타입) `{...} & { [string]: any, ... }` 꼴의 catch-all 인덱서 교차 타입이면 필드 읽기·쓰기가 사실상 모두 any 가 되어 non-optional 필드에 nil 대입도 통과한다. 옛 솔버 노이즈 340건, 새 솔버 0건 | rbvm:design/known-issues.md:18-45; rbvm:tools/check.sh:15-18 | 실측 | 반일반 | luau-types/solver-limits.md | 없음 | luau-lsp 1.69.0. "검사 통과 ≠ 로직 검증" 근거 |
| R-52 | 하네스·에이전트 운영 | 리뷰 "소진" 규칙: 재현한 것만 결함으로 센다. 1라운드는 관점별 여러 명, 이후는 1명이고, 라운드마다 새 리뷰어에게 이전 목록을 주고 "없는 것만" 찾게 한다. 재현된 새 결함 0건이면 그 영역을 닫는다(rbvm 다수→4→2→0). 한 판에 하나씩, 틀린 지적·중복이 절반을 넘으면 멈춘다 | rbvm-cr:60-70,714-723; rbvm-sib:145-161; tbox-cr:7-21; ts:<비공개> | 실측 | 일반 | harness/review-protocol.md | 없음 | 원 규칙 stl conventions. X-24·T-58 병합. O-01·O-02 와 같은 reference |
| R-53 | 하네스·에이전트 운영 | 엔진 동작 문서에는 직접 잰 것만 날짜·Studio 버전·시그널 모드와 함께 적고, 기억·인용은 근거 태그(【실측】【인용】【판단】)를 단다. "반박된 주장" 표와 "잘 된 것(유지)" 절로 에이전트가 같은 실수를 되풀이하거나 멀쩡한 설계를 "개선" 하지 못하게 한다 | rbvm-eb:3-5; rbvm-cr:8-12,670-712; rbvm-sib:163-173,183-186 | 사용자결정 | 일반 | harness/evidence-tags.md | 없음 | mrow·tbox 형식에서 옴. luau-kb `status:` 표식과 같은 방향 |
| T-01 | Roblox API | `DragDetector:AddConstraintFunction` 이 받고 돌려주는 CFrame 은 월드 좌표가 아니라 **끌기 시작점 기준 이동량**이다(월드 좌표를 돌려주면 두 배 위치로 간다). 제약 함수는 `DragStart` 보다 먼저 불린다 | ts:<비공개>; ts:<비공개> | 실측 | 일반 | roblox-luau/drag-detector.md | 없음 | Studio 0.742 Play. spike02 의 첫 PASS 근거가 틀렸다가 정정됨 |
| T-02 | Roblox API | `DragDetector.MaxActivationDistance` 기본 32 때문에 먼 물체를 못 끈다. 기준점은 캐릭터로 보이며 캐릭터가 없으면 검사가 걸리지 않았다 | ts:<비공개>; ts:<비공개> | 실측 | 일반 | roblox-luau/drag-detector.md | 없음 | "캐릭터가 기준" 은 두 조건만 본 추정 |
| T-03 | Roblox API | DragDetector 를 단 파트의 **자식 파트**를 눌러서는 반응하지 않는다. 누름 판정은 `CanQuery` 가 아니라 `CanCollide` 와 "Default 그룹과 부딪치는가" 를 따른다 | ts:<비공개>; ts:<비공개> | 실측 | 일반 | roblox-luau/drag-detector.md | 없음 | Studio Play. 모델 단위면 감지기를 Model 밑에 |
| T-04 | Roblox API | Physical 응답으로 끄는 물체는 커서나 카메라가 움직일 때만 목표를 다시 계산한다(휠만 굴리면 높이 그대로). 카메라를 0.01 흔들어 우회 | ts:<비공개> | 실측 | 일반 | roblox-luau/drag-detector.md | 없음 | Studio Play 2026-10-13 |
| T-05 | Roblox API | Physical 끌기는 잡은 점을 당겨 흔들리고 돈다 → `ApplyAtCenterOfMass=true` 로 흔들림 0, 회전은 `AlignOrientation`(RigidityEnabled)로 막는다 | ts:<비공개>; ts:<비공개> | 실측 | 일반 | roblox-luau/drag-detector.md | 없음 | |
| T-06 | Roblox API | DragDetector 공식 동작: `RunLocally=false` 면 서버가 처리하고 소유권과 무관하게 누구나 끈다. `true` 면 복제되지 않고 비앵커 파트는 소유권이 필요. Geometric 은 끄는 동안 비앵커 물체를 앵커한다. 그리드·스냅 내장 없음, ClickDetector 와 함께 못 쓴다 | ts:<비공개>; ts:<비공개> | 서술 | 일반 | roblox-luau/drag-detector.md | 없음 | 문서 인용. RunLocally 로드맵이 바뀌면 낡음 |
| T-07 | Roblox API | 클라이언트 소유로 넘겨 Physical 로 끈 카드를 놓을 때 서버가 `Anchored=true` 만 걸면 양쪽이 0.28스터드 어긋난 채 굳는다. 같은 값을 다시 쓰는 `p.CFrame=p.CFrame` 은 **복제되지 않는다** → 서버가 클라이언트의 마지막 위치(다른 값)를 직접 쓴다 | ts:<비공개>; ts:<비공개> | 실측 | 일반 | roblox-luau/network-ownership.md | 없음 | Studio 0.742, 서버1+클라1, 핑 0 |
| T-08 | Roblox API | 앵커되지 않은 파트는 가만히 있어도 엔진이 근처 플레이어 소유로 자동 배정한다 → 서버 소유가 필요하면 `SetNetworkOwner(nil)` 명시 | ts:<비공개>; ts:<비공개> | 실측 | 일반 | roblox-luau/network-ownership.md | 없음 | 문서상 규칙과 같음 |
| T-09 | Roblox API | 서버가 속도를 준 직후 소유권을 플레이어로 넘기면 그 속도가 넘어가지 않는다 → 속도는 새 소유자 쪽에서 준다 | ts:<비공개> | 실측 | 일반 | roblox-luau/network-ownership.md | 없음 | Studio Play 2026-10-12 |
| T-10 | Roblox API | 서버 물리를 클라이언트에서 보면 움직이는 프레임의 15%가 제자리이고 속도 편차 189%. 튕긴 사람에게 소유권을 넘기면 0%, 13~36% | ts:<비공개> | 실측 | 반일반 | roblox-luau/network-ownership.md | 없음 | 핑 0, 클라 하나 |
| T-11 | Roblox API | 네트워크 소유권 API 는 Workspace 자손에만 부를 수 있다(`Can only call Network Ownership API on a part that is descendent of Workspace`) | ts:<비공개> | 실측 | 일반 | roblox-luau/network-ownership.md | 없음 | |
| T-12 | Roblox API | 앵커된 파트는 항상 서버 소유이고 바꿀 수 없다. 앵커 파트가 없는 메커니즘은 어셈블리 하나에 소유권을 걸면 전체에 걸린다(고정을 푼 뒤에 부른다) | ts:<비공개> | 서술 | 일반 | roblox-luau/network-ownership.md | 없음 | creator-docs 인용 |
| T-13 | Roblox API | StreamingEnabled 에서 `ReplicationFocus` 가 먼 곳이면 먼 Model 은 빈 껍데기로만 온다(PrimaryPart=nil). 파트·데칼·**파트의 속성**은 오지 않고, **Model·Folder 자신의 속성과 Player 속성은 모두에게 간다**. 초점을 옮기면 1~2초 안에 바뀐다 | ts:<비공개>; ts:<비공개> | 실측 | 일반 | roblox-luau/replication-streaming.md | 없음 | 외부 모델이 반대로 단정한 것을 실측으로 뒤집음(T-57). 보안 경계인지는 문서 미확인 |
| T-14 | Roblox API | `workspace.StreamingMinRadius`·`StreamOutBehavior`·`StreamingTargetRadius` 는 스크립트에서 읽을 수 없다(`not a valid member`) → Rojo 프로젝트의 Workspace 속성으로 둔다 | ts:<비공개>; dv:research/feature-proposals-2.md:68 | 실측 | 일반 | roblox-luau/replication-streaming.md | 없음 | R-07(SignalBehavior)과 같은 패턴 |
| T-15 | Roblox API | Roblox 물리에는 구름 저항이 없다. 누운 원기둥·공은 스스로 멈추지 않아 소유권도 안 돌아온다 → 축 하나 `AlignOrientation`, 공은 `AngularVelocity` 0 + 토크 한도 질량×6 으로 제동 | ts:<비공개> | 실측 | 일반 | roblox-luau/physics.md | 없음 | 물리 속성 기본값 |
| T-16 | Roblox API | 빠르게 떨어지는 얇은 물체는 얇은 파트를 뚫는다. 보이지 않는 받침과 테이블 사이에 끼인 물체는 겹침 해소 과정에서 크게 튕겨 나간다 | ts:<비공개> | 실측 | 반일반 | roblox-luau/physics.md | 없음 | 수치는 장면 의존 |
| T-17 | Roblox API | `SeatWeld` 로 앉은 캐릭터를 `PivotTo` 로 옮기면 앵커된 Seat 까지 끌려간다 → 먼저 일으켜 세운다 | ts:<비공개> | 실측 | 일반 | roblox-luau/characters.md | 없음 | |
| T-18 | Roblox API | Humanoid 모델의 몸통·머리는 `CanCollide` 가 매 프레임 다시 켜져 `CanQuery=false` 가 먹지 않는다(서버 레이캐스트가 Torso 를 맞힘) | ts:<비공개> | 실측 | 일반 | roblox-luau/characters.md | 없음 | `EvaluateStateMachine=false` 로 우회(T-23) |
| T-19 | Roblox API | Workspace 에 들어가기 전에 만든 `WeldConstraint` 는 그 뒤 정한 위치를 따라가지 않았다 → 오프셋을 적는 `Weld`(C0) | ts:<비공개> | 실측 | 일반 | roblox-luau/constraints.md | 없음 | |
| T-20 | Roblox API | 자식 WeldConstraint 가 붙은 파트를 `Clone()` 하면 사본의 용접이 사본 밖 원본 파트를 계속 가리킨다(사본을 돌리자 원본이 24스터드 휘둘림) → 복제 시 용접을 지운다 | ts:<비공개> | 실측 | 일반 | roblox-luau/instance-api.md | 없음 | 대조군 24.0, 수정 후 0.000 |
| T-21 | Roblox API | 용접된 파트에 `CFrame` 을 쓰면 연결된 파트가 같이 움직이고 `Position` 을 쓰면 그 파트만 움직인다 | ts:<비공개> | 서술 | 일반 | roblox-luau/constraints.md | 없음 | WeldConstraint.yaml 인용 |
| T-22 | Roblox API | 캐릭터에 `Model:ScaleTo(5)` 가 0.6ms 에 먹는다(HipHeight 2.10→10.48). `Seat:Sit(humanoid)` 후 WalkSpeed·JumpPower·JumpHeight 를 0 으로 두면 일어나지 못한다 | ts:<비공개> | 실측 | 일반 | roblox-luau/characters.md | 없음 | R15 기본만 |
| T-23 | Roblox API | `Players:CreateHumanoidModelFromUserIdAsync` 는 아무 UserId 로나 되고 1.06~1.32초(Description 캐시 후 0.02초). `EvaluateStateMachine=false`, `PlatformStand`, 몸 전부 `Massless` 면 받침과 한 덩어리로 움직인다 | ts:<비공개> | 실측 | 일반 | roblox-luau/characters.md | 없음 | 게시 서버 호출 한도 미확인 |
| T-24 | Roblox API | `MeshPart.MeshId` 는 스크립트로 쓸 수 없다(`lacking capability NotAccessible`). `AssetService:CreateMeshPartAsync(Content.fromUri(id))` 0.64초. 틀린 ID 는 던지므로 pcall | ts:<비공개>; ts:<비공개> | 실측 | 일반 | roblox-luau/assets-runtime.md | 없음 | |
| T-25 | Roblox API | EditableMesh: 서버에서 지은 MeshPart 는 모양이 복제되지 않는다. 클라이언트에서 서로 다른 EditableMesh 약 5개에서 "memory budget" 에 막히고 `FixedSize=true` 사본은 25개 이상. 원본을 지우면 모양도 사라진다. 게시 게임은 Security 설정 "Allow Mesh / Image APIs" 를 켜야 한다 | ts:<비공개>; dv:research/agent-mode-plan.md:135-136 | 실측 | 일반 | roblox-luau/editable-mesh.md | 없음 | Studio Play 2026-10-16. D-F22 병합. 게시 게임 예산은 다를 수 있음 |
| T-26 | Roblox API | EditableImage 를 `MeshPart.TextureContent` 로 입히면 파트 Color 가 무시된다. `SurfaceAppearance.ColorMapContent` 는 게임 스크립트에서 못 쓴다(`lacking capability Plugin`) — 플러그인 권한 실행(execute_luau)에서는 돼서 함정 | ts:<비공개>; ts:<비공개>; ts:<비공개> | 실측 | 일반 | roblox-luau/editable-mesh.md | 없음 | 권한 문맥 차이 |
| T-27 | Roblox API | 완전 투명한 파트에 건 Highlight 는 아무것도 그리지 않는다. Highlight 는 클라이언트 동시 255개까지, 넘으면 조용히 무시 | ts:<비공개>; ts:<비공개> | 실측 | 일반 | roblox-luau/rendering.md | 없음 | 255 는 문서 인용 |
| T-28 | Roblox API | 서버 `GetProductInfo` 는 없는 ID 에서 `HTTP 404` 를 던지고 `AssetTypeId` 로 종류를 가른다(350~600ms). 클라이언트 `PreloadAsync` 는 종류가 다른 것과 없는 것을 똑같이 `Failure` 로 준다. 화면 밖 ImageLabel 은 preload 후에도 `IsLoaded=false` | ts:<비공개>; ts:<비공개> | 실측 | 일반 | roblox-luau/assets-runtime.md | 없음 | |
| T-29 | Roblox API | 에셋 프라이버시: 2026-05-05 이후 새 계정의 Image·Decal·Mesh 는 기본 Restricted 이고 권한 없는 experience 에서 로드되지 않는다. Decal ID ≠ Image ID. Open Use 여부를 런타임에 읽는 API 없음. 권한 수정 뒤에도 negative caching 으로 한동안 실패 | ts:<비공개>; ts:<비공개> | 서술 | 반일반 | roblox-luau/asset-privacy.md | 없음 | 정책·날짜 의존 |
| T-30 | Roblox API | 파트 윗면 SurfaceGui 의 가로축은 파트의 **긴 변**을 따른다(정사각형 X, 27×30 판 Z). 윗면 글자는 +90° 돌려야 바로 선다 | ts:<비공개>; ts:<비공개> | 실측 | 일반 | roblox-luau/gui-3d.md | 없음 | |
| T-31 | Roblox API | 카메라 앞 로컬 파트 HUD: SurfaceGui 를 `PlayerGui` 밑에 두고 `Adornee` 로 연결, `LightInfluence=0` 이면 2D 만큼 또렷하다. `RenderPriority.Camera+5` 에서 파트 6개 배치 16µs/프레임. 버튼 `Activated` 가 불린다 | ts:<비공개>; ts:<비공개> | 실측 | 일반 | roblox-luau/gui-3d.md | 없음 | 터치 미확인 |
| T-32 | Roblox API | `GetGuiObjectsAtPosition` 은 Adornee 로 붙인 SurfaceGui 안의 것도 돌려주고, 목록은 다음 렌더 뒤에 갱신된다. 가려진 GuiObject 에도 `MouseEnter` 가 오므로 가림 판정은 이 목록으로 하되 ScreenGui 것만 거른다 | ts:<비공개>; dvf:98-105; quad:research/devui-docking-plan.md:51 | 실측 | 일반 | roblox-luau/ui-input.md | 없음 | 세 저장소가 따로 같은 결론. D-F02 병합 |
| T-33 | Roblox API | Transparency 만 1 이고 Visible·Active 가 켜진 GUI 도 아래 클릭을 가져간다 | ts:<비공개> | 실측 | 일반 | roblox-luau/ui-input.md | 없음 | D-F01(Active Frame 이 Catcher 로 가는 클릭을 못 막음)과 함께 정리 필요 |
| T-34 | Roblox API | DragDetector 로 끄는 동안 키보드 `InputBegan` 이 `gameProcessed=true` 로 온다 → `if processed then return` 코드가 끄는 중의 키를 놓친다 | ts:<비공개>; ts:<비공개> | 실측 | 일반 | roblox-luau/ui-input.md | 없음 | 자동 입력으로만 확인. SignalBehavior 미기재 |
| T-35 | Roblox API | `/` 키는 `ChatInputBarConfiguration.KeyboardKeyCode` 를 바꿔도 채팅 포커스를 준다. Tab 은 CoreGui 에 영구히 묶여 있다 | ts:<비공개> | 실측 | 일반 | roblox-luau/ui-input.md | 없음 | |
| T-36 | Roblox API | 새 톱바(1325폭 데스크톱 Studio): `TopbarInset` Min (208,0), 1117×58, `GetGuiInset` 위 58. `ScreenInsets=TopbarSafeInsets` 만으로 코어 버튼에서 8 떨어진다 → 하드코딩 금지 | ts:<비공개>; ts:<비공개> | 실측 | 일반 | roblox-luau/topbar-insets.md | 없음 | 폰·태블릿 미측정 |
| T-37 | Roblox API | 화면을 만드는 순간 `GuiService:GetGuiInset()` 은 0 을 준다 → `TopbarInset` 변경 신호에서 다시 읽는다. TopbarSafeInsets 안의 AbsolutePosition 은 몇 프레임 튄다 | ts:<비공개>; ts:<비공개>; quad:feedback/table-sim-2026-10-12.md:123 | 실측 | 일반 | roblox-luau/topbar-insets.md | 없음 | quad 와 일치 |
| T-38 | Roblox API | `AbsolutePosition`·`InputObject.Position` 은 `IgnoreGuiInset=true` 화면에서도 톱바 인셋 아래를 원점으로 잰다. `GetMouseLocation` 은 인셋 포함 좌표라 `GetMouseLocation() - GetGuiInset()` 으로 맞춘다 | ts:<비공개>; dvf:463-464; /code/Projects/quad/kits/roblox-devui/README.md:658 | 실측 | 일반 | roblox-luau/topbar-insets.md | 없음 | D-F16 병합. quad 와 일치 |
| T-39 | Roblox API | `SetCoreGuiEnabled` 로 톱바를 끌 수 없고, Roblox 메뉴·신고 버튼은 위치·표시를 바꿀 수 없다. `ChatWindowConfiguration` 은 정렬 열거형만 있다 | ts:<비공개> | 서술 | 일반 | roblox-luau/topbar-insets.md | 없음 | DevForum 요약 |
| T-40 | Roblox API | 진입 스크립트가 캐릭터 스폰 전에 카메라를 Scriptable 로 바꾸면 스폰 때 기본 카메라 스크립트가 Custom 으로 되돌린다 | ts:<비공개> | 실측 | 반일반 | roblox-luau/camera.md | 없음 | `CharacterAutoLoads=false` 미확인 |
| T-41 | Roblox API | DataStore(2026-10): 값 JSON 4MiB, 이름·키·스코프 각 50자, buffer 직접 저장 불가. 예산(Read 300+CCU×40 등)은 2026-07-29부터 Open Cloud 와 공유. GetAsync 는 4초 캐시라 확인 읽기는 `UseCache=false`. pcall 실패가 "안 썼다" 를 보장하지 않는다. UpdateAsync 콜백은 재실행되며 yield 금지. SetAsync 에 userIds 를 붙이면 그 게임 예산을 쓰고 영구 데이터가 남는다 | ts:<비공개>; dvr:2026-10-19-server-security.md:183-201; dvr:2026-10-21-settings-datastore.md:57-58,111-121,130,135; dv:research/deploy-notes.md:34-36 | 서술 | 반일반 | roblox-luau/datastore.md | 없음 | D-R44·D-F28 병합. **devplorer 의 "60+플레이어×10" 은 옛 예산**(모순 8) |
| T-42 | Roblox API | Studio 의 DataStore 는 게시된 experience + "Enable Studio Access to API Services" 가 필요하고 **프로덕션과 같은 저장소**를 쓴다(스테이징 실 DataStore 에 쓰여 Play 재시작 후에도 남음). 미게시 파일은 에러, TeleportService 는 Studio 에서 동작하지 않는다 | ts:<비공개>; ts:<비공개> | 실측 | 일반 | roblox-luau/datastore.md | 없음 | |
| T-43 | Roblox API | MemoryStore 한도(쿼터 64KB+1.2KB×유저, 값 32KB, TTL 최대 45일, 단일 파티션). MessagingService 는 best-effort, 히스토리 없음, 1kB → 서버 목록은 MemoryStore TTL 하트비트, Messaging 은 보조 | ts:<비공개> | 서술 | 반일반 | roblox-luau/cross-server.md | 없음 | 시점 의존 |
| T-44 | Roblox API | Remote 한도: 클라→서버 약 500요청/초/클라이언트(같은 종류끼리 공유). UnreliableRemoteEvent 는 초과분과 1000바이트 넘는 페이로드를 버린다. 연결 전에 온 RemoteEvent 는 큐에 쌓였다 첫 연결에 한꺼번에 전달(디버그 연결을 먼저 붙이면 게임 처리기 몫을 가로챔), Unreliable·바인더블은 쌓지 않는다 | ts:<비공개>; dvr:2026-10-19-server-logs-remote.md:228-234; dvr:2026-10-20-bindable-watch.md:140 | 서술 | 일반 | roblox-luau/remotes.md | 없음 | D-R04 병합. 큐잉은 실측 필요 |
| T-45 | Roblox API | `loadstring` 은 서버 전용(`LoadStringEnabled`, NotScriptable), 바이트코드는 못 싣는다. `getfenv`/`setfenv` 는 환경 최적화를 끈다. 표준 라이브러리·문자열 메타테이블은 readonly 라 빈 환경을 줘도 `("x"):rep(2^28)` 로 진짜 string.rep 에 닿아 +256MB. `debug.info(level,"f")` 는 호스트 함수를 건넨다 | ts:<비공개> | 실측 | 일반 | roblox-luau/sandboxing.md | 없음 | readonly·rep 는 luau CLI 0.734 실측, 나머지 인용 |
| T-46 | Roblox API | 스크립트 타임아웃: Studio 10초(설정 가능), 라이브 약 20초(2018 비공식 글). `ScriptContext:SetTimeout` 은 PluginSecurity. 스크립트별 메모리 한도는 없고 서버 한도 6.25GiB+100MiB×최대 접속자 | ts:<비공개> | 서술 | 반일반 | roblox-luau/sandboxing.md | 없음 | 20초 근거가 낡음 |
| T-47 | Roblox API | Script Capabilities(Sandboxed 컨테이너)는 실험 기능(`Workspace.SandboxedInstanceMode=Experimental`). API 접근만 막고 CPU·메모리는 다루지 않는다. 안에서 getfenv/setfenv 불가 | ts:<비공개> | 서술 | 일반 | roblox-luau/sandboxing.md | 없음 | |
| T-50 | Roblox API | 글자 필터 의무: `FilterStringAsync`→`GetNonChatStringForBroadcastAsync`, fromUserId 가 서버에 없으면 던진다. 실패하면 표시하지 않는다. `TextChannel:SendAsync` 는 LocalScript 전용, `DisplaySystemMessage` 는 클라이언트 전용이며 필터 없음 | ts:<비공개>; ts:<비공개> | 서술 | 일반 | roblox-luau/text-safety.md | 없음 | |
| T-51 | 툴체인 | Place Publishing API(Open Cloud)는 EditableImage·EditableMesh·PartOperation·SurfaceAppearance·BaseWrap 이 든 플레이스를 갱신하지 못한다 → Studio 에서 게시 | ts:<비공개> | 서술 | 일반 | roblox-luau/publishing.md | 없음 | 문서 인용 |
| T-52 | 툴체인 | Open Cloud Luau Execution: 스크립트 4MB, 실행 5분, place 당 미완료 10개, 생성 5회/분. 물리 안 돎, Script 자동 실행 안 됨, 데이터모델 변경 저장 안 됨, DataStore 접근 가능, 게시된 버전이 대상 | ts:<비공개> | 서술 | 일반 | roblox-luau/publishing.md | 없음 | |
| T-53 | 툴체인 | Rojo 7.7: 프로젝트 루트 밖 형제 폴더 `$path` 로 빌드·sourcemap 가능. 없는 `$path` 는 에러, 빈 디렉터리는 OK. `.jsonc`·정식 `syncback` 은 7.7.0부터. `rojo upload` 로 Open Cloud 게시. `servePlaceIds` 로 받을 플레이스를 거른다 | ts:<비공개> | 실측 | 일반 | roblox-luau/rojo.md | 없음 | 로컬 rojo 7.7.0 |
| T-54 | perf | 런타임 생성 비용(Studio): 장식 없는 Part 2,000개 생성 118ms(0.078ms/개), 2,000개 정지 시 60fps. 인스턴스 1030개(SurfaceGui 202)에서도 60fps | ts:<비공개>; ts:<비공개> | 실측 | 반일반 | roblox-luau/perf.md | 없음 | 기계 사양 미상, 60fps 상한 |
| T-55 | 모듈·require | Studio 에서 이미 require 된 ModuleScript 는 캐시돼, 바깥에서 Rojo 로 싱크해도 갱신되지 않는다 → Play 를 다시 시작하거나 폴더를 `:Clone()` 한 사본을 require. 콘솔·execute_luau 에서 require 한 모듈은 게임 스크립트의 사본과 상태를 공유하지 않는다 | ts:conventions.md:139; dv:conventions.md:93; dv:research/design-paper.md:43-45; rbvm-sib:135-136; quad:session-summary.md:2493 | 실측 | 일반 | roblox-luau/require.md | 없음 | R-41·D-C02·D-F20 병합 |
| T-56 | Roblox API | 게임 패스는 ProcessReceipt 가 필요 없다. Developer Product 는 필수이고, `PurchaseId` 로 멱등 처리하며 저장이 끝난 뒤에만 `PurchaseGranted`(아니면 `NotProcessedYet` → 재접속 때 재호출) | ts:<비공개> | 서술 | 일반 | roblox-luau/monetization.md | 없음 | haiku 작성 보고서. 인용 재확인 필요(ts:<비공개>) |
| T-57 | 하네스·에이전트 운영 | 다른 모델 계열(agy/Gemini, Codex)은 "원문 그대로" 라며 지어낸 코드 인용을 붙이고 엔진 사실을 단정한다(예: "파트 속성은 스트리밍과 무관하게 모든 클라이언트에 간다" → T-13 실측으로 반증). 모든 주장은 메인이 원문·PoC 로 재현한 뒤에만 쓴다. 이 작업 공간에서 Codex bwrap 샌드박스는 뜨지 않았다 | ts:conventions.md:168-174; ts:<비공개>; ts:<비공개>; dvr:2026-11-04-structure-outside.md:3-5,66-69; tbox-cr:321-343,426-468 | 실측 | 일반 | harness/external-models.md | 없음 | D-R57·X-25 병합. 격리: 별도 uid, 과제마다 HOME, 브랜치 없는 worktree |
| T-59 | 하네스·에이전트 운영 | Gemini 의 소리 듣기: 정체 12개 중 7 정확·3 근접, 음높이 방향은 실패. 확신 값(0.95~0.98)은 정답과 무관하고, 123개를 한 번에 주니 같은 답을 되풀이했다 → 소리 판정에 쓰지 않기로 결정 | ts:<비공개> | 실측 | 반일반 | harness/external-models.md | 없음 | 작은 표본 |
| T-60 | 하네스·에이전트 운영 | 모델 평가는 눈가림으로: 파일 이름·mp3 ID3/APEv2 태그·wav 덧붙은 덩어리가 답을 흘린다(`strings` 로 발견) → 벗기고, 무작위 이름, 정답 파일은 평가 대상 uid 가 못 읽게(700) | ts:<비공개> | 실측 | 일반 | harness/eval-design.md | 없음 | |
| T-61 | 하네스·에이전트 운영 | 조사 에이전트에게는 쓸 파일 하나와 스크래치 디렉터리를 지정하고 형제 저장소를 작업 디렉터리로 쓰지 말라고 명시한다(`mise -C` 로 남의 생성 파일을 덮어쓴 사고). 팬아웃은 코드 실행·출처 확인 조각에만, 문서 정합성 검토는 나누지 않는다. 완료 판정은 하네스 알림 | ts:conventions.md:158-167; ts:<비공개> | 사용자결정 | 일반 | harness/subagents.md | 없음 | 사고 2026-10-11 |
| T-62 | 하네스·에이전트 운영 | 모델은 과제 성격대로 섞는다(목록화 가벼운 모델, 설계 강한 모델, 검토 다른 계열). 가벼운 모델 보고서는 설계에 쓰기 전에 인용을 다시 연다. 보고서와 PoC 가 어긋나면 PoC 가 이긴다. 플랫폼 사실은 1차 출처나 Studio 실측 전까지 【추정】 | ts:conventions.md:73-74,159-160,175-176; ts:<비공개> | 사용자결정 | 일반 | harness/subagents.md | 없음 | |
| T-63 | 하네스·에이전트 운영 | 무거운 실행(벤치·퍼저)은 `choom -n 1000` 으로 감싸 OOM 때 먼저 죽게 하고 PreToolUse 훅이 강제한다. N 을 몰래 줄여 "통과" 로 보고하지 않는다. 게이트는 exit code, 보고에는 검증 범위("타입·포맷만"/"스펙"/"Studio 실측")를 적는다 | ts:conventions.md:92-95,180-182; ts:settings.json:8-19; ts:<비공개> | 사용자결정 | 일반 | harness/heavy-runs.md | 일부(kb:luau-verify/references/negative-controls.md 자원 상한) | 원래 quad 규약. 이 감사 중에도 훅이 텍스트 append 를 오탐했다(키워드 매칭) |
| T-64 | 하네스·에이전트 운영 | `git push`·`git remote add` 는 `settings.json` 의 `permissions.deny` 로 기계적으로 막고, 커밋은 메인이 작업 단위마다, 푸시는 사용자가 | ts:settings.json:3-6; ts:conventions.md:195-198 | 사용자결정 | 일반 | harness/git-permissions.md | 없음 | D-C06(서버 pre-receive 훅으로 강제)과 비교 |
| D-R01 | Roblox API | RemoteEvent/RemoteFunction 를 건넌 표는 엔진이 다시 역직렬화한 사본이다. 메타테이블과 함수가 떨어지므로 서버의 `typeof` 판정을 믿을 수 있다(가짜 Vector3·메타테이블 표로 위조 불가). 받은 표는 클라이언트와 별칭을 공유하지 않는다. 프록시 테이블을 보내면 빈 테이블이 된다 | dvr:2026-10-20-actions-security.md:15; dvr:2026-10-19-server-edit.md:268-270; dvr:2026-10-19-server-logs-remote.md:200,256-257; dvr:2026-10-19-server-security.md:361-362; rbvm-cr:261 | 서술 | 일반 | roblox-luau/remote-trust.md | 없음 | R-43 병합. 원격 쪽 실측 없음(바인더블은 D-R02 실측) |
| D-R02 | Roblox API | BindableEvent:Fire 는 처리기마다 표를 새로 복사한다. 메타테이블은 버리고 함수는 같은 정체성으로 온다(rawequal 참). newproxy·thread 는 nil, `n` 유지. 순환 표는 "tables cannot be cyclic", 불리언 키 표는 "Invalid table key type used" 로 Fire 자체가 실패. Instance 키 표는 성공 | dvr:2026-10-20-bindable-watch.md:20-21,72-85 | 실측 | 일반 | roblox-luau/remote-trust.md | 없음 | Studio Edit 2026-10-20, 플러그인 문맥 |
| D-R03 | perf | 바인더블 인자 복사 비용: 2만 항목 표를 Fire 하면 1회 약 14ms, 처리기 하나 늘 때마다 2~4ms. 작은 인자 2000회 1.9ms. 바인더블은 크기 상한이 없다 | dvr:2026-10-20-bindable-watch.md:93-104 | 실측 | 반일반 | roblox-luau/perf.md | 없음 | Studio Edit, 잡음 큼 |
| D-R06 | Roblox API | 원격 페이로드 검사 순서: 재귀하기 전에 깊이 상한, 순환·메타테이블(`__metatable=false` 포함)·Instance·buffer·vector·함수·NaN·inf 거부, 항목 수 상한, 대략 크기 뒤 실제 `JSONEncode` 길이 재확인(제어문자 이스케이프로 약 6배) | dvr:2026-10-19-server-security.md:359-363 | 실측 | 일반 | roblox-luau/remote-validation.md | 없음 | 실행 검증과 추론 혼재 |
| D-R07 | Roblox API | 원격으로 건너오는 Instance 는 그 클라이언트에도 복제된 것뿐이라 서버 전용 인스턴스는 위조할 수 없다. 받는 쪽에 없는(스트리밍 밖 포함) Instance 참조는 nil 이 된다 → 이 nil 로 "이 클라이언트에 없음" 을 판정할 수 있다 | dvr:2026-10-19-server-logs-remote.md:256-257; dvr:2026-10-19-server-security.md:351; dvr:2026-10-19-server-security-round2.md:153; dv:research/design-paper.md:50-53 | 실측 | 일반 | roblox-luau/replication.md | 없음 | 스트리밍 nil 은 Studio Play 2026-10-19 실측. D-F17 병합 |
| D-R08 | 동시성 | RemoteFunction 호출은 호출마다 별도 스레드다. 확인과 설정 사이에 양보 지점이 있으면 동시 요청이 모두 확인을 통과해 쿨다운이 뚫린다 → 확인과 예약은 양보 없는 구간에서, 실패 시 내가 넣은 값일 때만 되돌린다 | dvr:2026-10-20-actions-security.md:36-43,159; dvr:2026-10-20-recorder-depth.md:30-42; dvr:2026-10-20-live-check.md:99-101 | 실측 | 일반 | roblox-luau/concurrency.md | 없음 | Studio Play 에서 수정 확인 |
| D-R09 | 동시성 | 협력 스케줄링이라 양보 없는 구간에는 다른 스레드가 못 낀다. 반대로 후크·DataStore 호출이 양보하는 사이에는 권한 회수 같은 일이 끼므로 효과 직전에 다시 확인한다(TOCTOU) | dvr:2026-10-21-ancestry.md:56-60; dvr:2026-10-19-server-security.md:98-119; dvr:2026-10-19-server-edit.md:205-215; dvr:2026-10-20-action-check.md:51-61 | 서술 | 일반 | roblox-luau/concurrency.md | 없음 | |
| D-R10 | 동시성 | 서버의 `InvokeClient` 는 클라이언트가 답하지 않는 것만으로 서버 스레드를 붙잡는다. OnInvoke 없는 BindableFunction:Invoke 는 기다린다. 시한이 지나도 spawn 한 스레드는 남으므로 동시 호출 수 상한이 필요하다 | dvr:2026-10-19-server-security.md:353-354; dvr:2026-10-19-server-logs-remote.md:125-136; dvr:2026-11-08-post-move-audit.md:102 | 서술 | 일반 | roblox-luau/concurrency.md | 없음 | `task.cancel` 이 엔진 호출 안 스레드를 끊는지 미실측 |
| D-R11 | Roblox API | DisplayName 은 유일하지 않고 다른 사람의 사용자명과 똑같이 지을 수 있다 → 권한 대상은 UserId 나 정확한 사용자명으로만 | dvr:2026-10-19-server-security.md:16-43,383-385 | 실측 | 일반 | roblox-luau/players.md | 없음 | CLI 시뮬레이션 |
| D-R12 | Roblox API | 복제 경계: PlayerGui 는 주인에게만, ServerStorage·ServerScriptService 는 복제 안 됨. ReplicatedStorage 에 잘못 두면 ModuleScript 소스까지 모두에게 가고 한 번 내려간 코드는 회수할 수 없다 → 시작 때 `IsDescendantOf` assert | dvr:2026-10-19-server-security.md:164-179,342-346; dvr:2026-10-19-server-edit.md:118-120; dvr:2026-10-20-client-actions.md:98-100 | 서술 | 일반 | roblox-luau/replication.md | 없음 | |
| D-R13 | Roblox API | 다른 플레이어의 Backpack 도 모두에게 복제된다고 알려져 있다(추정). StarterGear 미확인, Stats/StatsItem 은 클라이언트에 없다 | dvr:2026-10-19-server-round6.md:192-206; dvr:2026-10-19-ux-explore.md:11-14 | 서술 | 일반 | roblox-luau/replication.md | 없음 | 실측 보류 |
| D-R15 | 스타일·관용 | 판정 후크의 반환은 닫힌 쪽(fail-closed)으로 해석한다: "가리기" 는 `~=nil and ~=false` 면 가리고, "허용" 은 정확히 `==true` 일 때만 연다. Lua 식 truthy 로 해석하면 반대로 열린다 | dvr:2026-10-19-server-security-round2.md:15-24; dvr:2026-10-19-server-structure.md:90-96; dvr:2026-10-20-action-check.md:41-49 | 실측 | 일반 | luau-style/fail-closed.md | 없음 | D-F23 과 같은 reference |
| D-R16 | Roblox API | `Archivable=false` 인 인스턴스는 `Clone()` 이 nil 을 돌려주고 그런 자손은 소리 없이 빠진다. `GetDescendants` 는 Archivable 과 무관하게 보인다 | dvr:2026-10-19-server-edit.md:36-37; dvr:2026-10-19-server-structure.md:157-158; dvr:2026-10-20-client-actions.md:73-74 | 서술 | 일반 | roblox-luau/instance-api.md | 없음 | Studio 실측 기록 없음 |
| D-R18 | Roblox API | `OnServerInvoke`·`OnInvoke` 콜백은 설정한 스크립트에 묶여, 그 스크립트를 지우면 "Script that implemented this callback has been destroyed". 꺼진 LocalScript 를 서버가 켜면 모든 클라이언트에서 돈다 | dvr:2026-10-19-server-structure.md:106-114; dvr:2026-10-19-server-edit.md:59-71 | 실측 | 반일반 | roblox-luau/scripts.md | 없음 | |
| D-R19 | 툴체인 | `getfenv` 는 deprecated 린트로 게이트가 실패한다. `getfenv(2)` 는 pcall·`task.spawn` 을 거치면 엉뚱한 레벨을 가리킨다 → 호출자 스크립트는 `debug.info(2,"s")` | dvr:2026-10-19-server-structure.md:106-114,178-179; dvr:2026-11-04-server-split.md:28 | 실측 | 일반 | luau-style/deprecated-apis.md | 일부(kb:luau-verify/references/tooling.md §5 린트) | T-45(getfenv 는 최적화도 끈다)와 같은 reference |
| D-R20 | Roblox API | Luau 로 쓴 바이트코드 인터프리터(Fiu)·컴파일러(LuauCeption): 시간 훅이 CALL·RETURN·JUMPBACK·FORLOOP 에서만 불려 `string.rep(2^30)`·역추적 패턴·`table.sort` 같은 네이티브 호출 하나는 못 끊는다. 네이티브보다 11~109배 느리고(--codegen 6~82배), LuauCeption 은 괄호 250겹 508바이트 입력에 60초 초과. 3MB 컴파일러 require 0.3초. `pcall(loadstring, …)` 로 LoadStringEnabled 감지 | dvr:2026-10-20-interpreter.md:36-47,69-83,134-142; ts:<비공개>; dv:research/interpreter-survey.md:22-24,39-41,55-58 | 실측 | 반일반 | roblox-luau/sandboxing.md | 없음 | Fiu `fa1983d` 의존. T-49·D-F26 병합 |
| D-R21 | 동시성 | 끝나지 않는 대기(`Event:Wait()`, `task.wait(1e9)`, 최상위 `coroutine.yield()`)는 본문을 자기 스레드에서 돌리고 시한에 `task.cancel` 로 끊는다 | dvr:2026-10-20-interpreter.md:56-67,173-174 | 서술 | 일반 | roblox-luau/threads.md | 없음 | |
| D-R22 | GC·수명 | Instance 를 강하게 쥐는 id 표는 Destroy 된 것도 수거되지 못하게 한다. 상한과 정리(prune)로 대신하되, 상한에 닿은 뒤 매 요청 prune 하면 CPU 증폭기가 되므로 백오프가 필요하다 | dvr:2026-10-19-server-security.md:75-94,389-390; dvr:2026-10-19-server-security-round2.md:43-54 | 서술 | 일반 | roblox-luau/gc.md | 없음 | weak 표를 "실측 필요" 로 피했으나 quad·rbvm(R-18)이 이미 실측(모순 13) |
| D-R23 | Roblox API | 원격 DoS 예산은 요청 수가 아니라 일의 양으로, 일을 하기 전에 청구한다. `GetChildren`·`GetDescendants` 는 자르기 전에 배열 전체를 만든다. 거절 경로에서 청구가 빠지면 일이 공짜가 된다 | dvr:2026-10-19-server-security.md:47-71; dvr:2026-10-19-server-security-round2.md:58-62; dvr:2026-10-19-server-logs-remote.md:85-107 | 실측 | 일반 | roblox-luau/remote-rate-limit.md | 없음 | 버킷은 CLI 시뮬레이션. 엔진 비용 미실측 |
| D-R24 | Roblox API | `QueryDescendants` 는 깊이 200 사슬·결합자 4개까지 0.02ms 이하. 결합자 뒤 `*` 는 에러, `$=` 는 "not a valid selector". 깊이 500~1000 사슬에서 Studio 가 무응답 | dvr:2026-10-19-server-round6.md:312-317; dvr:2026-11-08-post-move-audit.md:16,40 | 실측 | 일반 | roblox-luau/instance-api.md | 없음 | `:has()` 미실측. `$=` 지원 기억을 실측이 뒤집음 |
| D-R26 | 스타일·관용 | Luau `string.format("%q", s)` 는 개행을 "백슬래시 + 실제 개행" 으로 써서 두 줄이 된다 → 한 줄 로그는 `\ddd` 로 직접 이스케이프 | dvr:2026-10-19-shared-specs.md:21-24; dvr:2026-10-20-bughunt.md:41 | 실측 | 일반 | luau-style/strings.md | 없음 | luau CLI |
| D-R27 | 스타일·관용 | 패턴 클래스: `%w`·`%a` 는 ASCII 만(`é_1` 불일치), `%a` 는 `_`·숫자를 포함하지 않아 `@(%a+)` 가 `@must_use` 를 `must` 에서 끊는다. `%c` 는 `\0`·DEL 에 일치. 앵커 없는 패턴은 줄 중간에서도 맞는다 | dvr:2026-10-19-server-structure.md:160; mw:known-issues.md:170-183 | 실측 | 일반 | luau-style/strings.md | 없음 | M-12 병합 |
| D-R28 | perf | Lua 패턴 역추적은 다항 시간이다: `.-.-.-.-.-.-b` 를 N자 입력에 쓰면 12자 0.3ms, 18자 3ms, 24자 15ms, 60자 100초 초과(O(N^6)). `find` 한 번이 120자 입력에 10초를 넘긴 사례도 있고 네이티브에서도 같다. 명령 수 예산·인터럽트로 못 막는다. `s=s..s` 18번이면 명령 20개로 256MB → 사용자 패턴에는 길이·수량자 수·대상 길이 상한 | dvr:2026-10-19-shared-specs.md:56-58; dvr:2026-10-20-interpreter.md:77; ts:<비공개> | 실측 | 일반 | luau-perf/strings.md | 없음 | luau CLI 0.734. T-48 병합. X-19(잘못된 패턴은 매칭 때 예외)와 짝 |
| D-R29 | 스타일·관용 | UTF-8: `#s`·`string.len` 은 바이트("한"=3). `string.sub` 는 다바이트 글자 가운데를 자른다. "`utf8.len` 이 nil 인 동안 줄이기" 는 O(limit²) → 이어짐 바이트(0x80–0xBF)를 최대 3번 거슬러 O(1). 잘못된 UTF-8 에서 `utf8.len` 은 `nil, 위치` 를 돌려주지만 `utf8.codes` 는 던진다 → `utf8.len(s) or 0` 은 조용히 0. `utf8.len` 은 서러게이트·U+10FFFF 초과를 거절 | dvr:2026-10-19-shared-specs.md:26-30; dvr:2026-10-19-server-edit.md:171-187; dvr:2026-10-19-server-round6.md:166-182,212; mrow-rv:357-367,1499; tbox-cr:214 | 실측 | 일반 | luau-style/strings.md | 없음 | CLI·Studio·lute·mlua 공통. M-10·X-18 병합 |
| D-R30 | 스타일·관용 | 로그 줄 위조는 `%c` 치환만으로 못 막는다. U+0085, U+2028/9, 방향 제어 문자, 보이지 않는 문자, 한글 채움 문자(3164·115F·1160·FFA0)도 막아야 한다 | dvr:2026-10-19-server-round6.md:156-221; dvr:2026-10-19-shared-specs.md:71-73 | 실측 | 일반 | roblox-luau/text-safety.md | 없음 | 전체 문자 목록은 원천에 |
| D-R31 | Roblox API | `RichText` 라벨에 플레이어가 정한 이름을 그대로 넣으면 `<font transparency="1">` 같은 태그로 화면을 속일 수 있다 → `& < > " '` 이스케이프 | dvr:2026-10-19-server-security.md:228-242,399 | 서술 | 일반 | roblox-luau/text-safety.md | 없음 | |
| D-R32 | 스타일·관용 | `table.insert(t, nil)` 은 아무것도 넣지 않는다 → 병렬 배열의 인덱스가 밀려 다른 대상에 값이 쓰인다. `t[i]=v` 로 채운다 | dvr:2026-11-04-structure-outside.md:22 | 실측 | 일반 | luau-style/tables.md | 없음 | 실제 버그. M-14 와 짝 |
| D-R35 | 스타일·관용 | yield 를 끼고 순회하는 중에 새 키를 넣으면 그 키를 볼 수도 못 볼 수도 있다(CLI 에서 일부를 건너뜀). 기존 키에 nil 대입은 안전 | dvr:2026-10-21-settings-datastore.md:65-74 | 실측 | 일반 | luau-style/tables.md | 없음 | luau 0.734 |
| D-R37 | 에러 | 믿을 수 없는 값에 `tostring`·`#`·일반화 반복을 쓰면 `__tostring`·`__len`·`__iter` 가 돌아 던지거나 양보하거나 내용을 속인다 → 검증기는 `pcall(tostring)`, `rawlen`/`rawget`/`next` 로 실제 필드만 본다. xpcall 처리기 안의 `tostring` 이 던지면 처리기 결과 대신 에러 문자열이 돌아온다. Roblox 원격은 메타테이블을 벗기지만 같은 프로세스에서 온 값은 해당 | dvr:2026-10-20-actions-security.md:30,106-111; dvr:2026-10-20-interpreter.md:98-107; dvr:2026-10-20-bughunt.md:30; tbox-cr:134-139,299 | 실측 | 일반 | luau-style/errors.md | 없음 | X-16 병합 |
| D-R38 | 에러 | pcall 인자 평가 함정: `pcall(f(x))` 는 `f(x)` 를 pcall 밖에서 먼저 실행해 그 반환값을 호출하려 한다("attempt to call a string value") — 성공해도 실패하고 f 의 에러도 못 잡는다. `pcall(inst.Method, inst, ...)` 의 메서드 인덱싱도 pcall 밖이다 → `pcall(f, x)` 또는 인덱싱을 클로저 안에서 | mw:known-issues.md:117-127; dvr:2026-10-21-modified-bold.md:17-28,39-44 | 실측 | 일반 | luau-style/errors.md | 없음 | M-13 병합. `IsPropertyModified` 0.11µs/호출 |
| D-R39 | 에러 | pcall 반환값 실수: `local ok = pcall(...)` 는 성공 여부만 담는다. if 식이 pcall 의 둘째 값을 버린 버그. `IsA("없는클래스")` 는 에러 없이 false | dvr:2026-10-19-shared-specs.md:107-108; dvr:2026-10-21-reset-default.md:84-85 | 서술 | 일반 | luau-style/errors.md | 없음 | |
| D-R40 | Roblox API | SignalBehavior 가 Deferred 면 `GetPropertyChangedSignal` 처리기가 대입 **뒤에** 돈다 → "깃발 켜고 대입 후 끄기" 패턴이 깨진다. BindableEvent 처리기는 Fire 가 끝난 뒤 돌았다(실측) | dvr:2026-10-20-client-palette-copy.md:49-52; dvr:2026-10-20-bindable-watch.md:85 | 실측 | 일반 | roblox-luau/signals.md | 없음 | quad H-291 과 같은 결론(모순 16: devplorer 서술만 "미실측") |
| D-R42 | Roblox API | `InvokeServer` 와 시한 없는 `WaitForChild` 는 영원히 기다린다 → `task.delay` 경쟁으로 시한을 건다 | dvr:2026-10-19-client-code.md:46-53,186; dvr:2026-10-19-server-security.md:149-160 | 서술 | 일반 | roblox-luau/concurrency.md | 없음 | |
| D-R43 | Roblox API | `HttpService:JSONEncode` 가 혼합·희소 키, 0·음수 키, inf, 잘못된 UTF-8 을 어떻게 다루는지는 미실측이다 → 항상 pcall, 키는 "모두 문자열" 이나 "1..n 밀집 배열" 만 받는다 | dvr:2026-10-19-server-security.md:209-214,224; dvr:2026-10-19-shared-specs.md:47-49; dvr:2026-10-19-server-round6.md:248 | 서술 | 일반 | roblox-luau/http-json.md | 없음 | devplorer 안에서 서술이 셋으로 갈림(모순 14). 실측할 가치 큼 |
| D-R45 | Roblox API | GetAsync 가 클라이언트 시한을 넘기면 클라이언트는 실패로 보고 서버는 늦게 성공한다. 기본값으로 시작한 창이 저장하면 실제 값을 덮어쓴다. SetAsync 는 마지막 쓰기가 이기므로 UpdateAsync | dvr:2026-10-21-settings-datastore.md:21-40,77-86,147-148 | 서술 | 일반 | roblox-luau/datastore.md | 없음 | |
| D-R46 | Roblox API | 원격 값 검증: `CFrame.fromMatrix` 로 비정규직교 회전이 들어오므로 `Orthonormalize`. EnumItem 은 `EnumType` 으로 비교하고 특성 값이 될 수 없다. 특성 이름은 `^[%w_]+$`, 100자 이하, `RBX` 접두 금지 | dvr:2026-10-19-server-edit.md:232-240,268-270,300,304-309; dvr:2026-10-19-server-structure.md:128-134,160 | 실측 | 일반 | roblox-luau/remote-validation.md | 없음 | Studio Play 2026-10-19 |
| D-R47 | Roblox API | `Script.Source` 는 런타임에 읽히지 않는다. `ReflectionService:GetPropertiesOfClass` 는 약 650개 클래스의 속성 목록과 Category·Permits·Serialized 를 주고(아이콘·정렬 순서는 없음), `Permits.Write` 는 허용 목록으로 판정해야 새 능력에 열린 쪽으로 실패하지 않는다 | dvr:2026-10-19-server-edit.md:128-150,293; dvr:2026-10-19-server-structure.md:136-140; dv:research/design-paper.md:59-60 | 실측 | 반일반 | roblox-luau/reflection.md | 없음 | D-F19 병합 |
| D-R48 | Roblox API | 클라이언트가 네트워크 소유자인 부품의 위치·속도 변경은 서버로 복제된다 | dvr:2026-10-19-server-edit.md:256-257 | 서술 | 일반 | roblox-luau/network-ownership.md | 없음 | T-07~T-09 와 같은 reference |
| D-R49 | Roblox API | 서버가 PlayerGui 에 넣은 ScreenGui·클론 모듈의 자손 LocalScript 와 `RunContext=Client` Script 는 넣는 순간 돈다(`ResetOnSpawn=false` 면 리스폰 뒤에도 남음). 의존성의 test 폴더(`RunContext=Plugin`)가 릴리스 번들에 섞인 실례 | dvr:2026-10-20-client-actions.md:56-66; dvr:2026-11-08-post-move-audit.md:24; dv:research/design-paper.md:38-42 | 실측 | 일반 | roblox-luau/scripts.md | 없음 | D-F21 병합. Legacy Script 미실측 |
| D-R50 | Roblox API | 부모 없이 `Instance.new` 로 만든 것은 게임 코드가 관찰하지 못한다 → 기본값은 만들어 읽고 Destroy 해서 얻는다. `ResetPropertyToDefault` 범위는 미확인 | dvr:2026-10-21-reset-default.md:17-37,61-70 | 서술 | 일반 | roblox-luau/instance-api.md | 없음 | |
| D-R52 | Roblox API | 일부 CoreGui 계열 인스턴스는 `Name` 을 읽을 때 에러가 날 수 있다 → `game:GetDescendants()` 전체를 돌 때는 pcall | dvr:2026-10-19-server-logs-remote.md:100-101; dvr:2026-10-21-ancestry.md:19 | 서술 | 일반 | roblox-luau/instance-api.md | 없음 | 실측 필요 |
| D-R53 | Roblox API | LogService: 서버 `print` 도 `MessageOut` 으로 모인다. "Stack Begin/End" 와 "Script '…', Line N" 은 별도 줄로 와서 직전 에러에 붙여야 한다. `GetLogHistory` 로 이전 기록을 채운다 | dvr:2026-10-19-server-logs-remote.md:22-51,140-162,267-268 | 실측 | 반일반 | roblox-luau/logservice.md | 없음 | |
| D-R54 | runtime·엔진 | `os.clock` 은 단조 시계다. `GetServerTimeNow` 는 보정 때문에 역행하거나 크게 뛸 수 있다 | dvr:2026-10-19-server-security.md:363-365; dvr:2026-10-20-recorder-depth.md:83-85 | 서술 | 일반 | roblox-luau/time.md | 없음 | |
| D-R56 | 하네스·에이전트 운영 | sonnet 서브에이전트가 공격 입력을 구체화하다 안전 분류기에 응답이 끊겼다 → 문서에는 구체적 공격 입력을 적지 않고, 짚은 지점만 메인이 받아 고친다 | dvr:2026-10-19-redteam.md:3-4 | 서술 | 일반 | harness/subagents.md | 없음 | |
| D-R58 | 하네스·에이전트 운영 | 독립 감사자(병렬, 읽기 전용)에게는 메인의 결론을 주지 않는다. 리뷰에는 실행 검증·추론·추정 표지를 단다 | dvr:2026-11-08-post-move-audit.md:5; dvr:2026-10-20-bughunt.md:3; dvr:2026-10-19-client-code.md:9-11 | 사용자결정 | 일반 | harness/review-protocol.md | 없음 | R-53(근거 태그)과 같은 reference |
| D-F01 | Roblox API | `Active = true` 인 Frame 은 그 아래 TextButton(Catcher)으로 가는 GUI 클릭을 막지 못한다(ZIndex 를 올려도) → 클릭 흡수는 내용 뒤에 투명 TextButton | dvf:585-592; dv:feedback/devui-upstream-candidates-2026-10-21.md:86-88 | 실측 | 일반 | roblox-luau/ui-input.md | 없음 | Studio Play 2026-10-20. quad 10-07 기록과 반대(모순 7). T-33 과 함께 정리 |
| D-F03 | Roblox API | `AutomaticSize` 부모 안에 Scale 크기 자식(`UDim2.new(1,0,0,1)`)을 두면 부모가 화면 너비까지 늘어난다 → 높이 1 Offset 프레임 + `UIFlexItem` Stretch | dvf:145-147; dvf21:66-68; quad:feedback/consumer-kits-studio-qa-2026-10-07.md:205 | 실측 | 일반 | roblox-luau/ui-layout.md | 없음 | DevForum 직원 답변 인용 |
| D-F04 | Roblox API | `AutomaticSize=Y` 인 ScrollingFrame 은 `UISizeConstraint.MaxSize.Y` 를 지키지 않는다 → 높이를 `math.min(내용, 상한, 남은 공간)` 으로 직접 정한다 | dvf:594-598; dv:feedback/devui.md:142-144 | 실측 | 반일반 | roblox-luau/ui-layout.md | 없음 | 원인 추정. 최소 재현 필요 |
| D-F05 | Roblox API | 글이 잘린 상태의 `TextBounds` 는 잘린 글의 폭이다 → 그 값으로 폭을 정하면 계속 줄어드는 순환. 글 폭은 `TextService:GetTextBoundsAsync` | dvf21:73-75 | 실측 | 일반 | roblox-luau/ui-layout.md | 없음 | |
| D-F06 | Roblox API | `ImageButton.Image` 는 단추 몸 전체를 채우고 `UIPadding` 은 자식에만 걸린다 → 아이콘 여백은 안쪽 ImageLabel | dvf21:37-38 | 실측 | 일반 | roblox-luau/ui-layout.md | 없음 | |
| D-F07 | Roblox API | TextBox 는 기본으로 글을 자르지 않는다(긴 글·PlaceholderText 가 밖으로 샘) → `ClipsDescendants = true` | dvf21:97-101 | 실측 | 일반 | roblox-luau/ui-layout.md | 없음 | |
| D-F08 | Roblox API | `VerticalScrollBarInset = ScrollBar` 면 스크롤바가 보일 때만 그 폭만큼 내용 폭이 준다 | dvf21:103-105 | 실측 | 일반 | roblox-luau/ui-layout.md | 없음 | |
| D-F09 | Roblox API | `RichText` 와 `TextTruncate=AtEnd` 는 함께 동작한다. "줄어드는 이름 + 고정 꼬리표" 는 `AutomaticSize X` + `UIFlexItem` Shrink | dvf:479-482 | 실측 | 일반 | roblox-luau/ui-layout.md | 없음 | devui.md:89 반대 주장은 철회됨 |
| D-F10 | Roblox API | Escape 는 Roblox 메뉴(`GuiService.MenuIsOpen`)를 열고 그동안 클릭이 먹통이다. ContextActionService Sink 로 못 막고 `SetMenuIsOpen` 은 RobloxScript 권한. TextBox 포커스 중에는 `InputBegan` 의 `gameProcessed==true` 라 단축키가 무시된다 | dvf:484-486; dv:feedback/devui.md:110-111; dvr:2026-10-20-client-palette-copy.md:42-44,105-107,149 | 실측 | 일반 | roblox-luau/ui-input.md | 없음 | D-R41 병합. T-34(끄는 중 gameProcessed) 와 같은 reference |
| D-F11 | Roblox API | Shift+P 는 내장 개발자 Freecam 이고, 이를 포함한 단축키를 누르면 모든 ScreenGui 가 숨는다 | dvf:487 | 실측 | 일반 | roblox-luau/ui-input.md | 없음 | 권한자 계정 기준 |
| D-F12 | Roblox API | 다른 TextBox 에 포커스가 있을 때 포커스 없는 TextBox 의 `CursorPosition` 을 쓰면 포커스가 그 상자로 넘어간다 | dvf:404,488-490 | 실측 | 일반 | roblox-luau/ui-input.md | 없음 | `CaptureFocus` 흉내로는 재현 안 됨 |
| D-F13 | Roblox API | 생성 직후나 부모가 붙기 전의 `CaptureFocus()` 는 먹지 않는다 → `task.defer` 뒤 `Parent and Visible` 확인 후 호출 | dvf:72-78 | 실측 | 반일반 | roblox-luau/ui-input.md | 없음 | |
| D-F14 | Roblox API | 게임 스크립트에는 클립보드 API 가 없다. 읽기 전용 TextBox 에 `CaptureFocus` + 전체 선택 후 사용자가 Ctrl+C 가 유일한 길 | dvf:116-120,267 | 실측 | 일반 | roblox-luau/ui-input.md | 없음 | |
| D-F15 | Roblox API | TextBox 는 Tab 을 가로챌 수 없다. `\t` 가 들어온 뒤에야 알 수 있으므로 들어오기 전 상태로 되돌린다 | dvf:160-163 | 서술 | 일반 | roblox-luau/ui-input.md | 없음 | |
| D-F18 | runtime·엔진 | 물리로 떨어지는 Part 의 `Position` 은 `GetPropertyChangedSignal` 을 0회 발화한다. Studio 에서 `game.JobId` 는 빈 문자열이다 | dv:research/feature-proposals-2.md:97,184,243 | 실측 | 일반 | roblox-luau/runtime.md | 없음 | 원 기록 dv:audit/2026-10-19-insight.md. StreamingTargetRadius 부분은 T-14 로 |
| D-F23 | Roblox API | 복제되는 모든 것은 공개로 간주한다. 클라이언트 쪽 게이트는 겉모양일 뿐이므로 서버가 요청마다 다시 검사하고, 판정기가 없으면 거부한다(fail-closed) | dv:research/cmdr-survey.md:19,45,61-62,71-74 | 서술 | 일반 | roblox-luau/security.md | 없음 | Cmdr 문서 인용 |
| D-F24 | Roblox API | RemoteEvent 입력을 `loadstring` 에 넣으면 백도어다(그래서 `LoadStringEnabled` 기본 꺼짐). 클라이언트가 보낸 바이트코드는 검증할 수 없으므로 서버는 소스만 받아 직접 컴파일한다 | dv:research/interpreter-survey.md:73-75,83-86 | 서술 | 일반 | roblox-luau/security.md | 없음 | T-45 와 교차참조 |
| D-F25 | Roblox API | 툴박스 모델의 `PackageLink.AutoUpdate=true` 는 공급망 위험이다. rbxm 은 Lune 으로 풀어 소스만 읽어 검사할 수 있다 | dv:research/devexplorer-review.md:5,21-22 | 실측 | 일반 | roblox-luau/security.md | 없음 | |
| D-F27 | 모듈·require | `require` 는 처음 로드되는 모듈의 코드를 실행한다(부작용) → 도구가 임의 모듈을 require 하는 것은 사실상 코드 실행이다. "타입만 가져오기" 도 안 된다 | dv:research/feature-proposals-2.md:77,265-266; tbox:CLAUDE.md:11-13 | 서술 | 일반 | roblox-luau/require.md | 없음 | X-06 병합 |
| D-F29 | Roblox API | F9 서버 출력은 소유자와 편집 권한 그룹원만 본다. RemoteFunction 을 가로채 캡처하면 `InvokeClient` 가 깨진다 | dv:research/feature-survey.md:22-23,101-102 | 서술 | 일반 | roblox-luau/runtime.md | 없음 | |
| D-F30 | 기타 | (타입) 새 솔버는 주석을 단 지역 변수(`local h: State<number>`)도 분기마다 대입 값의 타입으로 좁힌다. 갈래가 합쳐지면 유니언이 되어 제네릭 메소드 호출이 "Cannot call a value of the union type" → 주석을 단 if 식으로 우회 | dvf:48-58 | 실측 | 반일반 | luau-types/unions-singletons.md | 일부(kb:luau-types/references/unions-singletons.md §5) | luau-lsp 1.69.0. quad 없이 최소 재현 필요 |
| D-F31 | 기타 | (타입) 클로저 안 루프에서 const 업밸류 옵셔널을 좁히거나, 필드를 좁힌 뒤 다른 호출이 끼면 "could be nil" | dvf:492-496 | 실측 | 일반 | luau-types/solver-limits.md | 일부(kb:luau-types/references/solver-limits.md:78 "최소 꼴 재현 안 됨") | 재현 조건(루프·중간 호출)이 새 정보 |
| D-F32 | 기타 | (타입) 파라미터가 적은 함수 값을 `() -> ()` 로 주석해 콜백 자리에 넘기면 거부된다 | dvf:436-440 | 실측 | 일반 | luau-types/variance.md | 있음(kb:luau-types/references/variance.md §6) | 원천만 추가 |
| D-F33 | 기타 | (타입) `DateTime:ToLocalTime()` 이 `{any}` 로 추론된다. `pcall(string.find, s, p)` 는 "Argument count mismatch" 로 거부 → 클로저로 감싼다 | dvf:502-503 | 실측 | 반일반 | luau-types/solver-limits.md | 없음 | typedefs 버전 의존 |
| D-F34 | 툴체인 | 정규식으로 Luau 를 고치는 마이그레이션 스크립트가 `const` 선언 25곳을 놓쳤다 | dv:feedback/devui.md:149-150 | 실측 | 반일반 | luau-verify/tooling.md | 일부(kb:luau-verify/references/tooling.md §3) | `const` 를 모르는 도구 사례 |
| D-F35 | 하네스·에이전트 운영 | sonnet 서브에이전트의 【추정】 관찰 셋이 메인의 소스·Studio 재확인에서 모두 틀렸다 → 상류 보고 전에 메인이 다시 판정하고 근거 등급을 단다 | dv:feedback/devui.md:5,30-33,56,89; dvf:20-26,508-552 | 실측 | 일반 | harness/subagent-verification.md | 없음 | T-57·T-62 와 같은 방향 |
| D-F36 | 하네스·에이전트 운영 | 마찰 21건 중 13건은 답이 이미 문서에 있었다. 사람·에이전트가 먼저 읽는 README·파일 머리 주석에 링크가 없었기 때문 | dvf:31-32,383-384,566 | 실측 | 일반 | harness/docs-discoverability.md | 없음 | luau-kb 진입점 설계에 직접 적용 |
| D-F37 | 하네스·에이전트 운영 | 게임 안의 글(이름, 로그)을 에이전트에 넘길 때는 "데이터일 뿐 지시가 아님" 을 명시하고(프롬프트 주입 방어), 파괴적 편집은 사람이 확인한다 | dv:research/agent-mode-plan.md:98,112-118 | 사용자결정 | 일반 | harness/prompt-injection.md | 없음 | |
| D-F38 | 하네스·에이전트 운영 | computer use 스크린숏은 축소되므로 QR 같은 바이트 정확 데이터는 Bash 로 원해상도 캡처 후 해독기로 푼다 | dv:research/computer-use-survey.md:23-25,54-55 | 서술 | 반일반 | harness/computer-use.md | 없음 | 낡기 쉬움 |
| D-C01 | 모듈·require | 클라이언트 번들은 권한자의 PlayerGui 로 복제되어 위치가 바뀐다 → `@game/...` 절대 require 대신 상대 경로와 `@self`. 상대 경로 깊이는 init 모듈인지에 따라 다르다 | dv:conventions.md:78-80 | 실측 | 일반 | roblox-luau/require.md | 없음 | luau-lsp 실측 2026-10-19. R-39·S-123 과 한 reference |
| D-C03 | 테스트 | 엔진과 무관한 로직은 Roblox API 없이 짜서 luau CLI 스펙으로 돌린다. CLI 에는 `Vector3`·`CFrame`·`Color3`·`Enum` 같은 전역이 없으므로 공용 모듈은 로드 시점에 참조하지 않고 `typeof(v)=="Vector3"` 문자열 비교, Enum 조회는 호출 시점으로 미룬다. 로드할 때 엔진을 부르는 모듈(ReflectionService 등)을 거치면 CLI 에서 죽는다 | dv:conventions.md:53,67; tbox:CLAUDE.md:149-154; tbox:docs/hydration-design.md:131-132 | 사용자결정 | 일반 | luau-testing/cli-vs-roblox.md | 없음 | X-12 병합. R-47 과 같은 reference |
| D-C04 | 스타일·관용 | 다시 대입되는 모듈 상태를 지역 별칭으로 들면 그 순간의 값에 묶인다 → `State.x` 로 읽고 쓴다(표는 참조라 별칭으로 들어도 됨) | dv:conventions.md:71 | 서술 | 일반 | luau-style/modules-require.md | 없음 | |
| D-C05 | 하네스·에이전트 운영 | 서버·보안 코드는 메인이 쓰고 다른 모델이 읽기 전용으로 리뷰한다. 리뷰 모델의 기본은 토큰 비용 때문에 sonnet, opus 는 사용자가 말할 때만. 백그라운드 작업 완료는 하네스 알림으로 판단 | dv:conventions.md:100-107 | 사용자결정 | 일반 | harness/review-protocol.md | 없음 | O-02(sonnet→opus 두 단계)와 보완 |
| D-C06 | 하네스·에이전트 운영 | 봇 계정은 에이전트 전용 origin 에만 자유롭게 푸시하고, upstream 푸시 금지는 settings.json 이 아니라 서버 pre-receive 훅이 강제한다(실제 거절 확인) | dv:conventions.md:112-113 | 실측 | 일반 | harness/git-permissions.md | 없음 | T-64 와 비교 |
| X-02 | 모듈·require | `init.luau` 안의 `require("./src/...")` 는 바깥 폴더 이름이 `src` 일 때만 동작한다. pesde·Wally 로 이름이 바뀌면 CLI·Studio 0.740·lute·mlua 모두 `could not resolve child component "src"` 로 깨진다. Studio 에서는 옆에 `src` 라는 다른 모듈이 있으면 에러 없이 **그 모듈을 로드**한다 → `@self/...` 로 | mrow-rv:1159-1180,1488-1502; mw:base/architecture.md:92-97 | 실측 | 일반 | luau-style/modules-require.md | 없음 | 패키지 배포의 조용한 오작동 |
| X-04 | 모듈·require | 테스트 엔트리를 `init.luau` 로 지으면 "could not reset to requiring context (ambiguous)" 류 오류가 난다. 원인 설명은 갈린다: tbox 는 `src/init.luau` 와의 이름 겹침, mrow 는 `X.luau` 와 `X/` 가 형제일 때만 모호하고 `tests/init.luau` 의 진짜 함정은 그 안의 `./` 가 저장소 루트라는 점. require 된 파일은 값 하나를 return 해야 한다(`module must return a single value`) → 엔트리는 `run.luau` | tbox:CLAUDE.md:141-147; mrow-rv:1183-1187; mw:conventions.md:71; stl:base/architecture.md:78-83; stl:conventions.md:156 | 실측 | 일반 | luau-style/modules-require.md | 없음 | S-120·R-46 병합. 원인 모순(모순 6) → 최소 재현 먼저 |
| X-07 | 툴체인 | pesde 패키지 이름의 `<name>` 부분은 소문자·숫자·`_` 만(하이픈 불가). pesde 로 설치한 패키지 폴더 이름은 소문자 → 이름으로 루트를 찾지 말고 `script.Parent` 를 보관해 쓴다 | tbox:CLAUDE.md:34-37; dvr:2026-11-04-server-split.md:8; stl:base/architecture.md:24-34 | 실측 | 반일반 | roblox-luau/packaging.md | 없음 | D-R55 병합 |
| X-08 | 툴체인 | mise 로 고정한 pesde 에 `pesde self-upgrade` 를 쓰면 `~/.pesde/bin/pesde` 가 새로 생겨 고정 버전을 가린다 | tbox:CLAUDE.md:45-48 | 서술 | 일반 | luau-verify/toolchain.md | 일부(kb:luau-verify/references/toolchain.md §1 shim 함정) | |
| X-09 | 툴체인 | `pesde run` 은 스크립트를 Lune 으로 돌리고 엔진을 `~/.pesde/bin` 에서 PATH 로 찾는다. 그 경로가 PATH 에 없으면 `failed to replace process` 로 패닉(20MB 코어 덤프) → mise task 로 luau·lute 를 직접 부른다 | tbox:CLAUDE.md:134-137; mrow-rv:1228; tbox-cr:279 | 실측 | 일반 | luau-verify/tooling.md | 일부(kb:luau-verify/references/tooling.md §2) | |
| X-10 | 툴체인 | `pesde install` 의 `roblox_sync_config_generator` 경고는 무해하다. pesde 0.7.3 이하는 `const` 때문에 "failed to parse file to extract types" 를 내지만 설치는 정상(0.7.4 에서 수정) | tbox:CLAUDE.md:56-62 | 서술 | 일반 | luau-verify/toolchain.md | 일부(kb:luau-verify/references/tooling.md §3:61) | 0.7.4 고정이면 낡음 |
| X-13 | 툴체인 | stylua 는 현재 디렉터리의 설정만 찾는다. 패키지 안에서 돌리면 에러 없이 기본 설정(Lua 문법)으로 포맷해 `f<<T>>` 를 시프트로 바꾼다 → 루트에서 돌리고 diff 확인 | tbox:CLAUDE.md:80-91; mw:conventions.md:57-58 | 실측 | 일반 | luau-verify/tooling.md | 있음(kb:luau-verify/references/tooling.md §4) | tbox:84-91 "syntax=Luau 에서도 망가진다" 는 luau-kb 가 반박(모순 5). 원천 추가만 |
| X-14 | 에러 | NaN 과의 비교는 모두 거짓이라 `v < min`·`v > max` 경계 검사를 NaN 이 통과한다 → `not (v >= min and v <= max)`. CFrame 회전 성분·Color3 clamp 검사도 같은 함정. `min=0` 은 `math.huge` 를 통과시키므로 inf 는 따로 막는다 | tbox-cr:54-58,111-115,164-168,304,385,398-399 | 실측 | 일반 | luau-style/numbers.md | 없음 | luau 0.734 재현. S-115 와 같은 reference |
| X-15 | 스타일·관용 | 숫자 키 표는 배열이 아니어도 `#` 기반 검사를 통과한다(`{[0]=…}`, `{[1.5]=…}`, `{"a",nil,"c"}`, `t[1],t[2],t[4]` 만 있는 표의 `#t` 가 4). 배열 판정은 키가 1..n 연속 양의 정수인지 직접 센다 | tbox-cr:70-75,297-298 | 실측 | 일반 | luau-style/tables.md | 없음 | S-112 와 같은 reference |
| X-17 | Roblox API | Vector2·Vector3·CFrame·NumberRange 성분과 네이티브 `vector` 성분은 float32 다. 64비트 경계와 비교하면 틀린다(`NumberRange.new(0,0.1)` 이 `maxSpan=0.1` 실패) → 경계도 float32 로 반올림해 비교 | tbox-cr:153-162,356 | 실측 | 일반 | roblox-luau/datatypes.md | 없음 | 네이티브 vector 는 CLI 에서도 재현 가능 |
| X-19 | 에러 | 사용자가 준 Lua 패턴이 잘못되면 매칭 시점에 예외가 난다 → 생성 시점에 `pcall(string.match, "", p)` 로 확인 | tbox-cr:175-179 | 서술 | 일반 | luau-style/strings.md | 없음 | D-R28(역추적 비용)과 짝 |
| X-20 | Roblox API | `CFrame:FuzzyEq` 는 회전을 각도 근사로 비교한다(문서) → trace 를 보존하는 왜곡(대각 2, 0.5, 0.5)이 정규직교 검사를 통과할 수 있다 | tbox-cr:187-194 | 서술 | 반일반 | roblox-luau/datatypes.md | 없음 | Studio 확인 필요 표시 그대로 |
| X-22 | perf | 실패 메시지는 미리 만들지 않는다. 클로저·테이블로 두고 요청할 때 문자열을 만든다(Union 은 실패가 정상 흐름). tbox 실패 1회당 약 3.5µs, mrow 는 실패 5,642회를 즉시 만드는 데 약 1.1ms | tbox:docs/api-normalization.md:20; tbox:docs/error-path-design.md:24; tbox-cr:342; mw:audit/mrow-spike/README.md:104-105 | 실측 | 일반 | luau-perf/calls-and-closures.md | 없음 | luau 0.734 |
| X-23 | Roblox API | Roblox userdata 에 없는 멤버를 인덱싱하면 예외가 난다 → 임의 값을 덕 타이핑(`v.tag`)하지 말고 `typeof` 를 먼저 보거나 약한 키 집합으로 소속을 판정 | tbox:docs/redesign-precedents.md:23 | 서술 | 일반 | roblox-luau/datatypes.md | 없음 | quad Brand 설계의 근거 |
| M-01 | 툴체인 | lute 1.0.0 과 mlua 0.12.1(Luau 0.736)은 `const`·`f<<T>>`·문자열 require 를 CLI 와 똑같이 처리한다(lute 는 에러 메시지까지 바이트 단위로 같다). lute 에는 전역 `loadstring` 이 없어 소스 컴파일은 `@lute/luau`. mlua 는 `create_require_function(FsRequirer::new())` 로 require 등록 | mw:base/architecture.md:92-108; mrow-rv:1488-1502; tbox:CLAUDE.md:138-140 | 실측 | 일반 | luau-verify/tooling.md | 일부(kb:luau-verify/references/tooling.md:47 "lute 미확인") | X-11 병합. luau-kb 의 "미확인" 을 채운다 |
| M-02 | 툴체인 | `const` 와 `f<<T>>` 는 Luau 0.711 이상에서만 파싱된다(0.709·0.710 은 구문 에러). lune 0.10.5 는 Luau 0.709 를 번들한다(웹 조사) → lune 이 `const` 를 못 읽는 이유 | mrow-rv:1375; mw:session/2026-09-29-01-setup.md:45 | 실측 | 일반 | luau-verify/toolchain.md | 일부(kb:luau-verify/references/tooling.md:44 lune 실패만) | lune 번들 버전은 미실측 |
| M-03 | runtime·엔진 | 중첩 Lua 호출 프레임 한도는 `LUAI_MAXCALLS = 20000`. 평범한 재귀는 19,997 에서, 단계당 3프레임 문법은 6,662 단계에서 `stack overflow`. Studio 0.740·lute 도 같고 mlua 6,663. `-O2`·`--codegen` 과 무관하고 `pcall` 로 잡힌다 → 믿을 수 없는 입력의 재귀 파서는 pcall 이나 깊이 상한 | mrow-rv:390-401,1533; mw:base/architecture.md:100 | 실측 | 일반 | luau-style/runtime-limits.md | 없음 | 초안의 "약 10,000" 은 반박됨. C 호출 한도(S-133, ≈200)와 구분 |
| M-04 | perf | `s ..= c` 로 문자열을 누적하면 O(n²): 10만자 0.80s, 20만자 3.07s, 40만자 12.76s. 표에 모아 `table.concat` 한 번이면 선형(0.035→0.150s). 인터닝도 완화하지 못한다 | mrow-rv:407-423 | 실측 | 일반 | luau-perf/strings.md | 없음 | luau 0.734. 기계가 만든 긴 입력에서 DoS |
| M-05 | perf | 정수 10만 개 CSV 기준 `string.gmatch` + `tonumber` 는 약 125ns/항목, Luau 로 글자마다 도는 파서는 약 40배 느리다. 드문 대상을 훑을 때는 C 로 건너뛰는 `string.find` 스캐너가 낫다 | mrow-rv:809-813; mw:audit/mrow-spike/README.md:189-193; mw:base/migration-plan.md:115 | 실측 | 일반 | luau-perf/strings.md | 없음 | S-P47(C 로 내려가는 쪽이 이긴다)과 같은 원리 [정정: 할당 없는 `string.byte` 손 파서는 `gmatch`+`tonumber` 의 0.69~0.74배(인터프리터)·0.25배(native)로 오히려 빠르다. "약 40배"는 mrow 파서 컴비네이터 라이브러리의 값이었고 요약이 일반화를 잘못했다 — `luau-kb/skills/luau-perf/references/strings.md` §5] |
| M-06 | perf | 할당 위주 코드(테이블 만들기·클로저 호출)는 `-O2 --codegen` 으로 10% 안팎만 빨라진다(파서 1.40→1.06ms, 7.93→6.93ms) | mw:audit/mrow-spike/README.md:76,93,197-198; mrow-rv:861 | 실측 | 일반 | luau-perf/optimizer-and-native.md | 없음 | best-of-5. native 실측 희소 → 귀중 |
| M-08 | perf | 결과 테이블(`{failed, value}`) 대신 `(ok, T...)` 다중 반환으로 바꾸면 70~73% 빨라진다. 대가로 좁히기 안전성을 잃어 `ok` 를 확인하지 않고 값을 써도 진단 0건. 글자마다 결과 테이블을 2~3번 만들던 이중 peek 제거로 37~41% | mrow-rv:815-853 | 실측 | 반일반 | luau-perf/algorithms-and-structures.md | 없음 | 수치는 mrow 기준, 원리는 일반(할당 회피) |
| M-09 | 기타 | (타입) 반환 팩 유니온 `(boolean, T...) \| (false, E)` 는 구문 에러("Expected '->' when parsing function type, got '\|'"). 표현 가능한 형태는 `-> (boolean, T...)` 뿐 | mrow-rv:840-845 | 실측 | 일반 | luau-types/generics.md | 확인 필요(kb:luau-types/references/generics.md §8 타입팩) | |
| M-11 | 스타일·관용 | Lua 패턴의 `+`·`*` 는 되돌아간다(backtrack): `@(%a+) +([^\n]+\n)` 에서 공백 뒤가 비면 공백 하나를 내용으로 돌려받는다. PEG 식 탐욕 `many` 는 되돌아가지 않으므로 옮길 때 대안을 풀어 쓴다 | mw:conventions.md:124-125; mw:audit/mrow-spike/README.md:119,159 | 실측 | 일반 | luau-style/strings.md | 없음 | |
| M-14 | 스타일·관용 | `table.insert(t, f())` 에서 f 가 값 0개를 돌려주면 에러, 2개를 돌려주면 `insert(t, pos, v)` 오버로드가 되어 조용히 오염된다 → `(f())` 로 감싸 한 값으로 자른다. 타입 검사는 잡지 않는다 | mrow-rv:275,291-300; mw:conventions.md:122-123 | 실측 | 일반 | luau-style/tables.md | 없음 | D-R32 와 짝 |
| M-15 | 테스트 | lune(mlua)의 JSON 인코더는 배열부가 있는 표를 배열로만 내보내고 문자열 키를 버린다(골든 파일 손실 원인) | mw:known-issues.md:252-259; mw:base/architecture.md:133-138 | 실측 | 반일반 | luau-testing/golden.md | 없음 | lune 전용. Roblox JSONEncode 는 미실측(D-R43) |
| M-16 | 테스트 | luau 0.734 에서 `pairs` 순회에 기댄 출력은 같은 입력이면 프로세스 안팎 모두 바이트 단위로 같았다 | mw:known-issues.md:263-265 | 실측 | 반일반 | luau-testing/golden.md | 없음 | 삽입 순서가 같을 때의 관찰. 약속된 동작 아님(R-29) |
| M-18 | 테스트 | 재작성 검증 3단: 레거시와의 차등 비교, 고정 시드 퍼즈, 비교기 변이 자가검사(픽스처 103/103, 퍼즈 3000건 중 917건이 레거시 크래시, 변이 10/10 사살) | mw:audit/mrow-spike/README.md:18-20,72-90,201-203 | 실측 | 일반 | luau-testing/differential.md | 일부(kb:luau-verify/references/negative-controls.md §5 변이 검사) | 차등·퍼즈가 새 정보 |
| M-19 | 기타 | (타입) 자기 참조 함수 필드를 가진 테이블 타입 A 를 다른 자기 참조 타입 B 의 옵셔널(`B?`)에 대입하면 진단 0건(`B` 에 대입하면 잡힘) | mw:audit/mrow-spike/README.md:127-147; mrow-rv:774 | 실측 | 일반 | luau-types/unions-singletons.md | 일부(kb:luau-types/references/unions-singletons.md §4) | luau-analyze 0.734. 제네릭 없는 최소 재현이 새 정보 |
| M-20 | 하네스·에이전트 운영 | `.claude/` 와 CLAUDE.md 를 커밋한다(사람도 읽는 설계 기록이자 다른 사람의 에이전트가 저장소를 망치지 않게 하는 장치). 해소된 question.md 항목은 base/ 로 옮기고 본문을 지운다 | mw:conventions.md:26-33,41-45 | 사용자결정 | 일반 | harness/repo-docs.md | 없음 | stl question.md 381줄 반례 |
| O-01 | 하네스·에이전트 운영 | 다중 에이전트 리뷰의 확정 발견이 69→47→35 로 줄어도 수렴이 아니었다 → 에이전트를 절반으로 줄이고 넓은 훑기 대신 좁은 패스 여러 번, 수정은 작게 묶고 그 diff 를 다시 리뷰, 빈 결과가 나올 때까지 반복 | vs:docs/REVIEW-NEXT.md:8-15,200-201 | 사용자결정 | 일반 | harness/review-protocol.md | 없음 | R-52 와 같은 reference |
| O-02 | 하네스·에이전트 운영 | 두 단계 리뷰: sonnet 이 diff 에서 쉬운 것을 걷어 내고, 그다음 opus 가 구조의 이음매를 본다. opus 는 어느 영역 패스도 소유하지 않은 이음매에서 재현된 결함 3건을 찾았다 | vs:docs/REVIEW-NEXT.md:203-210,249-253 | 실측 | 일반 | harness/review-protocol.md | 없음 | D-C05 와 보완 |
| O-03 | 하네스·에이전트 운영 | "읽기 전용" 이라고 지시한 finder 도 저장소에 파일을 남겼다(`client/n5.test.ts`) → 패스마다 `git status` 로 확인 | vs:docs/REVIEW-NEXT.md:17-18 | 실측 | 일반 | harness/review-protocol.md | 없음 | |
| O-04 | 하네스·에이전트 운영 | 조사 서브에이전트 정의: 고정 스키마(비교 가능성), 모든 사실에 `file:line`, 없는 것은 `ABSENT`, 최종 응답은 40줄 이하 요약이고 문서는 파일로, model sonnet, 도구 제한 | vs:.claude/agents/ref-researcher.md:1-29 | 사용자결정 | 일반 | harness/subagent-definitions.md | 없음 | luau-kb `luau-distill` 류 에이전트의 본보기 |
| O-05 | 테스트 | 한 시드의 정확값 단언은 동전 던지기다("정확히 0" 단언 둘이 운 좋게 통과 — 성질은 시드의 약 2/3 에서만 성립) → 비교를 단언하고, 여러 시드로 평균, 대조군 | vs:CLAUDE.md:103-105 | 실측 | 반일반 | luau-testing/determinism.md | 없음 | 언어 무관 원칙 |

---

## 3. 주제별 개수

병합 후 **308행**이다. 병합 전 원 후보는 약 370개였다(§5).

| 주제 | 개수 | 메모 |
|---|---:|---|
| Roblox API | 110 | 대부분 Studio 실측이다. 출처는 table-sim(물리·드래그·GUI·DataStore), devplorer(원격 신뢰 경계·UI), rbvm(Signal·Instance API) |
| perf | 51 | stl perf 문서(S-P)가 대부분이다. 문자열(M-04·M-05·D-R28)과 Roblox 비용(D-R03·T-54)이 보탠다 |
| 기타 | 26 | 그중 19개는 (타입) 행이다(type function 제외 luau-types 보강분). 나머지 7개는 R-12·R-24~R-29 언어 함정 |
| 하네스·에이전트 운영 | 22 | 리뷰 프로토콜, 외부 모델 검증, 서브에이전트 정의 |
| 툴체인 | 18 | require·symlink, pesde, lute/mlua, luau-analyze 플래그 |
| GC·수명 | 16 | ephemeron 아님(R-22), Destroy 의미론(R-14~R-21), 약한 표 비용 |
| 스타일·관용 | 13 | 문자열·패턴, table.insert 함정, fail-closed |
| 모듈·require | 11 | CLI/Studio require 규칙, 캐시 |
| 동시성 | 11 | task·coroutine, Signal 구현, TOCTOU |
| runtime·엔진 | 11 | 메타메소드, NaN 키, 호출 한도 |
| 테스트 | 10 | 에러 줄 단언, CLI vs Roblox 분리, 차등·퍼즈 |
| 에러 | 9 | -O2 와 error level, pcall 함정 |

**보조 분포**
- 검증: 실측 238 / 서술 55 / 사용자결정 15.
- 판정: 일반 254 / 반일반 54. 고유만 해당하는 행은 넣지 않았다.
- 대상 스킬: roblox-luau 140 / luau-perf 58 / luau-style 45 / harness 22 / luau-types 19 / luau-verify 13 / luau-testing 11.
- luau-kb 중복: 없음 278 / 일부 26 / 있음 2 / **모순 1(S-129)** / 확인 필요 1(M-09).

**저장소별(병합 후 행 수)**: stl 85(S-P 51 + S 34), rbvm 49, table-sim 61, devplorer 79, tbox 14, moonwave·mrow 15, 그 밖 5.
- vitrine 은 Go 앱이라 해당 없음이다.
- LaftelDiscordRpc 는 빈 디렉터리다.
- VideoSync 는 하네스 지식만 있다(O-01~O-05).

## 4. stl `<!-- luau-kb 후보 -->` 표시 23곳 처리

| 표시 위치(`stl:conventions.md:`) | 처리 |
|---|---|
| 40 | S-136 |
| 42 | S-P24(옛 S-101) |
| 70 | 제외: 최소 재현 없음. 타입 함수 `View` 의 산물이다 |
| 72 | 제외: type function |
| 75 | S-138 |
| 77 | S-111 |
| 83 | 제외: luau-kb 중복(generics §3) |
| 84 | 제외: luau-kb 중복(generics §4, solver-limits S2) |
| 85 | 제외: luau-kb 중복(generics §5) |
| 86 | 제외: type function |
| 91 | 제외: luau-kb 중복(tooling §3) |
| 94 | S-130 |
| 95 | S-131 |
| 100 | S-112, S-113 |
| 109 | S-114. NaN 부분은 S-115 의 근거로만 쓰고, 정책 자체는 고유 |
| 114 | S-137. 묶기 설계는 고유 |
| 128 | S-P18(옛 S-102) |
| 129 | S-P19·S-P20(옛 S-103). 지역 상수 부분은 S-P24 |
| 136 | S-116 |
| 140 | S-117, S-118 |
| 147 | S-P45(옛 S-122) |
| 148 | S-P03·S-P09(옛 S-109) |
| 149 | S-P04(옛 S-105). 트레이트 진입점 비용은 고유 |

`stl:conventions.md:7`, `stl:rules/docs.md:16`, `stl:skills/doc-audit/SKILL.md:40` 은 표시를 설명하는 문장이라 23곳에 넣지 않았다.

## 5. 병합표 (사라진 ID → 남은 ID)

같은 사실이 여러 저장소에 있으면 원천을 한 행으로 모았다.

| 사라진 ID | 남은 ID | | 사라진 ID | 남은 ID |
|---|---|---|---|---|
| S-101 | S-P24 | | D-R04 | T-44 |
| S-102, D-R34 | S-P18 | | D-R05 | S-115 |
| S-103 | S-P19, S-P20 | | D-R14, D-R25, D-R51 | R-38 |
| S-104, X-21 | S-P01, S-P02, S-P05 | | D-R17 | R-16, R-21 |
| S-105 | S-P04 | | D-R33 | S-113 |
| S-106 | S-P44 | | D-R36 | S-135 |
| S-107 | S-P07 | | D-R41 | D-F10 |
| S-108 | S-P10 | | D-R44, D-F28 | T-41 |
| S-109 | S-P03, S-P08, S-P09 | | D-R55 | X-07 |
| S-110 | S-P36 | | D-R57, X-25 | T-57 |
| S-120, R-46 | X-04 | | D-F02 | T-32 |
| S-122, M-07 | S-P45 | | D-F16 | T-38 |
| R-41, D-C02, D-F20 | T-55 | | D-F17 | D-R07 |
| R-43 | D-R01 | | D-F19 | D-R47 |
| R-44 | S-116 | | D-F21 | D-R49 |
| T-48 | D-R28 | | D-F22 | T-25 |
| T-49, D-F26 | D-R20 | | X-01 | S-123 |
| T-58, X-24 | R-52 | | X-03 | S-126 |
| X-05 | S-124 | | X-06 | D-F27 |
| X-11 | M-01 | | X-12 | D-C03 |
| X-16 | D-R37 | | X-18, M-10 | D-R29 |
| M-12 | D-R27 | | M-13 | D-R38 |
| M-17 | S-127 | | | |

## 6. 저장소 간(·luau-kb 와) 모순되는 후보

| # | 내용 | 한쪽 | 다른 쪽 | 판정·권고 |
|---|---|---|---|---|
| 1 | `luau-analyze` 플래그 옵션 | kb:luau-types/references/recursion-and-limits.md:75 "플래그 옵션이 없다" | S-129: `--fflags=` 로 불리언 플래그를 바꿀 수 있다(stl:research/class-like/README.md:57) | ★2 로 **luau-kb 가 틀렸음**을 확인했다(0.742 `Analyze.cpp:434`). 정수 한도는 못 바꾼다는 단서를 붙여 정정한다 |
| 2 | 라이브 Roblox 최적화 수준 | stl: "라이브 -O2, Studio -O1" 을 사실로 적음(stl:papers/05-quad-survey.md:110, stl:conventions.md:136) | **quad**: "실측 필요(미실측)"(quad:archive/post-implementation-review/round14-reflection-plan.md:25) | S-116·S-P45 를 옮길 때 이 부분만 "서술" 로 표시한다. Studio 에서 `debug.info` 인라인 관찰로 실측할 과제 [정정: 판정됨. Roblox 문서 `luau/comments.md` 가 `--!optimize` 기본값을 Studio 테스트 1·라이브 게임 2 로 적는다. stl 쪽이 맞다(엔진 안 실측은 없음) — `luau-kb/skills/roblox-luau/references/perf.md` §6] |
| 3 | 메타테이블 세금의 범위 | perf §1 "MT 가 붙으면 인덱싱 1.59배"(perf:13-26) | perf §60 "칸·필드 읽기는 MT 무관"(perf:1698), stl:conventions.md:39 "사라짐" | 모순이 아니라 범위 차이다. 겉표의 정수 키에만 해당한다(★1 소스와 일치). S-P01·S-P02 를 한 쌍으로 옮긴다 |
| 4 | 약한 키 레지스트리 비용 | **quad**: "포인터 해싱 한 번, 무시할 만"(quad:base/brand-plan.md:147-150,284) | stl: 생성 1.66~1.9배, 풀 GC 2~3.7배(perf:504-525) | quad 는 조회만 보면 맞다. 등록·GC 비용은 stl 실측이 반례다. S-P36 에 둘 다 적는다 |
| 5 | stylua 와 `f<<T>>` | tbox:CLAUDE.md:84-91 "syntax=Luau 에서도 망가진다" | luau-kb tooling.md §4(설정이 없을 때만 재현), tbox:CLAUDE.md:80-82, mw:conventions.md:57-58 | tbox 84-91 이 낡았다. X-13 은 luau-kb 에 원천만 보탠다 |
| 6 | 테스트 엔트리 `init.luau` 의 "ambiguous" 원인 | tbox:CLAUDE.md:141-147(src/init.luau 와 이름 겹침) | mrow-rv:1183-1187(`X.luau`·`X/` 형제일 때만. 진짜 함정은 `./` 가 저장소 루트) | 옮기기 전에 최소 재현 2개를 만들어 판정한다(X-04) |
| 7 | `Active` Frame 이 클릭을 막는가 | **quad**: Active 로 스크림 관통을 고쳤다(quad:feedback/consumer-kits-studio-qa-2026-10-07.md:285) | devplorer: Catcher TextButton 으로 가는 클릭은 못 막는다(D-F01). table-sim: 투명 GUI 도 클릭을 가져간다(T-33) | 대상이 다르다(월드 클릭인지 GUI 버튼인지). 셋을 한 표로 재측한다 |
| 8 | DataStore 예산 | devplorer: 분당 60 + 플레이어×10(dvr:2026-10-19-server-security.md:183-201) | table-sim: Read 300 + CCU×40, 2026-07-29 부터 Open Cloud 와 공유(ts:<비공개>) | devplorer 수치가 **옛 예산**이다. T-41 로 병합하고 날짜를 표기한다 |
| 9 | Destroying 핸들러 순서 | **quad**: "비결정적"·"실기기 확인 필요"(quad:archive/surveys/2026-08-06-pre-implementation-audit.md:218) | rbvm: Deferred 에서 **연결 역순** 실측(R-03) | 한 번의 관측이지 계약이 아니다. "의존 금지" 를 유지하고 관측값만 적는다 |
| 10 | Destroying 시점의 계층 | **quad** mock: 동기 발화, 부모·자식이 살아 있다(quad:audit/round13-e29-mock-fidelity/README.md:61. quad 도 "상이" 로 표기) | rbvm: 핸들러 안에서 `Parent` 는 이미 nil(R-15). rbvm-cr:590 원래 서술도 정정됨 | 엔진 쪽(R-15)이 정본이다 |
| 11 | 대기 중 배달의 취소 | **quad**: "Disconnect 하면 대기 중 배달이 취소된다"(같은 파일 :58) | rbvm-sib:197: "Destroy 가 연결을 끊어도 큐에 든 Destroying 1회는 돈다" | Destroying 만 예외일 수 있다. Studio 재측 과제(R-14 비고) |
| 12 | Signal userdata 동일성 | rbvm:design/gc-and-lifecycle.md:87-92 "쥐고 있으면 같은 userdata" | rbvm-eb:22 "쥔 채로도 rawequal false" | 같은 저장소 안의 모순이다. 실측(R-01)이 이긴다 |
| 13 | weak 표의 Instance 수거 | devplorer: "실측 필요" 로 두고 회피(dvr:2026-10-19-server-security.md:92,389-390) | quad(quad:audit/README.md:21)·rbvm(R-18): Destroy 된 것은 수거됨을 실측 | devplorer 가 낡았다 |
| 14 | `JSONEncode` 의 혼합 표 처리 | dvr:2026-10-19-shared-specs.md:47 | dvr:2026-10-19-server-round6.md:248, dvr:2026-10-19-server-security.md:211-212 | 같은 저장소 안에서 서술이 셋으로 갈리고 모두 미실측이다. D-R43 은 실측 과제로 옮긴다 |
| 15 | `.luaurc` alias 런타임 | stl: CLI 런타임에서 일반 alias 가 동작하지 않는다(S-125, 2026-08) | Studio: 모르는 alias 는 에러, 알려진 alias 는 동작(R-40) | 환경이 다르다. CLI 쪽은 0.742 로 재측한다 |
| 16 | SignalBehavior Deferred | devplorer: "미실측"(dvr:2026-10-20-client-palette-copy.md:50) | **quad** H-291 실측(quad:session-summary.md:2190), rbvm(R-14) | 결론은 같은 방향이다. devplorer 서술만 낡았다 |
| 17 | MemoryStore 를 미게시 Studio 에서 쓸 수 있나 | ts:conventions.md:153 "실측 불가" 단정 | ts:<비공개> "Studio 동작, 미게시는 문서에 없음" | 같은 저장소 안의 모순이다. 실측 전까지 T-43 에 넣지 않는다 |
| 18 | `select` 루프 vs `table.pack` | perf:129 "1.6~2.3배 빠름"(방향 없음), stl:conventions.md:148 "select 쪽" | perf:1589 `{...}` 는 32인자까지 pack 보다 빠르고 1024에선 느림 | 인자 수 조건을 넣어 재측한다(S-P09) |
| 19 | 메서드 호출 웃돈 | perf:329-330 18%(0.734) | perf:1698 12%(+3ns), perf:1613 MT 메소드 55~72ns | 함수·버전·작업량이 다르다. 0.742 기준 한 표로 재측한다 |
| 20 | 가변인자 비용 | perf:1491 1.5~2ns/호출 | perf:1508 "원인 아님 ±2ns" | 잡음 경계라 단정할 수 없다 |
| 21 | 교집합이 never 로 붕괴하는가 | stl:papers/03-tuple.md:143-146 "`number & string` 을 never 로 붕괴시키지 않는다"(tbox 인용, 서술) | kb:luau-types/references/unions-singletons.md §7, generics.md §7 | 후보에서 뺐다. luau-types 담당에 확인 과제로 넘긴다 |

**quad 와 결론이 다른 것만 추리면** 2·4·7·9·10·11 이다. 이 가운데 quad 가 낡은 쪽은 10(mock 가정)이고, quad 가 미결인 쪽은 2·9 다. 나머지 셋은 조건 차이다.

## 7. 낡은 후보 (이전 전 재측·정정 필요)

| 묶음 | 해당 ID | 이유 |
|---|---|---|
| 0.734 `-O1` 단일 조건 수치 | S-P01, S-P03~S-P06, S-P10(5절), S-P14~S-P16, S-P30 | perf 1~14절은 0.734 인터프리터 기준이다. 배포 조건(0.742, `-O2`, native)에서 재측이 필요하다. 특히 S-P01 은 codegen 에서 세금이 더 크다(18절) |
| 방향·조건이 모호한 수치 | S-P09(7절), S-P08(53 vs 54절), S-P04(18% vs 12%) | §6 의 18~20 |
| 문서 안에서 이미 정정된 서술 | perf 11·12절(Max 1.83x 전제), 13절 AndThen 0.774µs, 49절 3ms, 36·37절 "TreeMap(정렬 배열)" 옛 이름 | 정본은 17·13-2·59·38-3 절이다. 표에는 정정본만 옮겼다 |
| 날짜·정책 의존(Roblox) | T-29(2026-05-05 프라이버시), T-41·T-43·T-44(2026-10 한도), T-46(2018 근거 20초), T-56(haiku 보고서), D-F22·T-25(EditableImage 설정), D-F38(computer use) | 옮길 때 "확인일" 필드를 붙이고 정기 재확인 대상으로 둔다 |
| 엔진 버전·모드 의존 | Studio 실측 전부(R-01~R-40 등): Studio 0.742, **Deferred 하나만** 쟀다 | Immediate 모드는 아무도 재지 않았다. R-03·R-04·R-14·R-15·D-R40 은 모드에 따라 달라질 수 있다. R-31(FindFirstDescendant 비활성)은 엔진 업데이트로 바뀔 수 있다 |
| 툴 버전 의존 | R-49(luau-lsp 1.69.0 파싱 에러), D-F30·D-F31·D-F33(lsp 1.69.0), X-10(pesde 0.7.3), S-125(2026-08), S-138(0.739 땜질 범위), S-129 의 `LuauReadOnlyIndexers` 줄, M-02(lune 번들 버전은 웹 조사) | luau-kb 기준(0.742, lsp 1.70.1)으로 재확인한다 |
| 원천 문서 자체가 낡음 | tbox:CLAUDE.md:84-91(stylua 경고), devplorer 의 weak 표·SignalBehavior "미실측" 서술, rbvm:design/gc-and-lifecycle.md:87-92, rbvm-cr:590·591, rbvm-cr:10 "Studio 확인 0건", rbvm:CLAUDE.md:47 "check.sh 통과"(stylua shim 으로 깨짐), stl:archive/question-resolved.md:1710-1714 "`const` 금지" | 후보로 옮기지 않았다. 원 저장소 정리(diet) 대상으로 넘긴다 |
| 미실측인 채 옮길 것 | D-R04→T-44(큐잉), D-R13, D-R43, D-R24 의 `:has()`, D-R49 의 Legacy Script, D-R50, D-R52, X-20, R-42, R-21 | `status: described` 로 옮기고 실측 과제 목록에 올린다 |

## 8. 우선 이전 Top 15

기준은 네 가지다: 재현 쉬움, 여러 저장소가 독립적으로 같은 결론, luau-kb 에 공백, 틀리면 조용히 망가짐.

| 순위 | ID | 이유 | 이전처 |
|---|---|---|---|
| 1 | S-P01 + S-P02 (+S-P05) | 메타테이블 세금의 정확한 범위(겉표 정수 키만, -O1 1.6x → codegen 2.0x)와 회피 패턴. 설계를 가장 크게 좌우하고 ★1 소스 근거까지 있다 | luau-perf/metatables.md |
| 2 | S-P17 + S-P18 + S-P19 + S-P20 | 배열부 성장 규칙의 함정 넷: nil 구멍 9.5배, 앞에서 비우는 큐 1.7~3배, 생성자 밖 대입 3배, 이름 필드 하나면 할당 둘. 다른 곳에 없는 실측이다 | luau-perf/tables.md |
| 3 | S-116 + S-118 | -O2 인라인이 `error(msg, level)` 을 틀리게 만드는데 -O1 테스트로는 영원히 안 보인다. 해법(스택 걷기)과 테스트 규칙(두 모드, 줄 단언)까지 한 세트다 | luau-style/errors.md, luau-testing/error-tests.md |
| 4 | S-123 + X-02 + X-04 + S-124 | require 의미론(`init.luau` = 폴더 자신, `@self`). 네 저장소와 네 런타임의 결론이 같다. 이름 바뀐 패키지가 다른 `src` 를 조용히 로드하고, 잘못된 경로는 analyze 0건이다 | luau-style/modules-require.md, luau-verify/checkers.md |
| 5 | R-39 + R-40 + T-55 | Studio require 규칙(접두 필수, 없으면 즉시 에러, 끝 슬래시 허용, alias 대소문자 무시, 캐시). CLI 표(4번)와 짝지어 한 장으로 만든다 | roblox-luau/require.md |
| 6 | R-22 + R-23 | Luau weak-key 테이블은 ephemeron 이 아니다. 3줄 재현이고 Lua 5.2+ 상식과 반대이며 영구 누수를 낸다 | luau-style/weak-tables.md (+luau-perf/gc-and-memory.md) |
| 7 | R-01 | 시그널 userdata 가 접근마다 새로 생겨 캐시 키로 못 쓴다. 래퍼·캐시를 짜는 모든 프로젝트가 밟는다 | roblox-luau/signals.md |
| 8 | R-14 + R-15 + R-17 | Deferred 에서 Destroying 은 늦게 배달되고, `Connected` 는 동기로 꺼지며, 핸들러 안의 Parent 는 이미 nil 이다. 파괴된 것에 Connect 하면 영원히 산다. rbvm 과 quad 가 각자 실측해 일치했다 | roblox-luau/lifecycle.md |
| 9 | R-12 | `expr :: T` 가 다중 반환을 하나로 자르는데 타입 검사는 통과한다. 2줄 재현이다 | luau-style/pitfalls.md |
| 10 | M-03 + S-133 | 호출 한도 둘: Lua 프레임 20000(네 런타임 공통, pcall 로 잡힘)과 C 재귀 resume 약 200. 믿을 수 없는 입력의 재귀 코드 전부에 걸린다 | luau-style/runtime-limits.md |
| 11 | M-04 + D-R28 + M-05 | 문자열 성능 기준선: `..=` O(n²), 패턴 역추적 O(N^6)(60자에 100초), gmatch 125ns/항목. luau-perf/strings.md 를 바로 세울 수 있다 | luau-perf/strings.md |
| 12 | S-P07 | 일반화 순회 > `next` 삼중항(5배) > Luau 래퍼(9배). 이터레이터 API 설계에 바로 쓰인다 | luau-perf/iteration.md |
| 13 | T-07 + T-08 + T-09 + T-13 | 네트워크 소유권 함정 넷(놓기 어긋남, 같은 값 쓰기 무복제, 자동 배정, 넘기기 직전 속도 소실)과 스트리밍 복제 경계. 외부 모델의 단정을 실측으로 뒤집은 사례다 | roblox-luau/network-ownership.md, replication-streaming.md |
| 14 | D-R01 + D-R02 + D-R06 + X-14 + D-R37 | 원격·바인더블 신뢰 경계: 복사 규칙, 메타테이블 제거, NaN·inf·`__len` 검증. 서버 코드를 쓰는 모든 게임에 해당한다 | roblox-luau/remote-trust.md, remote-validation.md |
| 15 | S-111 + M-14 + D-R32 | 타입이 못 잡는 호출 모양 함정 셋: 가변인자 내장 함수를 콜백으로, `table.insert(t, f())` 다중 반환, `table.insert(t, nil)`. 모두 한 줄 재현이다 | luau-style/pitfalls.md |

**차순위**
- S-139: 표 리터럴의 Subtyping 캐시 오염. luau-types 쪽 최고 가치다.
- S-P26·S-P22: -O2 인라인 범위와 다형 인라인 캐시.
- S-131: stylua 가 `;` 를 지워 파싱 에러를 만드는 함정.
- T-57·R-52·O-01·O-02: 리뷰·외부 모델 프로토콜. harness 스킬의 핵심이다.
- **luau-kb 정정 1건(S-129)** 은 순위와 무관하게 즉시 처리할 것을 권한다.

## 9. 이전 작업에 넘길 메모

- **perf 스크립트**: perf 1~21절은 재현 스크립트가 없다. Top 1·2·12 를 옮길 때 `snippets/perf/*.luau` 를 새로 쓰고, 0.742 로 `-O1`/`-O2`/`--codegen` 세 모드를 재측해 수치를 갱신한다(§1-3 선행 과제).
- **Studio 실측 행**: "[Studio 0.742, Deferred, 날짜]" 꼬리표를 그대로 옮긴다. Immediate 재측은 별도 과제로 둔다.
- **(타입) 행 19개**: luau-types 담당(type function 제외 범위)에게 넘긴다. 대부분 기존 reference 의 절 보강이다. 그중 S-139·S-141·S-142·S-145 는 새 절감이다.
- **luau-kb 에 새로 필요한 스킬**: luau-perf, luau-style, luau-testing, roblox-luau, harness.
  - roblox-luau 는 140행으로 가장 크다. `signals / lifecycle / instance-api / require / remote-trust / remote-validation / network-ownership / replication-streaming / ui-input / ui-layout / topbar-insets / datastore / sandboxing / drag-detector / characters / assets-runtime` 정도로 나눈다. 앞의 일곱 개가 우선이다.
