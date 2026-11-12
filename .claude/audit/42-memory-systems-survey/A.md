# 42-A. 에이전트 메모리 시스템 정적 조사: Mem0, Letta, Cognee, memU

> Snapshot 2026-11-12. 소스를 읽기만 했다(설치·실행·빌드 없음, `git clone --depth 1` 후 파일 열람). 읽은 커밋: mem0 `f1791daa`, cognee `8853378e` (v1.6.7), memU `fd86e386` (0.11.0-beta.3), letta-code `29a29d56`, letta(main) `8816d3a8`. 동작은 코드 열람으로만 추정했고 실측하지 않았다. 메모리·CPU 수치는 없다.

## 0. 읽은 범위
| 시스템 | 저장소 | 읽은 것 |
|---|---|---|
| Mem0 | github.com/mem0ai/mem0 | `mem0/memory/main.py`·`storage.py`, `utils/scoring.py`, `configs/`, `docs/migration/oss-v2-to-v3.mdx`, `integrations/claude-code-plugin/hooks` |
| Letta | letta-ai/letta main 은 안내문만(12파일). 옛 V1 서버는 `archive` 브랜치인데 `AGENTS.md` 가 비교·복사 목적 사용을 금지해 받지 않았다. 현재 소스인 letta-ai/letta-code(MemFS)를 읽음 | `src/agent/memory-*.ts`, `memory-frontmatter.ts`, `memory-constraints.ts`, `agent/prompts/letta_root_memfs.md`, `skills/builtin/maintaining-*-memory`, `subagents/builtin/reflection-v2.md` |
| Cognee | topoteretes/cognee | `cognee/infrastructure/engine/models/DataPoint.py`, `memory/entries.py`, `modules/migrations/`(README·registry), `modules/conflicts`, `modules/improve`, `modules/retrieval`, `search/types/SearchType.py`, DB 설정 |
| memU | NevaMind-AI/memU | README, `docs/adr/0007`, `database/models.py`, `app/agentic.py`, `app/settings.py`, postgres 마이그레이션 위치, hosts 어댑터 표 |

Letta 의 옛 서버(core/archival/recall 3층, 서버 DB)는 소스를 읽지 못했다. letta-code 시스템 프롬프트가 recall(메시지 기록)을 서버가 자동 저장한다고 적은 것까지만 확인했다. 대화 요약·eviction 은 서버 쪽이라 못 봤다.

