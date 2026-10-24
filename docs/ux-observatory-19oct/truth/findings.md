# Observatory round 3 · truth: does every word and number on the five screenshots say what is so?

Checked: the five screenshots (7–11.webp) against the engine's `observatory_from` and the scan summary
(`astro-import.py` 11409–11677, 10036–10070, 2284–2322, 4371–4386, 11258–11262), the page's JavaScript
for the function that draws each label (`astro-observatory.html`, line numbers below), the panel's own
header (`astro-app.py` 842–885, 1262–1282, 2470–2471, 2611–2677), the schema in `docs/ux-observatory-16oct/BRIEF.md`
and the real-size `R/truth/stress-dataset.json`. Brett's real record is not here, so every number was checked for
consistency with the other numbers on the same screen and with the rule that produced it.

File references are `page:NNN` = `astro-observatory.html`, `engine:NNN` = `astro-import.py`, `panel:NNN` = `astro-app.py`.
Effort: S = under an hour, M = half a day, L = more.

## Ranked findings

### 1. At 90 nights the week-dots hide their night counts, so the strip under-reports what each scope did (History)

**On screen** (7.webp): the S30 Pro lane shows dots numbered 5, 5, 7, 7, 6 and two plain dots = 32 nights, but
the line beside it says **35 nights**. S50 Pro: four plain dots + 4 + 4 + 2 = 14, beside **21 nights**. 107PHQ:
26 shown, beside **30 nights**. FRA400 and S30 add up (4 and 6). So 14 nights are on the strip without being
visible as nights.

**Why**: at 90 nights on Brett's screen the plot is about 850 px wide, 9.4 px per night, under the 16 px
minimum in `binFor` (page:1087), so a dot is a week. A week-dot carries its number only when it has more than
one night **and its radius is at least 6.5 px** (page:1114, `a.nights.size>1&&r>=6.5`). The radius comes from
the week's hours (page:1085), so a week of three short Seestar nights stays small and silent, and looks like
one night. The number is the only thing that distinguishes "one night" from "three nights" in a week-dot.

**Should say**: every week-dot with more than one night carries its number, whatever its size. Two ways:
(a) when a dot carries a number, make it at least 6.5 px (floor the radius in `makeDot`, page:1109); or
(b) at desktop widths let 90 nights stay a night per dot (lower `min` from 16 to 9 for `plot>=800`; at 9.4 px a
4.5 px dot never touches its neighbour). (b) is truer to the subtitle; (a) is the one-line fix.

Also on the same screen: the card's subtitle says "**one dot per night** a scope was out" (page:1477) while the
key line's last entry says "at this range a dot is a **week**, the number its nights" (page:1169, 7.webp bottom
right, same muted type as the legend). Two contradicting sentences 500 px apart. When `bin>1` the subtitle
should change: "one dot per week a scope was out · the number is its nights". Move `binNote` into the subtitle
and drop it from the key line.

Effort S · page only.

### 2. One freshness line: the same time stamp is on screen four times, and the pill says "live" about a record that is 19 hours old (Header, Brett's point 3)

**On screen** (11.webp), before any content:
- panel: "Worked out 19 Oct 2026, 03:38 · the PC's complete list · 5 warnings (see Data health)" (panel:2471)
- hero: "Record built **19 Oct 2026, 03:38** · the Mac's copy is from today" (page:989–992)
- pill: "● live · 19 h ago" (page:1006)
- nav bar, right: "record built 19 Oct 2026, 03:38" (page:950, markup 677)
- and the footer again: "Worked out on the PC on 19 Oct 2026, 03:38 from …" (page:1957, off-screen here)

**What is true**: the record was built on the **PC** at 03:38 (its nightly job). Brett is reading it on the
**Mac**, whose panel serves the PC's published copy while it is under 48 h old (panel:1266–1270). "live" means
the Mac's importer answered the page's 30-second poll; "19 h ago" is the age of the PC's record. "The Mac's copy
is from today" means the Mac's ledger snapshot that the PC read was **less than 24 h older than the build**
(page:991: `days===0` → "from today"); at 03:38 that snapshot was from the evening of 18 Oct, so "today" is
wrong by the calendar and says nothing about *when*. Three clocks (built, snapshot, importer answering) in one
sentence, and the one Brett needs, "how old is what I'm looking at", is split between "19 h ago" and "03:38".

