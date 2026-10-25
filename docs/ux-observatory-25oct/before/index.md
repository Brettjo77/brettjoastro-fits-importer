> Copied from the 25 Oct investigation: only five of the 78 screenshots are kept in the repo (the two double headers, the Overview at both widths, the Dashboard tab); the measurements below are from the full set.

# "Before" screenshots: the Observatory page, FITS Importer 1.7.6 (25 Oct 2026)

Repo `/home/user/brettjoastro-fits-importer`, branch `main` (HEAD 23609c7, `VERSION = "1.7.6"`), **read-only**: `git status` is
clean after this round. Everything ran in TEST MODE: the engine and the panel were started under `test_env_helper.make_env(root)`
with roots inside this folder (`testroot-render/`, `testroot-panel/`), so they refuse any path outside the root and never use port
8765. No real data, no real ledger, no real camera.

All files are in this folder: `/tmp/claude-0/-home-user/c23ee14e-85ed-5f5b-94f9-0fb713d6fb24/scratchpad/ux4/before/`.

## Dataset

`tools/dataset.json` = a copy of `scratchpad/ux3/build/dataset.json` (the 19 Oct round's set): the real-size stress set
(87 targets, 505 sessions, 6 scopes, 1,000.7 h) **with every 1.7.6 `observatory/1` field** (`scopeOrder`, `generatedAtLocal`,
`timezone`, `notCounted`, `notices`, `unknownNames`, `pendingImport` of 87 ASIAir files / Tadpoles Nebula / 85 backed up by the PC,
per-session `calDetail` / `importedOn` / `archived`, `servedFrom`). It was checked key-for-key against what the engine's
`observatory_from()` returns (1.7.6, astro-import.py:11433): nothing missing, one extra (`servedFrom`, which the panel itself adds).
The other candidates were rejected: `ux2/dataset.json` (41 targets) and `docs/ux-observatory-16oct/R/truth/stress-dataset.json`
(87 targets) both lack the seven 1.7.2+ fields (`generatedAtLocal`, `notCounted`, `notices`, `pendingImport`, `scopeOrder`,
`timezone`, `unknownNames`) and have no `calDetail`/`archived` on sessions, so the Recent nights ledger, the camera chip and the
pending line would not render as they do for Brett. The record says "built on the PC, 19 Oct 2026 03:38, from the Mac's record of
18 Oct 20:04", as of night 2026-10-18; it carries 5 warnings and 1 notice, so the Data checks badge shows **5**.

**Clock.** The browser clock was fixed at **2026-10-19 19:45 UTC (20:45 BST), timezone Europe/London** (Playwright
`page.clock.setFixedTime`): the evening after the record was built, so the freshness line reads "17 h old", the camera files "seen
5 min ago", and the newest night is "2 nights ago". Shots marked *realclock* used today's date (25 Oct 2026) instead: the same
record is then 6 days old. The standalone page remembers nothing between contexts (fresh profile each time).

**Fonts.** Headless Linux Chromium: DejaVu Sans / Liberation, not SF or Segoe. Text is a little wider than on Brett's Mac or PC;
the 19 Oct build notes measured the same effect (the scope key wraps to a second line in the header at 1440).

## Measurements

Measured with `document.documentElement.scrollHeight` and `getBoundingClientRect().top + scrollY` of the "What to do next" `<h2>`
(and its card), after the page settled (identical at 0.3 s, 1.3 s, 3.3 s, after a scroll and after a resize). Full numbers in
`measurements-standalone.json` and `measurements-panel.json`.

| View | Width | Page height | "What to do next" h2 top | its card top | Notes |
|---|---|---|---|---|---|
| Overview, dark, standalone | 1440 | **6,355 px** | **4,747 px** | 4,726 px | plan claimed 3,550 of 5,108 |
| Overview, dark, standalone | 390 | **11,796 px** | **8,371 px** | 8,354 px | plan claimed 7,694 of 11,479 |
| Overview, light, standalone | 1440 | 6,004 px | 4,395 px | 4,374 px | shorter only because a shorter night was selected in the chart before this pass (see below) |
| Overview, light, standalone | 390 | 11,168 px | 7,743 px | 7,726 px | same |
| Overview inside the panel's frame | 1440 | 6,373 px (the frame's document) | — | — | +18 px: the pending line's "Open the Panel to import" button |
| Overview inside the panel's frame | 390 | 13,202 px (the frame's document) | — | — | the page's header is 207 px in the frame (187 standalone): the Refresh button appears |
| /observatory opened on its own | 1440 | 6,355 px | — | — | "← Importer" link shown, Refresh hidden |

