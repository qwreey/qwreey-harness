# structure.md — 파일 길이, 폴더 묶음, 데이터와 코드 나누기

목차
- §1 왜 이 문서가 있나 (사용자가 직접 지적한 다섯 사례)
- §2 기준 수치와 예외
- §3 언제 나눌지 알아차리는 신호
- §4 나누는 절차
- §5 폴더 구성
- §6 데이터와 코드 나누기
- §7 실제 저장소의 좋은 예와 나쁜 예
- §8 측정 도구

이 파일에서 답하는 질문
- 이 파일에 기능을 더 붙여도 되나, 먼저 나눠야 하나?
- 큰 파일을 어떻게 나누면 동작을 안 바꾸고 안전한가?
- 새 모듈을 같은 폴더에 둘까, 폴더를 만들까?
- 요청 목록·비용·세트 배치 같은 것을 코드로 쓸까, 표로 쓸까, 생성할까?

필수 한 줄 규칙은 사용자 레벨 rules `code-structure.md` 에 있다. 저장소 `.claude/rules/`·`conventions.md`·`.claude/structure.json` 이 다르게 정하면 저장소가 이긴다. 기준 값의 합의 상태는 `claude-doctor/decisions/D-13-file-structure.md`.

---

## §1 왜 이 문서가 있나

status: [기록] claude-doctor `.claude/audit/12-code-structure.md` 사례 표. 모두 사용자가 직접 코드를 열어 보고 지적했다. 모델이 먼저 나누자고 한 경우는 table-sim 한 번뿐이다.

| 언제 | 저장소 | 지적 (요지) | 그때 크기 |
|---|---|---|---|
| 2026-09-07 | quad | "슬롯 파일 너무 길어서 … Slot/... 로 쪼갤 수 없는지", "src 안에 뭐가 너무 많은데" | `Slot.luau` 1,194줄, `src/` 평평한 파일 25개 |
| 2026-10-13 | stl-luau | "Adt 보고싶은데 Trait.luau 봐야하는건 조금 문제. 폴더로 묶어서" | 트레이트 시스템과 구현이 한 파일 |
| 2026-11-04 | devplorer | "server init 파일이 4000줄이나 된다는건 좀 다시 생각해볼 필요가", "폴더로 잘 묶을건 묶어주는것도 중요해" | `Server/init.luau` 4,199줄, `App/` 평평한 항목 60개 |
| 2026-11-10 | quad | quad-types "접힘이 하나도 없다" | `quad-types/src/init.luau` 970줄, region 0 |
| 2026-11-10 | table-sim | "net관련 파일이 하드코딩으로 몇천줄" (못 고침) | 서버 모듈 둘이 3,501줄·4,884줄 |

공통 원인은 둘이다.
- **한 파일에 계속 덧붙인다.** 요청 처리기를 더할 때 처리기 표가 있는 파일에 붙인다. devplorer `Server/init.luau` 는 사흘에 692 → 4,101줄이 됐다. Edit 도구는 조각만 보여 줘서 모델은 파일 전체 길이를 잘 보지 못한다.
- **새 모듈을 부르는 쪽 옆에 둔다.** 폴더 대신 이름 접두로 묶는다(`ExplorerActions`, `ExplorerControl`, `BookmarkMenu`).

## §2 기준 수치와 예외

status: 제안(D-13). 수치는 10개 저장소 실측 분포에서 잡았다. 비테스트 Luau 파일의 p90 은 quad 443, devplorer 594, table-sim 834 줄이다. 사용자가 "너무 길다"고 한 가장 작은 파일은 1,194줄이었다.

| 대상 | 경고 (분리 후보를 적는다) | 강제 (덧붙이기 전에 사용자에게 분리안을 묻는다) |
|---|---|---|
| 소스 파일 (`.luau` `.lua` `.ts` `.go` …) | 800줄 | 1,500줄 |
| 테스트·스펙 파일 | 1,600줄 | 3,000줄 |
| 한 세션 동안 한 파일이 늘어난 양 | +300줄 (그리고 경고 기준 이상) | — |
| 한 폴더에 바로 든 소스 파일 | 15개 이상이고 하위 폴더 2개 이하 → 묶음 제안 | — |
| 같은 PascalCase 접두를 가진 형제 파일 | 3개 이상 → `접두/` 폴더 후보 | — |

