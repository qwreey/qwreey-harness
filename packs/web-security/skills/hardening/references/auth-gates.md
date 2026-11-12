---
title: "Auth gates"
description: "Which checks a login, password-change or first-run setup flow needs: lockout and backoff limits, per-key serialization, hashing cost caps, shared buckets, and auth-before-route ordering."
keywords:
  - "인증"
  - "로그인"
  - "잠금"
  - "락아웃"
  - "lockout"
  - "backoff"
  - "백오프"
  - "brute force"
  - "무차별 대입"
  - "rate limit"
  - "argon2"
  - "bcrypt"
  - "password hashing"
  - "비밀번호 해시"
  - "session logout"
  - "세션 종료"
  - "first-run setup"
  - "초기 설정"
  - "one-time token"
  - "Caddy handle respond"
  - "route ordering"
  - "auth gate"
kind: reference
---
# Auth gates
- Cap failure counters and backoff math (a shift overflow after 35 failures reset the lockout).
- Serialize attempts per key; N concurrent requests skipped the backoff.
- Limit concurrent runs of expensive hashes (argon2, bcrypt); they are a DoS lever.
- Every endpoint that checks a password (change, reset included) shares one lockout bucket.
- Lockout and logout end the server-side session too.
- First-run setup (claiming the first password) needs a one-time token delivered over an operator-only channel (logs), and requests are serialized.
- After adding a proxy route, confirm auth still runs first (in Caddy, `handle` ran before `respond`, so a token check on one path was skipped).
