# 42-B. 에이전트 메모리 시스템 4종 소스 조사

> Snapshot 2026-11-12. 읽기 전용 정적 조사: 저장소를 /tmp/memsurvey 에 `git clone --depth 1`(agentmemory 는 `npm pack` 으로 받은 0.9.33 tarball 도 대조)만 하고 설치·빌드·실행은 하지 않았다. 아래 사실은 소스·docs 로 확인한 것이고, 확인 못 한 것은 그렇게 적었다.

## 0. 무엇을 읽었나
| 시스템 | 저장소 | 읽은 버전 | 설명 일치 | 라이선스 |
|---|---|---|---|---|
| Zep / Graphiti | github.com/getzep/graphiti | 0.31.2, commit ebef986 | Graphiti(오픈소스 엔진)만 읽음. Zep 서비스 자체는 클라우드 제품이라 소스 없음 | Apache-2.0 |
| AgentMemory | github.com/rohitg00/agentmemory, npm `@agentmemory/agentmemory` | 0.9.33, commit 57bc384 | 일치(코딩 에이전트용 영속 메모리). 저장소 `DESIGN.md` 는 메모리와 무관한 웹 디자인 문서 | Apache-2.0 |
| EverOS | github.com/EverMind-AI/EverOS | 1.6.0, commit 9cd1be6 | 일치(Markdown+SQLite+LanceDB, local-first). "procedural skill evolution" 은 agent_skill 로 구현됨 | Apache-2.0 (NOTICE 파일 있음; 핵심 알고리즘은 별도 패키지 `everalgo` 라 거기 소스는 못 봄) |
| openJiuwen agent-memory | github.com/openJiuwen-ai/agent-memory (GitCode 미러) | 0.2.0, commit 8db59ce | 일치. 단 graph/document 색인은 README 상 "planned" 가 섞여 있고, 문서가 말하는 `jiuwen_memory_adapter/cc_memory` 는 이 체크아웃에 없음(codex/hermes/openclaw 는 `.gitkeep` 뿐) | Apache-2.0 |

공통으로 모르는 것: 실제 동작·성능·메모리 사용량(실행 안 함), 벤치마크 주장의 진위.

## 1. Zep / Graphiti
1. 데이터 모델. 시간 인식 지식 그래프. 노드 `EpisodicNode`(원문 에피소드: source, content, valid_at), `EntityNode`(name, summary, attributes, name_embedding), `CommunityNode`, `SagaNode`. 간선 `EntityEdge`(name, fact 문장, fact_embedding, episodes 목록, attributes). 모든 항목에 `uuid`(uuid4)와 `group_id`(그래프 분할 단위; user/session/project 를 이 하나로 표현). 에이전트별 스코프는 없음. (graphiti_core/nodes.py, edges.py)
2. 계층. 에피소드(원문) → 엔티티·사실(간선) → 커뮤니티(요약 군집) 로 올라가는 구조적 계층. 이동은 LLM 추출이 주도하고 규칙(시간 정규화 정규식)이 보정한다. L0-L2 식 점진 공개는 없고, 검색 결과로 사실·노드 요약을 돌려줄 뿐이다.
3. 저장. 그래프 DB(Neo4j, FalkorDB, Neptune, Kuzu; Kuzu 는 deprecated 표기)에 저장. 사람이 읽거나 git 에 넣을 수 없다. 임베딩은 DB 안.
4. 검색. 간선·노드·에피소드·커뮤니티마다 설정 가능한 파이프라인: BM25(풀텍스트) + 코사인 + BFS 를 합치고 RRF, node_distance, episode_mentions, MMR, cross-encoder 로 재순위(search/search_config.py). `SearchFilters` 는 valid_at/invalid_at/created_at/expired_at 날짜 조건, 라벨, 속성 필터. 토큰 예산 조절은 못 찾음(개수 limit 만).
5. 수명. 이 시스템의 핵심. 간선에 이중 시간: `valid_at`(사실이 참이 된 때), `invalid_at`(참이 아니게 된 때), `expired_at`(시스템이 무효 처리한 때), `created_at`. 새 사실이 기존 사실과 모순되면 LLM 이 판정하고 옛 간선의 `invalid_at`/`expired_at` 을 채울 뿐 지우지 않는다(`_apply_temporal_invalidation`, utils/maintenance/edge_operations.py:716 부근). 노드 중복 제거는 이름 정규화 + MinHash/LSH 후보 + LLM(dedup_helpers.py). "will/plans to" 같은 미래형은 정규식으로 valid_at 을 에피소드 시각에 맞춘다(temporal_edge_utils.py). 감쇠·망각 정책은 없음.
6. 버전. 항목별 스키마 버전 없음. `graphiti_core/migrations/__init__.py` 는 빈 파일. 스키마 변경은 DB 인덱스·제약 재구성으로 처리.
7. 통합. 라이브러리(Python, async) + 별도 `server/`(FastAPI) + `mcp_server/`(기본 HTTP, stdio 도 가능, 인증 없음 "참조 구현"). 코딩 에이전트 훅 없음. 무거운 쪽: 그래프 DB 서버 + 에피소드마다 LLM 호출 여러 번(추출, 중복 판정, 모순 판정). 큐 기반 비동기 처리.
8. 라이선스 Apache-2.0. 텔레메트리(posthog)가 기본 의존성에 있음(끄는 설정 존재 여부는 미확인).