**제외하는 것**
- **생성물**: 머리 6줄 안에 생성기 경로와 "손으로 고치지 않는다" 같은 표시가 있는 파일. 예: table-sim 의 생성 데이터 파일.
- **순수 데이터 모듈**: 문자열 표나 아이콘 표처럼 로직이 없는 모듈. 예: table-sim `<비공개>`(리터럴 90%), devplorer `Shared/Explorer/ClassIcons.luau`. 길이보다 "로직이 섞였나"를 본다.
- **같은 종류만 모인 폴더**: `tests/`, `stories/`, tbox `schema/roblox/`(타입마다 한 파일). 평평한 것이 정상이다.
- 저장소가 `.claude/structure.json` 의 `ignore` 에 사유와 함께 올린 파일.

**강제 기준은 차단이 아니다.** 하던 수정은 마무리한다. 그 파일에 새 기능을 더하기 전에 분리안을 낸다.

## §3 언제 나눌지 알아차리는 신호

1. **줄 수**가 §2 를 넘는다. 훅 `structure-reminder` 가 편집 직후에 알린다.
2. **한 세션 성장**: 같은 파일에 기능 둘째를 붙이고 있다.
3. **머리 주석이 "그리고"로 늘어난다.** table-sim `<비공개>` 머리에는 입구, 권한, 로비 상태 보내기가 한 문단에 섞여 있다.
4. [비공개 프로젝트 세부 생략]
5. [비공개 프로젝트 세부 생략]
6. **클로저가 상태를 같이 쥔다.** table-sim `<비공개>` 는 `enter`·`hook` 클로저가 `lifted`·`carrying`·`dragging` 을 같이 쥐어서 옮기기만으로는 나눌 수 없었다. 이 신호가 보이면 **더 커지기 전에** 나눈다. 늦을수록 "옮기기"가 "다시 짜기"가 된다.
7. [비공개 프로젝트 세부 생략]

## §4 나누는 절차

status: [기록] quad `archive/surveys/2026-09-07-source-layout-plan.md`, devplorer `.claude/audit/2026-11-04-code-layout.md`, table-sim `todos.md:111-121`, devplorer memory `feedback-audit-after-move`.

1. **묶음 지도를 먼저 만든다.** 함수 목록을 책임별로 나누고, 묶음 사이 호출 방향을 적는다. 강하게 이어진 묶음은 한 파일에 남긴다. quad Slot 분할 계획은 여섯 묶음 가운데 다섯이 서로 재귀하는 것을 먼저 확인했다.
2. **"옮기기만" 커밋과 "고치기" 커밋을 나눈다.** 옮기기 커밋은 함수 본문을 바꾸지 않는다. 커밋 메시지에 `옮기기만`·`순수 이동`이라고 쓴다(devplorer `cfeedd1`, table-sim `6c55ec2`, stl `221cec9`).
3. **`X.luau` → `X/init.luau` 접기는 공짜다.** `init.luau` 안에서 `./` 는 부모 폴더, `@self/` 는 자기 폴더라서 바깥 `require("./X")` 가 그대로 유효하다. `X.luau` 와 `X/` 를 동시에 두지 않는다(modules§3).
4. [비공개 프로젝트 세부 생략]
5. **클로저에 얽힌 상태는 먼저 상태 객체로 꺼낸다.** 그다음에 옮긴다. 이 단계를 건너뛰면 분리가 멈춘다(table-sim 큰 화면 모듈).
6. **문서의 옛 경로를 고친다.** `.claude/` 문서가 `파일:줄` 을 인용하므로 옮기면 조용히 낡는다. 옛 경로 → 새 경로 대조표를 남긴다(devplorer `.claude/audit/2026-11-04-code-layout.md`). quad 는 `doc-check.py` 가 `.luau` 경로를 검사하게 넓혔다.
7. **옮긴 뒤 이음매 감사를 따로 돌린다.** 보안 리뷰와 줄 대조만으로 끝내지 않는다. 넘긴 상태가 값으로 묶였는지, 정리가 빠졌는지, 비동기 흐름이 바뀌었는지 본다. devplorer 는 이 감사에서 원래 있던 버그 여럿을 찾았다.
8. **층 규칙은 `require` 를 grep 해서 확인한 뒤에 적는다.** devplorer 는 처음 적은 층 규칙이 실제 코드와 달라 거짓이었다(modules§4).

