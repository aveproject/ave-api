# ave-api

Read-only reference implementation of the [AVE](https://aveproject.org)
(Agentic Vulnerability Enumeration) standard's record lookup API.

[![OpenSSF Scorecard](https://api.securityscorecards.dev/projects/github.com/aveproject/ave-api/badge)](https://securityscorecards.dev/viewer/?uri=github.com/aveproject/ave-api)
[![CodeQL](https://github.com/aveproject/ave-api/actions/workflows/codeql.yml/badge.svg)](https://github.com/aveproject/ave-api/actions/workflows/codeql.yml)

## What this is, and isn't

This is **a** reference implementation, not **the** standard. AVE itself,
the records and schema, lives in [aveproject/ave](https://github.com/aveproject/ave).
This service is a thin, read-only lookup layer over that data, provided so
implementers have a working example to call or fork rather than parsing raw
JSON files themselves. Anyone can run their own instance; nothing about AVE
depends on this specific deployment staying available.

## Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/` | Service info, record count, cache age |
| GET | `/records` | All records |
| GET | `/records/{ave_id}` | One record |
| GET | `/records/{ave_id}/mitigation` | The record's neutral `mitigation` object only |
| GET | `/search?q=...` | Substring search across title, description, attack class, behavioral fingerprint |
| GET | `/docs` | Interactive OpenAPI docs (auto-generated) |

No authentication. No write endpoints. Rate limited to 60 requests/minute
per IP as a basic abuse backstop, generous for any legitimate use.

## Running locally

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

## Data source

Fetches `dist/ave-records-latest.json` from
[aveproject/ave](https://github.com/aveproject/ave) on startup and every 15
minutes thereafter. This repo holds no copy of the record data itself;
`aveproject/ave` is the single source of truth.

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
