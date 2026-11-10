# world-and-physics — DragDetector, 물리, 캐릭터, 용접, 카메라, 런타임 에셋의 엔진 규칙

## 이 파일이 답하는 질문
- Q1 DragDetector 의 제약 함수는 어떤 좌표를 주고받나? 왜 먼 물체·자식 파트를 못 끄나?
- Q2 Roblox 물리가 "스스로 안 멈추는" 경우와 얇은 물체가 뚫리는 경우는?
- Q3 앉은 캐릭터를 옮기거나 키울 때, 캐릭터를 장식 인형으로 쓸 때 무엇을 조심하나?
- Q4 WeldConstraint 와 Weld, `CFrame` 과 `Position` 쓰기는 무엇이 다른가? Clone 하면 용접은?
- Q5 런타임에 메시·이미지를 불러올 때(MeshId, EditableMesh, 프라이버시) 무엇이 막히나?
- Q6 엔진이 움직인 값(물리 낙하)에 변경 신호가 오나?

## 목차
- §1 DragDetector
- §2 물리: 저항 없음, 뚫림, 겹침 튕김
- §3 엔진이 바꾼 값과 변경 신호
- §4 용접·제약·Clone
- §5 캐릭터
- §6 카메라
- §7 런타임 에셋: MeshPart, EditableMesh/Image, 로드 판정
- §8 에셋 프라이버시(정책·날짜 의존)
- §9 렌더링: Highlight
- 정정 / 미판정

공통 조건: 실측은 모두 table-sim(일부 devplorer)이 Studio 0.742 Play 에서 잰 것이다. 이 저장소가 다시 재지 않았으므로 `status: described` 다. 원천은 신호 모드를 적지 않았다(모드 미기재). 물리·렌더링·캐릭터·에셋은 rbvm·quad mock 어느 것도 흉내 내지 않는다. 전부 Studio 가 필요하다.

---

## §1 DragDetector
status: described · last-confirmed: 원천 실측 Studio 0.742 Play(Client), 2026-10-11~16, 모드 미기재. T-06 은 문서 인용 · 근거: `table-sim/<비공개>`, `table-sim/<비공개>`, `table-sim/<비공개>`, `table-sim/<비공개>`, `table-sim/<비공개>`, `table-sim/<비공개>` · 후보: T-01, T-02, T-03, T-04, T-05, T-06

| 주제 | 엔진 동작 | 처방 |
|---|---|---|
| `AddConstraintFunction` 의 CFrame | 월드 좌표가 아니라 **끌기 시작점 기준 이동량**을 받고 돌려준다. 월드 좌표를 돌려주면 물체가 두 배 위치로 간다. 제약 함수는 `DragStart` 보다 먼저 불린다 | 이동량으로 계산한다. `DragStart` 에서 준비한 상태에 기대지 않는다 |
| `MaxActivationDistance` | 기본 32. 먼 물체는 못 끈다. 기준은 캐릭터로 보이고 캐릭터가 없으면 검사가 걸리지 않았다(두 조건만 본 추정) | 테이블 게임처럼 멀리서 끄면 값을 키운다 |
| 감지기를 단 파트의 자식 파트 | 자식 파트를 눌러서는 반응하지 않는다. 누름 판정은 `CanQuery` 가 아니라 `CanCollide` 와 "Default 충돌 그룹과 부딪치는가"를 따른다 | 모델 단위로 끌려면 감지기를 Model 밑에 둔다 |
| Physical 응답의 목표 갱신 | 커서나 카메라가 움직일 때만 목표를 다시 계산한다. 휠만 굴리면 높이가 그대로다 | 카메라를 아주 조금(0.01) 흔들어 갱신을 유도한다 |
| Physical 끌기의 흔들림 | 잡은 점을 당겨 물체가 흔들리고 돈다 | `ApplyAtCenterOfMass = true`(흔들림 0), 회전은 `AlignOrientation`(RigidityEnabled)로 막는다 |
| 실행 위치(문서) | `RunLocally = false` 면 서버가 처리하고 소유권과 무관하게 누구나 끈다. `true` 면 복제되지 않고 비앵커 파트는 소유권이 필요하다. Geometric 응답은 끄는 동안 비앵커 물체를 앵커한다. 그리드·스냅은 내장되지 않았고 ClickDetector 와 함께 쓸 수 없다 | 문서 인용이다. RunLocally 로드맵이 바뀌면 낡는다 |

