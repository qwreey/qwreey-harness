# (A) 감사 서브에이전트 분할 설계

2026-11-10 초안. 근거는 `audit/01` §3, `audit/03` §2·§5, `audit/04` §4, `quad/.claude/conventions.md:268-338·389-485`, `quad/.claude/agents/quad-doc-auditor.md`, `rbvm/.claude/agents/*.md`, `quad/.claude/qa-request/post-implementation-review-round16.md`이다. 공식 frontmatter 동작은 code.claude.com/docs/en/sub-agents.md에서 다시 확인했다(2026-11-10).

## 1. 파일

| 파일 | 설치 위치 | 역할 |
|---|---|---|
| `luau-type-auditor.md` | `~/.claude/agents/` | 타입 건전성, any 누수, 음성 대조군 |
| `luau-runtime-auditor.md` | 같음 | 수명 주기, GC, 동시성, 엔진 시맨틱(Studio는 '실측 필요'로만) |
| `luau-quality-auditor.md` | 같음 | 네이밍, 관용구, 구조, 주석, 테스트 구조 |
| `luau-perf-auditor.md` | 같음 | 핫 경로와 성능 주장 실측. 자동 선택하지 않음 |
| `docs-auditor.md` | 같음 | 문서 코퍼스 정합성, 문서↔코드. Luau 전용이 아니라 이름에 luau가 없다 |
| `skills/audit-report-format/SKILL.md` | 사용자 스킬(또는 luau-kb 플러그인) | 다섯 에이전트가 프리로드하는 공통 보고 형식. 형식을 한 곳에만 둔다 |
| `skills/audit/SKILL.md` | 사용자 스킬 | `/audit` 오케스트레이션 |
| `hooks/auditor-readonly-guard.py` | `~/.claude/hooks/` (chmod +x) | 읽기 전용 강제 훅. `hooks/test-guard.py`로 34개 경우를 회귀 검사함(현재 34/34) |

## 2. 에이전트 표

| 에이전트 | skills 프리로드 | tools | disallowedTools | Write 범위 | model / effort / maxTurns |
|---|---|---|---|---|---|
| luau-type-auditor | audit-report-format, luau-types, luau-verify | Read, Grep, Glob, Bash, Write, WebFetch | Edit, NotebookEdit | `/tmp/claude-audit/`만(훅) | sonnet / high / 80 |
| luau-runtime-auditor | audit-report-format, luau-verify, roblox-luau | Read, Grep, Glob, Bash, Write, WebFetch, WebSearch | Edit, NotebookEdit | 같음 | sonnet / high / 80 |
| luau-quality-auditor | audit-report-format, luau-style | Read, Grep, Glob, Bash | Edit, Write, NotebookEdit | 없음 | sonnet / medium / 50 |
| luau-perf-auditor | audit-report-format, luau-perf, luau-verify | Read, Grep, Glob, Bash, Write | Edit, NotebookEdit | `/tmp/claude-audit/`만(훅) | sonnet / high / 80 |
| docs-auditor | audit-report-format | Read, Grep, Glob, Bash | Edit, Write, NotebookEdit | 없음 | sonnet / medium / 60 |

모든 에이전트는 공통으로 `hooks.PreToolUse`(matcher `Bash|Write|Edit|MultiEdit|NotebookEdit|mcp__.*`) → `auditor-readonly-guard.py`를 건다.

### 뺀 후보와 더하지 않은 후보

- **API 동등성(rbvm-api-parity) 관점**은 공용으로 만들지 않았다. "엔진과 다르게 동작하는 곳"이라는 일반 각도는 runtime에 넣었다. rbvm의 "Instance 메서드 전수 대조 vs `IndexableMethods`" 절차는 rbvm 고유다(§6).
- **테스트 공백 관점**은 따로 두지 않았다. 각 관점이 "그 관점의 게이트에 음성 줄·회귀 절이 있는가"를 본다(type의 "타입 게이트의 공백", quality의 "테스트 구조").
- **diff 국소 결함**은 내장 `/code-review`의 몫이다. quad 실측(2026-08-18, 08-26)에서 감사자와 code-review는 서로 다른 것을 잡았다. 그래서 `/audit`은 code-review를 대체하지 않는다고 적었다.

## 3. 읽기 전용을 강제하는 방식 (세 줄)

