# 12 — 코드 구조 지적 이력, 저장소 실측, 재발 방지 설계

2026-11-10 작성. 원천은 모두 읽기 전용으로 다뤘다. 다른 저장소에는 쓰지 않았고 git 은 `log`·`show`·`ls-tree` 만 썼다.

## 범위와 방법

- **사용자 메시지**
  - `history.jsonl` 2,294줄과 `projects/-code-Projects*/` 메인 세션 `.jsonl` 의 `type=user` 텍스트만 뽑았다(3,669건, `/tmp/cs12/user_msgs.jsonl`). 서브에이전트 트랜스크립트는 읽지 않았다.
  - 키워드는 감사 10과 같은 방식으로 한국어·영어 정규식을 썼다. 분리, 쪼개, 나누, 너무 길, 몇천, 폴더, 묶, flat, 재배치, 하드코딩, 중복, 복붙, 코드 퀄리티, 유지보수, 난잡, split, hardcode.
  - 근거 표기 `hL416` 은 history.jsonl 416번째 줄이다.
- **기록**
  - auto memory 10개 프로젝트를 봤다. 구조를 다룬 것은 devplorer `feedback-audit-after-move` 하나다.
  - 각 저장소 `.claude/` 의 review·audit·todos·conventions 를 봤다.
  - 10개 저장소의 커밋 메시지에서 분리·이동·구조·폴더·정리를 찾았다.
- **실측**
  - 새로 만든 `.claude/archive/research/drafts/style/skills/luau-style/scripts/structure-scan.py` 로 쟀다(§2).
  - 무거운 실행은 `choom -n 1000` 으로 감쌌다.
  - 제외한 것: `node_modules`, `vendor`, `*_packages`, `build`, `dist`, `refs`, `*-ignoreme`, `.claude/worktrees`, 생성물 머리 표시가 있는 파일.
- **이 문서가 쓴 것**
  - 훅 `.claude/archive/research/drafts/hooks/structure-reminder.py` 와 회귀 표 `test-structure-reminder.py`(32/32 통과)
  - 측정기 `.claude/archive/research/drafts/style/skills/luau-style/scripts/structure-scan.py`
  - 참고 문서 `.claude/archive/research/drafts/style/skills/luau-style/references/structure.md`
  - 사용자 rules 후보 `.claude/archive/research/drafts/style/rules/code-structure.md`
  - 결정 `.claude/base/decisions/D-13-file-structure.md`
  - 고친 것: `luau-style/SKILL.md` 표 세 줄과 description, `references/modules.md` §4 한 줄, `.claude/research/drafts/agents/luau-quality-auditor.md` 먼저 할 일 4번과 "구조 측정" 항목

## 0. 요약

| # | 발견 | 근거 |
|---|---|---|
| 1 | 구조 지적 사례 9건(주요 6, 부수 3). **주요 6건은 모두 사용자가 직접 코드를 열어 보고 지적했다.** 모델이 먼저 나누자고 한 것은 table-sim 1건뿐이다 | §1 |
| 2 | 지적을 받은 뒤의 분리는 빨랐고 안전했다. quad·stl·devplorer 는 같은 날 "옮기기만" 커밋으로 끝냈고, 분리가 만든 버그는 보고되지 않았다 | §1, 커밋 |
| 3 | **문제는 자라는 속도다.** devplorer `Server/init.luau` 는 사흘에 692 → 4,101줄, table-sim `<비공개>` 는 아흐레에 646 → 3,501줄, devui `Manager.luau` 는 이틀에 273 → 3,352줄이 됐다 | §2.4 |
| 4 | 리뷰는 크기를 보지 않았다. devplorer 리뷰 문서 15개가 4천 줄 파일을 `init.luau:1148` 처럼 인용했지만 분리를 말한 문서는 0개다 | §3 |
| 5 | 어느 저장소에도 줄 수 기준이 없다. 폴더 규칙은 devplorer 한 곳(2026-11-04)뿐이다. memory 에도 없다 | §3 |
| [비공개 프로젝트 세부 생략]
| 7 | 재발 방지는 알림 위주로 짰다. PostToolUse 훅(Write·Edit·**Bash**), paths 조건부 rules, 참고 문서와 측정기, 품질 감사자의 구조 측정이다. 별도 `/code-structure` 스킬은 만들지 않는다 | §5 |

