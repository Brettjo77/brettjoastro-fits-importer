# Observatory: UX review, 13 Oct 2026

Three reviewers looked at the Observatory tab after the 1.7.0 first cut, each
from one angle: the first screen and its hierarchy, the charts and visual
language, and the flow between the Observatory and the To process tab. This
is the merged list, in priority order, with what is already done. Brett put
the full pass on the backlog (13 Oct); the first two items were done the same
day because he asked for them.

## Done on 13 Oct

- **The job comes first.** The Overview opens on "What each scope captured
  last", then "What to process next on the PC"; the headline hours and the
  stats sit below. (Brett: "interesting, but not serving my purpose".)
- **Click a scope for its timeline.** Each scope's name on that first card
  turns the card into a calendar of its projects: one row per object, a dot
  per session sized by hours, the night-by-night activity on top, the quiet
  period shaded, the dataset's state at the end of each row; 90 nights / a
  year / all time. The hero rows and the Equipment cards open it too.
  All three reviewers asked for a per-scope timeline on a real calendar;
  this is that, in its first form.

## Where the reviewers agreed

1. **Time was never drawn to scale.** The drawer's "Sessions, night by night"
   puts sessions side by side, so a two-month gap looks like one night; the
   monthly rhythm chart skips empty months, so a cloudy month vanishes. Both
   should use the calendar renderer the scope timeline now has.
2. **Recency is never said.** Every date is absolute ("11 Oct 2026"). Add a
   helper that says "last night", "3 nights ago", "2 weeks ago", on the
   engine's noon-to-noon night, and use it on cards, in Targets (sort by
   most recent by default) and on the scope timeline rows.
3. **Three lists of the same datasets disagree.** The Overview queue and the
   Pipeline sort biggest first; the To process tab sorts newest first. Pick
   one (newest first matches "what did I capture recently") and point the
   Observatory's queue at the To process tab rather than compete with it:
   the Observatory owns understanding, To process owns acting.
4. **The masthead repeats the panel.** Its provenance lines say what the
   panel's own line above the frame says. Shrink the masthead to one sticky
   bar (wordmark, six "scope lights" lit when the scope ran inside the
   quiet period, tabs, a staleness pill only when the PC record is over a
   day old). That frees about 120 px of a frame that is only ~600 px tall.
5. **Blocks that can never show.** The engine always sends `delta: null`,
   `events: []`, `askarRigs: {}`, `calibration: {}` (library) and
   `shelves: {}`, so "New since the previous snapshot", "Sun, Moon and
   planets", the Askar rigs card, the calibration library and the shelves
   card are dead code. Delete them, or feed them.
6. **Colour means two things.** The Nights heatmap, the exposure chart and
   the filter minibar use a blue scale that is the S30's blue. Switch those
   to neutral greys ("starlight") so a scope colour only ever means a
   scope. Also: the S50's black mark loses its white edge in Footprints
   (the stroke is overwritten); keep `var(--edge)`.

## The rest, by priority

**Quick (an hour or less each)**

- "Show in To process" from the drawer lands on a half-drawn pane: the tab
  click starts `loadDesk()` without waiting, and the right pane uses the
  August-scan state. Wait for the load, use the live state, open the
  section that holds the row, scroll to it, pulse it once.
- Don't reload the Observatory iframe on every tab click; reload only after
  a rebuild or when `generated_at` changes. Today a round trip loses the
  open drawer, the scroll position and the filters.
- Give the drawer's dataset row a "Start Siril here" button (a third
  message kind, `archive-siril`, same checks as the other two) and call the
  open button "Open folder", not "Open in Explorer" built from the machine
  that *built* the file (on the Mac serving the PC's copy it says Explorer
  while Finder opens).
- Open the panel on the right tab: remember the last tab; with no camera
  connected start on To process with the newest row selected.
- Pipeline: order the columns To process, In progress, Still capturing,
  Done; collapse Done; sort Still capturing by `readyOn`.
- Coverage: tint each cell by hours (log scale) instead of a flat 14%.
- Fold the August-scan folder list on To process into a closed "Find any
  folder on the archive" section; it is a second to-process list with
  older states.
- Motion rules: nothing loops forever (`#twinkle` runs a 7 s animation
  behind every tab; the panel has no `prefers-reduced-motion` rule); hover
  transitions on rows; a one-off wash on rows that changed after Refresh;
  no entrance animation on lists he opens many times an evening.
- Keyboard and focus: the drawer needs `role="dialog"`, focus moved in on
  open, Esc to close, `inert` while closed; the panel's `role="button"`
  rows should answer Space as well as Enter; the panel has no
  `:focus-visible` style.

**Larger (half a day each)**

- "Up next on the PC" as a queue with one action: a big #1 card (target at
  24 px, why it is ready, calibration chips "✓ 40 darks / ✗ no flats
  linked", one primary button Open folder), then rows 2–5, then "On the
  bench" (in progress). Replaces the four-card columns.
- "Coming up": a strip of countdown chips for still-capturing datasets
  ("ready in 5 nights", a 3 px progress bar on the quiet period).
- Refresh shows what moved: keep the list visible while rebuilding, then
  compare old and new by dataset key, wash the changed rows, and say
  "2 changes: M 31 · FRA400 moved to In progress; …".
- Per-night figures in `projects.json` (`recent: [[night, seconds, frames]]`
  for the last 30 nights) so the To process tab can show a "This week"
  strip and a sparkline per row.
- Nights: one rolling 12-month strip ending at `asOfNight`, earlier years
  behind a button, full-moon marks, drop the Mon/Wed/Fri labels.
- "Tonight" on the Sky tab: a shaded band for the RA range on the meridian
  in the dark tonight at Shinfield, a low-sky band below Dec −8.6°, month
  chips, and a summary line ("23 of your targets are well placed; still
  capturing and up: …; already To process and up: M 31: process it rather
  than shoot more"). Needs the site's latitude and longitude: add
  `D.site` from `contract/scopes.json`, with a page constant as fallback.
- Touch, for the phone later: tooltips on tap, 40 px targets, an edge fade
  on the tab strip, a full-width drawer under 600 px.

## Decisions that need Brett, not code

- One sort order for every "to process" list: newest first or biggest first.
- Whether the Observatory's own queue stays, or becomes a pointer to the
  To process tab.
- The scope colours are kept exactly as set (S30 Pro yellow, 107PHQ green,
  S50 black, S30 blue, FRA400 red, S50 Pro pink); the light theme uses
  darker shades of the same hues.
