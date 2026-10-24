# History review: what was captured lately, on which scope (19 Oct 2026)

Reviewer lens: the morning-after question. Brett opens the Observatory and wants to know,
without hunting: *last night the S30 Pro did 503 subs of the Tadpoles mosaic and 245 of the
Western Veil, the 107PHQ did nothing.*

## The test, run against the page as built

How many clicks, scrolls and hovers from opening the tab to that sentence, on the page Brett
screenshotted on 19 Oct (record built 03:38, latest frames 16 Oct, nothing on 17 and 18 Oct):

1. **Scroll past ~700 px** before any content: the panel's own header, the tabs, the "Worked out"
   line, the night-sky hero, the share bar, the legend, the nav (11.webp is 2000 x 697 and is
   *all* header).
2. **"Last night" block** (`astro-observatory.html:1361-1380`, `renderLastNight`). It shows one
   night only, one row per scope. A scope that did two objects reads
   **"2 objects · 6.2 h · 1,234 frames"** and the names are pushed to a second, smaller line
   underneath (the `objs` line, line 1376). A scope that did nothing is simply absent: the page
   never says "the 107PHQ did nothing". When the last two nights were blank, the eyebrow reads
   "Latest night · 2 nights ago" and the blank nights are not mentioned.
3. **Scroll past "Needs your attention"** (about 700 px on the built overview,
   `built/final-1440-overview.png` y 540-1240) to reach the strip.
4. **The strip** (7.webp, 8.webp): the dots say *that* a scope was out and roughly how long, and
   the text column says "latest night: 2 objects, 6.2 h (16 Oct)". The object names need
   **one hover per dot**, or Tab + arrow keys. For four active scopes over a week that is 10-20
   hovers to read the week as a story.
5. **"Projects that moved lately"** (9.webp): each card says "last 16 Oct" but not what happened
   on 16 Oct (which scope, how many frames). Opening a card (10.webp) shows the lane; the
   night-by-night table is collapsed behind "3 nights on the S30 Pro: one row per night":
   **one more click**.

So: one night is readable with zero clicks (but names demoted, absences unsaid), and the
*recent* history is only readable as dots plus hovers. The page has every fact needed to print
the story; it just never prints it.

---

## Findings, most valuable first

### 1. Add "Recent nights": a night-by-night ledger, newest first, one column per scope  (L, page-only)

**Now:** one "Last night" block for one night (built overview, top card), then dots.

**Change:** replace the "Last night" block with a ledger card titled **Recent nights**:

- **Rows are nights**, newest first, evening -> morning as the page already writes them
  ("Thu 15 -> Fri 16 Oct"). Row head (172 px): date 14/600, under it "15.3 h · 5 objects on
  4 scopes" 12/400 muted. The **first row with frames** gets the eyebrow LAST NIGHT (or
  LATEST FRAMES · 2 NIGHTS AGO) and the date at 18/700, so the morning answer is the biggest
  text in the card.
