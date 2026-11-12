# claude-doctor: /code/Projects 하네스 재구성 계획

2026-11-10 작성. 근거는 `.claude/audit/01`~`06`에 있다. 수치는 감사 에이전트 보고에서 가져왔고, 그중 `(검)` 표시는 메인 세션이 직접 재확인한 것이다.

## 0. 진단 한 줄

지식이 **프로젝트 안의 "항상 로드되는" 문서**에만 쌓여 있다. 그 결과 다음 문제가 생긴다.

- 매 세션 수십 KB를 낭비한다. quad는 약 28~31k 토큰, table-sim은 73.6KB를 로드한다.
- 프로젝트 간 지식 이동이 "저쪽 보고 오기"(복사 후 포크)로만 일어난다.
- 사용자 레벨(`~/.claude`)이 비어 있었다(2026-11-10 시점: 사용자 스킬, rules, hooks, CLAUDE.md, agents 모두 0개 `(검)`). 지금은 `home/.claude/` 정본을 apply 해 CLAUDE.md·rules·hooks·settings·플러그인(q, qwreey-advisor, qwreey-conventions)이 있다. 현황은 `tools/home-sync.sh status`.

## 1. 목표 구조 (3층)

```
① 사용자 레벨 ~/.claude/           모든 세션, 항상 또는 조건부
   CLAUDE.md          ≤40줄 목표(실제는 약 50줄, 약 3.4k 토큰. 상시 로드 예산은 .claude/audit/29 판결): 형제 저장소 지도(무엇이 어디 있나, 읽기 전용 원칙,
                      -agy/-scratch/-codex 정의), 공통 작업 원칙
   rules/luau-*.md    paths: ["**/*.luau"] → Luau 파일을 다룰 때만 로드 (공통 코드 규약)
   settings.json      공통 deny(git push, Read(.env*)), heavy-proc-guard 훅
   skills/  ──symlink──▶ ② (또는 플러그인 설치)

② 정본 저장소  packs/luau-kb (claude-doctor 안의 도메인 팩; 이전에는 별도 저장소 /code/Projects/luau-kb)
   .claude-plugin/{plugin.json, marketplace.json}
   skills/
     luau-types/       SKILL.md(≤100줄: 결정 트리 + 증상→파일 라우팅)
                       references/{generics,variance,unions-singletons,
                       type-functions,recursion-and-limits,solver-limits}.md
                       (각 파일 맨 위 목차 + "답하는 질문", 절마다 status/last-confirmed)
     luau-verify/      음성 대조군, luau-analyze 직접 호출법, mise shim 함정
     luau-perf/        stl perf-measurements 증류
     roblox-luau/      Instance/Enum/서비스, Studio MCP 내장 스킬, rojo_sync_guide,
                       Roblox llms.txt 라우팅
     luau-testing/     러너 정책 (결정 필요, §4)
     new-luau-project/ [user] 스캐폴딩 정본(mise pin, .luaurc, stylua, .gitignore,
                       CLAUDE.md 뼈대, settings)
     delegate-agy/     [user] 4벌 통합, ROOT/BASE/UID 인자화, uid 중앙 표
     luau-solver-bug-triage / luau-recheck / luau-distill   [user]
     handover / audit-loop / review-round   [user] quad conventions에서 추출한 일반 절차
   snippets/          실행 가능한 정본. check_snippets.py
                      (-- expect-error / -- bug-present / --@run)
                      → 스킬 references의 모든 주장은 스니펫 ID로 연결, CI에서 검증
   typedefs/globalTypes.d.luau   8곳 복제본의 단일 원천 (검)
   hooks/heavy-proc-guard.py     .lsp.json(luau-lsp)
   AGENTS.md          Gemini/Codex용 진입점 (같은 references를 평문으로 가리킴)
   (나중) docs/        Starlight preset + snippet 검증을 quad/devplorer/stl 문서가 공유

③ 프로젝트 레벨 (각 저장소)
   CLAUDE.md          ≤80줄: 정체성, 넘지 않는 선, 빌드/검사 명령, 지금 상태 1줄
   .claude/rules/*.md paths 조건부 (예: docs/** 표기 규약, src/Collections/** 트레이트 규칙)
   .claude/skills/    프로젝트 고유 절차 (/release, /docs-audit, quad-ui-dev)
   .claude/{base,research,archive}/   그대로 두되 import 하지 않음
   todos              SessionStart 훅으로 '열린 항목'만 주입하거나 on-demand
```

