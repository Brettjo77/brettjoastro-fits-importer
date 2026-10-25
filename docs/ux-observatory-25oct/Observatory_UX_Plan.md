# Observatory UX plan

Version 2, 25 October 2026 (version 1: 23 October)
For: Claude Code, working in the BrettjoAstro FITS Importer repo on the PC
Owner: Brett
Built from, in priority order:
1. Brett's walkthrough of 25 Oct ("Observatory UX Redesign: User Walkthrough Requirements"). Where it differs from the research, it wins.
2. Claude's and ChatGPT's dashboard research (both 23 Oct).
3. The Observatory audits (16 and 23 Oct) and the Project Layer Spec (10 Oct).

On 25 Oct every point in those was checked against this plan, then checked again by a separate reviewer. Anything weighed and left out is in section 13, with the reason.
Companion: AstroLog_iPhone_Brief.md covers the phone app, in its own repo.

## 1. Goal

Rebuild the Observatory around the telescope: scope first, then project, then detail. The first screen answers "what is each scope doing, and what's ready?" at a glance, on the desktop and at phone width, without making Brett feel behind.

Everything available today stays reachable within a few taps.

## 2. What's wrong today (audit 23 Oct, walkthrough 25 Oct)

- **The top third is wasted.** On arrival it shows archive totals Brett isn't interested in, so the first screen does no useful work.
- **The organising idea is wrong.** The page is built around archive-wide summaries, but Brett thinks per telescope. His real route today: skim Recent nights, scroll past everything to the per-scope captures, then navigate from there.
- **Detail arrives all at once.** Counts, lists and breakdowns show on load, and opening a Ready to process item (for example Flaming Star) is a dense block.
- **The queue is buried.** "What to do next" is the sixth of seven Overview sections. In the panel's desktop frame it starts 3,550 px into a 5,108 px page (screen 4). At 390 px wide it starts 7,694 px into 11,479 px (screen 10 of 14).
- **The numbers overstate the backlog.** Ready to process holds 89 datasets (761.3 h), Finish it 50 (507.4 h), Still capturing 6 (38.5 h) and Done 1 (27.3 h), out of 146.
  - Finished work isn't matched. Black Eye Galaxy (M 64) on the S50, and Beehive Cluster (M 44) and Bode's Galaxy (M 81) on the FRA400, were finished by August but show as Finish it.
  - Test snaps sit in the queue: Hercules (NGC 6229) at 3 min, Betelgeuse at 0.1 h, Surfboard Galaxy (M 108) at 0.2 h, and Open cluster M 39 on the S30 at 0.4 h.
- **Three lists disagree.** The panel's To process tab sorts by most recently quiet. The Overview and the Pipeline board sort biggest first.
- **"live" reads as fresh data** but means the importer is answering. The same header says the page was built 12 h earlier from the Mac's record of 19 Oct.
- **A phone can't reach the page.** The panel binds to 127.0.0.1 and checks the Host header. That is right and stays.
- **Opening the Observatory on its own shows an error.** Going straight to /observatory in a browser tab returns raw JSON, {"error": "forbidden"}. It only works inside the panel's frame, so there is no full-width view. It did open on its own on 16 Oct.
- **Two dashboards.** The panel has a Dashboard tab (a status page built from the ledger) beside the Observatory tab, and both show hours per target.
- **Words and colour add load.** Cards say "nothing new for 322 nights". The S50's black vanishes on the navy header. FRA400 red sits beside 107PHQ green in stacked bars.

## 3. Ground rules

1. The Observatory stays read-only. Nothing on the archive is written, moved or deleted by it.
2. The panel stays local: 127.0.0.1 only, Host and Origin checks, the per-launch token. Don't open it to the network.
3. Follow the repo's CLAUDE.md: test mode always, both suites green, Mac and Windows in step, PARITY.md updated with any platform detail, CHANGELOG and VERSION bumped, every fix with a test that fails without it, no push without Brett's yes.
4. Keep the Observatory's own look: IBM Plex Sans and Mono, its cards and chips. Professional, colourful and calm. No stock UI-kit look.
5. No changes to the ledger, the archive layout, or the import, ship and clear behaviour. The archive's folder names and Day numbering always win.
6. No new dependencies or chart libraries without Brett's yes. The Observatory's charts are hand-built SVG in one generated page. Keep them that way.
7. Nothing lost. Every piece of data reachable today stays reachable within a few taps. Progressive disclosure hides detail; it never removes it.
8. One writer per fact. Anything Brett sets by hand (open, complete, parked, goals) has one home, and everything else reads it.
9. Explain each step to Brett in plain words, one step at a time.

## 4. Before writing code

