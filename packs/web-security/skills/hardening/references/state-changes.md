# State changes
- Replace firewall rules atomically, not flush-then-reapply; treat IPv4 and IPv6 alike (one firewall had no IPv6 filter).
- Write config and credentials as temp file, fsync, rename.
- A bad entry in a deny rule refuses startup, since dropping it narrows the denial. A bad entry in an allow rule is warned loudly and skipped.
