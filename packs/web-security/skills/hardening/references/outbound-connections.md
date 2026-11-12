# Outbound connections (SSRF)
- Open only the ranges you need. Reject self (all of 127.0.0.0/8, 0.0.0.0, ::1, own hostname) and dangerous ports (Docker 2375/2376, cloud metadata).
- Compare parsed canonical forms, not strings (`host:02375` passed; `127.0.0.2`).
- Check the resolved address at the moment of dialing.
- Allowlist URL schemes (`GIT_ALLOW_PROTOCOL` for git) and re-check after every redirect.
- Every feature that connects for the caller (forwarding, publishing, fetching) uses the same validator.
