# 툴킷 luau (Luau/Roblox)

검사 모듈: `scripts/toolkits/luau.py`. 공유 지식 저장소: luau-kb(`<작업공간>/luau-kb`, `--kb`로 바꿈).
갈린 규약의 합의안은 `<doctor>/decisions/D-xx`다(`.claude/base/decisions/README.md` 현황표가 확정 여부의 정본).

## 목차
- [감지 표식](#감지-표식)
- [툴체인](#툴체인)
  - [형제와 같다는 주석](#형제와-같다는-주석)
- [공유 지식 (luau-kb)](#공유-지식-luau-kb)
- [typedefs 사본](#typedefs-사본)
- [걸린 결정 (D-xx)](#걸린-결정-d-xx)
- [그 밖에 모델이 볼 것](#그-밖에-모델이-볼-것)

## 감지 표식

하나라도 있으면 켠다. scan 머리의 `툴킷:` 줄에 표식이 나온다.
- `*.luau` 파일
- `mise.toml`의 도구: luau, luau-lsp, stylua, lune, lute, rojo, wally, pesde, selene
- 루트의 `default.project.json`(Rojo), `.luaurc`, `pesde.toml`, `wally.toml`, `selene.toml`

툴체인 검사(아래)는 표식이 있어도 `*.luau`가 하나도 없으면 하지 않는다(스캐폴딩 전 저장소).

## 툴체인

항목 8. `.luau` 파일이 있는 저장소에서만 본다.

| 코드 | 뜻 | 등급 |
|---|---|---|
| `TOOL-PIN` | `mise.toml`의 luau, luau-lsp, stylua 핀이 **형제 저장소 핀과 다를 때만** 낸다. `mise.toml`이 없어도 낸다 | 정보 |
| `TOOL-SYNTAX` | `stylua.toml`에 `syntax = "Luau"`가 없다 | 오류 |
| `TOOL-NOSTYLUA` | stylua 설정 파일이 없다 | 경고 |
| `TOOL-CLAIM` | 설정 주석이 "형제와 같다"고 하는데 실제 값이 다르다 | 경고(같다) / 정보(따른다) |
| `TOOL-LUAURC` | `.luaurc`가 없다 | 정보 |

**판단 근거**
- **D-05 (버전 핀, 미확정)**: 목표값(예: 0.742 통일)은 정하지 않았다. 그래서 scan은 목표와 비교하지 않는다.
  - 비교 대상은 형제 저장소(같은 작업공간, 자기 worktree와 `-agy`·`-doctor` 같은 사본은 뺌)의 실제 핀이다. 어긋난 도구마다 "값(저장소…)"을 적는다.
  - 핀을 올리자고 고치지 않는다. 사용자가 물으면 D-05를 가리킨다.
  - 제안된 공통 규칙 둘(확정 전): 수치·결함 서술에는 그 버전을 같이 적는다. 0.734를 쓰는 저장소는 `luau-analyze`의 비정상 종료를 실패로 판정한다(본보기 stl `check.sh:29`).
  - luau-lsp 핀은 Roblox `globalTypes.d.luau` 판과 짝이다(table-sim, devplorer, tbox). lsp만 따로 올리면 안 된다.
- **D-02 (stylua, 확정)**: 사고를 내는 것은 설정 값이 아니라 설정이 적용되지 않은 실행이다.
  - `syntax = "Luau"`가 없거나 하위 폴더에서 실행하면 `f<<T>>`가 exit 0인 채로 시프트 연산이 된다(재현됨).
  - 재현 스크립트: `<작업공간>/luau-kb/tools/repro-stylua-typeargs.sh`
  - `syntax = "Luau"` 한 줄은 승인을 받으면 고칠 수 있다. `indent_type`·`call_parentheses` 값은 저장소 소유라 건드리지 않는다.
- **D-03 (러너, 확정)**: lune은 `const`를 파싱하지 못한다. `.vscode`의 `@lune/` 별칭처럼 lune 흔적과 "lune 안 씀" 서술이 섞여 있으면 모순으로 보고한다(moonwave 사례).

**모델이 볼 것**
- 게이트 스크립트(`scripts/check.sh`, `mise run check`)가 stylua를 저장소 루트에서 `--check`로 부르는지 본다.
- 문서에 적힌 버전과 `mise.toml`의 실제 핀이 같은지 본다. CLAUDE.md, GEMINI.md, conventions를 확인한다.

### 형제와 같다는 주석

`mise.toml`이나 `stylua.toml` 주석이 형제 저장소 이름을 들며 "같다"고 하면, scan이 형제의 실제 파일과 비교한다.
- mise 주석이 `stylua.toml` 모양을 말하면 stylua 설정끼리 비교한다.
- 실례
  - table-sim `mise.toml:3`: "quad·tbox·stl-luau와 같은 값"이라고 하지만 stl은 0.742/1.70.1이다.
  - stl `stylua.toml:1`: "tbox/quad와 같은 설정"이라고 하지만 tbox는 Spaces+Input이고 quad는 설정 파일이 없다.
- **고치는 법**: 형제 이름 대신 그 값을 고른 이유를 적는다. 예: "typedefs 정의 파일과 짝", "배터리 기대 건수 재현".
  형제 이름을 주석에 넣지 않으면 형제가 바뀌어도 낡지 않는다.
- `<doctor>/decisions/README.md`의 "이번에 발견한 낡은 서술" 목록과 대조해 이미 알려진 것인지 적는다.

## 공유 지식 (luau-kb)

항목 5. 일반 원리는 `references/staleness-and-kb.md#5-공유-지식-쏠림`. 여기는 luau 쪽 값이다.

| 코드 | 뜻 |
|---|---|
| `KB-MARK` | `<!-- luau-kb 후보 -->` 표시 목록. 옮길 대상 장부다 |
| `KB-CAND` | 표시는 없지만 일반 Luau 지식일 수 있는 줄. Luau 용어와 근거 신호(버전 `0.7xx`, "N배", "%", 상류, 결함, 재현, 실측)가 함께 있는 줄을 센다 |

**모델이 볼 것** (`KB-CAND` 판정)
- **후보**: 라이브러리 없이 재현되거나 Luau 버전에만 의존하는 사실. 솔버 동작, 표준 라이브러리 성능, stylua·luau-analyze의 함정, `-O2` 인라인 문제.
- **후보 아님**: 프로젝트 API, 설계 결정, 그 저장소의 수치 계약에 묶인 것.
- 둘이 섞였으면 "혼합"으로 적는다. 분류 예시는 `<doctor>/audit/07-stl-luau-diet.md` §5의 23개 표다.
- 이미 luau-kb에 있는지 확인한다: `grep -rn <핵심어> <작업공간>/luau-kb/skills`. 있으면 프로젝트 문서의 서술을 포인터로 바꾸는 안을 낸다.

**옮기는 순서**(luau-kb 작업에서 한다): snippet으로 재현(`luau-kb/tools/check_snippets.py`) → 스킬 reference에 적기 → 프로젝트 문서에는 포인터만.

## typedefs 사본

항목 6. `DRIFT-TYPEDEFS`: 저장소 안의 `globalTypes*.d.luau`를 luau-kb 정본 `typedefs/globalTypes.d.luau`와 md5로 비교한다.
- md5가 다르다고 곧 표류는 아니다. 그 저장소의 luau-lsp 핀과 짝인 판일 수 있다(rbvm의 캐시 판, tbox의 `globalTypes.None.d.luau`).
  그 저장소 `mise.toml` 주석과 `luau-kb/typedefs/README.md`의 비교표를 확인한다.
- 정본과 같은 사본은 지금 고칠 것이 없다. 참조로 바꾸는 일은 P5 범위다.
- 반입 사본(`intake/`)은 git 무시 파일까지 걷는다. `.claude/cache/` 같은 캐시가 같이 왔으면 이 경고는 거른다.

## 걸린 결정 (D-xx)

이 툴킷의 scan 코드나 발견이 아래 D-xx에 걸리면 한쪽으로 고치지 않고 묻는다(`fix-protocol.md#규약이-갈리는-항목`).
상태는 `.claude/base/decisions/README.md` "사용자 결정 현황"을 먼저 본다. 확정된 것은 그 결정대로 고칠 안을 낸다.

| scan 코드나 발견 | D-xx |
|---|---|
| `TOOL-PIN`, 버전 서술 | D-05 버전 핀 |
| stylua `indent_type`, `call_parentheses` 값 | D-02 stylua |
| `const` 사용 여부 | D-01 |
| lune, lute, luau 러너 | D-03 |
| `type function` 사용 범위 | D-04 |
| analyze와 lsp 중 무엇을 기준으로 할지 | D-06 |
| 주석 언어 | D-08 |
| 네이밍 케이싱 | D-09 |
| 에러 형식, `error(msg, level)` | D-10 |
| 객체 모양, 필드 지역 캐시 | D-11 |
| require 경로, `@game` | D-12 |
| 파일 길이·폴더 구조 | D-13 (기준 값은 언어 무관, 측정 도구는 luau-style) |

## 그 밖에 모델이 볼 것

- rules의 `paths`는 `src/**/*.luau`처럼 `.luau`를 겨냥한다. `RULE-DEADGLOB`이 나오면 생성물(`sourcemap.json`, `luau_packages/`)을 겨냥했는지 본다.
- Roblox 엔진 동작 주장은 Studio에서만 실측된다. 문서에 "확인됨"이라 적힌 엔진 동작은 근거(Studio MCP 기록, 공식 문서 URL)가 있는지 본다.
- 스킬 부작용 낱말에 `studio-sync`(Studio 쓰기)가 더해진다(`SKILL-SIDEFX`).
