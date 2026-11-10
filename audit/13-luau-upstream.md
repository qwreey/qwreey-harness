# 13. luau-upstream — 업스트림 관찰 스킬과 현재 상태

> 작성 2026-11-10. 결과물: `luau-kb/skills/luau-upstream/`(SKILL.md + references 5개), `luau-kb/tools/upstream_check.py`, `home/MANIFEST` 링크 한 줄.
> 조사 출처: luau·luau-lsp·StyLua·rojo 릴리스(태그 페이지, atom 피드), luau-lang/rfcs master 와 열린 PR, luau 이슈(API 약 10회), Roblox 주간 업데이트, DevForum, clientsettingscdn FFlag. 실측은 이 머신의 luau 0.734/0.742/0.746, luau-lsp 1.69.0/1.70.1, stylua 2.5.2/2.6.0 으로 했다.
> 설치: `mise install luau@0.746`, `mise install stylua@2.6.0`(문법 파싱 확인용). 전역 설정과 저장소 `mise.toml` 은 바꾸지 않았다. 단, mise 의 `installs/luau/{latest,0}` 링크는 0.746 으로, `installs/stylua/{latest,2}` 링크는 2.6.0 으로 옮겨졌다. 이 링크를 직접 부르는 곳은 없었다(전역 config 에 luau·stylua 없음).

## 1. 최신 버전 대 우리 핀

`python3 -I tools/upstream_check.py --notes` 출력:

| 저장소 | luau | luau-lsp | stylua | rojo |
|---|---|---|---|---|
| **최신** | 0.746 (11-07) | 1.70.1 (09-27, 번들 luau 0.740) | v2.6.0 (10-10) | v7.7.1 (10-02) |
| quad | 0.734 | 1.70.1 | — | 7.7.0 |
| stl-luau | 0.742 | 1.70.1 | 2.5.2 | — |
| tbox | 0.734 | 1.69.0 | 2.5.2 | — |
| table-sim | 0.734 | 1.69.0 | 2.5.2 | 7.7.0 |
| devplorer | 0.734 | 1.69.0 | 2.5.2 | 7.7.0 |
| moonwave-luau | 0.734 | 1.69.0 | 2.5.2 | — |

- luau 는 0.734 핀이 12판 뒤처졌다(약 3개월).
- luau-lsp 는 1.70.1 이 최신이다. main 에 "Sync to upstream Luau 0.742" 가 있지만 아직 릴리스되지 않았다.

## 2. bug-scan 결과 (0.742 → 0.746, 0.734 → 0.746 도 같음)

| 분류 | 스니펫 | 판정 |
|---|---|---|
| 뒤집힘 (고쳐짐) | `variance-value-phantom-nil` 8행 (S11) | 값 팬텀 `read p: T?` 에 빈 테이블을 넣던 구멍이 막혔다. 넓게 보면, 이미 만든 테이블에 없는 `read x: T?` 필드는 이제 nil 로 읽히지 않는다. 고쳐진 판은 미확인이고, 0.744 의 #2625/#2644 가 후보다 |
| 새 실패 (한계가 풀림) | `variance-intersection-instantiation` 19행 | `{ v: T } & {}` 에서 T 를 정확히 풀게 됐다. 결과의 `.v` 를 `string` 에 넣으면 잡히므로 검사가 꺼진 것은 아니다. 반공변 교집합 꼴은 그대로 남았다 |
| 같음 | 나머지 전부(마지막 실행 138개 중 136개) | — |

- 스니펫 밖에서 찾은 0.746 의 새 진단: stl-luau 게이트를 0.746 으로 읽기 전용 실행했을 때 진단이 0건에서 6건으로 늘었다. 최소 재현은 두 꼴이다.
  - **N1** 함수 반복자와 테이블의 유니온을 순회하면 "is not iterable" 이 난다. #3090 의 의도된 변경이 낳은 위양성 후보다.
  - **N2** type function 몸통에서 `if x == nil then {} else x` 로 고른 값을 순회하면 같은 에러가 난다.