1. Read CLAUDE.md and PARITY.md.
2. Find the code that builds the Observatory and the panel's To process list. The public GitHub copy is behind (1.6.0), so work from the local 1.7.x checkout. Strings that locate it: "What to do next", "Projects that moved lately", "Needs your attention", "a finished picture names the target and the scope", "nothing new for", "obsFrame", "The importer is answering".
3. Run both suites and note the counts.
4. Take a "before" set of screenshots of every current Observatory view at 390 px wide and in the panel's desktop frame, plus its loading, empty and error states where they can be shown safely in test mode. They are the record of what must stay reachable.
5. Report back in plain words:
   - how each state (Still capturing, Ready to process, Finish it, Done) is worked out;
   - where each list's order comes from;
   - which files in E:\Final Astro Images match no dataset, and why each one misses;
   - how an ASIAir frame's scope is known (focal length), and whether the newest frames can say which Askar the camera is on now;
   - which scopes had frames in the last 30 nights;
   - whether the Observatory can tell when Collect Lights has gathered a dataset's lights (a collected lights folder);
   - how a night's date is set for each site (Shinfield, Tenerife, and Starfront in Texas), and whether it follows the site's own evening (section 6.4);
   - why opening /observatory on its own returns "forbidden";
   - what the panel remembers from its last camera scan: files on a camera not yet imported, and when it last looked;
   - what the panel's Dashboard and Report tabs show that the Observatory doesn't, with a proposal for one dashboard (for example, the ledger figures move into Data checks and the Dashboard tab goes, or it is renamed Ledger);
   - which pictures exist for each dataset: the Seestar's own stacked JPEGs in stacks\, Brett's finals, and their sizes;
   - whether the toolchain's shared scope table (scopes.json) exists, and what it holds;
   - which view Brett calls "Imaging nights" (the Nights tab, or the What each scope captured lanes), and whether it colours nights with no frames. Confirm with Brett before changing either.
6. Stop for Brett's go-ahead.

## 5. Decisions

Agreed by Brett:

| Decision | Agreed | Not chosen |
| --- | --- | --- |
| Organising idea (25 Oct) | Scope first, then project, then detail | One Next up card for the whole archive |
| Default order for lists (25 Oct) | Most recent capture first; ready items newest ready first, ties broken by hours (23 Oct) | Biggest first; A to Z |
| Charts (25 Oct) | Each chart matches its data; donuts and rings for a share of a whole (section 9.3) | Bars only |
| Sample cut-off (23 Oct) | Under 30 minutes of integration | Another time, or a frame count |
| Scope colours (23 Oct) | Colour-blind safe versions of Brett's hues (section 9.2) | Current palette with labels only |
| Phone route (23 Oct) | AstroLog on the iPhone, fed by an export from this build (section 10) | A read-only Observatory snapshot |

The existing quiet-period rule stays: a dataset is Still capturing until 14 observing nights pass with no new frames, or Brett closes it.

Proposed, for Brett to confirm. Build these unless he says otherwise:

