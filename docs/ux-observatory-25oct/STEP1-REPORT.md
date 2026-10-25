# Observatory UX plan v2: step 1 report (25 Oct 2026)

Investigation against importer 1.7.6 (main, commit 23609c7). No code changed. Detailed findings with file:line citations:
- states/findings.md (states, order, finals, dates, config)
- scopes/findings.md (scope, nights, sites, contract)
- panel/findings.md (panel routes, Dashboard/Report, pictures, page look, security, tests)
- before/index.md + 78 PNGs (the "before" screenshots and measurements)

## Suites on 1.7.6
- Engine: 625 passed, 4 failed, 4 skipped of 633. The 4 are the known Linux-only lines (U1 shell-script checks, AP astropy checks that need a real Mac/PC); same as the 1.7.6 baseline run.
- Panel: 192 passed.

## Before screenshots (test mode, the 19 Oct record: 87 targets, 505 sessions, 1,000.7 h)
- Desktop 1440: page 6,355 px; "What to do next" starts at 4,747 px. Plan said 3,550 of 5,108.
- Phone 390: page 11,796 px; "What to do next" at 8,371 px. Plan said 7,694 of 11,479.
- Inside the panel at 390 px: 523 px of headers (panel + page) before the first card.
- Captured: Overview (both themes), the 8 other views (Targets, Coverage, Pipeline, Nights, Sky, Footprints, Equipment, Data checks; there is no Archive tab), scope card both faces, night panel, opened project card, states (loading, empty, no record, stale, importer not answering, rebuilding, warnings, /observatory alone, /observatory?json=1), the panel's Observatory/To process/Dashboard/Report tabs.

## The 13 questions

