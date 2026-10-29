# First Dig: source-linked Toronto opening intelligence

**Live proof:** [run the five-minute buyer decision test](https://first-dig-night-shift.onrender.com/decision-test) · [commercial milestone](https://github.com/gamingyeetmaster-dev/firstdig/issues/23)

First Dig turns separate Toronto public filings into a small, privacy-safe decision surface for suppliers to newly opening businesses. The product is technically live and commercially unproven: **0 independent buyer results, 0 paying customers, CAD $0 collected** as of October 29, 2026.

## What is demonstrated

| Proof | Verified evidence |
|---|---|
| Real processing scale | The active-permit ingestion requests a complete snapshot and rejects fewer than 100,000 rows rather than accepting a truncated feed ([PR #16](https://github.com/gamingyeetmaster-dev/firstdig/pull/16)). The latest observed production recovery built **6,734 project records**. This is pipeline output, not a lead or customer count. |
| Multi-source join | Opening Soon associates business licences, active building permits, and AGCO notices at a common address, while distinguishing filing volume from distinct source categories. |
| Buyer-visible provenance | After two decisions, the live test reveals filing counts, latest dates, and links to the official Toronto datasets—without exposing raw record IDs ([PR #25](https://github.com/gamingyeetmaster-dev/firstdig/pull/25)). |
| Fail-closed recovery | Public routes return 503 while the ephemeral cache is missing or stale ([PR #15](https://github.com/gamingyeetmaster-dev/firstdig/pull/15)). Transient-source retries may use only still-fresh cached inputs; expired inputs and partial snapshots remain rejected ([PR #21](https://github.com/gamingyeetmaster-dev/firstdig/pull/21)). |
| Public privacy | Anonymous records remove names, contacts, coordinates, civic numbers, units, ranges, fractions, and suffixes. The residual-address regression was fixed in [PR #22](https://github.com/gamingyeetmaster-dev/firstdig/pull/22). |
| Automated verification | [GitHub Actions run 40842127857](https://github.com/gamingyeetmaster-dev/firstdig/actions/runs/40842127857) passed the application test job; the merged source-trail release reports **42 tests**. The workflow's live-smoke job was skipped, so CI alone is not deployment proof. |
| Production verification | Browser QA on October 29 confirmed the live delayed/redacted pair, two-decision reveal gate, official source links, and 6,734-project fresh readiness. Active Render deploy identity and recovery no-email logs remain unverified because no workspace has been expressly selected. |

## The decision instrument

The public test deliberately hides source diversity until the participant has acted on both records:

1. Compare two real, delayed and redacted Opening Soon records.
2. Choose **contact today**, **research later**, or **ignore** for each.
3. Reveal whether the evidence is repeated filings from one source or corroboration across source categories.
4. Inspect official dataset links, filing counts, and dates.
5. Voluntarily copy or email only the bounded result; nothing is submitted automatically.

The intended participant is a Toronto supplier to newly opening restaurants or shops—POS/payments, signage, commercial insurance, business telecom, or similar. Residential Teardown contractors are a separate segment and their feedback must not be treated as Opening Soon validation.

## 75-second screen-recording storyboard

- **0–8s — Problem:** show three official-source inputs and the question: “Which new business is worth a seller's time?”
- **8–20s — Scale and safety:** show the readiness response with fresh status and 6,734 projects; overlay “partial or stale inputs fail closed.”
- **20–42s — Uncoached choice:** open the live decision test, point out delayed real records and hidden numbers, then choose one action for each without explaining source diversity.
- **42–58s — Evidence reveal:** reveal the two-source versus one-source result and open the official Toronto dataset links.
- **58–68s — Privacy boundary:** show the absence of names, contacts, coordinates, exact addresses, and record IDs.
- **68–75s — Honest close:** display “42 tests · 0 independent buyer results · CAD $0 collected” and link to issue #23.

## Architecture and failure boundary

```text
Toronto/AGCO sources
        ↓  validate snapshot size + freshness
atomic source cache
        ↓  normalize and join by address
project + opening records
        ↓  readiness requires fresh, non-empty output
public redacted views / authenticated detail
```

This design prefers an explicit 503 over presenting an empty market, an incomplete join, or stale data as current. The public test is a validation instrument, not evidence that buyers want the product.

## Commercial gate

Production still reports `auth_store=sqlite`. Before collecting payment or enabling subscription email, [issue #12](https://github.com/gamingyeetmaster-dev/firstdig/issues/12) requires an authorized current-instance inventory, transactional migration and reconciliation, secret binding, and restart-persistence verification. Recovery no-email behavior must be proven from service logs, not UI copy.

The next proof milestone is [issue #23](https://github.com/gamingyeetmaster-dev/firstdig/issues/23): one consented, uncoached Opening Soon buyer result, followed by an explicit CAD $99 pilot yes/no, useful cadence, and purchase authority. Until that happens, no adoption, demand, revenue, or customer-validation claim is warranted.

## Defensible application bullet

> Built a fail-closed Toronto public-data pipeline that rejects truncated permit snapshots, joins licensing/permit/AGCO evidence into 6,734 current project records, and exposes a privacy-safe, source-linked buyer decision test; 42 automated tests passed, while independent buyer validation and revenue remain at zero.
