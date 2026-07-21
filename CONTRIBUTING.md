# Contributing

This is a small, deliberately minimal service. Before opening a PR that
adds a feature, consider whether it belongs here at all: this repo's job is
read-only lookup over AVE's published data, nothing more. Feature requests
that turn this into something bigger (a write API, an auth layer, a
database) are likely better served by a different, separate service someone
builds against `aveproject/ave`'s raw data directly, not an addition to this
one.

## Local development

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

## Before opening a PR

- Run the validation commands in `README.md` against your local instance.
- Confirm CodeQL and Scorecard checks pass in CI; they run automatically on
  every PR.
- Keep changes to one concern per PR, matching how this repo's own initial
  setup was structured, one task, one branch, one PR.
