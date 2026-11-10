# 작업 환경 (모든 프로젝트 공통)

`/code/Projects/*` 는 한 사람이 운영하는 형제 저장소들이다. 대부분 Roblox/Luau.

## 형제 저장소 지도
| 저장소 | 무엇 |
|---|---|
| quad | Roblox DOMless UI 렌더러. 가장 큰 Luau 타입 한계 연구 (`.claude/base/typing-limits.md`) |
| stl-luau | Luau 표준 라이브러리(컨테이너·트레이트). 성능 실측 (`.claude/base/perf-measurements.md`) |
| rbvm | Roblox 엔진 동작을 흉내 내는 VM. Studio 엔진 동작 기록 |
| table-sim, devplorer, tbox, moonwave-luau, mrow, vitrine, VideoSync | 각 저장소 CLAUDE.md 참고 |
| luau-kb | **Luau/Roblox 공유 지식 정본**(스킬·스니펫·typedefs). 다른 저장소를 "보러 가기" 전에 여기 스킬부터 |
| claude-doctor | 이 하네스 구조 정리 작업 (계획: `PLAN.md`) |

## 다른 저장소를 다룰 때
- 다른 저장소는 **읽기 전용**으로 본다. 여러 Claude 세션이 동시에 각자 저장소에서 작업 중일 수 있다.
  수정이 필요하면 사용자에게 먼저 묻는다.
- 실행 중인 세션 확인: `for p in $(pgrep -x claude; pgrep -x agy; pgrep -x codex); do readlink /proc/$p/cwd; done | sort -u`
  (`pgrep -f` 는 셸 래퍼 자신을 잡으므로 쓰지 않는다)
- `.claude/worktrees/*` 는 살아 있는 에이전트가 쓰는 중일 수 있다 (lock 파일 확인). 지우기 전에 반드시 확인.

## ~/.claude 자체를 바꿀 때
- `~/.claude` 의 settings.json, CLAUDE.md, hooks/ 는 `/code/Projects/claude-doctor/home/.claude/` 가 정본이다.
  직접 고치지 말고 정본을 고친 뒤 사용자에게 알린다. 사용자가 `tools/home-sync.sh diff` 로 검토하고 `apply` 한다.
  관리 대상 목록은 `home/MANIFEST` 에 있다.

## 모델 사용
- haiku 는 **읽기 전용 위치 조사**(어디에 무엇이 있나)에만 쓴다. 파일 쓰기, 실행, 판단이 결과에 남는 일은 시키지 않는다.
  작은 모델은 규칙을 자주 어긴다.
- 쓰기나 위험이 있는 서브에이전트, 감사, 리뷰는 최소 sonnet 으로 한다.
- 규칙이나 스킬의 효과를 실측할 때도 sonnet 이상으로 잰다.

## 코드 리뷰 — 시킬 때를 기다리지 말고 먼저 한다
- 시점
  - 커밋하기 전에는 그 변경분을 리뷰한다.
  - 전체 리뷰를 한 지 오래됐거나 큰 구조 변경이 있었으면 전체 리뷰를 한다.
  - 버전이나 릴리스를 내기 전에 리뷰한다.
  - 의존 도구(luau, luau-lsp)를 올린 뒤에도 리뷰한다.
- 쓸 것
  - 내장: `/code-review`(버그), `/simplify`(품질), `/security-review`
  - Luau 관점별 감사: `/audit`. 타입, 런타임, 품질, 성능, 문서 감사자를 띄운다(설치 후).
  - 저장소 고유: 각 저장소의 review-round 류 스킬
- 발견은 재현해서 확인한 뒤 보고한다. 사용자가 찾기 전에 미리 찾는 것이 목적이다.
- 리뷰의 규모·강도·병렬 수는 프로젝트 지침(CLAUDE.md, memory)의 예산 규칙을 우선한다. 시점이 됐다는 이유로 대규모 리뷰를 띄우지 않는다.

## 도구
- Luau 툴체인은 mise. 셸 shim 이 "No version is set" 으로 실패하면
  `/code/.local/share/mise/installs/<tool>/<ver>/` 를 직접 호출한다.
- 벤치·퍼저·성능 실측은 `choom -n 1000 -- ...` 로 감싼다 (사용자 레벨 훅이 강제).
