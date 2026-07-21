---
name: code-review
description: Review a change against this repo's actual standards before it merges. Use as the last step, after implement.
---

Check, explicitly, not as a vague pass/fail impression:

- Every hard rule in `CLAUDE.md`, re-checked against the actual diff, not
  just the original plan; implementations sometimes drift from what
  grill-with-doc validated.
- No em dashes anywhere in the diff, including comments and any new
  documentation.
- No stray reference to a specific vendor's product name in new code or
  docs, unless it's naming the actual, established reference
  implementation, and even then only in a context that explains what it
  is to a first-time reader, per `CONTEXT.md`'s framing discipline.
- New routes have rate limiting. New outbound calls have timeouts and
  failure handling that degrades gracefully rather than raising past
  valid cached data.
- The change is the smallest version of itself that solves the actual
  ticket; flag anything that looks like it grew scope during
  implementation.
