# handoff

State handed to the next session or another repo's session (snapshots). Generated table.

<!-- coderag:begin -->
| Document | Description | Status |
|---|---|---|
| [claude-doctor 자신에 대한 정정 (2026-11-10)](claude-doctor-corrections.md) | luau-kb 증류에서 재현해 보니 claude-doctor 의 결정 문서·후보표·초안 서술이 틀렸거나 낡은 것들이다. 메인 세션이 반영한다. 근거 경로는 `/code/Projects/claude-doctor/packs/luau-kb/` 기준이다. 심각도 행동: rules·결정·후보표… | no frontmatter |
| [devplorer 세션에게: luau-kb 증류에서 나온 정정 (2026-11-10)](devplorer-corrections.md) | luau-kb 가 devplorer 의 서술을 더 새 실측·문서와 대조해 보니 틀렸거나 낡은 것들이다. 반영 여부는 devplorer 세션이 판단한다. 줄 번호는 2026-11-10 에 `/code/Projects/devplorer` 를 읽기 전용으로 열어 확인했다. 근거 경로는 `/… | no frontmatter |
| [VideoSync 세션에게: 메모리 분류 인계 (읽기 전용 감사)](memory-VideoSync.md) | claude-doctor 의 `.claude/audit/23-memory-portability.md` §6 에서 나왔다. `/code/.claude/projects/-code-Projects-VideoSync/memory/` 의 항목을 읽기만 했고 아무것도 고치거나 옮기지 않았다. 저… | no frontmatter |
| [claude-doctor 세션에게: 메모리 분류 인계 (읽기 전용 감사)](memory-claude-doctor.md) | claude-doctor 의 `.claude/audit/23-memory-portability.md` §6 에서 나왔다. `/code/.claude/projects/-code-Projects-claude-doctor/memory/` 의 항목을 읽기만 했고 아무것도 고치거나 옮기지 않았… | no frontmatter |
| [devplorer 세션에게: 메모리 분류 인계 (읽기 전용 감사)](memory-devplorer.md) | claude-doctor 의 `.claude/audit/23-memory-portability.md` §6 에서 나왔다. `/code/.claude/projects/-code-Projects-devplorer/memory/` 의 항목을 읽기만 했고 아무것도 고치거나 옮기지 않았다. 저… | no frontmatter |
| [quad 세션에게: 메모리 분류 인계 (읽기 전용 감사)](memory-quad.md) | claude-doctor 의 `.claude/audit/23-memory-portability.md` §6 에서 나왔다. `/code/.claude/projects/-code-Projects-quad/memory/` 의 항목을 읽기만 했고 아무것도 고치거나 옮기지 않았다. 저장소 밖(… | no frontmatter |
| [stl-luau 세션에게: 메모리 분류 인계 (읽기 전용 감사)](memory-stl-luau.md) | claude-doctor 의 `.claude/audit/23-memory-portability.md` §6 에서 나왔다. `/code/.claude/projects/-code-Projects-stl-luau/memory/` 의 항목을 읽기만 했고 아무것도 고치거나 옮기지 않았다. 저장… | no frontmatter |
| table-sim 세션에게: 메모리 분류 인계 (읽기 전용 감사) (공개판에서 뺀 파일) | claude-doctor 의 `.claude/audit/23-memory-portability.md` §6 에서 나왔다. `/code/.claude/projects/-code-Projects-table-sim/memory/` 의 항목을 읽기만 했고 아무것도 고치거나 옮기지 않았다. 저… | no frontmatter |
| [tbox 세션에게: 메모리 분류 인계 (읽기 전용 감사)](memory-tbox.md) | claude-doctor 의 `.claude/audit/23-memory-portability.md` §6 에서 나왔다. `/code/.claude/projects/-code-Projects-tbox/memory/` 의 항목을 읽기만 했고 아무것도 고치거나 옮기지 않았다. 저장소 밖(… | no frontmatter |
| [moonwave-luau 세션에게: luau-kb 증류에서 나온 정정 (2026-11-10)](moonwave-luau-corrections.md) | luau-kb 가 moonwave-luau 의 서술을 재현해 보니 범위가 부정확한 것들이다. 처방은 둘 다 그대로 맞다. 줄 번호는 2026-11-10 에 `/code/Projects/moonwave-luau` 를 읽기 전용으로 열어 확인했다. 근거 경로는 `/code/Projects… | no frontmatter |
| [quad 세션에게: claude-doctor 가 찾은 사항](quad.md) | claude-doctor 에서 quad 를 읽기 전용으로 조사하다 찾은 것들이다. 반영은 quad 세션이 판단한다. | no frontmatter |
| [rbvm 세션에게: luau-kb 증류에서 나온 정정 (2026-11-10)](rbvm-corrections.md) | luau-kb 가 rbvm 의 서술을 엔진 실측(대부분 rbvm 자신의 `.claude/design/engine-behavior.md`)과 대조해 보니 어긋나는 것들이다. 반영 여부는 rbvm 세션이 판단한다. 줄 번호는 2026-11-10 에 `/code/Projects/rbvm`… | no frontmatter |
| [rbvm 세션에게: 프로젝트 settings 의 `git push` deny 제거 제안](rbvm.md) | 위치: `rbvm/.claude/settings.json:25` 의 `"Bash(git push:*)"`(`permissions.deny`). 근거: 사용자 메모리 원칙 "git push / .env deny 는 이 sandbox 에서 부적절"(git 계정은 에이전트 전용, 사용자가… | no frontmatter |
| [stl-luau 세션에게: luau-kb 증류에서 나온 정정 (2026-11-10)](stl-luau-corrections.md) | luau-kb 가 stl-luau 의 서술을 재현하거나 다시 재 보니 틀렸거나 낡은 것들이다. 반영 여부는 stl-luau 세션이 판단한다. 줄 번호는 2026-11-10 에 `/code/Projects/stl-luau` 를 읽기 전용으로 열어 확인했다. luau-kb 는 클론인 `s… | no frontmatter |
| [stl-luau 세션에게 — 에이전트 문서 다이어트 반영 요청](stl-luau.md) | claude-doctor 가 stl-luau 의 `.claude` 문서를 공식 권장 구조로 재구성한 초안을 만들었습니다. 이 세션이 진행 중인 작업과 충돌하지 않도록, 반영은 이 세션이 직접 해 주세요. 지금 작업이 끝난 뒤에 해도 됩니다. | no frontmatter |
| table-sim 세션에게: luau-kb 증류에서 나온 정정 (2026-11-10) (공개판에서 뺀 파일) | `.claude/handoff/table-sim.md`(서버 파일 구조 제안)와 별개다. luau-kb 증류 중 대조한 table-sim 서술 가운데 낡은 것들이다. 줄 번호는 2026-11-10 에 `/code/Projects/table-sim` 을 읽기 전용으로 열어 확인했다. 심… | no frontmatter |
| table-sim 세션에게: 서버 파일 구조 정리 제안 (공개판에서 뺀 파일) | claude-doctor 의 코드 구조 감사(`.claude/audit/12-code-structure.md` §4)에서 나온 제안이다. table-sim 은 읽기만 했다. 반영 여부와 순서는 table-sim 세션이 판단한다. | no frontmatter |
| [tbox 세션에게: luau-kb 증류에서 나온 정정 (2026-11-10)](tbox-corrections.md) | luau-kb 가 tbox 의 서술을 재현해 보니 틀렸거나 낡은 것들이다. 반영 여부는 tbox 세션이 판단한다. 줄 번호는 2026-11-10 에 `/code/Projects/tbox` 를 읽기 전용으로 열어 확인했다. 근거 경로는 `/code/Projects/claude-docto… | no frontmatter |
| [vitrine 세션에게: 웹 플러그인 도입 (.claude/audit/16)](vitrine.md) | 근거는 `claude-doctor/audit/16-marketplace.md` §2, §8 이다. 반영은 vitrine 세션이 판단한다. 아래 모두 vitrine project 범위다(사용자 레벨에 두면 Luau 저장소에서도 Stop 리뷰가 돈다). | no frontmatter |
<!-- coderag:end -->