- **Columns are the six scopes in the importer's fixed order**, each headed by its dot, name
  and "›" (opens the scope's timeline, the existing `openScope`), with a 12 px line
  summarising the range: "5 nights · 9.5 h · 3,455 frames". A scope with nothing in the range
  keeps its place but shrinks to a 108 px column headed "S50 · nothing in 7 nights · last out
  30 Aug"; its cells are a faint 14 x 2 px dash. The active columns share the rest
  (about 220 px each at 1280 with four active).
- **Each cell holds that scope's objects that night**, biggest first, each a button
  (opens the existing night panel, `openNight(cam, night)`):
  - line 1, 14/600: common name + muted code, the page's existing `nameEl` so the code never
    splits from the name, plus a tiny MOSAIC tag from `targets[].mosaic`;
  - line 2, 12/400: **"503 frames · 1.4 h"** (frames first, because that is the number Brett
    says out loud; "hours unknown" when the exposure is missing, never 0.0 h);
  - line 3, 12/400 muted: how it was shot, "10 s LP" or "300 s L-eXtreme", and for the
    ZWO scopes the calibration filed that night: "✓ 30 darks · 25 flats" or
    "⚠ no darks or flats filed" in the warm warning colour. Seestars show nothing here
    (they calibrate in the camera, which the night panel says).
  - a 3 px bar in the scope's colour, width = this object's hours against the biggest in the
    range (dashed outline when hours are unknown). It is the same "bigger is more hours"
    rule as the dots, so the eye still gets the weight of a night without reading.
- **An empty cell in the top row says "not out"** in words; in older rows it is the dash.
  That is the "the 107PHQ did nothing" line, printed, zero clicks.
- **Blank nights collapse into one thin row**: "The last 2 nights · Sat 17 -> Mon 19 Oct ·
  no frames on any scope · latest frames 2 nights ago". Inside the range, a run of blank
  nights becomes "Tue 6 -> Thu 8 Oct · 2 nights · no frames on any scope". The page may only
  claim this for nights up to `asOfNight`; a night after the record was built is not shown
  as blank (see finding 7).
- **Range control** top right, the page's segmented style: **a week** (default) · 14 nights
  (the quiet period, matching the strip's band) · 30 nights. Remembered like the strip's range.
- Footer line: "In these 7 nights: 7 nights with frames · 61.2 h · 8,421 frames · 15 objects
  on 5 scopes", a three-item key (bar = hours, dashed = hours unknown, dash = not out), and
  the keyboard line (Tab to a night, left/right across the scopes, Enter opens the night).

**Why:** it is Brett's point 1 verbatim. The morning question becomes the first row of the
first card. The week reads as a story down the page, and each scope reads as a story down its
column ("the FRA400 has been on the Swan every clear night"). Nothing is hidden behind a hover.

**Mockups, built from the real-size dataset** (87 targets / 505 sessions,
`R/truth/stress-dataset.json`), with its six scopes renamed and recoloured to Brett's six in
his order, `asOfNight` moved to 18 Oct and the "still on the camera" numbers taken from
11.webp, so the picture shows his real situation of 19 Oct:
- `history-week-1440.png`: the default, a week.
- `history-30-1440.png`: 30 nights, to show it holds up at the busiest range
  (22 nights with frames, up to three objects on one scope in one night).
- Source: `mock-recent-nights.html` (`__DATASET__` slot) -> `recent-nights-rendered.html`.

Known rough edge of the mockup, not of the design: catalogue codes wrap away from the name
("NGC / 7320") because the mock has a plain name splitter; the built page's `nameEl` already
keeps name and code together and clamps to two lines, and should be used.

**Fields:** every one already exists in `sessions[]` since 1.7.2 (`astro-import.py:11289`,
`:11475`): `night`, `morning`, `camera`, `target`, `frames`, `hours`, `exps`, `filters`,
`gains`, `importedOn`, `archived`, `calDetail` / `cal`, `framesWithoutExposure`,
`integrationFromNote`; plus `targets[].mosaic`, `scopes[].order / colour / last`,
`asOfNight`, `quietPeriodDays`. No engine change.

**Effort:** L on the page (roughly the size of `renderStrips`); reuses `fmtNight`, `nameEl`,
`camDot`, `openNight`, `openScope`, `hoursTxt`, `calLine`, the segmented control and the
tokens. Replaces `renderLastNight` rather than adding to it.

### 2. Put "still on the camera" at the top of the ledger, and let it name the target  (S page / M engine)

**Now:** the header's warning line (11.webp: "87 files on the ASIAir not yet imported (1
target) · 85 already on the other computer · the lists below don't include them · seen 3 h
ago"), far from the history it qualifies.

**Change:** the same fact as the ledger's first row, in the warm wash the page uses for
warnings: **"⚠ 87 files still on the ASIAir, not yet imported · 1 target · 85 already on the
other computer · seen 3 h ago · not in the rows below"** with a button "Open the Panel to
import" (the Panel tab is where the import happens). The morning after a session the frames
are often *still on the camera*, so this row is the true "last night" until the import runs,
and it must sit above the ledger, not in the hero. Keep the header's short pill; drop its long
sentence (helps point 3).

**Engine:** `last-scan.json` (`save_scan_summary`, `astro-import.py:10038`) stores `files`,
`targets`, `elsewhere`, `camera`, `failedEject`, `seenAt`, `machine`, but **not the names**.
Add `targetNames[]` (the display names the scan resolved) and, for a Seestar, the scope, so
the row can read "87 files still on the ASIAir: **Tadpoles Nebula** · seen 3 h ago". The scan
already knows them (it asks `get_display_name`); this is a pass-through, no new logic.

### 3. Name the objects in the strip's text column  (S, page-only)

**Now:** `stripText` (`astro-observatory.html:1443-1452`) writes
"latest night: 2 objects, 6.2 h (16 Oct)" when a scope did more than one object (7.webp,
8.webp, right column). The names are only in the hover.

**Change:** "**16 Oct**: Tadpoles Nebula 503 frames · Western Veil 245 frames · 6.2 h".
Two names at most; a third and more become "+1 more". With one object keep the current
"latest: Flaming Star Nebula, 13 Oct · 7.1 h". Widths: the column is 520 px at 1440 and the
line is 13 px, so two names and two counts fit on one line; `commonName` already strips
codes.

**Why:** the strip is the summary of the ledger; its text column should say the same names,
so Brett never has to hover to confirm what a dot was.

### 4. Should the dots carry object names at 30 nights? No; the ledger does that job  (no change)

At 30 nights the plot is ~1000 px wide, so each night has 33 px; an object name needs 80 to
180 px, and nights with two or three objects would need stacked labels. Even a week in the
strip would give only ~140 px per night, still not enough for "Open cluster in the
Tadpoles (IC 410)". Labels on dots would collide exactly where Brett looks most (the band).
The honest answer is: the strip stays a shape (when, how much, which scope), the ledger is the
text. The hover and the keyboard walk stay as they are. The one tweak worth making is
finding 3.

### 5. Project cards: say what the latest night was, and open the nights table  (S, page-only)

**Now:** every card (9.webp) ends its meta line with "last 16 Oct". Opening a card (10.webp)
shows the lane, and the per-night table hides behind "3 nights on the S30 Pro: one row per
night".

**Change:**
- Card meta: "63.9 h · 5,603 frames · 29 nights · **latest 16 Oct: 503 frames on the
  S30 Pro**" (from `sessions[]`: the newest session for that target, frames and camera; two
  scopes the same night -> "503 on the S30 Pro + 60 on the FRA400"). One line, no new fields.
