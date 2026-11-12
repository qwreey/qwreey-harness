# 47. coderag 코드 품질: 하드코딩, 중복, 바퀴의 재발명, 단순화 실패, 그리고 관례·훅 설계 입력

> Snapshot 2026-11-12. coderag 7861ce8 에서 읽기 시작했고 검토 중 a4b518e 와 작업 트리 수정(다른 세션이 문구·작은 결함 수정 중)이 들어왔다. 위치는 파일 + 함수 이름으로 적는다(줄 번호는 움직인다). 읽기 전용이고 coderag `target/` 에 빌드하지 않았다. 크레이트 비용은 /tmp 의 빈 바이너리 probe(release, 4코어, 의존성 포함 cold build)로 쟀다. 측정 스크립트와 출력은 `raw/`.

## 결론
- 사용자 짐작은 절반이 맞다. 어지러움의 주원인은 "std 만 써서"가 아니라 **같은 일을 하는 작은 구현이 여러 벌**이라는 점이다. 직접 짠 파서·알고리즘은 대부분 이유가 있고(크기, 훅 기동, Claude Code·참조 구현과의 의미 일치, 캐시 결정성), 크레이트로 바꿔야 할 곳은 core 에 없다. 예외는 앞으로 만들 Luau 심볼 프로바이더(`full-moon`)다.
- 중복 묶음 10개를 찾았다. 그중 둘은 이미 **동작이 갈라졌다**: 시점 기록 판정(`DocRec::is_record` 와 `stale::historical`)과 펜스 안 제목 판정(mdfm 과 다른 두 곳).
- 하드코딩 중 설정·팩으로 가야 할 것은 넷이다: `coderef::EXCLUDED_DIRS`(Roblox 폴더 포함, 덮어쓰기 없음), `meta::LIFECYCLE`(Roblox 단계), `version::tool_of`(Roblox 도구 이름), `rules::SKIP_DIRS`(claude-doctor 훅의 사본인데 출처·대조 시험 없음). 나머지 const 는 형식·명세의 불변식이거나 이미 `DEFAULT_*` + 설정 덮어쓰기다.
- 기계 검사로 가장 쓸 만한 것은 **문자열 묶음 중복**(정밀도 약 90%, coderag 에서 23쌍이 5묶음)이다. 함수 길이·문자열 분기·"바퀴 재발명" 은 정밀도가 낮아 규칙(rule)과 검토의 몫으로 둔다.

## 1. 저장소가 밝힌 제약과 지금도 맞는지
| 밝힌 것 | 어디 | 지금 |
|---|---|---|
| "본체는 Rust 단일 정적 바이너리" | `CLAUDE.md`, `tech-design.md` §0 | 단일은 맞고 정적은 아니다. `target/release/coderag` 은 glibc 동적 링크, strip 안 됨 4.74 MB(strip 하면 3.67 MB). `[profile.release]` 없음. |
| `coderag-mdfm` "의존성 없음" | mdfm `Cargo.toml`, §0, §11.4 | 사실이지만 이유가 적혀 있지 않다. mdfm 을 쓰는 쪽(core, 프로바이더)은 이미 serde_json·toml(toml_edit+winnow)·clap 을 싣고 바이너리 의존성 50개다. "의존성 0" 은 바이너리 수준의 제약이 아니다. |
| glob 을 정규식 크레이트 없이: "훅은 파일을 열 때마다 뜨므로" | `rules/glob.rs` 머리 | 기동 비용 이유는 약하다(크기보다 프로세스 생성이 지배). 진짜 이유는 같은 줄의 "참조 구현(rules_inject.py)과 의미가 같아야" 쪽이고 그것은 유효하다. |
| 프로바이더 분리(불변식 1) | `CLAUDE.md` | 유효. 무거운 파서(swc, 앞으로 full-moon)를 프로바이더에 두면 core 크기·빌드에 안 닿는다. |
| "기록 판정은 `records::classify` 한 곳" | `CLAUDE.md` 현재 상태 | 깨졌다(2.1 의 C5). |
| 캐시는 텍스트·결정적(불변식 5) | `CLAUDE.md` | 유효. 블룸·해시를 크레이트로 바꾸지 않는 이유가 된다. |