## 2. AgentMemory (rohitg00)
1. 데이터 모델. TypeScript 타입(src/types.ts). 계층별 레코드: `RawObservation` → `CompressedObservation`(id, sessionId, type 15종, title, facts[], narrative, concepts[], files[], importance, confidence, agentId, origin), `Memory`(id, type: pattern/preference/architecture/bug/workflow/fact, title, content, concepts, files, sessionIds, strength, version, parentId, supersedes[], isLatest, forgetAfter, project, agentId), `SemanticMemory`(fact, confidence, accessCount, strength), `ProceduralMemory`(name, steps[], triggerCondition, frequency). 스코프: session, project, agent(`shared`/`isolated`), team(`mem:team:<id>:users:<uid>`). ID 는 접두사+난수형(generateId).
2. 계층. "4-tier consolidation": working → episodic → semantic → procedural(`ConsolidationTier`). `mem::consolidate-pipeline`(functions/consolidation-pipeline.ts)이 tier 단위(semantic, reflect, procedural, decay)로 돈다. 승격은 LLM 요약/추출 + 반복 횟수·접근 횟수 규칙. 점진 공개는 없고 컨텍스트 주입 때 `TOKEN_BUDGET`(기본 2000토큰, 길이/3 추정)에 맞춰 자른다(functions/context.ts).
3. 저장. 자체 엔진 iii-engine 위의 KV(`mem:*` 키 공간 50여 개). 파일 기반 `state_store.db`(deploy/runtime/worker-compose.yaml) 또는 redis. 위치 `~/.agentmemory/`. 사람이 읽을 수 없음. `obsidian-export` 로 Markdown 을 내보내는 단방향 기능은 있음. git 부적합(바이너리 DB).
4. 검색. BM25(+동의어·스테머·CJK 분절) + 벡터 + 그래프를 RRF(k=60, bm25 가중 0.4)로 합침(state/hybrid-search.ts). 계층(layer: observation/memory…)별 필터, 선택적 reranker.
5. 수명. 가장 풍부하다. `remember` 가 유사 기존 메모리를 `supersedes` 로 대체하고 `version+1`, `isLatest=false`(functions/remember.ts); 다른 project 는 대체하지 않음. `auto-forget`: `forgetAfter` TTL, 유사도 0.9 이상 모순 쌍 검출, 저가치 관찰 정리(dry-run 지원). 감쇠: `strength*0.9^기간`(consolidation-pipeline), 지수 시간 감쇠 λ=0.01(retention.ts). 감사 로그(audit), 스냅샷, evict, 디스크 크기 관리.
6. 버전. 항목별 스키마 버전 없음. 내보내기 JSON 에만 앱 버전 `version`(0.3.0..0.9.33 열거)이 있고 가져오기는 지원 목록에 있는 것만 받는다(export-import.ts). `functions/migrate.ts` 는 "memory.project 추론" 같은 일회성 데이터 보정이고 일반 마이그레이션 틀은 아님. 그래프 색인에만 전용 마이그레이션 상태기계(state/graph-index-migration.ts).
7. 통합. 가장 직접적인 코딩 에이전트 연동: Claude Code 훅(SessionStart, UserPromptSubmit, PreToolUse(Edit|Write|Read|Glob|Grep), PostToolUse, PreCompact, Stop, SubagentStart/Stop 등 plugin/hooks/hooks.json), Codex/Copilot/Devin/Droid/Antigravity 용 훅 JSON, Cursor·OpenCode·pi·Hermes 통합, MCP 도구 58개. SessionStart 에서 `additionalContext` 로 주입. 프로세스: 장기 실행 서버(Node + iii-engine 바이너리 다운로드·실행, sha256 표 포함). 가벼운 라이브러리가 아니다. LLM 요약·압축은 선택(키 없으면 규칙 기반).
8. 라이선스 Apache-2.0.