## 1. Mem0
1. 데이터 모델. `MemoryItem{id(uuid), memory(텍스트 한 문장), hash(md5), metadata, score, created_at, updated_at}` (`mem0/configs/base.py`). 범위는 `user_id`·`agent_id`·`run_id`(세션)와 질의용 `actor_id`. 벡터 저장소 payload 에 `data, hash, text_lemmatized, expiration_date, attributed_to, role` 등이 함께 들어간다. 프로젝트 개념은 OSS 에서 빠졌다(Platform 만).
2. 계층. 시멘틱·에피소드·절차(`configs/enums.py` MemoryType) 종류 구분만 있고 승격/강등 계층은 없다. 새 알고리즘은 한 번의 LLM 호출로 ADD 만 낸다(UPDATE/DELETE 제거, `docs/migration/oss-v2-to-v3.mdx`). 기존 기억은 중복 확인·`linked_memory_ids` 연결용으로만 프롬프트에 준다(`configs/prompts.py` ADDITIVE_EXTRACTION_PROMPT). 결정 주체는 LLM.
3. 저장. 벡터 저장소(기본 qdrant, 26종 어댑터) + SQLite 이력(`~/.mem0/history.db`, `MEM0_DIR`). 사람이 읽는 파일 없음, git 부적합.
4. 검색. 의미(벡터) + BM25(벡터 저장소의 keyword_search, 표제어 처리) + 엔티티 일치 가산을 더해 `max_possible` 로 나눈다(`utils/scoring.py`, `main.py::_search_vector_store`). `top_k` 기본 20, `threshold` 0.1, rerank 선택. 토큰 예산 개념은 없고 개수로만 제한한다. 표제어·엔티티 추출에 spaCy 모델이 필요하다(`utils/spacy_models.py`).
5. 수명. 중복은 md5 해시 일치로 건너뜀. 모순 해소는 LLM 이 하지 않고 새 기억을 추가하며 이전 기억과 연결한다(덮어쓰지 않음). `expiration_date`(YYYY-MM-DD)가 지난 항목은 검색에서 숨김(`_payload_is_expired`, `show_expired` 로 해제). 수동 `update/delete` 는 `history` 표에 ADD/UPDATE/DELETE 이전·이후 값을 남긴다. 감쇠 없음.
6. 버전. 항목별 스키마 버전 없음. 설정 `version: "v1.1"`(API 출력 형태). 이력 표는 `PRAGMA table_info` 로 열 집합을 비교해 달라지면 이름 바꾸기→새로 만들기→공통 열 복사→삭제 하는 트랜잭션 이전(`memory/storage.py::_migrate_history_table`). 큰 변경(v2→v3)은 코드가 아니라 문서의 중단 변경 표로 안내하고, TS/Python 이 payload 키 이름(`text_lemmatized`/`textLemmatized`)이 달라 한 컬렉션 공유 시 BM25 가 깨진다고 인정한다. 서버는 alembic 6개.
7. 연동. 라이브러리(`Memory`), REST 서버(`server/`, FastAPI+Postgres), `integrations/` 에 claude-code·codex·cursor 등 플러그인과 MCP 서버(`core/mcp_server.py`). Claude Code 플러그인은 SessionStart·UserPromptSubmit·PostToolUse(`.*`, 3초)마다 `python3` 프로세스를 띄운다.
8. 라이선스 Apache-2.0.

## 2. Letta (letta-code 의 MemFS, 현행)
1. 데이터 모델. 항목은 Markdown 파일이다. 루트 `MEMORY.md`(frontmatter 없음, 색인)와 그 밖 파일은 frontmatter `name`·`description` 두 필드뿐(`memory-frontmatter.ts`). 하위 폴더는 자기 `MEMORY.md` 가 있어야 "메모리" 로 인정. ID 는 경로, 범위는 `agent_id` 하나(기기 사이 이동). 에이전트 간 공유 메모리는 별도 git 저장소를 붙이고 떼는 방식(`managing-shared-memory`).
2. 계층(점진 공개의 가장 명시적인 예).
   - recall: 메시지 기록 전체, 서버가 자동 저장, 불변. 부분은 recall 서브에이전트로 검색.
   - core: 루트 `*.md` 가 컴파일되어 매 턴 시스템 프롬프트에 들어감. 합계 65,536자, 파일당 20,000자 상한(`.memfs.config.json`, 훅이 강제).
   - deferred(외부): 하위 폴더. 시스템 프롬프트에는 폴더 경로만 나열하고, 폴더를 열면 그 `MEMORY.md` → 파일별 `description` → 하위 폴더 색인의 첫 문단 순으로 한 층씩 드러난다. 목록은 최근 수정 10개. 깊이 기본 2(`maxDepth`).
   - 이동 결정은 에이전트(LLM)와 규칙. 에이전트가 "매 턴 필요하면 core, 주제가 나올 때만이면 deferred, 트리거가 있는 절차면 skill" 로 분류(`maintaining-deferred-memory` 스킬). 백그라운드 `reflection` 서브에이전트가 compaction 이벤트 또는 N 스텝마다 대화 기록을 읽고 memory 를 고친다(`reflection-v2.md`, `cli/helpers/memory-reminder.ts`). 반영은 커밋 뒤 다음 컴파일에만 일어남.
