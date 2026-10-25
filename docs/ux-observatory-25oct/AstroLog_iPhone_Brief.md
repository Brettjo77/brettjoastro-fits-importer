# AstroLog iPhone brief: the dashboard on the phone

Version 1, 25 October 2026
For: Claude Code, working in the AstroLog repo
Owner: Brett
Companion: Observatory_UX_Plan.md, the PC side, in the importer repo. This brief carries what applies only to the phone.
Built from, in priority order: Brett's walkthrough of 25 Oct ("Observatory UX Redesign: User Walkthrough Requirements"); Claude's and ChatGPT's dashboard research (both 23 Oct); the Observatory decisions of 23 Oct.

## 1. Goal

On the iPhone, away from the PC, Brett sees what each scope is doing and what's ready to process, using the same three layers as the Observatory: scope first, then project, then detail. Each of these takes under 10 seconds:

1. What is each scope doing?
2. What should I process next?
3. How many hours of M 31 do I have, and on which scopes?
4. What did I capture this month that isn't processed?
5. Is anything only on the Mac or still on a camera?

The phone uses the same words, order and colours as the Observatory.

## 2. Ground rules

1. Fit AstroLog's own plan. Read its CLAUDE.md, DECISIONS.md, spec-v2 folder and build order first. This brief adds screens; it doesn't undo decisions already made.
2. One writer per fact. The phone shows what the Observatory works out (states, order, goals). It never works out states itself and never sets goals.
3. Nothing here writes to the archive.
4. Nothing lost: whatever the Observatory export carries stays reachable within a few taps.
5. Explain each step to Brett in plain words, one at a time. Ask before anything irreversible and before any push.

## 3. Before writing code

1. Find out which AstroLog is on Brett's iPhone today: the native SwiftUI app, or the web app at astrolog.brettjoastro.co.uk. Widgets and Live Activities (section 7) need the native app.
2. Find where AstroLog works out its own statuses and goals today (for example captured, stacked, processed, complete, and its goal hours), and propose how they defer to the Observatory's export, so there is one writer for each.
3. Find where the three layers fit in AstroLog's tabs and build order.
4. Propose how the Observatory's export and its pictures (Observatory plan, Phase 5) reach the phone, for example a Supabase table loaded after each rebuild, or a file, and who carries them.
5. Stop for Brett's go-ahead.

## 4. Layer 1: Home

- **A one-line status at the top, always there**, matching the Observatory's: quiet "Everything's safe · records up to {night} · {age} old" when all is well; amber when data is at risk (frames only on the Mac, files still waiting on a camera, or the Mac's copy over 24 hours old); amber "Couldn't check" when the safety facts are missing. Data kept on the phone always shows its age and is never presented as current.
- **One colour-coded card per active scope**, in the same fixed order as the Observatory: the ZWO camera (saying whether it's on the FRA400 or the 107PHQ), the S50 Pro, the S30 Pro. Idle scopes sit in one collapsed Resting row.
- **Each card:** scope name, tag and colour; the current object, integration so far and nights (a second project smaller beneath, when there is one); a small 30-night activity strip in the scope's colour; one next action in words; a quiet count of what else is waiting on that scope.
- **Under the cards:** one line, "Ready to process: {n} datasets · {hours} ›". Then Recent nights as a compact strip that expands, and one quiet line: "This month: {n} projects moved forward · {n} finished".
- **One tap away:** Ready to process across all scopes (a strip with the count and hours per stage at the top, then summary rows, newest ready first, the first 3 of each group, then "Show all {n}"), Imaging nights, Find and Filters.
- Primary actions sit in the lower half of the screen, within thumb reach. Keep the controls on Home few.

### States

- Loading: show the last data with its age while new data arrives.
- Empty: say what's true ("Nothing captured in 30 nights. Last out: {date}").
- Offline: keep showing the last data, its age, and that it's offline.
- Couldn't load the export: say so, show the last good data and its age, and offer to try again.
- Back after hours: refresh on return and say when it last updated.

## 5. Layers 2 and 3: a scope's projects, then project detail

- **Tap a scope:** the one or two projects it has on the go, newest first, each with object, hours, nights, progress (a ring against the goal from the export, with the hours written beside it), last night captured and its labelled picture ("Seestar's own stack, not processed" or "Your final"; a calm placeholder in the scope's colour when there's no picture). Then the scope's other datasets in short rows: Ready to process, Finish it, Done, then a closed Parked group. Then the scope's Imaging nights calendar, and a note when other scopes hold data on the same object.
- **Tap a project:** a short summary first (state, reason, next step, hours, nights, first and last imaged). One tap further: integration by filter (donut), hours per night (bars), frames, calibration and processing status, and other scopes' data with how much is on disk. Anchored to the scope Brett came from, with a way back.
- Charts follow Brett's rules: donuts and rings for a share of a whole; bars to compare; calendars for activity; a small ring or bar against a goal. A small static chart can open a full interactive one (Apple's Swift Charts guidance).
- Transitions between layers animate smoothly and briefly, and are instant with Reduce Motion on.
- Pictures are kept on the phone with a size limit, oldest dropped first.

