# LANGUAGE.md - aveproject/ave-api

Small vocabulary, kept small on purpose; this is a simple service and
doesn't need an elaborate style guide.

- **"record," never "entry."** Matches `aveproject/ave`'s own terminology.
  An AVE record is not a database entry or a row; it's a defined,
  versioned unit of the standard.
- **"cache," never "database."** This service has no database. Calling
  the in-memory dict a "database" anywhere, in code comments, docs, or
  commit messages, misdescribes the architecture and invites someone to
  eventually add one that isn't needed.
- **"implementation," not "consumer," when referring to a tool built
  against AVE.** Matches `aveproject/ave`'s own `CONTEXT.md`.
- **"a reference API," not "the AVE API."** See `CONTEXT.md`'s framing
  discipline section; this is the same principle applied as a mechanical
  writing rule.
- No em dashes, anywhere, in any file, including code comments and commit
  messages. Matches the convention already enforced across every AVE
  project repo.
