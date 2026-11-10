# version-bump — luau / luau-lsp / stylua 를 올리는 절차

## 이 파일이 답하는 질문
- Q1 luau 를 새 버전으로 올려도 되는지 어떻게 판단하나?
- Q2 올리면 무엇이 고쳐지고 무엇이 깨지는지 어떻게 미리 아나?
- Q3 luau-kb 의 `last-confirmed` 는 언제, 어떻게 고치나?
- Q4 각 저장소에는 무엇을 넘기나(인계)?

## 목차
- §1 원칙
- §2 절차 (5단계)
- §3 bug-scan 결과 읽는 법
- §4 luau-lsp, stylua, rojo 를 올릴 때
- §5 인계 문서 틀
- §6 실행 기록

---

## §1 원칙
status: described · 근거: luau-verify `toolchain.md` §3–4, claude-doctor `decisions/D-05-toolchain-pins.md`

- 버전은 반드시 고정한다. 검사기(`luau-analyze`)와 실행기(`luau`)가 같은 배포판이라, 올리면 진단 기준선과 음성 대조군 건수가 바뀐다.
- **설치와 핀 변경은 다른 일이다.** `mise install luau@<ver>` 는 `installs/` 에 내려받기만 한다. 전역 설정과 저장소 `mise.toml` 은 바뀌지 않는다. 다만 mise 의 `installs/luau/latest` 와 `0` 심볼릭 링크는 새 버전으로 옮겨진다. 이 링크를 직접 부르는 스크립트가 있으면 그 스크립트의 동작이 바뀐다.
- 저장소의 핀은 그 저장소 세션이 바꾼다. 이 스킬은 판정 자료와 인계 문서만 만든다. 핀 정책은 D-05 다(제안 상태, 사용자 미확인).
- luau-lsp 는 자기 번들 Luau 를 쓴다. CLI 핀과 따로 움직이고 보통 몇 주 늦다. 같은 파일이라도 CI(`luau-analyze`)와 에디터(luau-lsp)의 판정이 다를 수 있다.

## §2 절차 (5단계)
status: verified (1–3단계, 2026-11-10 에 0.742 → 0.746 으로 실행) / described (4–5단계)

1. **새 버전을 설치한다.** 사용자 판단이다. 도구가 대신 설치하지 않는다.
   ```bash
   choom -n 1000 -- mise install luau@0.746     # 전역 설정·핀 불변
   ```
2. **스니펫 전체를 새 버전 열로 돌린다.** 기준 버전과 나란히 돌려야 차이만 보인다.
   ```bash
   cd /code/Projects/luau-kb
   python3 -I tools/upstream_check.py --bug-scan 0.746            # 기준: 설치된 것 중 바로 아래
   python3 -I tools/upstream_check.py --bug-scan 0.746 --base 0.734
   # 원 출력이 필요하면
   choom -n 1000 -- python3 -I tools/check_snippets.py --luau 0.742,0.746 snippets/*.luau
   ```
3. **분류한다.**
   - `bug-present` 가 뒤집힘 → **고쳐짐 후보**. 그 줄에 `[<새버전]` / `[>=새버전]` 버전 조건을 달고 대조군을 붙인다.
   - 새 실패 → **깨짐 후보**. 단, `expect-error 인데 0건` 은 "한계가 풀려서 이제 통과" 일 수도 있다. 반드시 그 자리의 결과 타입을 다시 재서 판정한다. (예: 2026-11-10 의 `variance-intersection-instantiation` 19행은 0.746 에서 T 가 `number` 로 정확히 풀려 한계가 풀린 것이었다.)
   - 같음 → 할 일 없음. 양쪽 다 실패한 파일은 이 스캔과 무관한 기존 문제다.
4. **luau-kb 를 갱신한다.**
   - 바뀐 절: `status` 와 `last-confirmed: luau <새버전>` 을 고치고, 결함 카탈로그(luau-types `solver-limits.md` §2)에 열을 하나 더한다.
   - 안 바뀐 절: `last-confirmed` 를 올릴지 여부는 그 절의 스니펫이 새 버전에서 ok 였는지로 정한다. ok 였으면 `luau 0.742 (0.746 동일)` 처럼 적는다.
   - `watchlist.md` 의 상태 칸을 고친다. 고쳐진 항목은 "고쳐짐(<버전>)" 으로 두고 바로 지우지 않는다. 핀이 낮은 저장소가 아직 그 결함을 겪기 때문이다.
   - 스니펫 파일 수정은 접두 담당이 한다(`variance-`, `generics-` 등은 types 담당). 다른 담당이면 인계 문서에 적는다.
