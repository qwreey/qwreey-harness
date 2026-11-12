---
name: roblox-world
description: >-
  Engine rules for Roblox GUI and the 3D world: GUI input delivery (click-through, gameProcessed, focus),
  AutomaticSize/AbsoluteSize/TextBounds update timing, ZIndex and clipping, topbar inset, SurfaceGui, DragDetector,
  physics (tunneling, overlap), welds, characters and Humanoid, camera, EditableMesh and asset loading. Use when GUI
  clicks, layout or text size misbehave, or when dealing with input and focus, physics, characters or camera. 트리거: GUI
  클릭 관통, AutomaticSize, 물리 뚫림.
---
# roblox-world

"화면(GUI)과 3D 월드에서 엔진은 실제로 어떻게 동작하나"를 다룬다. 원천은 형제 저장소의 Studio 실측이다(대부분 `status: described`). 렌더링·레이아웃·물리는 mock 으로 재현할 수 없으므로 확인은 Studio 로 한다(luau-roblox `env-dependence.md` §2). 시그널·Instance 수명·task 는 roblox-engine, 원격·복제는 roblox-net 이다.

## 결정 트리
1. GUI 인가 3D 인가? GUI 면 `references/gui-and-input.md`, 3D(파트·물리·캐릭터·카메라·메시)면 `references/world-and-physics.md`.
2. 값이 "아직 0"이거나 한 프레임 늦나? 레이아웃 파생값(`AbsoluteSize`, `TextBounds`)과 엔진이 바꾼 속성은 갱신 시점이 따로 있다 → `gui-and-input.md` §3, `world-and-physics.md` §3.
3. 클릭·키 입력이 엉뚱한 곳으로 가나? → `gui-and-input.md` §1, §7.
4. 속성의 정확한 뜻·기본값은 roblox-docs `api <Class>.<Property>` 로 확인한다.

## 라우팅
| 상황 / 질문 | 읽을 곳 |
|---|---|
| GUI 클릭이 뒤로 샌다, `Active` 가 안 막는다, 첫 GuiButton | `references/gui-and-input.md` §1 |
| AutomaticSize 함정, `AbsoluteSize`·레이아웃 파생값 갱신 시점 | `references/gui-and-input.md` §2–3 |
| 글자 크기·`TextBounds`·잘림 | `references/gui-and-input.md` §4 |
| 자식 순서·클리핑·ZIndex, 톱바 인셋과 좌표계 | `references/gui-and-input.md` §5–6 |
| 키보드·포커스·`gameProcessed`, SurfaceGui, 플러그인 위젯 입력 | `references/gui-and-input.md` §7–9 |
| DragDetector | `references/world-and-physics.md` §1 |
| 파트가 뚫고 지나간다, 겹침 튕김, 엔진이 바꾼 값과 변경 신호 | `references/world-and-physics.md` §2–3 |
| 용접·제약·Clone, 캐릭터·Humanoid, 카메라 | `references/world-and-physics.md` §4–6 |
| MeshPart·EditableMesh·EditableImage, 에셋 로드·프라이버시, Highlight | `references/world-and-physics.md` §7–9 |
| Instance 생성·속성 대입 비용 기준치 | roblox-engine `perf.md` §2 |
| 네트워크 소유권, 스트리밍으로 안 보이는 파트 | roblox-net `remotes-and-replication.md` §9–10 |

## 자주 밟는 함정 (요약)
- `Active = true` 는 GUI 대 GUI 클릭 관통을 막지 못한다. 투명한 TextButton 싱크를 깐다.
- 엔진이 값을 고쳐 쓰는 속성(`CanvasPosition` 클램프)과 아닌 속성이 섞여 있다. "쓴 값 = 읽은 값"을 가정하지 않는다.
- 좌표계가 둘이다. `AbsolutePosition`·`InputObject.Position` 은 톱바 아래가 원점, `GetMouseLocation()` 은 인셋 포함이다. 화면을 만드는 순간 `GetGuiInset()` 은 0 일 수 있다.
- DragDetector 의 `AddConstraintFunction` 은 월드 좌표가 아니라 끌기 시작점 기준 이동량을 주고받는다.
- 물리에 구름 저항이 없다. 누운 원기둥·공은 스스로 멈추지 않고, 빠르고 얇은 물체는 얇은 파트를 뚫는다.
