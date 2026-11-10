---
title: "DataStore·MemoryStore·상품·글자 안전·샌드박스·게시 도구"
description: "DataStore 크기·분당 예산, pcall 실패·UpdateAsync 재실행·GetAsync 캐시, Studio DataStore 가 프로덕션에 씀, MemoryStore·MessagingService 한도, ProcessReceipt, 글 필터·RichText, JSONEncode, loadstring, LogService, Open Cloud"
keywords:
  - "DataStore 한도"
  - "DataStore 예산"
  - "UpdateAsync 재실행"
  - "GetAsync 캐시"
  - "UseCache"
  - "Enable Studio Access to API Services"
  - "MemoryStore 한도"
  - "MessagingService 유실"
  - "ProcessReceipt"
  - "PurchaseGranted"
  - "FilterStringAsync"
  - "RichText 이스케이프"
  - "JSONEncode 혼합 키"
  - "loadstring"
  - "LoadStringEnabled"
  - "스크립트 타임아웃"
  - "LogService MessageOut"
  - "Open Cloud Luau Execution"
  - "로그 위조 문자"
kind: reference
category: roblox/services
tags: [security, policy, docs-quoted, correction]
last_verified: 2026-11-10
---
# platform-services — DataStore·MemoryStore·상품·글자 안전·샌드박스·게시 도구

## 이 파일이 답하는 질문
- Q1 DataStore 의 크기·예산 한도는? `pcall` 실패면 안 쓴 것인가? `GetAsync` 는 최신 값인가?
- Q2 Studio 에서 DataStore 를 쓰면 어디에 써지나? MemoryStore·Messaging·Teleport 는 Studio 에서 되나?
- Q3 서버 목록·서버 간 통신은 무엇으로 하나?
- Q4 개발자 상품 영수증은 어떻게 처리하나?
- Q5 플레이어가 쓴 글을 보여 줄 때 무엇을 막아야 하나?
- Q6 `HttpService:JSONEncode` 는 혼합·희소 표를 어떻게 다루나?
- Q7 `loadstring` 과 사용자 스크립트 샌드박스의 한계는?
- Q8 LogService 로 로그를 모을 때의 함정은?
- Q9 Open Cloud 게시·Luau Execution·Rojo 의 제약은?

## 목차
- §1 DataStore 한도와 의미
- §2 Studio 에서의 데이터 서비스
- §3 MemoryStore 와 MessagingService
- §4 게임 패스와 개발자 상품
- §5 글자 안전: 필터, RichText, 로그 위조
- §6 `HttpService:JSONEncode` 의 표 모양
- §7 `loadstring`, 샌드박스, 타임아웃
- §8 Luau 로 쓴 인터프리터
- §9 LogService
- §10 게시와 외부 도구(Open Cloud, Rojo, 패키지)
- 정정
- 미판정

한도·정책 수치는 날짜에 매인다. 절마다 확인일을 적었다. **정기 재확인 대상**이다(roblox-docs `sources.md` 로 문서를 다시 읽는다). Studio 실측은 원천 기록이고 이 저장소가 다시 재지 않았다.

---

## §1 DataStore 한도와 의미
status: described (문서 인용) · last-confirmed: 확인일 2026-10 (table-sim 조사), 정기 재확인 대상 · 근거: `table-sim/<비공개>`, `/code/Projects/devplorer/.claude/review/2026-10-21-settings-datastore.md:21-40,57-58,77-86,111-121,130,135,147-148`, `/code/Projects/devplorer/.claude/research/deploy-notes.md:34-36` · 후보: T-41, D-R45

크기:
- 값은 직렬화한 JSON 길이로 4 MiB(4,194,304자). 데이터스토어 이름·키·스코프는 각 50자.
- `buffer` 는 직접 저장하지 못한다. 문자열로 바꿔(예: `EncodingService:Base64Encode` 후 `buffer.tostring`) 넣는다. 문서는 "미리 압축하지 말라, 저장 쪽이 압축한다"고 한다.

예산(분당, 2026-10 문서):
| 단위 | Read | Write | List |
|---|---|---|---|
| experience 전체 | `300 + CCU×40` | `300 + CCU×20` | `300 + CCU×2` |
| 서버 하나(기본값) | `60 + 플레이어×40` | `60 + 플레이어×40` | `5 + 플레이어×2` |

