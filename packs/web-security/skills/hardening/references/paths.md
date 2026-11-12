---
title: "Paths"
description: "How to validate file paths safely: symlink resolution, check-then-use races, delete and move parity, special files, proxy path normalization, and decoded-path matching."
keywords:
  - "path traversal"
  - "경로 탐색"
  - "경로 검증"
  - "symlink"
  - "심볼릭 링크"
  - "symlink resolve"
  - "TOCTOU"
  - "race condition"
  - "os.Root"
  - "openat2"
  - "RESOLVE_BENEATH"
  - "delete move rename"
  - "FIFO"
  - "/dev/zero"
  - "special files"
  - "path normalization"
  - "경로 정규화"
  - "proxy prefix"
  - "%2f"
  - "URL decoding"
  - "percent encoding"
  - "case normalization"
  - "mount source"
  - "WebDAV"
  - "file serving"
  - "uploads"
kind: reference
---
# Paths
- Decide on the fully symlink-resolved path, parents included. If validation fails, never fall back to the unresolved path. Prefer Go `os.Root` or `openat2(RESOLVE_BENEATH)` to remove the check-then-use race.
- Create, delete, move, rename and mount sources all get the same check (delete and move once skipped link resolution).
- Read regular files only, with a size cap, so FIFOs and `/dev/zero` cannot hang or exhaust the server.
- A proxy routes on the normalized path but forwards the original; if normalization changes the first segment or prefix, return 400 (`/..%2f` and control characters escaped a prefix like `/exports/`).
- Judge the decoded path. Name matching must handle multiple segments, case and normal-form differences.
