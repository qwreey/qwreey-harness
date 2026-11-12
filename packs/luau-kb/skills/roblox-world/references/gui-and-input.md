---
title: "GUI 레이아웃·자동 크기·입력 전달·톱바 인셋의 엔진 규칙"
description: "GUI 누름은 첫 GuiButton 에서 멈추고 Active 로는 관통을 못 막는다(투명 버튼 싱크), AutomaticSize 함정, AbsoluteSize·CanvasPosition 갱신 시점, TextBounds·UIScale 글자 폭, 톱바 인셋 좌표계, gameProcessed·포커스, SurfaceGui"
keywords:
  - "GUI 클릭 관통"
  - "Active 클릭 안 막음"
  - "투명 TextButton 싱크"
  - "InputSink"
  - "남은 누름"
  - "AutomaticSize UISizeConstraint"
  - "AbsoluteSize 갱신 시점"
  - "CanvasPosition 클램프"
  - "TextBounds 잘림"
  - "GetTextBoundsAsync"
  - "UIScale 글자 폭"
  - "CanvasGroup 클리핑 ZIndexBehavior"
  - "GetGuiInset 0"
  - "TopbarInset"
  - "GetMouseLocation 인셋"
  - "gameProcessed"
  - "CaptureFocus"
  - "SurfaceGui 축"
  - "플러그인 위젯 UserInputService"
kind: reference
category: roblox/gui
tags: [studio, correction]
last_verified: 2026-11-10
---
# gui-and-input — GUI 레이아웃·자동 크기·입력 전달·톱바 인셋의 엔진 규칙

## 이 파일이 답하는 질문
- Q1 GUI 클릭은 아래에 겹친 GUI 로 어떻게 전해지나? `Active = true` 는 무엇을 막나?
- Q2 `AutomaticSize` 가 크기를 틀리게 잡는 경우는? `UISizeConstraint` 와 같이 쓰면?
- Q3 `AbsoluteSize`·`GetGuiObjectsAtPosition` 은 언제 갱신되나? 붙인 직후 읽어도 되나?
- Q4 톱바 인셋과 좌표계는 어떻게 맞추나? `GetGuiInset` 이 0 을 줄 때는?
- Q5 키보드·포커스·`gameProcessed` 의 함정은?
- Q6 자식 순서, 클리핑, UIScale 아래 글자 폭은 어떻게 정해지나?
- Q7 SurfaceGui(3D 면 위 GUI)는 어느 축을 따르나?

## 목차
- §1 GUI 입력 전달 규칙 (Active, 첫 GuiButton, 남은 누름)
- §2 자동 크기(AutomaticSize) 함정
- §3 레이아웃 파생값의 갱신 시점
- §4 글자 크기·TextBounds·잘림
- §5 자식 순서·클리핑·ZIndex
- §6 톱바 인셋과 좌표계
- §7 키보드·포커스·gameProcessed
- §8 SurfaceGui 와 3D 면 위 GUI
- §9 플러그인 위젯 안의 입력
- 정정 / 미판정

공통 조건: 이 파일의 실측은 모두 원천 저장소가 Studio MCP 로 잰 것이다. 이 저장소가 다시 재지 않았으므로 `status: described` 다. 신호 모드는 원천마다 다르다(아래 각 절). GUI 동작은 rbvm·quad mock 어느 것도 흉내 내지 않는다.

---

## §1 GUI 입력 전달 규칙 (Active, 첫 GuiButton, 남은 누름)
status: described · last-confirmed: 원천 실측 Studio 클라이언트 0.742, Play(Client), 2026-10-08(quad) / 2026-10-20(devplorer) / 2026-10-12(table-sim), 모드 미기재 · 근거: `/code/Projects/quad/.claude/feedback/consumer-kits-studio-qa-2026-10-07.md:316,392-411`, `/code/Projects/devplorer/.claude/feedback/quad-upstream-2026-10-20.md:585-592`, `table-sim/<비공개>`, `/code/Projects/quad/.claude/audit/kit-studio-2026-10-15/REPORT.md:7-10`, 문서 `reference/engine/classes/GuiObject.md`(last_updated 2026-11-10) Active · 후보: Q-054, D-F01, T-33, T-32