## 2. 찾은 것

### 2.1 중복 묶음 (남길 쪽 → 흡수할 쪽)
| # | 묶음 | 위치 | 남길 쪽 |
|---|---|---|---|
| C1 | 제외 폴더 목록 | `mdfm::DEFAULT_EXCLUDES`, `coderef::EXCLUDED_DIRS`+`coderef::excluded`(`_packages`·`Packages`), `rules::SKIP_DIRS`, (기록 아닌 폴더 `records::NON_RECORD_DIRS` 는 뜻이 달라 별개) | 걷기 모듈 하나의 `DEFAULT_SKIP_DIRS` + 설정. `rules::SKIP_DIRS` 는 사본으로 남기되 출처·대조 시험 |
| C2 | 디렉터리 걷기 | `mdfm::walk_dir`, `coderef::walk`(+`git ls-files`), `cache::list_modules_at` 안의 `walk`, `rules::load_rules`(한 단계) | `coderef::list_files` 방식(git 우선, 없으면 걷기)을 공용으로. `walk_markdown` 은 그 위의 필터 |
| C3 | frontmatter 읽기 | `mdfm::split_frontmatter`, `rules::parse_rule`(자체 `---` 분리와 `paths:` 목록 해석), `coderef::parse_headings` 머리의 `---` 건너뛰기 | mdfm. `split_inline_list` 에 중괄호 깊이를 더하면 `parse_rule` 이 흡수된다 |
| C4 | 제목·펜스 훑기 | `mdfm::fence_mask`+`heading`, `coderef::parse_headings`, `ledger::describe` | mdfm(펜스 길이 규칙이 맞는 유일한 구현) |
| C5 | 시점 기록 판정 | `DocRec::is_record`(첫 경로 조각, `sessions` 포함), `stale::historical`(아무 조각, `archive`·`session`·`sessions` 만), `records::Scope::folder_kind`(복수형 `sessions` 만), `mdfm::kind_from_path`(복수형 전부) | `records` 한 곳 + 폴더→kind 표 하나 |
| C6 | 상태·근거 어휘 | `mdfm::KNOWN_STATUS` = `meta::DOC_STATUS`, `mdfm::EVIDENCE_STATUS` = `meta::EVIDENCE`, 닫힌 상태 목록이 `ParsedDoc::listed`·`coderef` `check_ptr` 근처·`hook.rs` 상태 검사에 문자열로 셋 | mdfm const + `StatusSpec::is_closed()` |
| C7 | FNV-1a | `mdfm::fnv1a`, `cache::simple_hash`(같은 코드), `body::fnv`(시드 붙은 변형) | `mdfm::fnv1a`(블룸용 시드 변형은 둘 수 있음) |
| C8 | 토큰 어림·글자 분류 | `mdfm::stats_of`, `levels::estimate_output`, `render::truncate_tokens` 안의 `cost`, `budget::estimate` 가 `'\u{AC00}'..='\u{D7A3}'` 분류를 세 번 반복 | mdfm 에 `char_class(c)` 하나, 나머지는 계수만 곱함 |
| C9 | 프로젝트 설정 찾기 | `config::discover`, `records::Scope::for_claude_root`, `rules::project_config`·`global_config`(`layer::global_layer` 와 겹침) | `config` 에 `find_project_config(dir)` 하나 |
| C10 | Rust 프로바이더 뼈대 | `typescript-swc`·`jsdoc`·`markdown-frontmatter` 의 `main`·`ready`·`handle_dump`(토큰 유사도 0.68-1.00) | `coderag-proto` 에 `serve(handler)` |

