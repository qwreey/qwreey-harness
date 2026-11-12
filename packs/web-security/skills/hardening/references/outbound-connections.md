---
title: "Outbound connections (SSRF)"
description: "How to validate server-initiated connections: blocked ranges and ports, canonical address comparison, dial-time resolution checks, scheme allowlists, and redirect re-checks."
keywords:
  - "SSRF"
  - "server-side request forgery"
  - "outbound connection"
  - "아웃바운드 연결"
  - "port forwarding"
  - "포트 포워딩"
  - "redirect"
  - "리디렉션"
  - "URL validator"
  - "URL 검증"
  - "scheme allowlist"
  - "127.0.0.0/8"
  - "loopback"
  - "cloud metadata"
  - "클라우드 메타데이터"
  - "Docker 2375"
  - "DNS rebinding"
  - "dial time"
  - "IP notation"
  - "GIT_ALLOW_PROTOCOL"
  - "서버측 요청 위조"
kind: reference
---
# Outbound connections (SSRF)
- Open only the ranges you need. Reject self (all of 127.0.0.0/8, 0.0.0.0, ::1, own hostname) and dangerous ports (Docker 2375/2376, cloud metadata).
- Compare parsed canonical forms, not strings (`host:02375` passed; `127.0.0.2`).
- Check the resolved address at the moment of dialing.
- Allowlist URL schemes (`GIT_ALLOW_PROTOCOL` for git) and re-check after every redirect.
- Every feature that connects for the caller (forwarding, publishing, fetching) uses the same validator.
