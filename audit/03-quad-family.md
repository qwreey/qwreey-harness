# 03. quad 계열 에이전트 문서 감사 (quad / quad-changelog-check / quad-v1 / scratch·agy·codex)

감사일 2026-11-10, 읽기 전용. 줄 번호는 `/code/Projects/quad` 기준(아니면 명시). 토큰은 한국어 혼합 텍스트 기준 추정치(오차 ±25%).

## 0. 프로젝트 정체

| 디렉터리 | 정체 | 근거 |
|---|---|---|
| `quad` | 본체. Roblox DOMless UI 렌더러 v2(3.x~4.0.0 게시됨). `.claude/`가 5364파일(worktrees 제외)/약 55MB, 사용자 문서 `docs/`는 별도로 거대 | `du`, `todos.md:11` |
| `quad-changelog-check` | **quad 의 낡은 클론**(같은 origin `git.qwreey.moe/qwreey-bot/quad`, HEAD=`f00084a` 2026-09-10 23:30 = quad HEAD 의 조상, 754커밋 뒤처짐). 작업은 CHANGELOG.md 하나만 수정(미커밋 +191/-49, 3.0.0 항목 재작성). `prompt-ignoreme/prompt-ignoreme.md` 는 "v1(2.x) 수기 변경이력 복원문서 검수" 프롬프트 | `git log`, `git diff --stat` |
| `quad-v1` | 구 v1 레포(Lua, mkdocs, 2026-08-10 마지막 커밋). **`.claude/`·CLAUDE.md 없음** — 감사할 에이전트 문서 0. v1 지식은 quad 쪽 `.claude/reference/quad-v1-architecture.md` 로 이미 이식됨 | `ls -a` |
| `quad-scratch` | 일회용 Luau 프로브 모음(`luau-order-probe/`, `lt*.luau`, `gt/`, `rt/`) + quad 레포 사본(`quad-scratch/quad`, 158MB). 컨벤션 문서 없음 | `ls` |
| `quad-agy` | `delegate-agy` 스킬이 `git worktree` 로 만든 Gemini 위임 작업장(`<name>/` = 레포 체크아웃, `.home`=agy OAuth 홈, `.hooks`=push 거부 훅). 199MB | `quad/.claude/tools/agy-delegate.sh:1-25` |
| `quad-codex` | 같은 목적의 Codex 위임 결과물 보관(`naming-*/{prompt,answer,stdout}`, `run-marker-helper`). 레포 사본 아님, git 아님. 31MB. 이 디렉터리를 만드는 도구는 `quad/.claude/tools` 에 없음(agy 전용 스크립트만 있음) — 수동 절차 추정 | `ls` |

결론: **감사 대상 실체는 quad 하나**. changelog-check 는 삭제/아카이브 후보, v1 은 문서 없음, scratch/agy/codex 는 "산출물 폴더"라 `.gitignore`/정리 정책만 필요.

## 1. 상시 로드 비용 (CLAUDE.md -> @import 체인)

| 파일 | 줄 | 바이트 | 글자 | 추정 토큰 |
|---|---:|---:|---:|---:|
| `CLAUDE.md` | 54 | 4,449 | 2,685 | ~1.8k |
| `.claude/conventions.md` (`CLAUDE.md:34`) | 531 | 63,380 | 34,504 | ~21k |
| `.claude/project-context.md` (`CLAUDE.md:36`) | 111 | 10,035 | 6,008 | ~4k |
| `.claude/todos.md` (`CLAUDE.md:38`) | 92 | 10,494 | 6,257 | ~4k |
| **합계** | **788** | **88,358** | **49,454** | **약 28~31k 토큰, 매 세션 선로드** |

비교: 공식 권장 200줄/파일의 conventions 2.6배, 합계 3.9배. CLAUDE.md 자신이 `:22-27` 주석(렌더 전 제거됨)에서 "1537줄 → 지침 준수도 저하"를 이유로 쪼갰다고 적어놓고, `@import` 는 컨텍스트를 줄이지 않는다는 것도 인정함. 즉 **쪼갰지만 줄이지는 않았다**. `session-summary.md`(2562줄/237KB)·`README.md`(78줄) 는 의도적으로 import 안 함(`CLAUDE.md:48-51`) — 이 판단은 옳음.

