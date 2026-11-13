---
format: 1
title: 형제 저장소의 위임 사본을 정본과 대조하고 걷어내기
description: 네 저장소(quad, stl-luau, tbox, table-sim)와 stl-luau-doctor 의 agy-delegate.sh·delegate-agy 사본은 plugins/qwreey-delegate/skills/delegate 가 대체한다. 지우기 전에 각 저장소의 AGENTS.md 로 옮길 프로젝트 사실만 확인하면 된다.
status: active
---

# 형제 저장소 위임 사본 걷어내기

정본: `plugins/qwreey-delegate/skills/delegate/`(SKILL.md, scripts/delegate.sh, registry.tsv, templates/). 각 저장소 세션이 자기 저장소에서 대조하고 지운다. 이 문서는 읽기 전용 대조(2026-11-13)의 결과다.

## 공통

- 대조 결과: 다섯 저장소의 `agy-delegate.sh`·`delegate-agy/SKILL.md` 는 2026-11-09 이후 바뀐 것이 없다(`git log --since=2026-11-09` 가 위임 파일에는 비어 있다). 그래서 초안 이후 사본에만 생긴 개선은 없고, 정본에 더 흡수할 것도 없다. stl-luau-doctor 의 두 파일은 stl-luau 와 md5 가 같다.
- 정본이 사본보다 더 하는 것: 과제마다 HOME, detached worktree, `--ref`, mise.toml 에서 PATH 산출, `env -i`, `choom`(모든 백엔드), 동시 실행 상한, `collect`/`remove`/`gc`/`doctor`/`register`, codex `--mode empty`.
- 머리말(preamble)은 프로젝트 중립이다. 아래 "AGENTS.md 로 옮길 것"은 옛 머리말에만 있던 프로젝트 사실이므로 저장소의 `AGENTS.md`(skeleton: `templates/AGENTS.md.template`)에 먼저 쓴다. 정본 머리말은 "검사는 AGENTS.md 의 '검사' 절"이라고 가리킨다.
- 보고서 위치가 바뀐다: agy worktree 는 `REPORT.md`(옛 `AGY_REPORT.md`), 기록 디렉터리는 `.delegate/`(옛 `.agy/`). 이 이름을 적은 저장소 문서(스킬, conventions, 감사 기록 머리)를 같이 고친다.
- 옛 사본이 남아 있으면 `delegate.sh doctor` 가 INFO 로 알린다. 지우면 사라진다.
- 지우기 전에 확인: 돌고 있는 과제가 없는가(`delegate.sh list --all`), 옛 스크립트가 만든 `<repo>-agy/<name>`(`.agy/` 가 있는 것)은 `legacy` 로 보이므로 `AGY_REPORT.md` 를 보존할지 정하고 `remove --discard`.
- 옛 공유 `.home`(수백 MB)은 사용자 삭제 대상이다(`HUMAN_TODO.md`). 에이전트가 지우지 않는다.

## quad

- 대체되는 것: `.claude/tools/agy-delegate.sh`, `.claude/skills/delegate-agy/SKILL.md`. codex 쪽은 스크립트가 없었고(메모리 `reference-codex-delegation.md`), `delegate.sh run codex … --mode empty` 가 같은 꼴을 낸다.
- 유지할 uid: **61000**(registry 와 사본 일치).
- AGENTS.md 로 옮길 것(옛 머리말에만 있던 사실)
  - 전체 테스트는 `./scripts/test.sh`, 판정은 exit code(출력의 "ALL PASS" 줄 수가 아님).
  - `luau` 를 직접 돌리지 말 것(심볼릭 링크 문제). 프로브는 `quad-base/test/spec.*.luau`, `quad-roblox/test/spec.*.luau` 머리 하네스를 본떠 같은 폴더에 두고 test.sh 가 relink 한 뒤 돌린다.
  - worktree 생성 뒤 `pesde install` 은 registry 의 `setup` 열이 맡는다(이미 들어 있음). AGENTS.md 에 따로 쓸 필요 없음.
  - 정본 우선순위(`base/` > 나머지), 원장 README, 전체 감사는 `.claude/qa-request/external-review-entry.md` 로 가리키기.
- 확인할 차이
  - 사본은 브랜치 `agy/<name>` worktree 를 만들었고 정본은 detached 다. 남은 옛 브랜치 worktree(`naming-1021e` 등)는 `remove` 가 브랜치를 남기고 알린다.
  - 옛 `quad-codex/naming-*` 는 옛 수동 기록이다. `runs/<날짜>-<이름>/` 로 옮길지는 `gc` 가 "옛 기록"으로 알려 준다.
  - 사본 SKILL 의 quad 사례(nil 구멍, Context 설계, `q.Out`, `SetIfChanged`)는 저장소 문서의 역사다. 필요하면 quad 의 기록으로 옮기고 스킬에는 두지 않는다.

## stl-luau (그리고 stl-luau-doctor)

