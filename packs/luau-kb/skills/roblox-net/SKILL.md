---
name: roblox-net
description: >-
  Roblox client-server and services: RemoteEvent, RemoteFunction and BindableEvent rules, validating client input,
  replication, network ownership, streaming, DataStore, MemoryStore, product receipts. Use when designing remotes or
  writing DataStore or purchase code. 트리거: RemoteEvent 검증, DataStore 저장, 영수증.
---
# roblox-net

"서버와 클라이언트 사이, 그리고 Roblox 플랫폼 서비스는 실제로 어떻게 동작하나"를 다룬다. 원천은 형제 저장소의 Studio 실측과 보안 리뷰, 공식 문서다(대부분 `status: described`). 시그널·Instance·task 같은 핵심 런타임은 roblox-engine, mock·Studio MCP 절차는 luau-roblox, 문서 조회는 roblox-docs 다.

## 결정 트리
1. 클라이언트에서 온 값인가? 그렇다면 **복제되는 것은 공개, 서버가 다시 검사한다**가 출발점이다. → `references/remotes-and-replication.md` §1, §5
2. 값이 경계를 건너며 바뀌었나(메타테이블, 혼합 키, NaN, Instance 참조)? → 같은 파일 §2–4
3. 보이지 않거나 늦게 보이나(복제 범위, 스트리밍, 실행 문맥)? → 같은 파일 §7, §10
4. 서비스 한도·의미(DataStore, MemoryStore, 상품)나 Studio 에서 어떻게 시험하나? → `references/platform-services.md` §1–4
5. 한도·보안 수치는 날짜와 정책에 따라 바뀐다. 결정에 쓰기 전에 roblox-docs `search` 로 문서의 현재 값을 확인한다.

## 라우팅
| 상황 / 질문 | 읽을 곳 |
|---|---|
| 원격 설계 원칙, 서버 검사 | `references/remotes-and-replication.md` §1 |
| RemoteEvent·RemoteFunction 인자가 서버에서 달라졌다(메타테이블·키 소실) | `references/remotes-and-replication.md` §2 |
| BindableEvent 인자 복사, Instance 참조가 경계를 건널 때 | `references/remotes-and-replication.md` §3–4 |
| 원격 값 검증 순서(깊이·순환·NaN·±inf·크기), CFrame 같은 데이터 타입 함정 | `references/remotes-and-replication.md` §5 |
| 원격 한도, 연결 전 큐, DoS 예산 | `references/remotes-and-replication.md` §6 |
| 복제 경계, 스크립트 실행 문맥(서버·클라이언트·RunContext), 플레이어 식별 | `references/remotes-and-replication.md` §7–8 |
| 네트워크 소유권, StreamingEnabled 와 복제 범위 | `references/remotes-and-replication.md` §9–10 |
| DataStore 한도·의미, Studio 에서의 데이터 서비스 | `references/platform-services.md` §1–2 |
| MemoryStore·MessagingService, 게임 패스·개발자 상품 | `references/platform-services.md` §3–4 |
| 글자 필터·RichText·로그 위조, `JSONEncode` 의 표 모양 | `references/platform-services.md` §5–6 |
| `loadstring`·샌드박스, Luau 로 쓴 인터프리터, LogService | `references/platform-services.md` §7–9 |
| 게시, Open Cloud, Rojo, 패키지 | `references/platform-services.md` §10 |
| RemoteFunction 동시 요청 경쟁, `InvokeClient` 시한 | roblox-engine `tasks-and-threads.md` §5–6 |
| 바인더블 인자 복사 비용 | roblox-engine `perf.md` §4 |

## 자주 밟는 함정 (요약)
- 원격을 건넌 표는 사본이다. 메타테이블과 함수가 떨어지고, 프록시 표는 빈 표가 된다. 클래스 객체를 그대로 넘기지 않는다.
- 클라이언트가 보낸 값은 서버가 타입·범위·권한을 다시 검사한다. 클라이언트가 소유한 파트의 위치·속도 변경은 서버로 복제된다.
- 같은 값 쓰기는 복제되지 않는다. 앵커되지 않은 파트는 엔진이 근처 플레이어에게 소유권을 준다(`SetNetworkOwner(nil)` 로 고정).
- 서버의 `InvokeClient` 는 클라이언트가 답하지 않으면 서버 스레드를 붙잡는다(roblox-engine `tasks-and-threads.md` §6).
- Studio 의 DataStore 는 게시된 experience 와 Studio API 접근이 필요하고, 프로덕션과 같은 저장소에 쓴다. 시험용 experience 를 따로 둔다.
