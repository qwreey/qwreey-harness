---
title: "Supply chain"
description: "How to install remote scripts and binaries safely: pin to a commit or version, verify sha256, use strict curl flags, and replace files only after verification."
keywords:
  - "supply chain"
  - "공급망"
  - "curl | sh"
  - "install script"
  - "설치 스크립트"
  - "curl download"
  - "curl flags"
  - "--proto =https"
  - "pinned version"
  - "버전 고정"
  - "sha256"
  - "checksum"
  - "체크섬"
  - "hash verification"
  - "download verification"
  - "replace after verify"
  - "root install"
  - "원격 스크립트"
kind: reference
---
# Supply chain
- Pin remote scripts and binaries to a commit or version and verify sha256. No `curl | sh` as root.
- curl: `-f`, https only (`--proto =https --proto-redir =https`), with timeouts.
- Replace the existing file only after download and verification succeed; never delete first.