| Question | Proposed | Why |
| --- | --- | --- |
| Which scopes get a card | Scopes with frames in the last 30 nights. Idle scopes collapse into one Resting row. The rented Tenerife S30 Pro gets its own card when active, labelled with its site. | Active first, idle collapsed (walkthrough's suggestion) |
| Card order | Fixed, in the order Brett lists his rig: the ZWO camera, the S50 Pro, the S30 Pro, then any other active scope. Cards don't reshuffle from day to day. | Stable layouts let you know where to look |
| How the ZWO card knows its scope | From the newest ASIAir frames' focal length, which the Observatory already reads. No manual setting. After a quiet spell: "last on the FRA400". | One writer per fact |
| Goals for progress rings | A goal per project, default 12 h (AstroLog's default). One writer: set from the panel and kept beside open and complete in capture-state.json, then exported to AstroLog, which shows it read-only. Until a project has a goal, it shows hours and nights without a ring. Ask Brett before building the write. | A ring needs a goal; one hand-set file keeps one writer |
| Where today's header totals go | A secondary Archive tab, unchanged | Nothing lost |
| Finished, then new frames | Stays Done, with a "new frames since" note | A new final is Brett's call, not the page's |

## 6. Phase 1: honest numbers

Data first, display second.

### 6.1 Match finished pictures (Done)

- Match each final in E:\Final Astro Images to a dataset (one object on one scope):
  - object: through the shared target name table, accepting any known alias ("M64", "M 64", "Black Eye");
  - scope: from the per-scope folder the final sits in, or from its name;
  - a folder or name that covers both Askars: list it once in Data checks, answered through the panel's existing "Say which Askar" action, instead of leaving the dataset silently unfinished.
- A dataset with a matched final is Done. If it has nights newer than the final, it stays Done with a "new frames since" note (section 5, proposed).
- If E:\Final Astro Images can't be read during a rebuild, keep each dataset's last known state and say so (7.6). Never let Done datasets slip back because a folder was briefly unreachable.
- **Done when:** the rebuild reports how many datasets moved to Done; Black Eye (S50), Beehive (FRA400) and Bode's (FRA400) show Done, or Data checks names the exact file that's missing; engine tests cover an alias name, a scope folder, a shared Askar folder, a final older than the newest night, and an unreadable finals folder.

### 6.2 Samples out of the queue

- A dataset under 30 minutes of integration gets the state Sample. It sits outside every count and queue, listed only in a closed Samples group in the Pipeline and Projects views.
- **Done when:** NGC 6229 (3 min), Betelgeuse (0.1 h), Surfboard (0.2 h) and M 39 on the S30 (0.4 h) leave the queue; tests at 29 and 31 minutes.

### 6.3 One state and one order for every list

- One function decides state and order for every list: the scope cards and scope layers, Ready to process, the Pipeline board and the panel's To process tab, with the same counts everywhere.
- Order: most recent capture first. Ready items go newest ready first, by the date a dataset became ready (its quiet period ended, or Brett closed it); ties broken by hours.
- Each item carries its reason in words: "ready since {date} · {hours} on the {scope}".
- **Done when:** the To process tab, the Pipeline board and Ready to process show the same first five datasets in the same order, and a test proves it.

### 6.4 Nights dated by the site's own evening

- A night runs noon to noon in the site's local time and takes the date of its evening:
  - Shinfield: Europe/London;
  - Tenerife: Atlantic/Canary, from the site tag in the night folder name (for example "2026-09-10 Tenerife");
  - Starfront: America/Chicago.
- This is about how the Observatory dates and groups nights. Never rename archive folders; if the archive's Day labels disagree, report it.
- **Done when:** a test shows a Starfront session that starts at 21:00 Texas time (02:00 or 03:00 in the UK) lands on its Texas evening, and night dates don't depend on the PC's own clock or time zone.

### 6.5 The rules live in config

- The quiet period (14 observing nights), the sample cut-off (30 minutes) and the "active scope" window (30 nights) live in config.json with those defaults, so Brett can change them without a code change.
- **Done when:** changing any of them and pressing Refresh now changes the result, and a test covers each.

### 6.6 Leftovers from 16 October

- List the 2 target names the importer doesn't recognise (184 frames) for Brett. Add no names without his yes.
- Check whether the "Dark nebula LDN 386" frames were folded into "Eagle Nebula (M 16)". The ship log of 16 Oct wrote a folder called "Eagle Nebula (LDN 386)". Report it; change nothing without Brett's yes.
- Use the target table's type labels everywhere ("Emission nebula", not a mix with "Nebula").
- Fill the missing type and constellation for Middle Heart (LDN 1373), Fish on a Platter (B 144) and the Squid, with Brett's yes.

**Stop after Phase 1** and show Brett the counts before and after: Still capturing, Ready to process, Finish it, Done and Samples.

## 7. Phase 2: scope first

Three layers, each reached by tapping a card in the one above. Detail is always available, never imposed.

### 7.1 Layer 1: the landing screen

- **A one-line status at the top, always there.** In quiet text when all is well: "Everything's safe · records up to {night}". In amber when data is at risk: frames only on the Mac, files still waiting on a camera at its last scan ("{n} files waiting on the {camera}, last scan {date}"), or the Mac's copy over 24 hours old. In amber too if the safety facts couldn't be read: "Couldn't check data safety: {reason}". One line only; the rest of today's header moves to the Archive tab.
- **One colour-coded card per active scope**, in a fixed order (section 5): today the ZWO camera, the S50 Pro and the S30 Pro. Idle scopes sit in one collapsed Resting row.
- **Each scope card:**
  - scope name, tag and colour. The ZWO card says which scope the camera is on: "ZWO · on the FRA400";
  - the current project: object, integration so far, nights. One active project is the normal case; a second shows smaller beneath it;
  - a small activity strip of the last 30 nights in the scope's colour, the Imaging nights pattern;
  - one next action in words: the first unfinished step for the current project. For example "Still capturing · ready from 24 Oct", "Next step: collect the lights (3 nights, 650 frames)", then "Next step: stack the collected lights", then "Finish it · master saved 9 Oct". Where darks or flats are missing, it says so first;
  - a quiet count of what else is waiting on that scope: "{n} more ready to process";
  - when a dataset on that scope reaches Done, the card shows it with its picture until the scope's next night out.
- **Under the cards:** one line, "Ready to process: {n} datasets · {hours} ›", which opens the all-scopes list (8.5). Then Recent nights as a compact strip, newest first, that expands into the full list. Then one quiet line: "This month: {n} projects moved forward · {n} finished" (8.2).
- **One step away, not on this screen:** an Explore menu with Ready to process (all scopes), Imaging nights, Sky coverage, Footprints, Coverage, Equipment, Data checks (with its count, never red) and Archive. Find and a Filter control sit in the header. The build time, in UK time, and the "live" server dot sit in the footer.
- **Where today's Overview goes:** Recent nights becomes the strip; What each scope captured and What each scope shot feed the scope cards and stay as full views in Explore; Projects that moved lately folds into each scope's layer; Where the hours went moves to the Archive tab; Needs your attention becomes the status line plus Data checks.

### 7.2 Layer 2: a scope's projects (tap a scope card)

- The one or two projects this scope has on the go, newest first. Each shows object, hours, nights, progress (a ring against its goal once goals exist, otherwise hours and nights), last night captured and its picture (8.1).
- Then this scope's other datasets in short rows, most recent capture first: Ready to process, Finish it, Done, then Parked (8.3). Each group shows its first 3, then "Show all {n}" as a quiet count, never red.
- This scope's Imaging nights calendar.
- A note when other scopes already hold data on the same object: "Also on disk: 59.9 h on the S30 and 20.0 h on the ZWO rig".
- Filters (filter, status, date) sit behind one Filter control, not across the top.

### 7.3 Layer 3: project detail (tap a project)

- Anchored to the scope Brett came from, with a way back: "S30 Pro › Andromeda Galaxy". Opened from Find, Sky coverage or Ready to process, it anchors to the scope with the most recent capture and offers the others as chips.
- **A short summary first:** state, reason and next step; hours, nights, first and last imaged; the picture.
- **One tap further:**
  - integration by filter (donut) and hours per night (bars);
  - frames, calibration sets and processing status;
  - a sessions table: night, site, frames, hours, filter;
  - data from other scopes on this object: hours, nights and size on disk per scope;
  - file paths and frame details. Long frame lists load in pages (for example 200 at a time), never thousands of rows at once.
- **A direct route to the files:** "Open files" goes to the panel's Archive view for this target and scope (Open folder, Start Siril here, Copy path). The link changes the top window or asks the panel to switch tabs; it never loads inside the Observatory frame.

### 7.4 Cards and motion

- Cards are the main unit on every layer. Detail opens under a card or as the next layer, not in a pane beside it.
- Expanding a card and moving between layers animates smoothly and briefly (about 200 to 300 ms), so it is always clear where you came from and where you are. No decorative motion. With reduced motion set, changes are instant.
- Low load on arrival: few items per screen, generous spacing, one obvious next action per card.

### 7.5 Layout

```
PHONE, 390 px                       DESKTOP, panel frame
+============================+      +==================================================================+
| Everything's safe . Fri 16 |      | Everything's safe . records up to Fri 16 Oct                   |
+============================+      +====================+====================+====================+
| ZWO . on FRA400            |      | ZWO . on FRA400    | S50 Pro            | S30 Pro            |
| Flaming Star               |      | Flaming Star       | Tadpoles           | Tadpoles           |
| 33.0 h . 6 nights          |      | 33.0 h . 6 nights  | 11.3 h . 2 nights  | 10.2 h . 3 nights  |
| [30-night strip]           |      | [30-night strip]   | [30-night strip]   | [30-night strip]   |
| Finish it . master saved   |      | Finish it . master | Still capturing    | Still capturing    |
| {n} more ready             |      | {n} more ready     | {n} more ready     | {n} more ready     |
+============================+      +====================+====================+====================+
| S50 Pro                    |      | Resting: S30 . S50                                          (+) |
| ...                        |      | Ready to process: {n} datasets . {hours}                     > |
+============================+      | Recent nights: {night} . {night} . {night} ...             (+) |
| S30 Pro                    |      | This month: {n} moved forward . {n} finished                   |
| ...                        |      +==================================================================+
+============================+      | footer: built 09:30 UK time . server dot                       |
| Resting: S30 . S50     (+) |      +==================================================================+
| Ready to process        >  |
| Recent nights          (+) |
+============================+
```

The objects, hours and nights in the sketch are from the 23 Oct page, as examples only; the build fills them from the records.

- Desktop: scope cards three across. 820 px: two across. Phone: one column in the same order.
- Breakpoints: one column under 600 px, two from 600 px, three from 840 px. They follow the width the page actually has inside the panel's frame, not the browser window; use container queries where a card needs them. Check at 390 px (iPhone), 820 px (iPad portrait) and the panel's desktop frame.
- A Find box in the header opens a project's detail, so "how many hours of M 31, on which scopes" takes one step.
- The page remembers its last view and filter in this browser.

### 7.6 States for every new block

Every state says what happened and what to do next.

- Loading: keep the existing "Working it out" note. Cards keep their space while loading, so nothing jumps.
- Empty: say what's true and what comes next ("Nothing captured in 30 nights. Last out: {date}").
- Nothing found: Find or a filter with no results says so and offers to clear it.
- Stale or at risk: the amber status line.
- Couldn't check: the amber "Couldn't check data safety" line.
- Rebuild failed: keep the last good build on screen, say the rebuild failed and when, and how to try again.
- Partly unavailable: if the archive or E:\Final Astro Images can't be read, say which, and keep the last known states rather than changing them.
- Importer not answering: "The importer isn't answering. Showing the build from {time}."
- Panel restarted: the page reloads itself rather than failing on an old token.
- Refreshing: Refresh now shows it is working, can't be pressed twice, and the page says when the rebuild finished.
- Back after hours: the page refreshes on return and says when it last updated.
- Opened on its own: /observatory in its own tab shows a plain page with a link back to the panel, or the full page if section 4 finds that safe. Never raw JSON.

### 7.7 Done when

From Brett's walkthrough:
- The first screen shows one card per active scope and nothing that needs scrolling to understand.
- Each scope card states the current object, integration so far and nights, readable at a glance.
- The ZWO card shows which scope (FRA400 or 107PHQ) the camera is on.
- Tapping a scope opens its project layer; tapping a project opens its detail; files on disk are reachable from there.
- Every list sorts newest first by default.
- A project shows prior data from other scopes when it exists.
- Imaging nights, Sky coverage and Footprints remain available, below or behind the scope layer.
- All transitions animate smoothly on desktop and phone.
- Every chart type matches its data (section 9.3).
- No data reachable today becomes unreachable: Code maps every view in the "before" screenshots (section 4) to its new home.

Also:
- The landing screen draws in under a second on the PC.
- At 390 by 844 px the status line and three scope cards fit on the first screen; at 820 px the order holds and nothing overlaps; phone landscape (844 by 390) still reads in order.
- The card order is the same from day to day.
- With reduced motion set, transitions are instant.
- Each state in 7.6 is shown at least once in test mode.
- Panel tests check the three layers and their order in the generated page.
- The questions in section 11 pass.

**Stop** and send Brett screenshots at all three sizes. Brett then uses it for a week or two and sends a voice note. His notes come before Phase 3.

## 8. Phase 3: pictures, progress and the other views

### 8.1 Pictures

- Show a picture on each project in Layer 2 and at the top of Layer 3: Brett's final when the dataset is Done, otherwise the scope's own stacked JPEG from stacks\.
- ASIAIR datasets have no automatic stack. Show the final if there is one, otherwise a calm placeholder in the scope's colour with the object's name.
- Label every picture: "Seestar's own stack, not processed" or "Your final, {date}", so an automatic stretch is never mistaken for finished work.
- Serve it read-only through the panel with the Archive tab's path rules: only image files inside the archive or Final Astro Images, never a full FITS.
- Ask Brett before adding an image library for small copies. If none is installed, show the existing JPEG scaled by the browser.
- **Done when:** the pictures on a scope's layer load in under a second on the PC, and a test proves that a path outside the archive is refused.

### 8.2 Progress without guilt

- The "This month" line under the cards (7.1) comes from dates the records already hold: when a dataset became ready, when a master was saved, when a final appeared.
- Opening it lists them, the finished ones with their picture.
- A finished dataset gets a calm moment on its scope card (7.1). No fanfare, no streaks, no "days since", no red counts.

### 8.3 Park (ask Brett first)

- "Park" takes a dataset out of the queue without deleting anything. It goes into a closed Parked group and can be undone at any time. Brett can also park until a date, after which it comes back by itself.
- It would be a third hand-set value in capture-state.json, beside open and complete, set from the panel with its token. Build it only after Brett says yes.

### 8.4 Goals (ask Brett first)

- As proposed in section 5: a goal per project, default 12 h, kept in capture-state.json and set from the panel. Rings then show hours against the goal on Layer 2. The export (section 10) carries goals to AstroLog, which shows them but doesn't set them. Build it only after Brett says yes.

### 8.5 The Explore views

- **Ready to process, all scopes:** a strip at the top with the count and hours per stage (Still capturing, Ready to process, Finish it, Done), each opening that group. One line says the rule: "Ready: nothing new for 14 observing nights, or closed by you. Samples under 30 minutes are set aside." Then summary rows (object, scope tag, hours, ready since), newest ready first, each group showing its first 3, then "Show all {n}". Frames, filters and files open on a further tap.
- **Imaging nights:** keep it as it is, with the safe scope colours. If it colours nights with no frames red, make them neutral, with Brett's yes.
- **Sky coverage:** map first; the detail list stays collapsed until a target is picked. Each footprint is sized or labelled by its hours, and clicking one opens that project's detail. Zoom and pan work by buttons and keyboard as well as by dragging.
- **Footprints:** keep, in a secondary position.
- **Projects (today's Targets):** most recent capture first by default, also sortable by hours, name or state; "Show all" brings in Done, Parked and Samples; filters behind one control.
- **Archive:** today's header totals and Where the hours went, unchanged.

**Stop after Phase 3.**

## 9. Phase 4: words, colour, charts, accessibility

### 9.1 Words

- Count hours ready, not idle nights: "59.9 h ready since Dec 2025" replaces "nothing new for 322 nights".
- Keep the four state words exactly: Still capturing, Ready to process, Finish it, Done. They always appear as text beside any colour or icon.
- "Project" means one object across all scopes; "dataset" means one object on one scope.
- One format for durations: minutes under an hour ("45 min"), hours with one decimal from an hour up ("3.2 h").
- One format for dates: "Fri 16 Oct", with the year when it isn't this year. Times are UK time and say so.
- Dates, not countdowns: "ready from 24 Oct", never "ready in 3 days".
- Charts label their units, and nights with no frames show as gaps, never joined across.
- Where RA and Dec appear, label them J2000.
- No red badges on counts, and no streaks.

### 9.2 Colour

Brett's hues, moved to the Okabe-Ito colour-blind safe set. Scope colours carry through every layer, so a scope is recognisable by colour from its card to its file list.

Contrast was checked against the light page (#eeeae0, measured 23 Oct) and the August build's dark page (#0b0e15); recheck both against the current themes. Any colour under 3:1 against its ground gets a 1 px outline in the page's edge colour.

| Scope | Colour | Tag | Outline on |
| --- | --- | --- | --- |
| Askar FRA400 (ZWO) | #D55E00 | FRA | none (3.2:1 light, 5.0:1 dark) |
| Askar 107PHQ (ZWO) | #009E73 | 107 | light grounds (2.9:1) |
| Seestar S50 Pro | #CC79A7 | S50P | light grounds (2.6:1) |
| Seestar S30 Pro | #E69F00 | S30P | light grounds (1.9:1) |
| Seestar S30 | #0072B2 | S30 | none (4.3:1 light, 3.7:1 dark) |
| Seestar S50 | #1A1A1A | S50 | dark grounds, including the navy header (1.1:1) |

- Why these, where the research differed: the research suggested yellow #F0E442 for the S30 Pro, but it almost vanishes on the light page (1.1:1), so the S30 Pro takes Okabe-Ito orange #E69F00, the closest to today's amber. The research gave #CC79A7 to the S50; with a sixth scope it goes to the S50 Pro, and the idle S50 keeps Brett's black (also an Okabe-Ito colour) with an outline.
- One scope order everywhere, matching the cards: ZWO (FRA400, 107PHQ), S50 Pro, S30 Pro, S30, S50. Legends, stacked bars, tables and the export all use it.
- Keep the scope colours and tags in the toolchain's shared scope table (scopes.json) if it exists, so the page, the export and AstroLog read one source.
- Every coloured mark has its tag or scope name in view, so colour is never the only cue.
- Keep the 2 px gap between segments in stacked bars and donuts, so FRA400 and 107PHQ never touch.
- State chips: calm, distinct hues that never use red, with green kept for Done only. Amber is kept for data at risk. Each chip shows its word and an icon, so no red and green stoplight forms.
- Every chart keeps a legend or labels on its marks, except the small 30-night strips on cards: they are small static charts, read through the card's scope colour and opened by a tap.
- **Done when:** a script checks each colour against the ground it sits on in both themes and confirms the outline rule, and the S50 shows on the navy header.

### 9.3 The right chart for the job

| Data | Chart |
| --- | --- |
| A share of a whole, such as integration by filter within a project | Donut or ring, a few slices, each labelled with its value |
| A comparison across items or nights, such as hours per night | Bars |
| When a scope was active | Calendar heatmap, as in Imaging nights |
| Integration so far against a goal | A small progress ring or bar, with the hours written beside it ("8.2 of 12 h"), never a large dial |
| Position on the sky | Sky map or scatter with RA and Dec axes labelled (J2000), as in Sky coverage |

- Keep "view as table" on every full-size chart.

### 9.4 Accessibility

- WCAG 2.2 AA as the baseline.
- Primary controls at least 44 px at every width (WCAG's minimum is 24 px; Apple's guidance is 44 pt). The 820 px iPad is a touch screen too.
- Visible focus on every control, and everything reachable by keyboard, including opening and closing cards.
- Nothing important lives only in a hover tooltip. The server dot's meaning and chart values can be reached by tap and keyboard.
- Icon-only buttons, such as the theme button, get a label for screen readers and a tooltip.
- One status chip is used everywhere, with the state word, an icon and the colour.
- The page works at 200% zoom without sideways scrolling.
- Changes that arrive on their own, such as a rebuild finishing, are announced to screen readers.
- Keep the existing reduced-motion and forced-colours handling.
- Always do a manual keyboard and screen-reader pass. If Playwright and axe are available, add an automated check of the landing screen at 390 px and desktop width in both themes too, with no serious or critical violations. Ask before installing anything.

### 9.5 Night mode (optional, last)

- A third theme beside light and dark: deep red on black with dimmed brightness, one tap from the theme button, for use at the scope. Scope identity then rests on tags, not colour.
- It matters most in AstroLog on the phone at the scope, where it is a must (iPhone brief, section 8). Here, on the PC indoors, it is optional.

**Stop after Phase 4.**

## 10. Phase 5: the phone export

- The panel stays local, so the phone gets the same answer through AstroLog.
- In this repo: after each rebuild, write one small JSON file with everything the phone shows:
  - the status line's facts (frames only on the Mac, files waiting on a camera, the Mac copy's age, whether the check worked), plus the export's own build time, so the phone can show its age;
  - per active scope: current project or projects, hours, nights, last night, the 30-night activity strip, the next action, what else is waiting, and for the ZWO the scope it's on; the Resting scopes too;
  - every dataset's summary, in every state and on every scope, including Done, Parked and Samples;
  - Layer 3 essentials for every project, including other scopes' data on the object;
  - the Imaging nights data (hours per scope per night);
  - the count and hours per stage, and Ready to process across all scopes, newest ready first;
  - Recent nights and the "This month" counts;
  - goals, once 8.4 is built;
  - pictures as small copies carried with the export, each with its label. A PC file path is no use to a phone.
- Use the same state words, scope tags, colours and order as the Observatory, so AstroLog matches.
- If the Project Layer Spec's projects.json rollup already exists, extend it rather than adding a second file.
- Propose how the export and its pictures reach AstroLog, and who carries them, then stop. AstroLog_iPhone_Brief.md covers the app side, in its own repo.

## 11. Acceptance: the questions

Each answered in under 10 seconds from opening the Observatory, in the desktop frame, at 820 px and at 390 px:

1. What is each scope doing? (the scope cards)
2. What should I process next? (each card's next action, then Ready to process)
3. How many hours of M 31 do I have, and on which scopes? (Find, then the detail's other-scopes section)
4. What did I capture this month that isn't processed? (the Recent nights strip, or Ready to process filtered to this month across Still capturing, Ready to process and Finish it)
5. Is anything only on the Mac or still on a camera? (the status line, always there)

## 12. Out of scope here

- AstroLog on the iPhone: see AstroLog_iPhone_Brief.md. Widgets, Live Activities and the phone layout live there.
- Any write to the archive or the ledger, and the import, ship and clear paths.
- Exposing the panel beyond 127.0.0.1.
- The older claude.ai copy of the Observatory (29 August data): relabelling or retiring it is Brett's call, not Code's.

## 13. Considered and left out

These ideas were weighed and left out on purpose, or changed by Brett's walkthrough. Don't build them unless Brett asks.

| Idea | From | Why it's out |
| --- | --- | --- |
| One Next up card, and the top 3 of the queue, at the top of the first screen | Claude research; 23 Oct audit; Claude follow-up | Replaced by Brett's scope-first model (25 Oct): each scope card carries its own next action, and a one-line link under the cards opens Ready to process. |
| Projects as the main way in | Claude research; Claude follow-up | Brett works scope first (25 Oct). Projects are the second layer, and Find still opens any project directly. |
| List-detail and supporting-pane layouts | Claude research; ChatGPT | Replaced by Brett's cards (25 Oct): detail opens under a card or as the next layer. |
| A ban on equal-weight grids | Claude research | The scope cards are equal on purpose, one per telescope, each with its own next action. The ban was aimed at grids of unrelated tiles and charts. |
| Replacing donuts with bars | Claude research; ChatGPT | Brett's chart rules (25 Oct) keep donuts and rings for a share of a whole; bars still compare. |
| Recolouring the Nights heatmap in one hue | Claude research | Brett wants Imaging nights kept as it is (25 Oct); only the scope colours change. |
| Night mode as a must on the PC | Claude research; Claude follow-up | The PC is indoors. Night mode is a must in AstroLog at the scope (iPhone brief, section 8) and optional here. |
| UTC as the main time display | ChatGPT | Brett works in UK time and night dates (6.4, 9.1). |
| Live telescope status, telemetry charts, a Live and Playback timeline with "Go live" | ChatGPT | The Observatory reports archive records, not a running telescope; the ASIAIR and Seestar apps do live control. The live-versus-stale lesson is the status line in 7.1. |
| Telescope commands and command queues | ChatGPT | The Observatory never changes anything. |
| A failed camera eject on the status line | 16 Oct review | The panel's own status reports device problems; the Observatory reports data. |
| A FITS viewer with stretch, WCS and pixel readout (JS9, Firefly) | ChatGPT | PixInsight and Siril do this. |
| An Aladin Lite sky atlas for Sky coverage, with live coordinate, field of view and projection readouts | ChatGPT; Claude follow-up | Worth its own later change: it is a large library, needs a network, and is bigger than this plan. Sky coverage keeps its J2000 labels meanwhile. |
| A web app install (PWA), offline mode and Web Push | ChatGPT | The page is local to the PC; the phone route is AstroLog (decision, 23 Oct). |
| Annotations, comments, mentions and alert assignment | ChatGPT | One user. "Dealt with" in Data checks already acknowledges a check. |
| Marking a dataset stacked or processed by hand | Claude research | States come from the files: a master in the target folder means Finish it, a final means Done. A hand mark would be a second writer for the same fact. |
| Saved layouts and chart presets | ChatGPT | One user, one layout. The page remembers the last view and filter. |
| A formal four-layer state model (server, live, workspace, screen) | ChatGPT | Code's choice of structure. The plan only asks that state is worked out in one place (6.3). |
| Usability panels, questionnaires, analytics, error monitoring, Core Web Vitals targets | ChatGPT | One user on a local page. Brett's own reviews and the questions in section 11 replace them; 7.7 keeps the landing screen under a second. |
| A minimum-hours rule for "ready" (for example 4 h) | Claude research | The quiet period plus the 30-minute sample cut-off does this job (decision, 23 Oct). |
| New chart, component or state libraries | ChatGPT | Ground rule 6. |
| Effort estimates in days | ChatGPT | Sized for a design team, not this project. |
| Android | ChatGPT | No Android device in use. |

## 14. Order of work

1. Section 4: investigate, take the "before" screenshots, and report. Stop.
2. Phase 1 with tests. Stop: counts before and after.
3. Phase 2 with tests. Stop: screenshots at all three sizes. Brett uses it for a week or two and sends a voice note; his notes come before Phase 3.
4. Phase 3 with tests. Stop.
5. Phase 4 with tests. Stop.
6. Phase 5: the export. Stop.
7. Release per CLAUDE.md: VERSION bump, CHANGELOG entry with a Mac / Windows line, both suites green, zip from the commit, push only with Brett's yes.

## 15. Why each change

| Change | Evidence | Source |
| --- | --- | --- |
| Scope first, then project, then detail | That is how Brett thinks and works: per telescope | Brett's walkthrough (25 Oct) |
| Few items on arrival, detail one tap away | Showing a few important options first improves learnability, efficiency and error rate | Brett's walkthrough; NN/g progressive disclosure, in the Claude research |
| One next action per card: the first unfinished step | A small, completable step is easier to start than "process Andromeda" | Brett's walkthrough; Claude research (ADHD guidance, W3C COGA) |
| Cards in a fixed order | Stable layouts let you know where to look | Claude research (ADHD guidance); 16 Oct review |
| Most recent first for lists | Recency is how Brett remembers what needs doing | Brett's walkthrough; decision 23 Oct |
| The right chart for the data | Donuts for a share of a whole; bars to compare; calendars for activity | Brett's walkthrough. The research preferred bars throughout; see section 13 |
| Smooth, brief transitions | Motion that shows where you came from supports orientation | Brett's walkthrough; reduced-motion rule from the ChatGPT research |
| Hours ready, no idle-night counts, no streaks; progress this month; Park | Broken streaks and guilt framing make people give up; monthly progress and a way out of the queue avoid both | Behaviour change studies in the Claude research |
| Text beside every colour; safe palette | WCAG 1.4.1; about 8% of men have red-green colour blindness | Claude research (Okabe-Ito; Wong, Nature Methods 2011) |
| A status line that is always there | Confusing live and old data is the most damaging dashboard ambiguity; a missing warning must not look like "all safe" | ChatGPT research; 23 Oct audit; Claude follow-up |
| Every state says what to do next | Blank or generic states break trust | ChatGPT research |
| 44 px controls, WCAG 2.2 AA, no hover-only facts, 200% zoom, announcements | Platform and WCAG guidance | ChatGPT research |
| Other scopes' data inside a project | Brett wants to see when there's more on disk | Brett's walkthrough; ChatGPT research (linked views) |
| Labelled pictures | Pictures make targets recognisable; an unexplained stretch misleads | Claude follow-up (23 Oct); ChatGPT research |
| Nights by each site's own evening | Time basis must be explicit; the sites span UK, Canary and Texas time | ChatGPT research; Claude follow-up (23 Oct) |
| One dashboard, not two | Duplicated dashboards are an audit red flag | ChatGPT research |
| Numbers before layout | The counts drive the overwhelm, so fix them first | 16 Oct review; 23 Oct audit |
