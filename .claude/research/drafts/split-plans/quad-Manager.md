# 분리 계획 시험: quad devui `kits/roblox-devui/src/Window/Manager.luau`

> 2026-11-10. 읽기 전용 시험 실행이다. quad 저장소에는 아무것도 쓰지 않았다(다른 세션 상주). 계획기: luau-kb `skills/luau-style/scripts/split-plan.py`.
> 명령: `python3 -I split-plan.py /code/Projects/quad/kits/roblox-devui/src/Window/Manager.luau`. 아래 "계획기 출력"은 손대지 않은 원문이다.

## 이 파일의 모양

파일 3,352줄 가운데 2,800줄이 `build(q)` → `Manager.new()` **한 함수의 본문**이다. 그 안에 지역 함수 83개, 지역 상태 20여 개(`order`·`known`·`live`·`pending`·`units`·`quiet`…), 공개 메서드 표(`ExportLayout`·`ImportLayout`·`Register` 등 6개, 표 생성자 안의 `Name = function`)가 있다. 계획기는 이것을 알아보고 `new` 안으로 내려가 분석했다.

## 사람 분석과의 비교 (audit/12 §2.2: "창 관리, 도킹 배치, 분할, 탭, 저장")

| 사람 | 계획기 | 판정 |
|---|---|---|
| 저장 | `Import`(snapshot·stateOf·savedUnit·holders·`ImportLayout`·`ExportLayout`…) | 맞음. 이름은 `Persist`/`LayoutIO` 가 낫다 |
| 분할 | `Floor`(arrange·minOf·canFold·normalizeFolds·unitFloor) | 맞음. 이름 후보 `Arrange` 가 같이 나왔다 |
| 도킹 배치 | `JudgeOver`(dropAt·judgeOver·bandAt·half) + `Member` 의 setUnitSide·occupant·settle | 반쯤. 드롭 판정은 따로 나왔고 가장자리 배치는 `Member` 에 섞였다 |
| 탭 | `Member`(memberOf·dropMember·leave·neighbour) 와 `Focus`(newLeaf·newUnit·join·joinTabs) 로 갈림 | 어긋남. 탭은 "구성원 관리"와 "합치기"로 나뉘었다 |
| 창 관리 | `Focus`(focus·restack·renumber·succeed) + `OnPress`(pressed·onPress·hook) | 대체로 맞음 |

**일치도**: 5묶음 중 저장·분할·창 관리 3묶음이 대응, 도킹·탭은 경계가 다르다. 이 파일은 지역 함수가 상태 20개를 같이 쥐어서 호출·상태 신호가 촘촘하다. 경계가 흐린 것은 계획기 탓만이 아니라 코드가 실제로 얽혀 있다는 신호다.

## 스스로 비평

- **가장 중요한 출력은 6절 1단계다.** 상태가 인스턴스마다라서 `State.luau` 로 옮길 수 없고, 먼저 상태 표(`ctx`)로 꺼내는 다시 짜기가 필요하다. 군집 사이 상태 공유가 13개, 순환을 끊을 간선이 4개(15호출쌍)다. 한 게임 저장소의 화면 모듈이 이 단계를 건너뛰어 다시 자랐다(structure.md §7). 그래서 이 파일의 분리안은 "옮기기만"이 아니라 **"상태 표 꺼내기 → 옮기기"** 두 단계로 사용자에게 물어야 한다.
- `Register`(500줄, 안쪽 함수 11)는 그 자체가 닫개 덩어리다. 계획기가 `--scope Register` 를 안내한다. 창 하나를 등록하며 단계마다 클로저를 만드는 꼴이라, 파일을 나눠도 이 함수는 단계별 함수로 따로 쪼개야 한다.
- 구획은 주석 띠 셋뿐이고 범위가 넓어(`the split layout` 689–2082) 이름 짓기에 쓰지 않았다(구획이 `--max` 의 1.5배를 넘으면 무시). 이름은 대부분 "(약함)"이다 — 사람이 짓는다. quad 는 "가족 접기만" 저장소이므로 결과 폴더는 `Window/Manager/{init, Arrange, Drop, Persist, Tabs, Focus, Core}` 정도가 될 것이다.
- **알고리즘에 반영한 것**: (1) 파일 대부분이 한 함수의 본문이면 그 안으로 내려간다(두 단계까지 확인: `build` → `new`). (2) 표 생성자 안의 `Name = function` 공개 메서드를 단위로 잡는다(처음엔 공개 메서드 780줄을 통째로 놓쳤다). (3) `-- ── 제목 ──` 주석 띠를 구획으로 읽는다. (4) 150줄 넘는 함수 중 안쪽 함수가 다섯 이상이면 "닫개 덩어리"로 표시하고 `--scope` 를 안내한다.