3. 저장. 로컬 `<storage>/memfs/<agentId>/memory` 가 git 저장소, 서버(Letta Cloud)와 동기화. 사람이 읽을 수 있고 git 이력이 곧 변경 기록. pre-commit 훅이 frontmatter·깊이·글자 수·`readOnlyFiles`·색인 존재를 검증(`memory-constraints.ts`, `memory-git-hooks.ts`). 검증은 바뀐 경로에 얽힌 문제만 막고 예전 위반은 경고로 둔다.
4. 검색. 전용 검색 엔진이 아니라 파일 도구·grep, 색인 따라가기, recall 서브에이전트. 토큰 예산은 core 글자 상한과 `/doctor` 의 프롬프트 크기 경고.
5. 수명. 갱신 = 파일 고쳐 커밋. 모순은 `reflection` 지시("모순은 최신 증거 쪽으로 해소", 일회성 작업 상태는 기록 말 것)와 스킬 문서로 사람이 읽는 규칙에 기댐. 코드 수준 감쇠·만료·supersede 필드 없음. 비밀 저장 금지, 커밋 메시지에 근거를 적는 규약.
6. 버전. 저장소 단위 레이아웃 판별: `MEMORY.md` 가 있으면 `memfs-v2`, 없으면 `memfs-v1`(system/·reference/ 폴더 구조)(`memory-format.ts`). git 디렉터리 안 `letta-memory-layout-policy`(legacy-only / root-marker / shared-memory)가 훅 규칙을 고르고, `MEMORY.md` 가 처음 들어간 커밋 유무로 v2 전환 시점을 판단. 파일별 버전 필드는 없다(frontmatter 는 v2 에서 두 필드로 고정). 일괄 이전 도구는 이번에 찾지 못함.
7. 연동. `letta` CLI/TUI, `letta server`(App Server), 채널(Slack 등), SDK. 서버·클라우드가 중심이고 로컬 백엔드 모드도 있음. 서브에이전트(reflection, recall, memory, init)가 메모리 저장소를 작업 트리로 편집.
8. 라이선스 Apache-2.0(letta, letta-code 모두 LICENSE 헤더 확인).

