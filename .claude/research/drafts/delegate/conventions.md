# 접미 디렉터리 명명 규약과 외부 모델 진입점

2026-11-10 제안. 지금은 어느 문서에도 정의가 없다(`audit/04` §1).

## 1. `/code/Projects/<repo>-<접미>/` 규약

원칙
- 접미 디렉터리는 **git 밖**이다.
- **누가 쓰는지**(도구 / 사람과 메인 세션)와 **얼마나 사는지**(과제 동안 / 보존)로 나눈다.
- 저장소 안의 문서는 접미 디렉터리를 **근거로 인용하지 않는다.** 근거가 필요하면 그 파일을 저장소 안(`.claude/audit/…`, `spikes/`)으로 옮겨 커밋하고 그 경로를 인용한다. clone하면 저장소 밖 경로는 사라지기 때문이다.

| 접미 | 정의 | 누가 만들고 지우나 | 안의 꼴 | 수명 |
|---|---|---|---|---|
| `-agy` | Gemini(agy) 위임 작업공간 | `delegate.sh`만. 손으로 만들거나 고치지 않는다 | `<이름>/`(detached worktree, 그 저장소 uid 소유), `.homes/<이름>/`, `.hooks/pre-push`, `runs/<YYYYMMDD-HHMM>-<이름>/` | `<이름>/`과 `.homes/<이름>/`은 과제 동안(remove가 지움). `runs/`는 보존 |
| `-codex` | OpenAI codex 위임 작업공간 | 같음 | 같은 꼴. empty 모드면 `<이름>/`이 worktree가 아니라 빈 디렉터리 | 같음 |
| `-scratch` | 사람과 메인 세션의 일회성 실험(프로브 `.luau`, 측정 로그, 참고 저장소 클론) | 메인 세션 또는 사용자 | `<YYYY-MM-DD>-<slug>/`, 참고 클론은 `refs/<이름>/` | 버려도 되는 것만. 남길 가치가 생기면 저장소 안으로 옮긴다 |
| `-proto` | 메인 세션이 직접 고치는 **시제품 가지의 worktree** | 메인 세션(`git worktree add ../<repo>-proto/<slug> -b proto/<slug>`) | `<slug>/` ↔ 브랜치 `proto/<slug>` | 가지가 합쳐지거나 버려지면 `git worktree remove` |
| (저장소 안) `.claude/worktrees/` | Claude Code 하네스(`claude --worktree`, `isolation: worktree`)의 몫 | 하네스 | — | 하네스가 정리. `.gitignore`에 `/.claude/worktrees/` 필수(`audit/04` §5.1) |

현재 상태와의 차이(옮기는 법은 `migration.md`)
- `stl-luau-scratch/no-self-return/wt`는 실제 worktree(`proto/no-self-return`)라 규약상 `stl-luau-proto/no-self-return`이 맞다. 빈 `stl-luau-proto/`는 원래 이 용도로 만든 자리로 보인다.
- `quad-codex/naming-*`는 옛 수동 기록이다. 규약상 `quad-codex/runs/<날짜>-<이름>/`이 맞다.
- `quad-scratch/quad`(quad 저장소 사본 158MB)는 `-scratch`의 정의(버려도 되는 실험) 밖이다. 같은 저장소의 다른 시점이 필요하면 `-proto` worktree를 쓴다.
- `-scratch` 안에 worktree를 두지 않는다. `git worktree list`로 찾을 수 있게, worktree는 `-agy`, `-codex`, `-proto`, `.claude/worktrees/` 넷에만 둔다.

이 표는 사용자 레벨 `~/.claude/CLAUDE.md`에 세 줄로 들어간다(PLAN ①). 예:

```
- 형제 디렉터리: <repo>-agy / -codex = delegate 스킬 작업공간(손대지 않음), <repo>-scratch = 일회성 실험(근거로 인용 금지 — 남길 것은 저장소 안으로),
  <repo>-proto/<slug> = 브랜치 proto/<slug> 의 worktree. worktree 는 이 넷과 .claude/worktrees/ 에만 둔다.
```

## 2. GEMINI.md와 AGENTS.md

### 사실

