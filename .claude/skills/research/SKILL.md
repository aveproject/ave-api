---
name: research
description: Investigate a task, bug, or question before writing any code. Use before starting work on anything non-trivial.
---

Read `CONTEXT.md`, `ARCHITECTURE.md`, and `CLAUDE.md` first, every time,
even if this feels repetitive; this repo is small enough that skipping
this step saves little time and risks missing a hard rule.

Then investigate the actual codebase: read `main.py` in full, not just the
section that seems relevant, since this service is small enough that
"just the relevant part" often misses a hard rule stated elsewhere (rate
limiting, resilience patterns, the neutrality boundary on `/mitigation`).

Output: a short written summary of what was found, what's actually being
asked for, and which existing file(s) and pattern(s) the work should
follow. Do not write implementation code in this step.
