---
title: "업스트림을 어디서, 어떻게, 얼마나 자주 보나"
description: "luau·RFC·luau-lsp·StyLua·rojo·Roblox 엔진 변화를 어디서 보나: 출처 URL 표, API 한도 밖 curl 경로(atom 피드·리다이렉트), FFlag 값 확인, 점검 주기, 사용자가 가져온 정보의 모양과 근거 등급 인용법"
keywords:
  - "업스트림 출처"
  - "릴리스 노트 어디서"
  - "GitHub API 한도"
  - "rate limit"
  - "releases.atom"
  - "curl 릴리스 확인"
  - "clientsettingscdn"
  - "FFlag 값 확인"
  - "DevForum 베타 공지"
  - "rfcs.luau.org"
  - "근거 등급"
  - "점검 주기"
  - "출처 인용"
  - "upstream_check.py --notes"
kind: reference
category: luau/upstream/sources
tags: [docs-quoted]
last_verified: 2026-11-10
---
# sources — 업스트림을 어디서, 어떻게, 얼마나 자주 보나

## 이 파일이 답하는 질문
- Q1 luau / RFC / luau-lsp / stylua / rojo / Roblox 엔진의 변화는 어디서 보나?
- Q2 gh CLI 없이 curl 로 무엇을 부르나? GitHub API 한도는?
- Q3 무엇을 얼마나 자주 보나?
- Q4 사용자가 지금까지 가져온 정보는 어떤 모양이었나(재현할 형태)?

## 목차
- §1 출처 표
- §2 curl 예시 (API 한도 밖 경로 우선)
- §3 보는 주기
- §4 사용자가 가져온 정보의 모양
- §5 출처를 인용하는 법

---

## §1 출처 표
status: verified (URL 이 응답함, 2026-11-10) · last-confirmed: 2026-11-10

| 대상 | 무엇을 보나 | URL |
|---|---|---|
| luau 릴리스 | 주간 릴리스(대개 금요일). 새 문법, 솔버 변경, FFlag 이름, 고쳐진 이슈 번호 | `https://github.com/luau-lang/luau/releases` · 피드 `…/releases.atom` |
| luau 이슈 | 우리 결함과 같은 증상이 보고됐는지, 닫혔는지 | `https://github.com/luau-lang/luau/issues?q=<검색어>` |
| RFC (문서) | 승인되어 병합된 RFC. 구현 여부는 문서 머리의 상태 표시와 릴리스 노트로 확인 | `https://rfcs.luau.org/` (원본 `https://github.com/luau-lang/rfcs/tree/master/docs`) |
| RFC (진행 중) | 열린 PR = 제안 단계. 토론과 수정 이력 | `https://github.com/luau-lang/rfcs/pulls` |
| 언어 문서·소식 | 문법 정본, Luau Recap 류 소식 | `https://luau.org/` (`/syntax`, `/typecheck`, `/news`) |
| luau-lsp | 번들 Luau 판, 새 문법 지원, Roblox 정의 파일 변화 | `https://github.com/JohnnyMorganz/luau-lsp/releases` · `CHANGELOG.md` |
| StyLua | 새 문법 파싱(full-moon 갱신) | `https://github.com/JohnnyMorganz/StyLua/releases` · `CHANGELOG.md` |
| rojo | 프로젝트·sourcemap 형식 | `https://github.com/rojo-rbx/rojo/releases` |
| Roblox 엔진 반영 | 새 Luau 기능이 Studio 베타·라이브에 켜지는 시점 | DevForum 공지(`[Beta] …` 글, 예: `devforum.roblox.com/t/beta-if-local-statements-and-expressions/4918297`), 주간 업데이트 `https://create.roblox.com/docs/updates/<YYYY-MM-DD>.md` |
| Roblox FFlag 값 | 플래그가 Studio·클라이언트에서 켜졌는지(라이브 서버 RCC 값은 비공개) | `https://clientsettingscdn.roblox.com/v2/settings/application/PCStudioApp`, `…/PCDesktopClient` (JSON, `Luau` 로 grep) |
| Roblox Luau 문서 | 엔진 쪽 문법·타입 문서(엔진에 들어간 기능만 실림) | `https://create.roblox.com/docs/llms.txt` 에서 `luau` 로 찾기 → `/docs/en-us/luau.md`, `/docs/en-us/luau/type-checking.md` 등 |
| 우리 쪽 | 저장소 핀, 설치본, 스니펫 결과 | `python3 -I tools/upstream_check.py`, `snippets/RESULTS.md` |