## 3. Cognee
1. 데이터 모델. `DataPoint{id(uuid4, 또는 identity_fields 로 uuid5), created_at/updated_at(ms), version:int, ontology_uri, topological_rank, metadata{index_fields, identity_fields}}`. 그래프 노드·엣지 + 벡터 컬렉션 `<Type>_<field>`. 범위는 dataset(권한 단위), `node_set` 이름표, 사용자, 세션(`session_id`). 세션 항목은 `QAEntry` 등 판별 유니언(`memory/entries.py`).
2. 계층. 단기: 세션 캐시(Redis 또는 파일/SQL, TTL 이 있어 만료, `infrastructure/session`). 장기: 그래프+벡터. `improve()` 가 세션 항목을 영구 그래프로 연결·정제하는 단계(피드백, 선호도, 증거, 사실 충돌 검토; `modules/improve/stages.py`)이고, 각 단계에 켜짐 조건(gate)과 건너뛴 이유 코드가 있다. API 는 `remember → recall → improve → forget`. 결정 주체는 LLM(cognify 추출) + 규칙(gate, `recall` 의 전략 자동 선택은 규칙 기반이며 LLM 호출 없음).
3. 저장. 기본 SQLite(관계) + LanceDB(벡터) + Ladybug(Kuzu 계열 임베디드 그래프). Postgres/pgvector/Neo4j 도 가능. 파일은 이진 DB 라 사람이 읽기·git 부적합.
4. 검색. `SearchType` 20여 종: CHUNKS, CHUNKS_LEXICAL(BM25 소스 `bm25_retriever.py`), GRAPH_COMPLETION, HYBRID_COMPLETION, TEMPORAL, CYPHER, CODING_RULES, SKILLS 등. 하이브리드는 청크+엔티티 후보를 합치고 `project_external_metadata` 로 보강(`retrieval/hybrid/`). 토큰 예산 전용 로직은 확인 못함.
5. 수명. 노드 `version/updated_at`, `improve` 가 사실 충돌을 "time_varying/fixed" 로 분류해 conflict 엣지를 저장하고 검토→`resolved/unresolved`, 선택된 사실·해소자·이유를 기록(`modules/conflicts/models.py`). 오래된 세션은 `invalidate_sessions_for_deleted_data` 로 무효화, `forget` 으로 삭제, 출처(provenance) 기록. 시간 유효성 구간 필드는 DataPoint 에 없고 TEMPORAL 검색은 시간 추출 기반(세부 미확인).
6. 버전. 가장 성숙. 관계 스키마는 alembic. 그래프·벡터는 별도의 "데이터 이전 체인"(`modules/migrations/`): 데이터베이스(데이터셋 쌍)마다 마지막으로 적용한 slug 를 저장, 시작 시 체인을 앞으로 걷고 단계마다 도장. README 규약: slug 는 추가만·불변, 멱등·빈 저장소에서 즉시 종료, 파생 저장소 먼저 바꾸고 원천(그래프)은 마지막(중단 재시도 안전), 이전 단계가 쓰는 규칙을 `_frozen_*` 로 복사해 고정, 내려가기(`down`)는 선택, `cognee-cli upgrade/downgrade/stamp/history/current`, 레지스트리는 import 시 선형성 검증. `cognee_version` 열은 감사용이고 게이트는 revision 뿐. 이전 8건(`versions/`: id 이름공간 재배정, 출처 열 추가 등).
7. 연동. 라이브러리, FastAPI 서버, `cognee-mcp`(MCP 서버), CLI, 에이전트 데코레이터(`modules/agent_memory`), 원격 `serve()`. 프로세스는 서버/라이브러리 혼합, 의존성이 매우 무겁다(그래프·벡터·LLM·FastAPI, Python 3.10-3.14). 풋프린트 수치는 읽지 않음.
8. 라이선스 Apache-2.0.