**Should say**, one line under the title, nothing else repeated:

> Built on the PC at 03:38 this morning · 19 h old · from the Mac's record of last night 21:04 · next build tonight about 03:30

with the pill reduced to the connection only: "● importer answering" / "● importer not answering" / "rebuilding…".
"this morning / yesterday / N days ago" from `generatedAtIso`; the snapshot's time from `inputs.snapshot.at`
(the engine already gives it to the minute, page only prints the day); "next build" is a fixed fact of the PC's
job (03:30 sweep) and could come as `inputs.nextBuildAt` later (engine, optional).

Then: delete the nav bar's `asof` (page:677/950) and the panel's "Worked out …" note (panel:2471) — it duplicates
the hero, and "the PC's complete list" is jargon. If one short panel line must stay until the Observatory is its
own route, make it the one thing the hero doesn't say: "5 things to check · Data checks tab".

Effort S for the wording, M with the panel changes · page + panel:2471; no new engine field needed.

### 3. "87 files on the ASIAir not yet imported (1 target) · 85 already on the other computer" — Brett cannot tell what to do with it (Header + truth)

**On screen** (11.webp): "⚠ 87 files on the ASIAir not yet imported (1 target) · 85 already on the other
computer · the lists below don't include them · seen 3 h ago · the Mac's scan" (page:997).

**What is true** (engine:2284–2300 and panel:500–511): the scan's `new` list is the files on the camera that
this Mac has not imported **minus** the ones the PC's record already holds; those go to `elsewhere`. So the 87
and the 85 are **different files**: 87 still need importing on *either* computer, 85 need nothing. The sentence
reads as if the 85 were part of the 87. "The lists below don't include them" is true but leaves Brett asking
"so what?". "the other computer" when the page knows it is the PC (`elsewhere_machine`, engine:2322 — not in the
summary yet).

**Should say**:

> ⚠ 87 frames on the ASIAir still to import (1 target) · plug it into the Mac or the PC · another 85 on it are already backed up by the PC · the Mac looked 3 h ago

Needs one engine field: `pendingImport.elsewhereMachine` (the panel already has `who`, panel:532; add it to
`save_scan_summary`, engine:10038) so "the PC" replaces "the other computer". Worth adding the target's name
too (`pendingImport.targetNames[]`, M): "1 target" hides which project is waiting, which is History.

Effort S for the wording · engine field `elsewhereMachine` (S), `targetNames` (M).

### 4. "423 frames only on the Mac" sits under the wordmark in amber and reads like a fault in the Observatory

**On screen** (11.webp, panel header): "● 423 frames only on the Mac".

**What is true** (engine:4371–4386, `status_summary`; tooltip panel:1066–1069): these frames were imported and
cleared from the camera, and their only *verified* copy is on the Mac until the PC's sweep re-hashes the archive's
copy (the 03:30 sweep, then the next ship). Nothing is wrong and nothing is for Brett to do; the tooltip says
so but only on hover. Beside the Observatory's "1,326.1 hours" it reads as 423 frames the page is missing.

**Should say**: "423 frames await the archive's check (next: tonight's sweep)" — grey, not amber, since
amber is a warning colour everywhere else on this screen. The text is built in the engine (engine:4384–4385),
the colour in the panel.

Effort S · engine text at `status_summary` + panel style.

### 5. The same hours shown two ways on one screen: S50 Pro 85.8 h and 85.7 h; hero 1,326.1 h and slices adding to 1,326.0 h

**On screen**: 7.webp strip line "**85.8 h** over 21 nights" (all 21 of the S50 Pro's nights are within 90, so
this is its whole total); 11.webp share key "**85.7 h** · 6% · 21 nights". Hero "**1,326.1**"; the six slices
386.0 + 217.7 + 104.1 + 85.7 + 312.8 + 219.7 = **1,326.0**.

**Why**: the strip sums the sessions' hours rounded to tenths (`sumH`, page:792, the spec's "total is the sum of
displayed parts"); the share key and hero print the engine's own rounding of the raw seconds
(`sc["hours"]=round(…,1)`, engine:11574; `totals.hours`, engine:11661). Two rounding rules, two answers.