5. **각 저장소 영향을 보고한다.** §5 틀로 인계 문서를 쓴다. 저장소의 게이트(음성 대조군 배터리 건수)를 새 버전으로 돌려 보는 일은 그 저장소 세션의 몫이다.

## §3 bug-scan 결과 읽는 법
status: verified · 근거: `tools/upstream_check.py`, 2026-11-10 실행

| 칸 | 뜻 | 다음 행동 |
|---|---|---|
| 뒤집힘 | 진단이 없어야 하는 `bug-present` 줄에 진단이 생겼다 | 고쳐짐 후보. 같은 결함을 우회한 저장소 코드가 있으면 우회책을 걷을 수 있는지 본다(`watchlist.md` 의 수명 칸) |
| 새 실패: 예상 못한 진단 | 표식 없는 줄에 진단이 생겼다 | 퇴행이거나 더 엄격해진 검사. 실제 저장소 코드에서도 같은 모양이 깨질 수 있다 |
| 새 실패: expect-error 0건 | 잡던 것을 안 잡는다 | 한계가 풀렸거나(좋음) 검사가 꺼졌다(나쁨). 결과 타입을 재서 판정 |
| 새 실패: 메시지에 '…' 없음 | 메시지 문구가 바뀌었다 | 부분 문자열을 다시 고른다. 동작 변화는 아니다 |
| 같음 / 기존 실패 | 차이 없음 | 없음 |

- 함정: **이미 버전 조건이 달린 줄**(`bug-present [<0.742] || expect-error [>=0.742]`)은 두 버전 모두 ok 로 나온다. 그래서 `--base 0.734` 로 돌려도 0.742 에서 고쳐진 넷(S2, S13, S14, S16)은 보이지 않는다. 낮은 핀 저장소가 겪을 차이는 버전 조건 줄과 luau-types `solver-limits.md` §3 을 함께 읽어 모은다.
- "고쳐짐" 은 **에러가 새로 생긴다**는 뜻이다. 저장소의 코드가 그 구멍 덕분에 통과하고 있었다면 올리는 순간 진단이 늘어난다. 0.734 → 0.742 에서 한 저장소가 새 진단 12건을 얻은 것이 그 예다.

## §4 luau-lsp, stylua, rojo 를 올릴 때
status: described · 근거: luau-verify `tooling.md` §4, `toolchain.md` §3, D-05 §2-2

- **luau-lsp**: 번들 Luau 판이 무엇인지 릴리스 노트에서 먼저 본다. `check_snippets.py --lsp <ver>` 로 참고 열을 만들어 CLI 와 다른 칸을 찾는다. Roblox 정의 파일(`globalTypes.d.luau`)과 짝으로 핀한 저장소는 정의 파일과 함께 올린다.
- **stylua**: `tools/repro-stylua-typeargs.sh <새 stylua>` 를 먼저 돌린다. 새 문법(`const`, `class`, `if local` 등)을 파싱하는지 작은 파일로 확인한다(`syntax-adoption.md` §3).
- **rojo**: 새 문법 자체와는 무관하다(파일을 옮길 뿐). 프로젝트 파일 형식과 sourcemap 형식 변화만 본다. luau-lsp 의 sourcemap 소비와 짝이 맞는지 확인한다.

## §5 인계 문서 틀
status: described

```markdown
# luau <old> → <new> 영향 (YYYY-MM-DD, luau-kb bug-scan)
- 고쳐진 결함: <스니펫> — 이 저장소에서 그 결함을 우회한 곳: <경로 또는 '없음'>
- 새로 엄격해진 검사: <스니펫/모양> — 이 저장소에 같은 모양이 있는지 grep 할 패턴: <패턴>
- 할 일: 게이트를 <new> 로 돌려 배터리 건수 비교 → 바뀐 진단을 고치거나 기록 → mise.toml 머리 주석에 이유
- 핀을 올릴지는 이 저장소가 정한다 (D-05)
```

## §6 실행 기록
status: verified

| 날짜 | 기준 → 새 | 뒤집힘 | 새 실패 | 같음 | 메모 |
|---|---|---|---|---|---|
| 2026-11-10 | 0.742 → 0.746 | 1 (`variance-value-phantom-nil` 8행) | 1 (`variance-intersection-instantiation` 19행, 한계가 풀림) | 첫 실행 66/68, 스니펫이 138개로 는 뒤 재실행도 같은 2건만 다름 | 상세는 `watchlist.md` §2. 스니펫 밖의 변화(N1·N2)는 저장소 게이트로 찾았다 |
