# Wording: current phrase → recommended phrase

Brett is an astrophotographer, not a developer. His words are target, scope, night, frames, hours, subs, darks, flats,
master, final. Words to retire from the page: contract, ledger, row, project layer, dataset, programme, linked, schema,
capture-state.json, snapshot, inventory. Where a technical thing must be named, name what it is for Brett ("the list of
target names the importer knows").

## Header and freshness

| Mock | Current | Recommended |
|---|---|---|
| A, C | PC · E:\ ASTRO DATA ARCHIVE · LIVE FROM THE IMPORTER | PC · E:\ Astro Data Archive · from the importer's record |
| A | Built 16 Oct 2026, 09:12 from both computers' records (the Mac's is from 15 Oct 2026). | Record built 16 Oct 2026, 09:12 · the Mac's copy is from 15 Oct (a day old) |
| A | ✓ nothing known to be waiting on a camera | Frames still on a camera: not reported by this record *(grey, no tick)* — and when the engine knows: ⚠ 3,559 files on the Seestar not yet imported (29 targets) · the lists below don't include them |
| C | worked out 16 Oct 2026, 09:12 from 11,206 ledger rows | Record built 16 Oct 2026, 09:12 from 31,284 lines of the importer's record |
| C | the Mac's record is from 13 Oct 2026 | the Mac's copy is 3 days old (13 Oct) |
| C | on the camera, not yet imported: not reported by this record | Frames still on a camera: not reported by this record |
| A | worked out 16 Oct 2026, 09:12 *(second copy, right of the tabs)* | *(remove; one freshness line)* |
| A | hours of light frames | hours of integration *(then once, small: light-frame exposure, added up)* |
| C | cameras in the ledgers | scopes |
| C | one target on one scope *(for "datasets")* | keep, but call the tile "target + scope pairs" rather than "datasets" |
| C | 290 GB on the archive | 270 GB on the archive (as Windows shows it) |

## Last night

| Mock | Current | Recommended |
|---|---|---|
| A | LAST NIGHT OUT · 16 Oct 2026 · Friday · 3.8 h over 2 sessions · 2 scopes | Last night · Thu 15 → Fri 16 Oct · 3.8 h · 2 objects · 2 scopes |
| C | Fri 16 Oct 2026 · 3.8 h in 62 frames on 2 scopes | Night of Thu 15 → Fri 16 Oct · 3.8 h · 62 frames · 2 objects on 2 scopes |
| A | Last time out · 5 nights ago | Latest night · 5 nights ago (11 Oct) |
| C | Latest night, 5 nights ago | *(same as above)* |
| A | Askar FRA400 on Horsehead Nebula (IC 434) · 1.8 h · 21 frames · L-eXtreme | keep; add "300 s subs" when exposures are known |
| C | FRA400 · 1.8 h · 21 frames · 30 darks | FRA400 · 1.8 h · 21 frames · 30 darks filed that night |
| A | latest: Stephan's Quintet (NGC 7320), 16 Oct · 2.2 h *(when the scope shot 3 objects)* | latest night: 3 objects, 5.4 h (16 Oct) |
| A | nothing in 30 nights · last out 25 Jul 2026, 83 nights ago | keep (verified) |

## Data quality ("To check" / "Needs your attention")

| Mock | Current | Recommended |
|---|---|---|
| A | To check: 2 target name(s) the contract doesn't know; their 184 frames are not counted. [Review names] | 184 frames belong to 2 target names the importer doesn't recognise, so they are in no project. [Review the 2 names] |
| C | 2 target names the contract doesn't know · their frames are real but sit outside every project until the names are added | 2 target names the importer doesn't recognise · 184 frames are in no project until you add the names |
| A | To check: 2 rows carry no scope (no focal length and no camera name); not counted. [See the rows] | 2 frames name no scope (older ASIAir files with no focal length or camera), so no scope can claim them. [See the 2 frames] |
| C | 2 ledger rows · carry no scope | 2 frames · name no scope |
| C | Warning from the project layer *(fallback title)* | *(never show; every warning kind gets its own sentence)* |
| both | *(the Mac-age warning as "To check" / "See the rows")* | The Mac's copy of the record is 3 days old: sessions imported on the Mac since 13 Oct are missing here. [How to refresh] |
| A | Fine, nothing to do: 305 rows are second copies of the same bytes (the Mac's and the PC's import of one frame); counted once. | 305 frames were imported on both computers · counted once · nothing to do |
| C | 305 duplicate copies · counted once, correctly · the Mac's and the PC's import of the same frame | same |
| both | *(missing)* | 14,379 other files in the record (darks, flats, stacks, previews) are not light frames and are not counted here |
| C | 2,150 frames, exposure unknown · Milky Way Core on S30 Pro · … [Check the exposure] | 2,150 frames with no exposure in their headers · Milky Way Core on the S30 Pro · hours unknown, not zero [Tell the importer the sub length] |
| C | 2 datasets share one Askar folder … nobody can tell which until you say [Say which Askar] | Andromeda's Askar folder holds one master and lights from both Askars · the importer can't tell which scope made the master [Say which Askar] *(only when the master's name doesn't say)* |
| C | 15 datasets have no calibration linked to their lights · 8 missing flats only · 7 missing darks and flats | 13 waiting projects have no darks or flats filed with their lights · 8 need flats · 5 need darks and flats *(done and still-capturing excluded)* |
| C | 1 samples · kept out of the queue … under 1.0 h on one night · mark as sample, or process anyway | 1 quick look kept out of the queue · Fireworks Galaxy, 144 frames on one night, 87 nights ago · [It's a real project] [It's a quick look] |
| A | Samples, kept out of the queue: 6 datasets under 1.5 h · Sadr Region · S30 Pro 1.4 h · … quick looks and test snaps. Mark one as a real project to move it into the queue. | Quick looks, kept out of the queue (N) · one line each: name · scope · frames · nights · "why: 1 frame" · [real project] |

