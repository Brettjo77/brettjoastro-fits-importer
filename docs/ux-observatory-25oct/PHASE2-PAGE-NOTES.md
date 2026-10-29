# Phase 2 ("scope first"): the page side, 29 Oct 2026

What changed in `astro-observatory.html` (one file, now ~390 KB; it was 300 KB) and the `# ── P2 page ──` checks appended to chain NL in
`test_app.py` (7 checks). Nothing else was touched by this work. Not committed; VERSION, CHANGELOG, PARITY untouched.

## The three layers (plan §7)

- **Layer 1, the landing** (`RENDER.overview`, the default view): one status line in the header (`#status`, from
  `statusLine()`), one card per active unit from `units[]` in their order (`unitCard` ← `cardModel` ← `unitsOf`), the Resting
  row (a `details.fold`), then "Ready to process: {n} datasets · {hours} ›" (opens the Ready view), Recent nights as a 3-night
  strip that expands into today's full ledger (`renderRecent`, drawn on first open), "This month: {n} projects moved forward ·
  {n} finished" (`thisMonthLine`), and a quiet note with a link to Data checks when the record kept its states.
- **Layer 2, a unit** (`openUnit` → `RENDER.unit`): breadcrumb back, the unit's name and "on the FRA400", its one or two current
  projects as cards (object, hours, nights, last night, next action, "Also on disk: …"), the other datasets in short rows grouped
  Ready to process / Finish it / Still capturing / Done (3 each, "Show all {n}"), the Samples group, this unit's Imaging nights
  (the Nights heatmap drawn for its scopes only: `heatmapInto`), and "Timeline of its projects" (today's `scopePanelFor` for each
  scope of the unit). The ZWO unit's rows name the Askar per row.
