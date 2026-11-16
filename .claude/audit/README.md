# audit

Point-in-time measurements, reviews and debates (snapshots: never edit content, never read whole; open the section you need). The table is generated (`coderag gen && coderag static-gen --dir .claude/audit`); multi-file audits are listed by hand below it.

<!-- coderag:begin -->
| Document | Description | Status |
|---|---|---|
| [01. Claude Code 공식 권장사항 정리](01-official-docs.md) | 기준일: 2026-11-10. claude-code-guide 서브에이전트가 응답으로 돌려준 보고서를 메인 세션이 저장했다. 확인 수준 표기 [확인]: 공식 페이지 원문에서 확인 (memory.md, best-practices) [요약확인]: 요약 도구로 가져온 내용. 수치는 원문 재… | no frontmatter |
| [02. 생태계 조사: 이미 있는데 못 쓰는 공식/커뮤니티 자산](02-ecosystem.md) | 작성일 2026-11-10. 읽기 전용 조사(다른 프로젝트 수정 없음). 확인 방법 표기: 열람 = 실제 파일/도구 출력을 직접 읽음, fetch = WebFetch 요약(원문 전체 아님), 검색 = 검색 결과 요약만. | no frontmatter |
| [03. quad 계열 에이전트 문서 감사 (quad / quad-changelog-check / quad-v1 / scratch·agy·codex)](03-quad-family.md) | 감사일 2026-11-10, 읽기 전용. 줄 번호는 `/code/Projects/quad` 기준(아니면 명시). 토큰은 한국어 혼합 텍스트 기준 추정치(오차 ±25%). | no frontmatter |
| [04. quad 외 프로젝트 에이전트 문서 감사](04-other-projects.md) | 감사일 2026-11-10. 대상은 `/code/Projects/` 의 stl-luau, rbvm, moonwave-luau, table-sim, tbox, vitrine, VideoSync, devplorer, mrow 입니다. 형제 격인 quad 는 비교 기준으로만 봤고, 모든 프… | no frontmatter |
| [06. 문서 시스템 감사와 Luau 정본(canon) 배치안](06-docs-and-canon.md) | 작성: 2026-11-10 / 범위: /code/Projects 읽기 전용 감사(node_modules, dist 미열람) + Claude Code 공식 문서(plugins-reference, plugin-marketplaces) 확인. 표기: 근거 경로는 /code/Projects… | no frontmatter |
| [07. stl-luau 다이어트 (P3 시범)](07-stl-luau-diet.md) | 작업일: 2026-11-10 작업 위치: `/code/Projects/stl-luau-doctor` (worktree, 브랜치 `doctor/diet`). 기준 커밋은 `e77fc03` 이다. 원본 `/code/Projects/stl-luau`(`split/class-like`)는 건… | no frontmatter |
| [10 — 하네스 사용 흔적 채굴: 반복 지시, 정정, 작업 흐름, memory 감사](10-harness-usage-mine.md) | 2026-11-10 작성. 원천은 모두 읽기 전용으로 다뤘다. | no frontmatter |
| [12 — 코드 구조 지적 이력, 저장소 실측, 재발 방지 설계](12-code-structure.md) | 2026-11-10 작성. 원천은 모두 읽기 전용으로 다뤘다. 다른 저장소에는 쓰지 않았고 git 은 `log`·`show`·`ls-tree` 만 썼다. | no frontmatter |
| [14. 하네스를 툴킷·sandbox 에 묶이지 않게 — 하드코딩 조사와 재구성](14-toolkit-agnostic.md) | 작성 2026-11-10. 사용자 요구(같은 날): 이 하네스는 Roblox/Luau 전용이 아니다(블로그 react/astro, vitrine 이 웹 툴킷). 다른 sandbox 에서도 쓰고, 외부 프로젝트 일부를 반입해 감사한다. 개념은 coderag 지식 계층(`coderag/.… | no frontmatter |
| [16. 마켓플레이스 전수 조사: 공식 마켓 317개와 claude.com 디렉터리 3,638개](16-marketplace.md) | 작성일 2026-11-10. 대상은 공식 마켓(`claude-plugins-official`)과 claude.com 마켓 디렉터리 전체다. 판정 기준은 바뀐 방향 셋이다. 하네스는 툴킷과 무관하고, 웹(블로그 react/astro, vitrine go+react)도 대상이며, 다른 s… | no frontmatter |
| [22. 사용자 가시성(statusline, 위쪽 배치, 테마, 응답 표시)](22-user-ergonomics.md) | 2026-11-11: 사용자 가시성(mod·테마·표시) 작업은 별도 저장소 `/code/Projects/quietcode-claude` 로 옮겼다(q-ui 시제품 포함, 이 문서의 사본은 그쪽 `docs/research-user-ergonomics.md`). 이 문서는 이력으로 남긴다… | no frontmatter |
| [24. 스킬 감사: 공식 모범 사례와 공식 스킬 짜임 대비](24-skill-audit.md) | 작성일 2026-11-11. 읽기 전용 감사다. 스킬 파일은 고치지 않았고, 시안(§5)은 이 문서 안에만 있다. 표시: [확인] 문서·파일에서 직접 읽음, [측정] 이 감사에서 센 값, [추정] 공식 자료에 없어 추론함, [미확인] 자료가 없음. | no frontmatter |
| [.claude/audit/28 claude-doctor 저장소 감사 1패스: 목록과 측정](28-repo-audit-pass1.md) | 범위: 읽기 전용 측정. 판단과 개선안은 2패스(다른 검토자)가 한다. 기준 시점은 작업 트리 HEAD 6ca93be + 다른 에이전트가 고치는 중인 변경(conventions 플러그인, home/.claude/rules/comments.md, PLAN.md, README.md)이다.… | no frontmatter |
| [.claude/audit/32 플러그인이 상시 맥락을 실을 수 있는가](32-plugin-ambient-context.md) | 조사일 2026-11-11, Claude Code 2.1.316. 문서는 /tmp/ccdocs 와 code.claude.com(output-styles) 기준. 실험은 /tmp/ambient (플러그인 `--plugin-dir`, sonnet, `-p`). | no frontmatter |
<!-- coderag:end -->

Multi-file audits:
- [19-external/](19-external/) - external views on the harness: official docs, community, knowledge tools
- [29-repo-audit-pass2-debate/](29-repo-audit-pass2-debate/) - claude-doctor audit pass 2: measurements and verdict
- [31-home-claude-md-debate/](31-home-claude-md-debate/) - user-level CLAUDE.md rewrite, probes
- [35-global-text-review/](35-global-text-review/) - review of model-facing text changed that day
- [36-structure-survey/](36-structure-survey/) - sibling `.claude/` patterns and this repo's top-level layout
- [38-records-convention/](38-records-convention/) - records convention debate and synthesis
- [39-records-experiment/](39-records-experiment/) - this restructure: questions, measure script, move map, results
- [40-pack-scope-probes/](40-pack-scope-probes/) - pack scope probes
- [41-knowledge-packs-debate/](41-knowledge-packs-debate/) - knowledge pack container and coderag process model debate
- [51-precompact-omit/](51-precompact-omit/) - PreCompact stdout steers the compaction summary; plugins that re-inject a block at compact tell it to omit that block
- [54-record-scopes/](54-record-scopes/) - records go to the nearest scope that owns their subject (`.claude/scopes/<path>/` for shipped folders, `<component>/.claude/` for separately owned ones); misplaced snapshots move with path rewrites
- [55-readable-code-probe/](55-readable-code-probe/) - readable-code rule probe: 5 rule lines cut long unbroken functions 54% to 9% (4% with a layout alert), correctness unchanged; fixes to the rule and alert listed
- [56-readable-code-wording/](56-readable-code-wording/) - always-loaded readable-code rule wording debate: about 2.4k chars, language-neutral, skill pointers are not read so moved items vanish

Audits about one plugin, pack or `home/` part live in that part's scope, `../scopes/<repo path>/audit/`, with the same numbers:
- [scopes/packs/luau-kb/audit/](../scopes/packs/luau-kb/audit/) - 05, 08, 09, 11, 13 (Luau knowledge map, mines, gaps, upstream), 52-luau-kb-skill-descriptions/ (descriptions can shrink to 57% without losing triggers), drafts/ (drafts written during audits)
- [scopes/plugins/q/audit/](../scopes/plugins/q/audit/) - 20 (onboarding), 21 (subagent cost disclosure)
- [scopes/plugins/qwreey-sessions/audit/](../scopes/plugins/qwreey-sessions/audit/) - 15 (session log)
- [scopes/plugins/qwreey-advisor/audit/](../scopes/plugins/qwreey-advisor/audit/) - 18 (second opinion), 25-advisor-description-debate/ (skill description wording)
- [scopes/plugins/qwreey-conventions/audit/](../scopes/plugins/qwreey-conventions/audit/) - 23 (memory portability), 26-doc-hygiene-debate/, 27 (conventions skill audit), 33-language-and-rules/, 34-conventions-probes/, 48-code-reuse-debate/
- [scopes/plugins/qwreey-workspace/audit/](../scopes/plugins/qwreey-workspace/audit/) - 30 (workspace skill gate probe)
- [scopes/plugins/qwreey-operator/audit/](../scopes/plugins/qwreey-operator/audit/) - 50-main-delegate/ (main talks, big implementation goes to a background subagent)
- [scopes/home/.claude/audit/](../scopes/home/.claude/audit/) - 17 (hook message format)

Audits about coderag (37, 42-47, 49, 53) live in coderag `.claude/audit/` with the same numbers.
