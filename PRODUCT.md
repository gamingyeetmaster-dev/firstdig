# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Owners and sales/outbound people at Toronto-area trade and B2B-services companies who prospect off public filings instead of waiting for inbound leads:

- **Teardown Feed** — pool builders, landscapers, fence and railing companies, window and door dealers, custom millwork shops, home automation installers, and moving companies. Their job: be the first call when a teardown, new house, multiplex, garden suite or major addition is filed with Toronto Building.
- **Opening Soon** — POS/payments reps, insurance brokers, food and beverage distributors, commercial cleaners, signage shops, and linen services. Their job: reach a restaurant, bar, café, clinic, salon or shop before it opens, while it's still deciding vendors.

Both personas work a sales pipeline and treat the product as a daily prospecting input (map, filters, CSV export, daily email digest), not a one-time report.

## Product Purpose

Two subscription data feeds, built from public filings and refreshed daily, that surface a building project or a soon-to-open business before it's visible any other way — early enough that a subscriber can be the first vendor to reach out. Success is a subscriber treating the daily digest as part of their prospecting routine and converting past the 14-day trial into a paid subscription.

Runs as one Python process against one SQLite file; Stripe and Resend are optional and the product works fully (with a manual/free trial flow) without them configured.

## Positioning

Not a lead-gen marketplace. The two feeds are built by reading the same primary-record filings the city and province already publish (Toronto Building permits, AGCO liquor licence applications, Toronto business licences), then joining, classifying, and geocoding them per address — not selling the same shared lead to multiple buyers. Opening Soon's specific mechanism is stacking three independent filings by address: two or more signals at one address is treated as a business that is confirmed to be opening, not a rumour. Timing is the edge — a permit or licence application lands 60–180 days before the subscriber's own customer needs their trade or service, well ahead of when a lead-gen list would surface the same address.

## Operating Context

- Toronto only, for now; positioned to add other Canadian cities (Vancouver, Calgary, Ottawa) as feeds are added, per NAME.md's naming rationale — the name and product were deliberately kept city-agnostic.
- Data refresh is daily (permits/licences) to monthly (neighbourhood boundaries); subscribers act on a "the morning after it's filed" cadence via the dashboard, map/filter UI, daily email digest, and CSV export into their own CRM.
- Free/logged-out visitors see a delayed, redacted sample (`FREE_DELAY_DAYS`, builder name and applicant details stripped); paying subscribers see same-day filings with names and contact details where the filing itself discloses them.
- All source data is under the Open Government Licence – Toronto / Ontario; the product does not append personal data from other sources beyond what a filer put on a public permit/licence.

## Capabilities and Constraints

- Two products today: Teardown Feed ($79/mo) and Opening Soon ($99/mo), plus a bundle ($149/mo); 14-day free trial of both, no card required to start.
- Five source datasets (Toronto Building active permits, Toronto business licences, AGCO liquor licence applications, Toronto address points, Toronto neighbourhoods) — see `app/config.py` `SOURCES` for URLs and `README.md` for refresh cadence.
- Terminology to preserve: "feed," "signal(s)" (an individual filing event on a business), "digest" (the daily email), "filed"/"filing" for source events, "declared cost" for permit-stated construction value.
- Team seats and API access exist only as an ad-hoc, email-negotiated arrangement (`pricing.html`), not a self-serve tier.
- Legal/compliance constraint: only publish names, business names, and phone numbers that the filer put on a public permit or licence; never enrich with personal data from other sources (stated as a selling point in `pricing.html`'s FAQ, so it's a claim the product must keep being true, not just a description).

## Brand Commitments

- Name: **First Dig**, chosen in a documented second naming pass (see `NAME.md`) after rejecting "EarlyFiled." Trademark search (Canadian, all fields) came back clean as of 2026-09-23; `firstdig.ca`/`.app`/`.io` available, `.com` on the aftermarket. Treat the name itself as settled; do not propose alternatives without the user reopening naming.
- Voice/copy in the current templates (short declarative sentences, concrete numbers, explicitly anti-"lead-gen"-hype) is a first draft, not locked in — future design and copy work may revise it freely.

## Evidence on Hand

Pre-launch: zero real customers, testimonials, usage numbers, or case studies exist yet (per `LAUNCH.md`, the code is complete but the product has not been deployed to a public domain). The site's own "stats" strip (`index.html`) pulls live counts from the local pipeline database, not fabricated numbers — keep that real-data pattern rather than adding invented social proof, logos, or quotes anywhere in future work.

## Product Principles

1. The product's credibility rests on being a faithful pass-through of primary public records, not an enriched or aggregated lead list — never blur that line in copy or design.
2. Timing (60–180 days of lead time) is the core value proposition; every surface should make "how early" and "how fresh" legible.
3. Users are working professionals running a sales pipeline daily, not one-time researchers — the product must read as a routine tool (digest, filters, export), not a report.
4. Don't fabricate evidence (customers, testimonials, logos, numbers) while the product is pre-launch; real, live pipeline stats are fine, invented proof is not.
5. Toronto-first but not Toronto-locked in language or architecture — avoid hard-coding assumptions that would need to be undone when a second city is added.