- **Layer 3, a project** (`openProjectLayer` → `RENDER.project`): "ZWO › Stephan's Quintet" breadcrumb with a way back,
  "107PHQ › Stephan's Quintet (NGC 7320)", the other scopes as chips (anchored to the scope with the most recent capture when
  opened from Find or a list), the summary (state pill, reason, next step; hours, nights, first and last imaged; "Also on
  disk"), then `details` sections: integration by filter (a hand-built donut) and hours per night (bars); frames, calibration
  and processing (the three marks); the sessions table (night, site, frames, hours, filter · subs, calibration; 200 rows a page);
  other scopes on this object (hours, nights, frames, bytes, state); files (paths); and today's project panel (lanes and nights).
  "Open files" posts `archive-show` with the programme's `rel`; "Open in Explorer/Finder" posts `archive-open`; "Folder and
  files" opens today's drawer (`openTarget`).
- `go(id, instant, dir)` slides the next layer in from the right ("fwd") and back from the left ("back"), `--dur-short`
  (200 ms) over `--dur-fade`; `if(reduced()) instant=true` makes it instant under reduced motion. The page remembers the last
  view, its layer (unit / project / scope) and the Filter in the existing `aao` key (`mem.tab`, `mem.layer`, `mem.filter`).
- Container queries: `.ucards{container-type:inline-size}`, `@container cards (min-width:600px)` → 2 columns, `(min-width:840px)`
  → 3; measured inside frames of 700 px (2 columns) and 560 px (1 column) in a 1440 px window.

## Before → after: where every 1.8.0 view went (the Nothing-lost rule, plan §3.7)

| Before (docs/ux-observatory-25oct/before/index.md) | After |
| --- | --- |
| Overview › Recent nights (ledger, a week / 14 / 30 nights, the pending line) | Landing › "Recent nights" strip (3 nights) → expands into the same ledger (`renderRecent`, with `#pendLine`) |
| Overview › What each scope captured (tiles, moon row, columns, rows, selected night, Resting) | Explore › **What each scope captured** (`RENDER.scopes` → `renderStrips`) |
| Overview › What each scope shot | same view, under the chart (`renderShotBars`) |
| Overview › scope card face 2: a scope's timeline (`openScope` → `scopePanelFor`) | Layer 2 › "Timeline of its projects" (one panel per scope of the unit); every `openScope(cam)` call site (share bar, key, ledger heads, Equipment, chart labels, shot bars) opens the unit's layer |
| Overview › Projects that moved lately (cards with ring, lanes, the project panel) | Explore › What each scope captured, under the chart (`renderProjects`, `projCard`, `toggleProj`); the project panel is also Layer 3 › "Lanes and nights, every scope" |
| Overview › Needs your attention | Explore › **Data checks**, first card (`renderAttention`); the count sits on the Data checks item of Explore (ink, never red); the data-safety facts are the header's status line |
| Overview › What to do next (3 columns, Samples line) | Explore › **Ready to process** (`RENDER.ready` → `renderQueue`); the landing's "Ready to process: {n} datasets · {hours} ›" line opens it |
| Overview › Where the hours went | Explore › **Archive** (`RENDER.archive`) |
| Header: hero (hours of integration), frames · targets · nights · scopes, the share strip and its key line | Explore › Archive, the navy band at the top (`#archiveHero`, the same elements: `#hero`, `#comps`, `#sharebar`, `#sharekey`) |
| Header: freshness line ("Built on the PC at 03:38 … · 17 h old · from the Mac's record of …") and the pill | Footer (`#fresh`, `#live`), the build time in UK time |
| Header: the amber camera chip | The status line ("{n} files waiting on the {camera}, last scan {date}") |
| Nav: Key (the legend fold) | Explore › Key (the last item; the hidden `#keyBtn` keeps the fold's handler) |
| Nav: Refresh now | Still in the bar (right), shown inside the panel's frame; disabled while the rebuild runs; the footer says when it finished or didn't |
| Nav: theme button | Still in the bar |
| Targets | Explore › **Targets** (unchanged view; "Projects" in the menu's line) |
| Coverage | Explore › **Coverage** (unchanged) |
| Pipeline | Explore › **Pipeline** (unchanged) |
| Nights ("Imaging nights" heading) | Explore › **Imaging nights** (`RENDER.nights`, now `heatmapInto`, unchanged drawing) |
| Sky | Explore › **Sky** (unchanged) |
| Footprints | Explore › **Footprints** (unchanged) |
| Equipment | Explore › **Equipment** (unchanged) |
| Data checks (badge) | Explore › **Data checks · n** (unchanged, plus Needs your attention first and "Space on this computer" when the panel sends `space`) |
| The target drawer (`openTarget`: the project with its folders, Open in Explorer / Show in To process) | Reachable from Layer 3 ("Folder and files"), Targets rows, Coverage rows, Sky dots, Footprints, the night panel |
| The night panel (`openNight`) | Unchanged; opened from the ledger, the chart, the heatmap, the sessions tables, the lanes |
| Nav tablist / phone View select | Kept in the DOM, hidden (`go()` and the roving focus still use them); Explore is the switcher |

Every `openProject(name)` call now passes its scope, so a project opened from a scope's lane, the night panel, the queue, the
Pipeline, the shot bars or Where the hours went anchors Layer 3 to that scope.

## States (plan §7.6)

- Loading: the panel's "Working it out" note is unchanged; while a rebuild runs, `.ucards.busy` dims the cards in place (no jump).
- Empty: no active unit → "Nothing captured in 30 nights. Last out: {date}." (and the same line per unit in the Resting row).
- Nothing found: Find → "Nothing found for “…”. Try a catalogue code (M 31) or part of the name." with Clear; a Filter that leaves
  nothing → "No dataset matches the filter." / "No scope matches the filter." with "Clear the filter" (landing, Ready, Layer 2).
- Stale / at risk / couldn't check: the amber status line (four variants below). A 1.8.0 panel (no `status`) is amber too:
  "Couldn't check data safety: this record doesn't carry the safety facts", plus what the record itself knows (files waiting,
  age). Never "safe" without the facts.
- Rebuild failed: `refreshWatch` — after Refresh now, if the stamp never changes once the importer is idle again (or within 3 min),
  the footer says "The rebuild didn't finish: this is still the build from …" and a toast says the last good build stays.
- Partly unavailable: the landing's note ("An input couldn't be read … Done and Finish it kept their states · Data checks") from
  `statesKeptText`.
- Importer not answering: the footer pill reads "The importer isn't answering. Showing the build from 10:12 this morning." and a
  toast says it once.
- Panel restarted: unchanged (the panel's BOOT handling reloads the frame).
- Refreshing: the button is disabled (`aria-busy`) until the poll shows the new stamp; the footer says "Rebuilt 09:31 UK time."
- Back after hours: on `visibilitychange` to visible after more than an hour without a successful poll, the page polls and toasts
  "Checked for a newer record · Built on the PC at … · 17 h old".
- Opened on its own: the "← Importer" link shows when the page is the top window at `/observatory` (unchanged check).

## The fixture

`scratchpad/ux4/p2page/fixture.py` builds the fixtures from `docs/ux-observatory-16oct/R/truth/stress-dataset.json` (the 19 Oct
stress set: 87 targets, 505 sessions, 6 scopes, 1,000.7 h, as of night 2026-10-16) with every 1.7.2+ field, the phase 1 fields
(readySince, reason, finalDate, stateCounts…, samples under 30 min: 3) and the phase 2 fields of PHASE2-CONTRACT.md: `units[]`
(ZWO on the 107PHQ, S50 Pro with a Done note, S30 Pro, Starfront S50 Pro, S50 resting), `status`, `thisMonth` (8 moved
forward, 1 finished), `recordsUpTo`, `nextAction` / `calMissing`, `pendingImport.scope`, `space`; Okabe-Ito scope colours (plan
§9.2). Files: `fx-new.json`, the four status variants `fx-quiet` / `fx-risk` / `fx-stale` / `fx-unchecked`, and `fx-old.json`
(the 1.8.0 shape: phase 1 fields, none of phase 2). `render.py` fills the slot exactly as `observatory_html()` does (the engine
isn't imported: its three lines are copied). The suite's checks use a small hand-written fixture instead (the HN rows plus
scopes, their order, one session per row, and an engine `units[]` of three units).

Browser clock fixed at 2026-10-16 20:45 BST (the evening after the build), Europe/London, headless Chromium (Playwright 1.56),
dark theme unless named.

## Measurements (`scratchpad/ux4/p2page/measurements.json`)

| | 390×844 | 820×1180 | 1440×900 |
| --- | --- | --- | --- |
| landing ready (navigation → first card painted, ms) | 170 | 180 | 162 |
| header (wordmark + status line) · bar | 62 · 53 px | 66 · 45 px | 66 · 45 px |
| cards per row | 1 | 2 | 3 |
| cards (top–bottom, px) | 115–323, 333–512, 522–730, 740–947 | 111–338 ×2, 352–579 ×2 | 111–338 ×3, 354–581 |
| third card's bottom ≤ first screen | **730 ≤ 844** | 579 ≤ 1180 | 338 ≤ 900 |
| landing page height | 1,543 | 1,180 | 1,092 |
| Layer 2 (ZWO) page height | 2,677 | 2,668 | 2,643 |
| Layer 3 (Stephan's Quintet, sections closed) | 1,569 | 1,180 | 1,083 |

Also: phone landscape 844×390 → 2 columns in the fixed order (ZWO, S50 Pro, S30 Pro, Starfront); frames of 700 / 560 px inside a
1440 window → 2 / 1 columns (the page's own width, not the window's); reduced motion → `--dur-short: 0ms`, the layer is on with
no `entering` class after the click; before (25 Oct): 11,796 px / 6,355 px pages with "What to do next" at 8,371 / 4,747 px.

The four status lines, as rendered: "Everything's safe · records up to Fri 16 Oct" (quiet); "1,204 frames only on the Mac · 87
files waiting on the ASIAir, last scan Fri 16 Oct · records up to Fri 16 Oct"; "this record is 2 days old (the PC's copy) ·
records up to Fri 16 Oct"; "Couldn't check data safety: the ledger is locked by an import · records up to Fri 16 Oct". The old
record: "87 files waiting on the ASIAir, last scan Fri 16 Oct · Couldn't check data safety: this record doesn't carry the safety
facts · …". No "undefined" anywhere on the old record (landing, both layers, every section open).

## Screenshots

`/tmp/claude-0/-home-user/c23ee14e-85ed-5f5b-94f9-0fb713d6fb24/scratchpad/ux4/p2page/shots/` (62 PNGs):
`{phone390,tablet820,desk1440}-landing-{dark,light}.png` (first screen), `-landing-full-dark.png`, `-explore-open.png`,
`-filter-open.png`, `-layer2-unit.png`, `-layer3-project.png`, `-layer3-project-open.png` (every section open), `-find-m31.png`,
`-find-opened-m31.png`; `{phone390,desk1440}-view-{ready,nights,scopes,sky,footprints,coverage,equipment,health,archive,pipeline,targets}.png`;
`desk1440-status-fx-{quiet,risk,stale,unchecked,old}.png`, `desk1440-landing-old-record.png`, `desk1440-state-{offline-footer,
nothing-found,find-nothing}.png`, `phone844x390-landing.png`, `frames-700-and-560.png`. Tooling beside them: `fixture.py`,
`render.py`, `shoot.js`, `smoke.js`, `parse.js` (every `<script>` block through `new Function`), `dryrun.py` (runs the
`# ── P2 page ──` block against the page without the suite: 7 of 7 pass).

## Not done / for the other agents

- The S50's black dot on the navy Archive band has no outline yet (plan §9.2 is phase 4).
- Pictures, goals (rings), Park and the list behind "This month" are phase 3; the cards show hours and nights, no ring.
- The "Open the Panel" action on an amber status line shows only inside the panel's frame (it posts `open-panel`).
- `space` is rendered as the panel sends it (key → words, bytes → GB); the panel agent owns its shape.
- Sites on the sessions table come from `session.site` when the engine adds one (none today; the column shows "·").
- The suite was not run here (the caller runs it); `dryrun.py` and node parse stand in.
