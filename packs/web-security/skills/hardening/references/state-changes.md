---
title: "State changes"
description: "How to apply firewall and config changes safely: atomic replacement, temp-file fsync rename writes, IPv4 and IPv6 parity, and how deny versus allow rule errors are handled."
keywords:
  - "firewall"
  - "방화벽"
  - "firewall replace"
  - "atomic write"
  - "원자적 쓰기"
  - "fsync rename"
  - "temp file rename"
  - "config write"
  - "credentials write"
  - "IPv6"
  - "IPv4"
  - "deny rule"
  - "allow rule"
  - "flush reapply"
  - "rule errors"
  - "startup refusal"
  - "상태 변경"
kind: reference
---
# State changes
- Replace firewall rules atomically, not flush-then-reapply; treat IPv4 and IPv6 alike (one firewall had no IPv6 filter).
- Write config and credentials as temp file, fsync, rename.
- A bad entry in a deny rule refuses startup, since dropping it narrows the denial. A bad entry in an allow rule is warned loudly and skipped.