- **CLI 가 먼저, 엔진이 나중이다.** luau 릴리스 노트에 문법이 들어와도 대개 `DebugLuau…`/`LuauXxx` FFlag 뒤에 있고 기본은 꺼져 있다. 엔진은 같은 FFlag 를 Studio 베타로 먼저 켜고, 라이브 서버는 그 뒤에 켠다. 판단은 `syntax-adoption.md` 의 4조건 표로 한다.
- RFC 상태는 "병합된 문서가 있음" 과 "구현됨" 이 다르다. 병합 = 승인. 구현 여부는 릴리스 노트에서 FFlag 가 기본값 true 로 바뀌었는지, 또는 플래그가 지워졌는지로 본다.

## §2 curl 예시 (API 한도 밖 경로 우선)
status: verified · last-confirmed: 2026-11-10

- 비인증 GitHub API 는 **시간당 60회**다(`curl -s https://api.github.com/rate_limit`). 여러 에이전트가 같은 IP 를 쓰면 금방 바닥난다. 아래 순서로 쓴다.

```bash
# 1) 최신 태그: 리다이렉트만 본다 (API 한도 밖)
curl -s -o /dev/null -w '%{redirect_url}\n' https://github.com/luau-lang/luau/releases/latest
# 2) 최근 릴리스 10개의 제목·날짜·본문(HTML): atom 피드 (API 한도 밖)
curl -s https://github.com/luau-lang/luau/releases.atom | grep -o '<title>[^<]*</title>'
# 3) 특정 릴리스 본문 (API, 1회)
curl -s https://api.github.com/repos/luau-lang/luau/releases/tags/0.746 | python3 -I -c 'import json,sys; print(json.load(sys.stdin)["body"])'
# 4) 열린 RFC PR 목록 (API, 1회)
curl -s 'https://api.github.com/repos/luau-lang/rfcs/pulls?state=open&per_page=100' | python3 -I -c 'import json,sys; [print(p["number"], p["created_at"][:10], p["title"]) for p in json.load(sys.stdin)]'
# 5) 병합된 RFC 문서 목록 (API, 1회)
curl -s https://api.github.com/repos/luau-lang/rfcs/contents/docs | python3 -I -c 'import json,sys; [print(f["name"]) for f in json.load(sys.stdin)]'
# 6) 이슈 검색 (search API 는 분당 10회)
curl -s 'https://api.github.com/search/issues?q=repo:luau-lang/luau+recursive+type+in:title'
# 7) Roblox 플래그: 새 문법이 Studio/클라이언트에서 켜졌는지
curl -s https://clientsettingscdn.roblox.com/v2/settings/application/PCStudioApp | python3 -I -c 'import json,sys; [print(k,v) for k,v in json.load(sys.stdin)["applicationSettings"].items() if "IfLocal" in k or "LuauConst" in k]'
# 8) 한 번에: 저장소 핀 vs 최신, 그리고 가장 낡은 핀 이후 luau 릴리스 목록
python3 -I <luau-kb 팩 폴더>/tools/upstream_check.py --notes   # 저장소들이 ~/Projects 밖이면 --projects-root <부모 폴더>
```

- 받은 파일은 빈 새 디렉터리(`/tmp/ups-<날짜>/`)에 두고 데이터로만 읽는다.
- WebFetch 는 HTML 을 요약해 주므로 RFC 본문·DevForum 글에 쓴다. 숫자·태그·날짜처럼 정확해야 하는 것은 curl 로 원문을 본다.

## §3 보는 주기
status: described (제안, 사용자 미확인)