1. States. final → Done; master → Finish it; capture-state "open" → Still capturing; "complete" → Ready; otherwise 14 CALENDAR days since the last night → Ready, else Still capturing (astro-import.py:11254-11263, QUIET_PERIOD_DAYS :883, days_since :11219). The plan says "14 observing nights": the code counts calendar days. "sample" is a hand flag in capture-state.json; a master or final cancels it. NO writer for capture-state.json exists (no panel endpoint, no CLI). No minimum-integration cut-off. Nothing called parked. Nights newer than a final: stays Done already.
2. Order: six different rules. Page "What to do next": Ready/Finish by hours desc, Still capturing by readyOn asc (html:1904-1906); Pipeline hours desc (:2175); Projects that moved lately lastNight desc within 60 nights (:2002); Targets view hours (:2071); panel To process last session desc (app:2393); scope faces contract order. No "ready since" date stored (readyOn only while capturing; derivable as last night + 15 days).
3. Finals: matched by catalogue code only (not by name or alias), scope from a rig tag in the filename, else the parent folder, else the root; an unscoped picture in the shared Askar root counts only when the target has one dataset there (:10806-10867). Unmatched finals are listed nowhere; a finalsUnmatched[] field is cheap (_scan_finals already returns every picture). On the Mac finals are never checked by default (ASTRO_FINALS_DIR empty). Can't read E: from here: the real list needs Brett's PC.
4. Scope: FOCALLEN 402 → FRA400, 749 → 107PHQ, ±10 mm, from the first new file per target folder (:925, :1897-1902). "Which Askar now": derivable from the newest Askar session, not stated; frames still on the camera carry no scope in pendingImport (the scan computes it, :2723-2731, but doesn't save it). No "camera unit" concept.
5. Last 30 nights: scopes[].last and sessions[] answer it; the page already splits active/resting in three places (Recent nights, the chart strip, lanes). 19 Oct record: 5 active, S50 resting (last out 30 Aug 2025).
6. Collect Lights: not detectable. programmes[].collected is hard-coded False (:11544). Collect Lights leaves a lights/ folder and collect-lights-report.csv; the inventory could spot the csv (small change).
7. Nights/sites: observing_night is a naive noon pivot with no timezone (:1167-1171). ASIAir nights come from the file-name clock (the camera's local time), Seestar nights from DATE-OBS (UTC): two clocks already. Sites exist only in scopes.json; Tenerife and Starfront entries are switched off (unit: null) because no frame carries a unit identity, and a test asserts their frames are Shinfield. Nothing follows a site's evening; site-evening dating needs an identity per frame or a site tag at import.
8. /observatory "forbidden": not the typed URL (a bookmarked http://127.0.0.1:8765/observatory renders, with a "← Importer" link). The 403 comes when the link is clicked from another web page (cross-site Sec-Fetch, app:1155-1162, added 1.7.1) or when the Host is the machine's name instead of 127.0.0.1. Safe own-tab: a landing route, or take the HTML route (never ?json=1) out of COSTLY_GET. Bind/Host/Origin/token stay.
9. Last scan memory: last-scan.json {files, targets, elsewhere, camera, failedEject, seenAt, machine, targetNames[≤12], elsewhereMachine} (:10045-10062), written by the panel after a camera scan; shown as the amber "N files still on the ASIAir" chip and a line in Recent nights. No scope, no per-file list.
10. Dashboard/Report vs Observatory: Dashboard = pre-built state/dashboard.html (tiles, Space on this computer, camera storage, frames per month, integration by rig, Targets table, Recent activity, both ledgers merged). Report = plain-text SAFE/UNVERIFIED/NOT SAFE/NEVER-IMPORT/calibration/discards/events. The Observatory already has month rhythm, by-rig share, targets table, provenance, unknown names. Proposal: Space + calibration-library count → Data checks; SAFE verdicts, discards, events, Recent activity → rename Dashboard to Ledger; camera storage → drop (the panel header shows it). Exception to note: /api/archive/siril launches Siril (the one non-open action).
11. Pictures: Seestar keeper Stacked_N FIT + JPG are copied into the project folder (no stacks\ folder); masters and finals reach the record as NAMES only (mastersNamed/finalsNamed; no path or size); the panel has never served image bytes (JSON and HTML only). An image route would reuse archive_resolve + the image allow-list + nosniff and sit in COSTLY_GET. Sizes unknown.
12. scopes.json: six scopes (S30P yellow, S30 blue, S50 black → #0a0a0a invisible on dark, S50P null → grey, FRA400 red, 107PHQ green) + two site entries switched off; order honoured everywhere; no short tags. The page has no palette of its own. The plan's Okabe-Ito set goes into scopes.json (one source).
13. "Imaging nights": the Nights tab's literal heading. A calendar heatmap, one SVG per year, all scopes summed with scope chips to filter, five blue bins; nights with no frames are the plain card surface, never red. "What each scope captured" is the per-scope bar chart with the moon row. Confirm which one Brett means.

## Where the plan and the code disagree (to settle before Phase 1)
A. Versions: main is 1.7.6 since 24 Oct (the plan says the GitHub copy is 1.6.0).
B. Phone route: already built. The native AstroLog iOS app has an Observatory screen (23 Oct) reading observatory.json through the app's iCloud container, written by the importer 1.7.6. Phase 5 and iPhone brief §3.1/§3.4 are answered; what's missing is pictures (small copies) and goals.
C. Read-only (ground rule 1) vs Brett's 24 Oct yes to the Observatory changing records (toggles #9, filter tag #8). The plan's Park, goals, open/complete all need the same thing: ONE panel endpoint that writes hand-set facts (capture-state.json has no writer today). Plan §13 rejects a hand "processed" mark (states come from files); issue #9's "processed" toggle conflicts.
D. Quiet period: 14 calendar days in code vs "14 observing nights" in the plan.
E. Sites (§6.4): impossible without a per-frame identity; defer or record a site at import.
F. Order decision §6.3 supersedes the two open 13 Oct decisions.
G. The calibration work (#4) feeds Layer 3 and the "darks or flats missing" next action; #8 becomes part of Phases 2-3.
H. The stress dataset predates 1.7.2; design against the 19 Oct record or, better, Brett's current one.
