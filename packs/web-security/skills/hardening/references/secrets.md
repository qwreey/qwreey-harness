---
title: "Secrets"
description: "How to keep secrets out of logs, error bodies, query strings, masked configs, file modes, and build contexts."
keywords:
  - "secret logging"
  - "비밀 로깅"
  - "secrets"
  - "비밀 노출"
  - "secret exposure"
  - "masking"
  - "마스킹"
  - "logs"
  - "로그"
  - "query string"
  - "Referer"
  - "OAuth callback token"
  - "error response"
  - "에러 응답"
  - "internal error strings"
  - "file modes"
  - "파일 권한"
  - "build context"
  - "env block"
  - "command line"
  - "process command line"
  - "credentials leak"
  - "토큰 노출"
kind: reference
---
# Secrets
- Mask outside the gate and restore placeholders to the original value on save (env blocks in settings files, process command lines).
- Do not log query strings or Referer (an OAuth callback carried a token).
- Error responses never include internal error strings; log them instead.
- Secret files and backups are mode 600/700 and excluded from build contexts.
