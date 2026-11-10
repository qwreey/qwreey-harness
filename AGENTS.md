# AGENTS.md — luau-kb (Gemini, Codex 등 Claude Code 플러그인을 읽지 않는 에이전트용)

이 저장소는 Luau 타입 시스템의 한계와 검증 절차를 모은 정본 지식이다. Claude Code 는 플러그인(`.claude-plugin/`)으로 읽고, 다른 에이전트는 아래 평문 경로를 직접 읽는다. 내용은 같다.

## 언제 무엇을 읽나

| 상황 | 먼저 읽을 파일 (절대 경로) |
|---|---|
| Luau 타입 에러를 이해할 수 없다, 에러가 나야 할 곳에서 안 난다, 결과가 unknown 으로 샌다, 타입 팩·가변 인자 | `/code/Projects/luau-kb/skills/luau-types/SKILL.md` (결정 트리와 증상 → 파일 표) |
| 타입 검사 결과를 믿어도 되는지, 재현 파일 만들기, luau-analyze / luau-lsp 호출법, 스니펫 하네스 표식, require 해소 함정 | `/code/Projects/luau-kb/skills/luau-verify/SKILL.md` |
| 테스트·스펙 작성, 러너, 에러 메시지·사용자 줄 단언, `-O2` 로 테스트, mock 경계, GC·시간 의존 시험, 프레임워크(jest/TestEZ) 현황 | `/code/Projects/luau-kb/skills/luau-testing/SKILL.md` |
| 성능 측정법, 최적화 수준·인라인·native codegen 비용 | `/code/Projects/luau-kb/skills/luau-perf/` (작성 중일 수 있음, 있으면 `SKILL.md`) |
| 네이밍·관용구·모듈 구조·에러 처리·포맷 같은 코드 스타일과 타입이 못 잡는 언어 함정 | `/code/Projects/luau-kb/skills/luau-style/SKILL.md` |
| Roblox 엔진·서비스에 기대는 동작(task, 이벤트, Instance) 확인, mock 작성, Roblox Studio MCP, Roblox API 문서, globalTypes 정의 파일 | `/code/Projects/luau-kb/skills/roblox-luau/SKILL.md` |
| luau·luau-lsp·RFC 의 다가올 변화, 버전 올리기, 알려진 결함과 상류 항목 연결 | `/code/Projects/luau-kb/skills/luau-upstream/SKILL.md` |
| 공개 API 의 hover·자동완성·추론 타입(DX) 확인 | `/code/Projects/luau-kb/skills/luau-verify/references/checkers.md` §6, `/code/Projects/luau-kb/tools/lsp_probe.py` |