- **규칙**: 누름은 포인터 아래의 GuiObject 들에 위(앞)에서부터 `InputBegan` 으로 전해지고, **처음 만난 GuiButton(TextButton·ImageButton)에서 멈춘다**(그 버튼 포함). TextBox 도 멈추는 쪽이다. Frame·ScrollingFrame·CanvasGroup 은 받고 아래로 넘긴다.
- **`Active = true` 는 GUI 대 GUI 관통을 막지 못한다.** 문서상 Active 는 "3D 공간(ClickDetector·DragDetector 를 단 모델)으로 가는 입력을 막는지"와 GuiButton 의 `Activated` 발화 여부를 정한다. Active Frame 아래의 TextButton 은 여전히 `Activated` 를 받는다. ZIndex 를 올려도 같다.
- **투명해도 버튼이면 클릭을 먹는다.** `Transparency = 1` 이어도 `Visible` 인 GuiButton 은 아래 클릭을 가져간다. 안 보이는 표시는 `Visible = false` 로 끈다.
- **처방**: 면(패널·카드) 뒤로 클릭이 새지 않게 하려면 면의 직계 자식으로 투명한 전체 크기 TextButton(`Text = ""`, `AutoButtonColor = false`, `Selectable = false`, 가장 낮은 ZIndex)을 깐다. 이 "싱크"를 두면 부모 Frame 은 자기 안 누름의 `InputBegan` 을 받지 못한다. 끌기 같은 훅은 싱크에 건다.
- **남은 누름(latent press)**: GuiButton 을 누르고 다른 곳에서 떼면 그 버튼은 "눌린" 상태를 들고 있다. 나중에 **다른 곳에서 시작한** 누름을 그 버튼 위에서 떼도 `Activated` 가 한 번 난다. 의도치 않은 클릭의 원인이 된다.
- 가림 판정: 가려진 GuiObject 에도 `MouseEnter` 가 온다. 맨 위가 누구인지는 `PlayerGui:GetGuiObjectsAtPosition(x, y)` 로 본다(§3 갱신 시점 주의).
- 한 줄: 조상이 `Visible=false` 였다 다시 `true` 가 돼도 마우스가 움직이지 않으면 `MouseLeave`/`MouseEnter` 가 오지 않는다. 1px 움직여야 온다. 선택된(게임패드 선택) GuiButton 에 Return 을 누르면 `Activated` 가 난다.
- mock 흉내: 해당 없음. rbvm·quad mock 은 입력 전달을 흉내 내지 않는다. Studio(`user_mouse_input`)가 필요하다.

## §2 자동 크기(AutomaticSize) 함정
status: described · last-confirmed: 원천 실측 Studio Play(Client), Deferred, 2026-10-13(quad, 킷 없이 손으로 만든 인스턴스), 2026-10-20·21(devplorer, 모드 미기재) · 근거: `/code/Projects/quad/.claude/feedback/consumer-kits-studio-qa-2026-10-07.md:530-543`, `/code/Projects/quad/.claude/audit/kit-studio-2026-10-13/REPORT.md:27-30`, `/code/Projects/devplorer/.claude/feedback/quad-upstream-2026-10-20.md:145-147,594-598`, `/code/Projects/devplorer/.claude/feedback/quad-upstream-2026-10-21.md:66-68` · 후보: Q-051, D-F03, D-F04

| 구성 | 결과 | 처방 |
|---|---|---|
| 자동 높이 부모가 `UIPadding` 과 `UIListLayout` 을 둘 다 갖고, 그 직계 자식이 자동 높이 `ScrollingFrame` | 부모 높이가 `min(세로 패딩 합, 스크롤 프레임 높이)` 만큼 모자란다(패딩 24/24 → 48 모자람) | 사이에 패딩 없는 자동 높이 Frame 을 끼우거나, 높이를 Offset 으로 직접 쓴다 |
| `AutomaticSize` + `UISizeConstraint.MaxSize` | MaxSize 를 무시한다(본문 1000, Max 400 → 1000). Frame·ScrollingFrame 모두 | "자동 높이 + 최대 높이 = 넘으면 스크롤"은 성립하지 않는다. `math.min(내용, 상한, 남은 공간)` 을 직접 계산해 Size 에 쓴다 |
| 줄바꿈 자동 높이 TextLabel | 높이가 확정된 가장 가까운 조상보다 커지지 못한다(자연 높이 1575 → 294 에서 잘림) | 자연 높이를 재려면 충분히 큰 고정 높이 투명 Frame 안에 두고 읽는다 |
| 높이 0 인 클립 조상 아래 | 후손의 `AbsoluteSize` 변경 신호가 오지 않는다 | 측정용 래퍼는 1px 바닥을 둔다(0 에서 시작하면 0 에 갇힌다) |
| 자동 크기 부모 안의 Scale 크기 자식(`UDim2.new(1,0,0,1)` 구분선 등) | 부모가 화면(쓸 수 있는 공간) 너비까지 늘어난다 | Offset 크기 + `UIFlexItem` Stretch |
| 자동 크기 호스트 아래 깊이 2 이상의 보이는 Scale **잎**(GuiObject 자식 없음) | 호스트 자신이 아니라 호스트가 쓸 수 있는 공간 기준으로 풀려 호스트를 민다. 자식이 하나라도 있거나 숨긴 잎이면 안 민다 | 장식용 Scale 잎을 자동 크기 호스트 안에 두지 않는다 |

