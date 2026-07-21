---
name: test
description: Write tests for a change following red-green-refactor TDD, testing behavior through this service's public HTTP interface rather than internals. Use during implement, before considering a ticket done.
---

Write the test first. Watch it fail for the right reason, a missing
behavior or a real bug, not a typo or an import error, then write the
minimum code to make it pass, then refactor with the test as a safety
net. Skipping straight to the implementation and testing it afterward is
not TDD, even if a test file ends up next to the code.

Test through `/records`, `/records/{ave_id}`, `/records/{ave_id}/mitigation`,
and `/search` with FastAPI's `TestClient`, the same way a real caller
would, rather than importing and calling `_refresh_cache()` or
`_ensure_fresh()` directly. A test that reaches into an internal function
locks in that function's shape and breaks on refactors that don't change
any actual behavior; a test that hits the HTTP interface survives them.

Never let a test touch the real network. `main.py` makes exactly one
outbound call, to `aveproject/ave`'s raw content; monkeypatch
`main._refresh_cache` to populate `main._cache` with a small, fake
fixture of one or two records instead of hitting GitHub. A test suite
that depends on GitHub being up, or on `aveproject/ave`'s current record
content, is not a test suite, it is a flaky integration check wearing a
test's clothes.

Reset shared state before every test: `main._cache` and `main.limiter`'s
storage are both module-level singletons that persist across the whole
test session unless something clears them. An autouse fixture that
resets both before each test is not optional scaffolding, it is what
makes the rest of the suite trustworthy; without it, test order starts
to matter and failures stop being reproducible.

One behavior per test, named as a sentence that describes it,
`test_get_mitigation_404s_when_record_has_no_mitigation`, not
`test_mitigation` or `test_2`. If a test's name can't describe what it
checks in one sentence, it's checking more than one thing and should be
split.

Cover the behaviors that are actually load-bearing for this repo, not
just the happy path:
- Every route's 404 case, worded well enough that whatever it says is
  actually useful to whoever hits it.
- `/mitigation` returns the neutral `mitigation` object, and nothing
  else, and 404s cleanly when a record has none.
- `/search` matches across all four documented fields (`title`,
  `description`, `attack_class`, `behavioral_fingerprint`),
  case-insensitively, and returns an empty list rather than an error
  for no matches.
- The resilience pattern from `CLAUDE.md`: a refresh failure with a
  populated cache serves the stale data (200, not 500); a refresh
  failure with an empty cache is a real failure (500, it has to
  surface); startup logs and continues on a failed initial fetch rather
  than crash-looping.
- Every route carries its `@limiter.limit(...)` decorator; a route
  discovered without one while writing its tests is a bug in that
  route, not a gap in the test.

Run `pytest` before considering a ticket done, same bar as
`python3 -m py_compile main.py` in `implement`'s own checklist: a red
suite caught in code review that a local run would have caught is
wasted review time.