**Should say**: one number. In `derive()` (page:777–790) set each scope's hours to `sumH` of its sessions when
sessions exist, and the hero to the sum of the six scope figures; then the strip, the share bar and the hero
agree to the tenth, and the reconciliation row "Hours by scope, against the total" stops needing a tolerance.

Effort S · page only.

### 6. "1 Seestar S50 Pro" and the slice labelled "1": the real cause is not a stray "1" in the scope's name

The brief lists this as known ("the scope's name carries a stray 1"). It does not. `renderShare` (page:955–960)
labels a slice in-segment when it is wide enough, and otherwise gives it a **numbered tick**: the slice gets a
centred "1" and the key gets `<span class="no">1</span>` before the name (page:963). The S50 Pro's slice is
85.7 / 1326.1 × 1,546 px ≈ 100 px; the label "S50 Pro 85.7 h" needs 14 × 6.4 + 14 = 103.6 px (page:958), so
it misses by 4 px and becomes tick 1. The `.no` style (page:171) is a plain small bold number with no circle,
so the tick reads as part of the name. Nothing in the contract or the engine needs changing.

**Fix**: measure the text (`getComputedTextLength`) instead of 6.4 px a character; when the full label does not
fit try "S50 Pro 86 h" then "S50 Pro" before falling back to a tick; and if a tick is ever still needed, draw it
as a circled badge in both places so it reads as a footnote mark.

Effort S · page only.

### 7. Three "Finish it" pills on one card say the same words three times; the scope is only a 10 px dot (History: "onto what scope")

**On screen** (9.webp Western Veil): "● ◑ Finish it  ● ◑ Finish it  ● ◑ Finish it", dots amber, red, green.
Silver Sliver: "Finish it" (black dot), "Still capturing" (slate dot). Black and slate are the two hardest scope
colours to tell apart on the page.

**Fix**: when a project has more than one scope, the pill carries the scope's short name:
"● Finish it · S30 Pro", "● Finish it · FRA400", "● Finish it · 107PHQ". `projCard` (page:1533) already passes
`{cam}`; pass `text: s.word+" · "+short(p.camera)` when `progs.length>1`. One more pill width, and the card
answers Brett's first question without hovering.

Also to check on Brett's machine: in 10.webp the California Nebula's "Ready to process" pill has a **pale/white
dot**, not S30 blue as the same pill has on the Tadpole card. `col()` falls back to `var(--muted)` for a camera
that has no `scopes[]` row (page:816–817) — if one of California's datasets is on a scope spelled differently in
the ledger, it would show exactly like this. Hovering the dot gives the camera's name (page:821).

Effort S · page only.

### 8. Cut-off text where the whole sentence is the point

- 7.webp / 8.webp, S50 lane: "nothing in 90 nights · last out **24 May 2026**, 147 nights …" — the year
  and the ellipsis eat the "ago". `stripText` (page:1445) writes one line; the `.rt` column is 330 px and
  `nowrap` (page:349, 357). Should be two lines like the other lanes:
  "quiet for 90 nights" / "last out 24 May · 147 nights ago" (drop the year when it is this year).
- 10.webp, the three marks: "Active · last frames 2 ni…" and "Not tracked · the Seestar cali…"
  (`.marks3 .mark small` is `nowrap` + ellipsis, page:301). The subs are the useful half. Either let them wrap
  to two lines (the lane row is 60 px tall; remove `white-space:nowrap` for `.marks3`), or shorten:
  "2 nights ago", "in camera". Both are page only.

Effort S · page only.

### 9. "‹80", "‹66", "‹51" at the left of each lane are never explained on the strip

**On screen** (7.webp and 8.webp): a small "‹80" where the S30 Pro lane starts. Verified against the share key:
115 nights in all − 35 in range = 80 ✓; S30 72 − 6 = 66 ✓; S50 51 − 0 = 51 ✓; FRA400 63 − 4 = 59 ✓;
107PHQ 46 − 30 = 16 ✓ (and at 30 nights: 110, 72, 51, 6, 61, 37, all ✓). The numbers are right. But "‹80"
reads as "less than 80", and the only explanation is a hover tooltip (page:1140) and a line at the foot of the
*project* panel ("‹N = nights before this range", page:1300) — not on the strip itself.