### 1-1. 상시 로드 3파일 + CLAUDE.md 분류

| 범주 | 내용 | 대략 규모 |
|---|---|---|
| 항상 필요 | 한국어 사용·토큰 절약 원칙(`conventions.md:10-18`), 설계 원칙 둘(`:50-79`), SAFETY 요약(`:512-517`), 커밋 전 `doc-check` + test.sh exit code 규칙(`:229-230`,`:348-355`), 온디맨드 자료 표(`CLAUDE.md:42-60`), 충돌 시 우선순위(`CLAUDE.md:62-64`) | 약 90줄 |
| 조건부 | 문서 표기 규약 전체(`:80-192`, 113줄 = docs/.claude 편집할 때만), 감사 루프·code-review 규약(`:268-338`,`:389-485`, 약 170줄 = 핸드오버/리뷰 때만), 메모리 큰 실행 규약(`:381-388`), 서브에이전트 종료 판정(`:362-379`), 소스 주석·QuadNNNN·CHANGELOG 규약(`:344-347`), Studio MCP(`:494-497`) | 약 400줄 |
| 이미 끝난 기록 | 모델 전환 서사 fable→opus(`:19-46`, 28줄), 2026-08-26/09-01/09-07 "사실 정정" 서사와 취소선(`:393-460`), 폐기된 Workflow 경위(`:283-289`), M2 자율 구현 규약(`:519-531`, 마일스톤 종결 뒤인데 남음), `project-context.md` 의 M0~M11 경위·라운드 서술, `todos.md` 00번의 날짜별 경과, CLAUDE.md 머리 상태 문단(`:2-20`) | 약 150줄 |

즉 **상시 필요는 15~20%**, 나머지 80%는 조건부 또는 기록.

## 2. conventions.md 섹션별 태깅표

범례: (a) 상시 CLAUDE.md (b) `paths` 조건부 `.claude/rules/*.md` (c) 자동 호출 스킬 (d) 사용자 호출 슬래시 스킬/워크플로 (e) 프로젝트 공통 지식 → 사용자 레벨 스킬 (f) 아카이브/삭제

