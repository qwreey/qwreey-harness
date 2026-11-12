---
title: "Privileges"
description: "Which container privilege settings to apply: dropped capabilities, no-new-privileges, non-root users, and why a read-only runtime socket mount is not a mitigation."
keywords:
  - "Docker"
  - "docker privileged"
  - "privileged container"
  - "컨테이너 권한"
  - "compose"
  - "cap_drop"
  - "capabilities"
  - "no-new-privileges"
  - "non-root"
  - "비루트"
  - "docker socket"
  - "도커 소켓"
  - "socket mount"
  - ":ro mount"
  - "container runtime socket"
  - "least privilege"
  - "최소 권한"
kind: reference
---
# Privileges
- `cap_drop: ALL`, then add only what is needed; `no-new-privileges`; run non-root.
- Document mitigations that are not real ones (a `:ro` mount of the container runtime socket still grants control).