- 고쳐짐 확인 사례: 이슈 #2733(제네릭 몸통 무검사)은 "fixed in 739" 로 닫혔다.
  - 이슈 속 모양(구체 값을 `T` 자리에 넣기)은 0.742 부터 잡힌다.
  - 우리 스니펫의 모양(`T` 값을 구체 자리에 넣기)은 0.746 에서도 bug 다. 이슈가 닫혔다고 우리 결함이 고쳐진 것은 아니다.

## 3. 새 문법 상태 (4조건, 실측 + 엔진 플래그)

| 문법 | luau CLI | luau-lsp 1.70.1 | stylua | Roblox |
|---|---|---|---|---|
| `const` | OK | OK | 2.5.0+ | **라이브** (`FFlagLuauConst2=True`) |
| `if local` | 0.742+ 기본 파싱(실험 표시) | OK | **2.6.0+** | **Studio 베타만** (2026-10-06, 롤아웃 0%) |
| `while local` | 0.746 기본 파싱(0.745 실험) | SyntaxError | 2.6.0 도 실패 | 없음 |
| `class` | `DebugLuau*` 플래그로만 실행. `luau-analyze` 로는 검사 불가 | 플래그를 줘도 "illegal" | 실패 | 없음 |

- 핵심 기제: luau CLI 는 `Luau*` 플래그를 전부 켠다(`CLI/src/Flags.cpp`). 그래서 "experimental" 문법도 CLI 에서는 그냥 돈다. **CLI 에서 된다는 사실은 엔진에서도 된다는 증거가 아니다.**
- 시차는 두 종류다.
  - 솔버 버그 수정: OSS 와 같은 주(0–1주)에 엔진에 들어간다.
  - 새 문법: Debug 플래그 → Experimental 플래그 → Studio 베타 → 정식 순서를 밟는다. `if local` 은 CLI 에서 Studio 베타까지 약 1개월이 걸렸고, 라이브 반영은 아직이다.

## 4. 주목할 RFC
- **#242 classes mega-RFC**(열림, 11-04 갱신): 상속(`open`), 생성자, private 필드를 다룬다. 기본 `syntax-classes` 는 04-27 에 병합됐다. 제네릭 class 는 범위 밖이고, 따로 낼 RFC 는 아직 없다.
- **#238 if local / while local**(열림, beta·prototyping 라벨): 11-02 에 `while` 까지 범위를 넓혔다. 미병합이라 문법이 바뀔 수 있다.
- **relax-recursive-type-restriction**(2025-03 승인, 구현 없음)과 이슈 #2380(열림): 비균일 재귀(S7·S8)를 푸는 정본이다.
- **#11 exact table 닫힘**(10-28): 리터럴의 남는 키 검사는 이 모양으로 오지 않는다. 메인테이너는 반공변 재귀 자기 참조를 막힌 문제로 꼽았다.
- **#269 정수 타입 철회**(10-29): 0.746 이나 0.747 이 마지막이다. 주요 저장소를 grep 해 보니 쓰는 곳이 없어 영향은 없다.
- **#266 제네릭 제약**(초안), **#277 함수 선언 기본 const**(11-09), **#275 try/catch**(11-05).

### class 와 재귀 타입의 관계 (사용자 관찰과 근거 대조)
- "class 도입으로 재귀 타입 해결이 가속되고 있다"는 직접 근거를 업스트림 문서에서 찾지 못했다.
  - class RFC·PR 에는 재귀 타입 언급이 없다.
  - 제네릭 class 는 범위 밖이다.
  - 재귀 제한 완화는 승인 뒤 1년 8개월째 구현이 없고, master 에 제한 코드가 그대로 있다.
- 간접 연결은 있다.
  - class 는 명목 타입이고 상호 참조를 미리 선언해 허용한다. 자기 참조 OOP 타입이 구조적 재귀 별칭을 거치지 않게 된다.
  - shared self types RFC 를 철회하면서 class 가 그 대안이 됐다.
  - 이 연결은 [추론] 등급이다. `roadmap-notes.md` §2 에 그대로 적었다.

## 5. 지금 당장 각 저장소에 영향이 있는 변화 Top 5