| 줄 | 섹션(요지) | 태그 | 이동처/메모 |
|---|---|---|---|
| 1-8 | 머리말("매 세션 로드되니 늘리지 마라") | (f) | 메타. 4줄이 CLAUDE.md 규약과 중복(`CLAUDE.md:30-33`) |
| 10-18 | 한국어/모델 선택 일반 | (a) | 10줄로 압축 |
| 19-46 | fable 임시 강하, opus 5.5 전환 서사 | (f) | 결론 2줄만 남기고 `session/2026-09-28-01-*` 로 포인터. 모델명이 시간 종속 |
| 50-58 | 설계 원칙1 "가상 요구 방어 금지" | (a) | 본문 3줄로, 사용자 인용·경위는 session 으로 |
| 59-79 | 설계 원칙2 "한 필드 두 일 금지" | (a) | 3줄 + `Observer`/`EffectHandle` 사례 1줄. 경위 이동 |
| 80-93 | doc-check 설계 철학 | (b) | `paths: [".claude/**/*.md", "docs/**"]` |
| 94-147 | 절 인용 규약 (54줄) | (b) | 같은 paths. 상당수는 doc-check.py 가 이미 강제하므로 **규칙은 5줄, 나머지는 도구 --help/주석으로** |
| 148-170 | 옛 `X.luau` 표기, 레포 밖 소스 포인터 | (b) | 같은 rules 파일 |
| 171-192 | 세션 ID 지칭, 날짜 라벨 보류 | (b)/(f) | 171-181 (b), 182-192 는 "보류" 결정이라 (f) |
| 195-210 | Agent 위임/병렬/연기 | (a) | 6줄로. 단, `:198` 병렬 권장과 `:290` 감사자 병렬 금지가 충돌(아래 6절) |
| 211-223 | session/ 원문 남기기 | (b) | `paths: [".claude/**"]`. "공백 인정" 경위는 삭제 |
| 224-249 | 중대 변경 핸드오버 체크리스트 | (d) | `/handover` 슬래시 스킬로(체크리스트 6단계 + doc-check + 감사자 호출) |
| 250-258 | "import 파일을 고쳐도 그 세션엔 반영 안 됨" | (f) | 하네스 일반 지식이라 프로젝트 문서에 둘 필요 없음. 필요하면 사용자 레벨 한 줄 |
| 259-267 | doc-check 사용법 | (b) | doc-check.py docstring 과 중복 |
| 268-338 | quad-doc-auditor 도입 + 감사 루프 6단계 | (d) | `/audit-loop` 스킬. 폐기된 Workflow 경위(`:283-289`) 삭제 |
| 339-343 | 원장 문항은 평문 한 문단 | (b) | `paths: [".claude/qa-request/**"]` |
| 344 | 공개 표면 변경 시 CHANGELOG 한 줄 | (b) | `paths: ["quad-*/src/**","CHANGELOG.md"]` |
| 345 | 게시 소스 주석에 H-nnn 금지, `Ref:` 꼬리 | (b) | `paths: ["**/*.luau"]` |
| 346 | `QuadNNNN` 에러 식별자 | (b) | `paths: ["quad-*/src/**"]` (+ `scripts/error-codes.py` 가 강제) |
| 347 | 문서 luau 블록 게이트 | (b) | `paths: ["docs/**"]`. 정본은 `scripts/doc-snippets.py` 머리 주석 |
| 348-355 | test.sh 판정은 exit code, 새 솔버 | (a) 2줄 + (b) | exit code 규칙은 상시, 솔버 세부는 `paths: ["**/*.luau"]` |
| 356-361 | luau-analyze/luau-lsp 함정 4종, pesde install, relink | (e)/(b) | Luau 새 솔버 일반 지식은 사용자 레벨 `luau-newsolver` 스킬, quad 전용(relink/pesde)은 rules |
| 362-379 | 백그라운드 에이전트 종료 판정 | (e) | 하네스 일반 지식 → 사용자 레벨 CLAUDE.md/스킬로 승격. 사건 서사 삭제 |
| 380 | delegate-agy 포인터 | (c) | 이미 스킬 있음. 1줄만 남기고 삭제 가능(스킬 description 이 호출 조건 담당) |
| 381-388 | 메모리 큰 실행(choom, 예산) | (c)+hook | `heavy-proc-guard.py` 훅이 이미 강제. 예산 산식은 스킬로, 서브에이전트용 복붙 블록(`:388`)은 스킬이 대체 |
| 389-485 | code-review 규약 + 비용 정정 서사 (97줄) | (d)/(f) | `/review-round` 스킬로 결론만("인자에 서브에이전트 model:opus + 검증자 상한", "새 메커니즘은 사용자 문항") 15줄. 취소선·정정 서사 삭제 |
| 486-493 | 주기 감사 권고 | (f) | 위 감사 스킬과 중복 |
| 494-497 | Studio MCP 주의 | (a) 1줄 or (b) | 앞 2줄이면 충분 |
| 498-511 | 사용자 발언 인용 시 논거 남기기 | (b) | session/ 편집 rules |
| 512-517 | SAFETY(외부 push 금지, 별도 계정) | (a) | 유일하게 "절대" 급. 유지 |
| 518 | 커밋 트레일러 | (a)/(f) | 하네스 일반이라 중요도 낮음, 1줄 |
| 519-531 | M2 자율 구현 규약 | (f) | M0~M11 종결(2026-09-07)인데 남아 있음. archive 로 |

효과 추정: (a) 약 80줄(~2.5k 토큰) + CLAUDE.md. 조건부는 rules/스킬로 이동 후 상시 28k → 약 6~8k 토큰(**-75% 내외**).

## 3. 자동화 자산 공유 가능성 (질문 2)