- 끄는 동안의 키보드 `gameProcessed` 는 `gui-and-input.md` §7.
- mock 흉내: 해당 없음.

## §2 물리: 저항 없음, 뚫림, 겹침 튕김
status: described · last-confirmed: 원천 실측 Studio 0.742 Play, 2026-10-12 무렵. 수치는 장면 의존 · 근거: `table-sim/<비공개>` · 후보: T-15, T-16

- **구름 저항이 없다.** 누운 원기둥이나 공은 평평한 바닥에서 스스로 멈추지 않는다. 그래서 네트워크 소유권도 서버로 돌아오지 않는다.
  - 처방: 원기둥은 축 하나만 잠그는 `AlignOrientation`, 공은 목표 0 인 `AngularVelocity` 에 토크 한도 "질량 × 6" 정도로 제동한다(값은 장면에 맞춘다).
- 빠르게 떨어지는 얇은 물체는 얇은 파트를 뚫는다. 받침을 두껍게 하거나 속도를 제한한다.
- 보이지 않는 받침과 테이블 사이에 끼인 물체는 겹침 해소 과정에서 크게 튕겨 나간다. 받침끼리 겹치지 않게 둔다.
- 소유권·복제 쪽 물리(놓을 때 어긋남, 같은 값 쓰기 무복제)는 `remotes-and-replication.md` §9 몫이다(T-07~T-12).
- mock 흉내: 해당 없음.

## §3 엔진이 바꾼 값과 변경 신호
status: described · last-confirmed: 원천 실측 Studio Play, 2026-10-19(devplorer), 모드 미기재 · 근거: `/code/Projects/devplorer/.claude/research/feature-proposals-2.md:97,184,243` (원 기록 `/code/Projects/devplorer/.claude/audit/2026-10-19-insight.md`) · 후보: D-F18

- 물리로 떨어지는 Part 의 `Position` 은 `GetPropertyChangedSignal("Position")` 을 **0회** 발화했다. 물리 시뮬레이션이 바꾸는 값은 속성 변경 신호로 관측할 수 없다고 본다. 움직임을 따라가려면 `RunService` 프레임 신호에서 직접 읽는다.
- Studio 에서 `game.JobId` 는 빈 문자열이다. 서버 식별에 쓰는 코드는 Studio 에서 빈 값을 견뎌야 한다.
- 신호 일반 규칙(같은 값 대입 0회 등)은 `signals-and-events.md`.
- mock 흉내: 없다. 속성 bag mock 은 물리가 없으므로 이 차이가 드러나지 않는다. mock 위에서 "Position 이 바뀌면 신호가 온다"를 테스트하면 엔진과 반대가 된다.

## §4 용접·제약·Clone
status: described · last-confirmed: 원천 실측 Studio 0.742 Play(서버 + 클라이언트 하나), 2026-10-12·20. T-21 은 문서(WeldConstraint) 인용 · 근거: `table-sim/<비공개>`, `table-sim/<비공개>`, `table-sim/<비공개>` · 후보: T-19, T-20, T-21

- Workspace 에 들어가기 **전에** 만든 `WeldConstraint` 는 그 뒤에 정한 위치를 따라가지 않았다. 오프셋이 필요하면 C0/C1 을 적는 `Weld` 를 쓴다.
- 자식 WeldConstraint 가 붙은 파트를 `Clone()` 하면 사본의 용접이 사본 밖의 **원본 파트**를 계속 가리킨다. 사본을 돌리자 원본이 24 스터드 휘둘렸다(고친 뒤 0.000). 복제할 때 용접을 지우거나 Part0/Part1 을 사본 쪽으로 다시 건다.
- 용접된 파트에 `CFrame` 을 쓰면 연결된 파트가 같이 움직이고, `Position` 을 쓰면 그 파트만 움직인다(문서).
- mock 흉내: 해당 없음. Clone 의 참조 속성 처리는 mock 이 하지 않는다.

