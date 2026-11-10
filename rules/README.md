# rules — 경로 조건부 공통 규약

여러 Luau 저장소가 함께 쓰는 `paths:` 조건부 규칙 파일을 둔다. 정본은 이 디렉터리이고, 사용자 레벨 `~/.claude/rules/` 에는 심볼릭 링크로 건다(claude-doctor `home/MANIFEST` 의 `link rules/<파일> …` 줄).

| 파일 | paths | 줄 수 | 근거·예시 |
|---|---|---|---|
| `luau-core.md` | `**/*.luau` | 38 | `skills/luau-style/references/` (각 줄 끝 링크) |
| `code-structure.md` | `**/*.{luau,lua}` | 9 | **안내만 둔다.** 구조 규칙(D-13 확정)은 툴킷과 무관해서 정본이 사용자 레벨 `~/.claude/rules/code-structure.md`(claude-doctor `home/.claude/rules/code-structure.md`, MANIFEST 관리 파일)로 옮겨 갔다. 이 파일은 MANIFEST 로 링크하지 않는다. 플러그인을 읽지 않는 에이전트에게 정본 위치와 Luau 세부(`skills/luau-style/references/structure.md`·`splitting.md`, 입구 `init.luau`)만 알려 준다 |

## 작성 규칙
- frontmatter 에 `paths` 를 반드시 단다. 없으면 매 세션 항상 로드되어 비용이 그대로다.
- 한 줄에 규칙 하나, 명령형으로 쓰고 줄 끝에 근거 reference 링크를 붙인다. 근거와 사실은 references 에 두고 다시 쓰지 않는다.
- 링크는 `../skills/luau-style/references/X.md` 상대 경로다. 이 저장소 안에서도, `~/.claude/rules/` 와 `~/.claude/skills/luau-style` 이 나란히 링크된 사용자 홈에서도 같은 파일을 가리킨다.
- 파일 하나를 40줄 이하로 둔다.
- 정책이 갈린 항목은 사용자 결정 전에는 규칙으로 만들지 않는다. 이견 없는 공통분만 넣는다(아래).

## `luau-core.md` 각 줄의 출처 (2026-11-10)
사용자 확정 결정(claude-doctor `decisions/README.md` "사용자 결정 현황")과 충돌하지 않는 줄만 넣었다.
- **확정 결정**: `const` 사용과 파일 안 일관성(D-01), stylua 루트 실행·`<<` diff(D-02), 게이트 exit code·stderr(D-06).
- **일곱 저장소가 이미 일치하는 공통분**: 네이밍 다섯(D-09 의 이견 없는 부분), 식별자·에러 메시지 영어와 "파일의 주석 언어 따르기"(D-08 의 이견 없는 부분), 에러 리터럴, `@self`·리터럴 경로·엔트리 이름·실제 require 테스트(D-12 의 이견 없는 부분).
- **언어 사실에서 나온 줄**(스니펫으로 재현): `local const`, `(` 문장, `and/or` 삼항, 맨 `function`, `error(e, 0)` 되던지기, `pcall(f(x))`.
- **넣지 않은 것**(제안 상태라 스킬에만 `> 정책: 제안(D-xx)` 으로 둠): 새 파일의 주석 언어(D-08), 네임스페이스 함수 케이스·새 저장소 기본값(D-09), 라이브러리 raise 헬퍼 의무화와 줄 단언 테스트(D-10 — rules 에는 "헬퍼가 있으면 쓴다"만), 필드 읽기(D-11), `@game/`(D-12), 코드 `TODO`(D-07), 버전 명시(D-05).

## 심볼릭 링크로 건 rules 가 로드되는가 (실측 2026-11-10, Claude Code 2.1.316, `claude -p --model sonnet`)

임시 프로젝트 넷을 만들고 각각 `mod.luau` 를 Read 하게 한 뒤, `stream-json` 출력에 규칙 본문이 붙었는지와 모델의 답을 봤다. 프로젝트는 각자 `git init` 한 디렉터리이고 작업 디렉터리도 그곳이다.

| 프로젝트 `.claude/rules/luau-core.md` | 규칙 로드 |
|---|---|
| 실제 파일(복사본) | **로드됨** (Read 직후 system reminder, 첫 줄을 그대로 인용) |
| 프로젝트 **안** 파일을 가리키는 symlink(`../../shared/luau-core.md`) | **로드됨** (reminder 의 경로는 링크 대상 `shared/luau-core.md` 로 표시) |
| 프로젝트 **밖**(`/code/Projects/luau-kb/rules/luau-core.md`)을 가리키는 symlink | **로드 안 됨** (모델 답 "NONE") |
| 규칙 없음(대조군) | 로드 안 됨 |

공식 문서(code.claude.com/docs/en/memory, 2026-11-10 확인)와 일치한다.
- "Claude Code treats a symlink whose target is outside your working directory like an external import. The linked rules don't load until you approve external imports for the project, and after that only the ones without a `paths` field load."
  - 승인 대화상자는 대화형 세션을 시작할 때만 뜬다. 그래서 `-p` 에서는 승인할 길이 없다.
  - 문서대로라면 **승인해도 `paths` 가 있는 외부 symlink 규칙은 로드되지 않는다.** 그래서 `luau-core.md` 를 프로젝트 `.claude/rules/` 에 외부 symlink 로 거는 방식은 쓸 수 없다.
- 사용자 레벨은 다르다: "To load shared rules without that approval, keep them in `~/.claude/rules/`". `~/.claude/rules/` 의 파일은 사용자가 쓴 것으로 보고 대화상자 없이 신뢰한다.
  - 예외는 데스크톱 Cowork 세션이다. 거기서는 작업 디렉터리 밖을 가리키는 symlink 규칙 파일·디렉터리를 건너뛴다.
- 결론: 배포는 **사용자 레벨 `~/.claude/rules/luau-core.md` → 이 저장소 파일** symlink 로 한다(MANIFEST 의 `link` 줄).
  - 사용자 레벨 symlink 의 로드는 문서 근거만 있고 이번에 재지 않았다. 실제 홈 설정을 바꾸지 않기 위해서다.
  - home-sync 로 링크를 건 뒤 `.luau` 파일 하나를 Read 하는 `claude -p` 한 번으로 확인한다.
  - 특정 저장소에만 걸고 싶으면 링크 대신 복사본이나 프로젝트 안 파일을 쓴다.
