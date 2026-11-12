# AGENTS.md — luau-kb (codex, agy 등 Claude Code 플러그인을 읽지 않는 에이전트용)

이 저장소는 여러 Luau 저장소에 흩어져 있던 일반 Luau·Roblox 지식(타입 시스템의 한계, 검증 절차, 테스트, 성능, 스타일, Roblox 엔진 동작, 업스트림 변화)의 정본이다. 스킬 12개(문서 조회 도구 `tools/roblox_docs.py` 포함)와 경로 조건부 rules 2개로 나뉜다. Claude Code 는 플러그인(`.claude-plugin/`)으로 읽고, 다른 에이전트는 아래 평문 경로를 직접 읽는다. 내용은 같다.

## 언제 무엇을 읽나

| 상황 | 먼저 읽을 파일 (절대 경로) |
|---|---|
| Luau 타입 에러를 이해할 수 없다, 에러가 나야 할 곳에서 안 난다, 결과가 unknown 으로 샌다, 타입 팩·가변 인자 | `/code/Projects/claude-doctor/packs/luau-kb/skills/luau-types/SKILL.md` (결정 트리와 증상 → 파일 표) |
| 타입 검사 결과를 믿어도 되는지, 재현 파일 만들기, luau-analyze / luau-lsp 호출법, 스니펫 하네스 표식, require 오타가 검사기에 잡히는지 | `/code/Projects/claude-doctor/packs/luau-kb/skills/luau-verify/SKILL.md` |
| 테스트·스펙 작성, 러너, 에러 메시지·사용자 줄 단언, `-O2` 로 테스트, mock 경계, GC·weak 프로브, 시간 의존 시험, 프레임워크(jest/TestEZ) 현황 | `/code/Projects/claude-doctor/packs/luau-kb/skills/luau-testing/SKILL.md` |
| 코드가 느리다, 벤치마크 짜기·해석, 메타테이블·테이블·순회·호출·문자열 비용, 최적화 수준·인라인·native, 약한 표·GC 비용, 객체 크기 | `/code/Projects/claude-doctor/packs/luau-kb/skills/luau-perf/SKILL.md` |
| 네이밍·관용구·모듈 구조·파일 분리·에러 처리·주석·포맷 같은 코드 스타일과 타입이 못 잡는 언어 함정 | `/code/Projects/claude-doctor/packs/luau-kb/skills/luau-style/SKILL.md` |
| weak 표 의미론·누수 판정(ephemeron 없음, `__mode`), 코루틴 에러 삼킴·yield 불가 문맥, luau CLI 의 require 경로 해석(`init.luau`·`@self`·alias·symlink) — Roblox 엔진 없이 성립하는 것 | `/code/Projects/claude-doctor/packs/luau-kb/skills/luau-runtime/SKILL.md` |
| Roblox 코드를 luau+mock 으로 시험할지 Studio 가 필요한지, mock 작성, Roblox Studio MCP, Roblox API 의 타입(`Instance.new`·`GetAttribute`·Enum), globalTypes 정의 파일·sourcemap | `/code/Projects/claude-doctor/packs/luau-kb/skills/luau-roblox/SKILL.md` |
| Roblox 엔진 핵심 동작: 시그널(Deferred), Instance 수명·Destroy, Tween, `task`·경쟁, Actor·병렬, Studio 문자열 require·모듈 캐시, Roblox 안 GC 관찰, 엔진 비용 | `/code/Projects/claude-doctor/packs/luau-kb/skills/roblox-engine/SKILL.md` |
| 원격·복제·네트워크 소유권·스트리밍, DataStore·MemoryStore·상품·글자 필터·Open Cloud | `/code/Projects/claude-doctor/packs/luau-kb/skills/roblox-net/SKILL.md` |
| GUI 입력·레이아웃·톱바 인셋, DragDetector·물리·캐릭터·카메라·런타임 에셋 | `/code/Projects/claude-doctor/packs/luau-kb/skills/roblox-world/SKILL.md` |
| Roblox 공식 문서 조회(API 시그니처, 보안·스레드 안전성, deprecated, 문서 근거 인용) | `/code/Projects/claude-doctor/packs/luau-kb/skills/roblox-docs/SKILL.md`, 도구 `python3 -I /code/Projects/claude-doctor/packs/luau-kb/tools/roblox_docs.py` |
| luau·luau-lsp·stylua 를 올릴지, 새 문법·RFC 를 지금 써도 되는지, 알려진 결함이 상류에서 고쳐지는지 | `/code/Projects/claude-doctor/packs/luau-kb/skills/luau-upstream/SKILL.md` |
| 공개 API 의 hover·자동완성·추론 타입(DX) 확인 | `/code/Projects/claude-doctor/packs/luau-kb/skills/luau-verify/references/checkers.md` §6, `/code/Projects/claude-doctor/packs/luau-kb/tools/lsp_probe.py` |
| `.luau` 파일을 쓸 때 항상 지킬 짧은 규칙 | `/code/Projects/claude-doctor/packs/luau-kb/rules/luau-core.md` (경로 조건부 규칙, `/code/Projects/claude-doctor/packs/luau-kb/rules/README.md`) |
| 파일 길이·분리·폴더 묶음 같은 코드 구조 규칙 | 정본은 사용자 레벨 `~/.claude/rules/code-structure.md`(claude-doctor `home/.claude/rules/code-structure.md`, 툴킷 공통). Luau 세부는 `/code/Projects/claude-doctor/packs/luau-kb/skills/luau-style/references/structure.md`·`splitting.md`. `/code/Projects/claude-doctor/packs/luau-kb/rules/code-structure.md` 는 이 안내만 둔다 |

