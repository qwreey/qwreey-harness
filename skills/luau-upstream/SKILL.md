---
name: luau-upstream
description: >-
  빠르게 바뀌는 Luau 생태계(luau 주간 릴리스, luau-lang/rfcs, luau-lsp, StyLua, rojo, Roblox 엔진의 FFlag
  반영)를 관찰해 다가올 변화에 대비하게 하는 지식과 절차다. luau-kb 에 기록된 타입 한계·결함을 그것을 고칠
  업스트림 항목(RFC, 이슈, 릴리스 노트)과 연결한 감시 목록, 새 문법(class, if local, while local, const 등)의
  채택 판정표(CLI·luau-lsp·stylua·Studio/라이브 4조건), 버전 올리기 절차와 bug-scan(고쳐진 결함·새 실패 감지),
  진행 중인 큰 변화의 요약을 담는다. luau·luau-lsp·stylua 버전을 올릴지 정할 때, 업데이트 뒤 진단이
  바뀌거나 코드가 깨졌을 때, 새 문법이나 RFC 를 지금 써도 되는지 물을 때, "이 한계는 곧 고쳐지나",
  "업스트림에서 해결 중인가" 를 물을 때, 타입 한계를 피하는 우회책을 설계하거나 영구 코드로 남길지 정할 때,
  릴리스 노트·RFC·DevForum 소식을 확인하라는 요청을 받았을 때 쓴다. 한계 자체의 설명은 luau-types, 검사 도구
  사용법은 luau-verify 스킬에 있다.
---
# luau-upstream

Luau 는 매주 릴리스되고, 문법(`const`, `class`, `if local`)과 타입 솔버가 계속 바뀐다. 이 스킬은 "지금 아는 한계" 를 "업스트림이 그것을 어떻게 다루고 있는가" 와 이어서, 답과 설계가 다음 릴리스에서 낡지 않게 한다.

