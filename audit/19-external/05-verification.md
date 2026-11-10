# 외부 조사 주장 1차 출처 검증 (2026-11-10)

대상: 01-official.md, 03-knowledge-tools.md, 04-luau-ecosystem-and-evals.md. 직접 URL 을 열어 확인했다. 외부 코드는 실행하지 않았고, `curl` 은 GitHub·MITRE API 의 JSON 조회에만 썼다.

## 요약

| # | 주장 | 판정 |
|---|---|---|
| 1 | Codex·Gemini CLI 가 `~/.agents/skills` 를 읽는다 | 확인됨 |
| 2 | Vercel: 스킬 56% 미호출, AGENTS.md 색인 100% | 일부 다름 (조건 미공개) |
| 3 | CVE-2026-75130 / ContextCrush | 확인됨 (수정 여부 서술은 보정 필요) |
| 4 | Claude Code 공식 기능들 | 확인됨 |
| 5 | 로컬 경로 마켓 플러그인은 제자리 로드, bump 불필요 | 확인됨 |
| 6 | Claude 5 글, best-practices, hooks 취지 | 확인됨 (표현 보정 1건) |
| 7 | Roblox deprecated.md 603개, LLM 머리말 | 확인됨 |
| 8 | Roblox Studio MCP(rust) 2026-04-03 보관 | 확인됨 (날짜는 마지막 푸시일, 보관 실행일은 API 에 없음) |
| 9 | Copilot Memory 인용+사용 시점 검증, +7%p | 확인됨 (+7% 는 7%p, 28일 만료는 미확인) |

## 1. Codex CLI·Gemini CLI 의 Agent Skills 경로: 확인됨