## 4. memU (로컬 라이브러리 + 호스트 어댑터, 클라우드 선택)
1. 데이터 모델. `BaseRecord{id(uuid), created_at, updated_at}` 위에 `Resource(url, local_path, caption, embedding, track)`, `RecallFile(name, track, description, embedding, content)`, `RecallFileSegment(recall_file_id, track, text, embedding)`(`database/models.py`). 범위는 사용자 정의 scope 모델(기본 `user_id`, `agent_id`)을 병합(`build_scoped_models`).
2. 계층. ADR 0007 이 L0(원본 resource) → L1(굵은 문서: 메모리 분류 파일, 캡션 문단, skill Markdown) → L2(item: 문서를 쪼갠 검색 단위) 로 정의. L1 이 사람이 읽는 `MEMORY.md`/`INDEX.md`/`SKILL.md` 로 렌더링되고 L2 는 저장소 안에만 존재. 세 개의 독립 라인(chat/workspace/skill). 이동: L0→L1 은 호스트 에이전트(LLM)가 세션 기록을 읽어 쓴다("MemoryService 는 LLM 호출 없음", 판단은 에이전트). L1→L2 쪼개기는 규칙(코드): skill 은 `name+description` 한 조각, memory 는 비어 있지 않은 줄마다 한 조각(제목 제외, 중복 제거)(`_commit_segment_texts_for_file`). 현 코드는 ADR 문서보다 뒤처져 있다고 ADR 이 스스로 밝힘.
3. 저장. 기본 inmemory, 선택 SQLite(`sqlite:///memu.db`) 또는 Postgres(alembic `20260703_0001_initial_schema`), 임베딩 포함. L1 Markdown 파일을 `~/.memu` 쪽에 렌더(경로 `subdir/name.md`, `hosts/bridging/recall_files.py`). 읽기 좋은 파일은 파생물이고 원천은 DB.
4. 검색. `progressive_retrieve`(LLM 없음, 한 번): 질의를 한 번 임베딩해 L2 조각을 상위 `top_k` 로 뽑고, 그 조각이 가리키는 L1 파일로 말아 올린다(파일 점수 = 조각 최대). 호스트 지침 파일이 "답하기 전 `<binary> retrieve` 를 실행하라" 고 시킨다. ADR 은 임베딩+BM25 min-max 융합이라 적었으나 이 커밋의 `progressive_retrieve` 코드는 벡터 유사도만 쓴다(BM25 는 확인 못함).
5. 수명. `commit_results` 가 이름+track 으로 create-or-update. 설명이 바뀔 때만 다시 임베딩, 조각은 줄 단위 차집합으로 사라진 것만 삭제하고 새 것만 임베딩(변하지 않은 줄은 임베딩 유지). 임베딩 실패 시 아무것도 쓰지 않음(재시도 안전). 감쇠·만료·모순 처리 코드는 없고, 에이전트가 "아무것도 안 함/기존 skill 패치/새로 생성" 중 고른다.
6. 버전. 항목별 버전 필드 없음. Postgres 만 alembic. 옛 행은 "기본값으로 backfill" 방식(`track` 기본 "memory" 주석). SQLite 이전 코드는 찾지 못함.
7. 연동. Codex·Claude Code·Cursor·OpenClaw·Hermes 등 호스트별 어댑터 CLI. 기록: 스케줄된 브리징이 세션 로그(JSONL/SQLite)를 잘라 작업 파일을 만들고 에이전트가 쓴 결과를 `commit` 으로 반영. 주입: 호스트 지침 파일(`~/.claude/CLAUDE.md` 등)을 패치해 retrieve 를 시킴(자기 갱신 템플릿 ADR 0013). 데몬은 없고 CLI 호출형. 임베딩 키가 필요(로컬이어도 외부 임베딩 API).
8. 라이선스 Apache-2.0. 클라우드(memu.so)는 별도 서비스, 소스 미확인.

## 5. 한눈 비교
| | 항목 단위 | 계층 | 저장 | 검색 | 버전/이전 |
|---|---|---|---|---|---|
| Mem0 | 한 문장 + 해시 | 없음(종류만) | 벡터DB + SQLite | 벡터+BM25+엔티티 | 문서 안내, 이력표 열 비교 |
| Letta | Markdown 파일(name/description) | core / 색인 따라 deferred / recall | git 저장소 | 색인 탐색, grep | 저장소 단위 v1/v2 판별 |
| Cognee | 그래프 노드 + 버전 | 세션 캐시 → 그래프 | 임베디드 DB 3종 | 20종, 규칙으로 선택 | alembic 식 데이터 이전 체인 |
| memU | L1 문서 + L2 조각 | L0/L1/L2 | DB + 파생 Markdown | 조각 벡터 → 문서로 롤업 | Postgres alembic만 |

## 6. coderag 에 가져올 만한 것
전제(`audit/41-.../synthesis.md`): 로컬·결정적, 사람이 읽는 git 기록, 공유 10GiB cgroup, 비프로그래머 동료, 팩 색인은 프로젝트 사이 공유, 본문은 블룸 필터. 임베딩·LLM 호출 의존 방식은 결정성과 비용 때문에 그대로는 부적합하다.