**Fix**: add it to the strip's key line (page:1467): "‹80 = 80 earlier nights, before this range"; or render
it as "+80 before" so it needs no key. For the S50, whose 51 nights are *all* before the range, "‹51" next to
an empty lane is the whole story — fine once the key says what it means.

Effort S · page only.

### 10. Legend entries that are not true at the range shown

- "● no frames that night (30 nights only)" stays in the key at 90 nights (7.webp), where no such dots are
  drawn (page:1467; the empty dots are only drawn when `N<=30`, page:1148). Hide the entry when `N>30`.
- The "hours unknown" marks in the header legend (page:968–969) and the strip key (page:1467) are drawn in
  the **S30 Pro's amber** (`SC[0]`), on a page whose rule is "colour means scope". They should be a neutral
  grey ring, or the key should read "hours unknown (shown here in the S30 Pro's colour)". Neutral is simpler.

Effort S · page only.

### 11. "Open cluster in the Tadpoles (IC 410, NGC 1893)" · "Open cluster · in Auriga · mosaic"

The name is the PC's pre-merge contract (known). The **type line** is also the old entry's: "Open cluster" is
what the PC's `targets.json` said for NGC 1893; the merged contract files it under IC 410, "Tadpoles Nebula",
type **Emission nebula**, with "Open cluster in the Tadpoles (IC 410)" and "Tadpole Nebula" as aliases
(contract/targets.json, IC410 entry). After the merge this card and the "Tadpole Nebula (IC 410)" card above it
become one project on three scopes (S30, S50 Pro, S30 Pro), 39.4 h. Nothing for the page to do there.

One thing the page should change: **"mosaic"** on a project card means *any* dataset was a mosaic
(`tg["mosaic"] = tg["mosaic"] or …`, engine:11552; `describe(t)` page:1529 prints `t.mosaic`). On the merged
Tadpoles only the S30 Pro's dataset is a mosaic (10.webp: "3 nights · mosaic" under S30 Pro, the panel is right
per lane). The card should say "mosaic on the S30 Pro" when not every dataset is one — `programmes[].mosaic`
is already in the record (engine:11520).

Effort S · page only (`describe`).

### 12. In the project panel, "everything" is the same range as "90 nights" for any project younger than 90 nights

**On screen** (10.webp): "90 nights | **everything** | Close", with "everything" selected and the axis
21 Jul → 18 Oct, which is 90 nights. `projectPanelFor` (page:1279–1282) sets `NALL = max(90, …)`, so for a
three-night project both buttons are 90, and clicking "everything" changes nothing (which is how the screenshot
came to be). Drop "everything" when `NALL <= 90`, or label it "everything (90 nights)".

Effort S · page only.

### 13. "see Data health" points at a tab called "Data checks"

Panel line (panel:2471) says "5 warnings (see Data health)"; the page's tab is "Data checks 5" (page:1029).
One name. "Data checks" is the better one (it is what the tab does); change the panel's string, or delete the
panel line as in finding 2.

Effort S · panel:2471.

### 14. "waits until 31 Oct unless you add frames" — true, but the date reads as a deadline rather than the day it becomes Ready

Engine:11260: `ready_on = last_session + QUIET + 1` = 16 Oct + 15 = **31 Oct** (14 full quiet nights, 17–30 Oct).
Correct. Suggest "ready to process from 31 Oct unless you add frames" (page:1253), the same phrase the evidence
already uses ("ready to process from …", engine:11504), so the date means the same thing everywhere.

Effort S · page only.

### 15. "Refresh now" on the Mac does not refresh what the page shows

Panel:1262–1270: on the Mac the PC's published copy wins while it is under 48 h old; "Refresh now" rebuilds the
**Mac's own** record (panel:2455–2459), which the page then does not show. The pill says "rebuilding…" and comes
back to the same PC record. Brett pressed it this morning and saw no change, which is correct behaviour with a
misleading label. Tooltip/label on the Mac: "Rebuild the Mac's record (the PC's nightly copy is shown while it
is under 2 days old)". On the PC the label is right as it is. The panel knows which machine it is (`eng.IS_WINDOWS`).

