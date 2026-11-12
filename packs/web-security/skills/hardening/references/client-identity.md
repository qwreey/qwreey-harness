---
title: "Client identity for rate-limit and lockout keys"
description: "How to identify the client behind a proxy or unix socket so rate limits and lockouts key on the right address and cannot be forged."
keywords:
  - "client IP"
  - "클라이언트 IP"
  - "RemoteAddr"
  - "X-Forwarded-For"
  - "X-Real-IP"
  - "realip"
  - "reverse proxy"
  - "리버스 프록시"
  - "trusted proxy"
  - "신뢰 프록시"
  - "forwarded headers"
  - "rate limit key"
  - "lockout key"
  - "IP deny"
  - "unix socket"
  - "shared token"
  - "IP 스푸핑"
  - "IP spoofing"
kind: reference
---
# Client identity (rate-limit and lockout keys)
- Behind a proxy or unix socket, RemoteAddr is the same for every client, so one attacker can lock everyone out.
- Trust X-Forwarded-For / X-Real-IP only from known peers; where the peer address can be forged, use a shared token.
- After realip processing, IP-based deny rules must still apply.
- Bucket IPv6 by /64.
- Verify the docs' claim ("XFF is the real client IP") against the code; a contract document was wrong once.