## 3. EverOS (EverMind-AI)
1. 데이터 모델. 종류 8개: episode, atomic_fact, foresight, profile(user.md), agent_case, agent_skill, knowledge_document, knowledge_topic. 항목은 Markdown 파일 안의 `<!-- entry:<entry_id> -->…<!-- /entry:… -->` 블록(entry_id 예 `ep_20260601_00000001`). 파일 frontmatter: id, type, schema_version, user_id|agent_id, track, date, entry_count. 스코프 `<app_id>/<project_id>/{users/<uid>, agents/<aid>, knowledge}` 를 **경로**로 표현(frontmatter 에 넣지 않음). (docs/storage_layout.md, infra/persistence/markdown/_base/frontmatter.py)
2. 계층. 대화 버퍼(SQLite) → LLM 경계 탐지 → MemCell → episode(동기 기록) → OME(오프라인 엔진)가 비동기로 atomic_fact·foresight·profile·agent_case 생성 → case 군집 → agent_skill. `reflect_episodes`(cron, 기본 꺼짐)는 군집 안 조각난 episode 를 LLM 이 하나로 합치고 원본에 `deprecated_by` 를 단다. 결정 주체: 경계·추출·병합은 LLM, 스케줄·게이트는 설정(`ome.toml`, 2초 핫리로드). 점진 공개 단계는 없고 검색이 episode → atomic_fact 로 힙 확장(memory/search/hierarchy.py).
3. 저장. **Markdown 이 정본**, `.index/`(SQLite + LanceDB)는 파생물·gitignore 대상이며 지워도 `everos cascade rebuild` 로 복구. 일별 로그 추가형(`episode-YYYY-MM-DD.md`), 단일 파일 덮어쓰기(user.md), 스킬 디렉터리(`skills/skill_<name>/SKILL.md` + references/ scripts/). 사용자가 VSCode·Obsidian 에서 직접 고치면 watchdog 이 항목 단위로 재색인(content_sha256 비교). 사람이 읽기 좋고 git 에 넣을 수 있으나 숨김 폴더(.atomic_facts, .cases)와 항목 마커 주석이 있다.
4. 검색. LanceDB 한 쿼리 안에서 벡터 + BM25(FTS) + 스칼라 필터. HYBRID(RRF 후 LR 보정 점수, LLM 재순위 없음), AGENTIC(LLM 다중 라운드 + cross-encoder). 스킬 검색 전용 경로(skill_hybrid.py). 토큰 예산 조절은 못 찾음. Markdown 직접 grep 대체 경로 없음(문서에 명시).
5. 수명. 쓰기는 강한 일관성, 읽기는 최종 일관성(색인 지연 최대 10-15초). 병합은 위 reflect, 대체는 `deprecated_by`, 스킬은 새 case 가 올 때마다 기존 스킬을 LLM 이 add/update 하고 `confidence < retire_confidence(0.1)` 면 "은퇴"로 표시만 하고 원본 파일은 지우지 않는다(extract_agent_skill.py 머리 주석). 스킬 갱신 때 `source_case_ids` 계보와 quality_score 순으로 근거 case 를 프롬프트에 넣는다. 얇은 case 는 설계상 건너뜀. 감쇠 정책은 못 찾음. 삭제 API 있음.
6. 버전. 파일 frontmatter 에 `schema_version: 1` 을 쓰지만 **읽는 쪽에서 쓰는 코드는 못 찾았다**(src 전체 grep: 기록 측과 LanceDB 용 `.table_schema_version` 마커만). 즉 파일별 버전 필드는 자리만 있고 Markdown 마이그레이션 코드는 없다. 대신 파생 색인은 버리고 재빌드하는 전략이고, LanceDB 컬럼 변경은 마커 파일 + `memory_root_lock` 아래 1회 `alter_columns`, SQLite 는 alembic. 1.0.0 은 "새 아키텍처"로 옛 API 를 끊었다(docs/migration-to-1.0.0.md).
7. 통합. Python 서버(`everos server start`, 기본 127.0.0.1:8000) + 별도 패키지 `everos-mcp`(stdio MCP, uvx)가 HTTP API 를 호출. Claude Code·Codex 는 `mcp add` 안내만 있고 훅 없음. 같은 프로세스 안에 cascade(파일 감시) + OME(APScheduler) 코루틴이 돈다. 의존성 무거움: lancedb, pyarrow, sqlmodel, alembic, openai SDK, 임베딩·LLM 키 필요. 단일 memory-root 디렉터리를 복사하면 이전된다.
8. 라이선스 Apache-2.0.

