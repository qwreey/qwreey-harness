---
title: "Verification"
description: "How to test security gates: the no-token, wrong-token and right-token matrix, bypass-spelling tests, and tests that plant the real attack and also check normal behavior."
keywords:
  - "verification"
  - "검증"
  - "security test"
  - "보안 테스트"
  - "test matrix"
  - "no token wrong token"
  - "bypass spellings"
  - "우회 표기"
  - "%2f"
  - "control characters"
  - "case changes"
  - "extra zeros"
  - "alternate IP notation"
  - "regression test"
  - "회귀 테스트"
  - "negative test"
  - "attack test"
  - "fix is done"
kind: reference
---
# Verification
- For each route, send no token, a wrong token and a right token; confirm the first two are rejected.
- Pin bypass spellings as tests: `%2f`, control characters, case changes, ports with extra zeros, alternate IP notations.
- Unit tests plant the real attack vector and assert it is blocked, and also assert normal behavior.
- Check security claims in docs and comments against the implementation.