## 먼저 지킬 원칙
1. **기억으로 답하지 않는다.** 버전·상태는 빨리 낡는다. `roadmap-notes.md` 의 `last-checked` 가 30일보다 오래됐거나 질문이 "최신" 을 묻으면 `sources.md` 대로 다시 본다. 최소한 `python3 -I tools/upstream_check.py --notes` 를 돌린다.
2. **근거 등급을 붙인다.** [구현] 릴리스 노트·FFlag > [승인] 병합된 RFC > [제안] 열린 RFC PR > [풍문]. 날짜 없는 "곧 고쳐진다" 는 쓰지 않는다.
3. **고쳐졌는지는 돌려 보고 말한다.** 새 luau 를 설치했다면 `--bug-scan <ver>` 로 스니펫을 돌린다. 이슈가 닫혔어도 우리 모양은 안 고쳐졌을 수 있다(예: #2733).
4. **CLI 에 들어온 것 ≠ Roblox 에서 쓸 수 있는 것.** luau CLI 는 `Luau*` 플래그를 스스로 다 켜서 "experimental" 문법도 그냥 돈다. 엔진은 Studio 베타(옵트인) → 라이브 순으로 몇 주~몇 달 늦게 켠다. 버그 수정은 0–1주로 거의 같이 간다.
5. **설치는 사용자 판단, 핀은 각 저장소의 몫이다.** 전역 mise 설정과 저장소 `mise.toml` 은 고치지 않는다. 바꿀 것은 인계 문서로 남긴다(D-05, 제안 상태).

## 결정 트리
- **"이 한계는 곧 고쳐지는가?"**
  1. `references/watchlist.md` 에서 그 한계의 행을 찾는다(없으면 luau-types `solver-limits.md` §2 의 S 번호로 찾는다).
  2. 연결된 업스트림 항목의 현재 상태를 확인한다(이슈 열림/닫힘, RFC 단계, 릴리스 노트). 방법은 `sources.md` §2.
  3. 최신 luau 가 설치돼 있으면 `--bug-scan` 으로 그 스니펫이 뒤집혔는지 본다.
  4. 답: "고쳐짐(버전, 실측)" / "진행 중(근거 등급 + 날짜)" / "추적 항목 없음". 예상 시점은 근거가 있을 때만 말한다.
- **"새 문법을 지금 써도 되는가?"** → `references/syntax-adoption.md`
  1. 코드가 Roblox 엔진에서 도는가? 그렇다면 4조건(CLI, luau-lsp, stylua, Studio/라이브)이 모두 필요하다.
  2. 순수 luau(CLI) 라이브러리라면 CLI·luau-lsp·stylua 3조건, 그리고 소비자 저장소의 핀.
  3. FFlag 뒤에만 있으면(기본 꺼짐) **쓰지 않는다**. 대비(이름 충돌 회피, 설계 방향 맞추기)만 한다.
  4. 채택 정책은 사용자 확인 전이다. 판정표를 보여 주고 결정은 사용자에게 묻는다.
- **"버전을 올려도 되는가?"** → `references/version-bump.md`
  - 설치 → bug-scan → 뒤집힘(고쳐짐 후보, 새 에러 가능)과 새 실패(깨짐 후보)를 분류 → luau-kb `last-confirmed` 갱신 → 저장소별 인계.
  - luau-lsp 는 번들 Luau 판이 따로다. 정의 파일과 짝인 저장소는 함께 올린다.
- **"우회책을 영구 코드로 박아도 되는가?"** → `references/watchlist.md` 의 수명 칸
  - 업스트림이 [구현]/[승인] 으로 고칠 예정 → **임시**. 우회 자리에 추적 링크와 스니펫 이름을 주석으로 남긴다. 스니펫의 `bug-present` 가 고쳐짐을 알려 준다.
  - 추적 항목이 없거나 [제안] 뿐 → 영구로 둬도 되지만, 그 우회가 공개 API·타입을 비트는 것이면 안 된다(luau-types 원칙 3).
  - 고쳐지면 **코드 변경 없이 풀리는** 한계(예: 재귀 타입 제한 완화)는 우회 장치를 미리 심지 않는다.
- **"업데이트 뒤 깨졌다"**
  1. 어느 도구가 바뀌었나: luau CLI, luau-lsp(번들 Luau), stylua, Roblox 엔진(Studio 업데이트)?
  2. 두 버전으로 `--bug-scan <new> --base <old>` 를 돌리고 최소 재현을 만든다.
  3. 릴리스 노트에서 관련 FFlag 이름과 "Fix"/"New Solver" 항목을 찾는다(`roadmap-notes.md` §1 표).
- **"앞으로 무엇이 바뀌나"** → `references/roadmap-notes.md` (날짜·출처 포함, 빨리 낡음)

## 질문 → 파일 라우팅
| 질문 / 상황 | 읽을 곳 |
|---|---|
| 어디서 무엇을 보나, curl·API 한도, 주기 | `references/sources.md` |
| 알려진 한계 ↔ 업스트림 항목, 우회책 수명, bug-scan 결과 | `references/watchlist.md` |
| `class`, `if local`, `while local`, `const` 등을 써도 되나 | `references/syntax-adoption.md` |
| luau / luau-lsp / stylua 올리기, 깨짐·고쳐짐 분류, 인계 문서 | `references/version-bump.md` |
| 진행 중인 큰 변화(class 와 재귀 타입, 솔버, type function) | `references/roadmap-notes.md` |
| 한계 자체의 설명과 재현 | luau-types 스킬 |
| 검사기·하네스·mise 경로 | luau-verify 스킬 (`toolchain.md`) |

## 도구
```bash
cd /code/Projects/luau-kb
python3 -I tools/upstream_check.py --notes              # 저장소 핀 vs 최신, 낡은 핀 이후 릴리스
python3 -I tools/upstream_check.py --bug-scan 0.746     # 설치된 버전으로 스니펫 재검사, 3분류
```
설치돼 있지 않으면 도구가 `mise install luau@<ver>` 명령을 안내하고 멈춘다. 설치할지는 사용자에게 묻는다.

## 답할 때
- 버전, 날짜, 근거 등급, 출처 URL 을 함께 말한다.
- 사용자가 직접 찾아오던 모양(RFC 링크 + 릴리스 노트 문구 + FFlag 이름 → 설계 함의)으로 정리한다. `sources.md` §4.
- 새로 확인한 사실은 `watchlist.md`·`roadmap-notes.md` 를 고치고 `last-checked` 를 올린다.