- 마지막 행은 quad 2026-10-08 실측(클라이언트 0.742, `consumer-kits-studio-qa-2026-10-07.md` "리플 Scale 측정" 표)이다.
- mock 흉내: 해당 없음. 레이아웃 엔진은 어떤 mock 도 계산하지 않는다.

## §3 레이아웃 파생값의 갱신 시점
status: described · last-confirmed: 원천 실측 Studio Play(Client), **Immediate**(2026-10-15 quad 플레이스, 사용자 설정), Deferred(2026-10-13) · 근거: `/code/Projects/quad/.claude/audit/kit-studio-2026-10-15/REPORT.md:3,45`, `/code/Projects/quad/.claude/audit/kit-studio-2026-10-13/REPORT.md:49`, `table-sim/<비공개>` · 후보: Q-055, Q-050, T-32

- **붙인 직후 `AbsoluteSize` 를 읽으면** 레이아웃이 그 자리에서 계산되고 변경 신호도 같은 프레임에 왔다. 이 관측은 **Immediate 플레이스 한 구성**에서 나왔다. Deferred 에서 신호가 언제 오는지는 재지 않았다(M-07, 아래 미판정).
- `ScrollingFrame.CanvasPosition` 은 쓰는 즉시 클램프된다. 캔버스 300·창 100 에서 `(0,1000)` 을 쓰면 다음 줄 읽기가 이미 `(0,200)` 이다. 변경 콜백은 한 프레임 뒤 한 번, 값은 `(0,200)`(Deferred).
- 반대로 `TextBox.Text = "a\nb"`(MultiLine false)는 그대로 남았다. 엔진이 값을 고쳐 쓰는 속성과 아닌 속성이 섞여 있으므로 "쓴 값 = 읽은 값"을 가정하지 않는다.
- `GetGuiObjectsAtPosition` 결과는 **다음 렌더 뒤**에 갱신된다. Adornee 로 붙인 SurfaceGui 안의 것도 돌려준다. PlayerGui 가 없으면 쓸 수 없다. 같은 프레임 안의 동기 판정은 `AbsolutePosition`·`AbsoluteSize` 사각형을 직접 대조한다.
- mock 흉내: 해당 없음. mock 의 `AbsoluteSize` 는 상수이거나 없다.

## §4 글자 크기·TextBounds·잘림
status: described · last-confirmed: 원천 실측 Studio Play(Client), 2026-10-15(Immediate), 2026-10-20·21(devplorer, 모드 미기재) · 근거: `/code/Projects/quad/.claude/audit/kit-studio-2026-10-15/REPORT.md:48-49`, `/code/Projects/devplorer/.claude/feedback/quad-upstream-2026-10-21.md:37-38,73-75,97-105`, `/code/Projects/devplorer/.claude/feedback/quad-upstream-2026-10-20.md:479-482` · 후보: Q-052, D-F05, D-F06, D-F07, D-F08, D-F09

