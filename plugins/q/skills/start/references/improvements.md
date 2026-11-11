# 개선안 목록

진단 결과와 역할에 맞는 것을 최대 3개 고른다. 한 번에 하나씩 SKILL.md 5단계 틀로 제안하고, "예" 를 받은 것만 적용한다.
**공통 규칙**
- 진단 11번에서 사내 하네스(claude-doctor 정본)가 보이면 `~/.claude` 를 직접 고치지 않는다. "정본 담당자에게 이 내용을 요청" 으로 바꿔 제안하고, 요청 문안만 보여 준다.
- 기존 파일을 고칠 때는 먼저 `<파일>.bak-<YYYYMMDD>` 백업을 만든다고 제안 단계에서 미리 말한다.
- 사용자가 직접 해야 하는 일(Studio 설정, `/statusline`, `Shift+Tab`)은 "이렇게 해 보세요" 로 안내만 한다. 대신 실행하지 않는다.

| 코드 | 이름 | 언제 고르나 | 누구에게 |
|---|---|---|---|
| A | 동의 원칙 넣기 | 내 CLAUDE.md·rules·관리 CLAUDE.md 어디에도 동의 원칙이 없을 때. **늘 첫 번째** | 모두 |
| B | CLAUDE.md 줄이기 계획 | CLAUDE.md 가 200줄 넘을 때 | 개발자 |
| C | MEMORY.md 정리 | 160줄·20KB 넘거나 낡은 줄이 보일 때 | 모두 |
| D | `# Compact instructions` 절 | 개발자이고 긴 작업을 자주 할 때, 프로젝트 CLAUDE.md 에 그 절이 없을 때 | 개발자 |
| E | 상태줄에 컨텍스트 사용량 | 컨텍스트 개념을 처음 배웠을 때 | 모두 |
| F | luau-kb 플러그인 | Luau 저장소(`*.luau`, `default.project.json`)인데 luau-kb 가 없을 때 | Luau 개발자 |
| G | Studio MCP 연결 | Roblox 작업자인데 Studio MCP 연결이 없을 때 | Roblox 작업자 |
| H | 작업 전용 폴더·백업 습관 | 작업 폴더가 홈·바탕화면·다운로드이거나 git 이 아닐 때 | 비프로그래머 |
| I | 권한 모드 확인 | `bypassPermissions` 이거나, 비프로그래머가 중요한 폴더에서 auto 로 일할 때 | 모두 |
| J | 세션 기록(q 플러그인의 session-log 훅) | 개발자이고 한 일을 여러 세션에 걸쳐 할 때 | 개발자 |

## A. 동의 원칙 넣기
- 둘 중 **하나만** 고른다(둘 다 넣으면 같은 말이 두 번 읽힌다).
  1. 권장: `${CLAUDE_SKILL_DIR}/templates/rules/consent.md` 를 `~/.claude/rules/consent.md` 로 복사. 따로 떼어 있어 지우기 쉽다.
  2. `${CLAUDE_SKILL_DIR}/templates/CLAUDE.fragment.md` 의 내용을 `~/.claude/CLAUDE.md` 끝에 붙이기(파일이 없으면 새로 만들기).
- 미리보기로 템플릿 전문을 보여 준다. 상시 비용: 약 15~25줄.
- 되돌리기: 복사한 파일을 지우거나, 붙인 절을 지운다(백업 있음).
- 회사가 관리 CLAUDE.md 로 이미 배포했으면 고르지 않는다.

## B. CLAUDE.md 줄이기 계획
- 이번에는 **계획만** 보여 준다: 어느 절을 (1) paths rules 로, (2) 스킬로, (3) 지워도 되는지 표로.
- 실제 옮기기는 절 하나씩 따로 동의받는다. 팀이 함께 쓰는 프로젝트 CLAUDE.md 면 "팀에 먼저 공유" 를 권한다.

## C. MEMORY.md 정리
- 낡았거나 겹치는 줄 후보를 번호로 보여 주고, 사용자가 고른 번호만 지우거나 합친다.
- 지우기 전에 백업. 사용자가 "다 알아서" 라고 해도 후보 목록을 확인받는다.

## D. Compact instructions
- 프로젝트 CLAUDE.md 끝에 3~5줄 추가. 예:
  ```
  # Compact instructions
  요약할 때 사용자가 내린 지시와 금지 사항은 원문 그대로, 결정과 그 이유, 남은 할 일, 고친 파일 목록을 남긴다. 끝난 탐색 과정은 줄인다.
  ```
- 팀 공용 파일이면 B 와 같은 주의.

## E. 상태줄 컨텍스트 사용량
- 사용자가 직접 `/statusline` 을 입력하고 "컨텍스트 사용량 % 를 보여 줘" 라고 하면 된다고 안내한다(설정 파일을 바꾸므로 그 대화에서 다시 확인이 나온다).

## F. luau-kb 플러그인
- 명령(동의 후):
  `claude plugin marketplace add <luau-kb 저장소 주소>` → `claude plugin install luau-kb@luau-kb-market --scope project`
- `--scope project` 는 이 프로젝트 설정(`.claude/settings.json`)에 기록되어 팀원에게도 권장된다. 나만 쓰려면 `--scope local`. 어느 쪽인지 묻는다.
- 저장소 주소를 모르면 담당자에게 물으라고 한다(추측하지 않는다).

## G. Studio MCP 연결
- Studio 쪽: Assistant → … → Manage MCP Servers → Enable Studio as MCP server → Quick connect 에서 Claude Code (사용자가 직접).
- Claude Code 쪽 등록을 수동으로 해야 하면 `claude mcp add` 명령을 미리 보여 주고 동의 후 실행. 경로는 `roblox.md` 참고.
- 바꾸는 도구는 저장 후·혼자 쓸 때만 쓴다는 약속을 같이 안내한다.

## H. 작업 전용 폴더·백업 습관
- 파일을 바꾸지 않는 안내다. "다음부터는 `작업폴더` 를 하나 만들고 그 안에서 Claude 를 여세요", "큰 변경 전 폴더 복사" 를 권한다.
- 폴더를 대신 만들어 주겠다고 하면 그것도 쓰기이므로 동의 후.

## I. 권한 모드 확인
- `bypassPermissions` 가 기본으로 잡혀 있으면 문제로 보고하고, 설정에서 지우거나 `auto`/`default` 로 바꾸는 안을 낸다(설정 변경, 동의 필수).
- 비프로그래머에게는 "중요한 폴더에서는 `Shift+Tab` 으로 manual mode 로 바꿔 하나씩 확인" 을 안내만 한다.

## J. 세션 기록 (q 플러그인에 들어 있음)
- 하는 일: 세션을 백그라운드에서 요약해 저장소 밖에 쌓고, 다음 세션에서 이어받게 한다.
- 비용·주의: 요약에 별도 모델 호출(haiku)이 든다. 기록은 이 컴퓨터에 남는다.
- 명령(동의 후): q 가 이미 설치돼 있으면 따로 깔 것이 없다(훅은 q 가 켜져 있으면 돈다). 끄려면 환경 변수 `SESSION_LOG_DISABLE=1`. q 가 없으면 `claude plugin marketplace add <claude-doctor 저장소 주소>` → `claude plugin install q@claude-doctor-market`