C4 의 갈라짐(코드 읽기로 확인, 실행 안 함): `coderef::parse_headings` 와 `ledger::describe` 는 펜스를 이렇게 토글한다.
```rust
if tl.starts_with("```") || tl.starts_with("~~~") {
    fence = !fence;
```
네 개짜리 백틱 펜스 안의 ```` ``` ```` 줄에서 닫힌 것으로 보아, 예시 블록 안의 `## 제목` 을 실제 절로 센다. mdfm `fence_mask` 는 `n2 >= n` 과 같은 문자를 요구해 맞게 처리한다. 결과: 코드 주석 속 `§N` 검사가 예시 속 제목으로 통과할 수 있고, rule 원장 설명의 h1 이 어긋날 수 있다.

C5 의 갈라짐: `is_record` 는 `rel` 의 **첫** 조각만 보고 `stale::historical` 은 **모든** 조각에서 `archive|session|sessions` 를 본다. `research/sessions/x.md` 는 stale 에서는 기록(경로 참조 검사 제외), search 에서는 현재 지식(순위 감점 없음)이다.

### 2.2 하드코딩: 판별 기준과 분류
판별 질문: **두 프로젝트(또는 사용자)가 합리적으로 다른 값을 원할 수 있고, 그 값이 프로그램의 정확성이 아니라 대상 저장소의 내용에 대한 판단인가?** 그렇다면 정책이고 설정·데이터 표·팩으로 간다(코드에는 `DEFAULT_*` 기본값만). 아니면(형식 명세, 외부 도구의 고정 사실, 보안 허용 목록, 내부 관리값) const 가 맞다. 둘째 시험: 값에 특정 생태계 이름(Roblox, Wally, pesde)이 들어 있으면 거의 언제나 팩 몫이다.

| const | 판정 | 이유·제안 |
|---|---|---|
| `coderef::EXCLUDED_DIRS`, `coderef::excluded` 의 `_packages`·`Packages` | 정책, 고칠 것 | `.pesde`·`Packages`·`*_packages` 는 Luau 생태계. `[stale.code] exclude` 와 luau-kb 팩 기본값으로. 덮어쓰기 수단 없음 |
| `coderef::MAX_FILE_BYTES` (1 MB) | 기본값으로 | 생성물 크기는 저장소마다 다르다. `DEFAULT_MAX_FILE_BYTES` + 같은 표의 키 하나(qwreey 훅의 `MAX_BYTES` 도 같은 값) |
| `coderef::DOC_EXTS`, `mdfm::REF_EXTS` | 경계 | 무엇을 문서로 볼지는 거의 공통이지만 `d.luau` 가 들어간 `REF_EXTS` 는 생태계 냄새. 설정까지는 불필요, 출처 한 줄 |
| `meta::LIFECYCLE` | 정책, 고칠 것 | `beta-roblox`·`released-roblox` 는 luau-kb 의 사다리. taxonomy.toml 에 `[lifecycle] ladder = [...]`(없으면 지금 8단계)로. 비교·필터 코드는 그대로 |
| `version::tool_of` | 정책 + 단순화 실패 | 10갈래가 전부 항등(`"luau" => "luau"`). `KNOWN_TOOLS.contains` 로 줄이고 목록은 luau-kb 팩의 `[versions.map]` 로 |
| `rules::SKIP_DIRS` | 사본 | claude-doctor `rules_inject.py` `SKIP_DIRS` 와 같은 값. 바꾸지 말고 출처 주석 + 두 값 대조 시험(code-structure 규칙의 "copied file") |
| `mdfm::DEFAULT_EXCLUDES` | 기본값(설정으로 더하기만 됨) | `options.exclude` 로 더할 수 있으나 뺄 수 없다. C1 과 합칠 때 해결 |
| `KNOWN_KINDS`, `KNOWN_STATUS`, `EVIDENCE*`, `KNOWN_META_KEYS`, `SUMMARY_MAX`, `SCHEMA_VERSION`, `PROTOCOL_VERSION` | 불변식 | coderag 형식 명세(`format` 으로 판 관리). 중복만 정리(C6) |
| `NON_RECORD_DIRS`·`NON_RECORD_FILES`, `PATH_KEYS`, `LOCATOR_VERBS`, `comments::LANGS` | 불변식 | Claude Code 배치·도구 입력 키·보안 허용 목록·언어 문법. `LANGS` 는 좋은 데이터 표의 예 |
| `budget::DEFAULT_*`, `levels::DEFAULT_BUDGET`, `taxonomy::DEFAULT_REVIEW_DAYS`, `render::DESC_MAX` | 이미 기본값 | 설정·CLI 로 덮어쓴다. coderag 에서 `DEFAULT_` 접두 const 5개는 모두 덮어쓰기가 실제로 있다 |
| `RENAME_HISTORY: &str = "2000"`, `ledger::CAP` 류, `state::PRUNE_*` | 내부 관리값 | const 맞음. `RENAME_HISTORY` 는 숫자형으로 |

