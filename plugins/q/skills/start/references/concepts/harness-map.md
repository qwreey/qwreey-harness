# 하네스 지도 — 장치들이 어떻게 맞물리나

> 한 줄: "하네스" 는 모델(Claude) 바깥에서 **무엇을 보여 주고, 무엇을 하게 하고, 무엇을 막는지** 정하는 장치 전체다. 말(馬)에 씌우는 마구에서 온 말이다.

## 그림으로
```
 회사 관리 설정 · 관리 CLAUDE.md   ← IT 가 배포. 내가 못 끈다
          │
 ┌────────┴──────────── Claude Code (프로그램) ─────────────────┐
 │  항상 책상에 올림      필요할 때 올림        자동으로 돌거나 막음 │
 │  - CLAUDE.md          - rules(paths)       - 권한 설정·모드      │
 │  - auto memory        - 스킬 본문           - hooks              │
 │  - 스킬 이름·설명      - 하위 폴더 CLAUDE.md  - auto mode 검사 모델 │
 │  - MCP 도구 이름       - subagent 결과                            │
 └────────┬──────────────────────────────────────────────────────┘
          │  plugins = 위 것들(스킬, 훅, subagent, MCP)을 묶은 꾸러미
          ▼
        모델(Claude) ── 대화 · 파일 읽기 · 명령 실행
```

## 세 가지 성격으로 나누기
| 성격 | 장치 | 특징 |
|---|---|---|
| **권고** (Claude 가 읽고 판단) | CLAUDE.md, memory, rules, 스킬 | 싸고 유연하다. 대신 100% 지켜지지 않는다 |
| **강제** (프로그램이 막음) | 권한 규칙(allow/ask/deny), hooks, 관리 설정 | 반드시 지켜진다. 대신 융통성이 없다 |
| **분리** (따로 일함) | subagent, 별도 세션 | 내 책상을 깨끗하게 지킨다. 비용은 따로 든다 |
- 공식 권고: "매번 꼭 일어나야 하는 일은 훅, 거부 규칙, 관리 설정으로. CLAUDE.md 는 가이드라인이다."

## 어디에 두나 (범위)
| 범위 | 위치 예 | 누구에게 |
|---|---|---|
| 회사 | 관리 설정, 관리 CLAUDE.md | 회사 모든 사람 |
| 나 | `~/.claude/` (CLAUDE.md, rules, skills, settings.json) | 내 모든 프로젝트 |
| 프로젝트 | 저장소의 `CLAUDE.md`, `.claude/` | 그 프로젝트를 여는 모든 사람 |
| 나+프로젝트 | `CLAUDE.local.md`, `.claude/settings.local.json` | 그 프로젝트에서 나만 |

## 좋은 하네스의 원칙 (이 프로젝트가 배운 것)
1. **쌓지 말자.** 규칙·훅·스킬이 늘수록 상시 비용과 관리 부담이 커진다. 공식 도구로 되는 건 공식 도구로.
2. **항상 읽히는 것은 짧게,** 긴 지식은 필요할 때 읽히는 곳(스킬, paths rules)으로.
3. **꼭 지켜야 하는 것만 강제**한다. 취향을 훅으로 막으면 오히려 방해다.
4. 모델이 바뀌면 규칙 없이도 잘 하는지 다시 재 보고, 필요 없어진 규칙은 걷는다.

## 각 장치 설명
- `context.md`, `memory.md`, `rules.md`, `skills.md`, `hooks-and-reminders.md`, `plugins.md`, `subagent.md`, `auto-mode.md`

## 직접 확인하기
- `/context` (항상 올라간 것), `/memory` (메모 파일), `/skills` (스킬 목록), `/hooks` (훅), `/permissions` (권한 규칙), `/plugin` (플러그인)

## 이해 확인 질문 (설명 뒤 하나만 골라 묻는다)
- '권고' 와 '강제' 장치를 하나씩 들어 보세요.
- 꼭 지켜야 하는 규칙은 CLAUDE.md 와 훅 중 어디에 두나요?

## 근거
- 공식: code.claude.com/docs/en/context-window (시작 시 로드 목록), features-overview, memory (범위 표, 관리 CLAUDE.md), best-practices ("make it a hook, a deny rule, or a managed setting")
- 이 프로젝트: qwreey-harness .claude/audit/19-external/00-synthesis §0, §2.1 ("쌓기" 위험, 규칙 없이 재기)