## 2. 단계

| 단계 | 내용 | 위험 | 되돌리기 |
|---|---|---|---|
| **P0 위생** | ① quad·devplorer `.claude/worktrees` 정리 (14G + 445M) (검)<br>② quad-changelog-check의 미커밋 CHANGELOG만 살리고 보관(754커밋 뒤처진 클론) (검)<br>③ worktrees `.gitignore` 누락 5곳 보강<br>④ agy UID 충돌 해소 (quad와 tbox 모두 61000) (검)<br>⑤ stl-luau GEMINI.md를 BI 전환에 맞게 수정 (검)<br>⑥ moonwave `.claude` 커밋 여부 결정 (검) | 삭제가 포함됨 | 아카이브 tar 후 삭제 |
| **P1 사용자 레벨** | `~/.claude/{CLAUDE.md, settings.json 훅/deny, rules/luau-*.md}` | 낮음 | 파일 삭제 |
| **P2 luau-kb 골격** | 저장소 생성, plugin.json, snippets 하네스(초안 이식), typedefs, luau-types·luau-verify 증류 (quad 1387줄과 stl 481줄 typing-limits가 원천. quad-changelog-check는 근거에서 제외) | 낮음 (새 저장소) | - |
| **P3 프로젝트 다이어트** | 프로젝트 하나씩: conventions를 상시(≤80줄) / rules(paths) / 스킬 / archive로 분해. 시범 대상은 **stl-luau** (작고, 지금 BI 전환 중이라 정리 이득이 큼). 이후 table-sim → quad 순 | 다른 세션과 충돌 가능 (quad) | git으로 되돌림 |
| **P4 스캐폴딩·위임 통합** | /new-luau-project, delegate-agy 통합. 각 프로젝트의 사본 제거 | 중 | - |
| **P5 문서 정본** | Starlight preset과 doc-snippets 일반화, Roblox defs 일원화, 스킬과 사이트의 단일 원천화 | 큼 | 나중에 판단 |

검증 루프 (각 단계 끝):
- `/context all`로 상시 토큰 측정 (전후 비교)
- `/doctor prompt-audit`
- `claude plugin validate`
- `/skill-doctor`로 스킬 트리거 여부 확인
- 스킬마다 평가 시나리오 3개 (예: "제네릭 콜백 상한이 안 잡혀요" → luau-types 발동 → 올바른 references로 이동)

## 3. 이미 있는데 안 쓰던 것 (즉시)

- Roblox Studio MCP 내장 스킬 13개 (rbx-debug, rbx-unit-test, rbx-docs-search, rbx-perf-profiling …)와 `rojo_sync_guide` 규칙
- create.roblox.com/docs/llms.txt
- 공식 마켓플레이스: claude-md-management, session-report (1회 실행), plugin-dev, hookify
- 진단 명령: `/doctor prompt-audit`, `/skill-doctor`, `/context all`
- 서브에이전트 기능: `memory: project`, `skills:` 프리로드 → rbvm 감사 에이전트에 적용

## 3.5 2026-11-10 사용자 결정과 실측 사항