---

## 계획기 출력

### (계획기 제목) `/code/Projects/quad/kits/roblox-devui/src/Window/Manager.luau` (3352줄)

- 분석 범위: **build (396–3347) → new (541–3341)** 의 안쪽(541–3340줄). 파일 대부분이 한 함수의 본문이라 그 안의 지역 함수와 닫개 상태를 단위로 봤다. 이 상태는 인스턴스마다 따로라서 **모듈 수준 `State.luau` 로 옮길 수 없다** — 먼저 상태 표(객체)로 꺼내 함수에 넘기는 단계가 필요하다(splitting.md §닫개).
- 함수 89개(공개 6), 타입 선언 0줄, 상태 20개, 상수 5개, require·서비스 0개, 구획 3개(banner)
- 군집 6개 + 공용 헬퍼 3개(31줄). 나누면 군집 사이 require 19개, 순환 1묶음.

## 1. 응집 군집 (후보 파일)

| 후보 파일 | 줄 | 함수 | 공개 | 원래 구획 | 줄 범위 | 쓰는 상태 |
|---|---|---|---|---|---|---|
| `Manager/Import.luau` | 543 | 20 | 5 | - | 578–582, 653–664, 1225–1238, 1341–1372 … | live, pending, known, layoutUsed, pendingLeaf … |
| `Manager/Focus.luau` | 592 | 21 | 0 | - | 584–587, 968–983, 1083–1164, 1619–1644 … | units, order, layoutDirty, batching, arranged … |
| `Manager/Member.luau` | 791 | 16 | 1 | - | 599–606, 637–651, 950–963, 1072–1081 … | quiet, order, nextId, live, forgetting … |
| `Manager/Floor.luau` | 414 | 17 | 0 | - | 666–948, 984–1070, 1493–1521, 2255–2283 | pending, arranged |
| `Manager/OnPress.luau` | 121 | 6 | 0 | - | 1930–2055 | order, lastPress, hooked, offPress |
| `Manager/JudgeOver.luau` | 164 | 6 | 0 | - | 2085–2253 | order |
| `Manager/Core.luau` (공용 아래층) | 31 | 3 | - | - | - | - |

- **Import** (이름 근거: 낱말(약함); 다른 후보 ImportLayout, Unit, Window): remember, leafOfKey, unitOfKey, leavePending, snapshot, stateOf, groupable, holders, savedUnit, plainUnit, build, importBatch, noticeKeyless, gatherKnown … 외 6
- **Focus** (이름 근거: 중심 함수(약함); 다른 후보 DragSplitter, Join, Unit): liveKey, pushView, adopt, newLeaf, newUnit, dissolveIfSmall, refresh, batch, gatherOrder, renumber, restack, bringOut, focus, isOpen … 외 7
- **Member** (이름 근거: 낱말(약함); 다른 후보 Register, Collapsed, Drop): memberOf, neighbour, spreadCollapsed, restructured, dropMember, leave, setUnitSide, occupant, neighbours, settle, insets, apply, applyMember, plainState … 외 2
- **Floor** (이름 근거: 낱말(약함); 다른 후보 Arrange, Edge, Fold): floorOf, leafFloor, hasOpen, visibleOf, edgeLeaf, foldSize, minOf, stands, present, hasUnfolded, canFold, normalizeFolds, unitFloor, arrange … 외 3
- **OnPress** (이름 근거: 중심 함수(약함); 다른 후보 Entry, Focused, Hook): ownerOf, windowOf, focusedEntry, pressed, onPress, hook
- **JudgeOver** (이름 근거: 중심 함수(약함); 다른 후보 DropAt, Band, Drop): joinable, unitScreenRect, bandAt, half, judgeOver, dropAt
- **Core**(셋 이상의 군집이 부르는 작은 무상태 함수 — 다른 파일들이 require 하는 아래층. init 에 두면 순환이 된다): isOpenWindow, drawnOf, faceOf

## 2. 군집 사이 간선 (나눈 뒤의 require)

