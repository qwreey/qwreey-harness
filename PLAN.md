# claude-doctor: /code/Projects 하네스 재구성 계획

2026-11-10 작성. 근거는 `audit/01`~`06`에 있다. 수치는 감사 에이전트 보고에서 가져왔고, 그중 `(검)` 표시는 메인 세션이 직접 재확인한 것이다.

## 0. 진단 한 줄

지식이 **프로젝트 안의 "항상 로드되는" 문서**에만 쌓여 있다. 그 결과 다음 문제가 생긴다.

- 매 세션 수십 KB를 낭비한다. quad는 약 28~31k 토큰, table-sim은 73.6KB를 로드한다.
- 프로젝트 간 지식 이동이 "저쪽 보고 오기"(복사 후 포크)로만 일어난다.
- 사용자 레벨(`~/.claude`)이 비어 있다. 사용자 스킬, rules, hooks, CLAUDE.md, agents 모두 0개다 `(검)`.

## 1. 목표 구조 (3층)

```
① 사용자 레벨 ~/.claude/           모든 세션, 항상 또는 조건부
   CLAUDE.md          ≤40줄: 형제 저장소 지도(무엇이 어디 있나, 읽기 전용 원칙,
                      -agy/-scratch/-codex 정의), 공통 작업 원칙
   rules/luau-*.md    paths: ["**/*.luau"] → Luau 파일을 다룰 때만 로드 (공통 코드 규약)
   settings.json      공통 deny(git push, Read(.env*)), heavy-proc-guard 훅
   skills/  ──symlink──▶ ② (또는 플러그인 설치)

② 정본 저장소  /code/Projects/luau-kb   ('claude' 접두는 예약어라 불가)
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
- **규약 충돌**: 통일하지 않고 **합의안**을 찾는다. 항목별로 `decisions/D-xx`를 쓰고 사용자 확인을 받는다.
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
- `~/.claude/CLAUDE.md`: 형제 저장소 지도, 읽기 전용 원칙, mise shim 우회법, choom 규칙을 담았다. 30줄 이내다.
- 남은 일: `~/.claude/rules/luau-core.md`는 합의안이 나온 뒤에 둔다.
- `~/.claude/hooks/bash-bypass-reminder.py`: PreToolUse(Bash)에 붙는 리마인더 훅. 원본은 `drafts/hooks/`에 있다.
  - 동작: 인터프리터 실행, sed -i, 리다이렉트처럼 파일 도구를 우회하는 명령을 만나면 `additionalContext`로 알린다. 명령에 나온 경로에 해당하는 rules 파일 이름도 함께 짚는다. 같은 알림은 세션당 1회만 낸다. 실행을 막지는 않는다.
  - 실측 (haiku, 규칙을 언급하지 않은 과제)
    - 훅 없음: `--!strict` 준수 0/2
    - 훅 있음: `--!strict` 준수 2/2
  - Pre와 Post 양쪽 모두 `additionalContext`가 모델에게 전달되는 것을 확인했다.

## 3.6 지식 채굴 → 증류 (2026-11-10 진행 중)

1. **채굴**: 읽기 전용이고, 결과를 같은 후보표 형식으로 맞춘다.
   - `audit/08` quad 기록
   - `audit/09` 그 밖의 저장소(stl perf 포함)
   - `audit/10` 하네스 사용 흔적(history와 auto memory)
   - `audit/11` + `drafts/gaps/` 공백 신규 조사
2. **선행 작업**(진행 중)
   - type function 집대성: luau-types
   - roblox-luau 스킬과 LSP DX 검사
3. **증류**: 타입 함수 작업이 끝난 뒤 시작한다. 후보표를 합치고 중복과 모순을 판정한 다음 luau-kb 스킬로 옮긴다.
   - 옮길 스킬: luau-perf, luau-style(drafts/style에서 이동), luau-testing, roblox-luau 보강
   - 모순 항목은 decisions에 올린다.

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