1. **stl-luau: 0.746 으로 올리면 게이트가 깨진다.**
   - TypeError 가 0건에서 6건으로 는다(N1·N2, `src/Trait/init.luau` 5곳, `tests/spec.contracts.luau:86`).
   - 음성 대조군 배터리 61개 중 3개(60·63·64)의 기대 건수가 1–2씩 는다.
   - 런타임 테스트는 두 버전 모두 PASS 다.
   - 할 일은 stl 세션 몫이다: 순회 대상에 주석을 달고, 배터리 기대치를 확인한다. N1 은 업스트림 위양성 보고 후보다.
2. **0.734 핀 5곳(quad, tbox, table-sim, devplorer, moonwave-luau)**
   - 0.742 에서 S2·S13·S14·S16 과 #3020 이, 0.746 에서 S11 과 N1·N2 가 바뀐다. 한 번에 올리면 에러가 느는 방향의 변화가 겹친다.
   - D-05 안 A(0.742 로 맞추기)가 여전히 낮은 위험의 중간 단계다. quad 의 엔진 무관 그룹은 0.742 와 진단 차이가 0이다(D-05 §2-2).
3. **luau-lsp 1.70.1 의 번들은 luau 0.740 이다.**
   - CLI 0.742 게이트와 에디터의 판정이 다르다(S2).
   - 1.69.0 핀 4곳은 `if local` 도 못 읽는다.
   - 다음 lsp 릴리스(0.742 동기화)가 나오면 `check_snippets.py --lsp` 로 다시 잰다.
   - typedefs 와 짝으로 핀한 저장소는 함께 올린다.
4. **stl-luau 의 설계 판단(체이닝 DX 대 class 대기)**
   - 사용자는 "class 가 밀린다"를 근거로 삼았다. class 가 개발 중이라는 것은 [구현] 근거로 맞다(0.737–0.746 매주 진척, `Debug*` 플래그).
   - 그러나 엔진 반영 일정이 없고, 제네릭 class 와 재귀 타입 완화는 근거가 없다. `Arr<T>` 류 제네릭 컨테이너가 class 로 풀린다고 기대하면 안 된다.
   - 그 판단의 전제에 이 구분을 더해 전달할 가치가 있다.
5. **`if local` 은 Roblox 코드에 아직 쓰면 안 된다.**
   - Studio 베타(옵트인)뿐이고 클라이언트에는 플래그가 없다. CLI·lsp 1.70.1·stylua 2.6.0 은 이미 받아서, 순수 luau 쪽에서 "되는 것처럼" 보인다.
   - stylua 2.6.0 은 `f<<T>>` 오염 재현이 2.5.2 와 같다. 올려도 무해하고 `if local` 파싱이 생긴다.
   - `while local`·`class` 는 2.6.0 도 못 읽는다.

## 6. 사용 흔적 — 사용자가 가져온 정보의 모양 (history.jsonl 표본 7건)
- 출처 URL(RFC 문서, PR, 릴리스 태그)을 붙인다.
- 버전 경계를 함께 적는다(pesde 0.7.3 은 거부, 0.7.4 는 수용. selene 은 `const` 미지원이라 폐기).
- "RFC 만으로는 근거가 약하고, **구현이 debug 플래그 아래라도 서 있으면** 방향의 근거가 된다"는 기준을 쓴다(11-10, stl-luau).
- 결론이 설계 결정으로 이어진다: 이름 `Class` 회피(10-16), 도구 교체, 핀 올리기.
- 스킬은 이 모양을 근거 등급([구현] / [승인] / [제안] / [풍문])과 `sources.md` §4 표로 재현한다.

## 7. 주기적 점검 — 방식 비교 (제안만, 구현하지 않음)

| 방식 | 장점 | 단점 | 맞는 일 |
|---|---|---|---|
| 직접 호출(`/luau-upstream-check` 류 명령, 또는 스킬 자동 발동) | 결과를 바로 대화 맥락에서 쓴다. 설치·핀 결정에 사용자 판단이 끼어 있다. 비용은 부를 때만 든다 | 잊으면 안 본다. 지금까지 사용자가 직접 가져오던 문제가 그대로 남는다 | bug-scan, 버전 올리기, 문법 채택 판정 |
| `/loop` (세션 안 반복) | 설정이 쉽다 | 세션이 살아 있어야 한다. 주 1회 주기에는 맞지 않는다 | 릴리스 당일 몇 시간 지켜보기 정도 |
| `/schedule` (클라우드 루틴, cron) | 사용자가 잊어도 돈다. 주 1회(토요일, luau 가 금요일에 나온 뒤)에 맞다 | 클라우드 환경에는 이 머신의 mise 설치본·스니펫 실측이 없다. 네트워크만 쓰는 부분(최신 태그, 릴리스 노트 요약, RFC PR 변화, Roblox 플래그)만 가능하다 | "새 판 나옴 + 요지 + 볼 RFC" 알림 |

