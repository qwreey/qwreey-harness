# Supply chain
- Pin remote scripts and binaries to a commit or version and verify sha256. No `curl | sh` as root.
- curl: `-f`, https only (`--proto =https --proto-redir =https`), with timeouts.
- Replace the existing file only after download and verification succeed; never delete first.