- In the opened panel, show the nights table **open by default when the lane has eight nights
  or fewer** (it already sorts newest first, `nightRowsFor`, line 1258), collapsed with the
  count only above that. The table is the project's own ledger; hiding three rows behind a
  click saves nothing.

### 6. Page order: history first, decisions second  (S, page-only)

**Now** (built overview): Last night -> Needs your attention (~700 px) -> the strip -> What to
do next -> Projects that moved lately. With the double header that puts the dots ~1,400 px
down at 1440 wide.

**Change:** **Recent nights -> What each scope captured -> Needs your attention -> What to do
next -> Projects that moved lately.** The ledger and the strip are two views of one thing and
belong together; "Needs your attention" keeps its badge count in the nav so nothing is lost
by moving it one card down. This is the 16 Oct "decisions before history" order reversed on
Brett's own instruction (point 1); the earlier order was ChatGPT's, not his.

With finding 2 and the header slimmed (the other reviewers' point 3), the first row of the
ledger should sit within the first ~450 px of the tab at 1440 wide instead of the ~1,100 px
the current Last night block needs below the panel's header.

### 7. Be honest about blank nights and about which computer's record this is  (S, page-only)

The ledger claims "no frames on any scope" for a night. It may only do so for nights up to
`asOfNight`, built into the record by the PC nightly or the Mac on demand. When the record is
older than last night (the Mac's copy from yesterday, 11.webp's "the Mac's copy is from
today"), the top row must read "**record built 19 Oct 2026, 03:38** · nights after it are not
in this list", not "no frames". Fields: `asOfNight`, `generatedAtLocal`, `machine`. Also, when
a session's `archived` is below its `frames`, add "· not all on the archive yet" to its
third line (the ship has not run); `importedOn` ("on the PC") stays in the night panel, where
it already is.

### 8. A week view: yes, as the ledger's default, not as a strip range  (covered by 1)

A week of dots is seven dots and tells nothing; a week of rows is the story. The strip keeps
30 / 90 / a year / everything; the ledger gets a week / 14 / 30. The two controls are
different because the two cards answer different questions (what and how much, vs when and
how often).

### 9. Narrow screens  (M, page-only, after 1)

Under 900 px: the quiet scopes drop to a footer line ("Not out in these 7 nights: S50 (last
out 30 Aug)") and only active scopes get columns. Under 700 px (phone): one column; each
night is a block with the date, then one line per object with the scope's dot and short name
first ("● S30 Pro · Tadpoles Nebula · 503 frames · 1.4 h"), tappable at 44 px, blank runs as
one line. Same data, same order, no horizontal scroll.

---

## Keep as it is

- The strip's rules: six lanes in the fixed order, one dot per night, bigger is more hours,
  hollow when hours are unknown, the shaded last-14-nights band, the week/month bins past
  120 nights with the count inside the dot, the text column per lane, the dots sliding on a
  range change, the keyboard walk (Tab, left/right, Enter, Esc). This is the part Brett said was
  "the right direction".
- The night panel's content (`final-1440-night-panel.png`): frames, hours, exposure, filter,
  gain, the calibration block, "on the archive", "imported on", Open folder. The ledger opens
  it; it does not duplicate it.
- The opened project card's "one lane per scope" with the three marks and the Next column.
- "Night of Thu 15 -> Fri 16 Oct" wording (noon to noon) everywhere.
- Scope colours and order from the dataset, never from the page.
- Unknown is never zero ("hours unknown · 2,150 frames").
- The latest-night date in brackets on the strip's text column "(16 Oct)"; keep the date
  when finding 3 adds the names.

## Files in this folder

- `findings.md`: this file.
- `history-week-1440.png`, `history-30-1440.png`: the mockups.
- `mock-recent-nights.html`: the mockup source (`__DATASET__` slot).
- `dataset-history.json`: the real-size dataset with Brett's scope names, colours and order,
  `asOfNight` 2026-10-18 and the 19 Oct pending-import numbers.
- `recent-nights-rendered.html`: the mockup rendered with that dataset.