- **UIScale 아래 글자는 정수 글자 크기로 그려진다.** 14px 라벨의 abs/scale 이 배율 1.0 에서 288, 0.9 에서 282.2, 0.95 에서 290.5 였다. 폭이 배율에 비례하지 않는다. 배율 애니메이션 중 폭을 읽어 위치를 다시 놓으면 "Maximum event re-entrancy depth exceeded" 가 났다(한 번 열 때 7~30건). 폭은 배율 1 일 때만 읽는다.
- 잘린 상태의 `TextBounds` 는 **잘린 글의 폭**이다. 이 값으로 폭을 정하면 계속 줄어드는 순환이 생긴다. 원래 글 폭은 `TextService:GetTextBoundsAsync` 로 잰다.
- `TextBox` 는 기본으로 글을 자르지 않는다. 긴 글과 `PlaceholderText` 가 상자 밖으로 샌다 → `ClipsDescendants = true`.
- `RichText` 와 `TextTruncate = AtEnd` 는 함께 동작한다. "줄어드는 이름 + 고정 꼬리표"는 이름에 `AutomaticSize X` + `UIFlexItem` Shrink 를 준다.
- `ImageButton.Image` 는 단추 몸 전체를 채우고 `UIPadding` 은 자식에만 걸린다. 아이콘 여백은 안쪽 ImageLabel 로 만든다.
- `ScrollingFrame.VerticalScrollBarInset = ScrollBar` 면 스크롤바가 보일 때만 그 폭만큼 내용 폭이 준다.
- 아이콘 아틀라스는 축소 렌더 때 이웃 칸이 번진다. 칸 사이에 여백을 둔다(가치 낮음, Q-059).
- mock 흉내: 해당 없음.

## §5 자식 순서·클리핑·ZIndex
status: described · last-confirmed: 원천 실측 Studio Play(Client), Deferred, 2026-10-13 (깜빡임은 서술) · 근거: `/code/Projects/quad/.claude/audit/kit-studio-2026-10-13/REPORT.md:49-56`, `/code/Projects/quad/docs/how-to/03-long-lists-and-windowing.md:229` · 후보: Q-049, Q-053

- `GetChildren` 은 이 실측에서 삽입 순이었다. 문서 보장은 아니다(roblox-engine `instance-api.md` §1, R-38). 화면 순서는 물리 순서가 아니라 `UIListLayout.SortOrder`/`LayoutOrder` 와 `ZIndex` 가 정한다.
- 떼었다 다시 붙여 순서를 바꾸면 `AncestryChanged`·`ChildAdded` 가 다시 발화하고 레이아웃이 깜빡일 수 있다(서술). 순서만 바꿀 때는 `LayoutOrder` 를 쓴다.
- `ClipsDescendants = true` Frame 은 창 밖으로 나간 `UIStroke` 를 경계에서 자른다.
- `CanvasGroup` 의 클리핑과 `GroupTransparency` 적용은 `ScreenGui.ZIndexBehavior` 에 달렸다. 코드로 만든 ScreenGui 기본값(Global)에서는 자르지 않았고 Sibling 에서는 잘랐다. 원천이 같은 날 사용자 확인으로 정정한 결과다.
- mock 흉내: quad mock 의 children 은 삽입 순 배열이라 순서는 맞지만, 렌더 순서·클리핑은 없다.

## §6 톱바 인셋과 좌표계
status: described · last-confirmed: 원천 실측 Studio 0.742 데스크톱 Play(Client), 뷰포트 1325 폭, 2026-10-12·13. 폰·태블릿 미측정. 수치는 기기·버전 의존 · 근거: `table-sim/<비공개>`, `table-sim/<비공개>`, `/code/Projects/quad/.claude/audit/kit-studio-2026-10-13/REPORT.md:39-42`, `/code/Projects/devplorer/.claude/feedback/quad-upstream-2026-10-20.md:463-464` · 후보: T-36, T-37, T-38, T-39, Q-058

- 새 톱바: 높이 58. `GuiService.TopbarInset` 은 Min (208, 0), 크기 1117×58 이었다. `GetGuiInset()` 의 위쪽 값도 58. 수치를 하드코딩하지 않는다.
- `ScreenGui` 기본은 `ScreenInsets = CoreUISafeInsets`, `IgnoreGuiInset = false` 다. 이때 화면은 톱바 아래에서 시작한다(1325×717 화면에서 `AbsoluteSize` 1325×659). `ScreenInsets = TopbarSafeInsets` 만 주면 코어 버튼에서 8 떨어진 자리에 놓인다.
- **화면을 만드는 순간 `GetGuiInset()` 은 0 을 줄 수 있다.** `TopbarInset` 변경 신호에서 다시 읽는다. TopbarSafeInsets 안의 `AbsolutePosition` 은 처음 몇 프레임 튄다.
- **좌표계가 둘이다.** `AbsolutePosition` 과 `InputObject.Position` 은 `IgnoreGuiInset = true` 화면에서도 톱바 아래를 원점으로 잰다. `UserInputService:GetMouseLocation()` 은 인셋을 포함한 좌표다. 맞추려면 `GetMouseLocation() - GetGuiInset()`.
- 바꿀 수 없는 것(서술, DevForum 요약): `SetCoreGuiEnabled` 로 톱바를 끌 수 없다. Roblox 메뉴·신고 버튼의 위치와 표시는 못 바꾼다. `ChatWindowConfiguration` 은 정렬 열거형만 준다.
- mock 흉내: 해당 없음.