## §5 폴더 구성

- **기능마다 폴더를 두고, 입구는 `init.luau` 다.** 창이 있는 기능은 창 본체가 `init.luau` 다(devplorer `App/Inspect/init.luau`).
- **접두 가족은 폴더로 접는다.** 형제 파일 셋 이상이 같은 접두를 쓰면 폴더 후보다. 예: `Ref` + `PreRef` + `PostRef` → `Ref/`, devplorer `ExplorerActions`·`ExplorerControl` → `Explorer/Actions`·`Explorer/Control`.
- **폴더가 말해 주는 접두는 파일 이름에서 뺀다**(devplorer `App/Inspect/Remotes`). 부르는 쪽의 지역 이름은 `InspectRemotes` 처럼 알아보기 쉽게 써도 된다. 여러 곳에서 같은 이름으로 찾는 공용 모듈은 이름을 유지한다(devplorer `Shared`).
- **혼자 서는 작은 모듈은 폴더를 만들지 않는다**(devplorer `App/Link`).
- **대분류(층·종류) 폴더를 둘지는 저장소가 정한다.**
  - quad `quad-base/src` 는 "패밀리 접기만, 대분류 안 함"(사용자 2026-09-07)이다.
  - devplorer 서버는 층(`Core → Policy → Handlers → Window`)으로 나눴다.
  - stl 은 종류(`Collections/`, `Algorithms/`, `Traits/`)로 나눴다.
  - 같은 저장소 안에서는 한 방식만 쓴다(D-13).
- **테스트는 평평해도 된다.** devplorer `tests/core/<이름>.spec.luau` 처럼 소스 이름을 따라가면 찾기 쉽다.
- **긴 파일을 당장 못 나누면 region 으로 접는다.** `--#region 이름` / `--#endregion 이름` 은 VSCode 가 접는다(quality§2). 타입 모음처럼 한 파일이어야 하는 것에 맞다(quad `quad-types/src/init.luau`, `0c2eef35`). 로직이 섞인 파일에서는 나누기를 대신하지 못한다.

## §6 데이터와 코드 나누기

"항목마다 같은 모양"인 것이 코드에 펼쳐져 있으면 하드코딩이다. 판단 순서는 이렇다.

```
항목마다 같은 모양인가? (요청 이름·인자·비용·권한, 세트 배치, 색, 쿨다운)
├─ 아니오 → 코드로 둔다
└─ 예 → 값이 손으로 바뀌나, 툴이 만드나?
    ├─ 툴이 만든다(메시, 정의 덤프, 아틀라스) → 생성 데이터 파일 (a)
    └─ 손으로 바뀐다 → 처리 모양이 항목마다 같은가?
        ├─ 같다 → 선언 표 + 일반 처리기 (b)
        └─ 조금씩 다르다 → 표에 "다른 점"만 두고, 정말 특수한 것만 함수로 (c)
```

**(a) 생성 데이터 파일** — 좋은 예: table-sim 의 생성 데이터 파일.
- 머리에 `-- 만든 것: scripts/meshgen.py ← Prop.json … 손으로 고치지 않는다` 를 단다.
- 로직 파일과 떨어진 `assets/` 에 둔다. 저폴리 작업 뒤 9,911 → 2,190줄로 줄었는데 로직은 그대로였다.
- 생성기와 원본 경로를 머리에 적어 다시 만들 수 있게 한다.

**(b) 선언 표 + 일반 처리기** — 나쁜 예: table-sim `<비공개>`.
- 요청 이름이 다섯 곳에 문자열로 흩어져 있다: 클라이언트 `Bridge.send(name: string, ...: any)` 호출 약 110곳(이름 약 70개), 처리기 73개, `COSTS` 42개, `ACTIONS`, `MANY`.
- 인자 검사는 처리기마다 `type(x) ~= "number"` 로 손으로 쓴다(92곳).
- [비공개 프로젝트 세부 생략]
- 고칠 모양: `shared/Requests.luau` 한 표에 이름·인자 모양·비용·권한을 둔다. 서버 입구 하나가 그 표로 검사·청구·권한을 처리하고, 처리기는 검사가 끝난 값만 받는다.
  ```lua
  -- shared/Requests.luau (모양 예시)
  return table.freeze({
      bundleOrder = { args = { Arg.Id, Arg.Int }, cost = 1, perm = "place" },
      setDie      = { args = { Arg.Id, Arg.Sides }, cost = 1, perm = "place", unlocked = 1 },
  })
  ```
