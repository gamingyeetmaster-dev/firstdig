# First Dig: Toronto permit intelligence case study

**Status as of October 13, 2026:** live technical prototype. No customer adoption, revenue, partnership, or accuracy benchmark is claimed.

[Open the live application](https://first-dig-night-shift.onrender.com) · [View the source](https://github.com/gamingyeetmaster-dev/firstdig)

## The problem

Toronto publishes valuable construction, licensing, and liquor-application records, but each source has different fields and update patterns. A contractor evaluating new work must still answer practical questions:

- Is this record recent enough to matter?
- Which trade does the work actually involve?
- Do several filings point to the same project?
- Is the opportunity inside the contractor's service area?
- Is there enough evidence to investigate, or should it be rejected quickly?

First Dig explores whether those records can become a smaller, source-linked decision feed instead of another large permit search.

## What the product does

First Dig currently builds two feeds from public records:

1. **Teardown Feed** groups Toronto building permits by project, classifies residential scopes, geocodes them, and supports geographic filtering.
2. **Opening Soon** joins business licences, liquor applications, and commercial fit-out permits at the same address to identify addresses with one or more relevant filings.

The application includes magic-link authentication, trial entitlements, product-specific access controls, administrator diagnostics, daily data refresh, and optional Stripe, Resend, and Postgres integrations.

## Verified operating snapshot

This snapshot was verified from the production recovery that started at **2026-10-13 10:38:46 UTC**. Source counts can change on later refreshes.

| Measure | Verified result |
|---|---:|
| Active-permit source rows processed | 202,293 |
| Teardown Feed projects built | 6,676 |
| Opening Soon records built | 2,389 |
| Opening records with at least two filings | 244 |
| Production readiness after recovery | Ready and fresh |
| Email sent during recovery | None |

The filing count is not a count of independent sources: repeated permits or licences at one address can contribute multiple filings. Cross-source corroboration requires distinct source categories, tracked separately in [issue #8](https://github.com/gamingyeetmaster-dev/firstdig/issues/8).

These are pipeline outputs, not customers, qualified leads, or revenue.

## Engineering decisions

### Data-only recovery

A sleeping free host can wake after the intended refresh window. First Dig now performs bounded late recovery when its local dataset is missing or stale, while keeping email delivery disabled. A host-local lock prevents overlapping refresh work, and readiness remains false until the rebuilt dataset is non-empty and verified.

### Public privacy boundary

Anonymous Opening Soon pages do not expose exact coordinates, raw address identifiers, detail links, or a map. Exact project detail remains behind authenticated entitlements. The public GeoJSON response is empty for anonymous visitors, and direct requests for known raw-address detail return 404.

### Commercial-state migration

Account state can be moved from local SQLite to Postgres using a fail-closed one-shot migration. The command:

- inventories the source without exposing row contents;
- migrates users, magic links, and sent-digest history in one transaction;
- preserves IDs, trials, plan state, Stripe identifiers, preferences, token state, and digest deduplication history;
- accepts only an empty or exactly matching destination;
- reconciles every migrated row before commit;
- is idempotent and rolls back on conflicts.

The migration code is deployed, but the production cutover has not been performed. Production still reports auth_store=sqlite.

## Verification evidence

- 22 application tests passed in [GitHub Actions run 38357147552](https://github.com/gamingyeetmaster-dev/firstdig/actions/runs/38357147552).
- Privacy hardening shipped in [pull request #3](https://github.com/gamingyeetmaster-dev/firstdig/pull/3).
- Commercial-state migration shipped in [pull request #5](https://github.com/gamingyeetmaster-dev/firstdig/pull/5).
- The deployed migration release is commit [529de320](https://github.com/gamingyeetmaster-dev/firstdig/commit/529de320127fde1f554864138feaa44b22ff0433).

## Honest release boundary

First Dig is not ready to charge customers or send new Canadian commercial email.

Before commercial use, the project still needs:

1. a production SQLite inventory and recoverable snapshot;
2. execution and reconciliation of the commercial-state migration;
3. an authorized Postgres secret binding;
4. restart testing for account, trial, preference, and digest persistence;
5. durable email-outbox handling;
6. compliant sender identification, a real business mailing address, applicable consent, and unsubscribe handling;
7. interviews or observed use proving that the feed improves contractor decisions.

## Next validation

The next useful customer test is not “Would you buy permit data?” It is a short, consented comparison using real projects:

1. show a contractor a normal permit record and a First Dig project summary;
2. ask whether each project is worth investigating;
3. record decision time, missing information, and rejection reasons;
4. verify the conclusion against the linked public source;
5. stop if the summary does not produce faster or more defensible decisions.

That experiment would create evidence of customer value. The current pipeline and test results establish technical progress only.