### 6.1 층별 공개(L0-L1-L2) 를 색인에 넣기 (memU L0/L1/L2, Letta core/deferred)
- 풀 문제: 지금은 active/archived 두 단계라 "항상 알아야 할 것", "주제가 나오면 볼 것", "뒤져야 나오는 상세" 가 한 층이고, 본문 검색 결과가 넓다.
- 안: frontmatter 가 아니라 기존 구조로 도출한다. L0 = 제목+description 한 줄 목록(폴더별 색인 `MEMORY.md` 규약, Letta 방식), L1 = 문서의 절(heading) 목록과 첫 문단, L2 = 본문 조각(이미 블룸 필터 단위인 절). 검색 출력은 L0 로 시작하고 `get` 이 L1→L2 로 내려간다. memU 처럼 L2 가 맞으면 L1(문서)로 말아 올려 보여준다(문서 점수 = 절 최대 점수, 결정적).
- 비용: 색인은 이미 절 단위로 있으면 낮음(출력 형식·`get` 옵션). 폴더 색인 파일을 새로 요구하면 문서 규약이 늘어난다. 훅이 먼저 L0 만 넣는 compact 뒤 가리킴(M6)과 방향이 같다.
- 적합: 높음. 충돌: 결정성 유지됨(순수 구조), 동료 부담은 색인 파일을 자동 생성하면 없음.
- Letta 의 "core 상한(글자 수)·깊이 상한·파일당 상한" 은 훅/doctor 경고로 가져올 만하다(적합 중간): 늘 켜진 스킬 설명 6,456자 같은 실측 문제에 직접 쓸 수 있다.

### 6.2 파일별 형식 버전 + 이전(migration) (Cognee 체인, Letta 레이아웃 판별)
- 풀 문제: frontmatter 규약(title/description/status…)이 바뀔 때 옛 기록의 처리가 지금은 사람 손(또는 lint 경고)이다.
- 안(Cognee 규약을 Markdown 에 맞게 축소): 저장소 단위 `.claude/.format` 같은 한 줄 파일 또는 frontmatter 선택 필드 `format: 2`(없으면 1). 이전 단계는 append-only slug 체인(`0001-status-to-lifecycle` 등)으로 coderag 코어에 내장, 멱등, 결정적 변환이며, `coderag migrate --dry-run` 이 git diff 로 보이게 하고 사람이 검토·커밋. 변환 규칙을 그 시점 복사본에 고정(Cognee `_frozen_*`)해야 나중에 코드가 바뀌어도 이전 결과가 변하지 않는다. 각 저장소가 어느 slug 까지 적용됐는지는 저장소 안 파일에 적어 git 이 상태를 전달(Cognee 는 DB 행이라 다른 점).
- 항목별 버전과 저장소별 버전 중에서는 저장소별+선택적 파일별(`format` 이 없으면 기본)을 권한다. Mem0 는 버전이 없고 문서 안내에 의존해 호환이 깨진다는 부정적 사례(TS/Python 키 이름)이고, Letta 는 파일 존재로 v1/v2 를 추정하는 약식이다.
- 비용: 중간(체인 러너, 테스트, doctor 항목). 적합: 높음(사용자 관심사에 맞음). 충돌: 결정적·git 추적 그대로 유지. 비프로그래머는 `migrate` 한 줄만 실행. 위험: 옛/새 coderag 가 섞여 쓰이면 모르는 slug 를 만난다 → Cognee 처럼 "모르는 slug 면 아무것도 하지 않고 경고".

### 6.3 lint 를 변경된 경로에만 강제 (Letta pre-commit)
- 풀 문제: 규약을 올릴 때 옛 문서 수천 건의 경고가 새 편집을 막는다.
- 안: 새로 쓰거나 고친 파일에서 나온 위반만 오류, 나머지는 경고(`changedPaths`/`warnings` 분리). 이미 post-edit lint 가 시점 기록을 건너뛰고 있으니 이전(6.2)과 함께 두면 자연스럽다.
- 비용 낮음, 적합 높음, 충돌 없음.

### 6.4 만료일과 supersede 감시 (Mem0 `expiration_date`, Cognee conflict)
- 풀 문제: `review_after`·`last_verified` 가 이미 있다. 부족한 것은 기한 넘긴 문서를 검색이 어떻게 보이게 하느냐다.
- 안: `review_after` 가 지난 active 문서를 기본 검색에서 지우지 않고 "검토 기한 지남" 표시만 붙이고 doctor 에 모은다(Mem0 는 숨기지만 우리는 사람이 읽는 기록이라 삭제·숨김은 부적합). Cognee 의 충돌 기록처럼 `superseded_by` 가 가리키는 쪽이 active 가 아니면 doctor 가 경고.
- 비용 낮음, 적합 중간, 충돌: 숨기면 "닫힌 문서는 archive 로 옮김" 규약과 어긋나므로 표시만.