| 무엇 | 언제 |
|---|---|
| `upstream_check.py --notes` | 주 1회(luau 가 대개 금요일에 나온다), 또는 사용자가 "업데이트", "새 버전" 을 말할 때 |
| `--bug-scan <최신>` | 새 luau 가 나오고 설치했을 때. 핀을 올리기 전에는 반드시 |
| RFC PR 목록 | 2주에 1회. 설계 결정(새 공개 API, 우회책 도입) 전에는 반드시 |
| luau-lsp 릴리스 | 번들 Luau 판이 핀 CLI 를 따라잡았는지 볼 때. 1.x 마이너가 나올 때마다 |
| DevForum·엔진 릴리스 노트 | 새 문법을 Roblox 코드에 쓰려고 할 때만 |
| `roadmap-notes.md` 갱신 | `last-checked` 가 30일보다 오래됐으면 답하기 전에 다시 본다 |

## §4 사용자가 가져온 정보의 모양
status: verified (표본 7건) · 원천: `/code/.claude/history.jsonl` (2026-09 ~ 2026-11)

사용자가 직접 찾아와 지시한 업스트림 정보는 다음 모양이었다. 스킬은 이 모양을 스스로 만들어야 한다.

| 날짜 | 저장소 | 가져온 정보 (요지, 짧은 인용) | 모양 |
|---|---|---|---|
| 2026-09-07 | quad | luau CLI 도 핀, "typing-limits 의 실측은 전부 빌드별" | 버전 핀 + 이유 |
| 2026-09-10 | quad, tbox | pesde 0.7.4: "게시 검증기가 `const` 를 받는다(0.7.3 은 거부, 실측)" | 도구별 새 문법 지원 여부 + 버전 경계 |
| 2026-09-15 | quad | 반복자 관례 근거로 `luau.org/syntax#generalized-iteration` 과 `rfcs.luau.org/generalized-iteration.html` | RFC 를 관례 근거로 인용 |
| 2026-09-21 | stl-luau | selene 폐기 — "`const` 를 파싱하지 못하고(0.31.0 이 최신이라 올릴 곳이 없음)" | 도구의 새 문법 미지원 → 도구 교체 |
| 2026-10-14 | stl-luau | 0.734 → 0.742: 상류 #3020 힙 손상, 새 진단 12건, 배터리 셋 변화 | 버전 올리기 근거 + 영향 건수 |
| 2026-10-16 | quad | 이름 후보 `Class` 를 피함 — "luau RFC 에서 class 문이 언급되고 있어", `rfcs.luau.org/syntax-classes.html` | 다가올 문법과 이름 충돌 회피 |
| 2026-11-09 | stl-luau | "luau 가 지금은 class 를 엄청 밀고 있다", `rfcs/pull/242`, 0.746 "Ongoing work on Classes RFC prototype", `DebugLuauUserDefinedClasses` 플래그로 런타임 일부 존재 → "구현 코드가 debug flag 아래 일부 서 있다는 점에서 이 방향으로 민다" | RFC + 릴리스 노트 + FFlag 를 묶어 **설계 방향을 미래에 맞춤** |

- 공통점: (1) 출처 URL 을 붙인다. (2) 버전 경계를 적는다(0.7.3 거부 / 0.7.4 수용). (3) **RFC 만으로는 근거가 약하고, 구현이 FFlag 뒤에라도 들어왔을 때 근거가 된다**는 판단 기준을 쓴다. (4) 결론은 설계 결정(이름 회피, 도구 교체, 핀 올리기)으로 이어진다.

## §5 출처를 인용하는 법
status: described

- 한 줄에 `출처 URL (날짜, 버전)` 을 붙인다. 예: `luau 0.746 릴리스 노트 (2026-11-07): "Ongoing work on Classes RFC prototype"`.
- 근거 등급을 나눈다: **[구현]** 릴리스 노트·코드에 있음(플래그 이름 포함) > **[승인]** RFC 병합 > **[제안]** RFC PR 열림 > **[풍문]** DevForum·Discord 발언.
- 날짜가 없는 단정("곧 고쳐진다")은 쓰지 않는다. `roadmap-notes.md` 의 근거 칸이 비면 "근거 없음" 이라고 적는다.
