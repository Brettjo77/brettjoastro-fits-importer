# Observatory review, round 3: information hierarchy and the header

Reviewer lens: what the eye passes before the first useful thing, and what the first screen should be.
Everything measured on the page as built (1.7.4, `astro-observatory.html` rendered through the engine with a
dataset that has Brett's 87-files warning), in headless Chromium at 1440 × 900 and 2000 × 1100, and checked
against Brett's own screenshot `images/11.webp`. All heights below are CSS pixels; Brett's Safari screenshot is
about 1.23× these (his window is ~1,620 px wide), so multiply by 1.23 to find them in `11.webp`.

Files in this folder:

- `before-in-panel-1440x900.png`, `before-own-route-1440x900.png`: the page as built, inside the panel's tab and on its own.
- `after-in-panel-1440x900.png`, `after-in-panel-2000x1100.png`: the proposed compact header, history first, inside the tab (the panel's "Worked out … Refresh now" row removed, see finding 3).
- `after-own-route-1440x900.png`, `after-own-route-2000x1100.png`: the same page as its own route (the backlog item).
- `after-header-closeup.png`: the compact header at 1:1. `after-key-open.png`: the Key button open.
- `mock-compact.html`: the mock itself (the built page + one `<style id="compact">` and one `<script id="compact-js">`, built by `make_mock.py` from `observatory-brett.html`; nothing in the repo was touched). `measure.py` prints element heights for any page.

## The measurement: 1,120 px before the thing Brett comes for

What the eye passes, top to bottom, on the Observatory tab at 1440 wide, with Brett's record (two-line camera warning, five warnings):

| # | Element | Where it comes from | Height | Running total |
|---|---|---|---|---|
| 1 | Page top padding | `astro-app.py` `.wrap{padding-top:18px}` (one-page layout ≥ 1001 px) | 18 | 18 |
| 2 | Panel header: logo, "FITS Importer", "by BrettjoAstro · backup-first · everything local", the amber "423 frames only on the Mac", status pills, Rescan / Refresh report / Eject | `astro-app.py:1829-1844`, `.brand` | 68 + 14 gap | 100 |
| 3 | Panel tabs: Panel · To process · **Observatory** · Dashboard · Report | `astro-app.py:1845-1851`, `.tabs` | 43 + 12 gap | 155 |
| 4 | "Worked out 19 Oct 2026, 03:38 · the PC's complete list · 5 warnings (see Data health)" + **Refresh now** | `astro-app.py:1892` `#obsHead`, text set at `:2471` | 39 + 6 gap | 202 |
| | **The Observatory frame begins** | | | **202** |
| 5 | Hero top padding | `astro-observatory.html:148` `header.sky .wrap` | 16 | 218 |
| 6 | Eyebrow "PC · E:\Astro Image Data · from the importer's record" (11 px mono) | `:942` | 13 | 231 |
| 7 | Title "Astro Archive Observatory" (28 px bold) | `:662` | 31 + 8 | 270 |
| 8 | "Record built **19 Oct 2026, 03:38** · the Mac's copy is from today" + the live pill | `renderFresh` `:988-993` | 32 | 302 |
| 9 | ⚠ "87 files on the ASIAir not yet imported (1 target) · 85 already on the other computer · the lists below don't include them · seen 3 h ago · the Mac's scan" (two lines) | `:995` | 36 | 338 |
| 10 | Right half, same rows: **1,326.1** hours of integration (48 px), "light-frame exposure, added up across every target and scope", "120,571 frames · 87 targets · 240 nights · 6 scopes" | `renderHeader` `:943-949` | (inside 6–9) | |
| 11 | Share bar with in-bar labels and tick numbers | `renderShare` `:953-965`, 36 px tall | 36 + 4 | 378 |
| 12 | Share key: six columns, "Seestar S30 Pro / 386.0 h · 29% · 115 nights" | `:966-971` | 34 | 412 |
| 13 | Legend row: SCOPE ● S30 Pro ● S30 … · NEXT STEP five pills · MARKS hours unknown / hours unknown (bars) / the last 14 nights (wraps to two lines) | `legendInto` `:972-981`, `.legend` `:172` | 69 (incl. 12 px rule) + 12 pad | 493 |
| 14 | Sticky view bar: Overview … Data checks ⑤ · "record built 19 Oct 2026, 03:38" · theme toggle | `.navbar` `:198-203` | 49 | 542 |
| 15 | Main top padding | `main{padding:24px 0}` | 24 | 566 |
| 16 | **Last night** card (first content) | `renderLastNight` `:1361` | 127 + 24 | 717 |
| 17 | **Needs your attention** with Brett's five rows (three of them "Something to know") | `renderAttention` `:1417` | ~330–400 + 24 | ~1,100 |
| 18 | **What each scope captured** heading | `renderStrips` `:1457` | | **~1,120** |

So: 202 px of panel before the Observatory starts; 364 px of Observatory header and bar (the hero is 315 of that) before any content; 566 px before the first card; about 1,120 px before the strip Brett opens the page for. His window at 900 tall gives the frame 547 px, of which the hero and bar take 364, leaving **183 px of content on the first screen**: the words "LAST NIGHT" and a date. At 1100 tall the frame is 764 px and 400 px of content shows: Last night and the heading of Needs your attention. **History is never on the first screen at either size.** The frame also has its own scrollbar, so Brett scrolls inside a box that is 61 % of his window (69 % at 1100).

Two more things the measurement shows:

- The same timestamp is written **five times** on one screen: the panel's "Worked out 19 Oct 2026, 03:38", the hero's "Record built 19 Oct 2026, 03:38", the pill "live · 19 h ago", the bar's "record built 19 Oct 2026, 03:38", and the tab line's "the PC's complete list" / the hero's "the Mac's copy is from today" say the same provenance twice.
- The scope colours are explained **three times** in 120 px: the share bar labels, the share key, and the legend's SCOPE row. The "last 14 nights" mark and "hours unknown" dot are explained in the legend and again under the strip (`7.webp`, the row "a night out · bigger is more hours · frames, hours unknown · the last 14 nights").

## Findings, most valuable to Brett first

### 1. Put history first on the Overview (Brett's point 1) — S, page only

**Now:** Overview order is Last night → Needs your attention → What each scope captured → What to do next → Projects that moved lately → Where the hours went (`RENDER.overview`, `:1573-1581`). With five warnings the attention card is 330–400 px of amber boxes, and three of Brett's five are "Something to know" rows with nothing to do.

**Change:** Last night → **What each scope captured** → **Projects that moved lately** → Needs your attention → What to do next → Where the hours went. Last night stays first because it *is* the newest history and is one row. The 16 Oct spec said "decisions first, history after"; Brett's words this morning overrule that for the Overview, and the count badge on the "Data checks" tab already does the attention-getting at the top.

**Effort:** S. Six `root.append` calls in a different order. No engine field.

In the mock the strip heading is at 292 px of the page (449 px of the window inside the tab) and all six lanes are on screen at 900 tall (`after-in-panel-1440x900.png`).

### 2. One compact header: 103 px instead of 315 (Brett's point 3) — M, page only

The design, exactly as in `after-header-closeup.png` (container 1280, night-sky background kept in both themes, stars kept):

**Row 1, 44 px, two lines of 20 px, 10 px padding above**

- Left, line 1: **Astro Archive Observatory** 16 px / 700, then 14 px gap, then the eyebrow `PC · E:\Astro Image Data` 11 px mono, muted. Drop " · from the importer's record": every number on the page is.
- Left, line 2 (12 px, 20 px line): `Record built **19 Oct 2026, 03:38** · Mac copy: today` · the live pill as it is (24 px, five states) · the camera chip (below). The long sentence "the Mac's copy is from today / a day old (15 Oct)" becomes "Mac copy: today" / "Mac copy: 15 Oct, a day old"; the full sentence is the chip's hover text.
- The camera warning becomes a **22 px amber chip**: `⚠ 87 files still on the ASIAir`. Hover shows the whole sentence (targets, "85 already on the other computer", "seen 3 h ago · the Mac's scan"); click opens Data checks. When the engine says nothing is pending: a muted chip `✓ cameras clear · 3 h ago`. When the record did not check (no `pendingImport`): no chip at all; the fact stays on Data checks. Never a tick the engine did not give. Uses `pendingImport` as it is; no new field.
- Right, line 1: **1,326.1** 28 px / 700, then `hours of integration` 13 px / 600. The gloss "light-frame exposure, added up across every target and scope" moves to the number's hover text. The count-up on live refresh stays.
- Right, line 2 (12 px): `**120,571** frames · **87** targets · **240** nights · **6** scopes`, right-aligned under the number.

**Row 2, 31 px: the scope strip and its key**

- An 8 px gap, then the share bar as a **10 px strip** with 2 px gaps between scopes (colours from `D.scopes[].colour`, order from `scopes[].order`), no labels inside it, no tick numbers. Hover a slice for the tooltip it has today.
- 5 px gap, then **one line of key**, 12 px, spread across the width: `● S30 Pro **386.0 h** · 29% · 115 nights   ● S30 **217.7 h** · 16% · 72 nights   …` (short names: drop the "Seestar " / "Askar " prefix; the full name is the item's hover text). Click an item opens that scope's timeline, as the legend's scope buttons do today. If six items will not fit a line (names at Brett's are ~200 px each, 1,200 of 1,232 px), it wraps to a second 16 px line rather than clipping.
- This row is the scope legend. The in-bar labels, the tick numbers and the legend's SCOPE row all go. This also removes the "1 Seestar S50 Pro" look in `11.webp`: the "1" is the share bar's tick number (`s._tick`, `.sharekey .k .no`) prefixed to the name of a slice too thin to label; with no ticks there is no prefix.

**Row 3, 44 px: the sticky bar** (was 49)

- Left: the view tabs as today, 14 px, "Data checks ⑤" badge as today. Padding 10 px per tab so nine fit at 1280 with room.
- Right: `Key` button (32 px, outlined), `Refresh now` button (see finding 3), the theme toggle. The mono "record built 19 Oct 2026, 03:38" goes (it is in row 1).
- **Key** opens the current legend as a panel that drops under the bar (`after-key-open.png`): SCOPE row (clickable), NEXT STEP pills, MARKS. The page already has this fold for phones (`details.keyfold`, `#legendPhone`, `:670`); reuse it for desktop behind the button. The legend is a thing you read once; after that every pill on the page carries its own glyph and word, and the strip and the rings explain their own marks under themselves.

**Totals:** 10 + 44 + 8 + 10 + 5 + 16 + 10 = 103 px of header, 44 px of bar, **147 px** before the page (was 364; 217 px saved, 60 %). With the 24 px main padding the first card starts at 158 px of the frame.

**Effort:** M. CSS tokens and the three render functions (`renderHeader`, `renderShare`, `legendInto`), the `#asof` removal, the Key button. No engine field. Phone width (< 700) already has most of this (hero 34 px, bar 22 px, legend folded); the desktop rules move toward the phone rules, not away from them.

### 3. Remove the panel's "Worked out … · Refresh now" row; put Refresh in the page's bar — S, panel + page

**Now:** `astro-app.py:1892` draws a 39 px row above the frame: "Worked out 19 Oct 2026, 03:38 · the PC's complete list · 5 warnings (see Data health)" and the **Refresh now** button. Every word of it is already in the frame: the time in the hero, "the PC's complete list" in the eyebrow and the live pill, the warning count on the Data checks tab.

**Change:** hide `#obsHead` once the frame has posted `observatory-ready` (`astro-app.py:2469`), and give the page a **Refresh now** button in its bar that posts `{kind:"observatory-refresh"}` to the panel through the `ask()` channel it already uses for `archive-open` (`astro-observatory.html:1713`); the panel's message handler (`:2465`) runs the same code as `#obsRefresh` (`:2454`). While rebuilding, the live pill already shows "rebuilding…", so no second status line is needed. If the page is opened from a file (`window.parent===window`), the button hides, as the Open folder buttons do.

Saves 45 px (row + gap) inside the tab. Panel-side change, no engine field. This is also the first half of the own-route work (finding 9): the page needs its own Refresh either way.

### 4. One timestamp, one provenance — part of 2 and 3

After 2 and 3 the time is written once ("Record built 19 Oct 2026, 03:38"), the pill says the state (live / stale / rebuilding / updated / offline), and the provenance is one line ("PC · E:\Astro Image Data" + "Mac copy: today"). Where a sentence would help ("worked out on this PC from this PC's ledger, the Mac's snapshot of 19 Oct…") it is the hover text of the eyebrow, and it stays in full on Data checks.

### 5. "Needs your attention": fold when nothing needs a decision — S, page only

**Now:** every row is a 56–72 px amber box, including "305 frames were imported on both computers · nothing to do" and "14,379 other files are not light frames · filed, not counted". Brett's five "warnings" in `11.webp` are mostly of this kind.

**Change:** below the history (finding 1), draw the rows with a verb button (Review the names, Say which Askar, Tell the importer the sub length, Show them) as they are, and fold the "Nothing to do" rows into one muted line at the foot of the card: `Also: 305 frames imported on both computers · 14,379 files that are not lights · show`. When *no* row has a verb, the whole card is one line with its count and a "show" link. The count on the Data checks tab is unchanged (every item still counts there).

### 6. Last night as one row — S, page only

**Now:** 127 px: the eyebrow on its own line, a 28 px date, then a row per scope.

**Change:** eyebrow and 20 px date in the left column, the per-scope rows beside them (as in the mock, 110 px with two scopes). The date at 20 px is still the biggest text on the card. Saves 17 px per screen; more when there is one scope.

### 7. The strip card's own chrome — S, page only

**Now (`7.webp`):** under the lanes there is a marks row (24 px) and a keyboard-hints row ("Tab to a lane · ← → walk the nights · Enter open the night · Esc close", 24 px), and above them a 20 px instruction line ("one dot per night … hover, tap or focus a dot for the objects · click a scope's name for its timeline").

**Change:** keep the marks row (it is the strip's own legend and is why the header's MARKS row can go). Show the keyboard row only while a lane has keyboard focus (it is of no use to a mouse, and Brett is reading, not navigating). Shorten the instruction line to "one dot per night a scope was out · bigger is more hours · click a dot for the night, a name for the scope". Saves 24 px always and makes the lanes the first thing under the heading.

### 8. The frame itself: the panel's footer line — S, panel

**Now:** under the frame the panel prints its engine line ("Engine: astro-import.py (backup-first, ASIAir + Seestar) · the ASIAir is never modified · …", two lines at 1440, 56 px with its margin). On the Observatory tab it costs 56 px of a 900 px window and says nothing about the Observatory.

**Change:** hide `.foot` while the Observatory tab is on (one line in the tab click handler, `astro-app.py:1929`). With finding 3 the frame grows from 547 to 648 px at 900 tall (from 61 % to 72 % of the window).

### 9. What the page gains as its own route (backlog), against what can be done now in the tab

**Now, inside the tab** (findings 1–3, 5–8): header 103 + bar 44, the panel's row gone, footer gone. At 1440 × 900 the frame starts at 157 px and shows Last night and all six lanes of the strip; at 2000 × 1100 it shows the strip and the heading of Projects that moved lately (`after-in-panel-*.png`). Still two scrollbars (the page's and the frame's), still 157 px of importer chrome that is about cameras, not the archive, still the frame's inner scrollbar which Safari draws only while scrolling, so the page does not look scrollable.

**As its own route** (`http://127.0.0.1:8765/observatory`, the `← Importer` link already built and hidden at `:676`, as the layout review asked): the 157 px of panel chrome and the footer go; the whole window is the page; one scrollbar; `position:sticky` on the bar works against the window; the browser's Find scrolls the match into view; the URL can be bookmarked, opened in its own tab, or made a Dock app with Safari's Add to Dock (the panel's footer tip, which then applies to the Observatory itself); on a phone the address bar collapses. At 1440 × 900 the first screen is Last night, the whole strip and the heading of Projects that moved lately; at 2000 × 1100 the first row of project cards begins (`after-own-route-*.png`). It also ends the double header for good rather than by hiding rows. What it needs: the panel to open the tab as a link (or a button that navigates) and to keep the live pill's 30 s poll as the only refresh signal; finding 3's in-page Refresh is already half of it.

My order: do 1, 2, 3 and 8 now (one release, all S/M, page and panel, no engine work); 5, 6, 7 with them if time allows; the route next.

### 10. Smaller things seen on the way

- The hero's 48 px number moves by a few hours a week (1,326.1 → 1,332.3). It earns a place as the archive's total, not as the headline; 28 px is still the largest number on the screen.
- `11.webp`: the legend's "NEXT STEP" group is 540 px wide for five pills whose glyph and word are on every pill in the page. After finding 2 it lives behind Key.
- The eyebrow is mono 11 px with `letter-spacing:.08em` and a nowrap ellipsis; at 240 px max it never clips Brett's two paths (`E:\Astro Image Data`, the Mac's `/Volumes/...`). Give it a hover title with the full path.
- The share key in the mock uses `toFixed(1)`; the real page must use its one rounding function so the key's parts sum to the hero (the truth rule).

## Keep as it is

- The six-lane strip exactly as drawn: fixed scope order, dot size = hours, hollow = hours unknown, the quiet band on the right, the per-lane text ("129.5 h over 35 nights · latest night: 2 objects, 6.2 h (16 Oct)"), the 30 / 90 / a year / everything ranges, the sliding dots. This is the thing Brett screenshotted; it must not lose a pixel.
- The project cards: ring of hours by scope, one pill per scope, the mini timeline, and the "one lane per scope" panel with its three marks.
- The Last night card's content: night as "Fri 16 → Sat 17 Oct", a row per scope with object, hours, frames, filter, subs, darks filed.
- The night-sky header as the page's identity, in both themes; keep it dark, keep the stars, just make it short.
- The live pill's five states and the rule that the camera line is never a green tick the engine did not give.
- The Data checks count badge on its tab; it is the attention-getter once the attention card moves down.
- Colours only from the dataset; status as glyph + word; the 1280 px container centred at any width (1440 and 2000 render the same page, as measured).
- The phone rules already in the page (hero 34 px, bar 22 px, folded key): the desktop header should converge on them, not diverge.
