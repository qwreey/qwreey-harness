# /q:doctor 툴킷 만들기

툴킷을 만들거나 채우는 사람용이다. 진단할 때 모델이 읽는 쪽(감지, 동작, 툴킷별 판정)은 `skills/doctor/references/toolkits/`에 있다.

## 목차
- [모듈 인터페이스](#모듈-인터페이스)
- [새 툴킷 추가하기](#새-툴킷-추가하기)
- [web 툴킷 채우기](#web-툴킷-채우기)

## 모듈 인터페이스

`skills/doctor/scripts/toolkits/<이름>.py`. scan이 `importlib`로 읽는다(`python3 -I`라 sys.path에 기대지 않는다). scan을 import하지 않는다.

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
   100줄이 넘으면 맨 위에 목차를 둔다(`SKILL-TOC`). `references/toolkits/README.md`의 "있는 툴킷" 표와 doctor `SKILL.md` 표에 한 줄씩 더한다.
4. **코드 이름**: 툴킷 접두(`RUST-`, `WEB-`)를 쓴다. 옛 luau 코드(`TOOL-`, `KB-`)는 호환 때문에 그대로 둔다.
   핀 값은 저장소 소유라(D-05) 목표값과 비교하지 말고 `ctx.pin_mismatch`로 형제 사이 불일치만 낸다.
5. **주변 장치**
   - 무거운 실행: `plugins/qwreey-proc-guard/hooks/heavy-proc-guard.py`의 `TOOLKIT_EXECUTORS`에 실행기를 더한다(rust: `cargo` — 이미 있음).
   - 공유 지식 저장소(`rust-kb`)가 생기면 팩(`packs/rust-kb`)으로 두거나, 형제 저장소면 정본 harness.env 에 그 위치 변수를 적고 `home/MANIFEST`에 `link ... ${<변수>}/...` 줄을 더한다(home-sync 는 작업공간 위치를 짐작하지 않는다).
   - 감사자: 관점별 공통 감사자에 그 툴킷 지식 스킬을 프리로드하는 방식은 claude-doctor `.claude/research/drafts/agents/README.md` §9 제안.
6. **확인**: 그 언어 저장소 하나와 무관한 저장소 하나에 `scan.py --json`을 돌려 감지가 맞는지, 다른 저장소의 결과가 바뀌지 않았는지 본다.
   `claude plugin validate`로 스킬 형식도 본다.

## web 툴킷 채우기

지금 web은 감지와 `WEB-PLUGINS` 추천만 한다. 대상 예정: 블로그(react/astro, 아직 옮겨 오지 않음), vitrine(go + react/vite), quad·devplorer의 astro 문서 사이트.

### 도입 후보 플러그인 (실측 후)

- typescript-lsp, gopls-lsp(vitrine Go), rust-analyzer-lsp(Rust 저장소): 바이너리 설치 후 실측(claude-doctor `.claude/audit/16` §7-5)을 거쳐 `WEB-PLUGINS` 목록에 더한다.
- modern-web-guidance, axe-accessibility: 참고. web-kb 후보.

### 예약 검사 코드

코드 이름은 예약만 했다(`web.py`의 `CANDIDATES`). 실제 프로젝트를 감사하며 오탐·기준을 정한 뒤 하나씩 검사로 옮긴다.

| 예약 코드 | 볼 것 | 정할 것 |
|---|---|---|
| `WEB-LOCK` | 패키지 매니저 lock이 하나인가(package-lock / pnpm-lock / yarn.lock / bun.lockb 혼재), `packageManager` 필드와 맞는가 | 워크스페이스(monorepo)에서 하위 lock을 어떻게 볼지 |
| `WEB-TSSTRICT` | tsconfig의 `strict`(와 `noUncheckedIndexedAccess` 등). `extends` 사슬을 따라간다 | 등급(경고/정보), astro 기본 tsconfig 프리셋 해석 |
| `WEB-LINT` | 린터·포매터 설정(eslint / biome / prettier)이 있는가, 둘이 겹치는가 | 포매터 미설정을 D-02(stylua)처럼 사고로 볼 근거가 있는가 |
| `WEB-CMDS` | 빌드·테스트·타입검사 명령(`package.json` scripts)이 CLAUDE.md에 적혀 있는가, 적힌 명령이 scripts에 있는가 | 하위 디렉터리 package.json(vitrine `web/`)의 명령을 어떻게 적게 할지 |
| `WEB-NODEPIN` | node·패키지 매니저 버전 핀(mise.toml, `.nvmrc`, `engines`)이 형제 저장소와 어긋나는가 | 핀은 저장소 소유(D-05)라 목표값 없이 불일치만 알린다(코어 도우미 `pin_mismatch` 재사용) |
| `WEB-GENERATED` | 생성물(`dist/`, `.astro/`, `schema.d.ts`)이 커밋되거나 rules `paths`에 걸리는가 | 생성물 목록 |

그 밖의 후보(검사보다는 모델 판정): `SKILL-SIDEFX` 낱말(`npm publish`, `wrangler deploy`, `vercel --prod`), 공유 지식 후보 신호(브라우저·번들러 버전 의존 서술), 무거운 실행(`vitest bench`, lighthouse — heavy-proc-guard의 web 실행기는 이미 있다).

### 채우는 순서

1. 프로젝트를 `intake/<이름>/`로 반입한다(claude-doctor `intake/README.md`).
2. `scan.py intake/<이름>`으로 감지와 코어 결과를 본다.
3. 위 후보를 그 프로젝트에 손으로 적용해 보고, 참 발견과 오탐을 claude-doctor `.claude/audit/intake/<이름>-<날짜>.md`에 적는다.
4. 참 발견이 있던 후보부터 `web.py`의 `check()`에 옮기고, `references/toolkits/web.md`에 "검사" 표로 더한다(형식은 `luau.md`의 툴체인 표).
5. 옮긴 뒤 반입 사본과 vitrine에 다시 돌려 결과를 확인한다.