## §7 키보드·포커스·gameProcessed
status: described · last-confirmed: 원천 실측 Studio 0.742 Play(Client), 2026-10-12(table-sim, MCP 자동 입력), 2026-10-20(devplorer), 모드 미기재. D-F11 은 권한자 계정 기준 · 근거: `table-sim/<비공개>`, `/code/Projects/devplorer/.claude/feedback/quad-upstream-2026-10-20.md:72-78,116-120,160-163,404,484-490`, `/code/Projects/devplorer/.claude/review/2026-10-20-client-palette-copy.md:42-44,105-107,149` · 후보: T-34, T-35, D-F10, D-F11, D-F12, D-F13, D-F14, D-F15

| 상황 | 엔진 동작 | 처방 |
|---|---|---|
| DragDetector 로 끄는 중의 키보드 | `InputBegan` 이 `gameProcessed = true` 로 온다 | `if processed then return end` 만 쓰면 끄는 중 키를 놓친다. 그 키는 따로 본다 |
| TextBox 포커스 중 | `InputBegan` 의 `gameProcessed == true` | 단축키는 포커스 중 무시된다는 전제로 짠다 |
| Escape | Roblox 메뉴를 열고(`GuiService.MenuIsOpen`) 그동안 클릭이 먹통이다. ContextActionService Sink 로 못 막는다. `SetMenuIsOpen` 은 RobloxScript 권한 | Escape 를 게임 기능에 쓰지 않는다 |
| `/` 키 | `ChatInputBarConfiguration.KeyboardKeyCode` 를 바꿔도 채팅 포커스를 가져간다 | 단축키로 쓰지 않는다 |
| Tab | CoreGui 에 묶여 있다. TextBox 도 Tab 을 가로챌 수 없고 `\t` 가 들어온 뒤에야 안다 | 들어오기 전 상태로 되돌린다 |
| Shift+P | 내장 개발자 Freecam. 누르면 모든 ScreenGui 가 숨는다(권한자 계정) | 이 조합을 피한다 |
| 다른 TextBox 에 포커스가 있을 때 포커스 없는 TextBox 의 `CursorPosition` 쓰기 | 포커스가 그 상자로 넘어간다 | 커서 위치는 포커스를 가진 상자에만 쓴다 |
| 생성 직후·부모 붙기 전 `CaptureFocus()` | 먹지 않는다 | `task.defer` 뒤 `Parent and Visible` 확인 후 부른다 |
| 클립보드 | 게임 스크립트용 API 가 없다 | 읽기 전용 TextBox 에 `CaptureFocus` + 전체 선택 → 사용자가 Ctrl+C |

- mock 흉내: 해당 없음. `gameProcessed` 값과 CoreGui 가로채기는 Studio·실기기에서만 보인다.

## §8 SurfaceGui 와 3D 면 위 GUI
status: described · last-confirmed: 원천 실측 Studio 0.742 Play(Client), 2026-10-12~13. 터치 미확인 · 근거: `table-sim/<비공개>`, `table-sim/<비공개>`, `table-sim/<비공개>` · 후보: T-30, T-31

- 파트 **윗면** SurfaceGui 의 가로축은 파트의 **긴 변**을 따른다(정사각형이면 X, 27×30 판이면 Z). 윗면 글자가 바로 서려면 +90° 돌려야 할 수 있다. 크기를 바꾸면 축이 바뀔 수 있으므로 정사각이 아닌 판은 실측으로 확인한다.
- 카메라 앞에 놓는 로컬 파트 HUD: SurfaceGui 를 `PlayerGui` 밑에 두고 `Adornee` 로 파트에 연결한다. `LightInfluence = 0` 이면 2D 만큼 또렷하다. 버튼 `Activated` 가 불린다. `RenderPriority.Camera + 5` 에서 파트 6개를 매 프레임 배치하는 데 16µs 였다(기계 의존).
- mock 흉내: 해당 없음.

## §9 플러그인 위젯 안의 입력
status: described · last-confirmed: 원천 실측 2026-10-08(Luau CLI·Lune·Studio 재현, 버전 미기재) · 근거: `/code/Projects/quad/.claude/feedback/consumer-kits-studio-qa-2026-10-07.md:512-514` · 후보: Q-056

