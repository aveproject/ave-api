# ARCHITECTURE.md - aveproject/ave-api

## The whole thing, in one diagram

```
aveproject/ave (source of truth)
    |
    | raw.githubusercontent.com fetch, on startup + every 15 min
    v
in-memory cache (a Python dict, nothing more)
    |
    | four read-only routes
    v
GET /            service info, including cache_age_seconds
GET /records     full list
GET /records/{ave_id}              one record
GET /records/{ave_id}/mitigation   one record's neutral mitigation object only
GET /search?q=   substring match across title, description, attack_class,
                  behavioral_fingerprint
```

## Design decisions worth knowing before changing anything

**No database.** At the corpus's current size, a Python dict in memory is
faster, simpler, and has fewer failure modes than any database would
introduce. Revisit only if the corpus grows to a size where startup fetch
time or memory footprint becomes a real problem, not before.

**Lazy refresh, not a background scheduler.** `_ensure_fresh()` only
re-fetches when a request arrives and the cache is stale. No cron job, no
background thread, nothing that can silently die without anyone noticing a
missing heartbeat.

**A refresh failure serves stale data instead of failing the request.**
See `main.py`'s `_ensure_fresh()` for the actual implementation; this is
stated here because it's a load-bearing design decision, not just a bug
fix. Only a service that has never had a single successful fetch fails
hard.

**The `/mitigation` endpoint can only ever return the neutral `mitigation`
object.** This is structural, not a convention someone has to remember: the
code has no path to return anything else. The `mitigation` object's own
definition, and the boundary between it and any concrete, product-specific
control, is defined in `aveproject/ave`'s own schema, not in any single
implementation's docs; that boundary belongs to the standard, and this
service simply respects it.

**Rate limiting exists because the hosting context has real, finite
headroom**, not as defensive-by-default paranoia. See `CHANGELOG.md` for
when and why this was added.

## ADR: hosting platform

Considered Vercel (rejected: serverless-only Python, no persistent
in-memory state, incompatible with this service's cache design). Chose
Render as primary (zero card on file, real cost is a slower cold start
after idle) over Cloud Run (technically better fit for the persistent-
container model, but requires a card on file even though usage should
stay within the free tier). See `README.md` deployment section for the
current live choice; check there before assuming this ADR reflects where
it's actually running today, ADRs record reasoning at decision time, they
don't self-update.
