# remotes-and-replication — 원격·바인더블 신뢰 경계, 복제, 네트워크 소유권, 스트리밍

## 이 파일이 답하는 질문
- Q1 RemoteEvent/RemoteFunction 으로 받은 표를 서버가 믿어도 되나? 메타테이블·함수는 건너오나?
- Q2 BindableEvent 는 인자를 어떻게 넘기나? 무엇이 `Fire` 를 실패시키나?
- Q3 원격으로 받은 Instance 참조는 위조될 수 있나? nil 로 오는 때는?
- Q4 원격 값은 어떤 순서로 무엇을 검사하나? 데이터 타입 비교의 함정은?
- Q5 원격 요청 한도와 DoS 예산은 어떻게 잡나?
- Q6 어떤 컨테이너가 누구에게 복제되나? 스크립트는 어느 문맥에서 도나?
- Q7 네트워크 소유권과 물리 복제의 함정은?
- Q8 StreamingEnabled 에서 먼 것은 어떻게 오나? 속성은 오나?

## 목차
- §1 원칙: 복제되는 것은 공개, 서버가 다시 검사한다
- §2 RemoteEvent/RemoteFunction 인자 복사
- §3 BindableEvent 인자 복사
- §4 Instance 참조가 경계를 건널 때
- §5 원격 값 검증 순서와 데이터 타입 함정
- §6 원격 한도, 연결 전 큐, DoS 예산
- §7 복제 경계와 스크립트 실행 문맥
- §8 플레이어 식별
- §9 네트워크 소유권
- §10 스트리밍과 복제 범위
- 정정
- 미판정

모든 절의 근거는 원천 저장소(devplorer, table-sim, tbox)의 기록이다. 이 저장소는 Studio 로 다시 재지 않았다. 그래서 Studio 실측도 `status: described`(원천 실측 근거)로 둔다. 원천은 신호 모드를 대부분 적지 않았다. Immediate 모드는 아무도 재지 않았다.

---

## §1 원칙: 복제되는 것은 공개, 서버가 다시 검사한다
status: described · last-confirmed: 원천 서술 2026-10-19 · 근거: `/code/Projects/devplorer/.claude/research/cmdr-survey.md:19,45,61-62,71-74`, `/code/Projects/devplorer/.claude/review/2026-10-19-server-security.md:164-179,342-346` · 후보: D-F23, D-R12

- 클라이언트에 복제되는 것은 모두 공개로 본다. ModuleScript 소스도 복제되면 클라이언트가 읽는다. 한 번 내려간 코드는 회수할 수 없다.
- 클라이언트 쪽 검사(버튼 숨기기, 권한 확인)는 겉모양이다. 서버가 요청마다 다시 검사한다.
- 판정기가 없거나 판정이 실패하면 거부한다(fail-closed).
- 처방: 서버 전용 모듈이 `ServerScriptService`/`ServerStorage` 아래에 있는지 시작할 때 `IsDescendantOf` 로 assert 한다. 잘못 `ReplicatedStorage` 로 옮겨지면 바로 멈춘다.

mock 흉내: 해당 없음. 복제는 mock 이 흉내 내지 않는다.

## §2 RemoteEvent/RemoteFunction 인자 복사
status: described (원격 쪽 실측 없음) · last-confirmed: 원천 서술 2026-10-19~20 · 근거: `/code/Projects/devplorer/.claude/review/2026-10-20-actions-security.md:15`, `/code/Projects/devplorer/.claude/review/2026-10-19-server-edit.md:268-270`, `/code/Projects/devplorer/.claude/review/2026-10-19-server-logs-remote.md:200,256-257`, `/code/Projects/devplorer/.claude/review/2026-10-19-server-security.md:361-362`, `/code/Projects/rbvm/.claude/review/2026-10-05-code-review.md:261` · 후보: D-R01

- 원격을 건넌 표는 엔진이 직렬화했다 다시 만든 **사본**이다. 받는 쪽 표는 보낸 쪽과 별칭을 공유하지 않는다.
- 메타테이블과 함수는 떨어진다. 그래서 서버의 `typeof` 판정은 믿을 수 있다. 메타테이블 표로 가짜 `Vector3` 를 만들어 보내도 서버에서는 평범한 표다.
- 프록시 표(메타테이블로만 내용을 보이는 표)를 보내면 빈 표가 된다.
- 이 절은 문서·리뷰 서술이다. 바인더블 쪽(§3)은 실측이 있고 같은 방향이다.

