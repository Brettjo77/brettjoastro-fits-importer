# Observatory review A: "glanceable" — pictures instead of numbers

For Brett, 16 Oct 2026. Mock: `mock-A.rendered.html` in this folder (open it in a browser; Overview and Targets are real, the other tabs are stubs). Screenshots: `A-desk.png`, `A-phone.png`, plus `A-desk-targets.png`, `A-phone-targets.png`, `A-desk-lower.png`, `A-desk-dark.png`.

## What makes the current page hard to read (ranked)

1. **It is a wall of text cards.** The Overview opens with eighteen "last session" cards, all the same size and weight, then twelve more for the queue. Nothing is drawn; you have to read every card to know what happened. The one picture (hours by scope) is at the bottom.
2. **Scope colour isn't trusted.** The page paints the 107PHQ green and the S50 Pro magenta; the importer's contract says blue and green. The same scope should be the same colour in the panel, the Observatory and the receipts, or the colour stops meaning anything. The scopes also come in a different order in every panel.
3. **Stage is colour-coded in purples**, which collide with the Starfront's purple, and the single "state" badge hides mixed stages: Andromeda reads "To process" while one scope is in progress and one is still capturing.
4. **Unknown is shown as zero.** Milky Way Core says 0.0 h next to 2,150 frames. The exposure wasn't recorded; the hours are unknown, not nil.
5. **Bare numbers.** 101.7 / 35 / 4,956 only mean something if you look up at the column header. The five KPI tiles repeat the hero line.
6. **Nights are a count, not a time.** "35 nights" doesn't say when. The one view that shows time on a line (the scope timeline you liked) is hidden behind a click on a scope name.
7. **Thin bars with no label.** The S50 and S50 Pro slivers in "Integration by scope" are unlabelled; only the two big scopes get a number.
8. **Warnings don't say what to do**, and they undersell the problem: "2 things to know" is really 491 rows not counted (184 unknown names, 2 without a scope, 305 duplicates that were correctly dropped). The good news is mixed in with the bad.
9. **Test snaps clog the queue.** Datasets of 0.4 h, 0.8 h, 0.9 h from months ago sit in "To process" next to a 30-hour Andromeda set.
10. **Navigation takes room.** Nine tabs across a wide header; on the phone the tabs scroll sideways and there's no label saying which view you're on.

## The proposal

