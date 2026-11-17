# lib/

여러 플러그인(과 coderag)이 함께 쓰는 코드와 문구의 정본. 어느 플러그인에도 속하지 않고 설치되지 않는다.
플러그인은 서로의 파일을 import 할 수 없어서(따로 설치된다) 각자 사본을 들고 다니고, 그 사본은 `tools/sync-copies.py` 가 맞춘다.

| 파일 | 무엇 |
|---|---|
| `compact_epoch.py`, `harness_nonce.py`, `memory_signals.py`, `copy_regions.py`, `file_lock.py` | 파일째 복사하는 모듈. 사본 머리에 `@copy-of: lib/<파일>` |
| `known_repos.py` | 이 기기에서 일한 저장소 목록(세션 기록의 cwd, 옵션으로 더하고 빼기, 임시 폴더 등 기본 제외, worktree 합치기, 캐시). 파일째 사본(qwreey-workspace, qwreey-conventions), 설정은 옆의 harness_env 사본으로 읽는다. 테스트 `tools/tests/test-known-repos.py` |
| `ambient.py` | 플러그인 상시 규약 주입 훅. 파일째 복사하고, 플러그인마다 다른 것(태그 이름, 이벤트, 끄기 스위치, 회차 이름공간)은 플러그인의 `context/ambient.json`, 글은 `context/ambient.md`(서브에이전트용은 `context/subagent.md`, 없으면 메인 글). 형식은 파일 머리. 테스트 `tools/tests/test-ambient-lib.py` |
| (`home/.claude/lib/harness_env.py`) | harness.env 층 로더(settings.json 의 플러그인 옵션 층 포함, 순서는 파일 머리). 정본은 `~/.claude/lib` 로 설치되는 `home/` 쪽에 있고 여기엔 없다. 플러그인은 늘 파일째 사본을 쓴다(설치본은 옛 판일 수 있다). 로더는 방식과 여러 플러그인이 읽는 키만 갖고, 한 플러그인만 읽는 키의 기본값과 사용자 전용 여부는 그 플러그인이 `load_layers(defaults=, user_only=)` 로 넘긴다. 테스트 `tools/tests/test-harness-env.py`(층), `tools/tests/test-harness-env-owners.py`(키 주인, 옛 설치본) |
| `harness_texts.py` | 언어를 넘어 같은 문장을 써야 하는 상수(`OMIT_LINE`, `NONCE_RULE`). 사본은 영역 표시로 옮긴다 |

사본이 있어야 하는 곳의 목록은 `tools/tests/test-vendored-copies.py` 의 `EXPECTED`(파일), `REGIONS`(영역).

## 표시

- 파일 사본: 처음 10줄 안에 `@copy-of: <경로>`. 정본도 자기 경로를 적는다(바이트가 같으므로).
- 영역 사본: 주석 접두(`#`, `//`, `--`)와 표시만 있는 줄 두 개로 감싼다. 경로는 표시를 담은 파일의 저장소 루트 기준이고, 다른 저장소는 `../coderag/...` 처럼 쓴다. 자기 파일을 가리키는 영역이 정본이다.

```text
# @start-replace: lib/harness_texts.py#OMIT_LINE value=string template="OMIT_LINE = {value}"
OMIT_LINE = "..."
# @end-replace
```

  옵션이 없으면 정본 줄을 그대로(들여쓰기만 맞춰) 옮긴다. `value=string` 은 정본 영역의 문자열 리터럴 하나를 꺼내 `template` 의 `{value}` 자리에 큰따옴표 리터럴로 넣는다(Python, Rust, JS, Luau 에서 같은 escape).

## 동기화

정본만 고치고 다음을 돌린다(표준 라이브러리만 쓴다).

```bash
python3 -I tools/sync-copies.py           # 바뀔 내용을 diff 로
python3 -I tools/sync-copies.py --apply   # 사본에 쓰기
python3 -I tools/sync-copies.py --check   # 어긋나면 exit 1 (tools/tests/test-vendored-copies.py 가 부른다)
```

훑는 곳: 이 저장소의 `lib/`, `plugins/`, `packs/`, `tools/` 와 옆에 있으면 `../coderag` 의 `crates/`, `harness/`, `conventions/`. 표시 오류(정본 없음, 짝 없는 표시, 한 파일 안 같은 영역 이름, 사본을 정본으로 가리킴)는 exit 2.