### 주제가 여러 스킬에 걸칠 때의 정본
- weak 표: 의미론(ephemeron 없음, `__mode`)·누수 판정은 luau-runtime `gc-and-weak-tables.md`, Roblox 안 GC 관찰·Instance weak 키는 roblox-engine `gc-in-roblox.md`·`instance-lifecycle.md` §4, 비용·객체 크기·클로저 캐시는 luau-perf `gc-and-memory.md`, 누수 판정 하네스·프로브 함정은 luau-testing `gc-and-time.md`.
- require: 언어 차원 경로 해석(CLI)은 luau-runtime `require-by-string.md`, Studio 문자열 require·ModuleScript 캐시는 roblox-engine `require-in-roblox.md`, 검사기 대 런타임 판정표는 luau-verify `checkers.md` §7, 쓰는 규칙(`@self`, 리터럴, 엔트리 이름)은 luau-style `modules.md`.
- 코루틴: 순수 의미론은 luau-runtime `coroutines.md`, Roblox `task` 라이브러리는 roblox-engine `tasks-and-threads.md`, 비용은 luau-perf `calls-and-closures.md`.
- `-O2` 와 `error(msg, level)`: 경우별 표는 luau-testing `optimize-levels.md` §2, raise 헬퍼 처방은 luau-style `errors.md` §2, 인라인 규칙은 luau-perf `optimizer-and-native.md` §3.

상세 references (각 SKILL.md 의 표가 절 번호까지 안내한다):

luau-types
- `/code/Projects/claude-doctor/packs/luau-kb/skills/luau-types/references/generics.md` — 제네릭 추론, `f<<T>>`, 콜백
- `/code/Projects/claude-doctor/packs/luau-kb/skills/luau-types/references/packs-and-varargs.md` — 타입 팩, 가변 인자, `select`/`pack`/`unpack`/`pcall`, 넘친 인자, defer 패턴
- `/code/Projects/claude-doctor/packs/luau-kb/skills/luau-types/references/variance.md` — read 필드, 팬텀 표식, 공변/불변, 입력·출력 자리 원칙
- `/code/Projects/claude-doctor/packs/luau-kb/skills/luau-types/references/unions-singletons.md` — 싱글턴, keyof/index, 좁히기, 유니온 구멍, 콜러블 테이블
- `/code/Projects/claude-doctor/packs/luau-kb/skills/luau-types/references/recursion-and-limits.md` — 재귀 별칭, 선언 순서, too complex, 한도 플래그
- `/code/Projects/claude-doctor/packs/luau-kb/skills/luau-types/references/type-functions.md` — type function 정책(D-04: 사안별 판단), 대안, 판단 절차
- `/code/Projects/claude-doctor/packs/luau-kb/skills/luau-types/references/type-functions-limits.md` — type function 의 제약·부작용(버전 열)
- `/code/Projects/claude-doctor/packs/luau-kb/skills/luau-types/references/solver-limits.md` — 새/옛 솔버, 결함 카탈로그(버전별)