## 4. openJiuwen agent-memory
1. 데이터 모델. `MemoryUnit`(common/type_def/memory.py): id, `scope`(org, space, user, agent, session 5단), `tier`, `layers`(l0, l1), `segments`(content+assets+source), `temporal`(t_event, t_ingest, t_valid, t_invalid, t_message), `provenance`(합성 출처 id 목록), `supersedes`(직전 버전 id), tags, `system_metadata`/`user_metadata`(분리), `lifecycle`, entities, vectors, hierarchy(트리 참조). 중요도 범주(identity/rule/preference/knowledge/relation/default/transient)와 출처(original/inferred)는 system_metadata 키.
2. 계층(사용자가 특히 본 부분). 서로 직교하는 세 축을 문서가 분리해서 정의한다(docs/features/common/F01-memory-layer.md).
   - 인지 역할 `MemoryTier`: working(휘발), core(상주), episodic, semantic, procedural, archival(저빈도 장기 꼬리).
   - 추상도(저/중/고: 사실·사건·프로필)는 서로 다른 MemoryUnit 이고 hierarchy(트리) 참조로 잇는다.
   - **내용 층 L0/L1/L2**: 같은 항목의 압축도. L0 개요 50-100자, L1 요점 200-500자, L2 전문. L2 는 따로 저장하지 않고 `content` 자체이며, L0/L1 만 `layers` 에 저장(전문 이중 저장 금지). 길이가 `layer_annotator_threshold`(512자) 를 넘는 항목만 표시. 만드는 쪽 `LayerAnnotator`: 규칙판(L1=앞 200자 또는 키워드 밀집 문장, L0=태그+첫 문장, 짧으면 원문)과 LLM 판(temperature 0). 실패해도 쓰기를 막지 않고 빈 값으로 두면 검색 쪽이 대체 처리.
   - 이동 결정: 구성 파이프라인이 LLM·규칙으로 ADD/UPDATE/SUPERSEDE/NOOP 를 판정하고(유사도 high/medium 임계값으로 LLM 호출 여부 결정), evolve/dreaming 스케줄러가 중장기 승격(`middle_to_long_job`)과 FORGET 을 돌린다.
   - **점진 공개(검색 시)**: `DisclosureLevel` L0/L1/L2/ADAPTIVE. 고정 레벨은 예산 때문에 낮추지 않고, ADAPTIVE 는 후보 모두에 L0 를 주고 `max_tokens`(글자수/4 추정) 안에서 첫 항목부터 L1, 점수 차가 충분하면 L2 로 올린다. 기본 `TruncatingDiscloser` 는 ADAPTIVE 를 L0 로 고정. L0/L1 은 벡터 색인에도 별도 레코드(`<id>-layer-l0`)로 들어가 층별 검색이 된다. (docs/specs/S04-retrieval.md 340-365, 450-465행)