**Colour means scope, shape and a strong colour mean stage, time runs left to right.** Every place a scope appears it wears its contract colour (dot, ring, bar, strip, badge stripe), in one fixed order (the contract's: FRA400, 107PHQ, S30 Pro, S50, S50 Pro, Starfront). Every dataset's stage is a badge with its own colour and its own glyph (cyan aperture = still capturing, pink play = to process, orange half-moon = in progress, green tick = done, grey dashed = sample), so Andromeda shows four badges, not one. Hours are a ring (share by scope) and a stacked bar; frames with no exposure are a hatched segment, never 0. Anywhere there used to be a count of nights there is now a line with a dot per session, bigger for longer sessions, a shaded band for the 14-night quiet period, and the stage badge after the band: the picture you said was the right direction, on every project card and every row of the Targets list.

**Decisions first, history after.** The Overview opens with a big friendly "Last night out" line (date, scopes, objects, hours), then the two things to check (as buttons), then "what each scope captured in the last 30 nights" (one dotted line per scope), then "What to do next" in three columns (process / finish / still capturing) with a scope stripe, a labelled hours bar, a calibration warning and the shared-Askar-folder warning on the card itself, and the samples listed separately. Only then come the projects that moved lately, the last twelve months by scope on a seasons strip, the whole archive per scope (every bar labelled, even the thin ones), and the top ten projects. The header is a night sky carrying the one hero number, the share bar with every scope labelled, and a freshness line that says when the record was built and whether frames are still waiting on a camera.

**The Targets list is a strip of pictures.** Each row: a ring of hours by scope, the name and what we know about it (type and constellation, or "type not recorded"), one pill per scope with its stage badge, the hours labelled as "9.5 hours · 7 nights · 734 frames", and a 90-night timeline. The search box, the scope chips and the stage chips stay; a "Sample" chip joins them. Sort defaults to latest capture first, because that's the question you ask most.

## What changes, view by view

**Header (all views)**
- Night-sky header. Eyebrow, title, then the hero: `292.8` hours of light frames · 16,414 frames · 41 targets · 130 nights · 6 scopes, with a scope share bar and a key that gives every scope's hours (the thin ones too).
- Freshness line: "Built 16 Oct 2026, 09:12 from both computers' records (the Mac's is from 15 Oct 2026)" and either "nothing known to be waiting on a camera" or an amber pill "3,559 files on the camera not yet imported · 29 targets".
- Tabs on desktop; on the phone a labelled "View" selector. One page scroll, no inner scrollbars.

**Overview**
- "Last night out" headline card.
- Warnings as actions: each with a button ("Review names", "See the rows"); the duplicates note shown separately as "Fine, nothing to do".
- "What each scope captured in the last 30 nights": one dotted line per scope in contract order; hours and nights labelled on the right, with the latest object; quiet scopes say "nothing in 30 nights · last out 25 Jul 2026, 83 nights ago". Clicking a scope opens Targets filtered to it.
- "What to do next": three columns headed by the stage badge; each card has a scope stripe, labelled hours and nights, a bar against the biggest dataset, calibration gaps ("no darks or flats linked to its lights"), the shared-Askar warning, and for still-capturing cards the ready date. Datasets under 1.5 h are listed under "Samples, kept out of the queue".
- "Projects that moved lately": a card per project with frames in the last 60 nights: ring of hours by scope, labelled totals, a timeline with one lane per scope, and one stage badge per scope ("In progress ×2 · To process · Still capturing · 4 scopes, mixed stages" for Andromeda). Milky Way Core shows a hatched ring, hatched dots and "hours unknown · 2,150 frames".
- "The last twelve months, by scope": a column per month stacked by scope, labelled, on season tints; then one labelled bar per scope for the whole archive.
- "Where the hours went": the top ten, stacked by scope, labelled.

**Targets**
- Rows as described above; the "state (scope furthest behind)" column is gone, replaced by one pill per scope.
- Type and constellation degrade gracefully ("type not recorded"; no blanks).
- Chips: six scopes, five stages (incl. Sample). Count "41 of 41 targets".

**Pipeline / Nights / Sky / others**: not redrawn here. The same badges, scope colours and timelines should carry across when they are.

## Which points of the two reviews this answers

ChatGPT: 1 (every number labelled), 2 (unknown ≠ zero: hatched, "? hours"), 3 (mixed stages shown per scope), 4 (capture activity = timeline, stage = badge, calibration = warning line on the card; the Askar-folder warning is on the card and the project), 5 (decisions before history; one latest night, then the queue), 6 (one scrollbar, compact header, labelled view selector on the phone), 7 (warnings as actions, duplicates separated), 8 partly (the charts here all carry legends and labels; Nights/Sky/Coverage not redrawn).

Second review: 491 rows not counted is now three separate lines; Milky Way unknown; one badge per scope; decisions first; calibration as its own signal. **Sample state**: datasets under 1.5 h leave the queue and get their own badge and chip. **Missing type/constellation** handled. **Thin bars labelled** everywhere (share key, scope rows). **One scope order** everywhere (the contract's). **Freshness line** in the header with a slot for "N files on the camera not yet imported". Not done: showing which "still capturing" is your own capture-state.json (open by hand) versus the 14-night rule, because the dataset doesn't say which is which (see below).

## Data the page would need that the dataset doesn't carry

- **Pending import**: files and targets still on a camera, and a failed eject, so the freshness line can say "3,559 files not yet imported" instead of "nothing known". Suggested `D.pending = {files, targets, note}`.
- **Why a dataset is "still capturing"**: whether it's within the 14-night rule or kept open by hand in capture-state.json. A flag like `programme.openByHand` would let the badge say "kept open by you".
- **Sample marking**: the 1.5 h cutoff is a guess. A per-dataset `sample: true/false` (set by the importer or by you) would make the queue honest without a magic number.
- **The unrecognised names themselves**, so "Review names" can list them on the page instead of sending you to a command.
- Scope colours in the template should come from `D.scopes[].colour`, not the page's own table, so the panel and this page agree.
