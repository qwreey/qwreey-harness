# D-01 `const` — 결정 (2026-11-10)

원문: `/code/Projects/claude-doctor/decisions/D-01-const.md` 끝의 "사용자 결정" 절. 이 파일은 요약이다.

## 맥락
rbvm 은 `const` 를 금지했다(2026-08-24, 당시 pesde 0.7.3 이 `const` 선언에서 자동 타입 익스포트를 못 함). stl-luau·quad·tbox·moonwave-luau 는 재대입 없는 바인딩에 `const` 를 쓴다(quad 는 문서상 채택, 게시 소스 0줄). pesde 0.7.4 는 `const` 를 받는다.

## 결정
- `const` 를 써도 된다. Roblox 라이브(게시) 코드까지 포함한다. 금지 근거는 사라졌다.
- 새 파일은 `const`, 기존 파일은 그 파일 관행을 따른다.
- 한 파일 안에서 `const` 와 재대입 없는 `local` 을 섞지 않는다.
- rbvm 규약 갱신은 rbvm 세션 몫이다.

## 알아 둘 사실 (`skills/luau-verify/references/tooling.md` §3)
- lune 0.10.5 와 selene 은 `const` 를 파싱하지 못한다. 그래서 D-03 이 lune 을 쓰지 않는다.
- stylua 2.5.2 는 `const` 뒤 `(` 로 시작하는 문장의 `;` 를 지워 파싱 에러를 만든다(claude-doctor D-01 실측, luau-style 스킬).
- `local const x = 1` 은 `const` 라는 지역과 전역 대입 `x = 1` 이 된다.

## 반영한 곳
- `skills/luau-verify/references/tooling.md` §3

## 되돌릴 조건
`const` 를 못 읽는 도구가 필수 경로(게시, 타입 익스포트)에 다시 들어오면 다시 본다.
