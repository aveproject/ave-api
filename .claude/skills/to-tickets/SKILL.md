---
name: to-tickets
description: Break a spec into independently-shippable tasks. Use after to-spec, before implement.
---

Split the spec into the smallest set of independently-committable changes,
matching this project's own established convention: one task, one branch,
one PR per concern, never bundling unrelated fixes into a single commit
just because they were discussed in the same session.

Each ticket should be small enough to review in one sitting. If a ticket
touches both `main.py` logic and a documentation file, consider whether
those are actually two tickets.