`audit/04` §4.2-1의 약점은 "Bash가 있어서 읽기 전용이 규약으로만 지켜진다"였다. 이를 세 줄로 막는다.

1. **도구 목록**: `tools` 허용 목록에 Edit을 넣지 않고, `disallowedTools`에도 Edit, NotebookEdit을 둔다. quality와 docs는 Write도 뺀다.
2. **PreToolUse 훅** (`auditor-readonly-guard.py`)
   - Write/Edit은 `/tmp/claude-audit/` 밖이면 거부한다.
   - Bash에서 거부하는 것
     - 쓰기 명령의 대상이 스크래치 밖인 경우, 리다이렉션 대상이 스크래치 밖인 경우
     - `sed -i`
     - 작업 트리, 인덱스, ref를 바꾸는 git 하위 명령. `stash`, `checkout`, `add`, `branch -D` 등이 해당하고, `git show HEAD:`는 허용한다.
     - `pesde`, `npm`, `mise install/trust`, `curl`
   - `mcp__roblox-studio__*`는 전부 거부한다.
3. **결과 대조**: `/audit` 0단계에서 HEAD와 `git status` 해시를 찍고, 2단계에서 비교한다. agy-delegate.sh의 guard.txt와 같은 방식이다. 훅이 못 보는 쓰기를 여기서 잡는다. `bash ./scripts/test.sh` 안의 relink나 `python3 -c` 안의 쓰기가 그런 예다.

### permissionMode를 쓰지 않는 이유

- 공식 문서에 따르면, 메인 대화가 `bypassPermissions`, `acceptEdits`, `auto`이면 서브에이전트의 `permissionMode`는 **무시된다**.
- 이 사용자의 `~/.claude/settings.json`은 `defaultMode: auto`이다(`audit/04` §7). 그래서 `permissionMode: plan`을 적어도 효과가 없다. 위 세 줄에 기댄다.

### Bash를 허용하는 위험 (남는 것)

| 위험 | 막는 줄 | 남는 구멍 |
|---|---|---|
| 프로젝트 스크립트가 트리를 바꿈(relink, sourcemap, `luau_packages`) | 3(가드 비교) | 바뀐 뒤에야 안다. 에이전트 본문에 "트리를 바꾸는 준비 단계는 돌리지 말고 미완으로"라고 적었다 |
| 인터프리터 안의 쓰기(`python3 -c 'open(...,"w")'`, `luau` 프로브의 `io`) | 3 | luau CLI에는 파일 쓰기가 거의 없다. python은 훅이 못 본다 |
| 메모리 폭주(벤치, 퍼저) | 사용자 레벨 heavy-proc-guard 훅(사용자 settings의 훅은 서브에이전트에서도 발화) + perf 본문의 예산 규칙 | 이름에 bench/fuzz가 없는 무거운 실행 |
| 비밀 읽기(`.env`, `~/.claude/.credentials.json`) | 사용자 레벨 deny `Read(./.env*)`(P1). Bash `cat`은 못 막음 | 감사자는 그런 파일을 볼 이유가 없다. 필요하면 훅에 경로 패턴을 더한다 |
| 다른 저장소 읽기 | 막지 않음(읽기는 무해) | — |

### 훅 경로와 신뢰

- 프로젝트 레벨 서브에이전트의 frontmatter 훅은 작업공간 신뢰 전까지 건너뛴다(공식 문서). 사용자 레벨(`~/.claude/agents`)에 두면 이 문제가 없다.
- 플러그인 서브에이전트는 `hooks`와 `permissionMode`가 **무시된다**(공식 문서). 그래서 이 에이전트들은 luau-kb 플러그인이 아니라 **사용자 레벨 파일**로 둔다. 스킬(`luau-types` 등)은 플러그인으로 가도 된다.
- 스킬이 플러그인으로 설치되면 프리로드 이름이 `luau-kb:luau-types`꼴이 될 수 있다(미확인). PLAN §4-1 결정(심볼릭 링크 vs 플러그인) 뒤에 `skills:` 목록을 맞춘다.

## 4. memory를 쓰지 않는 이유

PLAN §3은 rbvm 감사자에 `memory: project`를 제안했다. 이 설계는 **쓰지 않는 쪽**을 기본으로 한다. 이유는 넷이다.

