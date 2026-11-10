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
| S-P01 | perf | 메타테이블이 붙은 테이블 **자신의 정수 키 칸** `t[i]` 읽기·쓰기는 MT 가 있기만 해도 느리다: -O1 1.59~1.60x, -O2 1.66~1.81x, `--codegen -O2` 1.96~2.00x. 빈 MT·`__index`·freeze·`rawget` 모두 같다 | perf:15-26, perf:492-502; stl:papers/08-trait-retrospective.md:30; stl:base/architecture.md:296 | 실측 | 일반 | luau-perf/metatables.md | 없음 | 0.734, 200만 합, 9회×3. ★1 소스 확인: 0.742 `lvmexecute.cpp:779,809,836,864` 의 빠른 경로가 `!h->metatable` 을 요구한다. 0.742 실측 재측은 없음 |
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
| S-P14 | perf | C 해싱이 Lua 비교자로 하는 정렬 병합을 이긴다(10만 Union 5.9배, Has 23.4배, FromList 50배). 정렬 배열에 하나씩 넣기는 O(n²)(2만 개 7.5x) → 일괄 정렬해 짓는다 | perf:162-178, perf:182-188 | 실측 | 반일반 | luau-perf/algorithms-and-structures.md | 없음 | 0.734 -O1 |
| S-P15 | perf | 힙 짓기 O(n) vs Push 반복 O(n log n): 무작위 입력에서는 N 과 무관하게 1.7배로 일정하다(평균 sift-up 깊이가 상수). PushPop 1.78배, top-100 은 힙이 전체 정렬보다 1.66배 빠르다 | perf:194-212 | 실측 | 일반 | luau-perf/algorithms-and-structures.md | 없음 | 0.734 -O1 |
| S-P16 | perf | 뜨거운 루프의 nil 검사 `if v ~= nil` 1.13x. 조밀 숫자 키 Set 의 nil/NaN 검사 1.09~1.10x, 해시 경로에서는 잡음에 묻힌다 | perf:112-119, perf:699-710 | 실측 | 일반 | luau-perf/iteration.md | 없음 | 6절 -O1, 26절 -O2 |
| S-P17 | perf | 배열을 채우며 구멍 자리에 nil 을 바로 대입하면 배열부가 자라지 못해 뒤 원소가 해시로 간다: 구멍 1/2 에서 생성 9.5배, 이후 인덱싱 4.5배(45.7 vs 10.1ms). 자리표시자로 채우고 마지막에 nil 로 바꾼다 | perf:542-557 | 실측 | 일반 | luau-perf/tables.md | 없음 | -O2, 15회 |
| S-P18 | perf | 배열부 크기는 늘어날 때 채워진 비율로 정해진다. 그래서 앞에서 nil 로 비워 가는 배열 큐는 1.7x, 인덱스가 계속 커지는 두 인덱스 큐는 링 버퍼의 3배(26.1 vs 8.65ms), 음수 키 PushFront 는 해시로 가서 2.5배. `table.remove(t,1)` 은 O(n)(용량 10만에 30만 개 넣기 4.7초). 처방: head 번호만 올리기 / 링 버퍼 | perf:1138-1141, perf:644-653; stl:conventions.md:128; stl:base/architecture.md:199; dvr:2026-10-19-shared-specs.md:105; dvr:2026-10-19-client-code.md:116-120 | 실측 | 일반 | luau-perf/tables.md | 없음 | -O2. S-102·D-R34 병합 |
| S-P19 | perf | 번호 칸은 테이블 생성자에 같이 적는다. `{value=v}` 뒤에 `node[1]=…` 를 대입하면 만들기가 3배(21.3 vs 6.8ms) → `{prev, nil, value=v}` 처럼 자리를 잡는다. 생성자 한 번이 `table.create` 후 대입보다 0.69~0.93x | perf:898-906, perf:1585; stl:conventions.md:129 | 실측 | 일반 | luau-perf/tables.md | 없음 | -O2. 57절 0.742 |
| S-P20 | perf | 레코드를 전부 배열 칸으로 쓰면 이름 필드 대비 트리 노드(6칸) 만들기 0.44x, 메모리 224→144B, 접근 0.69x. 이름 필드가 하나라도 있으면 해시부가 따로 할당돼 할당이 둘이 된다(만들기 2.3배, 메모리 1.56배) | perf:1024-1031, perf:898-904; stl:base/architecture.md:207-209 | 실측 | 일반 | luau-perf/tables.md | 없음 | -O2, 20만 노드. S-103 병합 |
| S-P21 | perf | 단건 접근: 상수 문자열 필드 `n.value` 5.1ns ≈ `n[1]` 4.7ns(`impl.X` 3.9 vs `impl[1]` 3.5, 인라인 캐시). 다른 모듈의 접근 함수를 거치면 12.7ns(2.5배) | perf:1042-1057, perf:1096-1105 | 실측 | 일반 | luau-perf/tables.md | 없음 | -O2, 21회 |
| S-P22 | perf | 상수 키 필드 인라인 캐시는 명령어 자리마다 하나다. 한 자리가 칸 배치가 다른 표들을 번갈아 보면 `t.Name` 6.5ns vs `t[i]` 4.6ns(1.4배). 표 하나면 키 162개에서도 0.4ns 차 | perf:1204-1222 | 실측 | 일반 | luau-perf/optimizer-and-native.md | 없음 | -O2, 11회. `bench:trait-fn-number.luau` |
| S-P23 | perf | 해시 조회 키 종류: 테이블 키 14.8ns vs 숫자 키 9.1ns | perf:1096-1099, perf:1103 | 실측 | 일반 | luau-perf/tables.md | 없음 | -O2 |
| S-P24 | perf | 상수 접기: 다른 모듈에서 받은 상수(`const K = M.K`, `Trait.TYPE_KEY`)로 `t[K] = v` 하면 상수 키 명령을 못 써 생성이 7~11% 느리다 → 리터럴이나 같은 파일의 리터럴 지역 상수로 적는다. 상수가 아닌 이름의 문자열 조회는 1.5~3ns 더 든다 | perf:597-600, perf:1488-1489; stl:conventions.md:42; stl:base/architecture.md:172,209 | 실측 | 일반 | luau-perf/optimizer-and-native.md | 없음 | -O2. "재대입 없는 리터럴 초기화 지역만 접는다" 는 원리는 스니펫으로 확인 필요. S-101 병합 |
| S-P25 | perf | 키 이름만 바꿔도 해시 칸 배치가 바뀌어 같은 모양의 생성 시간이 ±5% 흔들린다. 고르게 나은 이름은 없다 | perf:601-605 | 실측 | 반일반 | luau-perf/benchmarking-method.md | 없음 | 해석 주의용 |
| S-P26 | perf | -O2 인라인: 같은 모듈의 루프 없는 지역 함수는 인라인돼 0ns. 다른 모듈의 함수와 루프가 있는 함수는 인라인되지 않는다 → 같은 파일에 둔 흉내 함수로 벤치하면 비교가 틀어진다 | perf:1518, perf:1530, perf:1157-1158, perf:1424, perf:1696 | 실측 | 일반 | luau-perf/optimizer-and-native.md | 없음 | S-116(에러 level)의 원인과 같은 메커니즘 |
| S-P27 | perf | 업밸류로 값을 든 클로저 판이 지역 함수 판보다 5~8ns 비싸다(16.4 vs 8.1ns). 벤치 루프에서 한쪽만 업밸류로 읽으면 0.77x 같은 거짓 차이가 난다 | perf:1519-1531, perf:1599 | 실측 | 일반 | luau-perf/calls-and-closures.md | 없음 | -O2 |
| S-P28 | perf | 필드를 거친 인덱싱은 루프 밖에서 지역으로 받는다. `a.data[i]` 를 그대로 쓰면 1.43배(1024개 6247 vs 4356ns) | perf:1584, perf:1587 | 실측 | 일반 | luau-perf/iteration.md | 없음 | 0.742 -O2 |
| S-P29 | perf | 함수를 한 겹 감싸면 호출당 13~17ns, 호출 하나를 더하면 10~15ns. 테이블에서 함수를 루프 밖에서 미리 꺼내 두면 직접 호출과 같다(59.7 vs 59.8ns) | perf:1310-1321, perf:1299, perf:1405-1407 | 실측 | 일반 | luau-perf/calls-and-closures.md | 없음 | -O2, 15회 |
| S-P30 | perf | 평범한 함수 호출 0.012µs, `pcall` 0.037µs, `coroutine.create`+`resume` 0.174µs | perf:289-293 | 실측 | 일반 | luau-perf/calls-and-closures.md | 없음 | 0.734 -O1, 10만×5 |
| S-P31 | perf | 타입 캐스트 `::` 의 런타임 비용은 0이다(22.2~24.2 → 22.3~23.5ns, 잡음 안) | perf:1550-1551 | 실측 | 일반 | luau-perf/optimizer-and-native.md | 없음 | -O2. 단 R-12(다중 반환 절단)는 의미가 바뀌는 별개 문제 |
| S-P32 | perf | `rawget` 은 호출 비용이 있어 필드 읽기보다 비싸다(`v.__type` 8.1ns, `rawget` 11.5, `type()`+`rawget` 14.6). MT 정수 칸 세금도 못 피한다 | perf:1519-1521, perf:25-26, perf:1094 | 실측 | 일반 | luau-perf/metatables.md | 없음 | -O2 |
| S-P33 | runtime·엔진 | `#` 는 O(log n), 20만 배열에서 약 90ns. `table.sort`·`insert`·`concat` 은 n 이 아니라 `#` 범위를 본다(구멍 뒤 잘림·밖 값 섞임) | perf:471-480, perf:241 | 실측 | 일반 | luau-perf/tables.md | 일부(kb:luau-types/references/solver-limits.md §3 의 `#` 경계 줄) | perf:244-245 정정 꼬리표는 라이브러리 동작 쪽 이야기다 |
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
| S-P47 | perf | 차수만 보고 "훨씬 빠르다" 고 쓰지 않는다. O(n+m) 정렬 병합이 해시에 5.9~50배 지고, O(n) 힙 짓기는 상수 1.7배다. 이 런타임에서는 C 로 내려가는 쪽이 거의 늘 이긴다 | perf:169-172, perf:204-205 | 실측 | 반일반 | luau-perf/benchmarking-method.md | 없음 | 원칙 |
| S-P48 | perf | 결과 크기를 알면 `table.create(n)` 으로 미리 잡는다(N=10 에서 0.45→0.33µs, 크면 차이 없음). 크기 필드를 원소마다 올리기보다 지역으로 세고 한 번 쓰는 쪽이 1.16~1.18배 빠르다 | perf:757-758, perf:768, perf:884-886 | 실측 | 반일반 | luau-perf/tables.md | 없음 | -O2 |
| S-P49 | perf | fastcall 은 내장 라이브러리 함수만 받는다. `buffer.*` 등이 네임스페이스 함수인 이유에는 인덱싱 속도도 있다 | perf:424-426, perf:441 | 서술 | 반일반 | luau-perf/optimizer-and-native.md | 없음 | 사용자 발언 기반, 미측정 |
| S-P50 | 기타 | (타입) 교집합 타입 컨테이너에서도 메소드가 이터레이터 삼중항을 돌려주면 for-in 루프 변수 타입이 산다(인덱서·`__iter` 경유는 잃음). 이터레이터는 `(number, T)` 로 선언하고, `(number?, T?)` 면 옵셔널이 된다 | perf:76-91 | 실측 | 반일반 | luau-types/(신설) iteration-typing.md | 없음 | 0.734. `stl:audit/arr-type-redesign/spikes/37`. 0.742 재확인 필요 |
| S-P51 | GC·수명 | Luau GC 는 할당이 있어야 진행한다. 유휴 클라이언트 힙이 12초간 56MB 그대로였고, 짧은 쓰레기를 할당하자 약 10MB 로 돌아왔다. 힙 측정은 churn 뒤 최저값으로 하고, 빌드는 별도 함수로 한다(지역 변수가 붙잡음) | quad:audit/perf-studio-2026-10-22/REPORT.md:14-17 | 실측 | 일반 | luau-perf/gc-and-memory.md | 없음 | Studio Play. quad 출처지만 stl 에 없는 보완 사실이라 넣었다 |