- 2026-07-29 부터 게임 서버와 Open Cloud 가 experience 예산을 함께 쓴다. `UpdateAsync` 는 Read 와 Write 를 둘 다 쓴다.
- 옛 문서의 서버 쓰기 예산 `60 + 플레이어×10` 은 2026-10 기준으로 낡았다(정정 절).

의미:
- **`pcall` 실패가 "백엔드에 안 썼다"를 보장하지 않는다.** 최종 상태를 모를 수 있다.
- `GetAsync` 는 기본 4초 로컬 캐시를 쓴다. 확인 읽기는 `DataStoreGetOptions.UseCache = false`.
- `UpdateAsync` 콜백은 다른 서버와 충돌하면 **다시 실행된다**. 콜백 안에서 yield 하지 않고 부작용을 두지 않는다. `nil` 을 돌려주면 쓰기를 취소한다.
- `SetAsync` 는 마지막 쓰기가 이긴다. 읽고-고쳐-쓰기는 `UpdateAsync` 로 한다.
- 시한 경쟁: 클라이언트가 `GetAsync` 결과를 시한까지 못 받으면 실패로 보지만 서버는 늦게 성공할 수 있다. 기본값으로 시작한 화면이 저장하면 실제 값을 덮어쓴다. 로드 실패 상태에서는 저장을 막는다.
- `SetAsync` 에 `userIds` 를 붙이면 그 데이터가 그 사용자의 개인 데이터로 영구히 남는다(삭제 요청 대상). 남의 게임 예산을 쓰는 도구라면 붙이기 전에 따져 본다.

mock 흉내: 흔한 mock(가짜 store 표)은 캐시, 재실행되는 `UpdateAsync`, "실패했지만 써졌다"를 흉내 내지 않는다. 이 셋에 기대는 로직은 mock 에 `UpdateAsync` 재실행·실패 주입을 직접 넣어 시험한다.

## §2 Studio 에서의 데이터 서비스
status: described (DataStore 는 원천 실측, 나머지 문서) · last-confirmed: 원천 실측 Studio 2026-10-12, 모드 무관 · 근거: `table-sim/<비공개>`, `table-sim/<비공개>`, `/code/Projects/table-sim/.claude/conventions.md:153` · 후보: T-42

| 서비스 | Studio 동작 |
|---|---|
| DataStore | 게시된 experience 와 "Enable Studio Access to API Services" 가 필요하다. 미게시 파일에서는 에러. **프로덕션과 같은 저장소**에 쓴다(실측: 스테이징 실 DataStore 에 써져 Play 를 다시 시작해도 남았다) |
| MemoryStore | 문서상 동작하고 Studio 와 프로덕션 데이터가 분리된다. 미게시 파일에서 되는지는 미판정(아래) |
| MessagingService | 문서에 Studio 설명이 없다. 서버가 하나라 다중 서버 시나리오는 Studio 로 못 본다 |
| TeleportService | Studio 에서 동작하지 않는다(문서 명시) |

- 처방: 테스트용 experience 를 따로 게시해 Studio 접근을 그쪽에만 켠다. 데이터 서비스는 인터페이스로 감싸 `luau`+mock 으로 시험한다(luau-roblox `mocks.md` §2).

mock 흉내: 이 절 자체가 "언제 mock 으로 대신하나"의 근거다.

## §3 MemoryStore 와 MessagingService
status: described (문서 인용) · last-confirmed: 확인일 2026-10, 정기 재확인 대상 · 근거: `table-sim/<비공개>` · 후보: T-43

- MemoryStore: 쿼터 64KB + 1.2KB×사용자, 값 하나 32KB, TTL 최대 45일, 단일 파티션.
- MessagingService: best-effort 다. 히스토리가 없고 메시지는 1kB 까지다. 놓치면 다시 오지 않는다.
- 처방: 서버 목록은 MemoryStore 에 TTL 하트비트로 두고, Messaging 은 "빨리 알리기" 보조로만 쓴다.

mock 흉내: 인메모리 표·이벤트 버스로 대신하면 TTL 만료, 메시지 유실이 없다. 유실에 기대는 복구 로직은 mock 에 유실을 주입해 시험한다.

## §4 게임 패스와 개발자 상품
status: described (haiku 가 작성한 조사 보고서라 인용 재확인 필요) · last-confirmed: 확인일 2026-10 · 근거: `table-sim/<비공개>`, `table-sim/<비공개>` · 후보: T-56