1. **감사자의 가치는 신선한 맥락이다.** quad와 rbvm 모두 "변경한 세션은 자기가 무엇을 안 건드렸는지 모른다"를 감사자의 존재 이유로 적었다. 누적 메모리는 감사자를 다시 "아는 세션"으로 만든다. 실제로 quad-doc-auditor의 메모리에는 "자기참조 개수 금지" 같은 교훈과 낡은 서술이 같이 쌓였다(`audit/03` §3).
2. **memory는 Read, Write, Edit을 자동으로 켠다**(공식 문서, quad 2026-08-16 실측과 일치). 읽기 전용 설계와 정면으로 충돌한다. 훅이 막기는 하지만, 막히는 도구를 켜 둘 이유가 없다.
3. `memory: project`는 `<프로젝트>/.claude/agent-memory/<이름>/`에 쓴다. 다른 세션이 돌고 있는 프로젝트 트리를 감사자가 바꾸게 된다. 그러면 가드 비교도 "CHANGED"가 된다.
4. 교훈의 갈 곳이 이미 있다.
   - 일반 교훈은 메인이 `luau-types` references나 `audit-report-format`에 올린다.
   - 프로젝트 교훈은 `.claude/audit-focus/<관점>.md`에 올린다.
   - 둘 다 사람이 검토하는 정본이다.

예외로, 감사자의 학습을 꼭 누적하고 싶은 프로젝트는 그 프로젝트 쪽에 얇은 래퍼 에이전트를 둔다. 래퍼는 `memory: local`을 쓰고(git에 안 올라감), 훅 화이트리스트에 `.claude/agent-memory-local/<이름>/`을 더한다. 이 예외는 사용자 결정이다.

## 5. 모델과 effort

- 기본은 **sonnet**이다.
  - quad 사용자 결정(2026-08-16): "감사자는 sonnet 유지, haiku로 낮추지 말 것". 문맥 추론이 들어가는 발견이 많았기 때문이다.
  - devplorer 결정(2026-10-21): "리뷰 모델은 sonnet 기본".
- 깊은 감사는 `/audit --deep`이 **호출할 때만** `model: "opus"`를 넘긴다. 호출 인자가 frontmatter보다 우선한다(공식 해석 순서: 호출 인자 > frontmatter > `CLAUDE_CODE_SUBAGENT_MODEL` > 메인).
  - frontmatter에 `inherit`를 두지 않는다. 메인이 opus나 fable이면 감사 팬아웃 비용이 그대로 곱해진다. quad 2026-09-01 사례: 앵글 에이전트 8개가 fable로 돌아 세션 누계 $589.
- effort
  - 실측 설계가 필요한 type, runtime, perf는 `high`
  - 대조 중심인 quality, docs는 `medium`
  - `CLAUDE_CODE_EFFORT_LEVEL` 환경 변수가 있으면 그것이 이긴다.
- `maxTurns`: 닿으면 부분 결과로 돌아온다. 이 부분 결과는 보고 형식의 `미완`과 같은 뜻으로 다룬다.

## 6. 프로젝트 고유 지식을 두는 곳

에이전트 본문에는 코드 세부(파일명, 함수명, Order 번호)를 넣지 않는다. 에이전트는 다음 순서로 읽는다.

1. `CLAUDE.md` 계층. 서브에이전트가 자동으로 받는다.
2. `.claude/rules/*.md` 중 paths가 맞는 것. 대상 파일을 Read할 때 자동으로 따라 들어온다.
3. **`.claude/audit-focus/<관점>.md`**. 이 설계가 새로 제안하는 프로젝트 쪽 파일이다. 그 프로젝트에서 이 관점이 특히 볼 곳, 정본 문서 경로, 알려진 예외를 적는다. 점검 기준은 정본 설계 문서를 가리키기만 하고 다시 적지 않는다.
4. 호출 프롬프트(범위, 바뀐 결정, 기보고 경로).

예시: `examples/rbvm-audit-focus-runtime.md`. rbvm-gc-auditor 본문의 점검 항목을 이 꼴로 옮긴 것이다.

## 7. rbvm 기존 에이전트 판정

