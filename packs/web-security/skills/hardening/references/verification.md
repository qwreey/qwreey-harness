# Verification
- For each route, send no token, a wrong token and a right token; confirm the first two are rejected.
- Pin bypass spellings as tests: `%2f`, control characters, case changes, ports with extra zeros, alternate IP notations.
- Unit tests plant the real attack vector and assert it is blocked, and also assert normal behavior.
- Check security claims in docs and comments against the implementation.