luau-verify
- `/code/Projects/claude-doctor/packs/luau-kb/skills/luau-verify/references/negative-controls.md` — 음성 대조군, 돌연변이 검사, 체크리스트
- `/code/Projects/claude-doctor/packs/luau-kb/skills/luau-verify/references/checkers.md` — luau-analyze(`--fflags` 포함), luau-lsp 직접 호출, §6 DX 검사, §7 require 해소(검사기 대 런타임)
- `/code/Projects/claude-doctor/packs/luau-kb/skills/luau-verify/references/toolchain.md` — mise shim 함정, 버전 핀, pesde·Rojo 링크
- `/code/Projects/claude-doctor/packs/luau-kb/skills/luau-verify/references/snippet-markers.md` — 스니펫 표식 문법, 실행 머리(`-O2`, 컴파일 출력, codegen), Roblox 모드
- `/code/Projects/claude-doctor/packs/luau-kb/skills/luau-verify/references/tooling.md` — .luaurc, 러너, const(D-01), stylua(D-02), 린트와 게이트 판정

luau-testing
- `/code/Projects/claude-doctor/packs/luau-kb/skills/luau-testing/references/runners.md` — luau CLI 러너 사실, 엔트리, 픽스처, lute/lune, 프레임워크 현황
- `/code/Projects/claude-doctor/packs/luau-kb/skills/luau-testing/references/assertions.md` — 단언 패턴, 에러 메시지 모양, 사용자 줄 단언
- `/code/Projects/claude-doctor/packs/luau-kb/skills/luau-testing/references/optimize-levels.md` — `-O1`/`-O2` 로 두 번 돌리는 이유, 지시어, getfenv
- `/code/Projects/claude-doctor/packs/luau-kb/skills/luau-testing/references/negative-controls.md` — 러너 대조군, 등록 누락, 돌연변이, 차등, 퍼즈, 시드
- `/code/Projects/claude-doctor/packs/luau-kb/skills/luau-testing/references/roblox-boundary.md` — luau + mock 경계, 엔진과 mock 이 갈리는 점, Deferred 심
- `/code/Projects/claude-doctor/packs/luau-kb/skills/luau-testing/references/gc-and-time.md` — GC·weak 프로브, 가상 시계
- `/code/Projects/claude-doctor/packs/luau-kb/skills/luau-testing/references/repo-practices.md` — 형제 저장소들의 실제 테스트 방식

luau-perf
- `/code/Projects/claude-doctor/packs/luau-kb/skills/luau-perf/references/benchmarking-method.md` — 측정부터, 벤치 하네스, 모드 선택
- `/code/Projects/claude-doctor/packs/luau-kb/skills/luau-perf/references/metatables.md` — 메타테이블 세금의 범위와 피하는 법
- `/code/Projects/claude-doctor/packs/luau-kb/skills/luau-perf/references/tables.md` — 배열부·해시부 성장 규칙과 함정
- `/code/Projects/claude-doctor/packs/luau-kb/skills/luau-perf/references/iteration.md` — 순회 모양별 비용
- `/code/Projects/claude-doctor/packs/luau-kb/skills/luau-perf/references/calls-and-closures.md` — 호출 모양, 가변 인자, 클로저, pcall·코루틴 비용
- `/code/Projects/claude-doctor/packs/luau-kb/skills/luau-perf/references/strings.md` — 문자열 누적, 파싱, 패턴 역추적
- `/code/Projects/claude-doctor/packs/luau-kb/skills/luau-perf/references/optimizer-and-native.md` — 최적화 수준, 인라인, 인라인 캐시, native 코드 생성
- `/code/Projects/claude-doctor/packs/luau-kb/skills/luau-perf/references/gc-and-memory.md` — 약한 표 비용, GC 시간, 객체 크기, 클로저 캐시
- `/code/Projects/claude-doctor/packs/luau-kb/skills/luau-perf/references/algorithms-and-structures.md` — 알고리즘과 자료구조 고르기

