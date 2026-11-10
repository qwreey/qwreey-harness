---
paths:
  - "**/*.luau"
---
# Luau 공통 규칙 (저장소 무관)

저장소의 `.claude/rules/`·CLAUDE.md 가 다르게 정하면 그쪽을 따른다. 근거와 예시는 각 줄의 링크(luau-style 스킬 references)에 있다.

## 파일과 문법
- 파일 1행에 `--!strict` 를 둔다. `.luaurc` 만 믿지 않는다. → [modules§1](../skills/luau-style/references/modules.md)
- `const` 를 써도 된다. 기존 파일은 그 파일의 `const`/`local` 관행을 따르고 한 파일 안에서 섞지 않는다. → [idioms§1](../skills/luau-style/references/idioms.md)
- `local const x = …` 를 쓰지 않는다. 전역 대입 `x = …` 가 된다. → [idioms§1](../skills/luau-style/references/idioms.md)
- `(` 로 시작하는 문장을 쓰지 않는다. 지역에 받아서 부른다. → [idioms§1](../skills/luau-style/references/idioms.md)
- 삼항은 `if c then a else b` 식으로 쓴다. `c and a or b` 는 쓰지 않는다(`x or y` 기본값은 된다). → [idioms§2](../skills/luau-style/references/idioms.md)
- `f<<T>>(…)` 는 명시 타입 인자다. 시프트 연산으로 고치지 않는다. → [idioms§3](../skills/luau-style/references/idioms.md)
- 모듈 함수는 `local function` 이나 `const function` 으로 쓴다. 맨 `function name()` 은 진단 없이 전역이 된다. → [idioms§6](../skills/luau-style/references/idioms.md)

## 이름과 주석
- 타입과 `require` 받은 모듈은 PascalCase, 지역 변수·지역 함수는 camelCase, 술어는 `isX`, `_` 접두는 내부로 쓴다. → [naming§1](../skills/luau-style/references/naming.md)
- 그 밖의 케이스(네임스페이스 함수, 파일 이름)는 같은 폴더의 이웃 모듈을 따른다. → [naming§2](../skills/luau-style/references/naming.md)
- 사용자가 정한 이름이 규칙과 어긋나면 바꾸지 말고, 이유와 함께 이름 변경을 제안한다(일괄 수정은 승인 뒤). → [naming§3](../skills/luau-style/references/naming.md)
- 식별자와 에러 메시지는 영어로 쓰고, 주석은 그 파일에 이미 쓰인 언어로 쓴다. → [quality§1](../skills/luau-style/references/quality.md)
- 주석에는 코드가 말하지 않는 "왜"를 쓴다. → [quality§1](../skills/luau-style/references/quality.md)

## 에러
- 에러 메시지는 던지는 줄에 리터럴로 쓴다. 포맷 헬퍼로 흩지 않는다. → [errors§1](../skills/luau-style/references/errors.md)
- 받은 에러를 되던질 때는 `error(e, 0)` 으로 던진다. → [errors§1](../skills/luau-style/references/errors.md)
- 저장소에 raise 헬퍼가 있으면 손으로 센 `error(msg, n)` 대신 그것을 쓴다. `-O2` 인라인이 위치를 바꾼다. → [errors§2](../skills/luau-style/references/errors.md)
- `pcall(f(x))` 로 쓰지 않는다. `pcall(f, x)` 나 클로저로 감싼다. → [errors§3](../skills/luau-style/references/errors.md)

## require
- `init.luau` 안에서 자기 폴더의 파일은 `@self/x` 로 부른다. `./x` 는 폴더의 형제다. → [modules§3](../skills/luau-style/references/modules.md)
- `require` 인자는 문자열 리터럴로 쓰고, 테스트 엔트리 이름을 `init.luau` 로 짓지 않는다. → [modules§3](../skills/luau-style/references/modules.md)
- 새 모듈에는 그 모듈을 실제로 `require` 하는 테스트를 둔다. → [modules§3](../skills/luau-style/references/modules.md)

## 포맷·검증·보고
- stylua 는 저장소 루트에서 돌리고, `<<` 가 든 파일은 포맷 뒤 diff 를 본다. → [quality§3](../skills/luau-style/references/quality.md)
- 판정은 저장소 게이트의 exit code 로 하고, stderr 를 버리지 않는다. → [quality§5](../skills/luau-style/references/quality.md)
- 보고할 때 "타입·포맷만 / 스펙 통과 / Studio 실측" 을 구분한다. → [quality§5](../skills/luau-style/references/quality.md)