- 플러그인 위젯(UI Labs 등의 미리보기) 안에서는 `UserInputService` 가 입력을 받지 못한다. `IsMouseButtonPressed` 는 늘 false, `InputChanged`/`InputEnded` 가 오지 않는다. GuiObject 의 `InputBegan` 만 온다. "위젯에서 드래그가 시작만 되고 따라오지 않는다"의 원인이다.
- 처방: 입력 서비스를 주입받게 해 두고, 위젯에서는 GuiObject 이벤트로 버튼 상태를 세는 대체 구현을 넘긴다. 모듈 최상위에서 `GetService("UserInputService")` 를 잡아 두면 교체할 수 없다.
- 같은 사례의 부수 함정(`pcall(getfenv, 1)` 이 호출자 환경이 아니라 실행 중 스레드 전역을 준다)은 순수 Luau 사실이라 luau-style 쪽 몫이다(Q-119).
- mock 흉내: 해당 없음.

---

## 정정
| 원천 경로:줄 | 틀린 서술 | 맞는 것 | 근거 |
|---|---|---|---|
| `/code/Projects/quad/.claude/feedback/consumer-kits-studio-qa-2026-10-07.md:285` | 모달 면에 `Active = true` 를 주면 아래 스크림(TextButton)으로 가는 빈 곳 누름을 막는다 | 막지 못한다. Active 는 3D 입력만 막는다. GuiButton 싱크가 필요하다(§1) | 같은 파일 `:316`, `:392-411` 재측(2026-10-08), GuiObject.md Active, devplorer D-F01 |
| quad 커밋 `9bb7bfa3` 메시지 | "카드 Active = true 로 스크림 관통을 고침" | 그 수정은 효과가 없었다(같은 파일 `:316` "9bb7bfa3 의 카드 Active 가 듣지 않은 이유") | 위와 같음 |
| `/code/Projects/quad/.claude/base/onchange-plan.md:50-52` (M-07) | 붙인 직후 `AbsoluteSize` 는 계산이 보장되지 않는다 | Immediate 한 구성에서는 그 자리에서 계산됐다. Deferred 는 미측정이라 "조건부"로만 고친다 | `/code/Projects/quad/.claude/audit/kit-studio-2026-10-15/REPORT.md:45` |

claude-doctor .claude/audit/09 §6 #7("Active Frame 이 클릭을 막는가")은 조건 차이가 아니었다. quad 의 초기 서술이 틀렸고, quad 자신의 재측·devplorer·table-sim·문서가 모두 §1 규칙과 맞는다. table-sim T-33 의 "투명 표시"는 카드 **버튼**이었으므로 같은 규칙(첫 GuiButton 에서 멈춤)으로 설명된다.

## 미판정
**InputSink 속성.** 문서(GuiObject.md, last_updated 2026-11-10)는 `GuiObject.InputSink`(None/Activate/All)가 뒤의 객체로 가는 입력을 막는다고 쓴다(GuiButton 기본 Activate). quad 실측(2026-10-08, 클라이언트 0.742)은 Frame 에 세 값을 다 줘도 아래 스크림 `Activated` 를 막지 못했다. 기능 플래그가 그때 꺼져 있었을 수 있다. 재현 절차:
1. 빈 플레이스 Play(Client)에서 PlayerGui 에 ScreenGui 를 만들고, 전체 크기 TextButton "Under"(`Activated` 횟수를 `_G` 에 센다) 위에 Frame "Over"(ZIndex 2)를 둔다.
2. Over 의 `InputSink` 를 None, Activate, All 로 바꿔 가며 Over 가운데를 `user_mouse_input` 으로 클릭한다.
3. 다음 `execute_luau` 호출에서 Under 의 `Activated` 횟수를 읽는다. 대조군으로 Over 대신 TextButton 을 둔 경우(0 이어야 함)를 같이 잰다.
4. Studio 버전, 신호 모드, 날짜를 함께 이 절에 적는다. Over 가 3D 클릭(ClickDetector 파트)을 막는지도 같은 방법으로 본다.

**붙인 직후 `AbsoluteSize` 의 Deferred 동작(M-07).** Immediate 에서만 쟀다. Deferred 플레이스에서 `Parent` 대입 다음 줄에 `AbsoluteSize` 를 읽고, 같은 줄기에서 `GetPropertyChangedSignal("AbsoluteSize")` 핸들러가 돌았는지 기록한 뒤 `task.wait()` 뒤에 다시 본다.
