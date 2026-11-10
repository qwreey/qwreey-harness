# api-docs — Roblox API 문서 찾기

## 이 파일이 답하는 질문
- Q1 Roblox API 문서를 어디서, 어떤 URL 로 읽나?
- Q2 페이지 주소를 모를 때는?
- Q3 404 가 나면 문서가 없는 것인가?
- Q4 WebFetch 와 Studio MCP `http_get` 중 무엇을 쓰나?

## 목차
- §1 규칙
- §2 인덱스와 검색
- §3 URL 패턴
- §4 도구 선택

---

## §1 규칙
status: verified · last-confirmed: 2026-11-10 (`https://create.roblox.com/docs/llms.txt` 머리 "For Code Agents: Start Here", 검색 API 와 `.md` 페이지 curl 실측)

- **URL 을 추측하지 않는다.** llms.txt 는 "어느 인덱스에도 없는 경로는 존재하지 않는다"고 한다. 경로는 인덱스나 검색 결과에서 가져온다.
- **문서 URL 에 `.md` 를 붙이면 마크다운이 온다.** 링크를 따라갈 때도 `.md` 를 유지한다.
- **404 는 경로가 틀렸다는 뜻이다.** 주제가 문서화되지 않았다는 뜻이 아니다. 경로를 바꿔 가며 다시 시도하지 말고 검색한다(없는 클래스 `.md` 는 404, 실측).
- 전체 텍스트 파일 `/docs/llms-full.txt` 는 한 번에 읽지 않는다. 컨텍스트를 다 쓴다. 사이트 인덱스 `llms.txt` 도 약 187KB 라 하위 인덱스를 먼저 쓴다.
- 기억으로 API 동작을 단정하지 않는다. 문서도 동작을 다 말해 주지 않으므로, 순서·시점처럼 문서에 없는 것은 Studio 실측으로 간다(`env-dependence.md`).

## §2 인덱스와 검색
status: verified · last-confirmed: 2026-11-10

| 무엇 | URL |
|---|---|
| 사이트 인덱스 | `https://create.roblox.com/docs/llms.txt` |
| 엔진 API 인덱스(클래스·데이터 타입·enum·전역·라이브러리, 한 줄 요약) | `https://create.roblox.com/docs/reference/engine/llms.txt` |
| Open Cloud 인덱스 | `https://create.roblox.com/docs/cloud/llms.txt` |
| 검색 | `https://create.roblox.com/docs/api/search?q=<퍼센트 인코딩한 질문>` |

- 검색은 JSON 을 돌려준다(`results[].title/url/summary/type`). 예: `q=task%20defer%20order` → "Task scheduler", "Deferred engine events"(`/docs/en-us/scripting/events/deferred.md`) 등. 요청이 잘못돼도 `results` 가 빈 배열로 오므로 `error` 필드를 확인한다.
- 엔진 인덱스에는 메서드·속성 단위 항목이 없다. 관련 클래스를 찾은 뒤 그 클래스 페이지를 읽는다.

## §3 URL 패턴
status: verified · 원천: Studio 내장 skill `rbx-docs-search` (2026-11-10 열람), `task.md` 200 실측

이름은 Roblox API 이름과 정확히 같은 PascalCase 다. 확실하지 않으면 §2 인덱스로 먼저 확인한다.

| 종류 | URL |
|---|---|
| 클래스 | `https://create.roblox.com/docs/reference/engine/classes/<ClassName>.md` |
| 데이터 타입 | `…/reference/engine/datatypes/<TypeName>.md` |
| Enum | `…/reference/engine/enums/<EnumName>.md` |
| 전역 | `…/reference/engine/globals/<GlobalName>.md` |
| 라이브러리 | `…/reference/engine/libraries/<LibName>.md` (예: `libraries/task.md`) |
| 사용 중지 API | `…/reference/engine/deprecated.md` |
| 가이드 | `https://create.roblox.com/docs/<path>.md` (경로는 인덱스·검색에서) |

- 상속된 멤버는 부모 클래스 페이지에 있다(예: `Anchored` 는 `BasePart`).
- 엔진 API 페이지가 가이드로 링크하면 그 가이드 `.md` 도 읽는다.

## §4 도구 선택
status: verified (도구 제약) · last-confirmed: 2026-11-10

| 도구 | 쓸 때 | 제약 |
|---|---|---|
| Claude Code `WebFetch` (또는 `curl`) | Studio 가 없어도 된다. 검색 API JSON 도 읽는다 | 큰 페이지는 잘린다. `offset` 으로 이어 읽는다 |
| Studio MCP `http_get` | Studio 가 연결돼 있을 때. `query` 로 일치하는 절만 받아 컨텍스트를 아낀다(`context_lines`, `return_full`) | URL 이 `.md` 나 `llms.txt` 로 끝나야 한다. create.roblox.com/docs 와 github.com/Roblox/libmp 만 허용된다. 검색 API(`/docs/api/search`)는 허용 패턴에 맞지 않는다. `studio_id` 가 필요하다(읽기 전용) |

- 결과를 references 에 남길 때는 페이지 URL 과 문서의 `last_updated` 를 함께 적는다.
