# Paths
- Decide on the fully symlink-resolved path, parents included. If validation fails, never fall back to the unresolved path. Prefer Go `os.Root` or `openat2(RESOLVE_BENEATH)` to remove the check-then-use race.
- Create, delete, move, rename and mount sources all get the same check (delete and move once skipped link resolution).
- Read regular files only, with a size cap, so FIFOs and `/dev/zero` cannot hang or exhaust the server.
- A proxy routes on the normalized path but forwards the original; if normalization changes the first segment or prefix, return 400 (`/..%2f` and control characters escaped a prefix like `/exports/`).
- Judge the decoded path. Name matching must handle multiple segments, case and normal-form differences.