### 6.5 compact 복원 가리킴의 정당화 (Letta 프롬프트 컴파일, memU 주입 지침)
- 풀 문제: M6(앞에서 쓴 지식 가리킴). Letta 는 편집이 "다음 컴파일에만 반영" 이라고 명시하고 core 를 작게 유지한다. memU 는 매번 retrieve 를 시킴.
- 안: 우리 설계(항목당 수십 토큰의 경로§절 가리킴)와 같은 방향임을 확인. 추가로 Letta 처럼 가리킴 목록에 L0 설명 한 줄을 붙이면 다시 읽을지 판단 가능하다.
- 비용 낮음(M6 에 포함), 적합 높음.

### 6.6 가져오지 않는 것
- 임베딩·BM25 융합·엔티티 가산(Mem0, memU): 임베딩 API 키 또는 모델(spaCy 등) 필요, 비결정적, 메모리 큼. 단 "BM25 + 청크→문서 롤업" 의 롤업만 값이 있다(6.1). 사용자 결정(본문 색인을 넣고 잰 뒤)을 바꿀 근거는 아니다.
- LLM 추출(Mem0 ADD-only, Cognee cognify): 비용·비결정. 기록은 사람이 쓴 Markdown 이 원천이라는 우리 전제와 충돌.
- 그래프 DB(Cognee): 의존성·메모리·가독성 모두 부적합. memU 도 ADR 에서 같은 이유로 그래프를 포기했다.
- 데몬/서버(Cognee 서버, Mem0 서버): 우리 per-uid 데몬 설계가 더 가볍고 소켓·uid 격리 정책이 있다. Mem0 의 훅당 `python3` 기동(3-6초 제한)보다 Rust 훅 3ms 가 낫다.
- Letta 의 "에이전트가 기억 전체를 스스로 고침": 비프로그래머 동료 환경에서는 검토되지 않은 자동 편집이 위험. 단 reflection 이 기록하는 내용을 `promote:<pack>` 꼬리표 제안으로만 내는 것은 기존 결정과 맞는다.

## 7. 상위 5개 (효과 대비 비용)
1. 형식 버전 + 이전 체인(6.2): slug 불변·멱등·고정 규칙·dry-run diff. 사용자 관심 1순위.
2. L0/L1/L2 공개 층(6.1): 색인 출력은 L0 목록, `get` 이 절·본문으로 내려감, 절 → 문서 롤업.
3. 변경 경로에만 lint 강제(6.3): 이전 전후에 옛 문서가 편집을 막지 않게.
4. 늘 켜진 크기 상한 경고(Letta core 글자 수·깊이·파일당 상한을 doctor 에): 스킬 설명 6,456자 같은 문제.
5. 기한 지난 active 에 표시만 붙이기·supersede 불일치 경고(6.4).

## 8. 미확인·주의
- Letta V1 서버의 core/archival 구현과 대화 요약은 소스를 읽지 않았다(금지 안내 준수).
- Cognee 의 감쇠·시간 유효 구간 필드, 토큰 예산 로직은 확인하지 못했다. memU 의 BM25 와 SQLite 이전 코드도 못 찾았다.
- 메모리/CPU 수치는 없다. Mem0·Cognee 는 spaCy·LLM·DB 의존으로 공유 10GiB 에서 부담이 크리라는 짐작일 뿐 측정치가 아니다.
- 이 파일 안의 파일 경로는 모두 `/tmp/memsurvey/<name>/repo`(letta-code 는 `/tmp/memsurvey/letta-code/repo`) 기준 상대 경로다.