### 2.3 바퀴의 재발명: 크레이트 비용과 권고
probe: 빈 바이너리 strip 340,688 B 에 크레이트 하나를 쓰는 코드를 넣은 증가분(`raw/probe.out`). ignore+globset+pulldown-cmark 를 함께 넣으면 +1.85 MB(따로 합 2.94 MB, regex 를 공유).
| 직접 구현 | 크레이트 | 증가(strip) / cold build / 크레이트 수 | 행동 위험 | 권고 |
|---|---|---|---|---|
| YAML 부분집합 `mdfm::split_frontmatter` (~140줄) | yaml-rust2 (serde_yaml 은 보관됨) | +0.20 MB / 4.2 s / 12 | 엄격 YAML 은 `description: a: b` 를 거부하고 따옴표 없는 `[**/*.{ts,tsx}]` 를 흐름 매핑으로 읽는다. 줄 단위 오류(`L3: …`)가 사라진다 | 유지. 이유를 mdfm 머리에 한 줄 |
| glob `rules/glob.rs` (196줄, 시험 포함) | globset | +1.10 MB / 5.9 s / 9 | 0.4.21 은 중첩 `{}` 를 받는다(probe 로 확인), `literal_separator(true)` 면 `*` 가 `/` 를 안 넘는다. 짝 없는 `{` 는 globset 은 오류, 참조 구현은 닫힌 것으로 본다 | 유지(참조 구현 일치가 이유). ignore 를 들이면 거의 공짜라 그때 재검토 |
| 걷기·제외 C2 | ignore | +1.44 MB / 5.5 s / 16 | `.gitignore` 를 git 프로세스 없이 따른다. 지금 `coderef` 의 `git ls-files` 가 더 정확하다 | 유지, 대신 하나로 합침 |
| 마크다운 훑기 C4 | pulldown-cmark (기본 기능 끔) | +0.40 MB / 3.3 s / 5 | setext 제목·들여쓴 코드·HTML 블록을 맞게 본다. 절 줄 범위·slug 가 바뀌어 캐시 재생성 필요 | 지금은 유지하고 mdfm 하나로 합침. CommonMark 결함 보고가 나오면 채택 |
| 날짜 `project::civil_from_days`·`days_from_civil` (~40줄, 시험 있음) | jiff | +0.23 MB / 3.4 s / 3 | 없음 | 유지 |
| 블룸 `mdfm::body` | bloomfilter·fastbloom | 안 잼 | 해시·직렬화가 판마다 같다는 보장이 없어 불변식 5(결정적 캐시)와 충돌 | 유지 |
| base64·FNV | base64, fnv | 작음 | 없음 | 유지, FNV 는 C7 로 한 벌 |
| 주석 추출 `comments::LANGS` 표 | tree-sitter | 문법마다 C 빌드, 수 MB | 과함 | 유지. 같은 일을 claude-doctor `conventions-check.py` 가 Python 으로 한다(언어 표를 데이터로 공유할 여지) |
| (예정) Luau 심볼 | full_moon (luau) | +0.79 MB / 7.0 s / 23 | StyLua·selene 이 쓰는 표준 파서 | **채택**. 프로바이더 프로세스라 core 에 안 닿는다 |

