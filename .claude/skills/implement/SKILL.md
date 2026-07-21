---
name: implement
description: Build one ticket from to-tickets. Use after to-tickets, before code-review.
---

Implement exactly the ticket's scope, nothing adjacent, even if adjacent
cleanup is tempting. If something adjacent genuinely needs fixing, note it
as a new, separate ticket rather than folding it into this change.

Write or update tests alongside the change, not after. This is a small
enough codebase that untested logic is a real, avoidable risk, not an
acceptable shortcut.

Run `python3 -m py_compile main.py` at minimum before considering the
implementation done; a syntax error caught in code review that a
thirty-second local check would have caught is wasted review time.