| 부르는 쪽 → 불리는 쪽 | 호출 쌍 | 넘는 이름 |
|---|---|---|
| Member → Focus | 12 | batch, dissolveIfSmall, dragSplitter, focus, join, leaveIfElsewhere … 외 2 |
| Import → Member | 10 | apply, applyMember, dropMember, leave, occupant, plainState … 외 2 |
| Floor → Core | 7 | drawnOf, faceOf, isOpenWindow |
| Import → Focus | 7 | batch, liveKey, newLeaf, pushView, refresh, renumber … 외 1 |
| Focus → Core | 6 | drawnOf, faceOf, isOpenWindow |
| JudgeOver → Core | 6 | drawnOf, faceOf, isOpenWindow |
| Focus → Member | 5 | insertionPoint, leave, memberOf, restructured |
| Member → Import | 5 | gatherKnown, leavePending, noticeKeyless, remember, snapshot |
| Member → Core | 4 | drawnOf, isOpenWindow |
| Member → Floor | 4 | canFold, edgeJoin, floorOf, unitFloor |
| Focus → Import | 3 | build, gatherKnown |
| Floor → Member | 2 | occupant, spreadCollapsed |
| Focus → Floor | 1 | writeViews |
| Import → Floor | 1 | savedTree |
| OnPress → Core | 1 | faceOf |
| OnPress → Focus | 1 | focus |
| Floor → JudgeOver | 1 | joinable |
| Member → OnPress | 1 | hook |
| Member → JudgeOver | 1 | dropAt |

## 3. 순환 위험

- 서로 부르는 군집 5개. 위층 → 아래층 순서 제안: Import → Member → OnPress → Focus → Floor
  - 이 순서를 거스르는 간선 4개(호출 쌍 15)만 끊으면 순환이 없다:
    - Focus → Member 5쌍: insertionPoint, leave, memberOf, restructured
    - Member → Import 5쌍: gatherKnown, leavePending, noticeKeyless, remember, snapshot
    - Focus → Import 3쌍: build, gatherKnown
    - Floor → Member 2쌍: occupant, spreadCollapsed
  - 끊는 법: 그 이름을 부르는 쪽 군집으로 옮기기(작으면) → 내부 표 늦은 조회(`S.f(...)`, splitting.md §3) → 인자로 넘기기(콜백 주입) 순으로 본다.

## 4. 전방 선언

- `writeViews`: 선언 967줄, 정의 984줄, 정의는 Floor — 다른 군집(Focus)이 부른다 → 파일 경계를 넘으므로 늦은 조회 표로 바꿔야 한다
- `flushLayout`: 선언 576줄, 정의 1631줄, 정의는 Focus — 같은 군집 안에서만 쓴다 → 그 파일 안에 그대로 둘 수 있다

## 5. 공유 상태를 어디로

- 여러 군집이 쓰는 것 → 상태 표(인스턴스마다 하나, 함수에 넘김):
  - `order` (545줄) — 함수 13개, 쓰는 함수 2개, 군집 Focus, JudgeOver, Member, OnPress
  - `known` (552줄) — 함수 9개, 쓰는 함수 2개, 군집 Focus, Import, Member
  - `live` (553줄) — 함수 10개, 쓰는 함수 1개, 군집 Focus, Import, Member
  - `pending` (554줄) — 함수 10개, 쓰는 함수 5개, 군집 Floor, Focus, Import, Member
  - `forgetting` (556줄) — 함수 4개, 쓰는 함수 4개, 군집 Import, Member
  - `layoutDirty` (559줄) — 함수 8개, 쓰는 함수 6개, 군집 Focus, Import, Member
  - `keyless` (563줄) — 함수 2개, 쓰는 함수 1개, 군집 Import, Member
  - `units` (567줄) — 함수 8개, 쓰는 함수 4개, 군집 Focus, Import
  - `pendingLeaf` (568줄) — 함수 8개, 쓰는 함수 6개, 군집 Focus, Import, Member
  - `arranged` (569줄) — 함수 4개, 쓰는 함수 3개, 군집 Floor, Focus
  - `quiet` (571줄) — 함수 7개, 쓰는 함수 7개, 군집 Focus, Member
  - `importing` (574줄) — 함수 2개, 쓰는 함수 1개, 군집 Import, Member
  - `lastPress` (590줄) — 함수 3개, 쓰는 함수 3개, 군집 Member, OnPress
  - 숫자·불리언 상태를 다른 모듈이 다시 대입하면 사본이 갈라진다. 표의 필드로 옮겨 `State.x = …` 로 쓴다.