mock 흉내: 해당 없음. 원격은 mock 이 인터페이스 모양만 스텁한다. 복사·메타테이블 제거를 흉내 내지 않으므로 mock 위 테스트는 별칭을 공유한 채 통과할 수 있다.

## §3 BindableEvent 인자 복사
status: described (원천 실측) · last-confirmed: Studio Edit, 2026-10-20, 플러그인 문맥, 모드 미기재(처리기는 `Fire` 뒤에 따로 돌았다) · 근거: `/code/Projects/devplorer/.claude/review/2026-10-20-bindable-watch.md:20-21,72-85` · 후보: D-R02 (비용은 D-R03 → `perf.md`)

| 보낸 것 | 처리기가 받은 것 |
|---|---|
| 메타테이블을 단 표 | 새 표, 메타테이블 없음. 처리기마다 다른 사본 |
| 함수 | **같은 함수**(`rawequal` 참). 표 안의 함수도 같다 |
| `newproxy`, thread | `nil`. 인자 개수(`select("#")`)는 그대로 |
| 순환 표 | `Fire` 자체가 실패: `tables cannot be cyclic` |
| 불리언 키 표 | `Fire` 자체가 실패: `Invalid table key type used` |
| Instance 키 표 | 성공 |

- 원격(§2)과 달리 함수는 정체성 그대로 건너온다. 같은 VM 안이기 때문이다.
- 바인더블에는 크기 상한이 없다. 큰 표를 처리기마다 복사하는 비용은 `perf.md`.
- 처리기가 던져도 `Fire` 한 쪽으로 퍼지지 않았다.

mock 흉내: 보통 흉내 내지 않는다. 흔한 mock Signal 은 같은 표를 그대로 넘기므로 "받은 표를 고치면 보낸 쪽도 바뀐다"는 엔진에 없는 결합을 만든다.

## §4 Instance 참조가 경계를 건널 때
status: described (스트리밍 nil 은 원천 실측) · last-confirmed: Studio Play, 2026-10-19 · 근거: `/code/Projects/devplorer/.claude/review/2026-10-19-server-logs-remote.md:256-257`, `/code/Projects/devplorer/.claude/review/2026-10-19-server-security.md:351`, `/code/Projects/devplorer/.claude/review/2026-10-19-server-security-round2.md:153`, `<비공개>` · 후보: D-R07

- 원격으로 오는 Instance 는 그 클라이언트에도 복제된 것뿐이다. 서버 전용 Instance 는 클라이언트가 지어낼 수 없다.
- 받는 쪽에 없는 Instance(스트리밍 범위 밖 포함)는 `nil` 로 온다. 서버가 보낸 참조가 클라이언트에서 `nil` 이면 "이 클라이언트에는 아직 없다"는 뜻이다.
- 그래도 클라이언트가 보낸 Instance 가 "그 플레이어가 만져도 되는 것"인지는 서버가 따로 검사한다(§1).

mock 흉내: 해당 없음.

## §5 원격 값 검증 순서와 데이터 타입 함정
status: described (일부 원천 실측: Studio Play 2026-10-19, tbox 코드 리뷰) · 근거: `/code/Projects/devplorer/.claude/review/2026-10-19-server-security.md:359-363`, `/code/Projects/devplorer/.claude/review/2026-10-19-server-edit.md:232-240,268-270,300,304-309`, `/code/Projects/devplorer/.claude/review/2026-10-19-server-structure.md:128-134,160`, `/code/Projects/tbox/docs/code-review-2026-10-05.md:153-162,187-194,356`, `/code/Projects/tbox/docs/redesign-precedents.md:23` · 후보: D-R06, D-R46, X-17, X-20, X-23

검사 순서(값 하나를 받을 때):
1. 재귀하기 **전에** 깊이 상한.
2. 거부: 순환, 메타테이블(`__metatable=false` 로 잠근 것 포함), Instance(받을 자리가 아니면), buffer, vector, 함수, NaN, ±inf.
3. 항목 수 상한.
4. 대략 크기를 먼저 보고, 마지막에 실제 `HttpService:JSONEncode` 길이로 다시 잰다. 제어 문자는 이스케이프로 약 6배 커진다.