---

## 1. 사례 표

| # | 프로젝트·시점 | 대상 | 사용자 지적 (발췌) | 그 뒤 실제 처리 | 처음에 그렇게 짠 이유 (추정) |
|---|---|---|---|---|---|
| C1 | quad · 09-07 (hL416) | `quad-base/src/Slot.luau` 1,194줄, `src/` 평평한 파일 25개 | "슬롯 파일 너무 길어서 유지보수성 조금 복잡해짐 … Slot/... 로 쪼갤 수 없는지", "src 안에 뭐가 너무 많은데 파일 구조를 어떻게 정리할지" | 같은 날 `4ddb9c5a` 가족 폴더 이동: `Slot/{init,Owner,Elements,Raw,Tree,List}`, `Ref/{init,PreRef,PostRef}`, `Attribute/`, `Dispatch/Modifier/`. 계획 `archive/surveys/2026-09-07-source-layout-plan.md`, 사용자 "패밀리 접기만, 대분류 안함". 이어서 `66281ab4` Attribute→Attr | `Slot` 전부가 `Init(module)` 하나의 본문이었다. 전방 선언 여덟 개로 상호 재귀를 묶어 두어 파일 경계를 넘길 수 없었다. 새 값 타입마다 `src/` 에 파일을 하나씩 더했다 |
| C2 | stl-luau · 10-13 (hL1525) | `src/Trait.luau` (트레이트 시스템 + 트레이트 구현 + 내장 토큰) | "Adt 보고싶은데 Trait.luau 봐야하는건 조금 문제. 폴더로 묶어서 하나 파줘" | 같은 날 `221cec9` `Collections/`·`Algorithms/` 순수 이동, `4e07d1a` `Traits/` 한 파일씩·`Trait.luau` 는 시스템만, `9f1f937` 토큰을 각 컨테이너로, `50ce406` 재배치 리뷰 | 트레이트를 더할 때마다 시스템 파일에 덧붙였다. "정의가 쓰이는 곳" 옆에 둔 것이다 |
| C3 | stl-luau · 10-13 (hL1540) | 노드 도구가 한 파일 | "Node 는 한 파일에 있는게 좀 그렇네 … Trees 처럼, Node 폴더" | 같은 날 `beab32b` `src/Node/` 4개 파일 | 같은 이유. 단방향·양방향·이진 노드를 한 모듈로 시작했다 |
| [비공개 프로젝트 세부 생략]
| C5 | quad · 10-16 (hL1798) | quad 전체, table-sim 의 quad 사용 | "코드리뷰의 각도가 코드 퀄리티였던적은 잘 없음. 코드 분리나 등등" | `qa-request/code-quality-review-round15.md`(875줄, sonnet·Gemini 토론에 opus 판정). `68cd74e5` material `ListReorder/` 폴더화, `KeyedSlot` 복사 제거, `fitScale` 공유. **다음 날부터 devui `Manager.luau` 가 273 → 3,352줄로 자랐다** | 리뷰가 정확성·공개 표면만 봤다. 한 번 하는 품질 리뷰는 그 뒤의 성장을 막지 못했다 |
| C6 | devplorer · 11-04 (hL2160, hL2161) | `Server/init.luau` 4,199줄, `Client/App/` 평평한 항목 60개 | "server init 파일이 4000줄이나 된다는건 좀 다시 생각해볼 필요가", "폴더로 잘 묶을건 묶어주는것도 중요해. quad가 한 곳에 전체로 있다가 사람이 보기 많이 어려워져서" | 같은 날 `cfeedd1` 4,199 → 242줄(`Core/ Policy/ Handlers/ Window/`), `8951fc1` App 60 → 16, `c332af6` Explorer 긴 함수 분리, `7280dee` Common 분리. `conventions.md` "코드 배치" 규칙과 대조표 `.claude/audit/2026-11-04-code-layout.md`. 11-08 사용자 질문으로 옮긴 뒤 감사를 돌렸다(memory `feedback-audit-after-move`) | 처리기를 더할 때마다 `init.luau` 의 처리기 표 옆에 붙였다. 692 → 4,101줄까지 커밋 55개였다. 클라이언트는 `ExplorerActions`·`BookmarkMenu` 처럼 폴더 대신 접두로 묶었다 |
| C7 | quad · 11-10 (hL2270) | `quad-types/src/init.luau` 970줄 | "접힘이 하나도 없다는점 … `--#region` … 식으로 정리가 되어야할듯"(`note-ignoreme.txt`) | 같은 날 `0c2eef35` region 접기·주석 정리 | 타입 모음이라 한 파일이어야 했다. 그런데 묶음 표시 없이 덧붙였다 |
| [비공개 프로젝트 세부 생략]
| 부수 | quad · 09-08 (hL497) | `.claude/README.md` 151줄/163KB | "README.md 를 분리해 각 폴더 내에 두어" | `eb51010f` 폴더별 README | 문서에도 같은 덧붙이기 경향이 있다 |
| 부수 | quad · 09-03, 10-06 (hL300, hL1177) | 긴 함수 안의 디버그 갈래 | "위쪽으로 함수로 빼고, if debug then ...() end 식으로 끝나게 해서 코드 보기 좋게" | 그 회차에 반영 | 함수 단위의 같은 경향 |
| 부수 | quad · 10-22 (hL2122) | 킷 둘이 루트에 | "폴더로 나누는건 그대로일듯 해" | `3036e6b8` `kits/` 로 이동 | 패키지 단위 |