3. 저장. 저장소 추상(KV/Vector/Fulltext/Graph/Fused/Filesystem 6 포트). 정본은 KV 의 **JSON 바이트**(sqlite/postgres/redis/메모리), 색인은 Elasticsearch/Milvus/pgvector/neo4j 등 플러그인. 문서 메모리용 `markdown_impl` 은 사람 읽기용 **뷰**(USER.md, MEMORY.md, daily_memory/YYYY-MM-DD.md)이고 정본이 아니며 메타데이터는 md 에 안 들어간다(storage/markdown.py 머리 주석). 암호화 KV·FS 래퍼, 감사 로그 있음. git 친화적이지 않음.
4. 검색. 질의 파서(재작성·키워드·절대 날짜) → 채널별 recall(BM25 키워드, 벡터, 그래프[일부 계획], 엔티티 역색인, 문서) → Fuser(RRF, 가중 RRF, BM25 점수형, 점수 최대, 계층 병합) → reranker → 임계값 → Discloser. 위의 점진 공개와 부모-자식 트리 확장이 같은 `top_k`·`max_tokens` 를 공유. 전부 "점수 클수록 관련" 으로 통일하는 규칙 명시.
5. 수명. `LifecycleState`: active / superseded / archived(유효하나 냉각, 기본 검색 제외) / forgotten. "물리 삭제 대신 무효 표시"가 원칙(비파괴 갱신). `DeleteMode.FORGET` 기본. 이중 시간(`t_valid`/`t_invalid`)과 `as_of` 시점 조회를 지원(Graphiti 와 같은 계열). 충돌 해결 전용 `ConflictResolver`, 중복 제거 `Dedup`, `provenance`/`supersedes` 계보, 중요도 기반 망각 스케줄. 시간 감쇠 수식은 못 찾음(스케줄형 forget).
6. 버전. **항목마다** 인코딩 버전 `_v`(현재 4)를 JSON 에 쓰고 `loads` 가 `_v` 로 분기(common/type_def/memory_codec.py). 규칙: "필드 추가는 호환 변경이라 버전 안 올림(읽을 때 기본값), 필드 의미·구조 변경은 버전 올리고 loads 에서 분기". `_v<2` 는 읽을 때 자동 변환(평면 content → segments 한 개), `_v<4`(metadata 혼합→system/user 분리)는 **의미를 추측할 수 없다고 보고 로드를 거부**하며 먼저 명시적 마이그레이션을 돌리게 한다(ValueError). 저장소 쪽에는 `storage/migration.py`(제한된 크기의 레코드 스캔·커서 프로토콜, 평문 전환용)가 있다. 스키마 변경 이력이 코드 주석에 남는 점이 참고할 만하다.
7. 통합. SDK(MemoryAPI: add/search/list/get/update/delete/evolve/admin), HTTP 서버, CLI, MCP 서버(FastMCP, 인증 기본 required), 어댑터 `continuity`(에이전트 간 이어받기, mcp.py). 코딩 에이전트 훅은 이 체크아웃에 없음. 멀티 테넌트(org+space)와 권한(grant) 모델. Python ≥3.11, 백엔드를 고르는 만큼 무겁다(메모리 내 백엔드 있어 최소 구성은 가능).
8. 라이선스 Apache-2.0(Huawei 저작권 표기).

## 5. 비교 요약
| | Graphiti | AgentMemory | EverOS | openJiuwen |
|---|---|---|---|---|
| 정본 | 그래프 DB | iii KV(파일/redis) | Markdown | KV 의 JSON |
| 사람이 읽기 | 아니오 | 아니오(Obsidian 내보내기) | 예 | md 뷰만 |
| 계층 | 에피소드/엔티티/커뮤니티 | 4-tier | 에피소드→사실·스킬 | tier 6 + L0/L1/L2 + 트리 |
| 대체·무효 | valid/invalid/expired | supersedes+isLatest+TTL+감쇠 | deprecated_by, 스킬 은퇴 | lifecycle 4 + t_valid/t_invalid |
| 항목 버전 | 없음 | 없음(내보내기만) | frontmatter 자리만 | `_v` + 로드 거부 |
| 코딩 에이전트 훅 | 없음 | 많음 | 없음(MCP) | 없음(MCP) |

## 6. coderag 에 가져올 만한 것
전제(synthesis.md 와 이 저장소 규약): Markdown 정본, 결정적 검색, 한 uid 한 데몬, 공유 10GiB cgroup, 비프로그래머 동료. 네 시스템 모두 LLM 호출을 쓰기 경로 중심에 두므로 "결정적" 제약과 맞지 않는다. 구조(필드·규칙)만 빌리고 LLM 판정은 빌리지 않는다.