자리별 함정:
- `CFrame.fromMatrix` 로 비정규직교 회전이 들어올 수 있다. 받은 CFrame 은 `Orthonormalize()` 한다.
- `CFrame:FuzzyEq` 는 회전을 각도 근사로 비교한다(문서). 대각 성분을 왜곡해도 trace 가 같으면 통과할 수 있어 정규직교 검사로 쓰지 않는다(Studio 미확인).
- EnumItem 은 `EnumType` 으로 비교한다. 특성(Attribute) 값으로는 넣을 수 없다.
- 특성 이름은 `^[%w_]+$`, 100자 이하, `RBX` 접두 금지로 거른다.
- `Vector2`·`Vector3`·`CFrame`·`NumberRange` 성분과 네이티브 `vector` 성분은 float32 다. 64비트 경계값과 비교하면 틀린다(`NumberRange.new(0, 0.1)` 이 `maxSpan = 0.1` 검사에 실패). 경계도 float32 로 반올림해 비교한다. 네이티브 `vector` 쪽은 luau CLI 로도 재현된다.
- Roblox userdata 는 없는 멤버를 인덱싱하면 던진다. 임의 값을 `v.tag` 같은 덕 타이핑으로 판별하지 말고 `typeof` 를 먼저 본다.

mock 흉내: quad runshim 데이터 타입은 "아무 필드나 읽으면 값 객체"라 float32 반올림, 없는 멤버 에러, `Orthonormalize` 를 흉내 내지 않는다. 값에 기대는 검증 테스트는 Studio(또는 Lune 의 실 데이터 타입)로 한다.

## §6 원격 한도, 연결 전 큐, DoS 예산
status: described (한도는 문서 인용, 큐잉은 미실측, 예산은 CLI 시뮬레이션) · last-confirmed: 확인일 2026-10 (정기 재확인 대상) · 근거: `table-sim/<비공개>`, `/code/Projects/devplorer/.claude/review/2026-10-19-server-logs-remote.md:85-107,228-234`, `/code/Projects/devplorer/.claude/review/2026-10-20-bindable-watch.md:140`, `/code/Projects/devplorer/.claude/review/2026-10-19-server-security.md:47-71`, `/code/Projects/devplorer/.claude/review/2026-10-19-server-security-round2.md:58-62` · 후보: T-44, D-R23

- 클라이언트→서버는 클라이언트당 약 500 요청/초이고 같은 종류끼리 공유한다(2026-10 문서).
- `UnreliableRemoteEvent` 는 한도를 넘은 것과 1000바이트를 넘는 페이로드를 버린다.
- 서버에 연결이 없을 때 온 RemoteEvent 는 큐에 쌓였다가 첫 `Connect` 에 한꺼번에 전달된다고 알려져 있다. 그래서 디버그·로깅 연결을 먼저 붙이면 게임 처리기 몫을 가로챈다. Unreliable 과 바인더블은 쌓지 않는다. **큐잉은 미실측이다(미판정 절).**
- DoS 예산은 요청 수가 아니라 **일의 양**으로 잡고, 일을 하기 **전에** 청구한다.
  - `GetChildren`/`GetDescendants` 는 결과를 자르기 전에 배열 전체를 만든다. 개수 상한은 호출 뒤가 아니라 호출 전 비용에 걸어야 한다.
  - 거절 경로에서도 청구한다. 빠지면 거절되는 요청이 공짜 일이 된다.
  - 엔진 호출 비용 자체는 미실측이다.

mock 흉내: 해당 없음. 한도·큐는 mock 에 없다.