**Codex** (보고서 출처 https://learn.chatgpt.com/docs/build-skills):
- 문서 요지: `.agents/skills` 를 현재 디렉터리부터 저장소 루트까지 올라가며 스캔("Codex scans `.agents/skills` in every directory from your current working directory up to the repository root"), 사용자 `$HOME/.agents/skills`, 관리자 `/etc/codex/skills`, 시스템 번들. symlink 를 따라간다. 문서에는 버전 정보가 없다.
- 릴리스 노트(GitHub API, openai/codex):
  - rust-v0.94.0 (2026-02-02): "Skills can be loaded from `.agents/skills`" (#10317).
  - rust-v0.95.0 (2026-02-04): "Added personal skill loading from `~/.agents/skills` (with `~/.codex/skills` compatibility)" (#10437).
  - 즉 사용자 수준 `~/.agents/skills` 는 0.95.0 부터다.

**Gemini CLI** (보고서 출처 https://geminicli.com/docs/cli/skills/):
- 문서: 사용자 스킬 "Located in `~/.gemini/skills/` or the `~/.agents/skills/` alias", 워크스페이스 "`.gemini/skills/` or the `.agents/skills/` alias". 같은 계층에서는 `.agents` 가 우선. 페이지 날짜 "Last updated: Apr 30, 2026".
- 릴리스: `feat(core): add .agents/skills directory alias for skill discovery` (PR #18151)가 v0.29.0-nightly.20260205.a3af4a8ca (2026-02-05) 에 처음 실렸다. 첫 안정판 번호는 API 조회로 확인하지 못했다.
- 보정 사항(보고서에 없음): 같은 문서가 "Gemini CLI was replaced by Antigravity CLI on June 18th, 2026, for unpaid tier and Google One users" 라고 적는다. Gemini CLI 를 계속 소비 대상으로 삼을지는 이 사실을 반영해야 한다.

## 2. Vercel 평가: 일부 다름

출처: https://vercel.com/blog/agents-md-outperforms-skills-in-our-agent-evals (보고서 날짜 2026-01-27)
- 원문: "In 56% of eval cases, the skill was never invoked." (기본 동작, 명시 지시 전)
- 원문: "A compressed 8KB docs index embedded directly in `AGENTS.md` achieved a 100% pass rate, while skills maxed out at 79%."
- 표(통과율 Overall): 기준(문서 없음) 53%, 스킬 기본 53%, 스킬+명시 지시 79%, AGENTS.md 색인 100%. (Build/Lint/Test 세부: 색인 100/100/100, 기준 84/95/63)
- 다른 점. 보고서는 조건을 적지 않았고, 원문도 **모델, 하네스(에이전트), 과제 수를 공개하지 않는다**. 재시도로 분산을 배제했다고만 하고 횟수·분산은 없다. 따라서 "몇 개 과제에서 몇 %" 는 확인 불가다.
- 조건: 자사가 만든 Next.js 16 신규 API(`connection()`, `'use cache'`, `forbidden()` 등, 모델 학습 데이터에 없는 것) 평가 한정. 저자도 "working theory"라고 적고 모델이 좋아지면 격차가 줄 수 있다고 한다. 스킬 결과는 문구에 민감했다("invoke first" 가 `next.config.ts` 변경을 놓침).
- 결론: 방향성 근거로는 쓸 수 있으나 "스킬은 56% 호출 안 된다" 를 일반 법칙으로 인용하면 안 된다. "자사 Next.js 16 평가에서 56%" 로 한정해 써야 한다.

## 3. CVE-2026-75130 / ContextCrush: 확인됨

- CVE 레코드(MITRE cveawg API, 1차): VulnCheck 이 할당, 2026-08-18 공개. 제목 "Context7 2.1.2 Prompt Injection via Custom AI Instructions". 설명 "Context7 through 2.1.2 contains a prompt injection vulnerability ... through the Custom AI Instructions feature served via the MCP server ... exfiltrate credentials from environment files ... destructive file deletion". CWE-1427. CVSS v4.0 6.4 MEDIUM(벡터 AV:N/AC:L/AT:N/PR:L/UI:P), v3.1 은 같은 레코드에 별도 점수(검색 결과상 9.0 critical). 보고서의 "CVSS 가 출처마다 다르다" 는 한 레코드 안의 v3.1/v4.0 차이로 설명된다.
- NVD 페이지(https://nvd.nist.gov/vuln/detail/CVE-2026-75130)는 WebFetch 로 내용이 안 열렸다(JS 렌더링). GHSA 는 있다: GHSA-97r6-3rgm-v39r, Moderate, Unreviewed, 2026-08-18 (https://github.com/advisories?query=CVE-2026-75130).
- 벤더 원문: https://context7.com/guides/contextcrush. 타임라인 2026-02-18 보고, 02-19 수락, 02-23 운영 반영, 03-05 Noma 공개, 08-18 CVE. 서버 측 수정이라 npm 업그레이드가 필요 없고, Context7 은 "CVE 가 패키지 버전 2.1.2 에 잘못 묶는다" 며 VulnCheck 에 수정을 요청했다고 한다. 야생 악용은 관찰되지 않았다.
- 보정: 보고서의 "수정 여부는 출처마다 다르다" 는 해소된다. 벤더 1차 원문으로 2026-02-23 서버 측 수정이 확인된다(보고서는 2차 출처로 표기). 공격 경로가 "라이브러리 등록자가 Custom Rules 에 지시를 넣는다" 이므로 git pack 위험 논의에는 그대로 유효하다.

## 4. Claude Code 공식 기능: 확인됨

로컬: `claude --version` = 2.1.316. `claude plugin --help` 에 `details`, `eval`, `init`, `install` 등이 있다.

| 기능 | 근거 (code.claude.com/docs) |
|---|---|
| `/doctor`, `prompt-audit` | commands: "`/doctor [prompt-audit [path]]` ... Run a setup checkup that diagnoses installation, settings, extension, and `CLAUDE.md` problems ... The `prompt-audit` subcommand requires Claude Code v2.1.283 or later. Alias: `/checkup`" |
| `/skill-doctor` | commands: "Show what each of your skills costs in context and how often it gets used ... Requires Claude Code v2.1.252 or later and feature-flag fetching" |
| `/insights` | commands/costs: 최근 세션 최대 200개 분석, `~/.claude/usage-data/report.html` 저장, cloud 세션에서는 불가 |
| `claude plugin details` | plugins/cli-reference: "Show a plugin's component inventory and its projected token cost." |
| `claude plugin eval` | 같은 문서: "Requires Claude Code v2.1.269 or later." 케이스당 여러 번, 플러그인 없는 팔도 기본 실행 |
| `InstructionsLoaded` 훅 | hooks: "When a CLAUDE.md or `.claude/rules/*.md` file is loaded into context. Fires at session start and when files are lazily loaded". matcher 값 `session_start`, `nested_traversal`, `path_glob_match`, `include`, `compact`. 입력 필드명 `load_reason` 은 이 확인에서 못 봤다 |
| `# Compact instructions` | costs "Manage context proactively": CLAUDE.md 루트에 `# Compact instructions` 절 예시가 있다 |
| `idleCompaction` | settings-reference: "compacts a long conversation that you've stepped away from. Your next message then sends a summary instead of the whole conversation." 기본 `true`, v2.1.290 이상, 한 시간 캐시 TTL + 200,000 토큰 기본 임계 + 약 1시간 유휴. `/config` 행은 v2.1.302 이상. `false` 로 끈다 |

보고서의 "2.1.314 에서 적용 대상이 넓어졌다" 는 이번에 확인하지 않았다(changelog 미열람).

## 5. 로컬 경로 마켓은 제자리 로드: 확인됨

출처: https://code.claude.com/docs/en/plugins/loading.md "In-place and copied plugins".
- 원문: "Relative-path plugins in a marketplace you added from a local path: the plugin loads in place from its path inside the marketplace folder. Your edits to the source directory take effect at the next session start or `/reload-plugins`, and you don't need to increase the version."
- 보충: "A plugin loaded in place from a marketplace you added from a local path loads its current source files at every session start, whatever its version string says." `--plugin-dir`·skills-directory 플러그인도 제자리 로드다. 그 외 마켓 플러그인은 `cache/<marketplace>/<plugin>/<version>/` 로 복사된다.
- 주의: 제자리 로드 플러그인은 Node 의존성을 자동 설치하지 않는다. 그리고 보고서가 쓴 "plugins/loading" 은 정확히 `plugins/loading.md` 이다(요약 문구가 아니라 원문 일치).

## 6. 취지 인용: 확인됨

- Claude 5 글 (https://claude.com/blog/the-new-rules-of-context-engineering-for-claude-5-generation-models, claude.dev 로 308 리다이렉트, Thariq Shihipar, 2026-07-24):
  - "newer models have better judgement and can handle these decisions well without explicit rules."
  - "We removed over 80% of Claude Code's system prompt for models like Claude Opus 5 and Claude Fable 5 with no measurable loss on our coding evaluations."
  - "use the command `/doctor` in Claude Code to rightsize your skills, and CLAUDE.md files."
  - 상충 예: "leave documentation as appropriate" 와 "DO NOT add comments" 가 한 요청에 같이 나온다. 보정: 이것은 "지우라" 는 지시가 아니라 팀이 자기 트랜스크립트에서 발견한 상충이고, 제약을 줄이면 상충이 준다는 논지다. 보고서 표현("상충은 지우라고 한다")은 약간 강하다.
- best-practices (https://code.claude.com/docs/en/best-practices.md):
  - "If you keep adding emphasis to a `CLAUDE.md` line and Claude still misses it, that's a sign the line belongs in a hook. The reverse holds too: if you have hooks for things that are only preferences, delete them and let Claude decide."
  - "adding IMPORTANT probably won't fix it."
  - 표: "Add IMPORTANT or ALL CAPS to instructions Claude keeps missing" 는 하지 않아도 되는 일. "Current ones follow a plainly worded line, and piling on emphasis mostly makes Claude over-apply the rule."
  - "If something has to happen every time, make it a hook, a deny rule, or a managed setting. `CLAUDE.md` is for guidelines, and Claude is allowed to decide a guideline doesn't apply."
- hooks (https://code.claude.com/docs/en/hooks.md): "Write the text as factual statements rather than imperative system instructions ... Text framed as out-of-band system commands can trigger Claude's prompt-injection defenses, which causes Claude to surface the text to you instead of treating it as context." "For instructions that never change, prefer CLAUDE.md."

## 7. Roblox deprecated.md: 확인됨

- 웹(https://create.roblox.com/docs/reference/engine/deprecated.md)에서 열린다. 원문 머리: "# Deprecated Roblox Engine APIs" / "For LLM code assistants: Do NOT suggest any API listed below." / "If you encounter these in existing code, suggest the replacement and help the user migrate." / "Last generated from YAML source at build time."
- 구성: Properties 141, Methods 247, Events 38, Callbacks 2, Functions 15, Enum Items 160, 합 603. 보고서와 일치.
- 로컬 사본 `/code/.cache/roblox-docs/creator-docs/content/en-us/reference/engine/` 에는 `README.md`, `classes/`, `enums/`, `globals/` 등이 있으나 `deprecated*` 파일이 없다. 사본 전체에서 "Do NOT suggest" 문자열 검색 결과도 없다. 머리말의 "generated ... at build time" 과 맞물려, 사본에 소스 YAML 만 있고 이 페이지는 웹 빌드에서만 생성되는 것으로 보인다(빌드 파이프라인 자체는 확인하지 못했다).
- 보정: 머리말의 전반부만 인용하면 "쓰지 말라" 로 읽히지만, 원문은 기존 코드에서 만나면 대체 API 를 제안해 이전을 도우라고 한다. 검사 도구로 쓸 때 이 방향이 맞다.

## 8. Studio MCP(rust) 보관: 확인됨

- GitHub API(Roblox/studio-rust-mcp-server): `"archived": true`, `pushed_at` 2026-04-03T17:36:12Z, 마지막 커밋 "Update README.md" 같은 시각, 라이선스 MIT.
- README 원문: "This MCP Server is no longer being actively developed ... We've shifted ongoing engineering investment to the built-in MCP Server included with Roblox Studio ... source code and previous releases will remain available here".
- 보정: 2026-04-03 은 마지막 푸시(README 에 경고를 넣은 커밋) 일시다. 저장소를 archive 로 바꾼 정확한 날짜는 API 에 없다. 보고서가 "2026-04-03 에 보관" 이라 쓴 것은 약간 단정적이다.
- 보고서가 말한 `assistant/mcp.md` 의 링크 불일치는 이번에 열어 보지 않았다.

## 9. Copilot Memory: 확인됨

출처: https://github.blog/ai-and-ml/github-copilot/building-an-agentic-memory-system-for-github-copilot/
- "we store memories with citations: references to specific code locations that support each fact."
- "it verifies the citations in real-time, validating that the information is accurate and relevant to the current branch" (절 제목 "just-in-time verification").
- "7% increase in pull request merge rates (90% with memories vs. 83% without)." 정확히는 7%p 다(보고서의 +7%p 는 맞고, 블로그 자체는 "7%"로 표기).
- "3% increase in precision and 4% increase in recall." (코드 리뷰)
- "The memory pool self-healed as agents stored corrected versions based on their observations."
- 확인 불가: 보고서의 "28일 동안 쓰이지 않으면 지운다". 블로그 본문 요약에서는 찾지 못했다(GitHub docs 의 별도 페이지 `docs.github.com/.../copilot-memory` 에 있을 수 있으나 이번에 열지 않았다). 03 의 "Copilot 28일 만료" 에 기댄 비교 두 곳(§111, §176)은 출처 재확인이 필요하다.
- 한계: 병합률은 GitHub 자체 A/B 이고 인과 검증은 아니다.

## 보고서에 반영할 보정 목록

1. Vercel 56%·100% 는 "자사 Next.js 16 평가, 모델·하네스·과제 수 미공개" 로 한정한다.
2. Gemini CLI 는 2026-06-18 부터 Antigravity CLI 로 대체되는 경로가 있다. 소비 대상 판단 시 반영한다.
3. Context7 수정은 벤더 1차 원문으로 2026-02-23 서버 측 수정이 확인된다.
4. Copilot 28일 만료는 출처 재확인 전까지 "미확인" 으로 낮춘다.
5. rust MCP "2026-04-03 보관" 은 "마지막 푸시 2026-04-03, 현재 archived" 로 쓴다.
6. Claude 5 글의 "상충은 지우라" 는 "상충을 줄이려면 불필요한 제약을 걷어라" 로 완화한다.