**세어 보면**
- 사용자의 구조 지적 9건 가운데 6건이 Luau 로직 파일이다.
- 지적 시점의 크기는 970 ~ 4,884줄이다. 사용자가 "길다"고 반응한 가장 작은 로직 파일은 1,194줄(C1)이다.
- [비공개 프로젝트 세부 생략]

## 2. 현재 상태 측정

### 2.1 저장소별 분포 (비테스트·비생성 소스)

| 저장소 | 파일 | 줄 | p50 | p90 | 최대 | ≥800 | ≥1,500 |
|---|---|---|---|---|---|---|---|
| quad | 319 | 71,886 | 172 | 443 | 3,352 | 4 | 2 |
| stl-luau | 43 | 13,872 | 175 | 675 | 3,030 | 3 | 1 |
| table-sim | 73 | 31,988 | 197 | 834 | 4,884 | 9 | 4 |
| devplorer | 182 | 41,651 | 129 | 594 | 1,652 | 10 | 1 |
| tbox | 42 | 5,288 | 127 | 218 | 300 | 0 | 0 |
| rbvm | 11 | 2,062 | 111 | 443 | 490 | 0 | 0 |
| moonwave-luau | 3 | 2,630 | 1,261 | 1,294 | 1,294 | 2 | 0 |
| mrow | 74 | 4,265 | 43 | 86 | 343 | 0 | 0 |
| vitrine (Go·TS) | 50 | 10,066 | 166 | 414 | 702 | 0 | 0 |
| VideoSync (TS·Go) | 121 | 26,659 | 118 | 450 | 2,500 | 6 | 1 |

- 생성물로 뺀 것: table-sim 의 생성 데이터 파일 28개는 머리에 "만든 것: scripts/meshgen.py … 손으로 고치지 않는다"가 있다. quad `globalTypes.d.luau` 19,110줄도 뺐다.
- VideoSync `harness/browser/media/*.ts` 는 MPEG-TS 영상 조각이다(TypeScript 아님). 측정기와 훅 모두 `media/` 와 바이너리를 뺀다.

### 2.2 가장 큰 문제 파일 Top 5

| # | 파일 | 줄 | 성장 | 무엇이 섞였나 |
|---|---|---|---|---|
| 1 | table-sim `<비공개>` | 4,884 | 10-11 시작, 10-12 1,000 돌파, 커밋 79, **분리 0** | 함수 134개. 기록과 세션, 생성, 끌기·놓기, 묶음, 주머니, 손패 운반, 판·붙는 자리, 시계·주사위·피규어, 저장·불러오기. 전방 선언 3개, 모듈 수준 깃발 2개 |
| 2 | table-sim `<비공개>` | 3,501 | 646 → 3,501 아흐레, 커밋 92, 분리 0 | 처리기 73개 + 세트 생성 16갈래 + 한도·쿨다운 + 로비 상태. §4 |
| 3 | quad `kits/roblox-devui/src/Window/Manager.luau` | 3,352 | 10-20 273 → 10-21 3,252(도킹 단계마다 덧붙임), 분리 0 | 창 관리, 도킹 배치, 분할, 탭, 저장 |
| 4 | table-sim `<비공개>` | 3,223 | 1,851 → 1,457(분리) → 3,223(**재성장**) | 커서·평면·끌기 세 갈래·쥐여 받기·카메라 |
| 5 | stl-luau `src/Collections/Arr.luau` | 3,030 | 09-22 시작, 커밋 87 | 컨테이너 하나의 API(함수 145, region 31). "타입 하나에 파일 하나" 설계라 예외 후보(D-13) |

