# ave-api

Read-only reference implementation of the [AVE](https://aveproject.org)
(Agentic Vulnerability Enumeration) standard's record lookup API.

[![OpenSSF Scorecard](https://api.securityscorecards.dev/projects/github.com/aveproject/ave-api/badge)](https://securityscorecards.dev/viewer/?uri=github.com/aveproject/ave-api)
[![CodeQL](https://github.com/aveproject/ave-api/actions/workflows/codeql.yml/badge.svg)](https://github.com/aveproject/ave-api/actions/workflows/codeql.yml)
[![License: Apache 2.0](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)
[![Deployed on Cloud Run](https://img.shields.io/badge/deployed-Cloud%20Run-4285F4?logo=googlecloud&logoColor=white)](ARCHITECTURE.md)

- **Live API:** https://api.aveproject.org
- **Interactive docs:** https://api.aveproject.org/docs

## Quick start

```bash
curl -s https://api.aveproject.org/v1/records/AVE-2026-00046 | jq .
```

## What this is, and isn't

This is **a** reference implementation, not **the** standard. AVE itself,
the records and schema, lives in [aveproject/ave](https://github.com/aveproject/ave).
This service is a thin, read-only lookup layer over that data, provided so
implementers have a working example to call or fork rather than parsing raw
JSON files themselves. Anyone can run their own instance; nothing about AVE
depends on this specific deployment staying available.

## Endpoints

Version 1 of the contract lives under `/v1`:

| Method | Path | Description |
|---|---|---|
| GET | `/v1/` | Service info, API version, the catalog being served, cache age |
| GET | `/v1/records` | All records, deprecated ones included with their `status` |
| GET | `/v1/records/{ave_id}` | One record |
| GET | `/v1/records/{ave_id}/mitigation` | The record's neutral `mitigation` object only |
| GET | `/v1/search?q=...` | Substring search across title, description, attack class, behavioral fingerprint |
| GET | `/v1/releases` | The catalog releases of `aveproject/ave`, and which can be pinned |
| GET | `/docs` | Interactive OpenAPI docs (auto-generated) |

The unversioned paths (`/`, `/records`, `/records/{ave_id}`,
`/records/{ave_id}/mitigation`, `/search`) are aliases of their `/v1` paths
with identical bodies and headers, so existing callers keep working. New
callers should use `/v1`.

A deprecated record is served with its `status`; only an id that was never
published is a `404`.

No authentication. No write endpoints. Rate limited to 60 requests a minute
per IP for each path, as a basic abuse backstop, generous for any legitimate
use.

## Which data you got

Every data response (records, one record, a mitigation, a search) carries
headers saying which catalog it came from:

| Header | Value |
|---|---|
| `AVE-API-Version` | `1`, the contract version (on every response) |
| `AVE-Catalog` | `latest`, or the release tag, for example `v1.2.0` |
| `AVE-Records-SHA256` | SHA-256 of the records file the answer came from |
| `AVE-Schema-Version` | The schema version every record in it declares |
| `AVE-Source-Commit` | The `aveproject/ave` commit it was built from, when known (releases) |
| `ETag`, `Last-Modified` | For conditional requests; `Last-Modified` is the file's `generated_at` |

`GET /v1/` reports the same for the latest data in a `catalog` object, read
from the manifest that sits next to the records file.

## Pinning a release

Add `?release=vX.Y.Z` to any data route to read a fixed catalog release
instead of the latest data:

```bash
curl -s "https://api.aveproject.org/v1/records/AVE-2026-00046?release=v1.2.0"
```

The service downloads that release's `ave-records.json`, checks it against
the release's `SHA256SUMS` and manifest before serving anything from it, and
keeps the last few releases in memory. An unknown release is a `404`; a
release whose files do not agree is a `502` and is not cached. Releases from
`v1.2.0` on can be pinned; `GET /v1/releases` lists them. These checks prove
the files belong together, not who published them; to check provenance, use
`gh attestation verify` on a downloaded release.

## Caching

Send the `ETag` back as `If-None-Match` and an unchanged answer comes back
as an empty `304`:

```bash
curl -s -D - -o /dev/null https://api.aveproject.org/v1/records/AVE-2026-00046
curl -s -o /dev/null -w '%{http_code}\n' \
  -H 'If-None-Match: "<etag from above>"' \
  https://api.aveproject.org/v1/records/AVE-2026-00046
```

The latest data is `Cache-Control: public, max-age=300`; a pinned release
never changes, so it is `public, max-age=86400, immutable`.

## Not for scanning hot paths

This service runs as a single instance that scales to zero when idle, so the
first request after a quiet spell waits for a cold start, and every caller
shares one instance and its rate limit. Use it for lookups, links and
spot checks. A scanner that resolves `ave_id` values on every finding should
download a catalog release once (see
[Releases and pinning](https://github.com/aveproject/ave#releases-and-pinning)
in `aveproject/ave`) and read it locally.

## Running locally

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

## Data source

Fetches `dist/ave-records-latest.json` and its manifest from
[aveproject/ave](https://github.com/aveproject/ave) on startup and every 15
minutes thereafter. A pinned release is downloaded from that repo's GitHub
Releases on first use, and the list of releases comes from the GitHub
Releases API, cached for an hour. This repo holds no copy of the record data
itself; `aveproject/ave` is the single source of truth.

## Deployment

Deployed on Google Cloud Run (`--min-instances 0`, scales to zero at
idle). See `ARCHITECTURE.md`'s ADR section for the full reasoning,
including why Render was the original choice and what changed.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## Security

See [SECURITY.md](SECURITY.md).

## License

Apache 2.0, see [LICENSE](LICENSE).