- **공유 방식**: luau-kb는 플러그인 구조로 만든다. 소비는 당장 `~/.claude/skills` 심볼릭 링크로 한다.
- **규약 충돌**: 통일하지 않고 **합의안**을 찾는다. 항목별로 `.claude/base/decisions/D-xx`를 쓰고 사용자 확인을 받는다.
- **규칙의 3단 분담**
  - 네이밍, 품질, 관용 규칙은 스킬로 옮기되, 짧은 필수 규칙은 `rules`에 `paths: ["**/*.luau"]`를 붙여 둔다.
  - rules 자동 로드 실측 결과
    - 로드됨: Read, Write(신규 파일), Bash `cat`, 서브에이전트의 Read
    - 로드 안 됨: grep, 비-luau 파일
  - 감사 에이전트는 `skills:`로 스킬을 프리로드한다.
- **감사 에이전트**: 관점별로 분할한다(타입, 런타임, 품질, 성능, 문서). 오케스트레이션은 `/audit` 스킬로 한다.
- **agy/codex 위임**: 통합 스킬 하나로 합치고, uid는 중앙 표에서 관리한다.

### P0 실행 결과
- **quad**: 다른 세션이 실행 중이다. 14GB worktree는 lock이 걸린 채 쓰이는 중이라 **손대지 않았다**. 감사 보고서의 판단이 틀렸다.
- **정리한 것**: devplorer 22개, table-sim 2개, VideoSync 1개 worktree를 `git worktree remove`로 지웠다. 브랜치는 보존된다. quad-changelog-check 디렉터리도 지웠다.
  - 백업 위치: `/code/backups/claude-doctor-2026-11-10/`
  - 백업 내용: tgz, worktree별 status/diff/branch, CHANGELOG diff
- **보류한 것**: 실행 중인 세션이 있는 저장소의 `.gitignore` 보강과 tbox UID 수정(→ P4 위임 통합 때 처리), moonwave 커밋 여부(사용자 판단 필요).

### ~/.claude 정본 관리 (사용자 요청)
- 정본 위치는 `home/.claude/`이고, 관리 대상은 `home/MANIFEST`에 적는다.
- 동기화는 `tools/home-sync.sh status|diff|pull|apply`로 한다.
  - `apply`: 사용자가 검토한 뒤 직접 실행한다. 덮어쓸 파일은 `.bak-<시각>`로 먼저 백업한다.
  - `pull`: `/config` 등으로 실제 쪽만 바뀐 내용을 정본으로 가져온다.
- 이후 사용자 레벨 rules와 스킬 링크도 여기서 관리한다. 심볼릭 링크를 지원하도록 스크립트 확장이 필요하다.

### P1 실행 결과
- `~/.claude/settings.json`에 PreToolUse 훅 `~/.claude/hooks/heavy-proc-guard.py`를 추가했다. 훅이 발동하는 것도 확인했다.
  - 같은 때 deny 규칙(`git push`, `.env` 읽기)도 넣었으나 **철회 대상**이다. 이 환경은 sandbox이고 git 계정이 에이전트 전용이라, 에이전트의 push가 정상 흐름이다.
  - 제거는 auto 모드 분류기가 막아서 사용자가 직접 해야 한다.
  - rbvm과 table-sim의 프로젝트 settings에도 `git push` deny가 있다. 정리할지는 사용자가 판단한다.
- `~/.claude/CLAUDE.md`: 형제 저장소 지도, 읽기 전용 원칙, mise shim 우회법, choom 규칙을 담았다. 처음에는 30줄 이내였으나 지금은 약 50줄(약 3.4k 토큰)이다.
- 남은 일: `~/.claude/rules/luau-core.md`는 합의안이 나온 뒤에 둔다. (그 밖의 사용자 레벨 rules 5개 comments·agent-docs·code-structure·memory·web-security 는 `plugins/qwreey-conventions/rules/` 로 옮겨 훅 `rules_inject.py` 가 주입한다.)
- `~/.claude/hooks/bash-bypass-reminder.py`: PreToolUse(Bash)에 붙는 리마인더 훅. 정본은 지금 `plugins/qwreey-conventions/hooks/` 이다(user-level 훅은 모두 플러그인으로 옮겼다. `.claude/research/drafts/hooks/` 는 옛 초안이라 갱신하지 않는다).
  - 동작: 인터프리터 실행, sed -i, 리다이렉트처럼 파일 도구를 우회하는 명령을 만나면 `additionalContext`로 알린다. 명령에 나온 경로에 해당하는 rules 파일 이름도 함께 짚는다. 같은 알림은 세션당 1회만 낸다. 실행을 막지는 않는다.
  - 실측 (haiku, 규칙을 언급하지 않은 과제)
    - 훅 없음: `--!strict` 준수 0/2
    - 훅 있음: `--!strict` 준수 2/2
  - Pre와 Post 양쪽 모두 `additionalContext`가 모델에게 전달되는 것을 확인했다.