[비공개 프로젝트 세부 생략]

### 2.3 평평한 폴더 Top 5

| # | 폴더 | 소스 | 하위 폴더 | 메모 |
|---|---|---|---|---|
| 1 | quad `kits/roblox-devui/src/` | 38 | 2 (`Inputs/`, `Window/`) | 위젯·입력·팝업·가상 행이 한 줄로 섰다. `Popup*`·`Tree*`·`Virtual*`·`Color*` 가족 |
| 2 | table-sim `<비공개>` | 21 | 0 | 엔진 없는 로직 모음. 저장 문서, 권한, 더미, 손패, 묶음이 섞였다 |
| 3 | devplorer `src/Client/App/Explorer/` | 19 | 0 | 11-04 분리 때 `Explorer/init.luau` 에서 뗀 조각이 한 폴더에 모였다 |
| [비공개 프로젝트 세부 생략]
| 5 | devplorer `src/Server/Core/` | 16 | 0 | 층 규칙상 정상이지만 16개 |

빼고 본 것
- 같은 종류만 모인 폴더: `tests/`, `stories/`, tbox `schema/roblox/` 17개(타입마다 하나), table-sim 의 생성 데이터 폴더.
- Go 패키지(VideoSync `server/internal/hub/` 17개): Go 는 패키지 = 폴더라 평평한 것이 관례다.
- quad `quad-base/src/`: 29개지만 가족 폴더 5개가 있다. 사용자 결정("대분류 안함")대로다.

### 2.4 커지고 나뉜 이력 (`git log --numstat --follow`)

| 파일 | 800 넘은 날 | 최대 | 분리 | 그 뒤 |
|---|---|---|---|---|
| quad `Slot.luau` | 09-07 이전 | 1,194 | 09-07 `4ddb9c5a` → `Slot/` 7개 | 지금 `Slot/` 7개 파일, 가장 큰 `init.luau` 629줄 |
| devplorer `Server/init.luau` | 10-19 (692 → 1,688 하루) | 4,199 | 11-04 `cfeedd1` → 242 | 유지 |
| devplorer `App/Explorer/init.luau` | 10-19 | 2,117 | 11-04 `c332af6` 1,990 → 998 | 유지 |
| table-sim `<비공개>` | 10-12 이전 | 3,243 | 10-12 `6c55ec2` → 151 | 유지 |
| table-sim `<비공개>` | 10-12 | 3,223 | 10-12 `16923f3` 1,851 → 1,457 | **재성장 3,223** |
| table-sim `<비공개>` | 10-12 (646 → 889) | 3,501 | 없음 | — |
| table-sim `<비공개>` | 10-12 | 4,884 | 없음 | — |
| devui `Window/Manager.luau` | 10-21 (765 → 2,162 하루) | 3,353 | 없음 | — |
| VideoSync `engine.ts` | 09-16 이전 | 2,653 | 없음 | — |

- 훅이 있었다면(경고 800) 측정한 모든 경우에 800줄을 넘은 첫날 알림이 났다. 사용자가 지적한 날보다 devplorer 는 16일, table-sim `<비공개>` 는 29일 이르다.

### 2.5 하드코딩·중복 의심 (측정기 결과에서 사람이 거른 것)