- 게임 패스에는 `ProcessReceipt` 가 필요 없다(소유 여부를 조회한다).
- 개발자 상품은 `MarketplaceService.ProcessReceipt` 가 필수다.
  - `PurchaseId` 로 멱등 처리한다. 같은 영수증이 다시 올 수 있다.
  - 저장이 **끝난 뒤에만** `Enum.ProductPurchaseDecision.PurchaseGranted` 를 돌려준다. 아니면 `NotProcessedYet` 을 돌려주고, 엔진이 재접속 때 다시 부른다.
- 원천 저장소가 이 보고서를 "인용 재확인 필요"로 표시했다. 쓰기 전에 `MarketplaceService.md` 를 다시 읽는다.

mock 흉내: 해당 없음(구매는 Studio 테스트 구매나 사람 QA).

## §5 글자 안전: 필터, RichText, 로그 위조
status: described (D-R30 은 원천 실행 검증) · last-confirmed: 2026-10-19 · 근거: `table-sim/<비공개>`, `table-sim/<비공개>`, `/code/Projects/devplorer/.claude/review/2026-10-19-server-security.md:228-242,399`, `/code/Projects/devplorer/.claude/review/2026-10-19-server-round6.md:156-221`, `/code/Projects/devplorer/.claude/review/2026-10-19-shared-specs.md:71-73` · 후보: T-50, D-R31, D-R30

- 다른 플레이어에게 보이는 사용자 글은 필터가 의무다. `TextService:FilterStringAsync` → `GetNonChatStringForBroadcastAsync`(또는 받는 사람별 함수).
  - `fromUserId` 가 그 서버에 없으면 던진다.
  - 필터가 실패하면 **보여 주지 않는다**(원문으로 폴백하지 않는다).
- `TextChannel:SendAsync` 는 LocalScript 전용, `DisplaySystemMessage` 는 클라이언트 전용이며 필터가 없다.
- `RichText = true` 라벨에 사용자 문자열을 넣으면 `<font transparency="1">` 같은 태그로 화면을 속일 수 있다. `& < > " '` 를 이스케이프한다.
- 로그 한 줄을 위조하는 문자는 `\n` 만이 아니다. U+0085, U+2028/2029, 방향 제어 문자, 보이지 않는 문자, 한글 채움 문자(U+3164, U+115F, U+1160, U+FFA0)도 막는다. 전체 목록은 원천 `server-round6.md:156-221`.

mock 흉내: 필터는 Studio 에서도 제한적이다. 테스트는 필터 함수를 주입해 "실패 → 숨김" 경로를 시험한다.

## §6 `HttpService:JSONEncode` 의 표 모양
status: described (**미실측**, 원천 서술이 셋으로 갈림) · 근거: `/code/Projects/devplorer/.claude/review/2026-10-19-shared-specs.md:47-49`, `/code/Projects/devplorer/.claude/review/2026-10-19-server-round6.md:248`, `/code/Projects/devplorer/.claude/review/2026-10-19-server-security.md:209-214,224` · 후보: D-R43

- 혼합 키(`{1, 2, a = 3}`), 희소·0·음수 정수 키, ±inf 키, 잘못된 UTF-8 을 `JSONEncode` 가 어떻게 다루는지(에러인지, 모양을 바꿔 통과하는지)는 아무도 재지 않았다.
- 처방(어느 쪽이든 안전): `JSONEncode` 는 항상 `pcall` 로 감싼다. 받는 표의 키는 "모두 문자열" 또는 "1..n 밀집 배열"만 허용한다. 정수 검사(`k == math.floor(k)`)는 ±inf 를 통과시키므로 유한성도 따로 본다.
- DataStore 크기 한도도 이 직렬화 길이로 잰다(§1).

mock 흉내: luau CLI 에는 `HttpService` 가 없다. 흔한 mock 의 JSON 인코더는 엔진과 다른 규칙일 수 있으니 이 동작을 mock 으로 단정하지 않는다.

## §7 `loadstring`, 샌드박스, 타임아웃
status: described (readonly·`string.rep` 은 원천이 luau CLI 0.734 로 실측, 나머지 문서·글 인용) · last-confirmed: 확인일 2026-10 · 근거: `table-sim/<비공개>`, `/code/Projects/devplorer/.claude/research/interpreter-survey.md:73-75,83-86` · 후보: T-45, T-46, T-47, D-F24