Section tops on the 1440 Overview (dark): Recent nights 187 · What each scope captured 1,729 · Projects that moved lately 3,458 ·
Needs your attention 4,195 · What to do next 4,747 · Where the hours went 5,638 · footer 6,243. At 390: 257 · 2,429 · 5,244 ·
7,209 · 8,371 · 10,770 · footer 11,584.

Header band: 121 px at 1440 (the scope key wraps to 2 lines), 187 px at 390; nav bar 45 px (1440) / 53 px (390); `#main` starts
at 166 px (1440) / 240 px (390). Inside the panel the frame starts at **157 px** (1440: panel header 97 + tabs) and at **316 px**
(390), so the page's own header is at 157–278 px (1440) and 316–523 px (390) of the window: the "double header".

Why the Overview height moves: the "What each scope captured" card's height is set by the selected night's panel on the right
(1,739 px tall with the 5-scope night of Fri 16 Oct selected on load; 1,387 px after selecting a lighter night). The chart selects
the newest night out on load, so the first-load numbers above are the ones to compare with the plan.

## Files: view → file → what it shows

Prefix `desk1440-` = standalone page, 1440×900 viewport; `phone390-` = standalone page, 390×844 (a true 390 px viewport in Playwright,
no iframe trick needed this time); `panel-` = the real panel (astro-app.py in test mode) at that viewport. `-dark`/`-light` = the
page's own theme (`data-theme`). Full-page shots are the whole document; element shots are clipped to the element.

### 1. Overview

| File | What it shows |
|---|---|
| `desk1440-overview-dark.png` (1440×6355) | Overview, full page, dark |
| `desk1440-overview-light.png` (1440×6004) | Overview, full page, light theme |
| `phone390-overview-dark.png` (390×11796) | Overview, full page, dark, phone width |
| `phone390-overview-light.png` (390×11168) | Overview, full page, light, phone width |
| `desk1440-what-to-do-next-dark.png`, `phone390-what-to-do-next-dark.png` | the "What to do next" card alone (3 columns of Ready to process 41 / Finish it 23 / Still capturing 30; one column on the phone) |

### 2. The other views (full page, dark; the page's own tab names)

| View (tab name) | 1440 | 390 |
|---|---|---|
| Targets | `desk1440-view-targets-dark.png` (7,103 px) | `phone390-view-targets-dark.png` (24,418 px) |
| Coverage | `desk1440-view-coverage-dark.png` (5,484) | `phone390-view-coverage-dark.png` (5,922) |
| Pipeline | `desk1440-view-pipeline-dark.png` (7,092) | `phone390-view-pipeline-dark.png` (17,401) |
| Nights | `desk1440-view-nights-dark.png` (1,152) | `phone390-view-nights-dark.png` (1,584) |
| Sky | `desk1440-view-sky-dark.png` (4,037) | `phone390-view-sky-dark.png` (7,840) |
| Footprints | `desk1440-view-footprints-dark.png` (1,173) | `phone390-view-footprints-dark.png` (2,168) |
| Equipment | `desk1440-view-equipment-dark.png` (1,659) | `phone390-view-equipment-dark.png` (2,951) |
| Data checks (badge 5) | `desk1440-view-health-dark.png` (1,956) | `phone390-view-health-dark.png` (3,035) |