## 3.6 지식 채굴 → 증류 (2026-11-10 진행 중)

1. **채굴**: 읽기 전용이고, 결과를 같은 후보표 형식으로 맞춘다.
   - `.claude/audit/08` quad 기록
   - `.claude/audit/09` 그 밖의 저장소(stl perf 포함)
   - `.claude/audit/10` 하네스 사용 흔적(history와 auto memory)
   - `.claude/audit/11` + `.claude/archive/research/drafts/gaps/` 공백 신규 조사
2. **선행 작업**(진행 중)
   - type function 집대성: luau-types
   - roblox-luau 스킬과 LSP DX 검사
3. **증류**: 타입 함수 작업이 끝난 뒤 시작한다. 후보표를 합치고 중복과 모순을 판정한 다음 luau-kb 스킬로 옮긴다.
   - 옮길 스킬: luau-perf, luau-style(.claude/archive/research/drafts/style에서 이동), luau-testing, roblox-luau 보강
   - 모순 항목은 decisions에 올린다.

## 3.7 coderag 확장 (2026-11-10 승인, 설계 a1b309f 의 결정 49개 추천안 전부 확정, 구현 M1~ 진행)

1. **설계안 작성**: `coderag/tech-design.md` 에 아래 다섯 가지를 설계안으로 쓴다. 사용자가 검토한 뒤 확정한다.
   - **지식 계층 3단**: global / pack(luau-kb 등) / project. 우선순위는 project > pack > global 이고, 결과마다 계층을 표시한다.
   - **소스 선언**: path·glob / git / 패키지(lockfile 로 설치 경로를 해석) / pack. 모듈 해석은 코어가 맡는다.
   - **분류 체계**: 계층형 `category`(통제 어휘 `taxonomy.toml`) + 자유 `tags`, 검색 필터.
   - **버전·미래 필드**: `lifecycle`(rfc → implemented-cli → released-roblox → deprecated), `applies_to`(luau>=x), `review_after`, `--luau <ver>` 필터.
   - **원천 하나, 접근 둘**: luau-kb references 에 frontmatter 를 단다. 스킬(Claude)과 coderag CLI(다른 에이전트, 정밀 조회)가 같은 파일을 쓴다.
2. **확정 후**: luau-kb 증류·upstream 결과에 맞춰 `taxonomy.toml` 을 만든다.
3. **frontmatter 채우기**: luau-kb references 에 frontmatter 를 backfill 한다.

## 3.8 설계 원칙 (사용자 결정, 2026-11-10~11)

메모리에만 있던 원칙을 옮긴 것이다(.claude/audit/23, 메모리는 저장소와 동료에게 따라가지 않는다). 지금 사실로 고쳐 썼다.