- `loadstring` 은 서버 전용이고 `ServerScriptService.LoadStringEnabled`(스크립트로 못 바꿈)가 켜져야 한다. 바이트코드는 싣지 못한다.
- RemoteEvent 로 받은 글을 `loadstring` 에 넣으면 백도어다. 그래서 기본값이 꺼져 있다. 클라이언트가 보낸 바이트코드는 검증할 수 없으므로, 받으려면 소스만 받아 서버가 컴파일한다.
- `getfenv`/`setfenv` 는 그 함수의 환경 최적화를 끈다.
- 빈 환경을 줘도 샌드박스가 아니다. 표준 라이브러리와 문자열 메타테이블은 readonly 로 공유돼 `("x"):rep(2^28)` 가 진짜 `string.rep` 에 닿아 메모리를 256MB 쓴다. `debug.info(level, "f")` 는 호스트 함수를 건넨다.
- 스크립트 타임아웃: Studio 10초(설정 가능). 라이브는 약 20초라는 2018년 비공식 글뿐이다(근거 낡음). `ScriptContext:SetTimeout` 은 PluginSecurity 다. 스크립트별 메모리 한도는 없고 서버 전체 한도가 있다(6.25GiB + 100MiB×최대 접속자, 2026-10 문서).
- Script Capabilities(Sandboxed 컨테이너)는 실험 기능(`Workspace.SandboxedInstanceMode = Experimental`)이다. API 접근만 막고 CPU·메모리는 다루지 않는다. 안에서 `getfenv`/`setfenv` 를 못 쓴다.

mock 흉내: readonly 공유와 `string.rep` 경로는 luau CLI 에서도 같다. 타임아웃·Capabilities 는 엔진 전용.

## §8 Luau 로 쓴 인터프리터
status: described (원천 실측, Fiu `fa1983d` 기준) · last-confirmed: 2026-10-20 · 근거: `/code/Projects/devplorer/.claude/review/2026-10-20-interpreter.md:36-47,69-83,134-142`, `table-sim/<비공개>`, `/code/Projects/devplorer/.claude/research/interpreter-survey.md:22-24,39-41,55-58` · 후보: D-R20

- `loadstring` 없이 사용자 코드를 돌리려고 Luau 로 쓴 바이트코드 인터프리터(Fiu)와 컴파일러(LuauCeption)를 쓰는 길이 있다.
- 시간 훅은 CALL·RETURN·JUMPBACK·FORLOOP 에서만 불린다. 네이티브 호출 하나(`string.rep(2^30)`, 역추적이 큰 패턴, 큰 `table.sort`)는 끊지 못한다.
- 네이티브보다 11~109배 느리다(`--codegen` 대비 6~82배). LuauCeption 은 괄호 250겹 508바이트 입력에 60초를 넘겼다. 3MB 컴파일러의 require 는 0.3초.
- `pcall(loadstring, "return 1")` 로 `LoadStringEnabled` 를 감지할 수 있다.

mock 흉내: luau CLI 로 재현된다(엔진 무관).

## §9 LogService
status: described (원천 실측, Studio Play 2026-10-19, 모드 미기재) · 근거: `/code/Projects/devplorer/.claude/review/2026-10-19-server-logs-remote.md:22-51,140-162,267-268` · 후보: D-R53

- 서버의 `print` 도 `LogService.MessageOut` 으로 모인다.
- 에러의 "Stack Begin"/"Stack End" 와 "Script '…', Line N" 은 **따로 오는 줄**이다. 직전 에러 줄에 이어 붙여야 한 건이 된다.
- 연결 전 기록은 `GetLogHistory()` 로 채운다.

mock 흉내: 해당 없음.

## §10 게시와 외부 도구(Open Cloud, Rojo, 패키지)
status: described (Rojo 는 원천 로컬 실측, 나머지 문서 인용) · last-confirmed: 확인일 2026-10, Rojo 7.7.0, pesde 0.7.x · 근거: `table-sim/<비공개>`, `/code/Projects/devplorer/.claude/research/devexplorer-review.md:5,21-22`, `/code/Projects/tbox/CLAUDE.md:34-37`, `/code/Projects/devplorer/.claude/review/2026-11-04-server-split.md:8`, `/code/Projects/stl-luau-doctor/.claude/base/architecture.md:24-34` · 후보: T-51, T-52, T-53, D-F25, X-07

