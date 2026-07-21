# Security Policy

## Reporting a vulnerability

Email aveproject.org@gmail.com. Please do not open a public issue for a
security report until a fix is available; give a reasonable window to
respond before public disclosure, informally 90 days unless the report
itself indicates something actively being exploited, in which case sooner
coordinated disclosure is appropriate.

## Scope

This service is read-only, unauthenticated, and serves only public data
already published in [aveproject/ave](https://github.com/aveproject/ave).
There is no user data, no write path, and no secrets held by this service
beyond standard deployment credentials. Rate limiting (60 requests/minute
per IP) is in place as a basic abuse backstop; a report that this can be
bypassed is a valid, in-scope finding. Reports of highest value: anything
that could turn this into a write path, an SSRF vector (this service does
make one outbound fetch, to a fixed, hardcoded GitHub raw content URL, not
user-controlled), or a denial-of-service vector beyond what the existing
rate limiting already mitigates.

## What this is not the right place to report

A misclassification, wrong severity, or incorrect field in an AVE record
itself is a data-quality issue with the standard, not a security
vulnerability in this API. Report those to
[aveproject/ave](https://github.com/aveproject/ave/issues) instead.