- 대체되는 것: `.claude/tools/agy-delegate.sh`, `.claude/skills/delegate-agy/SKILL.md`. stl-luau-doctor 는 stl-luau 를 미러링하므로 같은 두 파일(md5 동일)을 같은 방식으로 정리한다.
- 유지할 uid: **61001**(registry 와 사본 일치).
- AGENTS.md 로 옮길 것
  - 진입점은 지금 `GEMINI.md` 다. 정본은 `AGENTS.md` 하나만 두고 `GEMINI.md` 는 없앤다(agy 는 둘 다 싣는다). 내용은 지식이 아니라 정본 경로 지도로 줄인다.
  - 검사: 전체 `./scripts/check.sh`(타입, 음성 대조군, require, 에러 규약, 포맷, 테스트), 테스트만 `luau tests/run.luau`, 타입 `luau-analyze <파일>`(새 솔버, strict). 프로브는 worktree 루트나 `tests/` 옆, require 는 파일 기준 상대 경로(`require("./src")`).
  - 좁은 버그 사냥 범위의 예(nil 구멍과 `n` 불변식, 별칭 연산)와 "여덟 라운드 리뷰" 사례는 사본 SKILL 에만 있다. 필요하면 저장소 conventions 의 "리뷰" 절로.
- 확인할 차이
  - 사본에는 `choom` 이 없었다(정본은 모두에 적용). `--ref`, 과제별 HOME 은 정본에 있다.
  - 사본 SKILL 의 "한 번에 하나"는 정본의 `DELEGATE_MAX_CONCURRENT=1` 로 강제된다.
  - 사본 SKILL 의 "돌고 있는 동안 스크립트를 고치지 말 것"은 정본이 자기 사본으로 다시 실행해서 필요 없다.
  - stl-luau 의 `.claude/audit/agy/*` 보관 관례는 정본 SKILL 5단계와 같다.
  - `-scratch` 를 근거로 인용한 문서가 있으면 저장소 안으로 옮긴다(정본 SKILL "Workspaces").

## tbox

- 대체되는 것: `.claude/tools/agy-delegate.sh`, `.claude/skills/delegate-agy/SKILL.md`.
- 유지할 uid: **61003**. 사본은 **61000** 을 쓰고 있어 quad 와 같다(충돌). registry 는 61003 이다. 지금 `tbox-agy` 에 61000 소유 파일(옛 `.home/`)이 남아 있으면 정본 첫 실행 전에 사용자가 지운다(`HUMAN_TODO.md`).
- AGENTS.md 로 옮길 것
  - 런타임 테스트 `luau packages/tbox/test/run.luau`(마지막 줄 `all schema tests passed.`, 판정은 exit code), 정적 분석 `cd packages/tbox && lute run scripts/analyze.luau`(`static analysis passed.`).
  - 프로브는 `packages/tbox/test/` 아래, require 는 상대 경로(`require("../src")`).
  - Roblox 전역(Vector3 등)은 luau CLI 에 없다. Roblox 스키마는 `test/schema/roblox/*.luau` 처럼 mock 테이블로 확인한다.
  - 사본은 `TOOL_PATH` 를 손으로 적었다(mise.toml 과 맞출 것). 정본은 mise.toml 에서 산출하므로 이 목록은 지운다. 단 사본 PATH 에는 `/usr/local/bin` 이 있었고 정본은 뺀다. tbox 가 그 안의 도구를 쓰는지 확인한다.
- 확인할 차이: 원본 경로는 읽지 말라는 문구는 정본 머리말에 있다(예외는 AGENTS.md).

## table-sim

- 대체되는 것: `.claude/tools/agy-delegate.sh`(스킬 `delegate-agy` 는 없다. `.claude/skills/` 에는 `quad-ui-dev` 만 있다).
- 유지할 uid: **61002**(registry 와 사본 일치).
- AGENTS.md 로 옮길 것
  - `vendor/` 는 gitignore 라 worktree 에 없다. 필요하면 원본 `table-sim/<비공개>` 를 **읽기만** 한다(정본 머리말의 "원본 경로를 읽지 말 것"의 유일한 예외로 AGENTS.md 에 적는다).
  - 게이트 전체 `scripts/check.sh` 는 vendor 가 없어 worktree 에서 돌지 않는다. 엔진 없이 도는 스펙만: `( ulimit -v 4000000; timeout 300 luau tests/run.luau )`, 판정은 exit code. 프로브는 `tests/core/` 스펙을 본뜬다.
  - `src/server`, `src/client` 는 Roblox 엔진이 있어야 돌므로 읽기만 하고 그 부분의 주장은 "추정"이다.
  - Studio, MCP, `studio-sync`, `scripts/sync.sh`, `scripts/vendor.sh`, 네트워크 내려받기 금지. 정본 머리말에는 "Studio, MCP, 네트워크 내려받기, 패키지 설치 금지"가 공통으로 있으나 sync 스크립트 이름과 형제 저장소 수정 금지는 프로젝트 사실이므로 AGENTS.md 에 쓴다.
- 확인할 차이: 사본에는 uid 실측 주석(2026-10-12)이 있다. 정본 `doctor` 가 매번 같은 검사를 한다.

## 권한 규칙

다섯 저장소의 `.claude/settings*.json` 에는 `agy-delegate` 를 가리키는 규칙이 없다(읽기 전용 확인). 정본 스크립트는 q 플러그인 경로에서 불리므로 허용 규칙이 필요하면 각 저장소 세션과 사용자가 정한다.