| 종류 | 위치 | 판정 |
|---|---|---|
| [비공개 프로젝트 세부 생략]
| [비공개 프로젝트 세부 생략]
| 패키지 사이 복사 | quad devui `ColorModel.luau` ↔ material `ColorPicker/ColorModel.luau`(204창, 머리에 "A COPY … a fix in one belongs in both"), `StoryKit`·`Quad.luau` 쌍 | 의도한 복사(devui 가 material 에 의존하지 않으려고). **같음 검사가 없다** → 측정기·감사자가 잡도록 함 |
| 의도된 사본 | vitrine `recovery/recover.py` ↔ `server/internal/recovery/kit/recover.py` (완전히 같음) | embed 때문. `format.go:4` 에 "deliberately independent" 주석. 문제 아님 |
| 데이터 모듈 | table-sim `<비공개>`(리터럴 90%), devplorer `ClassIcons.luau`(94%) | 데이터만 든 모듈이라 길이 기준 제외 대상. 좋은 꼴 |
| 생성 데이터 | table-sim 의 생성 데이터 폴더 (저폴리 전 9,911줄 → 2,190줄) | 좋은 꼴. 머리 표시, 생성기 경로, 로직과 분리 |

## 3. 원인 분석 — 왜 처음에 그렇게 짰나

1. **덧붙이기가 가장 싼 길이다.**
   - 요청 하나는 처리기 하나다. 처리기 표(`handlers`)가 있는 파일에 붙이는 diff 가 가장 작다.
   - devplorer 서버(커밋 55)와 table-sim 서버 모듈(커밋 92)의 성장은 거의 전부 이런 한 번에 몇십~몇백 줄짜리 덧붙이기다.
   - 사용자가 밤샘 자율 작업을 허락한 회차(table-sim 10-12~16, devplorer 10-19~21)에 가장 빨리 자랐다.
2. **길이가 보이지 않는다.**
   - Edit 도구는 `old_string` 조각만 다루고, Read 는 2,000줄에서 잘린다.
   - 감사 10 에 따르면 이 세션들은 파일 수정의 대부분(약 10.3k)을 `sed -i`·python 으로 했다. 그래서 파일 전체 길이를 볼 계기가 없었다.
3. **기준이 없었다.**
   - 10개 저장소 어디에도 줄 수 기준이 없었다. 폴더 규칙은 devplorer 가 분리를 겪은 뒤(11-04)에야 생겼다. memory 에도 없다.
   - 다른 저장소의 교훈이 넘어가지 않았다. 사용자가 devplorer 에 quad 경험을 직접 말해 줘야 했다(hL2161).
4. **리뷰의 각도가 달랐다.**
   - 보안·정확성 리뷰는 줄 번호로 인용하며 4천 줄 파일을 읽었지만 크기를 말하지 않았다(devplorer `review/` 15건).
   - 사용자도 "코드리뷰의 각도가 코드 퀄리티였던적은 잘 없음"이라고 했다(hL1798).
   - 품질 리뷰를 한 번 했어도(quad round15) 다음 날의 성장은 막지 못했다.
5. **늦게 나누면 비싸져서 미뤄진다.**
   - 클로저 공유 상태(큰 화면 모듈)와 전방 선언(quad Slot, table-sim 서버 모듈)이 있으면 "옮기기"가 "다시 짜기"가 된다.
   - 그러면 일부만 떼고 멈추고, 남은 덩어리가 다시 자란다(C4).
6. **폴더 대신 이름 접두로 묶는다.**
   - 새 모듈을 부르는 쪽 옆에 만들고 `ExplorerActions`, `BookmarkMenu`, `ItemZoneView` 처럼 이름으로 관계를 표시한다(devplorer 옛 App 60개, table-sim `<비공개>`).
7. **시제품 표시가 남은 채 확장된다.**
   - [비공개 프로젝트 세부 생략]
   - 처리기가 늘 때마다 손 검사도 같이 늘었다.
8. **복사로 의존을 피한다.** 의도는 정당하다(devui ↔ material). 하지만 같음을 지키는 장치 없이 "고치면 양쪽 다"라는 주석에만 기댄다.

## 4. table-sim net 분석

(공개판에서 이 절의 본문을 뺐다: 비공개 프로젝트의 코드 분석이다. 요지: 요청 계약이 여러 곳에 문자열로 흩어졌고 처리기 머리가 반복됐다. 선언 표와 일반 처리기로 옮기는 순서를 그 저장소 세션에 인계했다.)

## 5. 재발 방지 설계

### 5.1 고른 장치