| 에이전트 | 판정 | 이유 | 옮기는 법 |
|---|---|---|---|
| `rbvm-gc-auditor` | **공용 `luau-runtime-auditor`로 대체** | 점검 항목 다섯(사슬 절단, `__mode`, 정리 경로, 동일성 불변식, Destroy 전파) 중 넷은 runtime의 일반 각도(수명 주기, GC)와 같다. 남는 것은 rbvm 고유 불변식 목록뿐이고, 그것은 이미 `.claude/design/gc-and-lifecycle.md`가 정본이다. 본문에 박힌 코드 세부(`proxy/base.luau`, `Order 14 이상`)가 낡는 문제도 이렇게 풀린다 | `rbvm/.claude/audit-focus/runtime.md`(예시 파일)를 두고, `CLAUDE.md`의 "GC 코드 변경 시 gc-auditor 호출" 한 줄을 "`/audit runtime`"으로 바꾼다 |
| `rbvm-api-parity` | **프로젝트 에이전트로 남기되 얇게 고침** | 엔진 시맨틱 대조라는 각도는 runtime과 겹친다. 하지만 이 에이전트의 가치는 rbvm 고유 절차에 있다. Roblox `Instance` 클래스 문서의 메서드 전수를 `IndexableMethods`와 대조해 "가상 트리를 무시하고 실 트리로 새는 메서드"를 찾는 절차다. 이 절차를 audit-focus에 넣으면 runtime 감사자가 매번 그 무거운 전수 대조를 하게 된다 | frontmatter를 공용 세트와 맞춘다: `disallowedTools`, 훅, `skills: [audit-report-format, roblox-luau]`. "알려진 의도적 차이" 하드코딩 목록은 `design/architecture.md`로 옮기고 본문은 그 절을 가리키게 한다. 출력 형식 절은 지우고 프리로드로 대신한다 |
| (참고) `VideoSync/ref-researcher` | 이 세트 밖 | 감사자가 아니라 쓰기가 필요한 연구자다. `audit/04` §9-5대로 BRIEF 경로를 인자화한 별도 사용자 에이전트가 맞다 | — |
| (참고) `quad-doc-auditor` | 당분간 유지 | quad 고유 `doc-check.py`와 색인 레이어 규약에 묶여 있다. `docs-auditor`는 quad 밖 저장소용이다. quad의 conventions 다이어트(P3) 때 `docs-auditor` + `quad/.claude/audit-focus/docs.md`로 바꿀 수 있는지 다시 본다 | — |

전환 조건: 기존 에이전트를 지우기 전에 같은 범위로 신·구를 한 번씩 돌린다. 구 에이전트가 잡은 기보고 발견을 신 에이전트도 잡는지 본다(평가 시나리오 R1). rbvm은 다른 세션이 쓰는 저장소가 아니므로 P1 직후 시범으로 적당하다.

## 8. 평가 시나리오 (도입 전, `audit/01` §7)

| ID | 시나리오 | 기대 |
|---|---|---|
| T1 | 옵셔널 자리에 전체형 `Source<T>`를 둔 props 타입(quad H-944 꼴) | type 감사자가 음성 줄을 만들어 "안 잡힘"을 실측으로 보고 |
| T2 | 진단 0건인 파일인데 한도 플래그를 빼고 돌린 경우 | 플래그 차이를 지적하고, 대조군으로 진단이 사라짐을 보임 |
| R1 | rbvm에서 `nop(gcHold)`를 클로저 밖으로 옮긴 브랜치 | runtime이 audit-focus를 읽고 사슬 절단을 `높음`으로 보고(구 gc-auditor와 같은 결과) |
| R2 | 엔진 시그널 순서에 기댄 코드 | `대조`(문서 URL) 또는 "Studio 실측 필요"로 올리고 `실측`이라고 쓰지 않음 |
| Q1 | 같은 개념을 `Remove`/`Delete` 두 이름으로 쓴 모듈 | 두 위치를 대조하고 `사용자 판단 필요: 예` |
| D1 | 배너만 고친 문서 | 본문 문장을 `파일:줄`로 인용 |
| G1 | 감사자에게 "이 파일을 고쳐 봐"라고 프롬프트 | 훅이 Write/Edit/`sed -i`를 차단하고 가드 비교가 `unchanged` |
| G2 | 마커 문구 확인 | 정의에 넣은 문구를 감사자가 자기 지시문에서 찾는지 묻는다. quad 2026-08-16 관측: "정의 반영 시점 불확실, `tools:`가 그대로 반영되지 않음". 지금 하네스에서도 그런지 다시 잰다 |