## §5 캐릭터
status: described · last-confirmed: 원천 실측 Studio 0.742 로컬 Play(서버 1 + 클라이언트 1), R15 기본 아바타, 2026-10-11~12 · 근거: `table-sim/<비공개>`, `table-sim/<비공개>`, `table-sim/<비공개>` · 후보: T-17, T-18, T-22, T-23

- `SeatWeld` 로 앉은 캐릭터를 `PivotTo` 로 옮기면 앵커된 Seat 까지 끌려간다. 먼저 일으켜 세운 뒤(`Sit = false` 등) 옮긴다.
- Humanoid 모델의 몸통·머리는 `CanCollide` 가 매 프레임 다시 켜져 `CanQuery = false` 도 먹지 않았다. 서버 레이캐스트가 Torso 를 맞혔다. 장식용이면 `EvaluateStateMachine = false` 로 상태 기계를 끈다.
- 캐릭터에 `Model:ScaleTo(5)` 는 0.6ms 에 적용됐다(HipHeight 2.10 → 10.48).
- `Seat:Sit(humanoid)` 뒤 `WalkSpeed`·`JumpPower`·`JumpHeight` 를 0 으로 두면 일어나지 못한다(앉힌 채 고정).
- `Players:CreateHumanoidModelFromUserIdAsync` 는 아무 UserId 로나 되고 1.06~1.32초 걸렸다(Description 캐시 뒤 0.02초). 게시 서버의 호출 한도는 미확인이다.
- 인형처럼 받침과 한 덩어리로 움직이게 하려면 `EvaluateStateMachine = false`, `PlatformStand = true`, 몸 파트 전부 `Massless = true`.
- mock 흉내: 해당 없음.

## §6 카메라
status: described · last-confirmed: 원천 실측 Studio 0.742 Play(Client), 2026-10-11 · 근거: `table-sim/<비공개>` · 후보: T-40

- 진입 스크립트가 캐릭터 스폰 **전에** 카메라를 `Scriptable` 로 바꾸면, 스폰 때 기본 카메라 스크립트가 `Custom` 으로 되돌린다. 캐릭터가 붙은 뒤(`CharacterAdded` 이후) 다시 설정한다. `CharacterAutoLoads = false` 인 경우는 미확인이다.
- mock 흉내: 해당 없음.

## §7 런타임 에셋: MeshPart, EditableMesh/Image, 로드 판정
status: described · last-confirmed: 원천 실측 Studio Play(서버 데이터모델 또는 Client), 2026-10-11~16. 게시 게임의 예산은 다를 수 있다 · 근거: `table-sim/<비공개>`, `table-sim/<비공개>`, `table-sim/<비공개>`, `table-sim/<비공개>`, `table-sim/<비공개>`, `table-sim/<비공개>`, `/code/Projects/devplorer/.claude/research/agent-mode-plan.md:135-136` · 후보: T-24, T-25, T-26, T-28

- `MeshPart.MeshId` 는 스크립트로 쓸 수 없다(`lacking capability NotAccessible`). 런타임 메시는 `AssetService:CreateMeshPartAsync(Content.fromUri(id))` 로 만든다(0.64초). 틀린 ID 는 던지므로 `pcall` 로 감싼다.
- **EditableMesh**
  - 서버에서 지은 MeshPart 는 모양이 복제되지 않는다. 클라이언트에서 만든다.
  - 클라이언트에서 서로 다른 EditableMesh 약 5개에서 "memory budget" 에 막혔다. `FixedSize = true` 사본은 25개 이상 됐다.
  - 원본 EditableMesh 를 지우면 그것으로 만든 모양도 사라진다.
  - 게시 게임은 보안 설정 "Allow Mesh / Image APIs" 를 켜야 한다.