- **권고: 둘을 섞는다.**
  - `/schedule` 로 주 1회 네트워크 전용 요약을 받는다. 내용은 `upstream_check.py --notes` 에 해당하는 것, RFC 열린 PR 변화, `PCStudioApp` 의 `Luau*IfLocal*`/`Class` 플래그다.
  - 설치와 bug-scan 은 사용자가 직접 부른다. 설치가 사용자 판단이라는 원칙과도 맞다.
  - `roadmap-notes.md` 의 `last-checked` 가 30일을 넘으면 스킬이 먼저 다시 보도록 SKILL.md 원칙 1에 넣어 두었다.

## 8. 스킬 실효성 (sonnet, `claude -p --model sonnet --plugin-dir luau-kb`, stream-json)

| 질문 | Skill 호출 | 내용 |
|---|---|---|
| "stl-luau 의 luau 를 0.742 → 0.746 올려도 될까?" | `luau-kb:luau-upstream` | `--notes` 와 `--bug-scan` 을 돌렸다. stl 게이트를 읽기 전용으로 두 버전에 돌려 깨짐 6건과 배터리 3건을 찾아냈다(이 보고서 Top 5 의 1번 근거) |
| "if local 을 Roblox 코드에 지금 써도 돼?" (1차) | `luau-kb:luau-upstream` | 결론("아직 아님")은 맞았다. 다만 references 가 쓰이기 전이라 웹을 직접 뒤졌고, "CLI 에서도 실험 플래그 뒤" 라고 틀리게 말했다. 이 실수 때문에 `syntax-adoption.md` 에 CLI 플래그 기제를 넣었다. 재측정 결과는 아래 |
| "Foo<T> → Foo<U> 한계 곧 고쳐질까? 우회책 영구?" | `luau-kb:luau-upstream` | watchlist 를 읽고 #2380 과 RFC 를 확인해 [승인]/[구현 없음] 등급으로 답했다. 권고는 "추적 링크와 함께 임시" 였다 |

| "if local 을 Roblox 코드에 지금 써도 돼?" (재측정, references 완성 뒤) | `luau-kb:luau-upstream` | `syntax-adoption.md` 만 읽고 5턴 만에 정확히 답했다: 4조건 표, Studio 베타 롤아웃 0%, CLI 플래그 기제, RFC #238 미병합, exact table 철회 사례, D-05 미확정 |
| "luau 업데이트 뒤 for 루프에 'is not iterable' 이 새로 났다" | `luau-kb:luau-upstream` | N1·N2 와 #3090 을 짚고, 주석·갈래 나누기 우회와 보고 후보를 안내했다. 두 우회는 이 세션에서 0.746 rc=0 으로 확인했다 |

- 5개 질문 모두 첫 도구 호출이 `Skill(luau-kb:luau-upstream)` 이었다.

## 9. 인계
- **스니펫 담당**(types: `variance-*`): `variance-value-phantom-nil.luau` 8행을 `bug-present [<0.746] || expect-error [>=0.746]` 로 바꾼다. `variance-intersection-instantiation.luau` 19행을 `[<0.746]` 로 바꾼다. N1·N2 를 새 스니펫으로 추가한다. 상세는 `watchlist.md` §2.
- **luau-types references**: `variance.md` §3·§7, `solver-limits.md` §2 에 0.746 열을 추가한다.
- **D-05**: 사용자 확인 전이다. `syntax-adoption.md` §0 의 채택 규칙 제안도 함께 묻는다.
- **업스트림 보고 후보**(게시는 사용자 결정): N1(0.746 위양성), 그리고 추적 항목이 없는 S1·S4·S6·S9·S10·S12·S17·S18.
