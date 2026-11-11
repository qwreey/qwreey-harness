# 툴킷 — 언어·툴체인별 검사 자리

harness-doctor는 **코어**(언어와 무관: CLAUDE.md 계층과 크기, rules paths, 스킬 형식, 훅·설정, 낡음과 모순, 사본 표류, worktree·세션, 정본 싱크)와
**툴킷**(언어·툴체인: 핀, 포매터, 공유 지식 저장소, 언어 고유 사본)으로 나뉜다.
coderag의 지식 계층(global / pack / project, `coderag/tech-design.md` §13)과 짝을 맞춘다.

| harness-doctor | coderag | 예 |
|---|---|---|
| 코어 + 사용자 레벨(`--user`) | global | 하네스 규약, `decisions/` 중 언어 무관 결정(D-07) |
| 툴킷(`toolkits/<이름>`) + 그 공유 지식 저장소(`<이름>-kb`) | pack | luau + luau-kb |
| 대상 저장소 | project | quad, vitrine, `intake/<이름>` |

## 목차
- [있는 툴킷](#있는-툴킷)
- [동작](#동작)
- [모듈 인터페이스](#모듈-인터페이스)
- [새 툴킷 추가하기](#새-툴킷-추가하기)

## 있는 툴킷

| 이름 | 상태 | 감지 표식 요지 | 문서 |
|---|---|---|---|
| luau | 검사 있음(TOOL-·KB-·DRIFT-TYPEDEFS) | `*.luau`, mise의 luau·stylua 등, `default.project.json`, `.luaurc` | `luau.md` |
| web | **골격** — 감지만 | `package.json`의 astro·react·vite 등, `*.astro`·`*.tsx` | `web.md` |

## 동작

- scan은 저장소마다 모든 툴킷의 `detect()`를 부르고, 표식이 하나라도 나온 툴킷만 `check()`한다. 한 저장소에 여럿이 켜질 수 있다(quad = luau + web).
- 감지 결과는 보고 머리 `툴킷:` 줄과 `--json`의 `toolkits`에 나온다. 결과(finding)로는 내지 않는다.
- `--toolkits luau,web`은 감지와 무관하게 켠다. `--toolkits none`은 모두 끈다. `harness.env`의 `HARNESS_TOOLKITS`는 쓸 수 있는 툴킷 목록 자체를 줄인다.
- 툴킷 결과는 코어 항목 번호를 빌려 쓴다: 5 공유 지식, 6 사본 표류, 8 툴체인. `--only 8`이면 툴킷의 8번 검사만 돈다.

## 모듈 인터페이스

`scripts/toolkits/<이름>.py`. scan이 `importlib`로 읽는다(`python3 -I`라 sys.path에 기대지 않는다). scan을 import하지 않는다.

| 이름 | 필수 | 뜻 |
|---|---|---|
| `NAME`, `TITLE` | 예 | 툴킷 이름(파일 이름과 같게), 사람용 이름 |
| `REFERENCE` | 예 | `references/toolkits/<이름>.md` |
| `detect(ctx) -> list[str]` | 예 | 감지 표식 문자열 목록. 비면 꺼진다. 싸게 만든다(파일 목록·작은 설정 파일만) |
| `check(ctx)` | 예 | `ctx.want(n)`으로 항목을 고르고 `ctx.add(item, sev, code, where, msg, ref)`로 낸다 |
| `SKIP_DIRS` | 아니오 | git이 없는 대상(반입 사본)을 걸을 때 뺄 디렉터리 |
| `SIDE_EFFECT_WORDS` | 아니오 | `SKILL-SIDEFX` 정규식에 더할 낱말 |
| `PIN_TOOLS` | 아니오 | `ctx.pin_mismatch(mine, PIN_TOOLS)`로 형제 저장소 핀 불일치를 볼 mise 도구 |

`ctx`가 주는 것: `repo`, `files`(git ls-files, 없으면 걷기), `projects`(형제 루트), `env`(harness.env), `kb(name)`(공유 지식 경로),
도우미 `read`, `md5`, `run`, `rel`, `inside`, `strip_code`, `rule_files`, `common_dir`, `mise_tools`, `toml`, `pin_mismatch`.

## 새 툴킷 추가하기

예: rust(coderag). 순서대로 한다.

1. **감지 표식을 정한다.** 그 언어에만 있는 파일 하나 이상: rust는 `Cargo.toml`, `rust-toolchain.toml`, `*.rs`.
   다른 툴킷과 겹치는 표식(`mise.toml` 자체, `package.json` 자체)은 쓰지 않는다. 내용(의존성 이름, mise 도구 이름)으로 거른다.
2. **모듈을 만든다**: `scripts/toolkits/rust.py`에 위 표의 필수 이름을 둔다. 처음에는 `check()`를 비워 두고 web처럼 `CANDIDATES`만 적는다.
   ```python
   NAME, TITLE, REFERENCE = "rust", "Rust", "references/toolkits/rust.md"
   def detect(ctx):
       return [m for m in ("Cargo.toml", "rust-toolchain.toml") if (ctx.repo / m).is_file()]
   def check(ctx):
       return
   ```
3. **문서를 만든다**: `references/toolkits/rust.md`에 감지 표식, 코드 표(뜻·등급), 판단 근거, 모델이 볼 것, 걸린 결정을 둔다. 형식은 `luau.md`.
   100줄이 넘으면 맨 위에 목차를 둔다(`SKILL-TOC`). 이 README의 "있는 툴킷" 표에 한 줄 더한다.
4. **코드 이름**: 툴킷 접두(`RUST-`, `WEB-`)를 쓴다. 옛 luau 코드(`TOOL-`, `KB-`)는 호환 때문에 그대로 둔다.
   목표값이 확정되지 않은 핀은 목표와 비교하지 말고 `ctx.pin_mismatch`로 형제 사이 불일치만 낸다(D-05 교훈).
5. **주변 장치**
   - 무거운 실행: `home/.claude/hooks/heavy-proc-guard.py`의 `TOOLKIT_EXECUTORS`에 실행기를 더한다(rust: `cargo` — 이미 있음).
   - 공유 지식 저장소(`rust-kb`)가 생기면 `home/MANIFEST`에 `link ... ${HARNESS_WORKSPACE}/rust-kb/...` 줄을 더한다.
   - 감사자: 관점별 공통 감사자에 그 툴킷 지식 스킬을 프리로드하는 방식은 `<doctor>/drafts/agents/README.md` §9 제안.
6. **확인**: 그 언어 저장소 하나와 무관한 저장소 하나에 `scan.py --json`을 돌려 감지가 맞는지, 다른 저장소의 결과가 바뀌지 않았는지 본다.
   `claude plugin validate`로 스킬 형식도 본다.
