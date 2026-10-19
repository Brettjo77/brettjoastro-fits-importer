# Observatory round 3 · lens: the charts — what 16 Oct promised, what was built, what to draw next

Reviewer: `charts` (data-visualisation). Read: A / B / C mockups and notes, the five R reviews, SPEC.md, the
built page (`astro-observatory.html` 1.7.4, rendered here with the real-size stress dataset of 87 targets /
147 datasets / 505 sessions), the `built/` screenshots and Brett's five screenshots of 19 Oct. Every number in
the mockups comes from the stress dataset; every colour from `D.scopes[].colour`. The dataviz rules (form,
colour job, mark specs, legend rule, hover) were applied to each proposal; where a rule says "no", I say so.

Files in this folder (all under `/tmp/claude-0/-home-user/c23ee14e-85ed-5f5b-94f9-0fb713d6fb24/scratchpad/ux3/charts/`):

| File | What |
|---|---|
| `mock-1-what-each-scope-shot.png` | Proposal 1 at 90 and 30 nights, light theme |
| `mock-1-dark.png` | the same at 90 nights, dark theme |
| `mock-2-project-card-lanes-and-key.png` | Proposal 2: the project card as built (top row) and as proposed (bottom row) |
| `mock-3-twelve-months.png` | Proposal 3: the last twelve months by scope |
| `mock-light.png`, `mock-dark.png` | all three on one page, both themes |
| `mock-charts.html`, `make_mock.py` | the mockup page and the script that draws it from `stress.json` |
| `shot-built-cards-light.png` | the built project cards alone (stress data), for comparison |
| `shot-overview-light.png`, `shot-overview-dark.png`, `shot-targets.png`, `shot-equipment.png`, `shot-coverage.png` | the built page with the stress data, as I looked at it |
| `shoot2.sh` | the shoot script with a fixed injector (the original's `sed` breaks on a `#` in the JS) |

## 1. The short answer to "donut graphs etc. were not implemented"

The donuts **were** built: every project card carries a 56 px ring of hours by scope (`ring()` at
`astro-observatory.html:1517`, called from `projCard()` at :1532; visible in Brett's `9.webp`). What was
**not** built is the part that made A's ring mean something: A paired the ring with one timeline lane per
scope on the card, and the colour review (R/colour finding 2) said "rings get a key" because the six scope
colours cannot be told apart by colour alone. The built ring has no key (hours only on hover) and the
per-scope lanes collapsed into one mixed lane with grey dots where two scopes shared a night. So the ring
reads as decoration, which is probably why it does not register as "the donut graphs". Fixing that is
Proposal 2 below.

The genuinely missing pictures are the ones about **history per scope**, Brett's priority 1: B's "where each
scope is" row (latest object + growth), A's "last twelve months by scope" columns and C's "season strip",
and nothing anywhere that says *what* each scope shot in the range, only *when* (the dots) and the latest
object. Proposal 1 fills that gap and is the one I would build first.

## 2. Every visual element the 16 Oct round proposed, and whether it exists

**Built** = on the page and faithful · **Partly** = there but weaker than drawn · **Moved** = exists on
another view · **Not built**. "Earns its place" is my judgement against the dataviz rules and Brett's four
points; the ones worth building now are in §3.

| # | Element | Promised by | Built page | Where / how faithfully | Earns its place now? |
|---|---|---|---|---|---|
| 1 | Night-sky header: hero "N hours", labelled companions (frames, targets, nights, scopes) | A, C, SPEC §1.1 | **Built** | `renderHeader()` :941; `11.webp` | Keep (the header reviewers will shorten it) |
| 2 | Share bar by scope, every slice labelled, numbered ticks for thin ones + key | A, C, R/colour 2, R/type | **Built** | `renderShare()` :953; labels in-segment when they fit, numbered ticks and a key row otherwise | Keep; the "1 Seestar S50 Pro" bug is known |
| 3 | Legend strip (scope dots, next-step pills, marks) | C, SPEC §1.1 | **Built** | `legendInto()` :981 | Keep, though it is a row of chrome before content |
| 4 | Freshness pill + "N files on a camera not yet imported" | A, B, C, truth 2 | **Built** | `renderFresh()` :987 | Keep |
| 5 | Last night: one row per scope, hours, frames, filter, "3 objects" | A, C, truth 5 | **Built** | `renderLastNight()` :1362 | Keep |
| 6 | Needs your attention: jobs with counts and a verb | C, truth 4 | **Built** | `renderAttention()` :1415 | Keep |
| 7 | Six-lane strip, a dot per night sized by hours, hollow when unknown, quiet band, ranges, week bins | A, B, SPEC §1.4 | **Built** | `renderStrips()` :1452, `buildStrip()` :1120; `7.webp`, `8.webp` | Keep; this is the anchor |
| 8 | Strip text line per lane: "hours over N nights · latest object" | A | **Built** | `stripText()` :1443 | Keep, but it is text where a bar would say it faster → Proposal 1 |
| 9 | "Where each scope is": latest object + a sparkline of hours growing since first night + all-time totals | B | **Not built** | — | **No.** A cumulative sparkline only ever goes up; the strip already shows when a scope was out. Decoration by the "trend over time" test: "the FRA400 has more hours than it did" is not a question Brett asks. The latest-object half is already in #8. |
| 10 | What each scope **shot** in the range: the objects per scope with their hours | nobody drew it; A's strip text gives only the latest object | **Not built** | — | **Yes, first.** The direct answer to "what was recently captured and on what scope". Proposal 1. |
| 11 | What to do next: three columns, scope stripe, labelled hours bar against the biggest dataset, calibration mark, ready date | A, C, SPEC §1.5 | **Built** | `renderQueue()` :1486; the thin track bar under each card's hours | Keep |
| 12 | Quick looks listed under, never in | truth 1 | **Built** | `renderQueue()` | Keep |
| 13 | Project card: ring of hours by scope ≥ 56 px, no centre text | A, R/type 13, SPEC §1.6 | **Built** | `ring()` :1517: 56 px, 8 px stroke, 2.5 px gaps, hatched arc for unknown hours | Keep the ring |
| 14 | Project card: the ring's **key** (scope name + hours beside the ring) | R/colour 2 ("rings get a key"); B's labelled chips under the hours bar | **Not built** | hours only in the tooltip | **Yes.** Proposal 2a. Without it the ring fails the colour review's own rule. |
| 15 | Project card: **one timeline lane per scope** on the card | A ("a timeline with one lane per scope"); SPEC §1.6 says only "a mini timeline" | **Partly** | `projCard()` :1532 draws ONE lane for all scopes; a night on two scopes becomes a grey dot (`var(--ink2)`), so the card cannot say which scope was out; one lane per scope only in the expanded panel | **Yes.** Proposal 2b. The card is what Brett screenshotted as most important; the grey dot throws the scope away. |
| 16 | Project card: one pill per scope with the scope dot | A, C, truth 25 | **Built** | `pill(stKey(p),{cam})` | Keep |
| 17 | Expanded project panel: a lane per scope, quiet band, three marks, next step, a table of nights | C, SPEC §1.6, §3 | **Built** | `10.webp`, `built/final-1440-project-panel.png` | Keep as it is |
| 18 | Night panel: frames, hours, exposure, filter, gain, calibration filed that night, archive sizes, Open folder | SPEC §1b, §3 | **Built** | `built/final-1440-night-panel.png` | Keep |
| 19 | Calibration mark on every ZWO card / lane / night row; "in camera" for Seestars | C §6, SPEC §3 | **Built** | queue cards ("Darks and flats filed on 8 of 9 nights"), panel ("Flats missing on 3 of 4 nights"), night rows (✓ 30 darks / ⚠ none filed) | Keep |
| 20 | "The last twelve months, by scope": 12 stacked monthly columns, total labelled on each, season tints, on the Overview | A | **Moved, weaker** | Equipment → "The rhythm of the hobby" (:1893): **every month since Nov 2023** (36 columns, no total on any column, no nights count, legend only); the Overview has nothing monthly | **Yes, third.** Proposal 3: twelve months, labelled, on the Overview. Season tints: no (colour would mean a fourth thing). |
| 21 | Season strip: nights per month coloured by scope, the count on each column | C | **Not built** | — | Folded into Proposal 3 as the "N nights" line under each month; two charts of the same months is one too many. |
| 22 | Whole-archive bars: one labelled bar per scope (hours, frames, nights, since) | A | **Partly** | the header share key carries hours · % · nights; Equipment cards carry a filter-mix bar, not hours | No separate chart: the share bar + key already says it. |
| 23 | "Where the hours went": the top ten projects stacked by scope, labelled, hatched for unknown, table toggle | A, C, SPEC §1.7 | **Built** | `renderWhereHours()` :1586 (top 12) | Keep |
| 24 | "Gone quiet": a dot on the last night and a fading trail toward today on a 120-night track | B | **Not built** | queue cards say "nothing new for N nights" in words | **No.** The quiet band on every lane already draws "how quiet"; a second drawing of the same fact is decoration. |
| 25 | Targets list: a ring per row + a 90-night timeline per row | A | **Not built** (deliberately) | `RENDER.targets` draws scope dots + a pill per scope + numbers; SPEC §1.7 reduced Targets to "the detailed list"; R/type 13 called 44 px rings decoration | No ring. A per-row lane is tempting, but the list is 87 rows; the strip and the cards carry recency. Leave. |
| 26 | Coverage: filled / hollow / dash / crossed cells | C | **Built** (three of four) | `shot-coverage.png`; "not planned" needs `targets[].plannedScopes[]`, which the engine does not emit yet | Keep; the fourth state waits on the engine field |
| 27 | Nights heatmap with a numeric legend and a per-scope toggle | C | **Built** | `built/final-1440-nights.png`: "≤ 0.5 h · ≤ 1.5 h · ≤ 3.0 h · ≤ 5.0 h · more", scope chips, colour-by-frames toggle | Keep |
| 28 | Sky map: dot area = hours, colour = scope with most hours, faded outline = done, labels on the biggest, size key 1 / 10 / 50 h | C | **Built** | `drawSky()` :1837 | Keep |
| 29 | Footprints note above the map | C | **Built** | `RENDER.footprints` | Keep |
| 30 | Equipment: numbers with words, cards in scope order, exposure histogram | C | **Built** | `shot-equipment.png` | Keep |
| 31 | Data checks: the subtraction that explains every row | C, truth | **Built** | `built/final-1440-health.png` | Keep |
| 32 | Hover: one anchored tooltip on marks, value first, scope-colour key, same on keyboard, pinned on tap, 24 px hit circle | R/motion 3, 8, 11 | **Built** | `hoverable()`, `ttRow()` | Keep; Proposals 1–3 reuse it unchanged |
| 33 | Motion: one-time load-in, dots sliding on range change, panels sliding open, hero count-up only on a real change | R/motion | **Built** | `--dur-*` tokens, `.reveal`, `updateStrip()` | Keep |
| 34 | Both themes, the header always night-sky | R/colour 3 | **Built** | `:root[data-theme]` | Keep |

Of 34 promised elements: 25 built, 4 partly / moved, 5 not built. Of the five missing, two (#9 sparkline,
#24 fading trail) would be decoration under the dataviz rules and should stay out; three (#10, #14+#15,
#20+#21) earn their place and are the proposals below.

A note on the colours, computed not eyeballed (`validate_palette.js`, light surface `#fffdf9`, the stress
dataset's six): lightness band PASS; chroma floor FAIL for the S50 grey `#8a8a8a`; CVD separation PASS
(worst adjacent 8.4); normal-vision floor FAIL (grey ↔ blue 13.5, below 15); contrast WARN for amber
`#eda100` (2.13:1) and green `#4cbf8a` (2.26:1). The page cannot change the contract's colours, so every
proposal keeps the page's rule: a scope colour never appears without the scope's name in the same row, and
every value is also in text (the "relief" the validator demands for the contrast warning). Brett's real
contract differs from the stress dataset (S30 blue where the stress set has the Starfront purple; S50
near-black, S50 Pro slate): the same rule covers it, and the in-segment label colour in Proposal 1 is chosen
per fill by contrast (`ink_on()` in `make_mock.py`), never fixed.

## 3. The three charts that would make the biggest difference, ranked

### Proposal 1 · "What each scope shot" — hours by scope in the range, split by object

**The question it answers:** "In the last 30 / 90 nights, how much did each scope capture, and of what?"
Today the strip says *when* (dots) and the text beside it says the total and the latest object. Nothing says
"the FRA400's 163 hours were mostly the Swan, Bode's and the Eagle". This is Brett's point 1 in one picture.

**Mockup:** `mock-1-what-each-scope-shot.png` (90 and 30 nights), `mock-1-dark.png`.

**Form (dataviz):** compare magnitude across six scopes → horizontal bars; part-to-whole within a scope →
stacked pieces, at most six named + "N more objects" (the series cap). One series per row (the scope), so
the row's name is its legend: **no legend box**. The object pieces are all in the scope's colour, separated by
the 2 px surface gap, so colour still means scope and nowhere else. Colouring objects (sequential or
categorical) was rejected: a seventh colour meaning on a page that already has three.

**Where:** inside the "What each scope captured" card, under the dots and the axis, sharing the card's range
control (one filter row scopes everything below it). Same six lanes, same order, same names, so the two
drawings read as one. If the card grows too tall for the layout reviewer, it is the second face of the card
behind a "when · what" toggle, defaulting to "when".

**Data (all already in `observatory/1`; page-only):** `D.sessions[]` (`target`, `camera`, `night`, `hours`,
`frames`); `D.scopes[]` (`camera`, `colour`, `order`, `last`); `D.quietPeriodDays`; `D.asOfNight`. Hours
unknown: a session with `hours == 0 && frames > 0` (the page's `hoursUnknown()`). Object display name:
`commonName()`. Nothing new from the engine.

**Exact spec:**
- Row 74 px tall at desk (bar 20 px + a 16 px list line, a second list line 15 px below it); name column
  200 px (scope dot 10 px with the 2 px surface ring, name 13 px/600 ink; muted and 400 when the scope has
  nothing in the range); bar area = card width − 200 − 230; the 230 px right column carries the row's total.
- Bar 20 px thick (≤ 24), square at the left baseline, 4 px rounded data-end on the right; the row's track a
  1 px `--track` hairline across the full width; the biggest scope in the range sets the scale.
- Pieces: objects biggest first, up to six, then one piece "N more objects"; 2 px gap of `--card` between
  pieces; a piece carries its name + hours inside (12 px/600, ink or white by contrast with the fill) when
  that fits with 8 px padding each side, otherwise its number (1–7) centred; nothing inside under 14 px.
- Under the bar, one or two lines of 12 px text in `--ink2`: "**1** Swan Nebula **18.2 h** · **2** Bode's and
  Cigar widefield **16.5 h** · …" (number 700 ink, hours 600 ink, tabular). Never a third line: "and N more in
  the table". This is C's share-bar pattern (wide labelled inside, thin numbered, the list repeats all) and it
  is what makes the chart usable with Brett's long names.
- At the tip of the bar (ink 12 px tabular): "162.9 h · 42 nights · 29 objects"; then muted "+ 860 frames,
  hours unknown" when any session in the range has no exposure, with a 14 px hatched stub (the page's
  `hatchFor()`) at the end of the bar. Hatched never takes width in proportion: unknown is not a size.
- A scope with nothing in the range: no bar; the muted line the strip already uses ("nothing in 90 nights ·
  last out 30 Aug 2025, 412 nights ago").
- Hover / focus / tap (the page's `hoverable()`): the piece lifts (ink outline, as the heatmap cells do); one
  anchored tooltip: object name (13 px/700), then rows value-first with the scope-colour line key on the hours
  row: hours · nights · frames · last night "11 Oct · 5 nights ago" (drawn in the mockup). Click opens the
  project (`openProject`). Pieces are `tabindex=0` like the "Where the hours went" bars; the hit area is the
  whole 20 px bar plus its gaps. A range change re-draws pieces in place (320 ms width tween, keyed by
  scope|object), the same motion token as the dots.
- "view as table" in the card head (every chart has a table twin): Scope · Object · Hours · Nights · Frames ·
  Last night, sorted as the bars.
- Phone (< 700): name above the bar, bar full width, list under it, the total moves to the end of the name
  line. The numbered list is what keeps it readable at 358 px.
- Effort **M**, page-only.

### Proposal 2 · The project card: the ring gets its key, and one lane per scope

**The question it answers:** "On this project, which scope did what, and when?" — the card Brett
screenshotted (`9.webp`) as most important, which today answers "how much in total" (ring + numbers) and
"what next" (pills) but not "which scope, when": the single mixed lane paints a night on two scopes grey, and
the ring's shares are unreadable without the names and numbers.

**Mockup:** `mock-2-project-card-lanes-and-key.png` — as built on the top row (`shot-built-cards-light.png`
is the real thing), as proposed on the bottom row.

**Form (dataviz):** the ring stays (part-to-whole at a glance, ≤ 4 segments, no centre text, 56 px: all as
the type review asked). "A donut for comparing close values" is the anti-pattern, so the numbers go beside
it, not inside it. **2a, the key:** one line under the pills, in lane order: "● 107PHQ **30.0 h** · ● FRA400
**60.0 h** · ● S30 Pro **8.5 h** · ● S50 Pro **3.2 h**" (12 px, dot 9 px with the surface ring, scope short
name in `--ink2`, hours 600 ink, tabular; "hours unknown" where `hoursUnknown`). That is the key the colour
review required and the labelled bar B drew, as two lines of text instead of a second chart. **2b, the
lanes:** the mini timeline becomes one 18 px lane per scope (2–4 lanes, 36–72 px instead of 30), each with a
52 px label (scope short name, 11 px muted), its own `--track` hairline, dots in the scope's own colour sized
by hours (r 2.5–6, hollow when unknown), the quiet band and today line spanning all lanes, the "‹N" count of
earlier nights at the left of each lane as the page does now, the last 120 nights. No grey dots: every dot
has a scope. Hover and click as the lanes in the panel (`openNight`). The panel's "one lane per scope" and
the card's lanes then say the same thing at two sizes: SPEC §1b's "the three levels share one vocabulary".

**Data (page-only):** `targets[].programmes[]` (`camera`, `hours`, `lights`, `nights`, `status`) for the key;
`D.sessions[]` filtered by `target` for the lanes. Nothing new from the engine.

**Exact spec:** key line margin-top 8 px, wraps freely (each item `white-space:nowrap`); lanes block
margin-top 12 px; lane height 18 px, label column 52 px, plot to the card's inner width minus 8 px, drawn at
its real pixel width and redrawn on resize like the strip (no `preserveAspectRatio="none"`); quiet band
`--quiet-band`, 3 px radius, 14/120 of the plot; today line 1 px ink. Card order and the 3 / 2 / 1-up grid
unchanged; a four-scope card grows by ~60 px, which the grid absorbs because cards already differ in height
(`shot-built-cards-light.png`). Phone: the same; the lanes are one SVG. Effort **S–M**, page-only.

### Proposal 3 · "The last twelve months, by scope" on the Overview

**The question it answers:** "How has the season gone, scope by scope?" — the step between the 90-night strip
and the all-time share bar, which the page skips. A promised it on the Overview with a labelled total on every
column; the built page has a 36-column unlabelled version on Equipment that nobody scrolls to.

**Mockup:** `mock-3-twelve-months.png`.

**Form (dataviz):** change over time of a part-to-whole → stacked columns, one hue per scope (categorical,
fixed order), 2 px surface gaps between segments, 4 px rounded cap on the top segment only, columns 24 px,
hairline solid grid (`--grid`), one axis in hours (50 h steps; 25 h when the biggest month is under 120 h).
Six series → the legend row is mandatory (present) and no direct labels except the one that matters: the
month's **total on each cap** (12 px/600, tabular). Nights per month is text under the month label ("22
nights"), never a second axis. A's season tints are dropped: a fourth colour meaning. No animation beyond the
one-time load-in.

**Where:** the Overview, after "Projects that moved lately" and before "Where the hours went" (A's order), or
as the "a year" face of the strip card if the layout reviewer wants fewer cards. Equipment's "rhythm" chart
keeps the full history and gains the same column totals.

**Data (page-only):** `D.sessions[]` (`night`, `camera`, `hours`) grouped by `night.slice(0,7)`; nights per
month as a set of `night`. The current month is labelled "Oct · to 16" from `D.asOfNight`. Effort **S**.

**Exact spec:** plot 220 px + 28 px above for the caps + 44 px below for two label lines; left pad 48 px for
"150 h" ticks (11 px muted, tabular); hover on a segment shows the month, every scope's hours that month
(value first, colour line keys) and the total; "view as table" twin: Month · a column per scope · Total ·
Nights. Phone: the same twelve columns at 16 px, caps every other month, legend wraps.

## 4. Smaller chart findings on the built page

1. **The strip's right column is text doing a bar's job** (`7.webp`: "129.5 h over 35 nights"). Proposal 1
   replaces the need; if it is deferred, a 6 px hours bar under each text line, scaled to the biggest scope in
   the range, is an S change in `stripText()` :1443.
2. **Where the hours went** clips names with an ellipsis ("Great Globular (M 13) and NGC 62…",
   `shot-overview-light.png`): the rule is "never clip a label"; use `commonName()` with the codes in the
   tooltip, as the cards do. S, page-only, `renderWhereHours()` :1592.
3. **Equipment's "rhythm" chart** has 36 columns with no total and its first two year labels overlap ("Nov 2023"
   and "2024" collide in `shot-equipment.png`). Proposal 3's labelling fixes both; a year label should drop
   when the previous label is within 40 px.
4. **Nights heatmap**: the sequential blue ramp (`--heat1..5`) is one hue light→dark with a numeric legend, as
   the rules want. Keep.
5. **Sky map** colours a dot by "the scope with most hours", a scope colour on a derived fact; the legend says
   so and done is a faded outline. Acceptable; no change.

## 5. Keep as it is (do not lose these)

- The six-lane strip with its ranges, week bins, hollow dots and quiet band, and its keyboard walk.
- Colour means scope only; status is a glyph and a word; warnings on a warm wash; green never means "ok".
- Every number wears its word; unknown is never 0; the hatched mark for unknown hours.
- The project panel's one-lane-per-scope with the three marks and the night table, and the night panel.
- The calibration marks on ZWO cards and lanes, "in camera" for Seestars.
- "Where the hours went" with its table twin; the Nights heatmap's numeric legend; Coverage's three cell states.
- One anchored tooltip, value first, the same on keyboard and touch; the one-time load-in; dots that slide.
- The 56 px rings with no centre text (add the key; do not make them bigger or put numbers inside).

## 6. What the engine would need (none of it blocks the three proposals)

- Nothing for Proposals 1–3: sessions, programmes and scopes already carry every field used.
- For the Coverage "not planned on this scope" cell (#26): `targets[].plannedScopes[]`, still pending.
- The stress dataset predates `scopes[].order`, so the mockups use the page's fallback order (alphabetical by
  camera). On Brett's real record the lanes follow `scopes[].order`, the same as the strip.
