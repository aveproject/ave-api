---
name: grill-with-doc
description: Interrogate a proposed change against this repo's own documented principles before agreeing to build it. Use after research, before writing a spec.
---

Take the research output and the proposed change, and check it against
every hard rule in `CLAUDE.md` and every principle in `CONTEXT.md`,
explicitly, one by one, not as a vague gut check.

Ask, out loud, in the conversation, not just internally:
- Does this add a write endpoint? (Hard no, per `CLAUDE.md`.)
- Does this introduce a dependency on anything beyond `aveproject/ave`?
- Does this change what `/mitigation` can return?
- Does this add a route without rate limiting?
- Does this add an outbound call without a timeout and without failure
  handling that preserves the resilience pattern in `_ensure_fresh()`?
- Is there a simpler version of this that does less, given `CONTEXT.md`'s
  instruction to keep this service boring on purpose?

If the proposed change fails any of these, say so directly and propose the
narrower version, rather than building the version as originally
described and hoping it's fine.
