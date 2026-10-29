# ARCHITECTURE.md - aveproject/ave-api

## The whole thing, in one diagram

```
aveproject/ave (source of truth)
    |
    | raw.githubusercontent.com: latest records + manifest,
    |   on startup + every 15 min
    | github.com release assets: a pinned release, on first use
    | api.github.com: the list of releases, at most hourly
    v
in-memory caches (Python dicts, nothing more): latest, a few pinned
releases, the releases list
    |
    | read-only routes, under /v1 (the unversioned paths are aliases)
    v
GET /v1/            service info, api_version, catalog, cache_age_seconds
GET /v1/records     full list
GET /v1/records/{ave_id}              one record
GET /v1/records/{ave_id}/mitigation   one record's neutral mitigation object only
GET /v1/search?q=   substring match across title, description, attack_class,
                     behavioral_fingerprint
GET /v1/releases    the catalog releases, and which can be pinned
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

**Every data response names its catalog.** A catalog is the latest data
(`AVE-Catalog: latest`) or one release (`AVE-Catalog: v1.2.0`), and its
`sha256`, `schema_version`, `generated_at` and `source_commit` come from the
manifest beside the records file, never from guesses. The latest records and
manifest are fetched separately, so a refresh that gets two that do not match
(a commit landing between the two fetches) is refused like any other failed
refresh, and the last known-good cache keeps serving. The `ETag` is derived
from the records `sha256`, the path without its `/v1` prefix and the query,
so an alias and its `/v1` path share one.

**A pinned release is verified before it is served, and only then cached.**
`?release=` downloads `SHA256SUMS`, the manifest and the records file, and
runs the same checks as `aveproject/ave`'s `scripts/check_release_assets.py`.
A release that fails is a `502` and is not cached, so a later request tries
again. Releases never change, so the cache has no expiry, only a size bound
(`RELEASE_CACHE_SIZE`, oldest use evicted first).

**The releases list spends as little of GitHub's unauthenticated rate limit
as it can**: cached for an hour, then revalidated with `If-None-Match`, so an
unchanged list costs a `304`. A failed refresh keeps serving the last list.

**Rate limiting exists because the hosting context has real, finite
headroom**, not as defensive-by-default paranoia. See `CHANGELOG.md` for
when and why this was added.

## ADR: hosting platform

Considered Vercel (rejected: serverless-only Python, no persistent
in-memory state, incompatible with this service's cache design).
Originally chose Render as primary (zero card on file, real cost was a
slower cold start after idle) over Cloud Run (technically better fit
for the persistent-container model, but requires a card on file even
though usage should stay within the free tier).

Revisited for the first production deployment and switched to Cloud
Run: the card-on-file requirement was accepted deliberately, with a $1
budget alert as the concrete mitigation (a service expected to cost $0
means any alert firing at all is the signal, not a soft limit), in
exchange for the persistent-container model actually matching this
service's in-memory cache design instead of working around Render's
sleep-and-wake cycle. `--min-instances 0` keeps it free at idle the
same way Render's sleep did, just without the cold-start latency on
wake.

See `README.md`'s deployment section for the current live choice; check
there before assuming this ADR reflects where it's actually running
today, ADRs record reasoning at decision time, they don't self-update.
