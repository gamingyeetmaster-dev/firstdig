# First Dig — trade-proof validation protocol (8 October 2026)

**Status:** Internal research and QA protocol. **No outreach authorized.** All eight previously contacted companies remain protected; Land-Con, Gib-San and Ferrari Fences are not to receive another message unless they reply. The five 3 October prospects (Bradley Demolition & Excavation, Buildtrus, Metro Demolition & Excavation, Shorecon, New Depths) are also not to be re-contacted during the gate.

## Decision to test

A permit feed is not a unique product. PermitIndex already publishes Toronto permits by trade and neighbourhood, including demolition and pool categories, and offers daily alerts and paid exports. Its stated target is material suppliers and territory planning. First Dig's **unproven** advantage must be *contractor-ready decisions*: a source-linked, stage-aware explanation of why a project might fit a specific trade, when to verify it, and what uncertainty prevents it from being treated as a sales lead. Do not call a permit holder a customer or imply that a contractor is looking for quotes.

**Kill criterion:** If a contractor reviewing 20 consecutive eligible projects cannot identify at least five actionable, non-obvious next checks that the existing City/competitor view did not make obvious, and would not opt into another review, stop building trade scoring and revisit the offer. This is a proposed validation threshold, not observed demand.

## Three source-backed proof slices

| Trade | Public market evidence (dated) | First Dig must demonstrate | Exclude / caveat |
| --- | --- | --- | --- |
| Demolition & excavation | PermitIndex's 5 Oct 2026 page reported 1,600 demolition permits issued in the prior 12 months; median 43 days from application to issue; top listed areas included Yonge-Bay Corridor, Yorkdale-Glen Park and Newtonbrook West. https://permitindex.ca/toronto/trades/demolition | Join demolition with related new-build / revision records **at the same normalized address**; show permit status, issue date, permit IDs and confidence in sequencing; ask contractor whether this changes timing or project fit. | Do not infer that demolition work remains unawarded, that a rebuild is certain, or that all permits are residential. |
| Underpinning / basement | City active-permit data includes work and description fields, which First Dig's existing code searches for underpinning/basement terms. The competing addition feed is not evidence that all underpinning opportunities are covered. https://open.toronto.ca/dataset/building-permits-active-permits/ | Show exact source text triggering classification, structural scope, application/issue stage, and ambiguity between underpinning and basement apartment. Independently review 20 candidates before making precision claims. | No unsupported structural-engineering conclusions; exclude false positives from generic basement descriptions. |
| Pool / landscape / fencing | PermitIndex's 21 Sep 2026 page reported 177 pool-related permits over the prior 12 months and a median 30-day application-to-issue interval. https://permitindex.ca/toronto/trades/pools | Separate enclosure, deck/cabana and actual pool-work evidence. Label adjacent opportunities as *possible* rather than contracted work; distinguish pool builders from landscape suppliers. | Pool enclosure signals do not prove a pool-installation lead; local bylaw and seasonal context need confirmation. |

All competitor counts above are **dated page snapshots**, not verified First Dig counts or today's available leads. The City publishes active and cleared permits separately. Absence from the active file means no longer in that active snapshot, **not necessarily that a project was completed**: https://open.toronto.ca/exploring-cleared-building-permits/. City permit status search is described as updated through the previous business day: https://www.toronto.ca/services-payments/building-construction/building-permit/after-you-apply-for-a-building-permit/search-the-status-of-a-building-permit-application/.

## Reviewer protocol: 20 consecutive records per trade, no cherry-picking

1. Freeze the source snapshot timestamp, parser commit and 20 consecutive eligible permit IDs (not the top-scored 20). Record source freshness and any unavailable fields.
2. Two reviewers independently label each: **confirmed relevant / potentially relevant / irrelevant / insufficient evidence**, and **new actionable next check / already obvious / no action**. Disagreements are adjudicated before counting.
3. Present City source view and a competitor's publicly accessible view first, then First Dig's trade-matched explanation. Avoid giving First Dig an unfair information advantage.
4. Record evidence for stage, geography, trade, and uncertainty. Count precision among reviewed 'confirmed relevant' records; do not treat a potential match as confirmed.
5. Ask an authorized contractor whether they would spend 10 minutes reviewing another batch and whether any of the checks would change prioritization. Record exact qualitative responses with consent, including negative feedback.
6. Publish only aggregate anonymized findings and denominators. No customer lists, owner names, fabricated testimonials, or speculative dollar ROI.

### Minimal evaluation fields

`source_snapshot_date, permit_id, trade, city_source_url, city_stage, evidence_excerpt, classification, reviewer_1, reviewer_2, adjudicated_label, firstdig_unique_check, contractor_useful_yes_no, reason, limitations`

Do not claim a pilot was run until a real, permissioned contractor actually reviews records.

## Compliance gate — keep sending CLOSED

No new Canadian commercial email until **both** cooldown and the complete preflight pass:

- A genuine, valid First Dig **business mailing address** where mail can be received (never invent one; never use the founder's home address) **and** another contact method.
- Truthful identification of the sender and on-whose-behalf, plus a working, monitored unsubscribe mechanism and suppression process.
- Per-recipient consent basis documented with date, original **conspicuously published** address on a source controlled or caused by recipient, no accompanying no-solicitation notice, and a specific connection between offer and recipient's business role; alternatively another valid consent basis. A third-party scraped directory is not enough.
- Check all existing contact history, bounces, replies, opt-outs and duplicates before any future send.

Primary CRTC guidance: https://www.crtc.gc.ca/eng/com500/faq500.htm and https://web.crtc.gc.ca/eng/internet/anti/reg.htm. This is a workflow checklist, not a legal opinion. No new emails, direct messages, or unsolicited contact should be sent under this protocol.

## Inbound handling

If an actual reply arrives: preserve original thread and timestamp; classify as interested / request for proof / objection / unsubscribe / bounce / unrelated. Honour opt-outs immediately and suppress. For interested replies, respond only after checking the message and sender, and offer a **local/offline, permissioned 20-inquiry audit** using synthetic data first; do not ask for customer contact lists by email. If no replies, leave contact state unchanged.

## Technical prerequisites and truthful claims

- First Dig's permit loader currently upserts but does not reconcile records missing from the City's active snapshot. A candidate correction exists on a separate branch, **not deployed**. Before any 'active opportunity' claim, validate complete City source, missing-record handling, and rollback on an actual staging DB.
- The durable auth/trial/billing/digest adapter was merged at `7ec489cd94c64818c26b44f988cf0a4443ec1404`, but production persistence remains **unverified** until the existing Render Postgres URL is privately configured as `AUTH_DATABASE_URL`. Never expose credentials. Free validation DB expires 28 Oct 2026.
- The First Dig offline lead-gap audit v4.1 is a synthetic-data-tested prototype, **not proof of customer demand**. Use it only with permission and an explicit data-handling agreement.
- Never claim live permits, guaranteed work, qualified buyers, conversion, revenue, award, partnership, or customer results without actual evidence.

## Next measurable outcome

Obtain one **inbound or otherwise permissioned** contractor reviewer, conduct the 20-record blinded comparison for one trade, and record the full denominator, reviewer disagreement and one explicit 'would you use this again?' answer. Until then, keep growth in research/proof mode and do not launch another generic feature or email batch.