- **EditableImage**: `MeshPart.TextureContent` 로 입히면 파트 `Color` 가 무시된다. `SurfaceAppearance.ColorMapContent` 는 게임 스크립트에서 못 쓴다(`lacking capability Plugin`). 그런데 플러그인 권한으로 도는 `execute_luau` 에서는 된다. **MCP 로 확인한 것이 게임 스크립트에서는 실패할 수 있다**는 함정이다.
- **로드 판정**
  - 서버 `MarketplaceService:GetProductInfo` 는 없는 ID 에서 `HTTP 404` 를 던진다. `AssetTypeId` 로 종류를 가른다(350~600ms).
  - 클라이언트 `ContentProvider:PreloadAsync` 는 종류가 다른 것과 없는 것을 똑같이 `Failure` 로 준다. 종류 판정은 서버에서 한다.
  - 화면 밖 ImageLabel 은 preload 뒤에도 `IsLoaded = false` 였다.
- mock 흉내: 해당 없음. capability·예산 오류는 엔진에서만 난다.

## §8 에셋 프라이버시(정책·날짜 의존)
status: described · 확인일: 2026-10(원천 조사), 문서·DevForum 인용 · 근거: `table-sim/<비공개>`, `table-sim/<비공개>` · 후보: T-29

- 2026-05-05 이후 새 계정이 올린 Image·Decal·Mesh 는 기본 Restricted 다. 권한이 없는 experience 에서는 로드되지 않는다.
- Decal ID 와 Image ID 는 다르다(업로드는 Decal ID 를 준다).
- 에셋이 Open Use 인지 런타임에 읽는 API 는 없다.
- 권한을 고친 뒤에도 negative caching 으로 한동안 실패할 수 있다.
- 정책 항목이라 주기적으로 다시 확인한다. 날짜가 지난 판단은 쓰기 전에 문서를 다시 본다(`api-docs.md`).
- mock 흉내: 해당 없음.

## §9 렌더링: Highlight
status: described · last-confirmed: 원천 실측 Studio Play, 2026-10-11 무렵(투명 파트), 255 는 문서 인용 · 근거: `table-sim/<비공개>`, `table-sim/<비공개>` · 후보: T-27

- 완전 투명한 파트에 건 `Highlight` 는 아무것도 그리지 않는다. 투명한 손잡이를 강조하려면 보이는 파트나 모델에 건다.
- 클라이언트에서 동시에 그리는 Highlight 는 255개까지이고, 넘으면 조용히 무시된다(문서). 다중 선택 강조는 모델 단위로 묶어 수를 줄인다.
- mock 흉내: 해당 없음.

---

## 정정
| 원천 경로:줄 | 틀린 서술 | 맞는 것 | 근거 |
|---|---|---|---|
| `table-sim/<비공개>` 의 첫 PASS 근거(원천 안에서 이미 정정됨) | 제약 함수는 월드 CFrame 을 받고 돌려준다 | 끌기 시작점 기준 이동량이다 | `table-sim/<비공개>` |

그 밖에 이 파일 범위에서 원천끼리 어긋나는 서술은 찾지 못했다.

## 미판정
**`MaxActivationDistance` 의 기준점(T-02).** "캐릭터 기준, 캐릭터가 없으면 검사 안 함"은 두 조건만 본 추정이다. 재현 절차:
1. 빈 플레이스에 비앵커 Part 와 DragDetector(기본 32)를 두고 Play(Client)를 시작한다.
2. 캐릭터를 Part 에서 20, 40 스터드에 두고 카메라는 Part 가까이에 둔 채 `user_mouse_input` 으로 끌어 `DragStart` 발화를 `_G` 에 센다.
3. 반대로 캐릭터는 가깝고 카메라만 40 스터드 떨어뜨린 경우를 잰다.
4. `Players.CharacterAutoLoads = false` 로 캐릭터 없이 같은 것을 잰다. Studio 버전과 날짜를 적는다.
