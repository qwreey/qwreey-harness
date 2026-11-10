# 06. 문서 시스템 감사와 Luau 정본(canon) 배치안

작성: 2026-11-10 / 범위: /code/Projects 읽기 전용 감사(node_modules, dist 미열람) + Claude Code 공식 문서(plugins-reference, plugin-marketplaces) 확인.
표기: 근거 경로는 /code/Projects 기준 상대경로.

---

## 0. 요약

1. 문서 사이트는 **Astro Starlight 3벌**(quad, quad-changelog-check, devplorer)과 **MkDocs 1벌(quad-v1, 레거시 빌드 산출물만 남음)**이다. Moonwave 사이트는 하나도 없다. moonwave-luau는 "Moonwave 주석 추출기" 라이브러리일 뿐이다.
2. Starlight 설정은 **복붙 포크**다. quad가 정본에 가깝고(플러그인 6개, 컴포넌트, CSS 8개), qcc는 구버전 사본, devplorer는 "줄여서 쓴" 사본이다. 공유 패키지가 없다.
3. **스니펫 검증기는 quad에만 있다.** `quad/scripts/doc-snippets.py`(420줄) + `doc-snippets-runshim.luau`(227줄). 그러나 quad 전용 가정(mock 백엔드, `q` 셋업 모듈, `QuadNNNN` 에러 ID)이 박혀 있어 그대로 재사용은 불가능하고, 골격(펜스 표시 어휘, 체이닝, strict 검사 + 대조군)만 추출 가능하다.
4. **에이전트용 문서는 이미 있다.** `quad/docs/skills/quad-ui-dev/`(SKILL.md 41KB + references 3개)가 정본 스킬이고, `quad/docs/agents/01-quad-ui-dev-skill.md`는 그 스킬의 **설치/사용법을 사람에게 알려 주는 한국어 페이지**다(Claude 관련 문서 맞음). `starlight-md-txt`가 모든 페이지를 `<slug>.md.txt`로 노출한다. llms.txt 생성기는 없다.
5. 사람용 문서와 스킬은 **같은 원천에서 생성되지 않는다.** 스킬은 손으로 쓴 요약이고, 사이트 쪽이 정본이라고 SKILL.md 스스로 선언한다. 두 사본(quad / qcc)은 이미 내용이 갈라졌다(`diff -rq` 4개 파일 상이).
6. Luau 문법 하이라이트: **커스텀 grammar 없음.** Starlight 기본 Expressive Code(Shiki)의 내장 `luau`에 의존한다. 플레이그라운드 없음(실행 가능한 플레이그라운드 구현이 한 곳도 없다).
7. Claude Code 플러그인 포맷상 `claude-doctor`라는 이름은 `claude plugin validate`에서 **예약어 ERROR**(`claude-` 접두)다. 플러그인/마켓플레이스 이름은 `luau-kb` 등으로 정해야 한다(5절).
8. 추천: **대안 B — 별도 `luau-kb` 저장소를 marketplace + plugin + 스니펫 CI로 만들고, 사이트(Starlight)는 그 저장소의 `docs/`에서 빌드**하며, 프로젝트별 지식은 각 프로젝트에 남긴다(6절).

---

## 1. 문서 사이트 인벤토리

