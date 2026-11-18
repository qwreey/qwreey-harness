# D-12. `require` 경로 표기 (`./`, `@self`, `@game`)

> **상태: 확정(2026-11-11 사용자: 추천대로).** 4절의 추천안을 채택.

> 작성 2026-11-10. 실태 통계는 `/tmp/cd-exp/sty/src/` 사본의 `require("…")` 리터럴을 센 것이다.

## 1. 각 프로젝트의 입장과 실태

| 프로젝트 | 규칙 | 위치 | 실태 [실행] |
|---|---|---|---|
| stl-luau | `init.luau` 안 형제는 `@self/`, `./` 는 폴더의 형제. **정적 검사가 못 잡는다**, symlink 를 따라가지 않음 | `stl-luau/.claude/base/architecture.md:37-63,307-341` | `@self` 43, `./`·`../` 137 |
| tbox | `init.luau` 는 "자기가 들어 있는 폴더". 의존성은 `./roblox_packages/<name>`, 내부는 `@self/`. `../` 는 거의 항상 버그. 테스트 엔트리를 `init.luau` 로 짓지 않음 | `tbox/CLAUDE.md:95-117,141-147` | `@self` 34, 상대 93 |
| moonwave-luau | 같은 규칙. symlink 미추적 [실측]. 새 모듈은 실제로 불러보는 테스트 필요 | `moonwave-luau/.claude/conventions.md:66-74` | — |
| devplorer | **상대 경로만**. 클라이언트 번들이 PlayerGui 로 복제돼 위치가 바뀌므로 `@game/...` 절대 경로 금지 | `devplorer/.claude/conventions.md:78-80` | `@game` 0, 상대 710 |
| table-sim | 규칙 없음 | — | **`@game/ReplicatedStorage/…` 72**, 상대 225 |
| quad | `.luaurc` 별칭(`quad-base`, `quad-roblox`) + 상대 | `quad/.luaurc:6-9` | `@self` 46, 상대 207 |
| rbvm | (Studio 실측) `./` `../` `@self` `@game/…` 허용, 접두 없으면 에러, `@Self` 대소문자 무시 | `rbvm/.claude/design/engine-behavior.md:68-83`(감사 05 §2-3) | `@self` 9, 상대 17 |

## 2. 실제 근거

- `init.luau` 상대 경로 규칙: stl·tbox·moonwave 가 각자 실측했다. luau CLI 0.734 기준이다.
  - tbox `squish` 에서는 실제로 이 실수로 깨진 코드가 있었다(`tbox/CLAUDE.md:108-109`). [기록]
- **정적 검사가 require 경로 오류를 잡지 못한다**(→ 정정 절 참고: strict 조건부) (stl `architecture.md:307-330`, moonwave `conventions.md:73-74`). 그래서 "실제로 불러보는 테스트"가 유일한 그물이다. [기록]
- devplorer 의 `@game` 금지는 그 저장소의 배포 방식(복제되는 번들) 때문이다. table-sim 은 고정 위치(`ReplicatedStorage/TableSim`)에서 돌아서 `@game` 이 문제 되지 않는다. [기록·추정]
- CLI(luau)와 Studio 의 require 해석이 다를 수 있다. 비교표가 없다(감사 05 §2-3). [서술]

## 3. 합의안

### 안 A. 공통 사실 규칙 + 조건부 금지
- 공통 규칙은 다섯이다.
  1. `init.luau` 안에서 자기 폴더 파일은 `@self/`, `./` 는 폴더의 형제다.
  2. require 대상은 문자열 리터럴로 쓴다.
  3. 테스트 엔트리를 `init.luau` 로 짓지 않는다.
  4. 새 모듈은 실제로 require 하는 테스트를 둔다(정적 검사가 못 잡음). (→ 정정 절 참고: 규칙은 유지)
  5. symlink 를 따라가지 않으므로 스테이징은 복사로 한다.
- 조건부 규칙: **위치가 바뀌는(복제·이동되는) 코드에서는 `@game/` 절대 경로 금지.**

| 프로젝트 | 변경량 |
|---|---|
| 전부 | 0. table-sim 의 `@game` 72곳은 조건에 걸리지 않음 |

### 안 B. 공통 금지 `@game/`(상대 경로만)
- table-sim 72곳을 바꿔야 한다. 고정 위치 코드에서는 이득이 불분명하다.

## 4. 추천: 안 A

- 다섯 사실은 세 저장소가 독립적으로 실측했다. 공통 rules 가 막을 사고(`../roblox_packages`, `init.luau` 엔트리)가 실제로 있었다.
- `@game` 은 배포 방식에 매인 조건이라 조건문으로 둔다.

## 5. 사용자 확인 질문

require 규칙 다섯(`init.luau` 의 `@self`, 리터럴 경로, 엔트리를 `init.luau` 로 짓지 않음, 실제로 불러보는 테스트, symlink 미추적)을 공통 규칙으로 넣고, `@game/` 금지는 "위치가 바뀌는 번들일 때만"으로 둘까요?

## 정정 (2026-11-10, luau-kb 증류)
- "정적 검사가 require 경로 오류를 못 잡는다"에는 strict 조건이 붙는다. `--!strict` 면 없는 경로는 `Unknown require` 로 잡힌다. 못 잡는 것은 nonstrict 이거나, 오타가 다른 실제 파일로 풀리는 경우다.
- 규칙 4(실제 require 테스트)는 그대로 필요하다.
- 동적 require 경로: luau 0.734·0.742 런타임은 실행하고, strict 의 luau-analyze 만 `unsupported path` 로 거부한다(Studio 는 미측정). `ambiguous` 에러 서술은 낡았다.
- 근거: `packs/luau-kb/skills/roblox-luau/references/require-and-modules.md` §5·§9, `packs/luau-kb/skills/luau-verify/references/checkers.md` §7, `packs/luau-kb/snippets/style-require-paths.sh`
