---
name: First Dig
description: Shipment Tracking — Toronto permit/licence filings read as a courier's status trail, not a notice board.
colors:
  ink: "#0e1a2b"
  ink-2: "#46566b"
  ink-3: "#5c6b7e"
  surface: "#ffffff"
  surface-2: "#f2f4f7"
  surface-3: "#e8ebef"
  rule: "#d7dde5"
  navy: "#0e1a2b"
  on-navy: "#ffffff"
  focus: "#2f6fed"
  focus-wash: "#dce8fd"
  teardown: "#b06a12"
  teardown-ink: "#8a5210"
  teardown-wash: "#fbe9d2"
  opening: "#0e7c74"
  opening-ink: "#0b5f59"
  opening-wash: "#d9f0ee"
  warn: "#8a5210"
  warn-wash: "#fbe9d2"
  bad: "#8a2c22"
  bad-wash: "#f6ddd8"
typography:
  display:
    fontFamily: "Barlow Semi Condensed, system-ui, sans-serif"
    fontSize: "clamp(34px, 4.6vw, 54px)"
    fontWeight: 700
    lineHeight: 1.05
    letterSpacing: "normal"
  headline:
    fontFamily: "Barlow Semi Condensed, system-ui, sans-serif"
    fontSize: "clamp(22px, 2.6vw, 28px)"
    fontWeight: 700
    lineHeight: 1.05
  title:
    fontFamily: "Barlow Semi Condensed, system-ui, sans-serif"
    fontSize: "18px"
    fontWeight: 600
    lineHeight: 1.05
  body:
    fontFamily: "Public Sans, system-ui, -apple-system, 'Segoe UI', sans-serif"
    fontSize: "15.5px"
    fontWeight: 400
    lineHeight: 1.55
  label:
    fontFamily: "Overpass Mono, ui-monospace, Menlo, monospace"
    fontSize: "11px"
    fontWeight: 600
    lineHeight: 1
    letterSpacing: "0.06em"
rounded:
  none: "0px"
  sm: "3px"
  md: "4px"
spacing:
  xs: "8px"
  sm: "12px"
  md: "18px"
  lg: "24px"
  xl: "32px"
  xxl: "44px"
components:
  button-primary:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.surface}"
    typography: "{typography.body}"
    rounded: "{rounded.md}"
    padding: "10px 16px"
  button-primary-hover:
    backgroundColor: "{colors.ink-2}"
    textColor: "{colors.surface}"
  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.ink-2}"
    rounded: "{rounded.md}"
    padding: "10px 16px"
  pill:
    backgroundColor: "{colors.surface-3}"
    textColor: "{colors.ink-2}"
    typography: "{typography.label}"
    rounded: "{rounded.sm}"
    padding: "5px 8px"
  value-tag:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.surface}"
    typography: "{typography.label}"
    rounded: "{rounded.sm}"
    padding: "3px 7px"
  track-card:
    backgroundColor: "{colors.surface}"
    rounded: "{rounded.md}"
    padding: "32px"
---

# Design System: First Dig

## Overview

**Creative North Star: "Shipment Tracking"**

First Dig now reads like the tracking page a subscriber already trusts with a real shipment: navy ink on white and cool-gray, hairline rules, a timestamped status rail, and mono values wherever a fact came straight off a filing. It replaces "Posted Notice" (kraft paper, tape, staples, hand-torn edges, marker script), which the product owner rejected as unprofessional/novelty for a $79–149/month B2B tool. Every physical-collage device — rotation, tape marks, staples, torn edges, a handwriting display face, a warm cream/kraft ground — is gone, not toned down. Depth is flat: 1px hairline borders and a single 4px radius, never a thin-border-plus-wide-soft-shadow combination.