| 프로젝트 | 위치 | 스택 | 파일 규모(제외 후) | 비고 |
|---|---|---|---|---|
| quad | `quad/docs/` + `quad/docs/site/` | **Astro 7 + Starlight 0.42**, 정본 .md는 `docs/<track>/`, 사이트용 사본은 `sync-docs.py`가 `site/src/content/docs/`로 생성 | md 약 95(getting-started 22, how-to 11, overview 3, quadnomicon 12, reference 36, assets 6, agents 1, skills 4) + site 129. "948"은 `site/dist`, `site/node_modules`, `.astro` 포함 수치 | ko가 root 로케일 + en. 배포: Cloudflare Pages/Wrangler 수동(`site/DEPLOY.md`) |
| quad-changelog-check | `quad-changelog-check/docs/` + `docs/site/` | 동일(Starlight), **구버전 포크** | 구조 동일. `sync-docs.py` 162줄(quad는 325줄), 컴포넌트/스크립트 디렉터리 없음, CSS 2개(quad 8개) | quad의 브랜치/복제본으로 보임. `.claude/tools/doc-check.py` 437줄(quad 534줄) |
| devplorer | `devplorer/docs/` | Astro 7 + Starlight 0.42 + `starlight-image-zoom`만. 콘텐츠는 `src/content/docs/{start,windows,integrate}` 직접 작성(sync 없음) | md 약 13 | `astro.config.mjs` 주석이 "quad와 같은 구성을 줄여서 쓴다"고 명시. `dev.sh`, `deploy.sh`, `DEPLOY.md` 모두 quad 것의 포트 변경본(4322) |
| quad-v1 | `quad-v1/docs/{en,kr}` | **MkDocs**(`mkdocs_en.yml`, `mkdocs_kr.yml`, `requirement.txt`) 빌드 결과물(HTML, sitemap, CNAME)만 커밋 | 산출물 | 레거시. 이관 대상 아님(quad v2 문서가 `how-to/08-migrating-from-v1`로 흡수) |
| tbox | `tbox/docs/` | **사이트 없음.** 순수 md 설계 노트 5개(`api-normalization.md`, `hydration-design.md`, `error-path-design.md`, `redesign-precedents.md`, `code-review-2026-10-05.md`) | md 5 | 사용자 문서가 아니라 설계 기록 |
| vitrine | `vitrine/docs/` | **사이트 없음.** md + `api/openapi.json` | md 약 10 | `format.md`는 "문서 포맷"이 아니라 **vitrine blob 바이너리 포맷 명세**(HKDF/ChaCha20-Poly1305, "published contract"). 문서 시스템과 무관 |
| stl-luau | `stl-luau/.claude/base/docs-plan.md` | **미착수 계획서** (132줄) | - | "quad의 docs 구조와 Starlight/sync 구조를 그대로 따르라"는 사용자 결정(2026-09-22) 기록. 즉 4번째 포크가 예약돼 있다 |
| moonwave-luau | `moonwave-luau/` | Moonwave 사이트 **없음**. Moonwave 문서주석(`--[=[ ]=]`)을 순수 Luau로 파싱해 JSON/마크다운을 만드는 라이브러리(4단계 raw/low/middle/high, parser-lua 서브모듈, mrow로 재작성 예정) | - | 잠재적으로 "Luau 소스 주석 -> 레퍼런스 md" 생성기가 될 수 있는 유일한 후보. stl-luau 레퍼런스 페이지 "소스 주석에 이미 다 있다"는 문제(docs-plan 3-1)와 직결 |

### 1.1 도식

```
Starlight 포크 계보(복사 방향)

quad/docs/site  (정본: 플러그인 6, 컴포넌트 2, CSS 8, 스크립트 3, sync 325줄)
   |-- quad-changelog-check/docs/site  (구버전 사본: CSS 2, sync 162줄)
   |-- devplorer/docs                  (축약 사본: 플러그인 1, CSS 3, sync 없음)
   '-- stl-luau (예정, docs-plan.md: "그대로 따르라")

quad/docs/skills/quad-ui-dev  (정본 스킬)  <-- 갈라짐 -->  quad-changelog-check/docs/skills/quad-ui-dev
```

---

## 2. 공통 설정/컴포넌트/플러그인 중복 현황