## §7 복제 경계와 스크립트 실행 문맥
status: described (D-R18·D-R49 는 원천 실측, Studio Play 2026-10-19~20, 모드 미기재) · 근거: `/code/Projects/devplorer/.claude/review/2026-10-19-server-security.md:164-179`, `/code/Projects/devplorer/.claude/review/2026-10-19-server-round6.md:192-206`, `/code/Projects/devplorer/.claude/review/2026-10-19-ux-explore.md:11-14`, `/code/Projects/devplorer/.claude/review/2026-10-19-server-structure.md:106-114`, `/code/Projects/devplorer/.claude/review/2026-10-19-server-edit.md:59-71`, `/code/Projects/devplorer/.claude/review/2026-10-20-client-actions.md:56-66`, `/code/Projects/devplorer/.claude/review/2026-11-08-post-move-audit.md:24`, `/code/Projects/devplorer/.claude/research/feature-survey.md:22-23,101-102` · 후보: D-R12, D-R13, D-R18, D-R49, D-F29

| 위치 | 누구에게 |
|---|---|
| `ServerStorage`, `ServerScriptService` | 복제 안 됨 |
| `ReplicatedStorage`, `Workspace`(스트리밍 범위 안) | 모두 |
| `Player.PlayerGui` | 그 플레이어에게만 |
| 다른 플레이어의 `Backpack` | 모두에게 복제된다고 알려져 있다(추정, 미실측). `StarterGear` 미확인 |
| `Stats`/`StatsItem` | 클라이언트에 없다 |

- 서버가 PlayerGui 에 넣은 ScreenGui 나 복제한 모듈 아래의 `LocalScript`, `RunContext = Client` 인 `Script` 는 넣는 순간 그 클라이언트에서 돈다. `ResetOnSpawn = false` 면 리스폰 뒤에도 남는다. Legacy `Script` 는 미실측.
- 꺼진 `LocalScript` 를 서버가 켜면 모든 클라이언트에서 돈다.
- 의존성의 test 폴더(`RunContext = Plugin`)가 릴리스 번들에 섞여 들어간 실례가 있다. 번들에 넣기 전에 `RunContext` 를 훑는다.
- `OnServerInvoke`·`OnInvoke` 콜백은 그것을 설정한 스크립트에 묶인다. 그 스크립트를 지우면 호출이 `Script that implemented this callback has been destroyed` 로 실패한다.
- F9 서버 출력은 소유자와 편집 권한 그룹원만 본다. RemoteFunction 을 가로채 캡처하면 `InvokeClient` 가 깨진다.

mock 흉내: 해당 없음.

## §8 플레이어 식별
status: described (원천 CLI 시뮬레이션) · 근거: `/code/Projects/devplorer/.claude/review/2026-10-19-server-security.md:16-43,383-385` · 후보: D-R11

- `DisplayName` 은 유일하지 않고 다른 사람의 사용자명과 똑같이 지을 수 있다.
- 권한 대상은 `UserId`, 또는 정확한 사용자명(`Name`)으로만 지정한다. 표시용 문자열로 권한을 판정하지 않는다.

mock 흉내: 해당 없음.

## §9 네트워크 소유권
status: described (원천 실측: Studio 0.742 Play, 서버 1 + 클라이언트 1, 핑 0, 2026-10-12; T-12·D-R48 은 문서 인용) · 근거: `table-sim/<비공개>`, `table-sim/<비공개>`, `table-sim/<비공개>`, `table-sim/<비공개>`, `/code/Projects/devplorer/.claude/review/2026-10-19-server-edit.md:256-257` · 후보: T-07, T-08, T-09, T-10, T-11, T-12, D-R48

- 앵커되지 않은 파트는 가만히 있어도 엔진이 근처 플레이어에게 소유권을 준다. 서버 소유가 필요하면 `SetNetworkOwner(nil)` 을 명시한다.
- 앵커된 파트는 항상 서버 소유이고 바꿀 수 없다. 앵커 파트가 없는 어셈블리는 한 파트에 건 소유권이 어셈블리 전체에 걸린다. 앵커를 푼 **뒤에** 부른다.
- 소유권 API 는 `Workspace` 자손에서만 부를 수 있다(`Can only call Network Ownership API on a part that is descendent of Workspace`).
- 클라이언트가 소유한 파트의 위치·속도 변경은 서버로 복제된다.
- **같은 값 쓰기는 복제되지 않는다.** 클라이언트 소유로 끌던 파트를 놓을 때 서버가 `Anchored = true` 만 걸면 양쪽이 0.28스터드 어긋난 채 굳었다. `p.CFrame = p.CFrame` 은 서버 값과 같아 복제되지 않는다. 서버가 클라이언트의 마지막 위치(다른 값)를 받아 직접 쓴다.
- 서버가 속도를 준 직후 소유권을 넘기면 그 속도가 넘어가지 않았다. 속도는 새 소유자 쪽에서 준다.
- 서버 물리를 클라이언트에서 보면 움직이는 프레임의 15%가 제자리였고 속도 편차가 189%였다. 튕긴 플레이어에게 소유권을 넘기면 0%, 13~36%였다(반일반: 장면 의존).

