# rbvm — runtime 감사 초점

<!-- 위치: rbvm/.claude/audit-focus/runtime.md (예시 초안). rbvm-gc-auditor 본문의 점검 항목을 옮겼다.
     원칙: 기준은 정본 설계 문서이고, 이 파일은 "어디를 볼지"만 적는다. 코드 이름은 정본 문서가 소스다. -->

정본: `.claude/design/gc-and-lifecycle.md`(weak table 표, 강참조 사슬), `.claude/design/architecture.md`("프록시 라이브러리 모듈 계약", "Dispose 훅과 Order" 절). 둘이 코드와 다르면 **어느 쪽이 낡았는지 판정하지 말고 둘 다** 보고한다.

이 저장소에는 GC 경로를 지키는 테스트가 없다. 결함은 GC가 실제로 돌 때까지 드러나지 않는다.

## 볼 곳 (중요한 순)

1. **강참조 사슬**: 정본 §"gcHold"의 사슬이 Wrap 경로마다 성립하는가. 특히 클로저 본문 안의 업밸류 캡처가 남아 있는가(가장 위험한 단일 실수), 연결 핸들을 사슬에 다시 넣는 대입이 남아 있는가.
2. **`__mode`**: 모든 `setmetatable(..., { __mode = ... })`을 정본 표와 대조한다. 함정은 둘이다.
   - 엔진 시그널(userdata)을 키로 쓰는 테이블에 약한 키가 있는가. 다시 얻으면 주소가 바뀐다.
   - 객체↔프록시 매핑 캐시가 강해졌는가.
3. **정리 경로**: 새 매핑 테이블이 해당 모듈의 dispose에서 비워지는가, 새 연결이 lifecycle 배열에 들어가는가, 새 모듈의 dispose 훅 Order가 정본 표와 겹치지 않는가, Init의 멱등성.
4. **동일성 불변식**: "한 Namespace 안에서 같은 Instance → 같은 Proxy"를 우회하는 경로.
5. **Destroy 전파**: 가상 부모·자식 링크를 더한 코드가 정리 경로에서도 양방향으로 끊는가.

## 알려진 예외 (발견 아님)

- 루트 `README.md`와 `architecture.md`가 명시한 설계 제약.
- 엔진 객체가 얽힌 동작은 luau CLI로 실측할 수 없다. weak table 동작 자체는 `luau`로 실험해도 된다.

## 범위 밖

API 시맨틱 동등성은 `rbvm-api-parity`의 몫이다.