| 장치 | 위치(초안) | 무엇을 하나 | 왜 효과가 있나 |
|---|---|---|---|
| **PostToolUse 리마인더 훅** | `.claude/archive/research/drafts/hooks/structure-reminder.py` (+ `test-structure-reminder.py` 32/32) | Write·Edit·MultiEdit·**Bash 쓰기** 직후 파일 줄 수를 세어 알린다. 경고 800, 강제 1,500, 세션 성장 +300(파일마다 세션당 한 번). 새 파일이면 평평한 폴더(15개 이상, 하위 폴더 2 이하)와 접두 가족(셋 이상)도 알린다. 막지 않는다 | 원인 1·2를 바로 친다. 길이를 "편집한 그 순간"에 보여 준다. 28ms. 성장 기록(§2.4)에 대어 보면 모든 사례에서 첫날 걸린다. Bash 를 같이 보는 이유는 감사 10 에서 수정의 대부분이 `sed -i`·python 이었기 때문이다 |
| **paths 조건부 rules** | `.claude/archive/research/drafts/style/rules/code-structure.md` (`**/*.{luau,lua,ts,tsx,go}`) | 다섯 줄. 길이 기준, 옮기기만 먼저, 접두 가족 → 폴더, 표로 둘 것, 생성물·복사 표시 | 원인 3. 숫자가 처음으로 생긴다. luau-core 와 겹치지 않게 언어 무관 파일로 따로 둔다 |
| **참고 문서** | `luau-style/references/structure.md` | 기준과 예외, 신호 일곱, 나누는 절차 여덟, 폴더 구성, 데이터와 코드의 결정 트리, 실제 저장소의 좋은 예·나쁜 예 | 원인 5·6·7. "어떻게"를 실제 커밋으로 보여 준다(quad `4ddb9c5a`, devplorer `cfeedd1`, table-sim meshes) |
| **측정기** | `luau-style/scripts/structure-scan.py` | 긴 파일, 평평한 폴더, 접두 가족, 리터럴 위주, 긴 문자열 분기, 반복 머리, 파일 사이 복사, 성장·분리 이력. 읽기 전용 | 원인 4·8. 사람과 감사자가 같은 숫자를 본다. 저장소 `.claude/structure.json` 을 읽는다 |
| **품질 감사자 구조 측정** | `.claude/research/drafts/agents/luau-quality-auditor.md` 먼저 할 일 4번 + "구조 측정" | 측정기를 돌리고, 강제 기준 초과(중간), 재성장(높음), 평평·가족, 분기·머리, 검사 없는 복사를 문항으로 올린다 | 원인 4. 리뷰 각도에 구조를 넣는다. 기존 readonly 가드 아래에서 돈다(확인함) |
| **D-13** | `.claude/base/decisions/D-13-file-structure.md` | 기준 값, 알림 대 차단, 폴더 대분류는 저장소 몫, stl `Arr` 예외 | 폴더 방식이 세 저장소에서 갈렸다(가족 접기 / 층 / 종류). 공통으로 강제하지 않는다 |

### 5.2 고르지 않은 것

- **별도 `/code-structure` 진단 스킬**
  - 결정적 측정은 스크립트 하나로 끝난다.
  - "어떻게 나눌지"는 저장소 맥락이 필요해서 품질 감사자(`/audit quality`)가 이미 맡는 몫이다.
  - harness-doctor 는 하네스(문서·설정) 범위를 지키는 편이 낫다. 코드 구조를 넣으면 진단 범위가 흐려진다.
  - Luau 가 아닌 저장소(VideoSync, vitrine)는 측정기를 직접 돌리면 된다. 사용 빈도가 생기면 그때 얇은 스킬로 감싼다.
- **차단(PreToolUse deny)**: 하던 버그 수정까지 막는다. 사용자는 분리를 사안마다 승인해 왔다(D-13 안 C).
- **memory**: 저장소마다 따로 쌓여서 교훈이 넘어가지 않았다(원인 3). 사용자 레벨 rules 가 맞다.
- **CLAUDE.md 한 줄**: paths 조건부 rules 와 겹친다. 상시 로드량만 는다.
- **Stop 훅으로 세션 끝 보고**: PostToolUse 알림과 겹치고, 끝에 알면 이미 늦다.

### 5.3 저장소별 기준 제안 (`.claude/structure.json` — 각 저장소 세션이 만든다)

