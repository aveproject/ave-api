# Changelog

All notable changes to this project are documented here. Format loosely
follows [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Changed

- Hosting switched from the planned Render deployment to Google Cloud
  Run for the first production deployment (`--min-instances 0`,
  `--max-instances 3`, `us-central1`), accepting the card-on-file
  tradeoff in exchange for a persistent-container model that matches
  this service's in-memory cache design. A $1 budget alert is the
  concrete mitigation. See `ARCHITECTURE.md`'s ADR section for the full
  reasoning.

### Fixed

- `Dockerfile` only copied `main.py`, never `constants.py`, so the
  built image crashed on startup with `ModuleNotFoundError` before
  `uvicorn` ever bound to the port. Caught by the first real deploy
  attempt; `python3 -m py_compile main.py` never catches this since it
  runs against the full checked-out repo, not the trimmed set of files
  the Dockerfile actually copies into the image.
- The fix for the above (`COPY main.py constants.py .`) built fine
  locally under BuildKit but failed on Cloud Build's classic builder,
  which enforces the Dockerfile spec strictly: a multi-source `COPY`'s
  destination must end with `/`.

## [1.0.0] - initial release

### Added

- `GET /`, `GET /records`, `GET /records/{ave_id}`,
  `GET /records/{ave_id}/mitigation`, `GET /search`.
- In-memory cache of `aveproject/ave`'s consolidated record dump, fetched
  from the unversioned `dist/ave-records-latest.json` alias and refreshed
  every 15 minutes, so this service never needs a code change when the
  schema version bumps.
- Resilience baked in from the start: a refresh failure serves the last
  known-good cache instead of failing every route, and a failed initial
  fetch starts the service degraded (empty cache, retries on first
  request) rather than crash-looping.
- `cache_age_seconds` in the `GET /` response, surfacing cache staleness
  rather than hiding it.
- Rate limiting (60 req/min per IP) and basic security headers
  (`X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`).
- `CONTEXT.md`, `LANGUAGE.md`, `ARCHITECTURE.md`, `CLAUDE.md`,
  `docker-compose.yml`, `.pre-commit-config.yaml`.
- Six custom skills under `.claude/skills/`: `research`, `grill-with-doc`,
  `to-spec`, `to-tickets`, `implement`, `code-review`.
- CodeQL, Dependabot, and OpenSSF Scorecard CI workflows.
- `GOVERNANCE.md`, `SECURITY.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`.

### Notes

- Repo is public, matching `GOVERNANCE.md`'s own stated principle that any
  implementer may run their own instance from this source.
- Hosting: evaluated Vercel (rejected, serverless-only Python is
  incompatible with the in-memory cache design), Cloud Run, and Render;
  Render chosen as primary. See `ARCHITECTURE.md`'s ADR section for the
  full reasoning.