상세 references (각 SKILL.md 의 표가 절 번호까지 안내한다. luau-style, luau-perf, roblox-luau, luau-upstream 의 references 목록은 그 SKILL.md 를 본다):
- `/code/Projects/luau-kb/skills/luau-types/references/generics.md` — 제네릭 추론, `f<<T>>`, 콜백
- `/code/Projects/luau-kb/skills/luau-types/references/packs-and-varargs.md` — 타입 팩, 가변 인자, `select`/`pack`/`unpack`/`pcall`, 넘친 인자, defer 패턴
- `/code/Projects/luau-kb/skills/luau-types/references/variance.md` — read 필드, 팬텀 표식, 공변/불변, 입력·출력 자리 원칙
- `/code/Projects/luau-kb/skills/luau-types/references/unions-singletons.md` — 싱글턴, keyof/index, 좁히기, 유니온 구멍, 콜러블 테이블
- `/code/Projects/luau-kb/skills/luau-types/references/recursion-and-limits.md` — 재귀 별칭, 선언 순서, too complex, 한도 플래그
- `/code/Projects/luau-kb/skills/luau-types/references/type-functions.md` — type function 정책(D-04: 사안별 판단), 대안, 판단 절차
- `/code/Projects/luau-kb/skills/luau-types/references/type-functions-limits.md` — type function 의 제약·부작용(버전 열)
- `/code/Projects/luau-kb/skills/luau-types/references/solver-limits.md` — 새/옛 솔버, 결함 카탈로그(버전별)
- `/code/Projects/luau-kb/skills/luau-verify/references/negative-controls.md` — 음성 대조군, 돌연변이 검사, 체크리스트
- `/code/Projects/luau-kb/skills/luau-verify/references/checkers.md` — luau-analyze(`--fflags` 포함), luau-lsp 직접 호출, §6 DX 검사, §7 require 해소
- `/code/Projects/luau-kb/skills/luau-verify/references/toolchain.md` — mise shim 함정, 버전 핀, pesde·Rojo 링크
- `/code/Projects/luau-kb/skills/luau-verify/references/snippet-markers.md` — 스니펫 표식 문법, 실행 머리(`-O2`, 컴파일 출력, codegen), Roblox 모드
- `/code/Projects/luau-kb/skills/luau-verify/references/tooling.md` — .luaurc, 러너, const(D-01), stylua(D-02), 린트와 게이트 판정
- `/code/Projects/luau-kb/skills/luau-testing/references/runners.md` — luau CLI 러너 사실, 엔트리, 픽스처, lute/lune, 프레임워크 현황
- `/code/Projects/luau-kb/skills/luau-testing/references/assertions.md` — 단언 패턴, 에러 메시지 모양, 사용자 줄 단언
- `/code/Projects/luau-kb/skills/luau-testing/references/optimize-levels.md` — `-O1`/`-O2` 로 두 번 돌리는 이유, 지시어, getfenv
- `/code/Projects/luau-kb/skills/luau-testing/references/negative-controls.md` — 러너 대조군, 등록 누락, 돌연변이, 차등, 퍼즈, 시드
- `/code/Projects/luau-kb/skills/luau-testing/references/roblox-boundary.md` — luau + mock 경계, 엔진과 mock 이 갈리는 점, Deferred 심
- `/code/Projects/luau-kb/skills/luau-testing/references/gc-and-time.md` — GC·weak 프로브, 가상 시계
- `/code/Projects/luau-kb/skills/luau-testing/references/repo-practices.md` — 형제 저장소들의 실제 테스트 방식
- `/code/Projects/luau-kb/skills/roblox-luau/references/env-dependence.md` — luau+mock 으로 충분한가, Studio 가 필요한가 (판정 표)
- `/code/Projects/luau-kb/skills/roblox-luau/references/mocks.md` — mock 범위, 주입, 차이 기록, 충실도 검증
- `/code/Projects/luau-kb/skills/roblox-luau/references/studio-mcp.md` — Studio MCP 도구, 여러 Studio 고르기, studio-sync 규칙

## 읽는 법
- 절마다 `status: verified`(스니펫이 luau 0.734 와 0.742 에서 재현됨) 또는 `status: described`(원천 서술만 있음)가 붙어 있다. described 를 인용할 때는 미재현이라고 밝힌다.
- 근거 스니펫: `/code/Projects/luau-kb/snippets/*.luau`, 결과표: `/code/Projects/luau-kb/snippets/RESULTS.md`.
- 결정된 정책(D-01 const, D-02 stylua, D-03 러너, D-04 type function, D-06 검사기)은 `/code/Projects/luau-kb/decisions/` 의 요약을 따른다. `> 정책: 미정` 표시가 남은 항목(지금은 D-05 버전 핀)은 한쪽을 고르지 말고 양쪽 입장을 전한다. 목록은 `/code/Projects/luau-kb/decisions/README.md`.
- 도구는 PATH 의 mise shim 대신 `/code/.local/share/mise/installs/luau/<ver>/luau-analyze` 처럼 버전 경로로 직접 부른다.

## 이 저장소를 고칠 때
- 새 사실은 `snippets/` 에 최소 재현과 표식을 먼저 넣고 `python3 -I tools/check_snippets.py --luau 0.734,0.742 snippets/*.luau` 가 rc=0 인지 확인한다. 실행 조건(`-O2`, `--codegen`)이나 Roblox 정의 파일이 필요한 주장은 하네스 머리로 고정한다(`skills/luau-verify/references/snippet-markers.md` §2a·§2b).
- 프로젝트 고유 설계(특정 라이브러리의 타입 이름, API)는 넣지 않는다. 일반 Luau 지식만 둔다.