- Open Cloud Place Publishing API 는 EditableImage·EditableMesh·PartOperation·SurfaceAppearance·BaseWrap 이 든 플레이스를 갱신하지 못한다. 그런 플레이스는 Studio 에서 게시한다.
- Open Cloud Luau Execution: 스크립트 4MB, 실행 5분, 플레이스당 미완료 10개, 생성 5회/분. 물리가 돌지 않고 Script 가 자동 실행되지 않으며 데이터모델 변경은 저장되지 않는다. DataStore 는 쓸 수 있다. 게시된 버전이 대상이다.
- Rojo 7.7: 프로젝트 루트 밖 `$path` 로 빌드·sourcemap 이 된다. 없는 `$path` 는 에러, 빈 디렉터리는 괜찮다. `.jsonc` 와 정식 `syncback` 은 7.7.0 부터. `servePlaceIds` 로 받을 플레이스를 거른다(luau-roblox `studio-mcp.md` §4).
- 툴박스 모델의 `PackageLink.AutoUpdate = true` 는 공급망 위험이다. rbxm 은 Lune 으로 풀어 소스만 읽어 검사할 수 있다.
- pesde 패키지 이름의 이름 부분은 소문자·숫자·`_` 만 된다. 설치된 패키지 폴더 이름도 소문자다. 그래서 코드가 자기 루트를 이름으로 찾지 말고 `script.Parent` 를 모듈 로드 때 보관해 쓴다(roblox-engine `require-in-roblox.md` §3).

mock 흉내: 해당 없음.

---

## 정정

| 원천 경로:줄 | 틀린 서술 | 맞는 것 | 근거 |
|---|---|---|---|
| `/code/Projects/devplorer/.claude/review/2026-10-19-server-security.md:190` (S-08 본문) | DataStore 쓰기 예산은 서버 전체가 공유하는 "분당 60 + 플레이어 수 × 10" | 2026-10 문서 기준 서버 기본값은 `60 + 플레이어×40`(Write), experience 전체는 `300 + CCU×20` 이고 2026-07-29 부터 Open Cloud 와 공유한다. 원천이 옛 예산을 인용했다(모순은 날짜 차이로 판정) | `table-sim/<비공개>` (audit/09 §6 #8) |

## 미판정

| 주장 | 갈린 서술 | 재현 절차 |
|---|---|---|
| 미게시 Studio 파일에서 MemoryStore 를 쓸 수 있나 (audit/09 §6 #17) | `/code/Projects/table-sim/.claude/conventions.md:153` "미게시 플레이스에서는 실측할 수 없다" 대 `table-sim/<비공개>` "동작, 미게시는 문서에 없음" | 1) 게시한 적 없는 새 플레이스를 Studio 로 연다. 2) Play(Server)에서 `pcall(function() return game:GetService("MemoryStoreService"):GetSortedMap("probe"):SetAsync("k", 1, 30) end)` 결과를 돌려받는다. 3) 같은 코드를 게시된 테스트 플레이스(Studio 접근 켬)에서 돌린다. 4) 에러 문구와 함께 기록한다 |
| `JSONEncode` 가 혼합·희소·inf 키, 잘못된 UTF-8 을 어떻게 다루나 (audit/09 §6 #14) | 같은 저장소 안 세 서술: `shared-specs.md:47` "거부한다고 알고 있다(추정)", `server-security.md:211-212` "미실측", `server-round6.md:248` "조용히 다른 모양으로 바꿀 수 있다" | 1) 아무 플레이스의 Edit DataModel 에서 `HttpService:JSONEncode` 를 `pcall` 로 부른다. 2) 입력: `{1,2,a=3}`, `{[0]=1}`, `{[-5]=1}`, `{[1]=1,[3]=3}`, `{[math.huge]=true}`, `{"\255"}`. 3) 각 결과(성공 문자열 또는 에러 문구)를 표로 돌려받는다. 4) 성공한 것은 `JSONDecode` 로 왕복해 모양이 바뀌는지 본다 |
| 라이브 스크립트 타임아웃 값 | 2018년 비공식 글의 "약 20초"뿐 | 게시 서버에서 `while true do end` 를 돌리는 Script 의 에러 시각을 LogService 로 남긴다(테스트 전용 experience 에서만) |