- **규약 충돌은 한쪽으로 통일하지 않는다.** 대상은 const, stylua, 러너, 타입 함수, luau 버전 등이다. 항목마다 근거를 붙인 합의안을 `.claude/base/decisions/D-xx` 로 만들고 사용자 확인을 받는다. 정책이 갈리면 선택지와 근거를 제시한다.
- **짧은 필수 규칙은 rules, 상세는 스킬에 둔다.** rules 는 `paths:` 로 범위를 정한다. 파일을 Read/Write 할 때 로드되고, grep 으로는 로드되지 않는다. 사용자 레벨 rules 로드는 apply 뒤 실측으로 확인했다(2026-11-11). 감사 에이전트는 관점별로 나누고 스킬을 프리로드한다.
- **툴킷 무관.** 하네스는 Roblox/Luau 전용이 아니다. 공통 코어에 툴킷별 자리(luau, web …)를 두고, 툴킷은 감지 표식(mise.toml, package.json …)으로 고른다. 경로는 harness.env 변수로 빼서 다른 sandbox 로 옮길 수 있게 한다. 근거: `.claude` 를 제어하지 못해 실패한 예전 경험.
- **공유와 배포는 플러그인으로 한다.**
  - luau-kb 는 툴킷 pack 플러그인으로, Luau 저장소에서만 켠다.
  - 사람이 치는 명령은 짧은 이름공간 `q` 에 모은다(`/q:start`·`doctor`·`away`·`back`·`checkpoint`·`import`).
  - 모델이 부르는 qwreey-advisor 는 별도 플러그인이다.
  - rules 와 CLAUDE.md 파일은 플러그인에 담을 수 없으므로 home-sync 로 반영한다(개인 정책·환경 지도). 이식 가능한 상시 규약은 플러그인 SessionStart·SubagentStart 훅의 additionalContext 로 실을 수 있다(.claude/audit/32): q 의 훅 메시지·workspace 규약, qwreey-advisor 의 자기 점검 한 줄. 경로 조건부 로드(paths)는 대체재가 없다. settings 는 마이그레이션으로 반영한다.
- **비용은 막지 않고 알리고 줄 세운다.** 근거(사용자): "강제라면 위임해 두고 갔는데 멈춰 버려 오히려 손해", "전체 예산을 한계치로 두고 하나가 끝나면 다음을 돌리는 게 실제로 좋더라", "작은 패스를 여러 번 하는 게 토큰이 덜 든다".
  - 사용자가 있을 때는 팬아웃 전에 고지한다(말은 2개부터, 훅 warn 은 4개부터).
  - away 상태에서는 예산 상한과 슬롯으로 직렬화한다. 2배를 넘으면 기록하고 기다린다.
  - 예산 단위는 요금제에 맞춘다(USD 또는 한도 %).
  - 구현: CLAUDE.md "모델 사용과 서브에이전트 비용", `plugins/q/scripts/subagent-slots.py`, .claude/audit/21.
- **second opinion:** 내장 advisor 도구는 사용자가 요청할 때만 쓴다. 근거(사용자): 가격 대비 효용이 diff 기반 리뷰보다 너무 낮다. 흐름 검토는 `qwreey-advisor:inherit-advisor`(fork + 표지를 훅이 후행 프롬프트로 펼침), diff 검토는 `qwreey-advisor:fresh-advisor` 로 한다. 근거 실험은 .claude/audit/18 §9·§11·§12.
- **사용자 가시성도 개선 대상이다.** statusline, 테마, 응답 형식이 해당한다. 주관적이므로 설치는 묻고, 켜고 끌 수 있게 둔다(.claude/audit/22).

## 3.9 저장소 구조와 에이전트 기록 체계 (큰 틀 합의 2026-11-12, 세부는 토론 뒤 확정)

근거 조사: .claude/audit/36(형제 저장소 `.claude/` 공통 패턴, 옮길 때 깨지는 곳). 사용자: "큰 틀 동의하고 토론 해보는것도 동의".

- **이 저장소의 성격.** 사용자의 Claude 관련 지식과 플러그인을 모으는 저장소다("claude conf 같은 느낌…결국 내 오피니언임"). 나중에 공개할 수 있다.
- **층을 나눈다.**
  - 실제 소스: `home/`, `plugins/`, `tools/`, `.claude-plugin/`. `plugins/` 와 `.claude-plugin/` 은 settings 의 마켓 경로가 가리키므로 옮기지 않는다.
  - 도메인 팩: `packs/<이름>/` (luau-kb, web-security). 관용 규약(qwreey-conventions)과 분리한다. 사용자: "luau-kb 는 관용 표현이 아님".
  - 에이전트 기록: `.claude/` 아래 `plan/`, `base/`, `audit/`, `research/`, `archive/`, `handoff/`, `sessions/`, `packs/<팩>/`(팩의 개발 자료: bench, evals, decisions). 이유와 근거를 날것으로, 필요한 만큼 담는다. 소스와 관련은 있지만 소스가 아니다.
  - 사람 문서: 공개할 때 `docs/` 를 따로 쓴다.