- 표가 클라이언트와 서버 사이 계약 문서가 된다. 엔진 없이 `luau` 스펙으로 돈다.

*[비공개 프로젝트 세부 생략]
- 체스·장기·윷·볼링 세트 배치가 `CFrame.new(16 + (i - 2.5) * 1.3, 3, 0)` 같은 숫자로 코드에 박혀 있다.
- 갈래마다 같은 일을 반복한다: 개수 한도 검사, `useBuiltin`, 위치 계산, `spawnPiece(session, def, at, by, nil, true, true)` 의 불리언 나열.
- 고칠 모양: `core/Sets.luau` 에 `{ def, count, at = {x, y, z}, step, bundle = "line" }` 꼴의 레시피를 둔다. `spawnSet` 하나가 그것을 읽는다. 특수한 것(장기판의 편 돌리기)만 레시피에 함수 칸을 둔다.

**코드 생성은 마지막 수단이다.** 같은 언어·같은 저장소 안의 계약이면 공유 표 하나로 충분하다. 생성은 빌드 단계와 생성물 갱신 부담을 더한다. 생성을 고르는 때는 다음 중 하나일 때다.
- 원천이 코드 밖에 있다(Blender, API 덤프).
- 표에서 **타입**을 만들어야 하는데 타입 함수로는 비용이 너무 크다(quad 생성 D, D-04).

**그 밖의 모양**
- [비공개 프로젝트 세부 생략]
- **다른 패키지에서 복사한 파일**은 머리에 원본 경로를 적고, 같은지 보는 검사를 둔다. quad devui `ColorModel.luau` 는 material 에서 복사했다(의존을 피하려고). 머리에 "고치면 양쪽 다"라고 적었지만 검사가 없다. vitrine `recover.py` 두 벌은 embed 때문에 일부러 둔 것이다.

## §7 실제 저장소의 좋은 예와 나쁜 예

| 구분 | 예 | 무엇을 배우나 |
|---|---|---|
| 좋음 | devplorer `cfeedd1` — `Server/init.luau` 4,199 → 242줄, `Core/ Policy/ Handlers/ Window/` | 옮기기만, 층 규칙, 옛 경로 대조표, 옮긴 뒤 감사 |
| 좋음 | quad `4ddb9c5a` — `Slot/{init,Owner,Elements,Raw,Tree,List}`, `Ref/{init,PreRef,PostRef}` | 접기 공짜 규칙, 늦은 조회로 재귀 끊기, 문서 경로 검사 |
| 좋음 | stl `221cec9`·`4e07d1a` — `Collections/`, `Algorithms/`, `Traits/` 한 파일씩 | 시스템과 구현을 나눔(Trait.luau 는 시스템만) |
| [비공개 프로젝트 세부 생략]
| 좋음 | table-sim 의 생성 데이터 폴더 | 생성 데이터 분리와 머리 표시 |
| 나쁨 | table-sim 서버 요청 모듈 3,501줄 | 요청 계약이 문자열과 손 검사로 흩어짐(§6 b) |
| 나쁨 | table-sim 서버 객체 모듈 4,884줄, 함수 134개 | 여러 책임이 한 모듈 |
| 나쁨 | table-sim `<비공개>` 1,457 → 3,223줄 | 나눈 뒤 남은 덩어리가 다시 자람(§3 의 7) |
| 나쁨 | quad devui `Window/Manager.luau` 273 → 3,352줄 (이틀) | 도킹 단계마다 같은 파일에 덧붙임 |
| 나쁨 | devplorer 옛 `App/` 평평한 항목 60개 | 폴더 대신 이름 접두로 묶음 |

## §8 측정 도구

```bash
python3 -I ~/.claude/skills/luau-style/scripts/structure-scan.py <저장소> [--history 5] [--json]
```
- 긴 파일, 평평한 폴더, 접두 가족, 리터럴 위주 파일, 긴 문자열 분기, 반복되는 머리, 파일 사이 복사, 성장 이력을 낸다. 성장 이력은 `git log --numstat --follow` 를 읽기만 한다.
- 결과는 후보다. 데이터 모듈, 의도한 복사, 저장소가 정한 예외는 사람이 걸러 낸다.
