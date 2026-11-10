# quad 세션에게: claude-doctor 가 찾은 사항

claude-doctor 에서 quad 를 읽기 전용으로 조사하다 찾은 것들이다. 반영은 quad 세션이 판단한다.

## 코드
1. **`quad-base/src/Relate.luau:28` 의 `error(…, 3)`**
   - `-O2`(그리고 `--!native`)에서 에러 위치가 틀린 줄을 가리키거나 사라진다.
   - quad 를 `-O2` 로 돌리면 테스트 3개가 실패한다.
   - 근거: `claude-doctor/decisions/D-10` 정정 절, `drafts/gaps/optimize-levels.md`
2. **`scripts/doc-snippets-runshim.luau` 가상 task 큐의 정렬**
   - `table.sort` 는 안정 정렬이 아니다. 그래서 같은 시각 항목이 5개 이상이면 FIFO 순서가 섞인다(luau 0.742 실측).
   - 근거: `luau-kb/skills/roblox-luau/references/mocks.md`

## 문서·주석
3. **Surface 의 "no pcall" 주석**
   - type function 안의 pcall 이 안 되는 것은 luau-lsp 1.69.0 뿐이다. quad 핀인 1.70.1 에서는 이 주석이 틀리다.
   - 근거: `luau-kb/skills/luau-types/references/type-functions.md` §5
4. **`typing-limits.md:69` 의 "`error()` 대신 `print`"**
   - 0.734 이상에서는 필요 없다. `error()` 메시지는 네 판(luau 0.734/0.742, luau-lsp 1.69.0/1.70.1) 모두에서 진단으로 보인다.
5. **`base/architecture.md:783` "새 코드는 `const`"**
   - 게시된 소스는 0줄이라 실태와 맞지 않는다. D-01 은 `const` 사용 가능으로 확정됐다.
6. **보존 지시와 실제 상태가 다르다**
   - 패스스루 type function 뒤에 체이닝이 붕괴한다는 서술은 최소 꼴에서 재현되지 않았다.
   - 실물 `Quad` 가 깨진 원인은 인자 직렬화 실패로 보인다(추정).