## 6. Ordering and filters

- Most recent capture first for lists. Ready items go newest ready first, ties broken by hours. Scope cards keep their fixed order.
- Filters (scope, filter, status, date) sit behind one control.

## 7. Widgets, Live Activities and notifications (native app only)

- **Widgets** show one fact, and tapping one opens that scope's or dataset's page (a deep link). No app-like layouts.
  - Small, one per scope (Brett picks the scope): "{scope} · {object} · {hours}".
  - Medium: the top 3 of Ready to process.
  - Lock Screen, inline: "{n} ready · {hours}".
  - Widgets refresh on the system's schedule, not live, so each one shows when its data was built.
- **Live Activities** only for jobs with a clear end, such as an import or a ship from the Mac, or a stacking run, once the importer can signal them. Not a whole night of imaging, and nothing sensitive on the Lock Screen. Check Apple's current Live Activities guidance on developer.apple.com before building: the research couldn't read that page first-hand.
- **Background refresh** is scheduled by iOS, so never promise up-to-the-minute data; show the age instead.
- **Notifications**, if any: opt-in, and only when the status line would turn amber (data at risk). Never "you haven't processed in...".

## 8. Look and accessibility

- Same state words, scope tags, colours and scope order as the Observatory plan (section 9.2). AstroLog is dark only: recheck each scope colour against AstroLog's own dark background, and outline any under 3:1 (the S50's #1A1A1A needs one).
- Calm and colourful: generous spacing, few items per screen, one obvious next action per card.
- Dynamic Type up to the largest sizes without anything clipped; layouts reflow under large text.
- Tap targets at least 44 by 44 pt.
- VoiceOver reads each card in a sensible order, for example "S30 Pro: Tadpoles Nebula, 10.2 hours over 3 nights, still capturing". Charts and rings read their values ("8.2 of 12 hours").
- Respect Reduce Motion and Increase Contrast.
- A red night mode with dimmed brightness, one tap from Home, for use at the scope, with an option to switch on by itself after astronomical dusk. Here it is a must, not an option. Scope identity then rests on tags, not colour.
- No streaks, no red badge on the app icon, no countdowns, and hours ready instead of idle nights.

## 9. Acceptance

- The five questions in section 1, each in under 10 seconds on Brett's iPhone, away from home, in portrait and landscape.
- Home shows the status line and one card per active scope, each readable at a glance, and the ZWO card says which scope the camera is on.
- At the largest text size, Home still reads in order with nothing cut off.
- VoiceOver reads the scope cards and the queue in a sensible order.
- Coming back after hours, and going offline, both behave as section 4's states say.
- Brett uses it for a week or two before widgets and Live Activities are built.
- If built: the widgets show the same as the Observatory.

## 10. Out of scope

- Telescope control and live telemetry: the ASIAIR and Seestar apps do this.
- Viewing FITS files: PixInsight and Siril do this.
- Sky coverage, Footprints, Coverage and Equipment: they stay on the PC for now.
- Setting goals or parking datasets on the phone: those are set on the PC (one writer).
- Sign-in: unchanged by this brief; password managers and paste keep working.
- A web app install (PWA) instead of the native app: native was chosen for widgets.
- Android, for now.

## 11. Sources

- Brett's walkthrough (25 Oct): scope first, three layers, cards, smooth motion, chart rules, recency, cross-scope notes.
- Claude's dashboard research (23 Oct): Apple's iOS design guidance, WidgetKit ("widgets are not mini-apps"), Live Activities, Swift Charts, and the ADHD and colour guidance.
- ChatGPT's telescope dashboard research (23 Oct): Dynamic Type, 44 pt targets, Reduce Motion and Increase Contrast, background refresh limits, offline states, and showing the age of cached data.
