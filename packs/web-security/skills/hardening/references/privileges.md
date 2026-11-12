# Privileges
- `cap_drop: ALL`, then add only what is needed; `no-new-privileges`; run non-root.
- Document mitigations that are not real ones (a `:ro` mount of the container runtime socket still grants control).
