# 41. M2 컷오버 계획: 팩 rule 주입을 파이썬 훅에서 coderag 로

> Snapshot 2026-11-12. 아무것도 켜지 않은 준비 결과다. coderag 98163e8(미푸시)과 packs/*/coderag.toml 의 claude_plugin 한 줄까지만 끝났고, 아래 단계는 사용자가 순서대로 실행한다.

## 준비된 것
- coderag 98163e8: 매니페스트 `claude_plugin`, 프로젝트 팩 목록이 조회 범위를 정함(목록 없으면 등록된 팩 전부, rule 은 목록 없으면 없음, coderag/.claude/base/layers-and-packs.md §13.3), `coderag adapt --harness claude [--dry-run]`, `hook pre-compact` 가 하루 한 번 14일 넘은 state 파일 삭제. cargo test 전부 통과, 대조 테스트 116건 0 실패.
- claude-doctor: `packs/web-security/coderag.toml`(새로), `packs/luau-kb/coderag.toml` 에 `claude_plugin = "luau-kb@claude-doctor-market"` 한 줄. 임시 CODERAG_HOME 에 두 팩을 path 로 등록해 `pack status`, `gen --layer pack`(web-security 16항목, luau-kb 12모듈), 검색 모두 매니페스트 경고 없이 동작.
- 틈: hardening references 13개에 frontmatter 가 없다(SKILL.md 는 name·description 뿐). 검색은 되지만(제목은 H1, 요약은 첫 줄) `coderag lint` 는 title·description 필수라 알리고, keywords·category 가 없어 어휘 검색이 약하다. 지금은 안 넣었다. 컷오버와 무관하고 별도 작업이다.

## 이중 주입 위험과 순서의 원리
파이썬 팩 훅(PostToolUse `rules_inject.py`)과 coderag `hook post-tool` 이 같은 세션에서 둘 다 살아 있으면 맞는 rule 이 두 번 실린다(마커 저장소가 서로 달라 서로를 모른다). 그래서 순서는 (1) coderag 훅을 먼저 깔되 프로젝트 목록이 없으면 아무것도 안 넣는 상태로 두고, (2) 파이썬 훅을 팩에서 뺀 새 버전을 배포하고, (3) 마지막에 프로젝트 목록을 켠다. 틈이 생겨도 "잠깐 주입 없음" 쪽이지 "두 번"이 아니다. 훅은 세션 시작 때 읽히므로 각 단계 뒤 실행 중인 세션은 새로 연다.

## 순서
각 단계 끝의 롤백은 그 단계만 되돌린다.
1. coderag 바이너리. `cd /code/Projects/coderag && cargo build --release -p coderag-cli -p coderag-provider-markdown-frontmatter`. 래퍼 `bin/coderag` 가 `$CODERAG_BIN`, 플러그인 루트의 `target/{release,debug}`(더 새 것), `${CLAUDE_PLUGIN_DATA}/bin`, PATH 순으로 찾는다. 롤백: 없음(빌드만).
2. 전역 등록(사용자 파일). `~/.coderag/coderag.toml` 에 `[[packs]] name="web-security" path="/code/Projects/claude-doctor/packs/web-security"`, luau-kb 도 같게. 확인: `coderag pack status`. 롤백: 두 항목 삭제.
3. coderag 저장소 `hooks/hooks.json` 에 PostToolUse(`Read|Edit|Write|MultiEdit|NotebookEdit` → `hook post-tool`)와 PreCompact(`manual|auto` → `hook pre-compact`)를 더하고 `plugin.json` 을 0.2.0 으로. 현재 hooks.json 은 `post-edit`·`pre-bash` 둘뿐이라 이 단계 전에는 coderag 가 rule 을 못 넣는다. 목록 없는 프로젝트에서는 새 훅이 아무것도 안 하므로 안전하다. 반영은 coderag 플러그인 재설치(`claude plugin update coderag@<마켓>`). 롤백: hooks.json 되돌리고 0.1.0 으로.
4. 파이썬 대비 사본 정리 준비. `rules_inject.py`·`compact_epoch.py` 를 지우기 전에 `tools/tests/test-coderag-rules-parity.py` 가 읽을 참조 사본을 `tools/tests/reference/` 로 옮기고(팩 안에는 두지 않는다, 합의 6) 테스트 경로를 고친다. `packs/web-security/tests/test-web-security.py` 도 훅 시험이 있어 같이 손본다. 롤백: git revert.
5. web-security 0.4.0: `packs/web-security/hooks/` 삭제(hooks.json, rules_inject.py, compact_epoch.py, conv_env.py)와 `plugin.json` 0.4.0. luau-kb 도 같은 방식으로 0.6.0(`.luau` rule 훅 제거). marketplace.json 설명의 "훅" 표현도 고친다. 배포: 마켓 갱신 `claude plugin marketplace update claude-doctor-market` 뒤 각 저장소에서 `claude plugin update web-security@claude-doctor-market`. 이 시점부터 팩만 켠 프로젝트는 주입이 없다. 롤백: 이전 버전 태그로 되돌리고 update.
6. 대상 저장소 하나에서 켜기. 그 저장소 `coderag.toml` 에 `[[packs]] name = "web-security"`(luau 저장소는 luau-kb), 그다음 `coderag adapt --harness claude --dry-run`, 이상 없으면 `coderag adapt --harness claude`(`.claude/settings.json` 의 `enabledPlugins` 에 `web-security@claude-doctor-market` 추가), `coderag gen`. adapt 는 추가만 하고 기존 키·순서를 보존한다(들여쓰기는 2칸으로 다시 쓴다). 롤백: `[[packs]]` 줄 삭제(주입 중단)와 `enabledPlugins` 키 수동 삭제(adapt 는 지우지 않는다).
7. 나머지 저장소는 6번을 반복. 팩을 켠 저장소 목록은 `grep -l web-security */.claude/settings.json` 으로 먼저 뽑는다.

## 확인
- `python3 -I tools/tests/test-coderag-rules-parity.py`: 4번 전에 한 번(파이썬 사본과 같은 출력, 116건), 4번 뒤 참조 사본으로 다시.
- 실제 세션(6번 뒤, 새 세션): `.luau` 파일 하나와 `.ts` 파일 하나를 Read 해서 rule 이 한 번씩만 붙는지 본다(`<harness-hook>` 같은 덩어리가 파일당 하나). 같은 파일을 다시 Read 해도 안 붙고, `/compact` 뒤 다시 Read 하면 붙어야 한다.
- 두 번 붙으면 5번이 반영되지 않은 것: `claude plugin list` 로 팩 버전을 보고 세션을 새로 연다.
- `coderag rules --for src/a.ts` 로 어떤 팩의 rule 이 맞는지 훅 없이 확인.

## coderag 플러그인이 바이너리를 찾는 법(오늘)
`hooks/hooks.json` 은 `${CLAUDE_PLUGIN_ROOT}/bin/coderag` 를 부르고 이것은 bash 래퍼다. 플러그인 루트가 `/code/Projects/coderag` 로 설치된 한 `target/{release,debug}` 가 곧 개발 빌드다. 바이너리가 없으면 `coderag hook ...` 은 조용히 0 으로 끝난다(세션을 막지 않음, 그러나 주입도 없다). 마켓 캐시에 복사되는 설치에서는 캐시에 `target/` 이 없으므로 `$CODERAG_BIN` 이나 `${CLAUDE_PLUGIN_DATA}/bin/coderag` 가 필요하다.

## 미정(사용자 판단)
- 릴리스 배포와 서명: 다른 기기·동료에게 바이너리를 어떻게 주나(GitHub release, 플랫폼별 빌드, 체크섬·서명). 이 계획은 이 기기의 로컬 빌드만 전제한다.
- coderag 를 claude-doctor-market 에 넣을지 별도 마켓으로 둘지. 단 `claude_plugin` 키의 마켓 이름이 마켓마다 다르므로 팩 마켓과 coderag 마켓이 갈리면 설치 안내가 두 군데가 된다.
- hardening references 13개 frontmatter 를 언제 채울지.
- 단계 3 의 hooks.json 과 단계 5 의 팩 버전·훅 삭제는 이번 세션이 건드리지 않았다.
- adapt 는 settings 에 false 로 꺼진 키를 바꾸지 않고 충돌로 알리고 종료 1(coderag 2d40d39). 사용자가 그 저장소에서 일부러 끈 것일 수 있어, 목록과 settings 중 어느 쪽을 고칠지는 사람이 정한다.
