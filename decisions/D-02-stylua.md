# D-02 stylua — 결정 (2026-11-10)

원문: `/code/Projects/claude-doctor/decisions/D-02-stylua.md` 끝의 "사용자 결정" 절. 이 파일은 요약이다.

## 맥락
들여쓰기는 Tabs 5곳 / Spaces 2곳, `call_parentheses` 는 Always 2곳 / Input 4곳으로 갈렸고 quad 는 설정 파일이 없다. 들여쓰기를 바꾸면 3천~3만 3천 줄이 바뀐다. 하위 폴더에서 돌리거나 `syntax` 가 없으면 `f<<T>>(x)` 가 rc=0 인 채 시프트 연산으로 바뀐다.

## 결정
- 값(들여쓰기, `call_parentheses` 등)은 각 저장소의 `stylua.toml` 이 소유한다. 맞추지 않는다.
- 공통 규칙은 셋이다: **루트(설정 파일이 있는 곳)에서 실행**, **`syntax = "Luau"`**, **포맷 뒤 diff 에서 `<< ` 나 ` >>` 확인**.
- 새 저장소의 기본값 제안은 Tabs + `call_parentheses = "Input"` 이다(강제 아님).

## 반영한 곳
- `skills/luau-verify/references/tooling.md` §4, `tools/repro-stylua-typeargs.sh`

## 되돌릴 조건
stylua 가 설정 탐색을 상위 디렉터리까지 하거나 기본 문법을 Luau 로 바꾸면 공통 규칙의 앞 둘을 다시 본다.