| 저장소 | 값 | 예외(ignore)·메모 |
|---|---|---|
| quad | 기본(800/1,500/15) | 없음. devui `Manager`·`Decoration` 이 초과 → round16 품질 후보. 폴더는 "가족 접기만"을 rules 에 명문화 |
| stl-luau | 기본 | `src/Collections/Arr.luau` 를 예외로 둘지 D-13 문항. 이미 region 31개 |
| table-sim | 기본 | 없음. §4 순서 |
| devplorer | 기본 | 없음. 이미 "코드 배치" 규칙이 있으니 숫자만 더한다. `Output/View` 1,652 |
| tbox | 기본 | `schema/roblox/` 는 측정기·훅이 같은 종류 폴더로 보지 않는다 → `flat: 20` 이나 rules 에 "타입마다 파일 하나" 명시 |
| moonwave-luau | 기본 | `init.luau`, `example/ffi.luau` (단일 파일 라이브러리·예제) |
| VideoSync | 기본 | Go 패키지 폴더는 평평해도 된다 → `flat: 30`. `engine.ts` 2,500 |
| rbvm, mrow, vitrine | 기본 | 없음 |

### 5.4 반영 절차 (사용자 승인 뒤)

1. `.claude/archive/research/drafts/hooks/structure-reminder.py` → 정본 `home/.claude/hooks/`, `home/.claude/settings.json` 에 다음을 더한다.
   ```json
   "PostToolUse": [{ "matcher": "Write|Edit|MultiEdit|Bash",
     "hooks": [{ "type": "command", "command": "python3 -I /code/.claude/hooks/structure-reminder.py", "timeout": 10 }] }]
   ```
   `tools/home-sync.sh diff` 로 검토한 뒤 `apply` 한다.
2. `.claude/archive/research/drafts/style/rules/code-structure.md` → 사용자 rules. `luau-style` 의 `structure.md`·`scripts/` 는 스킬과 같이 옮긴다(PLAN §4-1 의 위치 결정을 따른다).
3. 저장소별 `.claude/structure.json` 과 table-sim 분리 순서는 각 저장소 세션에 인계한다. 다른 세션이 쉬고 있을 수 있으므로 여기서는 만들지 않았다.

### 5.5 검증한 것과 한계

- 훅 회귀 표 32건. 대상: 경고, 강제, 성장, 세션당 한 번, 테스트 두 배, 생성물 제외, 평평·가족(이미 폴더가 있으면 조용), `.md`·vendor 제외, worktree 포함, `structure.json` 덮어쓰기·ignore, 끄기 변수, 바이너리 `.ts`, 깨진 입력, Read 무시, Bash 의 sed·리다이렉트·python 쓰기, Bash 읽기와 프로젝트 밖 경로 무시.
- 실제 파일로 한 번 돌려 봤다(table-sim `<비공개>` → 강제 알림, 28ms).
- 측정기를 10개 저장소에 돌렸다(§2). 결과는 후보라서 사람이 걸렀다(§2.5).
- **한계**
  - Bash 인터프리터 명령은 명령에 적힌 소스 경로를 다 본다. `python3 scripts/sfx/build.py` 처럼 스크립트 자신이 길면 그 파일도 알린다(세션당 한 번).
  - Write 의 `tool_response.type` 이 없는 환경에서는 "세션 첫 Write = 새 파일"로 어림한다.
  - 접두 가족은 PascalCase 앞 단어만 본다. `*View` 같은 접미 가족은 측정기 보고에만 사람이 적었다.
  - 반복 머리·분기 탐지는 정규식 근사다. 같은 일을 다르게 쓴 복붙은 못 잡는다.

## 6. 인계 거리 (각 저장소 세션에 전할 것)

- [비공개 프로젝트 세부 생략]
- **quad**: devui `Window/Manager.luau` 3,352·`Decoration.luau` 1,676 분리를 round16 품질 후보로. `ColorModel`·`StoryKit`·`Quad.luau` 복사본의 같음 검사(`run.sh` 에 diff 한 줄). devui `src/` 38개의 묶음(`Popup*`, `Tree*`, `Virtual*`, `Color*`).
- **devplorer**: `Output/View.luau` 1,652, `Palette/init.luau` 1,379. `App/Explorer/` 19개를 하위 묶음으로 나눌지.
- **stl-luau**: `Arr.luau` 예외 여부(D-13 문항).
- **VideoSync**: `engine.ts` 2,500(상태 기계). Luau 밖이라 rules 만 적용된다.