1. **기록 단계 L0/L1/L2(적응형 공개)** (openJiuwen)
   - 풀려는 문제: 지금 검색 결과는 title+description 한 줄이고 그다음은 본문 전체다. 긴 문서(40-80k 토큰 스냅샷, 68KB SKILL 본문)를 열기 전에 중간 단계가 없다. compact 뒤 "앞에서 쓴 지식" 가리킴도 한 줄 설명(L0)과 절별 요약(L1)이 있으면 다시 읽을 범위를 좁힌다.
   - 형태: L0 = 이미 있는 frontmatter `description`. L1 = 문서의 `## ` 절 제목 목록 + 절별 첫 문장(결정적으로 추출, LLM 불필요) 또는 선택적 frontmatter `summary:`. L2 = 본문. 질의에 `level=0|1|2|auto` 와 예산을 받아 auto 는 openJiuwen ADAPTIVE 규칙(전부 L0, 예산 남으면 1등만 L1/L2)으로. 절별 블룸 필터 색인이 이미 절 단위라 L1 의 단위가 공짜로 맞는다.
   - 비용: 낮음(색인에 절 목록·첫 문장 저장, 질의 옵션 1개). 적합: 높음. 충돌: 없음. 규칙판 주의점: 규칙판 L0 는 "더 짧은 절단"이 되기 쉽다고 문서 스스로 인정하므로, 사람이 쓰는 description 을 L0 로 유지하는 편이 낫다. LLM 이 만드는 L1 은 결정성·비용 때문에 거부.
2. **파일별 형식 버전 + 명시적 마이그레이션** (openJiuwen `_v`, EverOS `schema_version`)
   - 풀려는 문제: frontmatter 규약이 바뀌면(예: status 값 추가, keywords 형식) 옛 기록을 린트가 어떻게 볼지 정해진 바가 없다. 사람이 쓰는 git 기록이라 일괄 재생성도 못 한다.
   - 교훈: (a) EverOS 는 `schema_version` 을 쓰기만 하고 읽지 않아 형식 이탈을 못 잡는다. 필드만 두지 말고 린트가 검사해야 한다. (b) openJiuwen 규칙을 그대로 옮길 가치가 있다: 필드 추가는 버전을 올리지 않고 기본값으로 흡수, 의미·구조 변경만 올린다; 읽는 쪽은 구버전 중 안전한 것은 읽을 때 변환(저장은 안 건드림), **의미를 추측해야 하는 것은 거부하고 `coderag migrate` 안내**.
   - 형태: 선택 frontmatter `format: 2`(없으면 1). `coderag doctor` 가 낡은 형식을 목록으로 보여 주고, `coderag migrate --dry-run` 이 diff 를 만들고 사람이 git 으로 검토 후 커밋. 색인 쪽은 EverOS 처럼 "색인은 파생물이라 버리고 재생성" + 색인 헤더에 형식 버전(이미 계획된 색인 형식 변경과 같이).
   - 비용: 중간(마이그레이션 틀·테스트). 적합: 높음. 충돌: 비프로그래머가 쓰는 파일에 필수 필드를 늘리면 안 되므로 **필드는 선택**, 없으면 최신 해석 + 경고.
3. **Archive 를 넘는 수명주기 상태와 "비파괴 대체" 계보** (openJiuwen lifecycle, EverOS deprecated_by, AgentMemory supersedes/isLatest)
   - 풀려는 문제: 현재 status 는 active → landed/superseded/rejected/archived. 이미 `superseded_by` 가 있어 세 시스템이 하는 핵심을 대부분 갖고 있다. 빠진 것은 (a) 대체 체인 전체(A→B→C)를 따라가 최신만 노출하는 검색 쪽 처리, (b) 대체된 문서가 인용하는 "이 문서는 X 로 대체됨" 힌트를 결과에 붙이기, (c) `forgotten`(내용이 틀려 보이지 말아야 하나 삭제는 않음) 구분.
   - 비용: 낮음. 적합: 중간. 충돌: 상태 값을 늘리면 동료가 헷갈릴 수 있으니 (c) 는 보류하고 (a)(b) 만.