| 자산 | 내용 | 공유 가능성 | 비고 |
|---|---|---|---|
| `.claude/tools/doc-check.py` (534줄) | 깨진 파일/절 참조, README 색인 누락, 날짜 없는 시한부 주장, 미반영 배너 | **부분 공유**. 엔진은 일반적(링크·색인·절 인용 검증), 하드코딩은 `OURS` 명명 관례·`SKIP_DIRS`·"quad" 전용 어휘·`docs/` 구조 | 일반 코어 + 프로젝트별 설정 파일로 분리하면 claude-doctor 에 "문서 stale 감사" 도구로 편입 가능. 다른 프로젝트가 같은 규약(절 인용·README 색인)을 안 쓰면 가치가 반감 |
| `.claude/hooks/heavy-proc-guard.py` (82줄) | Bash 에 bench/fuzz/stress 면 `choom` 강제 PreToolUse 훅 | **즉시 공유 가능**. 프로젝트 의존 0, 컨테이너 공용 cgroup 이 사유(`:1-12`) | 사용자 레벨 `~/.claude/settings.json` 훅으로 승격. 같은 컨테이너에 다른 세션이 도는 한 모든 프로젝트가 혜택 |
| `settings.json` | 위 훅 1개뿐. `includeCoAuthoredBy:false` | 훅과 함께 사용자 레벨 | 프로젝트 쪽은 비워도 됨 |
| `settings.local.json` | skillOverrides, prefersReducedMotion — 개인 설정 | 사용자 레벨로 이동 대상(프로젝트에 둘 이유 없음) | |
| `tools/agy-delegate.sh` (130줄) + `skills/delegate-agy` (68줄) | 다른 모델(Gemini) worktree 격리 위임 | **공유 가능**: 격리 방식(uid 분리 setpriv, worktree, push 훅, HEAD 스냅샷 비교)은 quad 무관. 경로 `/code/Projects/quad-agy` 하드코딩만 파라미터화 | 사용자 레벨 스킬 `delegate-agy` 로 승격. quad-codex 는 같은 패턴의 수동판이라 스크립트화하면 통합 |
| `agents/quad-doc-auditor.md` (138줄) | 코퍼스 신선 맥락 감사자 | **패턴만 공유**: "변경 세션이 아닌 신선한 서브에이전트가 읽기 전용 감사"는 일반적. 프롬프트의 quad 어휘는 교체 필요 | 일반형 `doc-auditor` 에이전트 템플릿화 가능 |
| `agents/quad-site-tester.md` (112줄) | 헤드리스 Chrome 으로 Starlight 사이트 실측 | quad 전용(URL, Astro). 패턴은 일반 | 그대로 둠 |
| `agent-memory/quad-doc-auditor/` | 감사자 자기 메모리 5개(`feedback_self_referential_counts` 등) | quad 전용. 단 "자기참조 개수 금지" 류 교훈은 일반 | 일반 교훈만 사용자 레벨로 |
| `scripts/doc-snippets.py` | 문서 ` ```luau ` 블록을 펜스 표시(continue/skip/no-run/error=)로 타입체크+mock 실행 | 아래 4절 | |

## 4. luau-test (질문 3)

| 항목 | 관찰 |
|---|---|
| 규모 | 폴더 4(`done` 32, `rewrite-required` 2, `not-run` 1, `review-required` 0) + README 326줄 + STATUS 317줄 = **상태 문서가 코드(35 스파이크)보다 훨씬 큼** |
| 체계 | "폴더가 곧 상태" + `git mv` + STATUS 한 줄 갱신(`luau-test/README.md:6-18`). 각 스파이크 머리 주석이 `검증 대상/배경/실행/기대 결과`(예: `done/01-two-pass-array-hash-order.luau:1-14`) |
| 문제 1 | `done/` 은 "통과"가 아니라 "더 할 일 없음" — 폐기된 것(11, 19, 22)도 done. 상태 신호로 부정확 |
| 문제 2 | **CI(test.sh)에 연결 안 됨**: `scripts/test.sh` 에 `luau-test` 참조 0. 즉 일회성 스파이크이지 회귀 정본이 아님. 실제 회귀는 `quad-base/test/spec.*.luau` 가 대체했고(STATUS 가 "spec.X 가 대체"를 반복 기록) 스파이크는 그 전신 |
| 문제 3 | README 가 이미 없는 `review-required/` 를 표에 넣고 "현재 비어 있음" 서사(날짜 6개)를 안고 있음. STATUS 머리 "마지막 갱신 2026-09-07" 이 현재(11-10)와 2개월 어긋남 |
| 재사용성 | **구조 자체(폴더=상태, 머리 주석 4필드)는 "새 가정 검증 스파이크"용으로 재사용 가능하나, "실행 가능한 스니펫을 정본으로"의 용도는 `.doc-snippets` + `scripts/doc-snippets.py`(2026-11-10 신설)가 훨씬 적합** |

`doc-snippets.py` 는 일반화할 가치가 큼: 문서 펜스 정보문자열을 닫힌 어휘(`continue`=앞 블록에 이어붙임 / `skip` / `no-run` / `error=QuadNNNN`)로 표시하고, 표시 밖이면 doc-check 가 ERROR 로 거부(`doc-check.py` 3-2). 컨텍스트(`q`, 모듈 등록)는 결정적으로 주입. **실행 가능한 스니펫 = 정본** 모델의 완성형이므로 claude-doctor 의 "문서 코드블록 검증" 공통 스킬 후보. luau-test 는 신규 확장 없이 STATUS 를 줄이고 "과거 스파이크 보관" 으로 동결 권장.

## 5. "스킬이었어야 할 것" (질문 4: CLAUDE.md:42-60 온디맨드 표와 conventions)

| 현재 위치 | 내용 | 스킬 형태 | 이유 |
|---|---|---|---|
| `conventions.md:224-249` | 중대 변경 핸드오버 체크리스트 | `/handover` (사용자 호출) | 절차형·가끔 실행·"핸드오버 준비하고 커밋해" 라는 트리거가 이미 있음(`:279`) |
| `conventions.md:268-338` | 감사자 호출 + 감사 루프 | `/audit-loop` | 6단계 절차, 인자(바뀐 파일 목록) 필요 |
| `conventions.md:389-485` | code-review 호출법 | `/review-round` | 인자 템플릿("model:opus", 검증자 상한)이 본질 |
| `conventions.md:381-388` | choom·예산·서브에이전트 복붙 블록 | 자동 스킬 + 기존 훅 | 훅이 차단하면 스킬을 읽게 하는 구조 |
| `conventions.md:362-379` | 백그라운드 에이전트 종료 판정 | 사용자 레벨 일반 지식 | 프로젝트 무관 |
| `CLAUDE.md:44-60` "외부 모델 감사 진입점 `qa-request/external-review-entry.md`" | 외부 모델에 감사 시킬 때 | 이미 `delegate-agy` 스킬이 있으니 통합 | 포인터 두 경로(스킬 + 표 행) 중복 |
| `conventions.md:94-147` 절 인용 규약 | 인용 문법 | 규칙(b) + doc-check 에러 메시지로 학습 | 도구가 강제하면 문서는 짧아도 됨 |
| `research/release-3.4.0-plan.md`, `release-4.0.0-plan.md` + `scripts/publish.py`, `release-assets.py`, `check-version.py` | 릴리스 | `/release` | 이미 스크립트 3개가 절차를 구성, 문서가 그 설명 |
| `.claude/audit/*`(58MB), `docs-review-*`, `doc-cleanup-*` | 문서 감사 | `/docs-audit` | 반복 수행 흔적 다수(`audit/code-review-2026-10-12~16`) |
| `agents/quad-site-tester.md` | 사이트 실측 | 에이전트로 유지 | 올바른 형태 |
| `question.md`(74줄)·`HUMAN_TODO.md` | 질문/사람 몫 | 문서로 유지 | 상태 데이터이지 절차 아님 |

## 6. quad vs quad-changelog-check 중복 (질문 5)

| 지표 | 값 |
|---|---|
| 관계 | 같은 레포의 stale 체크아웃(조상 커밋, 754커밋 뒤). 분기가 아니라 시점 차이 |
| `.claude/` 파일 수 | C 610개(7.7MB) vs Q 5,364개(55MB, worktrees 제외) |
| C 기준 | 동일 455(74.6%) / 내용 다름 139(22.8%) / C에만 16(2.6%) |
| Q 기준 | C와 동일한 파일은 Q 전체의 **8.5%**, Q에만 있는 파일 **약 4,760**(audit·base·session 증가분) |
| `CLAUDE.md` | 실질 동일(diff 2줄: 4,449 vs 4,282 B, 54줄 동일) |
| `conventions.md` | C 502줄 vs Q 531줄, diff `<`54/`>`25 (약 85% 공유) |
| `todos.md` | C 236줄 vs Q 92줄(Q는 2026-10-15 정리로 감축). diff 180줄 |
| `docs/` | C 167파일 vs Q 26,666파일(node_modules 포함 추정) |
| 소스 | `quad-base/src` 51/49 파일 차이, `quad-roblox/src` 17/17 차이 |
| 유일한 독자 가치 | `CHANGELOG.md` 미커밋 변경(3.0.0 항목 재작성)과 `prompt-ignoreme/prompt-ignoreme.md` 뿐 |

처방: CHANGELOG 변경과 프롬프트를 `quad` 쪽으로 옮기거나 `git worktree` 로 대체하고 디렉터리는 삭제. 두 에이전트가 각각 `/code/Projects` 에서 구 사본 지침을 읽는 위험(오래된 규약으로 작업)이 가장 큼.

## 7. 잘못 쓰인 부분 (질문 6)

| 유형 | 증거 | 문제 / 제안 |
|---|---|---|
| 비대한 상시 지시 | conventions 531줄, 한 불릿이 14~97줄(`:389-485`) | 지침 준수도 하락. 파일 자신이 "200줄 권장 초과 시 준수도 저하"를 인정(`CLAUDE.md:22-27`)하면서 3.9배 |
| 모순 | 상태 날짜: `CLAUDE.md:3` "2026-09-07 기준" vs `todos.md:8` "2026-09-06 기준" | 같은 사실을 세 곳이 서술(`CLAUDE.md:2-20`, `project-context.md:11-30`, `todos.md:8-22`)하고 "두 곳을 같이 고칠 것"(`CLAUDE.md:15`)이라고 요구 — 규약이 중복을 낳고 있음 |
| 모순 | `conventions.md:198` "병렬화 가능한 작업은 Agent 여러 개 동시" vs `:290` "감사자는 한 턴에 하나, 병렬 금지" vs `:455-480` "문서 추론형은 쪼개지 않는다" | 각 규칙은 좁은 예외로 해소되지만 읽는 쪽이 우선순위를 추론해야 함. 한 문장 결정표로 |
| 모순 | `conventions.md:1-4` "늘리기 전에 따져라" vs 날짜 신설 태그 18개 `**[20…`가 계속 증가 | 규약과 실행 불일치 |
| 오래된 날짜 주석 | `[20..` 날짜 태그 56개(conventions). 예: `:19-46` 모델 전환(2026-09-01→09-28), `:519` M2 자율 구현(2026-08-28, 종결) | 시간 종속 정보가 상시 컨텍스트에 있음. 마일스톤 종결 후 규칙이 잔존 |
| 오래된 날짜 | `todos.md` 번호 00,4,6,7,9 (1~3,5,8 누락), 6번 "2026-08-14 열네 번째 세션" | 시간 순서 서술이 "지금 할 일" 문서에 섞임. 문서 자신이 "해소된 건 지워라"(`todos.md:4`) 라고 하는데 지켜지지 않음 |
| 에이전트에게 불필요한 메타 | `conventions.md:6-8` HTML 주석이 제거된다는 설명, `:250-258` import 갱신 시점 한계, `:393-460` 취소선 정정 서사, `:19-46` 모델 가격 논쟁, 인용된 사용자 원문 다수 | 행동을 바꾸지 않는 경위 서사. 근거는 `session/` 파일이 이미 가짐. 인용문 보존 규약(`:498-511`)이 스스로 상시 컨텍스트 팽창을 유도 |
| 강조 남발 | `⭐` 30회(conventions), `⭐⭐` 2회, 반드시/절대/⚠️ 포함 41줄, 거의 모든 불릿이 `**⭐ [날짜 신설] …**` 머리 | 강조가 변별력을 잃음. 진짜 필수는 SAFETY(`:512`)·exit code(`:348`) 정도. 날짜 태그는 규칙 본문이 아니라 session 포인터로 |
| 사실 오류 이력 | `:393` "`/code-review`는 사용자만 호출" 틀림(2026-08-26 정정), `:430` "서브에이전트 모델 지정 불가"를 취소선 처리 후 번복 | 틀린 서술을 지우지 않고 취소선+정정으로 쌓아 읽는 비용 증가. 정정 후엔 올바른 문장만 남길 것 |
| 규약 중복 | doc-check 가 강제하는 것(절 인용·옛 X.luau·README 색인)을 conventions 가 113줄로 설명 | 도구가 강제하므로 에러 메시지에 사유를 넣고 문서는 요지만 |
| 인덱스 폭증 | `.claude/README.md` 78줄 12KB, 폴더마다 README, session-summary 2562줄 | 색인이 색인을 가리키는 3계층. 검색(grep)이 정본이라면 README 레이어 축소 가능 |
| 디스크 위생 | `.claude/worktrees` 14GB, `audit/` 58MB, `docs/` 728MB | 문서 저장소가 아니라 작업 산출물 포함. 에이전트가 Glob/Grep 하면 노이즈. `.claudeignore`류/삭제 필요 |
| 스킬 우회 | 스킬은 1개(`delegate-agy`)뿐인데 절차는 conventions 에 산문으로 | 5절 |

## 8. 우선순위 높은 변경 5개

| 순위 | 변경 | 효과 |
|---|---|---|
| 1 | **conventions.md 를 (a) 약 80줄로 줄이고 나머지를 `.claude/rules/*.md`(paths 조건부)와 스킬로 분해** — 2절 표대로: 문서표기·소스주석·QuadNNNN·CHANGELOG 는 rules, 핸드오버·감사 루프·review 는 `/handover` `/audit-loop` `/review-round` | 상시 약 28k → 6~8k 토큰, 지침 준수도 회복 |
| 2 | **종결·서사 제거**: `:19-46`(모델 전환), `:393-460`(취소선 정정), `:283-289`(Workflow 폐기), `:519-531`(M2 자율 규약) 를 `archive/` 로 이동하고 결론만 한 줄. 동시에 `CLAUDE.md:2-20` 상태 문단과 `todos.md` 00번을 `ROADMAP.md` 한 곳으로 단일화 | -150줄, 모순(09-06/09-07) 제거 |
| 3 | **`quad-changelog-check` 정리**: 미커밋 CHANGELOG 변경과 `prompt-ignoreme` 를 quad 로 이관 후 디렉터리 삭제(stale 규약 오독 방지), `quad-scratch/quad` 사본 삭제, `quad-agy` 의 worktree 정리 및 `quad-codex` 결과를 `quad/.claude/audit` 또는 보관 위치로 | 낡은 사본 2개 제거, 디스크 수백 MB |
| 4 | **자동화 승격**: `heavy-proc-guard.py` 를 `~/.claude/settings.json` 훅으로, `delegate-agy`(+`agy-delegate.sh` 경로 파라미터화)를 사용자 레벨 스킬로, 백그라운드 에이전트 종료 판정(`:362-379`)을 사용자 레벨 지침으로 | 모든 프로젝트에 메모리 가드·교차 모델 검토 적용 |
| 5 | **스니펫 정본화 공유 + luau-test 동결**: `scripts/doc-snippets.py` 의 닫힌 펜스 어휘 모델을 claude-doctor 공통 도구로 일반화하고, `luau-test/` 는 README/STATUS 를 짧게 줄여 "과거 스파이크 보관(CI 미연결)"으로 명시. `doc-check.py` 는 일반 코어 + quad 설정으로 분리 | 문서 코드블록 stale 방지를 다른 프로젝트에도 적용, 상태 문서 부담 제거 |
