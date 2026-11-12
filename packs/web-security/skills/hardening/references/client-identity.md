# Client identity (rate-limit and lockout keys)
- Behind a proxy or unix socket, RemoteAddr is the same for every client, so one attacker can lock everyone out.
- Trust X-Forwarded-For / X-Real-IP only from known peers; where the peer address can be forged, use a shared token.
- After realip processing, IP-based deny rules must still apply.
- Bucket IPv6 by /64.
- Verify the docs' claim ("XFF is the real client IP") against the code; a contract document was wrong once.