4. **시간 신선도 필드(이중 시간 중 `valid`만) + review 신호** (Graphiti, openJiuwen t_valid/t_invalid)
   - 풀려는 문제: 팩의 사실(API 동작, Roblox 제약)이 낡는다. 이미 `last_verified`/`review_after` 가 있어 같은 일을 한다. 빌릴 것은 모델이 아니라 **검색 결과에 낡음을 표시**하는 쪽: `review_after` 가 지난 문서는 결과에 `stale?` 표시, 질의 `--as-of` 는 가치 낮아 제외.
   - 비용: 낮음. 적합: 중간. 충돌 없음. 자동 감쇠(AgentMemory strength 0.9^기간)는 결정성은 지키지만 사람이 쓴 지식을 점수로 깎으면 중요한 규칙이 사라지므로 **거부**.
5. **PreCompact/SessionStart 의 사용 이력 원장 + 주입 예산** (AgentMemory 훅 구성, openJiuwen 예산 규칙)
   - 풀려는 문제: synthesis 의 열린 문제(compact 뒤 복원). AgentMemory 는 PreCompact 와 PreToolUse(Read/Grep 등)에 훅을 걸어 무엇을 읽었는지 적고 SessionStart 에서 `additionalContext` 로 예산 안에 되돌려 준다. 우리 계획과 같은 구조이고 참고용 선례로 확인됨. 빌릴 점: (a) 주입량에 명시적 토큰 상한(기본 2000토큰 근처) 과 초과 시 오래된 항목부터 버리기, (b) 항목에 L0 를 붙이면 "제목 — 경로§절" 한 줄 가리킴이 한 줄 설명까지 확장, (c) 서브에이전트 시작/종료 훅도 원장에 포함.
   - 비용: 낮음(이미 계획된 것의 세부). 적합: 높음. 충돌: AgentMemory 는 항상 도는 서버라 훅이 HTTP 를 부르는데, 우리는 3ms CLI 훅 유지가 합의이므로 **구조는 안 빌림**.
6. 검토했으나 거부 또는 보류
   - LLM 이 판정하는 병합·모순 해결·요약(Graphiti, EverOS reflect, openJiuwen Evolver): 결정성·비용·오염 위험으로 거부. 다만 "사람/에이전트가 `supersedes` 를 적고 린트가 대체 쌍의 유사도를 검사"하는 보조는 가능.
   - 에이전트가 쓰는 자동 메모리(EverOS 일별 로그, AgentMemory 관찰): 우리 기록은 사람이 검토하는 git 문서라 자동 기록은 `sessions/` 스냅샷으로만 이미 존재. 팩의 `promote:<pack>` 꼬리표와 겹침.
   - 벡터·그래프 색인, 별도 DB 서버: 10GiB 공유 cgroup 과 동료 PC 설치 부담으로 거부. EverOS 의 "색인은 파생물, 정본은 Markdown, 지워도 재생성"이라는 원칙만 확인(이미 우리 방식).
   - EverOS 의 에이전트 스킬 진화(case → 군집 → SKILL.md): 흥미롭지만 LLM 필수. 우리 `promote:<pack>` 교훈 모으기의 장기 선례로 메모만. 계보 필드 `source_case_ids` 는 "이 규칙은 어느 세션 기록에서 나왔나" 를 frontmatter 에 남기는 방식으로 빌릴 수 있음(비용 낮음, 적합 중간).

## 7. 상위 5
1. 기록 L0/L1/L2 와 `level=auto` + 토큰 예산 질의(openJiuwen). 결정적 규칙으로 가능, 절 단위 색인과 맞음.
2. 선택 `format:` frontmatter + doctor 검사 + `coderag migrate --dry-run`(openJiuwen `_v` 규칙; EverOS 는 "쓰기만 하고 읽지 않음" 의 반면교사).
3. compact 뒤 가리킴에 예산 상한과 L0 한 줄을 붙이는 방식(AgentMemory 훅 선례, openJiuwen 예산 규칙).
4. 대체 체인을 따라 최신만 노출하고 결과에 "대체됨 → X" 표시, `review_after` 지난 문서에 stale 표시(Graphiti/openJiuwen/AgentMemory 공통 패턴의 결정적 부분).
5. 파생 색인 + 정본 Markdown 의 재생성 원칙에 "색인 헤더 형식 버전 + 변경 시 전체 재생성" 을 명문화(EverOS 의 `.table_schema_version` 마커 + 락 아래 1회 마이그레이션 방식).
