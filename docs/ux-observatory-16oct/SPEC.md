# The Observatory, rebuilt: the merged specification (17 Oct 2026)

What the one page will be, blended from directions A and C (B's timeline spine kept), after the
five detail reviews in `R/`. Each rule below names the review it comes from, so the reasoning is
one click away. Brett's words that shaped it: "this type of thing is the right direction" (the
scope timeline), "be creative and colourful", "the devil is in the detail", "dynamic impact that
looks professional", "specific for the scopes attached to the ZWO camera, so FRA400 and
107PHQ, is the associated calibration frames", and "take a look at the data we have on disk:
there is a macro view, project view, micro view".

## 1. The page, top to bottom (A's order, C's honesty)

1. **Night-sky header** (both themes keep it dark): eyebrow, title, one freshness line, the hero
   "292.8 h" with its labelled companions (frames, targets, nights, scopes), the share bar by scope
   with every slice labelled, the legend strip (scopes in the one fixed order, the five next-step
   pills, the two unknown marks), and a sticky nav bar. The freshness line has a pill with five
   states: live · N min ago, a day old, rebuilding…, updated just now, importer not answering, and a
   slot for "N files on a camera not yet imported" (shown only when the engine says so; never a
   green tick when it doesn't know). [truth 2, motion 5, layout 2]
2. **Last night**: the date written as "Thu 15 → Fri 16 Oct" (night = noon to noon), one line per
   session with the scope's dot and name, hours, frames and filter; "3 objects" when a scope did
   several. Totals shown as the sum of the rounded parts. [truth 5]
3. **Needs your attention**: jobs with counts and a verb each (Review the names, Check those rows,
   Check the exposure, Say which Askar, Link darks and flats), the "fine, nothing to do" line for
   duplicates, every count from an engine field, never from a sentence. A done job collapses with
   Undo. [C, truth 4, motion 9]
4. **What each scope captured**: six lanes in the fixed order, a dot per night sized by hours,
   hollow when hours are unknown, the quiet band on the right, ranges 30 / 90 / a year /
   everything, with the week-cluster rule past 120 nights so dots never bunch; a text line per lane
   (hours over N nights, latest object, or "nothing in 30 nights, last out …"). Dots slide when the
   range changes. [A, B, motion 4]
5. **What to do next**: three columns, Ready to process (biggest first), Finish it, Still capturing
   (soonest ready first), each a compact card: name, scope dot and short name, labelled hours,
   nights, the hours bar against the biggest dataset, the calibration mark, the pill. Quick looks
   are listed under the columns, never in them. [A, C, type 2]
6. **Projects that moved lately**: cards with the ring of hours by scope, labelled numbers, one
   pill per scope (four on Andromeda), a mini timeline, and a header that is a real button: opening
   it slides a full-width panel under the row with one lane per scope, the quiet band, the stage
   glyph after the band and the three marks beside each lane. [A, C, motion 2]
7. **Where the hours went** (chart / table) and the rest of the views (Targets as the detailed
   list, Coverage, Nights, Sky, Footprints, Equipment, Data health), restyled to the same tokens.

## 1b. Three levels, the same as the disk (Brett, 17 Oct)

What is on the archive, as the importer lays it down and reads it back:

| Level | On disk | What it holds | On the page |
|---|---|---|---|
| **Macro: the archive** | `E:\Astro Image Data\<scope root>\` (S30P, S50, S50P, ZWO Askar Scopes), `E:\Final Astro Images\`, `_verify\` (both computers' records) | every scope, every season, both computers' ledgers, the inventory, the finals | the header, the six-scope strip, Needs your attention, What to do next, Where the hours went, the Nights / Sky / Equipment / Data health views |
| **Project: one object** | `<scope root>\<Name (CODE)>[ (mosaic)]\` with its `Day N` folders, `Stacked_*` autostacks (Seestar), your masters in the object folder, Collect-Lights output, and the final in `Final Astro Images\<root>\CODE_Name__YYYY-MM_Rig` | one object on one scope (a dataset); the same object on several scopes is one project (the Askars share one folder) | the project card and its expanded panel: one lane per scope, the quiet band, the three marks, masters and finals named, and one row per Day folder |
| **Micro: one night** | `<Name> Day N\`: the lights (`Light_<target>_<exposure>s_Bin1_<camera>_gain<g>_<datetime>_<temp>C_<n>.fit`), the linked `Darks\`, `Flats\`, `Bias\`, `_Working Files (regenerable)`, a Seestar's own stack | that night's frames, with exposure, filter, gain, binning, sensor temperature and rotation read from the names; which calibration frames were linked and whether they matched; what the archive has verified; which computer imported it | a **night panel** opened from a dot or a Day row: the date (evening → morning), frames and hours, filter and exposure, gain and temperature, the calibration block of §3, autostacks and working-file size, "imported on the Mac / PC, verified on the archive", and Open folder |

Rules that follow:

- Every dot on every timeline is a night folder, and opens the night panel. Every lane is a dataset,
  and opens the project panel. Every scope row opens the scope. Nothing is a dead end.
- The three levels share one vocabulary: the same scope colour, the same pills, the same marks, the
  same number formats, so a number seen at macro level is the sum of what the project and night
  levels show.
- The night panel is where the ZWO calibration detail lives (§3); the project panel shows only the
  summary mark per lane; the macro level shows only the count of datasets missing calibration.
- The micro level needs the night's fields in the dataset (§6.3): today the page has frames, hours,
  filters, exposures and the calibration counts per session, but not gain, temperature, the Day
  folder key, which computer imported it, or the autostack and working-file sizes. The engine has
  all of them in the ledger and the inventory.

## 2. Meaning: what every mark says

- **Scope colour means scope, nowhere else**, from `D.scopes[].colour`, always beside the scope's
  name, always in the one order the engine gives (`scopes[].order`). A 2 px surface ring on every
  mark; no glow anywhere. [colour 1, 2, 5]
- **Status is a glyph plus a word, not a hue.** Still capturing = teal tint ◔, In progress / Finish
  it = teal solid ◑, Ready to process / Process it = ink solid ▶ (the one thing to do, highest
  contrast), Done = outline ✓, Quick look = dashed outline ○. The pill shows the next step as a
  verb where there is one. [colour 1, truth vocabulary]
- **Three small marks beside every Askar dataset lane**: Capture (Active · last frames N nights
  ago / Open, kept by you / Closed by you on {date} / Quiet · nothing new for N nights), Processing
  (Not started / Master saved / Final found), Calibration (see §3). A `?` where the engine is unsure,
  with the note. [C, truth 3]
- **Unknown is never 0**: "hours unknown · 2,150 frames", hollow dots, hatched bar segments, and
  the job "Check the exposure" with a button to tell the importer the sub length once. [all]
- **Quick look** is Brett's flag (`programmes[].sample`), never an hour rule. Nothing with a master
  or a final can be a quick look. [truth 1]
- **Warnings** are ink on a warm wash with ⚠; "fine" rows are muted with ✓; green is never used for
  "ok" (green is the S50 Pro). [colour 6]
- The shared-Askar note appears only when the engine says the master's owner is uncertain
  (`masterOwnerUncertain`), and is suppressed when the file name carries a scope id. [truth]

## 3. Calibration for the ZWO scopes (Brett, 17 Oct)

Every FRA400 and 107PHQ dataset carries a **Calibration block**, in the queue card as one mark and
in the expanded lane and the night panel in full:

- Per dataset: "darks and flats on 7 of 9 nights · 2 nights without", with the mark ✓ Complete,
  ⚠ Missing flats, ⚠ Missing darks and flats, or ○ Unknown.
- Per night (in the night panel): darks N (exposure, gain), flats N (filter), bias N, matched or
  not (gain, exposure within tolerance, taken within the window, sensor temperature for darks),
  and whether the archive has verified the copies; a night with none linked is marked, and its Day
  folder opens with one click through the existing archive-open route.
- Seestars say "not tracked · the camera calibrates in itself", never "not needed". [truth]

The engine already matches these frames at import (gain, exposure, window, temperature) and links
them into the night's folder; only the totals reach the page today. §6 lists the fields.

## 4. Craft: type, spacing, layout

- **Eight sizes, three weights**: 11 / 12 / 13 / 14 / 16 / 20 / 28 / 48, weights 400 / 600 / 700.
  Headings 20/700, item titles 14/600 (16/700 on project cards), meta 12/400, eyebrows 11/600
  caps. Numbers in tabular figures, right-aligned in columns, unit in the same size and lighter,
  number and unit never split across lines. [type 1, 3, 4]
- **One spacing ladder** (4 / 8 / 12 / 16 / 24 / 32 / 48): 24 between cards, 8 between items, a
  4 px inset accent bar, two control heights (24 chip, 32 button; 44 on touch). [type 5]
- **Long names**: common name + muted codes that never split from each other, clamped to two lines
  with the full name on hover; chart labels truncated with a title. Tested with "Open cluster in
  the Tadpoles (IC 410) (NGC 1893)". [type 2]
- **Container 1280 px**, centred at 1920; breakpoints 1100 / 900 / 700: tabs tighten then wrap, a
  labelled View select under 700, project cards 3 / 2 / 1-up, the six-scope strip becomes one
  shared SVG with names inside at phone width, the queue becomes tappable cards, every grid column
  `minmax(0, …)`, every SVG drawn at its real pixel width and redrawn on resize (no
  `preserveAspectRatio="none"`). Nothing under 44 px to tap on a phone. [layout 1, 3, 4, 5]
- **Phone first screen**: header ~190 px, sticky 52 px bar, then Last night and the top three to
  process, all within the first 844 px. [layout 2]
- **One scrollbar**: the Observatory opens as its own route on the local panel with a "← Importer"
  link, not an iframe inside the panel's page. [layout]
- **Both themes**: dark by default (night, by the scope), light when the OS says so or by the
  toggle, remembered in localStorage; the header stays night-sky in both. Text tiers pass AA on both
  (muted ≥ 5.2:1), pill text ≥ 4.5:1. [colour 3, 4]

## 5. Motion: alive, not busy

Tokens: `--dur-micro 60 · short 120 · base 200 · long 320 · reveal 480`, `--ease-out / in / move /
spring`, `--stagger 70`, all to 0 under `prefers-reduced-motion` (opacity fades stay at 120 ms).
[motion spec]

- **Load-in**, once: header halves rise, share bar grows left to right, blocks rise with a 70 ms
  stagger, rings draw, dots sweep left to right; 1.2 s in all. The hero number does **not** count
  up on load. [motion 7]
- **Range change**: dots keyed by scope|night slide to their new places (320 ms), the band slides,
  leavers fade, arrivers pop. [motion 4]
- **Expand a project**: a full-width panel under the card's row, height 480 ms, contents fade 60 ms
  later, scroll only as far as needed, Esc closes, focus returns. The night panel opens the same
  way from a dot or a Day row. [motion 2]
- **Hover and focus**: cards lift 1 px, buttons press, dots scale 1.25 with an ink stroke, chips
  wash, the tab underline slides. One anchored tooltip on marks only: 90 ms open, instant while
  warm, value first, a scope-colour key, the same on keyboard focus, pinned by a first tap on touch,
  24 px hit circle. [motion 3, 8, 11]
- **Live refresh**: 30 s poll of `/api/status`; when the record changes the page redraws in place:
  the hero counts from old to new (the only count-up), changed numbers wash, the new session pops
  into its strip, a toast says what arrived with Show. [motion 5]
- **Keyboard**: tabs as a roving tablist, each strip one tab stop with ← → walking the nights,
  Enter opens the project, ranges as a radio group, Esc everywhere. [motion 6]

## 6. What the engine must add (the honest page needs facts, not regexes)

From `R/truth/data-needs.md`, in priority order:

1. Pass through what it already knows: `programmes[].captureState` and its source,
   `calibration.{nightsWith, nights, darks, flats, biases}`, `masters[]`, `finals[]`,
   `notCounted {unknownNames{names, frames}, noScope, noNight, unreadable, duplicates, notLightFrames}`,
   structured `warnings[] {kind, count, frames, text}`, `scopes[].order`, `scopes[].kind`,
   `unknownNames[]`, `inputs` as the object (snapshot machine, time, age, rows), a documented
   `snapshotRows` vs `ledgerMeta.rows`.
2. New: `pendingImport {files, targets, failedEject, camera, seenAt}` from the last scan;
   `programmes[].sample` from capture-state.json; `masterOwnerUncertain`; `calibration.mode`
   (tracked / inCamera / unknown); `programmes[].exposureOverride`; several sessions per scope and
   night with their objects; `night.evening`; `generatedAtLocal` + timezone;
   `targets[].plannedScopes[]`.
3. For the night panel (§1b) and the calibration block (§3): per night, the Day folder key, gain,
   sensor temperature, binning, which computer imported it and whether the archive verified it,
   autostack and working-file sizes, and the linked darks / flats / biases with count, exposure,
   gain, filter, matched flags and verified flag.
4. For live refresh: `observatory.generatedAtIso` and `rebuilding` on `/api/status`, and
   `GET /observatory?json=1` returning the dataset. [motion 5]

Page-side rules with no new data: one rounding function and totals as the sum of displayed parts;
scopes counted with a set; percentages by largest remainder; minutes under 0.1 h; scope order only
from `scopes[].order`; never regex `evidence`, `sourceNote` or warning prose. [truth]

## 7. Build order (proposed as 1.7.2)

1. Engine fields (§6.1 to §6.3) with tests in chain OB; the two `/api/status` additions.
2. Tokens (type, spacing, colour, motion) into `astro-observatory.html`; both themes.
3. Header, legend, last night, needs-attention, the six-scope strip, the queue, the project cards
   and panel, the night panel, in that order, each checked at 390 / 768 / 1024 / 1440 with the
   harness in `R/layout`.
4. The remaining views restyled; the Observatory as its own route; the panel's Refresh retired in
   favour of the in-page refresh.
5. The stress dataset (`R/truth/stress-dataset.json`, 87 targets / 147 datasets) run through every
   view before release; Safari and Edge checked on Brett's machines.

## 8. Still Brett's to decide

- The names (Tadpoles, Sadr / NGC 6910, Sh2-171 / NGC 7822, LDN 386, the Squid's code), which fix
  the project count before any of this is drawn.
- Which datasets are quick looks (a line each in capture-state.json; the page will offer a button).
- The sub length for frames with no exposure recorded (Milky Way Core).
