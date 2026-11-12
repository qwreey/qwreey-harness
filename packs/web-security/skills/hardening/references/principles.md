---
title: "Core principles and why"
description: "What the ten core security principles are and the reasoning and real cases behind each, for when a checklist item's rationale is unclear."
keywords:
  - "security principles"
  - "보안 원칙"
  - "fail closed"
  - "실패 시 닫기"
  - "allowlist vs denylist"
  - "허용 목록"
  - "denylist"
  - "network location is not authentication"
  - "네트워크 위치는 인증이 아님"
  - "injection points"
  - "single validator"
  - "symlink resolution"
  - "edge enforcement"
  - "resource caps"
  - "fix verification"
  - "hardening"
  - "하드닝"
  - "security review"
  - "보안 리뷰"
  - "loopback bind"
  - "empty allowlist"
kind: reference
---
# Core principles and why

1. Fail closed. Missing config, parse failure, empty value or unseen input is rejected. An empty allowlist means nothing is allowed. (An empty allowed-hosts setting let every Host through; a Docker authorization proxy allowed unknown endpoints by default, so swarm and plugin routes reached host root; a gate stayed open when no password was set.)
2. Allowlists over denylists. When upstream adds an option, a denylist is bypassed silently; if an allowlist blocks something legitimate, fix it then. (security options, mount types, network drivers, URL schemes)
3. Network location is not authentication. Containers, plugins and user code on the same network are attackers too. Bind services to loopback and open one proxy outward. (An admin API was reachable unauthenticated from the internal network; an auth sidecar listened on 0.0.0.0.)
4. Every point where data crosses into another language is an injection point: shell, argv, nginx/Caddy/sshd config, CSS, HTTP headers, logs. Use a structured encoder, or a strict charset allowlist when none exists.
5. Server-initiated connections go through one validator. Per-feature checks always miss one. (A port-forward feature and a publish feature both bypassed the shared target guard.)
6. Judge a path by what it resolves to, after symlinks, normalization and decoding, not by its string.
7. Reads that can carry secrets are protected like writes. Distrust "this file has no secrets" comments; judge by whether the format can hold them.
8. Enforce security properties at your own edge, per resource. Do not depend on an operator's outer proxy configuration.
9. Every input, connection and process has a cap: size, time, concurrency.
10. A fix is done when a test shows the request that must be blocked is blocked. The success path alone proves nothing.