luau-style
- `/code/Projects/claude-doctor/packs/luau-kb/skills/luau-style/references/naming.md` — 이름 짓기
- `/code/Projects/claude-doctor/packs/luau-kb/skills/luau-style/references/idioms.md` — 문법 관용구
- `/code/Projects/claude-doctor/packs/luau-kb/skills/luau-style/references/modules.md` — 파일 머리, 모듈 모양, require 쓰는 규칙
- `/code/Projects/claude-doctor/packs/luau-kb/skills/luau-style/references/structure.md` — 파일 길이, 폴더 묶음, 데이터와 코드 나누기
- `/code/Projects/claude-doctor/packs/luau-kb/skills/luau-style/references/errors.md` — 에러 던지기·잡기·테스트, `-O2` 와 raise 헬퍼
- `/code/Projects/claude-doctor/packs/luau-kb/skills/luau-style/references/pitfalls.md` — 타입 검사가 못 잡는 언어 함정
- `/code/Projects/claude-doctor/packs/luau-kb/skills/luau-style/references/quality.md` — 주석, 마커, 포맷, 테스트 관용, 검증과 보고
- `/code/Projects/claude-doctor/packs/luau-kb/skills/luau-style/references/project-overrides.md` — 저장소마다 다른 값과 결정 상태

luau-runtime
- `/code/Projects/claude-doctor/packs/luau-kb/skills/luau-runtime/references/gc-and-weak-tables.md` — weak 표 의미론, 누수 조건과 판정, 프로브 함정, weak 설계 처방
- `/code/Projects/claude-doctor/packs/luau-kb/skills/luau-runtime/references/coroutines.md` — 코루틴 에러 삼킴, yield 할 수 없는 문맥, 문맥 전파 없음
- `/code/Projects/claude-doctor/packs/luau-kb/skills/luau-runtime/references/require-by-string.md` — luau CLI require 경로 해석, ambiguous 에러, alias, symlink, 정적 검사, 패키지 사본

luau-roblox
- `/code/Projects/claude-doctor/packs/luau-kb/skills/luau-roblox/references/env-dependence.md` — luau+mock 으로 충분한가, Studio 가 필요한가 (판정 표)
- `/code/Projects/claude-doctor/packs/luau-kb/skills/luau-roblox/references/mocks.md` — mock 범위, 주입, 차이 기록, 충실도 검증
- `/code/Projects/claude-doctor/packs/luau-kb/skills/luau-roblox/references/studio-mcp.md` — Studio MCP 도구, 여러 Studio 고르기, studio-sync 규칙
- `/code/Projects/claude-doctor/packs/luau-kb/skills/luau-roblox/references/api-types.md` — Instance·Enum·서비스·속성·엔진 호출의 타입
- `/code/Projects/claude-doctor/packs/luau-kb/skills/luau-roblox/references/typedefs.md` — Roblox 정의 파일과 sourcemap 을 luau-lsp 에 넘기기

roblox-engine
- `/code/Projects/claude-doctor/packs/luau-kb/skills/roblox-engine/references/signals-and-events.md` — RBXScriptSignal 배달 시점·순서·끊기, 속성 변경 신호
- `/code/Projects/claude-doctor/packs/luau-kb/skills/roblox-engine/references/instance-lifecycle.md` — Destroy, Destroying, 파괴된 Instance, userdata 신원, 수명 묶기, 누수
- `/code/Projects/claude-doctor/packs/luau-kb/skills/roblox-engine/references/instance-api.md` — 트리 API, Clone, Attribute·태그, QueryDescendants, 데이터 타입 값
- `/code/Projects/claude-doctor/packs/luau-kb/skills/roblox-engine/references/tween-and-animation.md` — TweenService 엔진 사실
- `/code/Projects/claude-doctor/packs/luau-kb/skills/roblox-engine/references/tasks-and-threads.md` — task 라이브러리, 협력 스케줄링의 경쟁, 시한, 시계
- `/code/Projects/claude-doctor/packs/luau-kb/skills/roblox-engine/references/parallel-luau.md` — Actor, 병렬 단계, 스레드 안전 등급, SharedTable
- `/code/Projects/claude-doctor/packs/luau-kb/skills/roblox-engine/references/require-in-roblox.md` — Studio 문자열 require, ModuleScript 캐시, VM 경계
- `/code/Projects/claude-doctor/packs/luau-kb/skills/roblox-engine/references/gc-in-roblox.md` — Roblox 안 GC 관찰, Instance·연결이 얽힌 수거
- `/code/Projects/claude-doctor/packs/luau-kb/skills/roblox-engine/references/perf.md` — Roblox 엔진 쪽 비용 기준치, 최적화 수준