- **도메인 팩은 기본 꺼짐 (동의).** `defaultEnabled: false` 로 두고, 쓰는 프로젝트가 `.claude/settings.json` 의 `enabledPlugins` 로 켠다. `q:start` 가 감지 표식(`.luaurc`, `package.json` …)으로 켤 팩을 제안한다. `HARNESS_TOOLKITS` 는 기계 단위로 훅을 끄는 스위치로만 남는다(스킬 설명 비용은 못 줄인다). 선행 실측: 스킬 `paths` 가 설명 목록에서도 빠지게 하는지, `defaultEnabled` 동작.
- **기록 체계는 coderag 와 결합한다 (사용자 제안, 조사 중).** 사용자: "claude 기록의 경우는 coderag 와 같이 결합되는게 맞지 않을까…markdown 관련도 넣고 있으니까. 특히 검색 관련해서나 stale 관련해서나 이미 만들어진 틀이 있으니까. 또 하이쿠 모델을 통해서 찾도록 하는것도 coderag 와 연계 가능". 다루는 것:
  - 문서마다 status 한 줄(active / landed in X / superseded by Y / rejected)과 폴더별 README 색인.
  - 검사: 깨진 링크, 색인 누락, 끝난 문서가 archive 밖에 있는 경우, 상시 로드 크기.
  - 오래된 기록을 읽을 때 stale 경고(지금은 `records_read.py`).
  - `q:recall` 의 haiku 위치 찾기를 coderag 검색으로 바꾸기.
  - coderag 가 없을 때도 기록은 평범한 markdown 으로 읽혀야 한다.
- **claude-doctor `.claude/` 재편은 coderag 로 구조화하는 실험으로 한다.** 사용자: "git이 있어서 실패하더라도 잃는건 없을거니까".
- **순서.**
  1. coderag 적합성 조사(.claude/audit/37)와 heavy-proc-guard 오탐 수정.
  2. 실측: 스킬 `paths`, `defaultEnabled`.
  3. 기록 규약 토론(opus 2개, 2라운드). 문구와 자동화 수준, coderag 결합 방식을 정한다.
  4. 재편 실험: 끝남, main 에 합침(사용자: "합치자"). 기록은 `.claude/` 아래(`.claude/README.md`), PLAN.md 는 사용자 결정으로 루트("나도 많이 참조하는 파일"). 시점 기록 안의 옛 경로도 스크립트로 바꿨다(사용자: "작은 모델로 기계적으로 링크를 고치는게 나을지도"). 결과는 `.claude/audit/39-records-experiment/after-D.md`(coderag 10/12, grep 7/12). 남은 것: coderag static-gen 이 하위 폴더로 내려가지 않음, luau-kb 의 옛 경로 12개 파일(가져올 때 고침), 커밋 때 records_check 알림.
  5. `packs/`: web-security 는 옮김(기본 꺼짐, 마이그레이션 0008, q:doctor PACK- 검사; 사용자: "가로 하는게 맞는것 같음…doctor 가 점검하는 부분에 같이 있으면 편하겠다"). luau-kb 는 이력째 가져옴(git subtree, packs/luau-kb 0.5.0, 기본 꺼짐; 개발 자료 evals 는 `.claude/packs/luau-kb/`). 웹·Luau 저장소별 켜기가 남았다.
  5a. 지식 팩의 그릇 재검토(사용자: "luau-kb 는 stale 해질 수도 있고, 필요에 따라 검색해야할 수도 있고…web security 도 그런데, 시행착오로 새로운게 나올 수도 있고, 그래서 싱크 되거나 해야할 수도"). PLAN 3.7 의 "원천 하나, 접근 둘" 중 coderag 접근이 빠져 있었다.
     - 1단계 끝: `~/.coderag/coderag.toml` 에 `[[packs]] luau-kb` 를 저장소 사본 경로(`packs/luau-kb`)로 등록. pack 계층 검색과 stale 이 동작한다. 이 설정의 정본을 home/ 에 둘지는 home-sync 가 `~/.claude` 밖을 다루지 않아 2단계 결정 뒤에 정한다.
     - 2단계 토론(.claude/audit/41): 지식 본문은 coderag pack, 플러그인은 입구만. 사용자 추가 쟁점: "cli 를 직접 호출하지 않아도 되는 방향…mcp로써 작용한다던가. 특히 데몬셋이 된다면 fs watch…블룸 필터나 시멘틱 서치", "coderag 자체에 rules 나 추가적 컨텍스트를 통해 유사한 진입점을 제공하는게 나을수도…compact 훅이나 rules inject 구조들이 복제되고…claude 로 제한되는 락인", "얇은 입구는 packs 마다 전부 복제된다는게 조금 걸려".
  6. 자동화: 규약 스킬, doctor 검사, 커밋할 때 info 알림, `q:start` 의 `.claude/` 뼈대 템플릿.