| 기능 | quad | qcc | devplorer | 중복/비고 |
|---|---|---|---|---|
| Starlight 본체 | 0.42.9 | 구버전 | 0.42 | `package.json` 각자 고정. 공유 preset 없음 |
| Luau 하이라이트 grammar | 기본 Shiki `luau` (커스텀 없음) | 동일 | 동일 | 커스텀 tmLanguage/Shiki 설정 grep 결과 0건(`tmLanguage`, `shiki`, `expressive` 설정 없음). Luau 최신 문법(`const`, `<<T>>` 등)은 기본 grammar에서 깨질 수 있음 - 미검증 |
| 인터랙티브 플레이그라운드 | 없음 | 없음 | 없음 | 구현된 곳 없음 |
| 코드블록 실행/검증 | `scripts/doc-snippets.py` | **없음**(`scripts/`에 없음) | 없음 | quad 단독 |
| include/transclusion | **계획만**(`quad/.claude/research/doc-include-plan.md`, 118줄, 단방향 생성 파일럿 설계) | 계획서 사본만 | 없음 | 미구현. 설계 결론: Python stdlib 100줄, `--write`/`--check` |
| md -> 사이트 변환 | `sync-docs.py` 325줄(상대링크 치환, GitHub alert -> Starlight aside, `<picture>` -> light/dark, ` ```quiz ` 펜스 -> `<Quiz>` MDX, HTML 주석 제거, 각주 등) | 162줄 구버전 | 불필요(직접 작성) | **가장 큰 자산이자 가장 큰 기술부채**. quad 전용 TRACKS 하드코딩(`['overview','getting-started','how-to','quadnomicon','reference','agents']`)과 `watch-docs.py`의 TRACKS는 이미 불일치(agents 누락) |
| sidebar topics | `starlight-sidebar-topics` | 없음 | 없음 | |
| mermaid | `astro-mermaid` + `mermaid-zoom.js` + `check-mermaid.mjs` | 있음(zoom 스크립트는 없음) | 없음 | |
| changelog 페이지 | `starlight-changelogs` + CHANGELOG.md 헤딩 파싱 | 일부 | 없음 | |
| 퀴즈 | `starlight-quiz` | 없음 | 없음 | |
| 각주 팝오버/모바일 스와이프 | `public/scripts/*.js` 자체 구현 | 없음 | 없음 | 일반화 가능한 Starlight 컴포넌트 |
| `.md.txt` 노출(에이전트용) | `starlight-md-txt` | 없음 | 없음 | llms.txt와 다름. 페이지별 원문 노출 |
| image zoom | 있음 | 있음 | 있음 | 3곳 동일 |
| dev/deploy 스크립트 | `dev.sh`, `deploy.sh`, `DEPLOY.md`, `wrangler.toml` | 동일 | 동일(이름/포트만 변경) | 3곳 복붙 |
| 문서 코퍼스 감사기 `doc-check.py` | 534줄 | 437줄 | stl-luau 214줄(다른 검사 항목) | **3개의 서로 다른 구현**(md5 전부 상이). 검사 항목은 프로젝트별 규칙(`QuadNNNN`, `spikes/NN`, `perf N절`)이 섞여 있음 |
| `doc-coverage.py` | 143줄(공개 표면 심볼 vs 레퍼런스 헤딩) | 5.8KB 구버전 | 없음 | quad 전용 |
| 에이전트 위임 스킬 `delegate-agy` + `agy-delegate.sh` | 있음 | - | - | quad, stl-luau, tbox(+table-sim)에 **각자 사본, md5 모두 상이** |
| Roblox 타입 정의 `globalTypes.d.luau` | `scripts/roblox-defs/` | 동일 md5 | `devplorer/typedefs/` | tbox는 `typedefs/roblox/globalTypes.None.d.luau`. 4곳 복제. quad/qcc는 md5 동일 |

### 2.1 판정

- **중복 구현은 사실이다.** 특히 (a) Starlight 설정+스크립트 3벌, (b) `doc-check.py` 3벌, (c) `delegate-agy` 4벌, (d) Roblox defs 복제 4곳.
- 그러나 "정본화" 가치가 가장 높은 것은 (1) 스니펫 검증기 골격, (2) sync-docs 변환 규칙, (3) Starlight preset이고, `doc-check.py`는 프로젝트 특화 규칙 비중이 커서 **일반 골격만** 추출해야 한다.

---

## 3. 에이전트용 문서/지식 현황

```
quad/docs/
|-- agents/01-quad-ui-dev-skill.md     사람용 한국어 페이지: "스킬 quad-ui-dev 설치와 사용"
|                                       (Claude Code 설치법, 다른 에이전트에 붙이는 법, 갱신)
|-- skills/quad-ui-dev/                에이전트용 정본 스킬 (영문, 토큰 절약 목적)
|   |-- SKILL.md  (41KB, frontmatter name/description)
|   '-- references/{code-recipes,rules-and-invariants,v1-migration}.md
'-- site/ (starlight-md-txt가 각 페이지를 <slug>.md.txt로 노출)
```

| 질문 | 답 | 근거 |
|---|---|---|
| `agents/`는 Claude 관련인가 | **예.** 단 "에이전트가 읽는 문서"가 아니라 "에이전트 스킬을 쓰려는 사람이 읽는 문서" | `quad/docs/agents/01-quad-ui-dev-skill.md` |
| 사이트의 Agents 토픽 | 있음(`sidebar-topics`의 'Agents (에이전트)' 배지 AI). 스킬 본문은 사이트에 싣지 않고 레포 링크로 둠(사용자 결정 2026-09-21, docs-review 3-7) | `quad/docs/site/astro.config.mjs` |
| llms.txt / llms-full.txt | **없음**(생성 설정 없음). 대신 `starlight-md-txt`의 `.md.txt` | astro.config, find 결과 |
| 스킬 배포 방식 | `git clone --branch <tag>` 후 폴더 복사(수동). 플러그인/마켓플레이스 미사용 | agents/01 페이지 2절 |
| 스킬과 사람용 문서의 단일 원천 | **아님.** 스킬은 사이트의 "압축 요약"이며 수기 유지. SKILL.md가 "없는 것은 사이트 페이지를 가져와라, 심볼은 지어내지 말고 grep하라"고 지시 | SKILL.md 본문 |
| 사본 드리프트 | quad vs qcc: SKILL.md + references 3개 모두 상이 | `diff -rq` |
| `.claude/agents/` | `quad-doc-auditor.md`, `quad-site-tester.md`(문서/사이트 감사 서브에이전트, 읽기 전용). `devplorer/tools/agent/SKILL.md`는 별도 목적의 스킬(`devplorer-agent`, 라이브 서버 읽기) | 각 경로 |
| Gemini/Codex 호환 | stl-luau에 `GEMINI.md`, 각 프로젝트 `CLAUDE.md`. `AGENTS.md`는 refs의 외부 레포에만 존재. quad는 `delegate-agy`로 Gemini를 *위임 대상*으로 사용 | 파일 목록 |

**결론:** 에이전트 지식의 원천이 (1) 사이트 md(사람용), (2) 수기 SKILL.md, (3) `.claude/` 코퍼스(내부 설계) 세 갈래이고, 이를 잇는 생성 파이프라인은 없다. quad의 `doc-include-plan.md`와 `rfc-docs-section-plan.md`는 이 문제를 각각 "단방향 생성기"와 ".claude를 사이트로 노출"로 부분적으로 다룬 계획 단계 문서이며 둘 다 미구현이다.

---

## 4. 스니펫 실행/검증 도구

grep 키워드: `doc-check`, `doc-snippets`, `doc-include`, `doc-coverage`, `luau-analyze`. (프로젝트 루트 기준, archive/session/audit/node_modules/dist 제외)

| 도구 | 위치 | 기능 | 재사용성 |
|---|---|---|---|
| **doc-snippets.py** | `quad/scripts/doc-snippets.py` (+ `doc-snippets-runshim.luau`) | docs의 ```luau 펜스를 추출. 펜스 정보 문자열로 `continue`/`skip`/`no-run`/`error=QuadNNNN` 표시. getting-started는 parse+mock 실행, how-to/reference는 **신솔버 strict 타입체크** + mock 실행. 줄 끝 `-- 타입 에러` 주석 줄에 진단이 반드시 나야 통과. 대조군 3개(체커 고장 감지). `test.sh`가 매번 실행(`quad/scripts/test.sh` 87-89행). 작업 폴더 `.doc-snippets/` | **중간.** 일반 골격(펜스 파싱, 체이닝, 표시 어휘, 대조군)은 재사용 가능. 하드코딩된 것: `TRACKS`, `q`=quad 셋업 모듈, `QuadTypes`/`RobloxModule`, mock 백엔드, `QuadNNNN`, `-- 새 파일:` 모듈 등록 관례, `scripts/roblox-defs` 경로 |
| doc-check.py (quad) | `quad/.claude/tools/doc-check.py` | .claude 코퍼스 깨진 파일/절 참조, 마크다운 링크, ```luau 펜스 표시 어휘 검증(3-2), 색인 누락 | 낮음(quad 규약 의존). 펜스 어휘 검사 일부만 일반화 가능 |
| doc-check.py (stl-luau) | `stl-luau/.claude/tools/doc-check.py` | 파일/스파이크/질문/perf 절 참조 | 낮음 |
| doc-coverage.py | `quad/scripts/doc-coverage.py` | 공개 표면 심볼 vs 레퍼런스 헤딩 | 낮음(quad 심볼 모델) |
| check-mermaid.mjs | `quad/docs/site/check-mermaid.mjs` | mermaid 블록 검증(puppeteer-core, jsdom) | 높음(언어 무관) |
| luau-analyze/lune 직접 호출 | stl-luau는 **luau + luau-analyze만**(lune 의도적 배제, `stl-luau/mise.toml`), tbox는 luau 0.734 + lute 1.0.0 + luau-lsp 1.69.0(`mise run analyze`) | 소스 검증용. 문서 스니펫 용도 아님 | 툴체인 선택이 프로젝트마다 다름(lune/lute/luau-only). **공유 러너는 런타임 어댑터를 가져야 함** |
| doc-include | **없음**(계획서만) | - | - |
| 일반 `luau-test`/snippet 러너 | `quad/.claude/luau-test/`(스파이크 상태 폴더, 스니펫 러너 아님) | - | - |

### 4.1 재사용 설계 메모

일반화 시 인터페이스(제안):

```
snippet-check.py --root docs/ --track getting-started=run --track reference=strict \
                 --defs <globalTypes.d.luau> --prelude <file> --runtime {luau|lune|lute} \
                 --error-prefix QuadNNNN(옵션)
```

- 추출/표시 어휘/체이닝/대조군은 그대로 이식.
- 프로젝트별 요소(prelude, 모듈 레지스트리 규칙, 런타임 shim)는 설정 파일(`snippets.toml`)로 분리.
- Luau 신솔버 플래그 4개(`LuauSolverV2`, `LuauTarjanChildLimit`, `LuauSubtypingIterationLimit`, `LuauTypeInferIterationLimit`)는 Luau 버전에 종속(quad/stl-luau/tbox가 서로 다른 Luau 버전 0.734/0.742를 고정) -> 정본 저장소에서 "지원 Luau 버전 매트릭스"로 관리해야 한다.

---

## 5. Claude Code 플러그인 포맷 (공식 문서 근거)

출처: https://code.claude.com/docs/en/plugins-reference (manifest reference), https://code.claude.com/docs/en/plugin-marketplaces (2026-11-10 열람).

### 5.1 plugin.json (`.claude-plugin/plugin.json`)

| 항목 | 내용 |
|---|---|
| 필수 | **`name`만 필수.** 매니페스트 자체도 선택(없으면 표준 레이아웃에서 컴포넌트 자동 탐색, 이름은 마켓플레이스 항목/디렉터리명) |
| 권장(없으면 validate 경고) | `version`, `description`, `author{name,email?,url?}` |
| 메타 | `displayName`, `homepage`(URL 파싱 실패 시 로드 실패), `repository`, `license`, `keywords`, `defaultEnabled`, `dependencies`, `metadata`, `userConfig`, `settings`(`agent`/`subagentStatusLine`만 유효) |
| 컴포넌트 경로 | `skills`(디렉터리, 기본 `skills/`에 **추가**), `commands`(대체), `agents`(.md 파일만, 디렉터리 불가, 대체), `hooks`(`hooks/hooks.json`과 병합), `mcpServers`(`.mcp.json`과 병합), `lspServers`(`.lsp.json`과 병합), `outputStyles`, `workflows`, `experimental.{themes,monitors,evals}` |
| 경로 규칙 | 모두 `./` 시작, 플러그인 루트 내부, 존재해야 함. `..` 금지 -> **루트 밖 파일(예: 모노레포의 `../docs`) 직접 참조 불가** |
| 변수 | `${CLAUDE_PLUGIN_ROOT}`(버전 설치 경로, 업데이트 시 바뀜), `${CLAUDE_PLUGIN_DATA}`(`~/.claude/plugins/data/<id>/` 업데이트 후 유지), `${CLAUDE_PROJECT_DIR}` |
| 이름 규칙 | kebab-case. 모든 컴포넌트는 `<plugin>:<name>`으로 네임스페이스(예: `/luau-kb:luau-analyze`) |
| **예약어** | `claude-`, `anthropic-`, `anthropics-`, `cc-plugin-` 접두 및 `claude`, `anthropic`, `claude-code`, `claude-mods` 단독은 **validate ERROR**(`claude plugin init`/`tag`도 거부, 로드는 됨). => **`claude-doctor`는 플러그인명으로 부적합**. 마켓플레이스명도 `claude-plugins-official` 등 공식명은 add 시 거부 |
| 기타 | 플러그인 루트의 `CLAUDE.md`는 컨텍스트로 로드되지 않음(validate 경고). 지침은 skill에 넣어야 함. `bin/`은 Bash PATH에 추가(claude.ai/Cowork는 `bin/` 있는 플러그인 설치 불가) |

### 5.2 .lsp.json (또는 manifest `lspServers`)

필수 `command`(공백 불가, 인자는 `args`), `extensionToLanguage`(점 시작 확장자 -> 언어ID, 1개 이상). 선택: `args`, `transport`(stdio 기본, socket 수락하나 실제 stdio), `env`, `initializationOptions`, `settings`, `workspaceFolder`, `startupTimeout`, `shutdownTimeout`, `requestTimeout`(기본 60000ms, v2.1.288+), `restartOnCrash`, `maxRestarts`, `diagnostics`. **알 수 없는 키는 오류로 플러그인 로드 실패(strict).** Luau용 예:

```json
{ "luau": { "command": "luau-lsp", "args": ["lsp", "--definitions=${CLAUDE_PLUGIN_ROOT}/defs/globalTypes.d.luau"],
            "extensionToLanguage": { ".luau": "luau", ".lua": "luau" } } }
```

(luau-lsp 바이너리는 플러그인이 번들하지 않으므로 mise 등으로 사용자가 설치해야 함 - 의존성 문서화 필요. 위 JSON은 필드 규격에 맞춘 예시이며 실제 동작은 미검증.)

### 5.3 marketplace.json (`.claude-plugin/marketplace.json`)

| 항목 | 내용 |
|---|---|
| 필수 최상위 | `name`, `owner{name}`, `plugins[]` (선택: `description`) |
| 플러그인 항목 필수 | `name`, `source` |
| source 종류 | 상대 경로(`./plugins/x`, marketplace 루트 기준, `..` 금지), `github{repo}`, `git-subdir{url,path}`, `url`, `archive`(zip/HTTPS), `npm`, `command`. git 계열은 `ref`/`sha` 고정 가능 |
| strict | 기본 true: plugin.json 있으면 항목의 commands/agents/skills 등이 **추가**되고 hooks는 이벤트별 교체. `strict:false`에서 plugin.json이 있고 항목이 컴포넌트를 선언하면 충돌로 로드 실패 |
| 이름 | 항목 `name`과 plugin.json `name`을 **동일하게** 유지(다르면 `Plugin "x" not found`) |
| 설치 | `claude plugin marketplace add <owner/repo|URL|./path>` -> `claude plugin install <name>@<marketplace>`. 검증: `claude plugin validate ./dir [--strict]` |
| 로컬 개발 | 로컬 경로 마켓플레이스는 파일을 직접 읽어 `/reload-plugins`로 반영(버전 변경 불필요). 호스팅 설치본은 캐시 사본 |
| 버전 | plugin.json `version`을 설정하면 그 값에 **고정**(올리기 전까지 업데이트 안 됨) |
| 팀 강제 | org 문서(`plugins/org`)상 관리자가 마켓플레이스를 모든 머신에 요구 가능; 프로젝트 `settings.json`의 `extraKnownMarketplaces`/`enabledPlugins`는 이 감사에서 미확인 |
| 서브모듈 | 마켓플레이스 루트가 곧 플러그인이면 모든 서브모듈을 clone할 수 있음 -> 플러그인은 하위 디렉터리에 둘 것(v2.1.295+) |

### 5.4 이 포맷이 설계에 주는 제약

1. **플러그인은 캐시로 복사된다.** 루트 밖 상대경로, 형제 디렉터리 심볼릭 링크에 기대면 깨질 수 있다(심볼릭 링크 처리는 문서에서 확인 못 함 - 미검증). 스니펫/defs는 플러그인 디렉터리 **안**에 두거나 마켓플레이스 항목의 source를 `git-subdir`로 지정해야 한다.
2. 플러그인 스킬은 `luau-kb:<skill>` 네임스페이스가 붙는다. 프로젝트 `.claude/skills/<x>`(네임스페이스 없음)와 호출명이 달라진다.
3. `CLAUDE.md`/`AGENTS.md`는 플러그인으로 전달되지 않는다 -> **항상 로드되는 컨텍스트**는 플러그인으로 줄 수 없고, 스킬(온디맨드) 또는 프로젝트 쪽 `@import`로만 가능.
4. Claude Code 전용 포맷이다. Gemini(agy)/Codex는 플러그인을 읽지 않는다. 이들에게는 `AGENTS.md`/`GEMINI.md` + 평문 md 참조로 전달해야 한다.

---

## 6. 정본 저장소 후보 구조

### 6.1 원칙

- **원천은 평문 md 하나**(사람용 사이트와 에이전트 스킬이 공유), Claude Code 플러그인은 *배포 어댑터*일 뿐.
- 실행 가능한 스니펫을 CI로 검증해 "문서가 거짓말하지 않는" 정본을 만든다.
- 프로젝트 고유 지식(quad의 Source/State, stl-luau의 컨테이너 계약)은 각 프로젝트에 **남긴다**. 정본은 "Luau 언어/도구/Roblox 공통"만.

### 6.2 제안 트리 (`luau-kb`)

```
luau-kb/                                   (git 저장소 1개, 이름은 claude- 접두 회피)
|-- .claude-plugin/
|   '-- marketplace.json                   name=luau-kb-market, owner, plugins[] (상대경로 ./plugins/*)
|-- plugins/
|   |-- luau-kb/                           * 플러그인 1: 지식+도구
|   |   |-- .claude-plugin/plugin.json     name, version, description, author
|   |   |-- skills/
|   |   |   |-- luau-typing/SKILL.md       (신솔버/제네릭/타입 함수 한계 - stl-luau/quad typing-limits에서 승격)
|   |   |   |-- luau-testing/SKILL.md      (luau/lune/lute 선택, mise 고정, analyze 플래그)
|   |   |   '-- roblox-luau-conventions/SKILL.md
|   |   |-- agents/doc-auditor.md          (quad-doc-auditor 일반화)
|   |   |-- hooks/hooks.json               (예: Luau 편집 후 luau-analyze, heavy-proc-guard 이식)
|   |   |-- .lsp.json                      (luau-lsp + defs)
|   |   |-- defs/globalTypes.d.luau        (4곳 복제 -> 1곳, 버전 태그)
|   |   '-- bin/snippet-check              (PATH에 노출되는 러너 래퍼)
|   '-- luau-docs-kit/                     * 플러그인 2(선택): 문서 작성 보조 skill (펜스 표시 어휘 규약 등)
|-- snippets/                              실행 가능 정본(CI 대상)
|   |-- *.luau  + snippets.toml            (표시: continue/skip/no-run/error=)
|   '-- tests/                             대조군(고장 감지)
|-- tools/
|   |-- snippet-check.py                   doc-snippets.py 일반화(런타임 어댑터 luau|lune|lute)
|   |-- sync-docs.py                       quad 325줄 일반화(트랙은 설정)
|   '-- skill-export.py                    docs md -> SKILL.md/references 조립(7절)
|-- site/                                  Starlight preset (npm 패키지 또는 template)
|   |-- preset/ (astro.config 팩토리, 컴포넌트, CSS 8, 스크립트 3)
|   '-- docs/ (Luau 공통 문서: 언어 함정, 도구 체인, Roblox 연동)
|-- AGENTS.md  (+ GEMINI.md 심볼릭/포워더)  타 에이전트용 진입점: 평문 md 경로 안내
|-- .github/workflows/ (또는 mise task)    validate(plugin/marketplace --strict) + snippet-check + site build
'-- CHANGELOG.md / version matrix          지원 Luau 버전 표 (0.734, 0.742 ...)
```

소비 방식:

```
각 프로젝트(quad, stl-luau, tbox, devplorer, ...)
  |- Claude Code:  claude plugin marketplace add <git url>  ->  install luau-kb@luau-kb-market
  |                 (프로젝트 .claude/settings.json에 enabledPlugins 선언)
  |- Gemini/Codex: AGENTS.md / GEMINI.md 에서 luau-kb의 평문 md 경로를 @import 또는 링크
  |                 (플러그인 비의존 = 같은 skills/*.md를 직접 읽음)
  '- 문서 사이트:  site preset을 npm/git 의존성으로 import, 프로젝트 docs/는 자기 것 유지
```

---

## 7. 사람용 문서 + 에이전트 스킬의 단일 원천화

```
docs/<track>/*.md  (정본, frontmatter title/description)
       |-- sync-docs  --> Starlight 사이트          (사람)
       |-- starlight-md-txt --> <slug>.md.txt       (에이전트가 웹에서 가져옴)
       |-- llms.txt 생성(신규, 목차+요약)            (에이전트 크롤)
       '-- skill-export --> skills/<name>/references/*.md  (복사/발췌: 마커 구간 include)
                            SKILL.md 는 수기 유지(압축 규칙 + "정본은 사이트" 포인터)
```

- 이미 계획된 `doc-include-plan.md`의 단방향 생성기(원본 마커 구간 -> 생성 파일, `--check`로 어긋나면 실패)를 `skill-export.py`의 엔진으로 삼는다. 스킬의 references/rules-and-invariants.md(에러 문자열 -> 처방)는 `reference/errors/`에서 생성 가능하다(문서에 이미 `QuadNNNN` 표가 있음).
- SKILL.md 본문(41KB)은 압축 요약이라 자동 생성보다 **CI의 stale 검사**(참조된 심볼이 reference에 있는가 - `doc-coverage` 일반화)가 현실적이다.

---

## 8. 대안 비교와 추천

### 대안 A. 현상 유지 + 점진 복붙 (stl-luau도 quad 포크)

- 장점: 즉시 가능, 기존 `docs-plan.md` 결정과 일치. 프로젝트 간 결합 없음.
- 단점: 포크 4벌 -> 드리프트 가속(이미 qcc/devplorer가 뒤처짐), 스니펫 검증기는 quad만 보유, 스킬 사본 갈라짐, 신솔버 플래그/Luau 버전 변경 시 N곳 수정.
- 위험: 낮음(단기) / 부채: 높음(장기).

### 대안 B. 별도 `luau-kb` 저장소 = marketplace + plugin + 스니펫 CI + Starlight preset (6.2 구조)

- 장점: 단일 원천(defs, 러너, preset, 스킬), CI로 스니펫 정본 보증, `claude plugin install` 한 번으로 소비, 버전 고정(`version`)으로 재현성, 평문 md 병행으로 Gemini/Codex도 소비.
- 단점: 새 저장소 유지비, Claude 플러그인은 캐시 복사라 프로젝트별 오버라이드/실험이 번거로움, 버전 고정 때문에 "올리기 전 업데이트 안 됨" 운영 규율 필요, 프로젝트 고유 지식 경계 설정 비용, `bin/` 포함 시 claude.ai/Cowork 미지원.
- 위험: (1) 동기화/버전 - Luau 버전 매트릭스, defs 버전 태그 필요. (2) 플러그인은 `CLAUDE.md` 컨텍스트를 못 줌 -> 항상 로드되는 규칙은 프로젝트 `CLAUDE.md`에 남아야 함. (3) 네임스페이스 변경으로 기존 `/delegate-agy` 호출명이 `/luau-kb:delegate-agy`로 바뀜. (4) 스킬 설명(description) 품질이 트리거를 좌우.

### 대안 C. `claude-doctor`(현재 작업 디렉터리)를 자체 marketplace로 확장

- 장점: 이미 존재하는 감사 허브를 재사용, 새 저장소 없음.
- 단점: **이름 문제** - 플러그인명 `claude-doctor`는 예약 접두(`claude-`)로 validate ERROR. 마켓플레이스명으로도 `claude-` 접두는 공식 사칭 경고 가능성(공식 예약명 목록은 정확히 일치한 이름만 거부하나 정책상 회피 권장). 또 감사/진단 도구와 Luau 정본이 한 저장소에서 목적이 섞임.
- 위험: 이름 변경 시 전체 참조 수정.

### 추천: **대안 B를 단계적으로** (단, 이름은 `luau-kb` 등 비예약어)

마이그레이션 단계:

| 단계 | 작업 | 산출/검증 | 근거 |
|---|---|---|---|
| 0 | 이름 결정(`luau-kb`), 저장소 생성, `claude plugin validate --strict` CI | 빈 플러그인 + marketplace 통과 | 5.1 예약어 |
| 1 | **defs 일원화**: `globalTypes.d.luau` 4곳 -> `defs/` + 버전 태그 | 각 프로젝트 `relink.sh`/`mise` 경로 갱신 | md5: quad=qcc 동일, tbox/devplorer 별도 |
| 2 | **snippet-check 추출**: `quad/scripts/doc-snippets.py` 일반화(설정 분리, 런타임 어댑터). quad가 첫 소비자로 회귀 확인(현 `test.sh` 통과 유지) | quad 대조군 통과, stl-luau에서 2번째 적용 | 4절 |
| 3 | **스킬 승격**: `delegate-agy`(4벌 -> 1), `luau-typing`/`luau-testing`은 stl-luau/quad `base/typing-limits.md` 등에서 발췌. quad-ui-dev는 **quad에 남김**(프로젝트 고유) 단 같은 export 파이프라인 사용 | 플러그인 설치로 호출 확인 | 3절 |
| 4 | **Starlight preset 추출**: quad site의 설정/컴포넌트/CSS/스크립트 -> preset. qcc/devplorer는 preset 소비로 교체, stl-luau 사이트는 처음부터 preset 사용 | 3사이트 빌드 동등성(`check-mermaid` 포함) | 2절 |
| 5 | **llms.txt + skill-export** (doc-include 설계 구현) | `--check` CI | 7절 |
| 6 | **AGENTS.md/GEMINI.md 포워더**, `.lsp.json`, hooks 추가 | Gemini/Codex가 평문 md로 소비 가능 확인 | 5.4 |
| 7 | 프로젝트 `.claude/settings.json`에 `enabledPlugins` 선언, 옛 사본 삭제 | 사본 0 확인(md5 목록 감사) | - |

핵심 위험과 완화:

| 위험 | 완화 |
|---|---|
| 동기화/버전 드리프트 | plugin.json `version` 고정 + CHANGELOG + Luau 버전 매트릭스; 소비 프로젝트는 태그 핀(`git` source `ref`/`sha`) |
| Luau 버전별 솔버 거동 차이(0.734 vs 0.742, quad 실측 한계) | 스니펫 CI를 매트릭스로 실행, 프로젝트는 자기 mise 버전을 설정으로 전달 |
| 타 에이전트(agy/Codex) 비호환 | 정본은 평문 md. 플러그인은 Claude 전용 어댑터. 루트 AGENTS.md가 경로 안내 |
| 정본 vs 프로젝트 지식 경계 | "Luau/Roblox 일반"만 승격, 프로젝트 고유 규칙(`QuadNNNN` 등)은 프로젝트에 둠 |
| 플러그인 루트 밖 참조 불가/심볼릭 링크 불확실 | 플러그인 디렉터리 내부에 자급(defs/tools 포함) 또는 `git-subdir` source |
| `luau-lsp` 등 외부 바이너리 | 플러그인이 번들하지 않음 -> mise 설치 안내를 스킬/README에 명시 |
| 스킬 트리거 품질 | description 작성 규칙을 별도 skill로 문서화, `claude plugin eval`(docs에 존재) 활용 검토 - 미검증 |

### 즉시 실행 가능한 저비용 항목(대안 B 비의존)

1. qcc의 스킬/문서 사본을 quad와 diff하여 "어느 쪽이 최신인가" 결정(현재 4개 파일 상이).
2. `quad/docs/site/watch-docs.py`의 TRACKS에 `agents` 누락 수정은 quad 소관이므로 보고만(읽기 전용 감사라 수정 안 함).
3. stl-luau 문서 착수 전에 4단계(preset)를 먼저 하면 5번째 포크를 막을 수 있다.

---

## 부록. 감사 한계

- 읽기 전용: 코드를 실행하지 않았다(doc-snippets, 빌드 미실행). 줄 수/해시/diff는 정적 확인.
- Shiki 내장 `luau` 언어 사용 여부는 설정 부재로 추정(Starlight 기본 Expressive Code). 최신 Luau 문법 렌더링 오류는 미검증.
- 플러그인 심볼릭 링크 처리, `extraKnownMarketplaces` 세부는 공식 문서 해당 페이지를 직접 열지 못해 미확인.
- `quad/docs` 파일 948 중 상당수는 `site/dist`, `site/node_modules`, `.astro` 산출물로 추정(열람하지 않음).
- `claude plugin eval`/`org` 관련은 plugins-reference 본문의 링크만 확인.
