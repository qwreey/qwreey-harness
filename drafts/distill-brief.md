# 증류 공통 지침 (luau-kb 로 지식 옮기기)

모든 증류 에이전트가 따른다. 2026-11-10.

## 원천
- 후보표
  - `audit/08-quad-knowledge-mine.md` (ID `Q-`)
  - `audit/09-other-knowledge-mine.md` (ID `S- R- T- D- X- M- O-`, perf 절 분할안 §1, 모순 §6, 낡음 §7)
  - `audit/11-knowledge-gaps.md` + `drafts/gaps/*.md` 와 `drafts/gaps/snippets/` (공백 초안 6개, 스니펫 41개)
  - `drafts/style/` (luau-style 스킬 초안, `rules/luau-core.md`, inventory)
  - `decisions/README.md` 와 D-xx. 맨 끝의 "사용자 결정 현황" 표가 권위 있는 상태다.
    - 확정: D-01, D-02, D-03, D-04, D-06
    - D-10 은 정정이 있다
    - 나머지는 '제안' 상태다
- 원천 저장소(quad, stl-luau, rbvm, table-sim, devplorer, tbox 등)는 **읽기 전용**이다. 근거 원문을 확인할 때만 연다.
  - 다른 Claude 세션이 상주하므로 쓰기와 git 조작을 하지 않는다.

## luau-kb 형식 (기존 스킬과 같게)
- `SKILL.md` 는 100줄 이하로 둔다. 결정 트리와 '증상/질문 → 파일' 라우팅 표만 넣는다.
- description 은 3인칭으로 '무엇 + 언제' 를 쓰고 1,536자 이하로 둔다.
- `references/` 는 1단계 깊이만 둔다. 각 파일은 다음 구조를 따른다.
  - 맨 위에 목차와 "이 파일이 답하는 질문"
  - 각 절에 `status: verified|described`, `last-confirmed: <도구 버전>`, 근거(스니펫 ID 또는 원천 경로:줄, 후보 ID)
- 원문을 옮기지 말고 **자기설명적으로 다시 쓴다.** 프로젝트 고유 설계(Quad API, stl 트레이트 등)는 빼고, 그 설계의 이유가 된 일반 사실만 남긴다.
- 후보 ID(Q-018 등)를 근거로 남겨 역추적할 수 있게 한다.

## 스니펫
- 실행 가능한 주장은 `luau-kb/snippets/<접두>-*.luau` 로 둔다.
- 접두는 담당별로 고정한다.

  | 접두 | 담당 |
  |---|---|
  | `perf-` | luau-perf |
  | `rbx-` | roblox-luau |
  | `style-` | luau-style |
  | `test-`, `pack-`, `opt-`, `native-` | testing·types·verify |

- 순수 Luau 검사: `python3 -I tools/check_snippets.py --luau 0.734,0.742 snippets/<내 접두>-*.luau` 가 rc=0 이어야 한다.
- Roblox 타입 스니펫은 `drafts/gaps/tools/check_roblox.py` 방식으로 검사한다. 이 검사기를 `check_snippets.py` 에 통합하는 일은 '검증·타입·테스트' 담당만 한다.
- `snippets/RESULTS.md` 는 공용 파일이다. 자기 접두 절만 추가하고 다른 절은 건드리지 않는다.
- 무거운 실행(벤치)은 `choom -n 1000 --` 으로 감싼다.

## 모순과 낡음
- 원천끼리 결론이 다르면 먼저 조건 차이(버전, `-O` 수준, native, Deferred/Immediate 모드, 엔진 대 mock)로 설명되는지 본다.
  - 설명되면 조건을 명시해서 둘 다 적는다.
  - 설명되지 않으면 재현해서 판정한다.
  - 정책 문제라면 `claude-doctor/decisions/D-xx` 새 파일로 올린다(합의안 형식).
- 원천 서술이 재현해 보니 틀렸으면 그 파일의 '정정' 절에 원천 경로와 함께 모은다(각 저장소 세션에 전달할 용도).

## 커밋과 경계
- luau-kb 에 커밋한다. `git add` 는 **자기 담당 경로만** 한다.
- `index.lock` 이 있으면 잠시 기다렸다가 재시도한다.
- 메시지 끝에 `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` 를 붙인다. push 는 하지 않는다.
- 새 스킬을 만들면 `claude-doctor/home/MANIFEST` 에 다음 형식으로 링크 한 줄을 추가한다.
  `link skills/<name> /code/Projects/luau-kb/skills/<name>`
- 스킬의 실효성은 **sonnet** 으로 확인한다. haiku 는 쓰지 않는다.
  - 방법: `claude -p --model sonnet` 로 질문 2~3개를 던져 Skill 이 호출되는지 본다(stream-json).