- **기록 규약 토론 결과(.claude/audit/38 synthesis)에 대한 사용자 답.** "추천대로 할게", "저장소 변경은 승인".
  - coderag 저장소 변경을 승인했다. coderag 에는 따로 세션이 없으므로 이 세션이 서브에이전트로 맡는다. 1단계는 C1, C2, C6 이다.
  - coderag 를 쓰는 형태: 먼저 바이너리 경로(harness.env `HARNESS_CODERAG`)로 시작하고, 실험을 본 뒤 사용자 설치에서 플러그인을 켠다. 최종적으로는 빌드된 바이너리를 배포한다. 사용자: "github release 로 실어서 넣고, 내가 gpg 사이닝을 더할게.(sandbox 바깥에서)". claude-doctor 에는 받기·서명 확인·없으면 소스 빌드를 하는 스크립트를 둔다.
  - 소급: 새 저장소와 claude-doctor 에만 적용한다. 형제 저장소의 옛 형태는 검사기가 인정만 한다.
  - raw 측정 출력은 gitignore 한다. 요약에 수치와 재생성 명령을 남긴다.
- **아직 사용자에게 물을 것.** luau-kb 설치 범위(저장소별 켜기), 형제 저장소 지도의 포인터 방식. (`rules/code-structure.md` 9행은 가져온 뒤 고쳤다.)

## 4. 사용자가 결정할 것

1. 공유 방식: `~/.claude/skills` 심볼릭 링크 vs 플러그인 설치 (버전 bump 필요)
2. 규약 충돌 정리
   - const: rbvm은 금지, 나머지는 기본
   - stylua: Tabs/Spaces, call_parentheses Always/Input
   - 러너: luau / lune / lute
   - 타입 함수: "쓰지 않음" vs "진단 전용"
   - 툴체인 pin: luau 0.734 vs 0.742
3. 다른 프로젝트 수정 범위 (quad는 다른 세션이 활발히 수정 중)
4. 미검증 서술의 처리 (예: tbox stylua `f<<T>>` 오염 경고는 재현 실패)
5. 영어 지시가 늘면 모델이 사용자 언어를 잊고 영어로 답하는 문제(.claude/audit/31 남은 과제). 후보: 상시 본문 끝에 사용자 언어를 다시 적기, 응답 언어를 확인하는 훅. 정할 때 실측으로 판단한다.
6. home-canon-guard 훅(정본 대신 `~/.claude` 를 직접 고치는 것 차단)과 worktree-guard 훅(lock·살아 있는 세션 확인 없는 worktree 삭제 차단). 생기면 사용자 CLAUDE.md 의 해당 상시 줄을 뺀다(.claude/audit/31).
