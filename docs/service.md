# The WODCraft compilation service

A small HTTP service around the compiler, for clients that cannot embed it.

**Most clients should not use it.** An Apple application embeds `WODCraftKit` and compiles offline;
anything Python calls `wodcraft.api` directly. This service is for the rest: a web page, a script in
another language, a CI step, a no-code tool.

```bash
pip install "wodcraft[service]"
wodcraft-service --port 8000          # or: uvicorn wodcraft.service:app
```

No database, no state, no temporary file, no subprocess: one process that calls the compiler in
memory.

## Endpoints

| Method and path | What it does |
|---|---|
| `POST /compile` | `{source, file?}` → `{ok, documents[], diagnostics[]}` |
| `POST /check` | same body → `{ok, errors, warnings, diagnostics[]}` |
| `POST /format` | same body → `{ok, formatted, changed, diagnostics[]}` |
| `POST /show` | `{source, category?, level?, units?, language?}` → `{ok, board, diagnostics[]}` |
| `GET /catalog` | the 212 movements and the equivalence tables |
| `GET /library` | the standard library index, `?query=` filters it |
| `GET /library/{path}` | one workout: `source` and `compiled` |
| `GET /spec` | the specification this service implements |
| `GET /health` | `{status, wodcraft, version}` — always open |

A source that does not compile is **not** an HTTP error: the call returns `200` with `ok: false` and
the diagnostics, because that is the useful answer. Real HTTP errors are `401` (missing key), `404`
(unknown workout) and `413` (source above 256 kB).

```bash
curl -s localhost:8000/check -H 'content-type: application/json' \
  -d '{"source":"AMRAP 12\n  10 Trusters 43 kg\n"}' | jq '.diagnostics[0]'
{
  "code": "E020",
  "severity": "error",
  "message": "Unknown movement 'Trusters'.",
  "line": 2,
  "col": 6,
  "suggestion": "did you mean 'Thruster' or 'Kettlebell thruster' or 'Dumbbell thruster'?"
}
```

## Running it in the open

- **Set `WODCRAFT_API_KEY`.** When it is set, every endpoint but `/health` requires the same value in
  the `X-API-Key` header. Left unset, the service is open — fine on a laptop, not on the internet.
- Sources are capped at 256 kB; a workout is a few hundred bytes.
- The service holds nothing: no user data, no session, no log of what was compiled. Put it behind
  your own reverse proxy for TLS and rate limiting.
- `deploy/Dockerfile` builds a wheel and runs it as an unprivileged user, with a health check:
  `docker build -f deploy/Dockerfile -t wodcraft-service .`