### 2.4 단순화 실패와 큰 파일
- 비시험 함수 533개 중 60줄 이상 21개, 100줄 이상 7개(`raw/fnlen.txt`). `coderag-cli` `main`: **608줄, 분기 약 208**(하위 명령 전부가 한 `match`, `Get` 갈래만 130줄). `stale::stale_report` 133줄: 서로 독립인 문서별 검사 8가지가 한 반복문에 이어 붙어 있어 검사 함수 표로 나눌 수 있다. `comments::extract`(127, 렉서 상태 기계)와 `typescript-swc` `extract_file`(105, AST 방문)은 길이가 일의 모양이라 그대로 둘 만하다.
- 문자열 분기 8갈래 이상: `version::tool_of`(10, 항등), `mdfm::kind_from_path`(15), `records::Scope::folder_kind`(8), `meta::Meta::from_pairs`(26). 앞의 셋은 표로 갈 것(뒤 둘은 C5 와 같은 표), `from_pairs` 는 필드마다 다른 대입이라 표가 더 나쁘다.
- 800줄 초과(시험 두 배): `mdfm/src/lib.rs` **1,722**(강제 기준 1,500 초과, 예외 표시 없음), `docs/coderef.rs` 1,384, `docs/mod.rs` 1,283, `docs/search.rs` 970, `cli/src/main.rs` 944, `cli/tests/e2e.rs` 918, `rules/tests.rs` 804.
- 작은 것: `cache::now_rfc3339` 는 이름과 달리 `format!("epoch:{secs}")` 를 돌려준다. `rules::excluded` 는 qwreey-conventions 의 `.claude/conventions.json` 을 읽는다(다른 플러그인 설정 파일에 묶임, 의도는 주석에 있음).

## 3. coderag 고칠 순서
| 순서 | 항목 | 바꿀 것 | 비용 | 위험 |
|---|---|---|---|---|
| 1 | mdfm/lib.rs 분리(이동만) | `frontmatter.rs`·`meta_line.rs`·`refs.rs`·`walk.rs`·`lint.rs`·`doc.rs`, lib 는 재내보내기 | S | 낮음 |
| 2 | cli main 분리(이동만) | `cmd/<하위명령>.rs` 하나씩, `main` 은 분기만 | M | 낮음 |
| 3 | coderef.rs·docs/mod.rs 분리(이동만) | `coderef/{refs,targets,files,check}.rs`, `render_get`·`render_toc`·`render_list_line` 을 `docs/render.rs` 또는 `docs/get.rs` 로 | M | 낮음 |
| 4 | 값이 같은 중복 | C6(어휘, `is_closed`), C7(FNV), C8(글자 분류), C10(프로바이더 뼈대), `tool_of` → 목록 | S | 낮음(값 동일, 시험 그대로) |
| 5 | 동작이 갈라진 중복 | C4(mdfm 의 제목·펜스를 export 해 coderef·ledger 가 씀), C5(기록 판정 한 곳, 폴더→kind 표 하나) | M | 중간: search 순위·stale 제외 범위가 바뀜. 바뀌는 문서를 시험으로 못 박고 |
| 6 | C3, C9 | `parse_rule` → `split_frontmatter`(중괄호 인식), 설정 찾기 함수 하나 | M | 중간: rules 주입은 참조 구현과의 대조 시험으로 지킴 |
| 7 | 정책을 설정·팩으로 | C1+`EXCLUDED_DIRS`+`MAX_FILE_BYTES` → 걷기 모듈 + `[stale.code]`, Luau 폴더는 luau-kb 팩 기본값. `LIFECYCLE` → taxonomy `[lifecycle] ladder`, 도구 목록 → luau-kb `[versions.map]` | M | 중간: 설정 키 추가(형식 판은 그대로 가능), 기본값은 지금 값 유지 |
| 8 | `stale_report` 검사 표 | 검사마다 함수, 표를 돌며 모음 | M | 낮음 |
| 9 | 빌드 설정·문서 | `[profile.release] strip = true`(4.74 → 3.67 MB), "정적" → "단일 바이너리(glibc 동적)", mdfm "의존성 없음" 에 이유, `now_rfc3339` 이름, `RENAME_HISTORY` 숫자형 | S | 낮음 |

