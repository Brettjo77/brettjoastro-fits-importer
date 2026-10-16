# Observatory review B: the story of the season

For Brett. Direction: **time is the organising idea.** The page should read like a diary of the season, not a spreadsheet of it.

## What makes the current page hard to read (worst first)

1. **The latest captures are a wall of eighteen text cards.** "What each scope captured last" is three sessions per scope as small grey boxes. To answer "what did I shoot lately, on what?" you read 18 cards and rebuild the timeline in your head. The one view that does it visually, the per-scope timeline (dots per session on a calendar), is hidden behind a "timeline ›" link and shows one scope at a time.
2. **No sense of time anywhere on the Overview.** Every list is sorted by size or by status, so a session from July looks the same as one from last night. "Last on 25 Jul 2026" for the S50 is a date you have to subtract from today yourself.
3. **Colour means nothing in particular.** Scope colours appear only as 8-pixel dots. The big "Integration by scope" bar is the one colourful thing and it has no labels on the thin S50 / S50 Pro segments. The rest of the page is grey text on white, so nothing is findable at a glance.
4. **The scope colours on the page aren't the contract's colours.** The template hard-codes its own palette (107PHQ green, S50 black) and only uses `D.scopes[].colour` for scopes it doesn't recognise. So the same scope can be green here and blue in the dataset the importer sends. One palette, from the data, everywhere.
5. **Decisions come after history.** Totals, the processing queue and the "things to know" sit below the 18 session cards. The queue is the thing you came for.
6. **Unknown looks like zero.** Milky Way Core shows 0.0 h beside 2,150 frames. On the current timeline an unknown-hours session is drawn as an empty ring, which reads as "a tiny session".
7. **The "to process" queue is padded with test snaps.** Dumbbell 0.9 h, Fireworks 0.8 h, and on the real archive things with 1 or 4 frames, sit between real projects. The queue looks longer and less honest than it is.
8. **Numbers without their nouns.** "20.4  9,494  32" on an equipment card, "24" on a tile. Every figure needs its unit beside it (ChatGPT's point 1; I agree).
9. **Scope order changes from panel to panel.** Overview goes S30 Pro, 107PHQ, S50; Equipment goes S30 Pro, 107PHQ, S50, FRA400; the Coverage columns differ again. The eye never learns where a scope lives.
10. **On the per-scope timeline (the bit Brett likes): at "a year" the dots pile on top of each other, long names get cut ("Silver Silver Galaxy (N…"), and the top "Every night" row is bars while the object rows are dots.** Also the warning strip says "2 things to know" when 491 rows are actually not counted, and the header doesn't say whether frames are still sitting on a camera.

## The proposal

**Make the timeline the page.** The first thing under the header is one strip, "The story of the season": a lane per scope, in its own colour, with a dot per night the scope was out, bigger for more hours, hatched when the exposure wasn't recorded. Today is on the right and the last 14 nights are a tinted band, so "still capturing" versus "gone quiet" is simply left-or-right of the band. A range control (30 nights · this season · 90 · a year · everything) sets how far back it looks; past 120 nights each dot becomes a week, so the dots never pile up. Hover or tap any dot for the objects that night. Above it, a big friendly line says what happened last night (object, scope, hours, frames) and the four totals, each with its unit. The header carries a freshness line: when the page was worked out, which records it read, and a slot for "N files on the camera not yet imported".

Then the page answers Brett's three questions in order. **Where each scope is**: one row per scope with its latest object, a small line of how its hours have grown since its first night, and its all-time totals. **Growing now**: a card for each project touched in the last 14 nights, newest first, with the project's whole life on one line (dots coloured by scope), the hours split by scope as a bar with every scope labelled below it (thin segments included), and a status pill saying when it becomes ready to process. **Gone quiet: ready to process**: biggest first, where the "how quiet" is drawn, not written: a dot on the last night out and a fading trail toward today on a 120-night track. Below that, the five "half done" projects with their saved masters, and the done count. Test snaps under 1 h are kept out of the queue and listed in one line as samples, so the queue is honest.

**Colour means scope; a glyph plus a colour means status.** The six scope colours come from the dataset and are used boldly: tinted lanes, glowing dots, coloured card tops, coloured trails. Status has its own four colours (cyan capturing, pink ready, amber in progress, green done) and always a shape and a word beside it, never colour alone. Everything is on a deep night-sky background so the colours carry; every number has its noun; unknown integration is hatched, never 0.

## What each existing view becomes

- **Overview** → the page above: last night · the season strip · where each scope is · growing now · gone quiet · half done.
- **Nights** (the calendar heatmap) → folded into the season strip. "Everything" at week-per-dot shows the same rhythm, in scope colour instead of blue, with the objects on hover. The heatmap's summary line (busiest month, longest run, longest dry spell) becomes the strip's caption at the "everything" range.
- **Equipment** → "Where each scope is" plus the strip. The six cards' numbers are the row's all-time column; the monthly stacked bar is the strip at "everything"; filters and exposure lengths move to the scope's own drill-down (tap a scope name).
- **Per-scope timeline** (the card Brett likes) → it is the anchor. All scopes at once, dots everywhere (no bars-versus-dots mismatch), weekly dots at long ranges, and names in a fixed-width HTML column that wraps instead of truncating and stays put when the strip scrolls sideways on the phone. The one-scope, one-row-per-object view stays as the **Timeline** tab, with the same fixes.
- **Targets / Pipeline / Coverage** → one **Projects** tab: the list with the status pills, a scope filter, and the 50 datasets honestly ("4 scopes: 2 in progress · 1 ready · 1 capturing"). Tapping a project opens the drill-down sketched at the bottom of the mock (Andromeda): its own timeline with a lane per scope, hours by scope, and one row per scope with status, numbers, dates, filters, what the importer found, and calibration. The Askar "master may belong to the other Askar" warning sits at the top of that page in its own box, because it changes two statuses.
- **Sky / Footprints** → unchanged, kept as **Sky**.
- **Data health** → unchanged, but the header's "N things to check" now gives the full count (491 rows not counted: 184 unknown names, 2 no scope, 305 duplicate copies, with the duplicates marked as correct).

## The addendum's points, and which this direction answers

- Test snaps inflating the queue → **yes**: a 1 h cutoff (a setting) and a "Sample" state shown as one line under the queue.
- Missing type / constellation → **yes**: the card shows what exists and says "type not recorded" when nothing does; inconsistent type labels need the engine, not the page.
- Thin bars without labels → **yes**: every hours-by-scope bar has a labelled chip per scope beneath it, and the lanes carry their own hours.
- One fixed scope order → **yes**: most hours first, used in the strip, the rows, the cards, the bars and the drill-down, and said on the page.
- Freshness line with "not yet imported" → **yes**: designed in the header; the sample dataset doesn't carry the number (see below).
- 491 not 184 → **yes**, counted from the health notes. Unknown vs zero → **yes**, hatched. Mixed statuses → **yes**, "4 scopes, honestly" with a pill per status. Decisions before history → **yes**, the queue is above the cards and there are no session cards. Intent vs guess for "still capturing" → **designed** (the drill-down says "kept open by you" or "frames arrived inside the quiet period") but the dataset has no per-scope flag yet.

## Data the page needs that the dataset doesn't carry

- `pendingOnCamera { files, targets, failedEject }`: files still on the cameras, for the header freshness line.
- A per-programme `keptOpen: true/false` (from capture-state.json) so "Still capturing" can say whether it is Brett's intent or the quiet-period rule.
- A per-programme `sample: true` or a `minIntegrationHours` setting, so the engine and the page agree on what is a test snap (the mock uses 1 h).
- Optional: `scopes[].short` for a short display name, so the page doesn't have to strip "Seestar" / "Askar" itself.

## Files

- `/tmp/claude-0/-home-user/c23ee14e-85ed-5f5b-94f9-0fb713d6fb24/scratchpad/ux2/B/review.md` (this)
- `/tmp/claude-0/-home-user/c23ee14e-85ed-5f5b-94f9-0fb713d6fb24/scratchpad/ux2/B/mock-B.html` (source, with `__DATASET__`)
- `/tmp/claude-0/-home-user/c23ee14e-85ed-5f5b-94f9-0fb713d6fb24/scratchpad/ux2/B/mock-B.rendered.html` (filled with dataset.json; open this)
- `/tmp/claude-0/-home-user/c23ee14e-85ed-5f5b-94f9-0fb713d6fb24/scratchpad/ux2/B/B-desk.png` (1440×2400)
- `/tmp/claude-0/-home-user/c23ee14e-85ed-5f5b-94f9-0fb713d6fb24/scratchpad/ux2/B/B-phone.png` (390×3000)

Note on the phone shots: headless Chromium here won't open a window narrower than about 485 px, so every "390" screenshot in `shots/` (the originals too) is a 485-wide layout cropped to 390, which is why their right edges are cut off. For B-phone.png the document is forced to 390 px on load, so it shows the true phone layout.