- agy는 cwd에서 저장소 루트까지 올라가며 **`GEMINI.md`와 `AGENTS.md`를 둘 다** 싣는다. 파일당 24,000바이트 상한이 있고, `@[label](path)` include를 펼친다(`/code/.gemini/antigravity-cli/builtin/skills/agy-customizations/docs/rules.md`).
- codex는 `AGENTS.md`를 싣는다(codex 표준). 단, `--ignore-user-config`과 빈 디렉터리(empty 모드)에서는 실을 것이 없다.
- Claude Code는 `CLAUDE.md`를 싣는다. `@AGENTS.md`로 import하면 그 내용이 **항상 로드**되어 비용이 그대로 든다(`audit/01` §1).
- 지금은 stl-luau에만 `GEMINI.md`(8.1KB)가 있고, quad는 `.claude/qa-request/external-review-entry.md`를 사용자가 손으로 붙여 넣는다. stl-luau `GEMINI.md`는 결정(AB, BD)을 다시 적었다가 낡았다.

### 제안

1. **프로젝트마다 `AGENTS.md` 하나만 둔다. `GEMINI.md`는 없앤다.** 둘 다 있으면 agy가 둘 다 싣는다. `delegate.sh doctor`가 이것을 경고한다.
2. **`AGENTS.md`는 지식이 아니라 지도다**(`templates/AGENTS.md.template`, 6KB 이하).
   - 담는 것: 정본 경로 목록, 기보고 위치, 검사 명령, 그 저장소만의 함정, 전체 감사 진입점 포인터
   - 담지 않는 것: 결정, 구조, 타입 모양. 이런 것을 다시 적으면 낡는다.
   - 같은 지식을 가리키는 방식: 지식의 정본은 Claude가 쓰는 `CLAUDE.md`, `.claude/conventions.md`, `.claude/rules/*.md`, 설계 문서 그대로다. `AGENTS.md`는 그 경로만 나열한다. 외부 모델이 같은 파일을 직접 읽는다.
3. **역할과 보고 규칙은 프로젝트 파일에 쓰지 않는다.** "다른 시선, 좁은 질문, 실측/추정, 제안은 결정이 아님" 같은 공통 규칙은 `delegate` 스킬의 머리말이 매번 붙인다. 프로젝트 넷이 같은 문단을 따로 고치던 문제(`delegate-agy/SKILL.md` 유사도 0.16~0.24)가 이렇게 사라진다.
4. **Claude 쪽은 `AGENTS.md`를 import하지 않는다.** 대신 `doc-check`(있으면)나 `/doctor prompt-audit`이 `AGENTS.md`의 경로가 실제로 있는지 검사하게 한다. 지도에는 경로만 있으므로 낡을 수 있는 것도 경로뿐이다.
5. **공용 Luau 지식**은 `luau-kb/AGENTS.md`(PLAN ②)에 둔다. 프로젝트 `AGENTS.md`는 그 절대 경로를 한 줄로 가리킨다. `/code/Projects`는 755라 무권한 uid도 읽을 수 있다. include(`@[…](…)`)로 펼치지 않는 이유는 24KB 상한과 규칙 예산(20k 토큰)을 프로젝트 몫으로 남기기 위해서다.
6. **quad의 `external-review-entry.md`는 그대로 둔다.** 이 파일은 "전체 감사" 절차서이고, 진입점과는 역할이 다르다. quad `AGENTS.md`의 마지막 절이 그것을 가리킨다. 그 파일 0절("이번 감사의 초점")이 시점에 묶여 있다는 점은 그 파일 스스로 밝히고 있다.

### 저장소별 초안 방향

| 저장소 | 지금 | 할 일 |
|---|---|---|
| stl-luau | `GEMINI.md` 8.1KB(낡음: AB, BD를 확정으로 서술) | `AGENTS.md`로 새로 쓴다. "무엇인가"의 src 목록, 확정된 결정 절, 사고 서술은 빼고 정본 경로만 남긴다(P0 ⑤를 이 작업으로 대신함). "좁은 질문만" 원칙은 스킬 머리말과 SKILL "언제"로 옮겨졌다 |
| quad | 없음(external-review-entry.md) | `AGENTS.md` 새로 쓴다. 정본 우선순위(`base/` > 나머지), 원장 README, test.sh exit code, relink 함정, 전체 감사는 entry로 |
| table-sim | 없음(머리말에 vendor, Studio) | `AGENTS.md`: vendor 읽기 예외, `tests/run.luau`, `src/server`·`src/client`는 추정만 |
| tbox | 없음(머리말에 검사 명령) | `AGENTS.md`: `luau packages/tbox/test/run.luau`, `lute run scripts/analyze.luau`, Roblox 전역은 mock |