The direction contract for this world called for a fabricated mono "tracking-code" per record (format `TDF-2026-04471`) as a flourish. The shipped build deliberately does not render one anywhere on the site — there is no real tracking-code field in the source data (`STAGE_LABELS`/permit records carry no reference number), and inventing one would violate PRODUCT.md's "faithful pass-through of primary public records" principle. Where the source cites a record, it renders the real source name instead (`.track-code`: "Toronto Building · permit record", "AGCO · licence · permit"). This is a deliberate, load-bearing omission — the build wins over the direction contract here, and no future surface should add an invented reference-number device to satisfy the contract's letter over the product's honesty constraint.

This pass extended the system from homepage + two dashboards to the whole site. `pricing.html`, `product_teardown.html`, `product_openings.html`, `detail_project.html`, `detail_opening.html`, and `account.html` are now migrated: `pricing.html` needed almost no change (it already inherited the system's tokens, cards, and `.notice` banners correctly); `product_teardown.html`/`product_openings.html` gained a `.track` hero reusing the homepage's real-record tracking card, and their "who uses it" / "three filings" explainer grids moved from ad-hoc layouts onto `.differentiators`; `detail_project.html`/`detail_opening.html` gained the new vertical `.event-rail` showing a record's real historical events; `account.html` gained the new `.picker` component in place of an inline-styled reuse of the dashboard `.rail`. Only `login.html`, `methodology.html`, and `terms.html` remain outside the migration — `login.html` in particular is a plain form-in-a-card that never used `.hero`/`.eyebrow`; all three inherit the shared tokens, nav, footer, buttons, and `.notice` banner styling like every other page. Note: an earlier version of this file described `.hero .eyebrow` as unremoved drift on the not-yet-migrated pages; a direct scan of every template this pass found none using `.hero`, `.eyebrow`, or `.timeline` any longer, so those dead CSS rules were removed from `app.css` in this same pass rather than left as a trap for a future reuse.

A real bug was fixed in this pass: `app.css` defined `.notice-box`/`.notice-box.ok`/`.notice-box.err`, but every caller (`account.html`, `login.html`, `pricing.html`) used `class="notice"` — a class-name mismatch that left every success/error banner on those three pages completely unstyled (no border, no background, no color distinction between success and error). Fixed by renaming the CSS rules to `.notice`/`.notice.ok`/`.notice.err` to match the callers, which also gave `.notice.err` a background wash (`--bad-wash`) it never had before. See the Components → Notice Banner entry and the Do's and Don'ts caution below — this is exactly the kind of drift (a component styled in CSS under one name while every real usage is under another) that is invisible until you diff class names against the stylesheet, and it is worth checking for specifically before assuming a component is "done."

**Key Characteristics:**
- Navy ink on white/cool-gray surfaces; two accent colors (amber for Teardown, teal for Opening) swapped by `[data-product]`, never a parallel palette
- Barlow Semi Condensed for all display/heading/label/button type (civic-signage lineage); Public Sans for body; Overpass Mono for every filing-sourced value
- Flat by default: 1px hairline rule borders, one 4px radius, no drop shadows on cards or table rows
- No rotation, no physical props, no handwriting display face, no cream/kraft ground — the world this replaced
- Status is told by shape *and* color together (the stage-glyph system), never color alone

## Colors

A cool, precise navy-on-white register with two swappable product accents; the palette flips fully for dark mode except one deliberately stable navy pair reserved for the nav bar.

### Primary
- **Deep Navy Ink** (`#0e1a2b`, dark-mode `#e7edf5`): primary text, headings, primary button fill, focus-visible outline ink. This is the semantic `--ink` token — it inverts with theme.

### Secondary
- **Signal Amber** (`#b06a12`): Teardown Feed's product accent. Drives `--accent` when `[data-product="teardown"]`; used on the hero's big declared-value stat, `.pill.td`, and the Teardown tracking panel.
- **Courier Teal** (`#0e7c74`): Opening Soon's product accent. Same role set as Signal Amber, swapped by `[data-product="openings"]`, never a second stylesheet.

### Neutral
- **Surface White** (`#ffffff`): page and card background.
- **Surface Gray** (`#f2f4f7`) / **Surface Gray Deep** (`#e8ebef`): secondary section backgrounds, table headers, hover rows, rail/picker background.
- **Rule Hairline** (`#d7dde5`): every border, table rule, divider, status-rail/event-rail spine.
- **Ink Mid** (`#46566b`) / **Ink Faint** (`#5c6b7e`): secondary and tertiary text (`.muted`, mono labels, sub-lines).
- **Warn Ochre** (`#8a5210`) / **Bad Red** (`#8a2c22`): trial-countdown pill and `.notice.err` error states only.

### Named Rules
**The Stable Navy Rule.** `--navy`/`--on-navy` (`#0e1a2b`/`#ffffff`) are the *only* theme-stable tokens in the system — used exclusively for the nav bar and its mobile dropdown, which stay dark navy in both light and dark mode. Every other element that needs an "inverted" look (`.btn.primary`, `.value-tag`) uses the normal flipping `--ink`/`--surface` pair instead, specifically so it inverts correctly in dark mode (light-on-dark becomes dark-on-light). An earlier version of this build used the stable navy for buttons too, which made them nearly invisible against a dark-mode page; the fix was switching buttons and badges back to the flipping ink/surface pair while keeping only the nav bar stable. Don't reach for `--navy`/`--on-navy` for any new component — it is reserved for chrome that must never change with theme.

**The One Register, Two Accents Rule.** The palette is one navy-and-white system with exactly two swappable product accents (amber, teal), toggled by `[data-product]` on an ancestor. Extend the same `--accent`/`--accent-ink`/`--accent-wash` triad with a new accent color for a future feed rather than adding a parallel palette.

## Typography

**Display Font:** Barlow Semi Condensed (with system-ui fallback) — all headings, labels, and buttons. Chosen for its lineage in California DMV signage, a deliberate civic/precision reference.
**Body Font:** Public Sans (with system-ui, -apple-system, "Segoe UI" fallback) — U.S. civic-tech typeface, running copy.
**Label/Mono Font:** Overpass Mono (highway-signage lineage) — every filing-sourced value and every uppercase label.

**Character:** A condensed civic-signage grotesk for headlines and controls, a plain humanist sans for prose, and tabular monospace for anything a reader needs to scan as data — the pairing reads as a courier's manifest, not a typeset editorial page.

### Hierarchy
- **Display** (700, `clamp(34px, 4.6vw, 54px)`, line-height 1.05, Barlow Semi Condensed): page `h1` and the hero tracking card's headline.
- **Headline** (700, `clamp(22px, 2.6vw, 28px)`, line-height 1.05, Barlow Semi Condensed): section `h2`.
- **Title** (600, 18px, Barlow Semi Condensed): `h3`.
- **Body** (400, 15.5px, line-height 1.55, Public Sans): running copy, `.track-lede`, differentiator descriptions, event-rail entries.
- **Label** (600, 11–12.5px, letter-spacing 0–.06em, Overpass Mono or Public Sans): field labels (`.track-fields dt`, `.kv dt`), table headers, pills, status-point/event-point labels (`.status-point .lbl`/`.event-point .ev-title` are Public Sans; adjoining dates `.dt`/`.d` are mono).

### Named Rules
**The Data Is Mono Rule.** Any value pulled straight from a filing — address, filed date, declared cost, signal count, score — renders in Overpass Mono with tabular figures (`.num`, `.mono`, `.track-fields dd.mono`, `.event-point .d`). Prose about the value stays in Public Sans; the value itself is never set in the display or body face.

## Layout

Content sits in a single centered container, `.wrap` (max-width 1180px, 24px side padding); long-form prose narrows to `.narrow`/`.prose` (760px / 70ch). On the homepage and the two product marketing pages: a full-width tracking card (`.track`, 32px padding) holds the hero record, a 4-column stat row (`.stat-row`) beneath it, and a `.differentiators` grid (`repeat(auto-fit, minmax(220px,1fr))` — generalized this pass from a hardcoded 4-column grid so it reflows cleanly whether a page has four items or six) collapsing naturally at narrow widths, with a hard 1-column stack under 560px. The dashboards use a fixed two-column app shell (`.dash`: 250px filter rail + fluid main column), collapsing to a single stacked column under 860px. Detail pages (`detail_project.html`, `detail_opening.html`) use a fixed-width `.detail` container (max 980px) with a `.two` two-column split: `.kv` definition list plus the new vertical `.event-rail` on the left, minimap and nearby-records table on the right, collapsing to one column under 820px. Sections use consistent vertical rhythm (`section{padding:44px 0}`; the tracking-hero stage takes `52px 0 28px`).

Surfaces sit level at all times — no rotation on any element, in contrast to the world this replaced.

## Elevation & Depth

Flat by default. There is no card drop-shadow anywhere in the migrated surfaces — depth comes from a single 1px hairline border (`--rule`) and background-tint contrast (`--surface` vs `--surface-2`), never a shadow. The one shadow-shaped value in the system is a **ring**, not an elevation cue: `.stage-glyph.current` uses `box-shadow: 0 0 0 3px var(--accent-wash)` to halo the current status point (used identically in both the horizontal `.status-rail` and the vertical `.event-rail`), and focus-visible states use `box-shadow: 0 0 0 4px var(--focus-wash)` for accessible focus. Neither reads as "raised."

### Named Rules
**The No-Shadow-Card Rule.** Cards, table rows, and panels are bordered, not shadowed. A thin-border-plus-wide-soft-shadow combination (the prior Posted Notice world's signature, and a recognized "AI-generated UI" tell) does not belong in this system; if a component needs to stand out, use a hairline border and background-tint change instead.

## Shapes

Rectangular and level. The system's one radius scale runs from a sharp 0px (rare) to a shared default 4px (`--radius`), applied uniformly to buttons, pills, inputs, cards, the picker, and the map container — corners register as "barely eased," not softly rounded UI chrome. No rotation, no torn/cut/pinned silhouettes, no physical-prop geometry of any kind. Dividers are always solid 1px hairlines (`--rule`); there are no dashed "perforation" lines in this world (that device belonged to Posted Notice).

## Components

The navy-and-white system is restrained (flat buttons, square pills, hairline tables); its distinguishing element is the stage-glyph status system, which renders real pipeline data rather than decorating it — now expressed in both a horizontal (current-stage snapshot) and vertical (full history) form.

### Buttons
- **Shape:** 4px radius, 1.5px solid ink border.
- **Primary:** ink fill (`#0e1a2b`, flips to `#e7edf5` fill in dark mode via the `--ink`/`--surface` pair), `10px 16px` padding, 600-weight Public Sans label; hover darkens to `--ink-2`.
- **Ghost:** transparent fill, `--rule` border, `--ink-2` text.
- **Small (`.btn.sm`):** same treatment at `7px 11px`, used in nav, dashboard rail actions, and trial pill contexts.

### Chips (Pills)
- **Style:** mono uppercase label (11px, letter-spacing .04em), `5px 8px` padding, 3px radius, 1px `--rule` border by default.
- **State:** `.pill.acc` (context accent wash), `.pill.td` / `.pill.op` (fixed product wash regardless of ambient accent), `.pill.warn` (trial countdown).

### Cards / Containers — Tracking Card (signature component)
- **Corner Style:** 4px radius, 1px `--rule` border, no shadow.
- **Background:** `--surface`, always.
- **Internal Padding:** 32px.
- **Distinctive behavior:** holds a kicker (product pill + real source citation, never a decorative eyebrow), a headline, a status rail, a 4-up field definition list, and a CTA row. Used for the homepage hero record and both product-marketing pages' sample panels (`data-product="teardown"` / `data-product="openings"`).

### Status Rail / Stage Glyph (signature component)
`.status-rail`/`.status-point`/`.stage-glyph`: a horizontal timestamped checkpoint trail. This is a real, load-bearing accessibility and legibility device, not decoration — it renders the pipeline's actual current-stage snapshot (`applied → issued → construction → completed`, from `STAGE_LABELS`, or the three-signal set for Opening Soon). State is told by shape *and* color together, never color alone:
- **done**: a filled dark dot with an inset checkmark notch.
- **current**: a filled accent-colored dot with a soft accent-wash ring (`box-shadow: 0 0 0 3px var(--accent-wash)`).
- **pending**: a hollow outline dot (1.5px border, no fill).

On table rows a condensed variant (`.stage-cell`) pairs the same glyph with a text label. Collapses to a stacked layout with inline label+date under 560px.

### Event Rail (signature component)
`.event-rail`/`.event-point`: the vertical sibling of the Status Rail, added this pass on `detail_project.html` and `detail_opening.html`. Where the horizontal rail shows a record's *current-stage snapshot*, the Event Rail shows a record's *real historical event log*, one `.event-point` per past event, in filing order: actual permit revisions with real dates and statuses for `detail_project.html` ("Permit timeline" — `x.application_date`, `x.status`, `x.permit_num`, real data, not synthesized), and actual signal-by-signal filing history for `detail_opening.html` ("Paper trail" — one point per real AGCO/licence/permit signal). It reuses the identical `.stage-glyph` marker vocabulary from the horizontal rail (done / current / pending, same shape+color states) rotated 90°: a 1.5px `--rule` spine runs down the left edge (`.event-rail::before`), each `.event-point` positions its glyph absolutely at `left:0`, and content (date in mono, title, description) stacks to its right. No new marker shape was invented — the vertical rail borrows the horizontal rail's glyph states rather than adding a second status vocabulary.

### Picker (component)
`.picker`: added this pass on `account.html`, replacing an inline-styled reuse of the dashboard `.rail` sidebar class in a non-sidebar context. It is the standalone, bordered sibling of `.rail` — same header/label/checkbox-group/`.hoods` scrollable-list treatment (`--surface-2` background, mono uppercase `h4` group headers, 1px `--rule` border, 4px radius), but as a self-contained boxed facet picker inside a form rather than a fixed-width page-edge column. Use `.rail` when the facet list is a persistent page-edge filter column (dashboards); use `.picker` when the same facet-picking UI needs to sit inline inside a form or card (e.g. the account page's neighbourhood digest picker).

### Value Tag
`.value-tag`: an inverted mono chip (ink fill, surface text) marking a subscriber-only field shown in a public sample (builder's name, phone, contact) — uses the flipping `--ink`/`--surface` pair, not the stable navy, so it inverts correctly in dark mode.

### Tables / Manifest
`.tbl`/`table`: 1px hairline border container, no radius-on-corners fuss beyond the container, sticky mono uppercase headers, hover row tint (`--surface-2`), right-aligned numeric columns (`.r`). Reads as a manifest of tracked filings, not a decorated card list.

### Differentiators
`.differentiators`/`.differentiator`: a plain grid list, each item marked only by a 2px solid top rule (`border-top:2px solid var(--ink)`) — no card, no side-tab, no icon. The grid is `repeat(auto-fit, minmax(220px,1fr))` (generalized this pass from a hardcoded 4-column grid so it works for both a 4-item and a 6-item list without a bespoke column count per page); it now also backs `product_teardown.html`'s "Who uses it, and how" and `product_openings.html`'s "Three filings, one address" grids, converted from ad-hoc layouts.

### Notice Banner
`.notice`/`.notice.ok`/`.notice.err`: a flat bordered banner (`--surface-2` background, 1px `--rule` border, 4px radius) for form-result and session messages (checkout success, saved preferences, sign-in link sent, login errors, billing-off notice). `.notice.ok` shifts the border to `--op` (teal); `.notice.err` shifts the border to `--bad` and now also washes the background `--bad-wash` and sets text to `--bad` (this pass added the background wash — previously `.notice.err` only changed the border). Used on `account.html`, `login.html`, and `pricing.html`.

### Navigation
Theme-stable navy bar (`--navy`, `#0e1a2b`, does not invert with dark mode) with a 1px `--rule` bottom border; nav items are 600-weight Public Sans labels in `--nav-ink-2`, going full `--on-navy` white on hover/active. Below 820px it collapses to a hamburger toggle that expands a full-width navy dropdown panel. Nav and footer are shared chrome — identical across every page in the site, migrated or not.

### Dashboard Rail / Filters
`.rail`: fixed 250px filter column, `--surface-2` background, mono uppercase group headers (`h4`), flat inputs/selects with 1px `--rule` borders and 4px radius, checkbox groups for multi-select facets (kinds, stages, categories, neighbourhoods). See Picker above for the non-sidebar sibling.

### Paywall Banner
`.paywall`: a flat inline notice bar (`--surface-2` background, 1px `--rule` border, 3px accent-ink left border) above the results table or detail content for unauthenticated/trial views — plain and high-contrast, not an accent-washed card. Now also used on `detail_project.html` and `detail_opening.html`.

## Do's and Don'ts

### Do:
- **Do** render the stage/status glyph with shape and color together (filled+checkmark for done, filled ring for current, hollow outline for pending) — never a color-only dot or pill for stage, in either the horizontal Status Rail or the vertical Event Rail.
- **Do** render every filing-sourced value (address, date, declared cost, signal count, score) in Overpass Mono with tabular figures.
- **Do** keep the two product accents (amber Teardown, teal Opening) switched by `[data-product]` on an ancestor, not by duplicating the palette per product.
- **Do** use the flipping `--ink`/`--surface` pair for any element that needs an inverted look (buttons, badges) so it inverts correctly in dark mode; reserve the stable `--navy`/`--on-navy` pair for the nav bar only.
- **Do** use a 1px hairline border plus background-tint contrast for anything that needs to stand out from its surface — never a card drop-shadow.
- **Do** use `repeat(auto-fit, minmax(220px,1fr))` (or equivalent) for a card/item grid whose item count varies by page (`.differentiators`) rather than a hardcoded column count — it was generalized this pass specifically so the same class serves a 4-item and a 6-item list.
- **Do** double-check that a component's CSS class name and its template callers actually match before shipping — the `.notice-box`/`.notice` mismatch left three pages' success/error banners completely unstyled for an unknown period; a class rename in one place without grepping every caller is how this happens.

### Don't:
- **Don't** invent a tracking-code or reference-number field for a record. The direction contract for this world specified one; the build deliberately omitted it because the product has no real tracking-code data to show, and PRODUCT.md commits to being a faithful pass-through of primary filings, not an embellished one. Cite the real source (e.g. "Toronto Building · permit record") instead.
- **Don't** apply rotation, tape/staple/torn-edge props, or a handwriting display face to any component in this world — that was the prior "Posted Notice" system and has been fully removed, not toned down.
- **Don't** add a thin-border-plus-wide-soft-shadow combination to a card or panel; it's a recognized "AI-generated UI" tell and this system is flat-by-hairline instead.
- **Don't** use `--navy`/`--on-navy` for anything other than the nav bar — an earlier build used it for buttons and they went nearly invisible in dark mode; that bug is why the rule exists.
- **Don't** invent a second status-marker vocabulary for a new record-history surface. The Event Rail deliberately reused the Status Rail's exact `.stage-glyph` states rather than introducing a new dot/icon system for "history" vs. "current stage" — one glyph vocabulary, two orientations.
- **Don't** reintroduce `.hero`/`.eyebrow`/`.timeline` — they were dead CSS left over from the prior "Posted Notice" layout (no template used them any longer, confirmed by a direct grep across all templates) and have been removed from `app.css` in this pass. A marketing "eyebrow" kicker above a headline is banned by the craft floor regardless; a timeline needs the vertical `.event-rail` component instead.
