---
name: hardening
description: Security hardening checklists for server and infra work. Use when adding or reviewing an HTTP endpoint, auth/login/lockout/rate limiting, a reverse proxy or Caddy/nginx config, exec/shell/argv calls, file paths, uploads or WebDAV-like file serving, server-side fetch or port forwarding (SSRF), secrets and logging, Docker/compose privileges, install scripts and curl downloads, firewall rules, or any security review. 보안 리뷰, 하드닝, 인증, 프록시 설정, 경로 검증, 명령 주입, 비밀 노출.
---

# Hardening checklists

The always-on rule lists the principles; this skill holds the situational checklists behind them. Each item is a mistake that really shipped once.

## How to use
1. Name what you add or review (endpoint, proxy route, exec call, file access, outbound connection, container, script).
2. Open only the references for that area, plus `principles.md` when an item's reasoning is unclear.
3. Go through each item and mark it pass, fixed, or not applicable. Do not skip silently.
4. Prove each fix with a test that sends the bad request and sees it rejected (include bypass spellings), plus a test that normal use still works.
5. Check security claims in docs and comments against the implementation.

## References (in `references/`)
- `principles.md`: the ten core principles with the reasoning and cases behind each.
- `auth-gates.md`: login, lockout, backoff, hashing cost, first-run setup, route/auth ordering.
- `client-identity.md`: client IP behind proxies, forwarded headers, rate-limit and lockout keys.
- `browser-and-origin.md`: CSRF, WebSocket origin, postMessage, cookie forwarding, user-file rendering, headers.
- `paths.md`: symlinks, races, delete/move, special files, proxy path normalization, decoding.
- `injection.md`: argv, shell-sourced files, config templating, CSS, tools that execute config, untrusted repos.
- `outbound-connections.md`: SSRF validator, address forms, dial-time checks, schemes, redirects.
- `secrets.md`: masking, logs, error bodies, file modes, build contexts.
- `resource-limits.md`: timeouts, size caps, process and connection caps.
- `supply-chain.md`: pinned downloads, hashes, curl flags, replace-after-verify.
- `state-changes.md`: firewall replace, atomic writes, deny vs allow rule errors.
- `privileges.md`: container capabilities, non-root, socket mounts.
- `verification.md`: the test matrix for gates and bypass spellings.
