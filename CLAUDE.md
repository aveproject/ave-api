# CLAUDE.md - session rules for aveproject/ave-api

Read `CONTEXT.md` first if this is a fresh session; it has the full
framing. This file is the short, mechanical version for quick reference
mid-session.

## Hard rules

- No write endpoints. Ever. If a task description implies one, stop and
  flag it rather than build it; this repo's entire identity is read-only.
- Never check in a copy of AVE record data. The cache is populated at
  runtime from `aveproject/ave`; nothing record-shaped belongs committed
  to this repo's own files.
- `/records/{ave_id}/mitigation` returns only the neutral `mitigation`
  object. Do not extend it to return anything product-specific, from this
  project's tools or any other implementation's.
- No em dashes, anywhere, including code comments and commit messages.
- No auth today, and don't add it speculatively. If real abuse is
  observed, revisit; until then, the existing rate limiting is the
  intended level of protection.

## Resilience rules

- Every network call this service makes (currently: one, the fetch to
  `aveproject/ave`) must handle failure without taking down unrelated
  requests. A dependency being briefly unreachable is a routine event, not
  an incident; the cache-serves-stale-on-refresh-failure pattern in
  `_ensure_fresh()` is the model to follow for any future external call
  this service adds.
- Never let a startup-time failure crash-loop the container. Log and start
  degraded (empty cache, will retry) rather than exit non-zero on a
  transient boot-time network issue.
- If a new endpoint is added, it needs the same `@limiter.limit(...)`
  decorator every existing route has. A route added without it is a gap in
  the rate-limiting coverage, not an oversight to catch later.
- Timeouts on every outbound call, no exceptions. The existing fetch uses
  `timeout=10`; any new outbound call needs an explicit timeout of its
  own, never the client library's default.

## Security rules

- No em dashes, including in error messages returned to callers; a stray
  one in a 404 detail message is still a house-style violation.
- Never log full request bodies or headers at INFO level or above; this
  service has no secrets today, but logging discipline should not depend
  on that staying true forever.
- CORS stays wide open (`allow_origins=["*"]`) deliberately; this is
  public, read-only data with no reason to restrict origins. Don't narrow
  it without a real reason, and don't widen anything else without one
  either.

## Before opening a PR

- Run the validation commands in `README.md` against a local instance.
- Confirm CodeQL and Scorecard checks pass in CI.
- Check `ARCHITECTURE.md`'s ADR section before changing the hosting setup;
  know what was already considered and rejected before re-proposing it.