mock 흉내: 해당 없음. 물리·소유권은 항상 Studio(`env-dependence.md` §2).

## §10 스트리밍과 복제 범위
status: described (원천 실측: Studio 0.742 Play, 2026-10) · 근거: `table-sim/<비공개>`, `table-sim/<비공개>`, `/code/Projects/devplorer/.claude/research/feature-proposals-2.md:68` · 후보: T-13, T-14

- StreamingEnabled 에서 `ReplicationFocus` 가 먼 곳이면 먼 Model 은 빈 껍데기로 온다(`PrimaryPart = nil`). 그 아래 파트·데칼·**파트의 속성**은 오지 않는다.
- 반면 **Model·Folder 자신의 속성과 Player 속성은 모두에게 간다.** 스트리밍은 속성을 숨겨 주지 않는다. 비밀을 Model 속성에 두지 않는다(보안 경계인지는 문서 미확인).
- 초점을 옮기면 1~2초 안에 바뀌었다.
- `workspace.StreamingMinRadius`, `StreamOutBehavior`, `StreamingTargetRadius` 는 스크립트에서 읽을 수 없다(`not a valid member`). `SignalBehavior` 와 같은 꼴이다(`signals-and-events.md`). 값은 Rojo 프로젝트의 Workspace 속성으로 두고 저장소에서 관리한다.
- 받는 쪽에 아직 없는 Instance 참조는 `nil` 이다(§4).

mock 흉내: 해당 없음.

---

## 정정
없음. 이 파일에 옮긴 행 가운데 원천끼리 결론이 갈린 것은 없다. table-sim 은 외부 모델이 "Model 속성도 스트리밍으로 숨겨진다"고 단정한 것을 실측으로 뒤집었다(T-13). 그 단정은 원천 저장소의 서술이 아니라 외부 검토 결과라 여기 올리지 않는다.

## 미판정
미실측 주장이다. Studio MCP 를 쓰지 않아 판정하지 않았다. 재현할 때는 `studio-mcp.md` §5 관용구(결과는 `return`, Deferred 는 두 번 호출)를 따르고 모드를 함께 적는다.

| 주장 | 후보 | 재현 절차 |
|---|---|---|
| 연결 전에 온 RemoteEvent 는 큐에 쌓였다가 첫 Connect 에 전달된다 | T-44 | 1) Play(서버+클라이언트 1)에서 서버에 연결 없는 RemoteEvent 를 둔다. 2) 클라이언트가 `FireServer` 를 5번 한다. 3) 서버에서 `task.wait(1)` 뒤 처리기 A 를 연결하고 받은 횟수를 센다. 4) 이어 처리기 B 를 연결해 B 가 옛 것을 받는지 본다. 5) 같은 시나리오를 UnreliableRemoteEvent 로 반복한다 |
| 원격 표는 사본이고 메타테이블·함수가 떨어진다 | D-R01 | 1) 클라이언트가 `__index` 단 표, 함수를 품은 표, 프록시 표를 보낸다. 2) 서버에서 `getmetatable`, 필드 타입, `next(t)` 를 기록해 돌려준다 |
| 다른 플레이어의 Backpack 이 모두에게 복제된다 | D-R13 | 1) 클라이언트 2개로 Play. 2) 플레이어 A 의 Backpack 에 Tool 을 넣는다. 3) 클라이언트 B 에서 `Players.A.Backpack:GetChildren()` 을 본다. 4) `StarterGear` 도 같은 방법으로 본다 |
| Legacy `Script` 를 PlayerGui 에 넣으면 도는가 | D-R49 | 1) 서버가 PlayerGui 에 `RunContext = Legacy` Script 를 넣는다. 2) 스크립트가 `RunService:IsClient()` 와 함께 표식을 남기는지 본다 |
