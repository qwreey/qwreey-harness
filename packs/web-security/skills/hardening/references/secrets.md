# Secrets
- Mask outside the gate and restore placeholders to the original value on save (env blocks in settings files, process command lines).
- Do not log query strings or Referer (an OAuth callback carried a token).
- Error responses never include internal error strings; log them instead.
- Secret files and backups are mode 600/700 and excluded from build contexts.
