# Starfront phase 1: the page and the panel (6 Nov 2026)

What the Observatory page (`astro-observatory.html`) and the control panel (`astro-app.py`) now show of the Starfront
Seestar, read only, from the record's `starfront` section and the engine's `units[]` (DESIGN.md "The record", "The
page", "The panel"). The checks are the `# ── SF (starfront) ──` block at the end of chain NL in `test_app.py` (12
checks, 2 skips on an engine without the scan). Nothing else was touched: no VERSION, CHANGELOG, PARITY, README.

## The page

### The Explore view "Starfront"

`RENDER.starfront`, a view in `VIEWS` (a hidden tab like every other view). The Explore menu lists it right after
"What each scope captured", and only when the record carries `D.starfront`; without the section the view says "No
Starfront scan yet" and nothing else changes, so a record from before the scan renders exactly as it did.

The head: the camera dot, "Starfront", the site chip, then "ZWO Seestar S50 Pro (Starfront) · last scan Fri 6 Nov
14:10, 2 h ago" (plus "scans paused" / "tunnel down" when so). Then five cards, in this order:

1. **Hours against target**, one row per project, most recent night first (`orderDatasets`): the object name, the label
   "14.1 of 20 h · 61 %" (minutes under an hour: "45 min of 12 h · 6 %"), a bar whose track is the target to scale
   across projects and whose fill is the hours, coloured by status (collecting = the capturing hue `--st-live-ink`,
   ready = the ready hue `--st-action-bg`, pulling and pulled-awaiting-clear = the Finish-it hue, cleared = the quiet
   line); under it the status pill (Collecting / Ready to pull / Pulling / Pulled, awaiting clear / Cleared), the ETA
   ("ETA about 3 nights, Tue 10 Nov"; a collecting project with no data in the window says "no ETA: nothing new in the
   last 14 nights"), nights and last night, and the flags as chips with their words (site mismatch, clock mismatch,
   mixed settings, pointing moved, unknown name; the reason is the chip's tooltip). A row opens the project (layer 3).
   "view as table": Project · Status · Hours · Target · Of target · ETA · Flags.
2. **Cumulative hours over nights**: a hand-built SVG, one line per project (a small palette, the legend under it names
   each with its hours-of-target line), each project's target as a faint dashed line in its colour, the ETA as a hollow
   point at (ETA date, target) joined to the last night by a dotted line; y ticks at 0, half the biggest target and the
   biggest target; the first and last date on the x axis. "view as table": nights down, a column per project with the
   running total.
3. **Nights at the site**: "7 nights with data · last scan … · nights are America/Chicago, named by their evening", a
   30-night strip ending on the newest night the section knows (a cell's shade is the roof-open share of the dark hours
   when `nightsLog` has them, the bar the hours captured), and a closed "Night by night" table (newest first: Night ·
   Captured · Dark · Roof open · Projects). The nights are the log's rows joined with the projects' nights.
4. **Storage on the scope**: "118 GB used · 110 GB free of 228 GB · 12.2 GB a night · full in about 9 nights", a meter
   with the per cent used, and when `pullNow` is set a warning line "Pull soon: the scope is full in about 2 nights
   (27 GB free)" with the meter in the attention colour.
5. **Tunnel, roof and the scan**: Tunnel ("up · last OK Fri 6 Nov 14:10 · on-demand", "down … · on hold
   (starfront-vpn-hold)"), Roof ("open since … · read …", "unknown"), Scanning ("on, every 2 hours from the PC" /
   "paused (starfront-pause in the state folder)"), Clock ("filename clock, unconfirmed"), Dark library ("120 files ·
   3.4 GB · newest Sun 1 Nov 09:00"), Camera; a warning is in the attention colour. A closing line says phase 1 is read only.

Dates and hours use the page's helpers (`fmtDate` "Fri 6 Nov", `fmtH` "14.1 h" / "45 min"); a time is the ISO string's
own HH:MM ("Fri 6 Nov 14:10"); GB figures come as numbers of GB and are shown with `sfGb` (one decimal under 100,
none above, TB from 1,024).

### The pure layer

`/* ==== Starfront pure layer … ==== */` sits INSIDE the phase 2 pure region (so the P2 node harness carries it and
`exploreItems()` may call `SF()`): `SF()` normalises the section once per record (every field tolerated, nothing throws),
`sfHoursLine`, `sfEtaTxt`, `sfNextAction`, `sfCumulative`, `sfNights` / `sfNightTxt`, `sfLastScanTxt`, `sfStorageModel`,
`sfStatusLines`, `sfBarsTable` / `sfCumTable`, `sfUnit`, `sfProject`, `sfUnitRows`, `sfLayerFor`, `sfUnitSub`,
`siteChipTxt`. The DOM pieces (`sfBarsCard`, `sfCumChart`, `sfCumCard`, `sfNightsStrip`, `sfNightsCard`, `sfStorageCard`,
`sfStatusCard`, `sfProjectsBlock`, `renderSfProject`) sit with the Explore views.

### The unit card, layer 2 and layer 3

- `normalise` keeps a unit's `site`; `shortName` reads the Starfront camera as "S50 Pro · Starfront" ("ZWO Seestar S50
  Pro (Starfront)" and "Seestar S50 Pro (Starfront)" alike). The card shows a site chip when the label doesn't already
  carry the site (the engine's label "S50 Pro · Starfront" does, so the chip shows on a unit labelled otherwise). The
  card's current projects come from the engine's summaries through `resolveSummary`'s fallback (no programme behind
  them yet), the next action is the engine's ("Collecting · 14.1 of 20 h · ready in about 3 nights").
- Layer 2 (`RENDER.unit`) for the Starfront unit: the site chip in the head; the sub line from the scan ("35.2 h on the
  scope · 12,654 subs · 7 nights · on the sky … · last scan …") while the ledger has no sessions for it; the current
  cards as for any unit; then "On the scope, from the scan" with every scan project (object, hours of target, status,
  ETA, nights, flags) and the note "nothing pulled yet, so the ledger has no rows for these"; no heatmap and no timeline
  while there are no sessions (its nights live on the Starfront view).
- Layer 3 (`renderSfProject`) for a Starfront project: the crumb back to the unit, "Starfront › Pleiades (M 45)", the
  scan note, the home scopes as chips with "Also on disk" when the ledger knows the object on other scopes, the state box
  (pill, next action, ETA, flag chips), the summary (hours and subs, target and per cent, nights, stacks, GB on the
  scope, first and last night), the flags with their reasons, the Nights table (night, hours, subs, so far), the
  cumulative chart for this project, by filter and gain. `openProjectLayer` and `RENDER.project` route to it through
  `sfLayerFor(tid, cam)`: a project the record has no target for, or a target the ledger knows on other scopes only when
  the layer is opened on the Starfront camera (from the card, layer 2 or the Starfront view); once pulled rows exist on
  the Starfront camera the ordinary layer takes over. `LAYER.ok` accepts a Starfront tid, so the remembered layer
  restores. A tid written as `starfront:<name>` resolves too.

## The panel

- `/api/state` carries `starfront`: `{scannedAt, scanAge, tunnelUp, tunnelLastOk, tunnelMode, roof, roofReadAt, paused,
  hold, share, canScan, scanWhy}`, or null when nothing names Starfront here (no scan file and no share in the config).
  `starfront_state()` reads `starfront-last-scan.json` from the state folder (the scan file as the engine writes it, or
  the same under a `starfront` key), prefers the engine's own `starfront_panel_status()` for the roof, the tunnel's last
  OK and the flags when the engine has it, and reports the two flags by their files (`starfront-pause` → `paused`,
  `starfront-vpn-hold` → `hold`).
- The Panel tab's Starfront card (`#sfCard`, hidden while `starfront` is null) under the scan card: the eyebrow "Starfront
  · last scan Fri 6 Nov 16:11, 1 min ago", the line "tunnel up (last OK …) · roof open (read …) · scans paused
  (starfront-pause) · VPN on hold (starfront-vpn-hold)" (in the warning colour when the tunnel is down or a flag is set),
  and **Scan now** with "read only" beside it (disabled while busy; on an engine without the scan or off the PC it is
  disabled and the note says why).
- `POST /api/starfront/scan` → `App.do_starfront_scan()`: the engine's `run_starfront_scan` in this process through
  `_run("starfront scan", …, need_camera=False)` (the oplock, stdout into the Activity log like the rebuild). A scan the
  engine ends with `sys.exit` or an exception is the job's error in the banner, never a traceback; a `{"ok": False,
  "reason"}` answer becomes "Starfront scan did not finish: <reason>". No pull, no clear, nothing writes to the share.

## The checks (`# ── SF (starfront) ──`, chain NL, 12 checks)

Page (node, the phase 2 pieces cut from the served page plus `_SF_HARNESS`): the markers; every block of the view from a
fixture with two projects (M 42 ready at 20.3 of 20 h with `mixed-settings`, M 45 collecting at 14.1 of 20 h with an ETA
of 3 nights / 10 Nov), storage, roof, tunnel, nightsLog (with one empty night) and a dark library; the Explore order; the
unit card and layer 2's scan rows; `sfLayerFor`; the same record without the section and a 1.8.0 record (no error, no
"undefined", no Starfront in Explore). Panel (its own env `SF`, a share folder with one sub and the test-mode tunnel
probe): the card and its script; `/api/state.starfront` before any scan (present because the config names a share);
from a hand-written scan file with each flag; Scan now runs the engine's scan as a job and the share is untouched; then
a rebuild with a Mac snapshot, the served record carries the section and the S50P-STARFRONT card, and the page's pure
layer draws the real record. On an engine without the scan the last two are skipped and the refusal is checked instead.
Each check fails against the 1.9.0 page and panel (run that way in the scratch harness: 8 of 8 fail, the rest skip).

## The fixture and the tooling

`/tmp/claude-0/-home-user/c23ee14e-85ed-5f5b-94f9-0fb713d6fb24/scratchpad/ux4/sf-page/`: `fixture_sf.py` builds
`fx-sf.json` (the phase 2 stress fixture plus the section with three projects: M 42 ready with a flag, M 45 collecting
with an ETA, IC 1396 a mosaic with 45 min, two flags and no ETA; storage, roof, tunnel, nightsLog, darklibrary; the
S50P-STARFRONT unit and scope), `fx-sf-warn.json` (tunnel down and on hold, paused, roof unknown, pullNow) and `fx-old.json`
(1.8.0); `render.py` fills the slot as `observatory_html()` does; `shoot.js` (node Playwright, Chromium, clock fixed at
6 Nov 2026 16:30 UTC, Europe/London) shoots and dumps the rendered texts to `texts.json` (no console or page errors on any
fixture, no "undefined"); `panel_harness.py` starts the panel in test mode as chain NL does, writes the scan file and the
flags, presses Scan now (the engine's scan ran against the share folder) and shoots the Panel tab (`shoot_panel.js`);
`dryrun.py` runs the SF block outside the suite (`--installed` runs the copy in test_app.py); `dryrun_orig.py` runs it
against HEAD's page and panel.

## Screenshots (`…/scratchpad/ux4/sf-page/shots/`)

- `phone390-fx-sf-starfront.png`, `desk1440-fx-sf-starfront.png`: the Starfront view (full page).
- `…-fx-sf-starfront-tables.png` (both toggles on "view as table"), `…-fx-sf-starfront-open.png` (Night by night open).
- `…-fx-sf-layer2-unit.png`: the Starfront unit's layer 2 (the card is on the landing; `desk1440-fx-sf-explore-open.png`
  has the Explore menu with Starfront in it).
- `…-fx-sf-layer3-project.png`: layer 3 for Pleiades from the scan, every section open.
- `…-fx-sf-warn-*.png`: the same with the tunnel down, paused, the roof unknown and the pull warning.
- `…-fx-old-starfront.png`: the view on a record without the section ("No Starfront scan yet").
- `phone390-panel-starfront.png`, `desk1440-panel-starfront.png`: the Panel tab's Starfront card after Scan now.

## Not done / for the other agents

- The unit card's tag shows the engine's `short` (`S50P-STARFRONT`), which is long on a phone; a shorter `short` on the
  engine's unit would read better. The card's label already carries the site, so the site chip only shows on a unit
  whose label doesn't.
- The scan's ETA for a project with no hours yet comes out as thousands of nights (the panel harness showed "about 7199
  nights, Sat 22 Jul 2046" for a one-sub test project); the page shows what the record says. The engine may want to
  leave `eta` null until there is a nightly rate.
- `darklibrary` in the scan file carries `bytes`, the record's section (DESIGN) `gb`: the page reads `gb` and shows
  "120 files" alone when only bytes are there. One of the two should give way.
- Roof-open hours on the nights strip need the roof log (`starfront-watch`); without it the cells are flat.
- The suite was not run here (the caller runs it); the dry-runs and the node parse stand in. The scan ran in the dry-run
  because this container has tzdata; on a PC without it the "Scan now" check still passes (the job's error is the
  banner) and the round-trip checks skip with the reason.