roblox-net
- `/code/Projects/claude-doctor/packs/luau-kb/skills/roblox-net/references/remotes-and-replication.md` — 원격·바인더블 신뢰 경계, 복제, 네트워크 소유권, 스트리밍
- `/code/Projects/claude-doctor/packs/luau-kb/skills/roblox-net/references/platform-services.md` — DataStore·MemoryStore·상품·글자 안전·게시 도구

roblox-world
- `/code/Projects/claude-doctor/packs/luau-kb/skills/roblox-world/references/gui-and-input.md` — GUI 레이아웃·자동 크기·입력 전달
- `/code/Projects/claude-doctor/packs/luau-kb/skills/roblox-world/references/world-and-physics.md` — DragDetector, 물리, 캐릭터, 카메라, 런타임 에셋

roblox-docs
- `/code/Projects/claude-doctor/packs/luau-kb/skills/roblox-docs/references/sources.md` — 문서 조회 방식 비교, `tools/roblox_docs.py` 명령, 온라인 대체(llms.txt), 인용 규칙, 신뢰 경계

luau-upstream
- `/code/Projects/claude-doctor/packs/luau-kb/skills/luau-upstream/references/sources.md` — 업스트림을 어디서, 얼마나 자주 보나
- `/code/Projects/claude-doctor/packs/luau-kb/skills/luau-upstream/references/watchlist.md` — 알려진 한계와 그것을 고칠 업스트림 항목
- `/code/Projects/claude-doctor/packs/luau-kb/skills/luau-upstream/references/syntax-adoption.md` — 새 문법 채택 판정표
- `/code/Projects/claude-doctor/packs/luau-kb/skills/luau-upstream/references/version-bump.md` — luau / luau-lsp / stylua 올리는 절차와 bug-scan
- `/code/Projects/claude-doctor/packs/luau-kb/skills/luau-upstream/references/roadmap-notes.md` — 진행 중인 큰 변화

## 읽는 법
- 절마다 `status: verified`(스니펫이 luau 0.734 와 0.742 에서 재현됨) 또는 `status: described`(원천 서술만 있음)가 붙어 있다. described 를 인용할 때는 미재현이라고 밝힌다.
- 근거 스니펫: `/code/Projects/claude-doctor/packs/luau-kb/snippets/*.luau`, 결과표: `/code/Projects/claude-doctor/packs/luau-kb/snippets/RESULTS.md`.
- 결정된 정책(D-01 const, D-02 stylua, D-03 러너, D-04 type function, D-06 검사기)은 `/code/Projects/claude-doctor/packs/luau-kb/decisions/` 의 요약을 따른다. `> 정책: 미정` 표시가 남은 항목(D-05 버전 핀)과 `> 정책: 제안(D-xx)` 표시(D-07~D-13, 사용자 미확인)는 한쪽을 강제하지 말고 양쪽 입장과 제안을 함께 전한다. 목록은 `/code/Projects/claude-doctor/packs/luau-kb/decisions/README.md`.
- 도구는 PATH 의 mise shim 대신 `/code/.local/share/mise/installs/luau/<ver>/luau-analyze` 처럼 버전 경로로 직접 부른다.

## 이 저장소를 고칠 때
- 새 사실은 `snippets/` 에 최소 재현과 표식을 먼저 넣고 `python3 -I tools/check_snippets.py --luau 0.734,0.742,0.746 snippets/*.luau` 가 rc=0 인지 확인한다. 실행 조건(`-O2`, `--codegen`)이나 Roblox 정의 파일이 필요한 주장은 하네스 머리로 고정한다(`skills/luau-verify/references/snippet-markers.md` §2a·§2b).
- 프로젝트 고유 설계(특정 라이브러리의 타입 이름, API)는 넣지 않는다. 일반 Luau 지식만 둔다.