Effort S · panel.

### 16. The ASIAir storage pill shows a reading with no time, next to "no camera connected"

11.webp: "● no camera connected" and "ASIAir 105.0 GB / 223.3 GB · 118.4 GB free" side by side. The reading is
from the last scan (panel:2670–2677) and is true as of then; it should say so: "ASIAir, 3 h ago: 105.0 / 223.3 GB".
Outside the Observatory, but it is in the first 60 px of the screen.

Effort S · panel.

### 17. Small ones (Low)

- "Projects that moved lately … newest first": the sort (page:1579) never returns 0 for equal nights, so the
  three "last 16 Oct" cards come in whatever order the record had them. Tie-break by hours, biggest first, and
  say "newest first, then biggest".
- The project panel's title puts " · one lane per scope" after the name, so it wraps to a line starting with "·"
  (10.webp). Put "one lane per scope" at the start of the subtitle instead (page:1281–1284).
- The hero's six companions: "240 nights" is nights with any scope out; the share key's nights (115 + 72 + 51 +
  21 + 63 + 46 = 368) are per scope. Both true; a hover on "240 nights" saying "nights with at least one scope
  out" would stop the sum being tried.
- "in the importer's fixed order" (strip subtitle, page:1477) → "scopes in their usual order".
- The panel footer "you can override that" (page:1300) does not say how; "(capture-state.json: open / complete)"
  or a link to the Data checks explanation.

## Numbers checked and found right (no one needs to re-check these)

- Every "‹N" earlier-nights figure at 30 and 90 nights (finding 9).
- 30-night and 90-night lane lines agree with each other and with the share key: S30 Pro 20.2 h / 5 nights ⊂
  129.5 h / 35 ⊂ 386.0 h / 115; FRA400 14.6 / 2 ⊂ 21.9 / 4 ⊂ 312.8 / 63; 107PHQ 42.6 / 9 ⊂ 147.2 / 30 ⊂
  219.7 / 46; S30 17.4 / 6 (all within 90) ⊂ 217.7 / 72.
- FRA400 "latest: Flaming Star Nebula, 13 Oct · 7.1 h" matches the Flaming Star card ("last 13 Oct", FRA400 lane).
- Silver Sliver "4 nights" = 1 dot in the last 120 + "‹3" on its mini line.
- Share percentages 29 + 16 + 8 + 6 + 24 + 17 = 100 (largest remainder, page:800).
- 24 May 2026 → 18 Oct 2026 = 147 nights.
- "31 Oct" (finding 14).
- "18 Oct · last night" is the record's `asOfNight` (built at 03:38 on the 19th, during the night named 18 Oct).
  True at build; by the evening of the 19th "last night" has moved on, which finding 2's "19 h old" covers.

## Keep as it is

- A night is noon to noon and is named by its evening, everywhere, with "Thu 15 → Fri 16 Oct" in the night rows.
- "hours unknown" is never 0: hollow dots, hatched ring segments, "frames, hours unknown" in the lane text.
- "Not tracked · the Seestar calibrates in the camera" (never "not needed"), and "Not started" / "Active · last
  frames N nights ago" as three marks per lane: the right facts, only the cut-off needs fixing (finding 8).
- The per-lane text beside the strip ("129.5 h over 35 nights · latest night: 2 objects, 6.2 h (16 Oct)"): this
  is the History line Brett opens the page for; keep its shape.
- The freshness line never shows a green tick for a camera it did not check (page:1000) — keep that rule when
  rewording finding 3.
- Scope colour from the record only, never a palette in the page; status as glyph + word; the warm-wash warning
  style for the shared-Askar note ("One master in the shared Askar folder, not named for either Askar") with
  the fix spelled out in the panel.
- `‹N` counts, the quiet band, and the dot tooltips listing each night's objects: all true, all useful.
- The footer's "Worked out on the PC on … from this PC's record, the Mac's copy of …, the archive's inventory …"
  is the one place the full provenance belongs; keep it there (and only there, finding 2).