## Queue and status

| Mock | Current | Recommended |
|---|---|---|
| A | Process these · 18 datasets · no new frames for 14 nights and nothing started. Start with the biggest. | Ready to process · 18 · nothing new for 14 nights, nothing started yet · biggest first |
| A | Finish these · 5 datasets · a master is saved but no final picture yet. | Finish · 5 · a master is saved, no final yet |
| A | Still capturing · 11 datasets · frames within the last 14 nights. Soonest ready first. | Still capturing · 11 · new frames in the last 14 nights, or kept open by you · soonest ready first |
| C | 23 datasets have had no new frames for 14 nights and nothing started · biggest first | 23 ready to process: nothing new for 14 nights and nothing started · biggest first |
| C | 5 datasets have a master of yours saved but no finished picture yet | 5 to finish: a master of yours is saved, no final yet |
| A | · ready 20 Oct | waits until 21 Oct unless you add frames *(engine date = last night + 15)* |
| C | quiet from 29 Oct if nothing new | ready to process from 30 Oct if nothing new |
| C | capture-state.json says open · last session 44 nights ago | kept open by you · last frames 44 nights ago |
| both | *(missing)* | closed by you on 12 Jul · ready to process |
| C | Quiet · no frames for 96 nights | Quiet · nothing new for 96 nights |
| A, C | no darks or flats linked to its lights | no darks or flats filed with these lights |
| C | Not needed · Seestar handles its own | Not tracked · the Seestar calibrates in the camera |
| C | Seestar: its own calibration *(session line)* | calibrates in the camera |
| C | no calibration that night | no darks or flats filed that night |
| C | Complete · darks and flats linked | Darks and flats filed · on 3 of 5 nights |
| C | Master saved ? · 1 master in the folder · which Askar? | Master saved ? · one master in the shared folder · which Askar made it? |
| C | Not started ? · unless the folder's master is this scope's | Not started ? · unless the shared folder's master is this scope's |
| A | In progress ×2 · To process · Still capturing · 4 scopes, mixed stages | 1 still capturing · 1 to process · 2 in progress · on 4 scopes |
| A | · 2 scopes, same stage | on 2 scopes |
| A | Decide *(verb for Sample)* / Finished *(verb for Done)* | *(see final vocabulary)* |
| A | Hatched: exposure not recorded, so hours are unknown (not zero). | Hatched: no exposure in the headers, so the hours are unknown (not zero) |
| A | ? hours · unknown · 2,150 frames | hours unknown · 2,150 frames |
| both | 0.0 h *(for 80 s)* | 1 min |
| A | ‹35 | 35 earlier |
| A | Jan 26 | Jan 2026 |
| A | + 215 fr, h? | +215 frames, hours unknown |
| A | the coloured badge is the stage | the coloured badge is the next step |
| C | Why: FRA400 — master saved: … · 107PHQ — … | *(tooltip only)* |
| C | always in this order, most hours first | always in this order *(fixed order from the importer)* |
| A, C | Data health · 2 / Data health ❷ | Data checks · 2 to look at |

## Final status vocabulary (one plain sentence each)

Shown on every dataset (one target on one scope) as a pill with a glyph; the project row shows the counts of its
pills in this order. The pill is the **next step**; the three small marks beside it say *why*.

| Pill | Glyph | One sentence for Brett | When |
|---|---|---|---|
| **Still capturing** | ◔ cyan | New frames arrived in the last 14 nights, or you've kept this one open, so keep shooting. | engine `capturing` |
| **Ready to process** | ▶ amber | Nothing new for 14 nights (or you closed it) and nothing has been started, so it is waiting for you. | engine `ready_to_process` |
| **Finish it** | ◑ violet | A master of yours is saved but there is no final picture yet. | engine `in_progress` |
| **Done** | ✓ green | A finished picture names this target and this scope. | engine `done` |
| **Quick look** | ○ grey | A test or a one-off snap you've said is not a project; it is kept out of the queue. | your flag only |

Capture marks (why): **Active** · last frames N nights ago — **Open, kept by you** — **Closed by you on {date}** —
**Quiet** · nothing new for N nights.
Processing marks: **Not started** — **Master saved** — **Final found** — add **?** when the shared Askar folder makes it uncertain.
Calibration marks: **Darks and flats filed** (on N of M nights) — **Flats missing** — **Darks and flats missing** —
**Not tracked** (the Seestar calibrates in the camera) — **Unknown** (no record for this scope).
Integration: **9.5 h** — **hours unknown** (frames with no exposure in their headers) — never 0.0 h for a real number: use minutes below 0.1 h.

Retired: "In progress" (keep only as the count word "2 in progress" on project rows, or use "2 to finish"), "To process"
(→ "Ready to process"), "Half done", "Process it" / "Keep capturing" as pill text (the pill names the state; the button
next to it carries the verb), "Sample" (→ "Quick look").