There is no "Archive" tab on the 1.7.6 page (the panel's own "To process" tab is the archive view, see §5). The views are
`VIEWS=[overview, targets, coverage, pipeline, nights, sky, footprints, equipment, health]` (astro-observatory.html:1204); "Data
checks" is the label of `health`. Each view was painted with `go(id,true)` after a scroll to the top.

### 3. Pieces of the Overview (element shots, dark unless named)

| File | What it shows |
|---|---|
| `desk1440-header-dark.png`, `phone390-header-dark.png` | the header band: wordmark + eyebrow "PC · E:\Astro Image Data", the freshness line "Built on the PC at 03:38 this morning · 17 h old · from the Mac's record of 18 Oct 21:04", the pill ("saved record" standalone, "live" in the panel), the amber chip "⚠ 87 files still on the ASIAir", the hero 1,000.7 h, "78,668 frames · 87 targets · 320 nights · 6 scopes", the share strip and the scope key |
| `desk1440-header-light.png`, `phone390-header-light.png` | the same in the light theme |
| `desk1440-sharebar-dark.png`, `phone390-sharebar-dark.png` | the share strip and the scope key line (`#share`) alone |
| `desk1440-navbar-keyfold-open-dark.png`, `phone390-navbar-keyfold-open-dark.png` | the nav bar with the **Key** fold open: scope swatches, the next-step pills, the marks (hollow dot, hatched, the band, the speck, the moon glow, ‹N). This is the page's legend; there is no "Explore" bar on 1.7.6 (the only "Explore" in the page is "Open in Explorer") |
| `desk1440-scopecard-face1-all-scopes-dark.png` (1232×1739), `phone390-…` (358×2821) | the first scope card, **face 1**: "What each scope captured" with all scopes (tiles, moon row, all-scopes column chart, one row per scope, the selected-night panel for Fri 16 Oct, Resting, the legend) plus "What each scope shot" under it |
| `desk1440-scopecard-face1-all-scopes-light.png`, `phone390-…-light.png` | the same card in the light theme |
| `desk1440-scopecard-night-panel-dark.png` (312×853), `phone390-…` | the **night panel** of the scope chart with the newest night selected: "Selected night · Fri 16 Oct · 11.5 h · across 5 scopes", the moon (waxing crescent 31 %), one row per scope with its objects, Previous / Next night out |
| `desk1440-scopecard-other-night-selected-dark.png`, `phone390-…` | the chart after clicking a different column (column 29, the last one: a night with no frames), so the panel shows the "no frames" case |
| `desk1440-scopecard-face2-one-scope-timeline-dark.png`, `phone390-…` | the first scope card, **face 2**: `openScope("Seestar S30 Pro")` (the first scope in `scopeOrder`) expands the scope's own timeline panel "Seestar S30 Pro: what it has been doing" (one row per object, a dot per night, 90 nights / a year / everything) inside the card |
| `desk1440-project-card-open-dark.png` (1232×1817), `phone390-…` (358×4334) | "Projects that moved lately" with the first card (Stephan's Quintet) **opened**: the project panel, "one lane per scope" (S30 Pro / FRA400 / 107PHQ), its marks and nights table |
| `desk1440-project-card-open-card-only-dark.png`, `phone390-…` | just the opened card: ring, meta line, one row per scope with its state, the mini timeline with one lane per scope |

### 4. States

| State | File | How it was produced |
|---|---|---|
| Loading, "Working it out…" | `panel-desk1440-observatory-loading-working-it-out.png` | the real panel; the `/observatory?t=` reply was held for 6 s with a Playwright route, shot 0.9 s after clicking the tab: the panel's note row says "Working it out…" with its own Refresh now, the frame is empty |
| Empty record (no targets) | `panel-desk1440-observatory-empty-record.png` | `state/observatory.json` rewritten with `targets: []`: the panel serves its note "Nothing to show yet: no light frames in this computer's ledger … Warnings: …" (the five warnings run together without separators) and its row says "See the note in the frame." |
| No record yet | `panel-desk1440-observatory-no-record-yet.png` | the file moved away: "The Observatory hasn't been worked out on this computer yet. Press Refresh now (above), or run --projects in Terminal…" |
| Stale / old record | `desk1440-header-realclock-6-days-old-dark.png`, `phone390-…`, `desk1440-recent-nights-realclock-dark.png`, `phone390-…` | the same record with today's real date (25 Oct): "Built on the PC at 03:38 on 19 Oct · 6 d old", the pill still says "saved record"/"live" (the stale state keeps the word "live": `setLive`, astro-observatory.html:1170), and Recent nights shows "record built 19 Oct 2026, 03:38 · nights after it are not in this list". `desk1440-header-state-stale-dark.png` / `phone390-…` = `setLive("stale")` forced on the fixed-clock page (identical to fresh: that is the point) |
| "The importer isn't answering" | `panel-desk1440-importer-not-answering.png`, `-header.png`, `panel-desk1440-tab-panel-importer-dead.png` | **genuine**: the panel process was killed (SIGKILL) under the open page, then one poll was forced (`live.fails=1; poll()`), which is what the page does on the second failed 30 s poll. The page's pill reads "importer not answering" (the camera chip wraps to a second line, header grows 121→143 px); the panel's own pill reads "panel disconnected — is the app running?". Standalone equivalents: `desk1440-header-state-offline-dark.png`, `phone390-…` (`setLive("offline")`) |
| Rebuilding / refresh in progress | `panel-desk1440-observatory-rebuilding-forced.png` (`setLive("rebuilding")` in the frame), `desk1440-header-state-rebuilding-dark.png`, `phone390-…`; **real**: `panel-desk1440-refresh-real-t0.3s.png`, `-t1.8s.png`, `-t14s.png` | the real Refresh now was clicked in the frame last of all: the panel ran `/api/projects/rebuild` on the empty test ledger, so the record was replaced by an empty one within ~1 s (t0.3s shows the "rebuilding…" pill; t1.8s and t14s show the result: the frame reloaded to the "Nothing to show yet" note with the test root's warnings). The rebuild is too quick on an empty ledger to show a longer "rebuilding…" phase; the forced shots stand in for it |
| Record with warnings / notices | `panel-desk1440-observatory-data-checks-warnings.png`, `desk1440-view-health-dark.png`, `phone390-view-health-dark.png`, and "Needs your attention 5" on every Overview shot | the dataset's 5 warnings + 1 notice (184 frames of 2 unknown names, 5 no scope, 7 no night, 3 unreadable, 11 projects without darks/flats) |
| `/observatory` opened on its own in a tab | `panel-desk1440-observatory-route-alone.png` | the full page served outside the frame: "← Importer" back link shown, Refresh now hidden, pill "live", the pending line has no "Open the Panel" button. **Not forbidden**: it renders |
| `/observatory?json=1` opened in a tab | `panel-desk1440-observatory-json-route.png` | **the raw dataset as JSON, readable in the tab** (Chrome's JSON viewer, "Pretty-print" box). The server sends it to any same-site GET without a token (astro-app.py:1286, guarded only by the cross-site Sec-Fetch check). So the expectation "raw JSON forbidden" is not what 1.7.6 does: capture this as the before-state |
| Both themes | `*-overview-dark.png` / `*-overview-light.png`, `*-header-*`, `*-scopecard-face1-all-scopes-*` | `data-theme` set on the root; the page's own toggle (`#theme`) does the same |

### 5. The panel itself (astro-app.py in test mode, port 48229, state planted)

| File | What it shows |
|---|---|
| `panel-desk1440-observatory-tab.png` (1440×900) | the Observatory tab at desktop width: panel header (97 px) + tab row, then the page in the frame from 157 px: **the double header**. Pill "live", Refresh now shown, the pending line's "Open the Panel to import" button shown (only inside the frame) |
| `panel-desk1440-double-header.png` (1440×323) | the same cropped to the two headers and the page's nav bar |
| `panel-desk1440x2400-observatory-tab.png` (1440×2400) | the same tab in a 2,400 px tall window (the frame fills the window, so a "full page" of the panel is the window; the page scrolls inside the frame) |
| `panel-phone390-observatory-tab.png` (390×844), `panel-phone390-double-header.png` (390×556) | the panel at 390 px: the panel header wraps (pills, buttons and the tab row take 316 px), then the page's own 207 px header: 523 px of headers before the first card. The page's View `<select>` renders with no visible label at this width inside the frame |
| `panel-desk1440-tab-to-process.png`, `panel-phone390-tab-to-process.png` | the To process tab in its test-mode state (shot before the real Refresh): "The To-process list hasn't been worked out on this computer yet…", "Folders still to process 0 · 0.0 h", "The archive isn't reachable at …/testroot-panel/archive-mount", the Find a target box, and the empty Archive pane on the right. Not Brett's lists: those need a ledger / `projects.json` |
| `panel-desk1440-tab-dashboard.png` | the Dashboard tab: "Nothing has been imported on this Mac yet, and the PC's record isn't on the archive. Once either computer has imported and shipped, the dashboard shows here…" (no ledger in the test root) |
| `panel-desk1440-tab-panel.png`, `panel-phone390-tab-panel.png`, `panel-desk1440-tab-report.png` | the Panel and Report tabs for context (no camera, idle, nothing imported) |

## Commands used

```
# standalone page: the engine imported in test mode, dataset → tools/rendered.html (684 KB)
python3 tools/render.py                    # engine 1.7.6, TEST_ROOT = before/testroot-render
NODE_PATH=/opt/node22/lib/node_modules node tools/shoot_standalone.js   # all desk1440-* and phone390-* shots + measurements-standalone.json
NODE_PATH=/opt/node22/lib/node_modules node tools/probe_height.js       # the settle check for the heights

# the real panel in test mode (make_env root = before/testroot-panel; record + scan summary planted in <root>/state;
# the page template copied into the root and named by ASTRO_OBSERVATORY_TEMPLATE, as test_app.py does at line 1693)
python3 tools/launch_panel.py             # prints PORT=48229 PID=4546 ROOT=…  (saved in tools/panel.env)
NODE_PATH=/opt/node22/lib/node_modules node tools/shoot_panel.js        # all panel-* shots + measurements-panel.json; kills the panel at the end
```

Playwright 1.56.1 (`/opt/node22/lib/node_modules/playwright`, found by NODE_PATH; `require('playwright')` fails from a bare
shell without it), bundled Chromium 1194, no `playwright install`. Contexts: `deviceScaleFactor 1`, `colorScheme dark`,
`reducedMotion reduce`, `timezoneId Europe/London`, and `data-motion="reduce"` set on the root at DOMContentLoaded so the
reveal/tween animations never run. The ux2 `shoot_file.sh` / ux3 `shoot_phone.sh` Chrome CLI scripts were not needed (Playwright
gives a real 390 px viewport and frames); `tools/render.py` is the ux3 `render.py` with the test-mode environment added.

## Not captured, and why

- **A long-running "rebuilding…" in the real panel.** The real Refresh rebuilds from the test root's empty ledger in under a second,
  so only the 0.3 s shot catches the pill; the forced `setLive("rebuilding")` shots stand in. A ledger big enough to take minutes
  would have to be fabricated inside the test root; not done.
- **To process and Dashboard with Brett's real lists.** They need a ledger / `projects.json` built by the engine; the planted
  Observatory record does not feed them. They are shot in their empty test-mode state only.
- **A genuinely stale pill wording.** 1.7.6 keeps the word "live" when the record is over a day old (the age is in the sentence),
  so stale and fresh look the same apart from "6 d old"; both are on record.
- **The 390 px panel's other tabs beyond To process** (Dashboard, Report): not asked for; desktop only.
- **A phone-width `/observatory`-alone and `?json=1`**: desktop only (the content is the same).
- **The panel's note when the page template is missing** was seen in passing ("The Observatory page (astro-observatory.html) isn't
  beside the engine … Please run the installer again", HTTP 500) before the template was copied into the root; not screenshotted.
- Hover tooltips (the value-first chart tips, the pill titles) are not in any shot; titles are quoted in `measurements-panel.json`
  where they were read.