- 한 군집만 쓰는 것 → 그 파일로 같이 옮김: `nextId`→Member, `hooked`→OnPress, `offPress`→OnPress, `batching`→Focus, `layoutUsed`→Import, `keylessNoticed`→Import, `splitDrag`→Focus

## 6. "옮기기만" 커밋 순서

1. **(다시 짜기)** 닫개 상태를 상태 표로 꺼낸다. 지역 함수가 `ctx` 를 받게 바꾼다. 이 커밋은 옮기기가 아니다 — 동작 diff 0 을 테스트로 확인한다. 이 단계를 건너뛰면 분리가 멈춘다(실제 사례의 교훈).
2. `Manager.luau` → `Manager/init.luau` 로 접는다(바깥 require 경로 그대로).
3. 공용 아래층 함수 3개를 `Manager/Core.luau` 로 옮긴다(init 이 아니라 여기를 다른 조각이 require 한다).
4. 경계를 넘는 전방 선언(`writeViews`)을 내부 표 늦은 조회로 바꾼다.
5. 옮기기만: **JudgeOver** (164줄, 함수 6) → `Manager/JudgeOver.luau`. require: Core
6. 옮기기만: **Floor** (414줄, 함수 17) → `Manager/Floor.luau`. require: JudgeOver, Core
   - 아직 위층에 있는 이름은 늦은 조회로 받는다: Member.occupant, spreadCollapsed
7. 옮기기만: **Focus** (592줄, 함수 21) → `Manager/Focus.luau`. require: Floor, Core
   - 아직 위층에 있는 이름은 늦은 조회로 받는다: Import.build, gatherKnown; Member.insertionPoint, leave, memberOf, restructured
8. 옮기기만: **OnPress** (121줄, 함수 6) → `Manager/OnPress.luau`. require: Focus, Core
9. 옮기기만: **Member** (791줄, 함수 16) → `Manager/Member.luau`. require: Focus, Floor, OnPress, JudgeOver, Core. init 이 공개 1개를 재수출
   - 아직 위층에 있는 이름은 늦은 조회로 받는다: Import.gatherKnown, leavePending, noticeKeyless, remember, snapshot
10. 옮기기만: **Import** (543줄, 함수 20) → `Manager/Import.luau`. require: Focus, Member, Floor. init 이 공개 5개를 재수출
11. 이음매 감사(옮긴 상태가 값으로 묶였나, 정리 누락, 순서)와 문서의 옛 `파일:줄` 갱신.

## 7. 긴 함수 (파일을 나눠도 남는 덩어리 — 본문을 단계별 함수로)

- `Register` 500줄 (2837줄~, Member) — **닫개 덩어리**: 안쪽 함수 11개가 지역 10개를 같이 쥔다. 상태 표로 먼저 꺼내야 옮기기만으로 나눌 수 있다. 안쪽 계획: `--scope Register`
- `ImportLayout` 213줄 (2569줄~, Import)

## 8. 반복 블록 (고치기 커밋 후보 — 옮긴 뒤에)

- 5회 (679, 955, 1037, 2394, 2736줄): `for _, m in leaf.Members do ⏎ local e = m.Entry ⏎ if e ~= nil then`
- 같은 머리 줄 14회: `local e = m.Entry`
- 같은 머리 줄 11회: `if e ~= nil then`
- 같은 머리 줄 9회: `if u ~= nil then`
- 같은 머리 줄 8회: `if entry ~= nil then`
- 같은 머리 줄 8회: `local deco = entry.Deco`

## 9. 참고: 이름 가족과 구획

- 접미 `window` 4개: ExportWindow, ForgetWindow, ImportWindow, isOpenWindow
- 접미 `unit` 4개: newUnit, plainUnit, savedUnit, takeUnit
- 접두 `unit` 3개: unitFloor, unitOfKey, unitScreenRect
- 접두 `import` 3개: ImportLayout, ImportWindow, importBatch
- 접미 `key` 3개: leafOfKey, liveKey, unitOfKey
- 구획 3개: units (headers TABS, SPLITS)(592–688); the split layout (header SPLITS)(689–2082); joining and splitting (headers TABS, SPLITS)(2083–3340)

