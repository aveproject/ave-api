# CONTEXT.md - aveproject/ave-api

Context for anyone working on this repo, contributors and Claude Code
sessions alike. This repo is public; nothing below assumes the reader has
any prior history with this project.

## What this is

A read-only reference API for AVE (Agentic Vulnerability Enumeration).
Four endpoints: list records, get one record, get one record's neutral
mitigation object, search. No auth, no write path, ever.

## What this is not

Not the standard. AVE itself, its records and schema, lives in
[aveproject/ave](https://github.com/aveproject/ave); this repo has no
authority over that content and holds no copy of it, checked in, ever.
Not the only reference implementation, either, and doesn't need to be:
`GOVERNANCE.md` states plainly that anyone may run their own instance from
this source, and nothing about AVE depends on this specific deployment
staying available.

Not a threat-intelligence product. If a feature request would turn this
into scanning, detection, scoring, or anything beyond looking up records
that already exist, it belongs in a different, separate project, not an
addition here. Keep this boring on purpose.

## Data flow, one direction

`aveproject/ave` publishes `dist/ave-records-latest.json`. This service
fetches it, caches it in memory, and serves it back out through four thin
endpoints. Nothing here originates data, transforms it meaningfully, or
stores a durable copy anywhere. If a task description involves writing new
record content, generating new fields, or anything that isn't "fetch,
cache, serve," stop and check whether the task actually belongs in
`aveproject/ave` instead.

## Framing discipline

Never describe this as "the AVE API," definite article, implying the only
one. "A reference API for AVE" or "the AVE reference implementation" is
correct.

Never let this repo's own docs, README, or code comments describe a
third-party product or service, however closely associated with this
project's maintainers, as though it were part of the AVE standard or a
required dependency of this service. This service depends on
`aveproject/ave` alone. If it's ever worth mentioning that some other tool
happens to interoperate with AVE, that belongs in `README.md`'s own
clearly-labeled list of related projects, explained plainly enough for a
first-time reader, not referenced here as though the name alone were
self-evident. Anyone reading this file may be encountering this project
for the first time; nothing here should assume they already know its
history.

## How to work on this repo

See `CLAUDE.md` for session rules, including the resilience and security
rules. See `ARCHITECTURE.md` for how the service is actually structured.
See `GOVERNANCE.md` for decision process. See `SECURITY.md` before
touching anything auth- or network-adjacent, even though there's no auth
today; the file explains why and what would change that.