## 4. qwreey-conventions 설계 입력
지금 플러그인의 모양: 규칙은 짧고 이유가 있고(`rules/*.md`), 훅은 막지 않고 한 줄 info, 추가한 줄만 보며, 기존 문제는 Stop 에서 사용자에게 보고만, 예외는 사유 필수(`@structure-exempt: <사유>`, 사유 아닌 말은 무효), 저장소 설정(`.claude/structure.json`, `.claude/conventions.json`)이 이긴다. 아래도 그 모양을 따른다.

### 4.1 규칙에 적을 것 (code-structure.md `## Data` 아래나 새 `rules/reuse.md`, 영어)
- **Reuse before writing.** Before adding a walker, frontmatter/TOML reader, truncation, hash, glob or date helper, grep the repo for one and extend it. Why: copies drift; in coderag three fence scanners already disagree.
- **Policy vs invariant.** A value two projects could reasonably want different (dir/extension lists, size limits, stage ladders, tool names) lives in config or a data table; code keeps it only as `DEFAULT_*`. Values fixed by a format, spec or correctness stay `const`. Ecosystem names in a list (Roblox, Wally) mean it belongs to a pack.
- **One vocabulary, one place.** Status names, folder kinds and similar sets are defined once and referenced.
- **Hand-written parser or algorithm: say why not the library** in one line at the top (size, startup, semantic parity, determinism). No reason, use the library. `rules/glob.rs` is the model.
- (이미 있음) 사본은 출처를 적고 대조 시험을 둔다. `rules::SKIP_DIRS` 가 이 규칙 위반의 실례다.

### 4.2 기계 검사 후보와 coderag 표본 정밀도
| 검사 | 신호·기준 | coderag 결과 | 정밀도 | 권고 |
|---|---|---|---|---|
| H1 문자열 묶음 중복 | 추가된 줄의 배열 리터럴·`"a" \| "b"` 갈래에서 문자열 3개 이상, 저장소 다른 곳의 묶음과 공통 3개 이상 또는 Jaccard ≥ 0.5 (`raw/litsets.py`) | 23쌍 → C1·C5·C6·비교 연산자·닫힌 상태 5묶음. 오탐은 doc 주석 안 문법(`version.rs` 머리) 2쌍 | 약 90%(쌍), 묶음 단위 5/5 | **켤 만함**(info). 재현율은 낮음(FNV·글자 분류·걷기는 못 잡음) |
| H2 마법 수 중복 | 16진 6자리 이상, 4자리 이상 정수, `\u{..}` 글자가 2개 파일 이상 | FNV 두 상수, 한글 범위 두 끝 = 2묶음 맞음, `2000` 우연 1 | 약 75% | 켤 만함, 정수는 5자리 이상으로 올리면 `2000` 이 빠짐 |
| H3 비슷한 함수 | 식별자 정규화 후 6-토큰 shingle Jaccard (`raw/dupfn.py`) | ≥0.4: 7쌍 중 6 맞음(프로바이더 뼈대 한 묶음), ≥0.22: 35쌍 중 약 10 | 86% / 약 30% | 훅 말고 요청 시 감사 도구. 재현율 1/10 묶음 |
| H4 정책 냄새 const | `const NAME: &[&str]` 3개 이상 | 21개 중 설정 감 3-4 | 15-20% | 끔. 이름 필터(`DIRS\|EXCLUDE\|SKIP\|EXTS\|IGNORE`) 를 걸면 6개 중 3-4(50-67%), H1 이 같은 것을 더 정확히 잡음 |
| H5 문자열 분기 > 8 | `match` 갈래 수 | 4개 중 3 맞음(`from_pairs` 는 오탐). 정규식 탐지는 들여쓰기로 2개를 잘못 셈 | 75% | 규칙 문장으로 충분, 훅은 구문 분석이 필요해 보류 |
| H6 긴 함수 | 비시험 100줄 이상 | 7개 중 확실 2, 경계 3, 오탐 2 | 30-70% | 이번 편집으로 기준을 **넘은** 때만 info, 기존 것은 Stop 보고 |
| H7 바퀴 재발명 | 이름·모양(`parse_*`, `walk`, `glob`, `b64`, `fnv`) | 후보 약 10, 크레이트로 바꿀 것 0 | 약 0% | 훅 금지. 규칙(why-not 한 줄)과 검토로. 기계로는 "직접 짠 파서 파일 머리에 이유 줄이 있나" 존재 검사까지만 |

