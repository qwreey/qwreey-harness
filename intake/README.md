# intake/ — 외부 프로젝트 반입과 감사

다른 sandbox 나 다른 사람의 프로젝트 일부를 가져와 하네스를 감사하는 자리다.
사본은 git 에 넣지 않는다(`.gitignore` 의 `intake/*/`). 커밋하는 것은 이 문서와 감사 보고서(`audit/intake/`)뿐이다.

## 1. 어디에 두나

```
intake/<이름>/            # 소문자-하이픈. 예: blog, vitrine-web
  CLAUDE.md, CLAUDE.local.md(있으면), GEMINI.md, AGENTS.md
  .claude/                # rules, skills, agents, settings.json, conventions·todos 등
  <소스 일부>             # 원래 상대 경로를 지켜서(cp --parents)
  INTAKE.md               # 반입 기록(아래)
```

- 원래 디렉터리 구조를 지킨다. rules `paths` glob 과 스킬 링크가 상대 경로로 맞아야 `RULE-DEADGLOB`·`SKILL-NEST` 판정이 의미 있다.
- 저장소 하나에 디렉터리 하나. 같은 프로젝트를 다시 가져오면 `<이름>-<YYYYMMDD>/` 로 나란히 둔다(전후 비교용).

## 2. 무엇을 가져오나

| 우선 | 가져올 것 | 왜 |
|---|---|---|
| 꼭 | `CLAUDE.md` 계층(루트, `.claude/CLAUDE.md`, 하위 디렉터리 것), `.claude/` 전체, `GEMINI.md`·`AGENTS.md` | 코어 검사 대상 |
| 꼭 | 툴킷 감지 표식: `package.json`(+lock 한 개), `tsconfig*.json`, `mise.toml`, `Cargo.toml`, `stylua.toml`, `.luaurc`, `default.project.json`, 린터·포매터 설정 | 툴킷 감지와 툴체인 검사 |
| 권장 | rules `paths` 가 겨냥하는 소스 폴더 일부(폴더마다 파일 몇 개), 게이트 스크립트(`scripts/check.sh` 등) | glob 판정, 문서↔명령 대조 |
| 권장 | 감사자에게 볼 코드: 바뀐 파일이나 핵심 모듈 | `/audit` 대상 |
| 선택 | `git log --stat -20` 출력(`INTAKE.md` 에 붙임) | 낡음 판정에 쓸 날짜. 반입 사본에는 git 이력이 없다 |

- **web 반입 때 확인할 것**: 블로그(react/astro)를 가져오면 `scan.py` 의 `WEB-PLUGINS`·`WEB-RULE` 정보가 나오는지 보고, 프로젝트 `.claude/settings.json` 에 `handoff/vitrine.md` 의 `enabledPlugins` 조각과 frontend-design 명시 호출 줄이 있는지 대조한다.

가져오지 않는 것
- **자격 증명과 비밀**: `.env*`, `*.pem`, `*.key`, `id_*`, `.credentials.json`, `.npmrc`·`.pypirc` 의 토큰, `settings.local.json` 안의 키, 클라우드 설정(`.aws/`, `.config/gcloud/`).
  반입 뒤에도 한 번 훑는다: `grep -rIlE '(api[_-]?key|secret|token|password)\s*[:=]' intake/<이름>` — 걸리면 그 파일을 지우고 `INTAKE.md` 에 적는다.
- 의존성·생성물·캐시: `node_modules/`, `dist/`, `.astro/`, `target/`, `luau_packages/`, `Packages/`, `.claude/cache/`, `.coderag/`
  (git 이 없는 반입 사본은 scan 이 무시 파일까지 걷는다. 캐시가 오면 `DRIFT-TYPEDEFS` 같은 오탐이 난다).
- `.git/` (넣으면 scan 이 별개 저장소로 보고 git 검사를 돌린다. 반입은 "git 없는 사본"으로 다룬다).
- `.claude/worktrees/`, 세션 기록(`projects/`, `session/`).

`INTAKE.md` 에 적을 것: 원본 위치(호스트·경로·커밋), 반입 날짜, 가져온 범위와 뺀 것, 원본 sandbox 의 환경 차이(툴체인 경로, 래퍼, push 정책), 감사 목적.

## 3. git 에 넣을지

- 기본: **넣지 않는다.** `intake/*/` 는 `.gitignore` 로 제외된다. `git status` 에 나오지 않는 것을 확인한다: `git check-ignore -v intake/<이름>/CLAUDE.md`.
- 커밋하는 것: 감사 보고서 `audit/intake/<이름>-<YYYY-MM-DD>.md`. 보고서에는 인용한 줄만 넣고 파일 통째 사본은 넣지 않는다.
- 다 쓴 사본은 사용자가 지운다(에이전트는 지우지 않고 `HUMAN_TODO.md` 에 올린다).

## 4. 감사 순서

1. **반입 확인**: 위 2절의 비밀 검사, `INTAKE.md` 작성.
2. **환경과 툴킷 감지**:
   ```bash
   python3 -I ~/.claude/skills/harness-doctor/scripts/scan.py --env
   python3 -I ~/.claude/skills/harness-doctor/scripts/scan.py intake/<이름> --only 1      # 머리의 "툴킷:" 줄 확인
   ```
   감지가 틀리면 `--toolkits web` 처럼 강제하고, 감지 표식이 빠진 이유(설정 파일을 안 가져옴 등)를 `INTAKE.md` 에 적는다.
3. **harness-doctor**: `/harness-doctor intake/<이름>`.
   - git 이 없는 사본이라 `SET-NOGIT`(정보)이 나오고 7번의 git 검사, 9번 worktree 는 건너뛴다. `STALE-AGENTDOC-OLD` 처럼 커밋 날짜가 필요한 판정도 나오지 않는다.
   - 형제 비교(`TOOL-PIN`, `TOOL-CLAIM`, `DRIFT-SKILLCOPY`)의 기본 형제는 `intake/` 의 다른 사본이다. 이 작업공간과 비교하려면 `--projects <작업공간>`.
   - 고칠 안의 처리 방식은 `반입 원본에 전달` 이다. 사본을 고쳐 봐야 원본에 가지 않는다. 고친 문장·diff 를 보고서에 적어 원본 세션에 넘긴다.
4. **감사 에이전트**(설치 후, `drafts/agents/README.md`): 반입 디렉터리에서 `/audit <관점> intake/<이름>/<경로>`.
   - 사본은 git 이 없다. `/audit` 0단계 가드(HEAD·status 해시)는 `find intake/<이름> -type f -newer intake/<이름>/INTAKE.md` 로 바꿔 본다.
   - 실행이 필요한 관점(types, runtime, perf)은 그 툴킷 툴체인이 이 sandbox 에 있어야 한다. 없으면 `미완`으로 두고 이유를 적는다.
   - 무거운 실행은 이 환경의 래퍼(`HARNESS_HEAVY_WRAP`)로 감싼다.
5. **보고서**: `audit/intake/<이름>-<YYYY-MM-DD>.md` 에 scan 집계, 판정, 고칠 안, 툴킷 검사 후보(web 골격을 채울 재료 — `references/toolkits/web.md` "채우는 순서")를 적는다.
