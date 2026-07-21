# Governance

This repo is a reference implementation of the AVE standard, not the
standard itself. Its governance is intentionally lighter than
[aveproject/ave](https://github.com/aveproject/ave)'s, which governs the
standard's own succession, decision process, and trademark terms; see that
repo's own GOVERNANCE.md for those.

## Maintainer

Maintained by the AVE Project. Contact: aveproject.org@gmail.com.

## Decision process

Small, low-stakes changes (dependency bumps, documentation fixes, minor
endpoint additions that don't change existing behavior) may be merged by
the maintainer directly. Anything that changes an existing endpoint's
response shape, removes an endpoint, or adds authentication should be
raised as an issue for discussion before a PR is opened, since those are
the kinds of changes that break something a second implementer may already
depend on.

## This is not the only reference implementation, and doesn't need to be

Nothing about the AVE standard requires this specific service to exist or
stay available. Anyone may run their own instance from this repo's source,
or write an entirely different one against `aveproject/ave`'s raw record
data directly. If this instance ever becomes unmaintained, the standard
itself is unaffected; that separation is the point.
