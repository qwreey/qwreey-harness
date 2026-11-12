# Browser and cross-origin
- State-changing requests are CSRF-protected (Sec-Fetch-Site/Origin checks, Go `http.CrossOriginProtection`); GET has no side effects.
- A WebSocket that only checks Origin == Host also needs a Host allowlist against DNS rebinding.
- postMessage handlers check both origin and source (an embedded-widget message handler and a browser-side extension both lacked this).
- Strip cookies on hops to less-trusted upstreams, especially cookies scoped to a parent domain (an auth sidecar's session cookie was forwarded to every vhost).
- Never render user files inline on the app origin: `Content-Disposition: attachment`, `nosniff`, `CSP: sandbox` (stored XSS through a file-sharing endpoint).
- Build header values with a standard formatter (`mime.FormatMediaType`), not hand-quoting.
- Delete test pages and docs from third-party static trees before serving (a VNC web client's bundled test pages were served).
- Default headers: nosniff, `no-store` on APIs, frame-ancestors, Referrer-Policy, hide server version.
