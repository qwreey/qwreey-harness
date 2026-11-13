# audit

Point-in-time measurements, reviews and debates (snapshots: never edit content, never read whole; open the section you need). The table is generated (`coderag gen && coderag static-gen --dir .claude/audit`); multi-file audits are listed by hand below it.

<!-- coderag:begin -->
| Document | Description | Status |
|---|---|---|
| [01. Claude Code 공식 권장사항 정리](01-official-docs.md) | 기준일: 2026-11-10. claude-code-guide 서브에이전트가 응답으로 돌려준 보고서를 메인 세션이 저장했다. 확인 수준 표기 [확인]: 공식 페이지 원문에서 확인 (memory.md, best-practices) [요약확인]: 요약 도구로 가져온 내용. 수치는 원문 재… | no frontmatter |
| [02. 생태계 조사: 이미 있는데 못 쓰는 공식/커뮤니티 자산](02-ecosystem.md) | 작성일 2026-11-10. 읽기 전용 조사(다른 프로젝트 수정 없음). 확인 방법 표기: 열람 = 실제 파일/도구 출력을 직접 읽음, fetch = WebFetch 요약(원문 전체 아님), 검색 = 검색 결과 요약만. | no frontmatter |
| [03. quad 계열 에이전트 문서 감사 (quad / quad-changelog-check / quad-v1 / scratch·agy·codex)](03-quad-family.md) | 감사일 2026-11-10, 읽기 전용. 줄 번호는 `/code/Projects/quad` 기준(아니면 명시). 토큰은 한국어 혼합 텍스트 기준 추정치(오차 ±25%). | no frontmatter |
| [04. quad 외 프로젝트 에이전트 문서 감사](04-other-projects.md) | 감사일 2026-11-10. 대상은 `/code/Projects/` 의 stl-luau, rbvm, moonwave-luau, table-sim, tbox, vitrine, VideoSync, devplorer, mrow 입니다. 형제 격인 quad 는 비교 기준으로만 봤고, 모든 프… | no frontmatter |
| [05. Luau/Roblox 지식 지도와 Luau 스킬 세트 설계안](05-luau-knowledge-map.md) | 작성 2026-11-10. 대상: `/code/Projects` 전체(읽기 전용). 쓴 곳은 `claude-doctor/audit/` 와 `/tmp` 뿐. 근거 표기: `프로젝트/경로:줄`(줄은 `##` 제목 줄 번호 기준, 시점 2026-11-10). 프로젝트 접두어 `stl`=st… | no frontmatter |
| [06. 문서 시스템 감사와 Luau 정본(canon) 배치안](06-docs-and-canon.md) | 작성: 2026-11-10 / 범위: /code/Projects 읽기 전용 감사(node_modules, dist 미열람) + Claude Code 공식 문서(plugins-reference, plugin-marketplaces) 확인. 표기: 근거 경로는 /code/Projects… | no frontmatter |
| [07. stl-luau 다이어트 (P3 시범)](07-stl-luau-diet.md) | 작업일: 2026-11-10 작업 위치: `/code/Projects/stl-luau-doctor` (worktree, 브랜치 `doctor/diet`). 기준 커밋은 `e77fc03` 이다. 원본 `/code/Projects/stl-luau`(`split/class-like`)는 건… | no frontmatter |
| [08 — quad `.claude/` 기록에서 캐낸 일반 Luau/Roblox 지식 (luau-kb 이전 후보)](08-quad-knowledge-mine.md) | 작성: 2026-11-10 · 대상 저장소: `/code/Projects/quad` (읽기 전용으로만 봄, 쓰기 0) 원천 경로는 quad 저장소 루트 기준 상대경로다(`.claude/…`, `docs/…`, `scripts/…`). 줄 번호는 grep -n / Read 로 확인한 값… | no frontmatter |
| [09. quad 밖 저장소의 일반 Luau/Roblox 지식 채굴 — luau-kb 이전 후보](09-other-knowledge-mine.md) | 감사일 2026-11-10. 읽기 전용(원천 저장소는 아무것도 고치지 않음). 범위: stl-luau(정리판 `stl-luau-doctor`), rbvm, table-sim, devplorer, tbox, moonwave-luau·mrow, vitrine·VideoSync·Laftel… | no frontmatter |
| [10 — 하네스 사용 흔적 채굴: 반복 지시, 정정, 작업 흐름, memory 감사](10-harness-usage-mine.md) | 2026-11-10 작성. 원천은 모두 읽기 전용으로 다뤘다. | no frontmatter |
| [11. 지식 공백 메우기 — 결과 요약](11-knowledge-gaps.md) | 작성 2026-11-10. 대상은 `05-luau-knowledge-map.md` §0-4 의 "지식이 없는 영역" 6개다(type function 제외). 초안: `.claude/archive/research/drafts/gaps/*.md`. 스니펫: `.claude/archive/… | no frontmatter |
| [12 — 코드 구조 지적 이력, 저장소 실측, 재발 방지 설계](12-code-structure.md) | 2026-11-10 작성. 원천은 모두 읽기 전용으로 다뤘다. 다른 저장소에는 쓰지 않았고 git 은 `log`·`show`·`ls-tree` 만 썼다. | no frontmatter |
| [13. luau-upstream — 업스트림 관찰 스킬과 현재 상태](13-luau-upstream.md) | 작성 2026-11-10. 결과물: `luau-kb/skills/luau-upstream/`(SKILL.md + references 5개), `luau-kb/tools/upstream_check.py`, `home/MANIFEST` 링크 한 줄. 조사 출처: luau·luau-lsp·… | no frontmatter |
| [14. 하네스를 툴킷·sandbox 에 묶이지 않게 — 하드코딩 조사와 재구성](14-toolkit-agnostic.md) | 작성 2026-11-10. 사용자 요구(같은 날): 이 하네스는 Roblox/Luau 전용이 아니다(블로그 react/astro, vitrine 이 웹 툴킷). 다른 sandbox 에서도 쓰고, 외부 프로젝트 일부를 반입해 감사한다. 개념은 coderag 지식 계층(`coderag/t… | no frontmatter |
| [15. 세션 기록 자동화 — remember 조사, 환경 실측, 요약 품질 실측](15-session-log.md) | 이름 변경(2026-11-11): 플러그인 `session-log` 는 `q` 로 합쳐졌다(`plugins/q/`). 명령은 `/q:checkpoint`, `/q:import`. 저장 위치와 기록 형식은 그대로다. 아래의 옛 이름은 이력이다. | no frontmatter |
| [16. 마켓플레이스 전수 조사: 공식 마켓 317개와 claude.com 디렉터리 3,638개](16-marketplace.md) | 작성일 2026-11-10. 대상은 공식 마켓(`claude-plugins-official`)과 claude.com 마켓 디렉터리 전체다. 판정 기준은 바뀐 방향 셋이다. 하네스는 툴킷과 무관하고, 웹(블로그 react/astro, vitrine go+react)도 대상이며, 다른 s… | no frontmatter |
| [17. 훅 메시지 형식 실측과 규약](17-hook-messages.md) | 날짜 2026-11-10, claude 2.1.316, sonnet. 규약 본문: `home/.claude/HOOK-MESSAGES.md`. | no frontmatter |
| [18. 검토(second opinion) 운용 제안: advisor 대신 예측 가능한 독립 검토](18-second-opinion.md) | 날짜 2026-11-10, claude 2.1.316, 메인 opus 5.5. 이번에는 제안만 한다. 설정·CLAUDE.md·훅은 고치지 않았고 플러그인도 설치하지 않았다. 초안은 `drafts/second-opinion/`에만 있다(§12 뒤 플러그인 `plugins/second-o… | no frontmatter |
| [20. 회사 배포용 하네스 온보딩 진입점](20-onboarding.md) | 이름 변경(2026-11-11): 플러그인 `harness-onboarding` 은 `q` 로 합쳐졌고 진입점은 `/q:start`(스킬 `plugins/q/skills/start`)다. 아래의 옛 경로·이름은 이력이다. | no frontmatter |
| [21. 서브에이전트 비용: 고지, 슬롯, 가시화](21-cost-disclosure.md) | 이름 변경(2026-11-11): 사용자 호출 명령은 플러그인 `q` 로 모였다(`/away`→`/q:away`, `/back`→`/q:back`). 스킬은 `plugins/q/skills/{away,back}`. 아래 서술의 옛 위치 `home/.claude/skills/*` 는 이… | no frontmatter |
| [22. 사용자 가시성(statusline, 위쪽 배치, 테마, 응답 표시)](22-user-ergonomics.md) | 2026-11-11: 사용자 가시성(mod·테마·표시) 작업은 별도 저장소 `/code/Projects/quietcode-claude` 로 옮겼다(q-ui 시제품 포함, 이 문서의 사본은 그쪽 `docs/research-user-ergonomics.md`). 이 문서는 이력으로 남긴다… | no frontmatter |
| [23. auto memory 이식성](23-memory-portability.md) | 2026-11-11 사용자 문제 제기: 저장소에 실려야 할 지식이 메모리에만 들어가 다른 사람이 저장소를 열면 빠지고, 폴더를 옮기면 메모리가 끊기는데 사용자들이 모른다. 회사 동료(비개발자 포함)에게도 배포할 하네스라 이 점을 장치로 다뤄야 한다. 상태: 설계와 구현 완료(미커밋).… | no frontmatter |
| [24. 스킬 감사: 공식 모범 사례와 공식 스킬 짜임 대비](24-skill-audit.md) | 작성일 2026-11-11. 읽기 전용 감사다. 스킬 파일은 고치지 않았고, 시안(§5)은 이 문서 안에만 있다. 표시: [확인] 문서·파일에서 직접 읽음, [측정] 이 감사에서 센 값, [추정] 공식 자료에 없어 추론함, [미확인] 자료가 없음. | no frontmatter |
| [qwreey-conventions 스킬 감사와 남은 주석 보고](27-conventions-skill-audit.md) | 범위: `plugins/qwreey-conventions` 의 스킬 둘(`comments`, `agent-docs`), 짝 규칙(`home/.claude/rules/comments.md`, `agent-docs.md`), 훅 알림 문구. 커밋하지 않았다. 기준: skill-creato… | no frontmatter |
| [.claude/audit/28 claude-doctor 저장소 감사 1패스: 목록과 측정](28-repo-audit-pass1.md) | 범위: 읽기 전용 측정. 판단과 개선안은 2패스(다른 검토자)가 한다. 기준 시점은 작업 트리 HEAD 6ca93be + 다른 에이전트가 고치는 중인 변경(conventions 플러그인, home/.claude/rules/comments.md, PLAN.md, README.md)이다.… | no frontmatter |
| [.claude/audit/30 - workspace 스킬 게이트 실험 (paths, 차단 후 로드 게이트, compact)](30-workspace-skill-gate-probe.md) | 2026-11-11, Claude Code 2.1.316, sonnet. 실험 파일은 /tmp/probe30 (프로젝트 /tmp/probe30/proj, 훅 /tmp/probe30/hooks/gate.py, 설정 /tmp/probe30/settings.json 을 `--settings… | no frontmatter |
| [.claude/audit/32 플러그인이 상시 맥락을 실을 수 있는가](32-plugin-ambient-context.md) | 조사일 2026-11-11, Claude Code 2.1.316. 문서는 /tmp/ccdocs 와 code.claude.com(output-styles) 기준. 실험은 /tmp/ambient (플러그인 `--plugin-dir`, sonnet, `-p`). | no frontmatter |
| [43-levels-measure/ — coderag 단계 공개(L0/L1/L2) 실측](43-levels-measure/README.md) | Snapshot 2026-11-12. coderag 38d7920(플러그인 0.3.3)의 `search --level` 실측. 설계는 `.claude/research/coderag-format-and-levels.md` §4-§5, 사용자 결정은 §6-3("자동 펼침의 경우 실측부터"… | no frontmatter |
| [44-search-output-tokens/ — coderag search 출력 토큰 절감 실측](44-search-output-tokens/README.md) | Snapshot 2026-11-12. coderag 3fd0944(플러그인 0.4.0)의 `search` 출력 형식 변경 실측. 근거: quad 3질의 23결과에서 절대경로가 글자의 30%(추정 토큰 약 18%), 꼬리표 약 7%. 사용자 결정 "추천대로"(A+C 기본, B 옵션). | no frontmatter |
| [45-search-descriptions/ — coderag search 결과의 설명 줄: 얼마나 차지하고, 무엇을 줄여도 고르는 데 지장 없나](45-search-descriptions/README.md) | Snapshot 2026-11-12. coderag 3fd0944 위에 `--desc-max` 추가(커밋 0b0c724, 푸시 없음)로 잰 실측. 근거: audit/44 에서 결과 한 줄 설명(한글 약 1.6토큰/자)이 출력의 주비용. 사용자: "설명은 영어여도 될 수도 있겠다는 생각… | no frontmatter |
| [46-coderag-agent-surface/ — 46. coderag 가 모델에게 보이는 것 전부: 스킬·MCP 도구 관점 검토](46-coderag-agent-surface/README.md) | Snapshot 2026-11-12. coderag 234c6c1(플러그인 0.4.2, `target/release`) 읽기 전용 검토. 다른 세션이 고치던 `crates/coderag-core/src/docs/stale.rs`(코드 주석 참조 스캐너)와 coderag/.claude/base/docs-search.md §11.… | no frontmatter |
<!-- coderag:end -->

Multi-file audits:
- [19-external/](19-external/) - external views on the harness: official docs, community, knowledge tools
- [25-advisor-description-debate/](25-advisor-description-debate/) - wording of the qwreey-advisor skill descriptions
- [26-doc-hygiene-debate/](26-doc-hygiene-debate/) - agent-docs and comments conventions (history out of docs)
- [29-repo-audit-pass2-debate/](29-repo-audit-pass2-debate/) - claude-doctor audit pass 2: measurements and verdict
- [31-home-claude-md-debate/](31-home-claude-md-debate/) - user-level CLAUDE.md rewrite, probes
- [33-language-and-rules/](33-language-and-rules/) - reply-language drift and rule placement, measured
- [34-conventions-probes/](34-conventions-probes/) - qwreey-conventions hook probes (injection, Stop block)
- [35-global-text-review/](35-global-text-review/) - review of model-facing text changed that day
- [36-structure-survey/](36-structure-survey/) - sibling `.claude/` patterns and this repo's top-level layout
- [37-coderag-records/](37-coderag-records/) - can coderag back the records system
- [38-records-convention/](38-records-convention/) - records convention debate and synthesis
- [39-records-experiment/](39-records-experiment/) - this restructure: questions, measure script, move map, results
- [40-pack-scope-probes/](40-pack-scope-probes/) - pack scope probes
- [41-knowledge-packs-debate/](41-knowledge-packs-debate/) - knowledge pack container and coderag process model debate
- [42-memory-systems-survey/](42-memory-systems-survey/) - static survey of 8 agent memory systems
- [43-levels-measure/](43-levels-measure/) - coderag L0/L1/L2 levels measurement
- [44-search-output-tokens/](44-search-output-tokens/) - search output token cut (legend paths, tags, handles)
- [45-search-descriptions/](45-search-descriptions/) - search summary line length and language vs picking accuracy
- [46-coderag-agent-surface/](46-coderag-agent-surface/) - review of every coderag string a model sees (skill/MCP view)
- [47-coderag-code-quality/](47-coderag-code-quality/) - coderag hardcoding, duplicates, reinvented wheels; convention input with measured precision
- [48-code-reuse-debate/](48-code-reuse-debate/) - code-reuse rule wording debate (P concise, Q toolkit-wide) and the revised rule
- [49-records-description/](49-records-description/) - who writes search summary lines: descriptions required on new records incl. snapshots, write-time lint, no backfill
- [drafts/](drafts/) - drafts written during audits
