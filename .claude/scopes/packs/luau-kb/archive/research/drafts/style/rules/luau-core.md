---
paths:
  - "**/*.luau"
---
# Luau 공통 규칙 (저장소 무관)

저장소의 `.claude/rules/`·CLAUDE.md 가 다르게 정하면 그쪽을 따른다. `→ X§n` 은 `~/.claude/skills/luau-style/references/X.md` 의 n절(근거·예시)을 가리킨다.

## 파일과 문법
- 파일 1행은 `--!strict` 로 쓰고, 이어서 무엇·왜를 적은 머리 주석을 둔다. → modules§1
- `const`·`local` 은 그 파일의 기존 관행을 따르고 한 파일 안에서 섞지 않는다. 새 파일은 저장소 규칙을 따른다. → idioms§1
- `local const x = …` 를 쓰지 않는다. 전역 대입이 된다. → idioms§1
- `(` 로 시작하는 문장을 쓰지 않는다. 지역에 받아서 부른다. → idioms§1
- 삼항은 `if c then a else b` 식만 쓴다. `a and b or c` 는 금지이고, `x or y` 기본값은 허용한다. → idioms§2
- `f<<T>>(…)` 는 명시 타입 인자이니 고치지 않는다. 제네릭이 안 풀리면 캐스트보다 이것을 먼저 쓴다. → idioms§3
- 모듈 함수는 `local function` 또는 `const function` 으로 쓴다. 맨 `function name()` 은 전역 대입이다. → idioms§6

## 이름과 주석
- 타입과 `require` 받은 모듈은 PascalCase, 지역 변수와 지역 함수는 camelCase, 종류 술어는 `isX`, `_` 접두는 내부로 쓴다. → naming§1
- 그 밖의 케이스(네임스페이스 함수, 파일 이름)는 같은 폴더 이웃 모듈을 따른다. → naming§2
- 식별자와 에러 메시지는 영어로 쓴다. 주석은 그 파일에 이미 쓰인 언어로 쓴다. → quality§2
- 주석에는 "무엇"보다 "왜"를 쓴다. 공개 소스에 원장 번호만 남기지 않는다. → quality§2
- 코드 `TODO` 에는 이유와 추적처를 붙이고, 끝나면 지운다. → quality§6

## 에러
- 에러 메시지는 raise 줄에 리터럴 그대로 쓴다. 메시지로 grep 해서 자리를 찾을 수 있어야 한다. → quality§1
- 라이브러리 코드에서 손으로 센 `error(msg, 2)` 를 쓰지 않는다. `-O2` 인라인이 위치를 지운다. 저장소의 raise 헬퍼를 쓴다. → quality§1

## require
- `init.luau` 안의 자기 폴더 파일은 `@self/x` 로 부른다. `./x` 는 폴더의 형제다. → modules§3
- `require` 인자는 문자열 리터럴로 쓰고, 테스트 엔트리 이름을 `init.luau` 로 짓지 않는다. → modules§3
- 새 모듈에는 실제로 `require` 하는 테스트를 둔다. 정적 검사는 경로 오류를 못 잡는다. → modules§3

## 포맷·검증·보고
- 손으로 정렬하지 않는다. 저장소 루트에서 `stylua` 를 돌린다. 하위 폴더에서 돌리면 설정을 못 찾아 `f<<T>>` 가 조용히 깨진다. → quality§3
- 판정은 저장소 게이트 스크립트의 exit code 로 한다. 진단은 stderr 로 나오니 버리지 않는다. → quality§5
- 진단이 0건이면 일부러 틀린 음성 대조군으로 검사가 살아 있는지 확인한다. → quality§4
- `luau` 를 직접 돌릴 땐 `ulimit -v`·`timeout` 을 같이 건다. → quality§5
- 보고할 때 "타입·포맷만 / 스펙 통과 / Studio 실측" 을 구분한다. 돌려 보지 않은 것을 "동작함"이라 쓰지 않는다. → quality§5