### 4.3 거짓 긍정 줄이기 전략
- **추가한 줄만**, 그리고 "새로 생긴 중복"만 알린다(H1: 추가된 묶음이 기존 묶음과 겹칠 때). 기존 중복은 Stop 에서 사용자에게 수만 보고(conventions-check 의 "남은 주석 보고" 와 같은 길).
- **신호 겹치기**: H1 은 문자열 3개 이상 + 다른 파일(같은 파일이면 거리 50줄 이상) + 시험·픽스처·doc 주석 제외. `as_str`·`from_str`·`Display` 처럼 짝을 이루는 열거형 변환 함수 안의 묶음은 뺀다(coderag 의 `id::kind_str` ~ `records::as_str` 유형).
- **저장소 자신의 설정으로 확인**: `DEFAULT_` 접두 const 는 덮어쓰기가 있다는 약속으로 보고 H4 에서 뺀다(coderag 5/5 가 실제로 덮어쓰기 있음). 이 접두를 4.1 규칙의 일부로 두면 검사가 규칙을 읽을 수 있게 된다. 값이 `coderag.toml`·`structure.json` 같은 저장소 설정 파일에 이미 있으면 알리지 않는다.
- **예외 문법**: `// @dup-ok: <사유>`(묶음 바로 위 3줄 안) 또는 `.claude/conventions.json` `"dup_allow": [{"path": "<글롭>", "reason": "…"}]`. `@structure-exempt` 처럼 사유 없거나 사유 아닌 말("나중에", "-")은 무효. 사본은 `@copy-of: <저장소/경로>` 로 적으면 H1 대신 "대조 시험이 있나" 를 묻는다.
- **알림이지 차단이 아님**: 모두 `level="info"`, (세션, 파일, 범주)당 한 번. 알림에 겹친 위치 `파일:줄` 을 넣어 모델이 바로 판단하게 한다.
- **켜기 전 표본 재기**: 그림자 모드(알림 없이 `$TMPDIR` 또는 `${CLAUDE_PLUGIN_DATA}/dup-shadow.jsonl` 에만 기록, reply_language 의 `drift.jsonl` 처럼)로 coderag·quad·claude-doctor 훅에서 한 주 돌리고, 사람(또는 sonnet 이상 검토)이 표지를 붙여 정밀도 80% 이상일 때 켠다. 이 감사의 표(4.2)가 첫 표지 집합이다.

## 5. 덧붙임: 하네스 자신의 같은 문제
claude-doctor 훅에도 같은 묶음이 있다. `structure-reminder.py` 와 `conventions-check.py` 의 `SKIP_PARTS`(거의 같은 집합 둘), `rules_inject.py` `SKIP_DIRS`(coderag `rules::SKIP_DIRS` 의 원본). H1 을 만들면 claude-doctor 가 첫 시험장이다. 공용 `lib` 하나로 모으는 것은 플러그인이 서로 독립 설치된다는 제약 때문에 사본 + 대조 시험이 현실적이다.
