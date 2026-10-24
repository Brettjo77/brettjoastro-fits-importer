# Observatory round 3 · lens: typography, spacing, alignment, grid, density, hierarchy

Reviewed: `A/mock-A.html` (+ A-desk, A-desk-lower, A-desk-targets PNGs) and `C/mock-C.html` (+ C-desk, C-desk-2), at 1440 and 1920 wide, plus 2× zooms of the header, totals, queue, project card and target row of each. Numbers below (sizes, weights, paddings) are read from the source, not guessed.

Deliverables beside this file: `demo-type.html` (render with `../../render_mock.py`; `demo-type.rendered.html` is the filled copy), `demo-type.png` (1440) and `demo-type-1920.png` (1920), `tokens-type.css`.

## The five things that matter most

1. **Both mocks have no type scale.** A uses 20 distinct font sizes (9.5, 10, 10.5, 11, 11.5, 12, 12.5, 13, 13.5, 14, 14.5, 15, 15.5, 16, 18, 21, 24, 30, 36, 44) and seven weights (500/550/600/650/700/750/780); C uses 19 sizes and five weights. Half-pixel steps (12 → 12.5 → 13 → 13.5) are invisible as hierarchy but visible as unevenness, and system-ui on Windows snaps 550/650/750 to whatever Segoe cuts are installed, so weight pairs that look distinct on a Mac collapse on the PC. **Fix:** eight sizes (11 / 12 / 13 / 14 / 16 / 20 / 28 / 48), three weights (400 / 600 / 700), set as tokens, nothing in px inline. Severity: **high** (it is the root of half the findings below).

2. **Long names break the layout in both.** Neither mock separates the common name from its catalogue codes, so a wrap lands wherever it lands: A's project card already shows "Christmas Tree Cluster (NGC / 2264)" with the code orphaned; C's queue puts "Andromeda Galaxy (M 31)" on three lines and "Squid Nebula (OU 4)" on three, making a 3-field row 120 px tall. With the real "Open cluster in the Tadpoles (IC 410) (NGC 1893)" (48 chars) A's job card goes to three lines, C's queue cell to five, and C's "Where the hours went" labels (SVG `text-anchor:end` at x=220) run off the left edge of the viewBox and are clipped. **Fix:** split every name into common name + codes (`Open cluster in the Tadpoles` + `(IC 410, NGC 1893)`), codes muted and `nowrap`, the whole name clamped to two lines with the full string in `title`; chart labels truncated at ~28 chars with the full name in `<title>`. Severity: **high**.

3. **Numbers are not set as numbers.** A has zero `tabular-nums`; its Targets "Hours" column is left-aligned (`9.5 hours / 101.7 hours / ? hours`) so the decimal point wanders by two digit-widths from row to row, and the header share-key sets "152.8 h · 101.6 h · 20.4 h" proportionally. C does use `tabular-nums` in `.num` cells (good) but applies it to the 56 px hero figure too, which makes "292.8" loose. Units are inconsistent: A says "9.5 h" in one place and "9.5 hours" in another, C "30.0 h". **Fix:** every column of numbers right-aligned, tabular, with a lighter-weight unit at the same size and baseline (`30.0 h`); hero and tile values proportional; number + unit, dates and "N nights" wrapped in `nowrap` so they never split. Severity: **high**.

4. **Section headings are the same size as item titles.** A: h2 15.5 px/700, project name 14.5 px/700, job title 13.5 px/650, body 15 px: a 1 px step between a section heading and the things inside it. C: h2 16 px/700 and the project summary name 16 px/800: the item is heavier than its section. Neither page has a readable three-level hierarchy per block (section → item → meta). **Fix:** h2 20/700 with a 4 px gap to its 13 px sub-line and 16 px to content; item titles 14/600 (16/700 for project cards); meta 12/400 in secondary ink. Severity: **high**.

5. **Spacing has no ladder.** A uses paddings 16 18 / 12 14 / 10 14 / 9 11 / 8 14 and gaps 14 / 12 / 8 / 6 / 4 between siblings of the same kind; C uses 16 18 / 12 16 / 10 12 / 9 12 / 6 16 and card margins 14 while rows inside use 6 and 10. The page therefore has no vertical rhythm: cards are 14 px apart, items inside them 6–12 px apart, and the two distances are close enough to read as "roughly the same" rather than "section vs item". Accent bars come in 7 px (A job), 6 px (C project), 4 px (C table/lanes); A's bar is a separate grid column with its own radius, so it does not meet the card border cleanly. Chips and buttons have six different heights (20–34 px). **Fix:** 4 px base (4 / 8 / 12 / 16 / 24 / 32 / 48): 24 between cards, 8 between items, 12 item padding, 16 card padding (20 at ≥ 1200); one 4 px accent bar drawn with `box-shadow: inset 4px 0 0` so it follows the card radius; two control heights only (24 chip, 32 button). Severity: **medium-high**.

---

## All findings, ranked

### 1. No type scale (A and C, everywhere) · HIGH
*Where:* every block. *What:* A 20 sizes / 7 weights, C 19 sizes / 5 weights (counted from source). A's `b{font-weight:650}`, `.pill 550`, `.proj .t 700`, `.hero .big 780` all sit on one card. *Why:* the eye reads 12 vs 12.5 as a rendering wobble, not a level; weights between the 400/600/700 stops are not guaranteed to exist in Segoe UI / SF, so the hierarchy changes per OS. *Fix:* tokens in `tokens-type.css`; see the specimen at the bottom of the demo.

### 2. Long names (A job card, A project card, A target row, C queue, C recent captures, C lanes, C hours chart) · HIGH
Details in the top five. Also: A's `.wh .n` (hours chart) is the only place with `text-overflow:ellipsis`, and it is a 230 px column, which cuts "North America Nebula (NGC 7000)" (31 chars) at 13 px once Brett's longer names arrive. C's recent-captures second column at 46 % of a 560 px card wraps "Horsehead Nebula (IC 434)" to two lines for every row. *Fix:* as above; the demo's queue row and project card show the 48-char name on real data.

### 3. Numbers not set as numbers (A everywhere, C hero) · HIGH
Details in the top five. Additionally A's project-card stat line `101.7 h · 4,956 frames · 35 nights · last 15 Oct` wraps after the separator ("…35 nights · / 15 Oct" in A-desk at 1440), and A's quiet-scope line wraps "83 / nights ago". *Fix:* the separator travels with the item that follows it (`<span class=nowrap>· last 15 Oct</span>`), shown in the demo.

### 4. Headings vs item titles (A h2 15.5 vs item 14.5; C h2 16 vs project name 16/800) · HIGH
Details in the top five. *Also:* C's `.proj>summary .nm` at 16/800 inside a `details` is heavier than the page h1 (24/700), so project names shout louder than the page title.

### 5. Spacing ladder and card chrome (A and C) · MEDIUM-HIGH
Details in the top five. *Also:* A nests three bordered boxes (card → column → job, each with a 1 px line and its own background) and adds `box-shadow` on top; C's `.tile` is `#fff` on a `#fffdf8` card, a difference small enough to read as a mistake on a calibrated screen. *Fix:* one border per level; inner items use the `--card2` tint without a border, or a border without a tint, never both plus a shadow.

### 6. Eyebrows and column heads: four styles for one job · MEDIUM
*Where:* A `.eyebrow` (mono 11, .12em), A `.lastnight .when` (mono 12.5, .08em), A `.thead` (mono 11, .06em), A `.asof` (mono 11, lowercase); C `.src` (mono 11, .08em), C `.lastnight .when` (sans 12, .08em), C `th` (sans 10.5, .05em, 700), C `.legend .lab` (sans 10.5, .06em, 700), C `.lanes .hd` (sans 10.5, .05em, 700). *Why:* 10.5 px uppercase bold is below the legibility floor on a 1× Windows monitor; mono column heads make a table read like a terminal, which is exactly what Brett said he does not want ("like looking at Excel"). *Fix:* one `.eyebrow/.colhead` token: sans 11/600, .06em, uppercase, secondary ink. Mono only for machine strings (the `PC · E:\…` path, timestamps, ledger ids).

### 7. Baseline alignment of mixed sizes · MEDIUM
*A header:* "292.8" (44) and "hours of light frames" (13.5) share a baseline (`align-items:baseline`): correct. *A last-night card:* the 30 px date and the session list are `align-items:center`, so the first session line floats above the date's cap height and nothing shares a baseline. *A target row:* "9.5" (18/750) and "hours" (15/400) are inline so they align, but the sub-line "7 nights · 734 frames" is 11.5 px with a 2 px top margin, an uneven stack. *C hero:* `<small>` 18 px rides the 56 px baseline: correct, but the gradient fill (`background-clip:text`) is decoration on the one number that should be plain ink. *C last night:* 30 px date + 14 px small, baseline-aligned: correct. *C tiles:* value 22 / label 12 / sub 11, three levels: good, but the sub wraps to two lines in three tiles and one in two, so the tiles' text blocks have ragged bottoms. *Fix:* big-number + word pairs always inline on one baseline; stat-tile subs get a two-line min-height; drop the gradient.

### 8. Number columns in C's queue and lanes · MEDIUM
*Where:* C `.lanes` grid `150px 132px minmax(220px,1fr) 350px 128px` and C `table.list`. *What:* "Missing darks and flats" at 13/700 wraps to three lines in the 350 px three-indicator cell; "last 12 Jul 2026" breaks as "last 12 Jul / 2026"; the Integration column mixes a 15 px bold value with 11 px muted lines below it, three lines deep, so rows are 90–130 px tall for one dataset. *Why:* the row height is set by whichever cell wraps worst, so every row is a different height and the lanes no longer line up with the timeline axis. *Fix:* numeric cells on one line (`30.0 h`), nights · frames in the next column, dates `nowrap`; indicator cells show the word only, with the detail on hover/below; a row should be ≤ 64 px.

### 9. Pill, chip and button sizes · MEDIUM
*Where:* A `.badge` (12/650, pad 2 9 2 5), `.pill` (12/550, pad 2 4 2 8), `.chip` (12/550, pad 3 10 3 8), `.link` (12.5, pad 3 11), `.attn .act` (12/650, pad 2 10), `.more` (12.5, pad 7 11). C `.pill` (12/700, pad 3 9 3 7), `.att .act` (12.5/700, pad 6 10, r8), `.more` (12.5, pad 5 10, r8), `.ctl button` (12, pad 3 9, r7), `.tbtn` (12, pad 4 9, r8), `.q` 16 px circle. *Why:* heights range 20–34 px and radii 7/8/999 on the same card, so controls read as from different kits. *Fix:* chips/badges 24 px high, pill radius; buttons 32 px high, 6 px radius; nothing else.

### 10. Page width and 1920 behaviour · MEDIUM
A `.wrap` 1240 px, C 1180 px, both centred, header gradient full-bleed. At 1920 both leave 340–370 px of empty paper each side, which is the right call for prose and cards (line length), but C's two-column `row2` (queue beside recent captures) is still 560 px per column at 1920 because the container caps it, so the queue stays cramped at any width. A's 30-night strip stretches to 650 px while its right column is fixed at 330 px: fine. *Fix:* `--container: 1280px` for the Overview; `--container-wide: 1440px` for the data-dense views (Targets list, Pipeline list) so they use the extra room; the header's inner wrap shares the same container so the eyebrow and the first card's left edge line up (they do in both mocks: keep that). Gutter 24 px desktop, 16 px phone.

### 11. Header density · MEDIUM
*A:* eyebrow, h1, freshness line, hero number with five labelled totals, share bar, six-item share key, tab row, and a mono "worked out 16 Oct 2026, 09:12" that repeats the freshness line: eight rows of text before any content, and the scope hours appear three times on the Overview (share key, "whole archive per scope" bars, ring). *C:* lighter (eyebrow, h1, a three-line right-aligned freshness block, the last-night panel, tabs) but the freshness block's third line is a negative statement ("on the camera, not yet imported: not reported by this record") in the most prominent spot on the page. *Fix (in the demo):* header = eyebrow, h1, one freshness line, tabs. The hero and share bar move into the first card, where A's share bar and C's tiles sit together, each scope's hours stated once with a `nowrap` value.

### 12. Line length of explanatory text · MEDIUM
C `#projSub` runs to ~190 characters on one line at 1440 ("41 targets, 50 datasets · three shown here, the rest on the Projects view · a project's badges count … next step"); A's `.sub` under "Projects that moved lately" is ~150 characters; C's `.sub` beside "Integration by scope" is right-aligned and 100+ characters. Comfortable measure is 45–75 characters. *Fix:* `.prose{max-width:72ch}` on every sub/explainer; anything longer is two sentences or a tooltip.

### 13. Rings at 44 px are decoration (A target row) · MEDIUM-LOW
A 44 px ring with a 7 px stroke cannot show a 3 % share (the S50's 1.6 h is a 1.5 px arc), and the 72 px ring on project cards carries "9.5 / hours" with "hours" at 10 px, below the floor. *Fix:* rings ≥ 56 px (`--ring-min`) and no centre text (the stat line beside it already states the hours; a number in a ring and the same number beside it is the same fact twice). In the 44 px row, a single scope dot or a stacked 4 px bar carries the share better.

### 14. Left accent bar as a grid column (A `.job`) · MEDIUM-LOW
The 7 px strip is its own grid column with `border-radius:12px 0 0 12px`, so at the card's 12 px radius it forms a rounded tab that sits 1 px inside the border (visible in the 2× zoom). C's `border-left:6px` on `summary` and `4px` on `td` give two widths on one page. *Fix:* `box-shadow: inset 4px 0 0 var(--sc)` on the card itself (demo queue row): follows the radius, no extra column, one width.

### 15. Mono for human text (A) · LOW
A sets axis ticks, column heads, the "last night out" eyebrow, the footer and the "worked out" line in `ui-monospace`. Mono is for strings Brett might copy (paths, times). *Fix:* sans for all of these; mono only for the eyebrow path and timestamp.

### 16. Tile sub-lines ragged (C `.tiles`) · LOW
"objects you have shot · 1 as mosaics" wraps; "160 sessions" does not; the tiles are the same height (grid) but their text ends at different depths. *Fix:* keep subs to one short phrase ("1 shot as mosaics") and reserve two lines of height.

### 17. Tab count styling (A) · LOW
A's "Data health · 2" sets the count as plain text in the tab label; C's yellow count pill is clearer and is what the demo uses.

### 18. Legend strip repeats the header (C) · LOW
C's legend card ("SCOPE … NEXT STEP … MARKS") is a fourth row of pills and dots before the first content card; with one fixed scope order and one chip style it can be a single line under the share bar, not a card.

---

## A versus C, block by block (which is better crafted, and why)

| Block | Better | Why |
|---|---|---|
| Header | **C** | Less duplication (no second "worked out" line, totals not in the header), one freshness block, the last-night panel is a clean card on the sky. A's share bar + labelled key is the better *element*, so keep it, but inside the totals card. C's three-line right-aligned freshness block should become one line. |
| Totals | **C** (A has none) | Hero + five labelled tiles + one share bar with every scope labelled is the right content and a real three-level hierarchy per tile. Loses points for the gradient number, tabular hero, the numbered 3–6 slivers (numbers under a 4 px segment are not labels), and a two-column legend whose reading order (1,2 / 3,4 / 5,6) does not match the bar's left-to-right order. The demo uses one six-column row in bar order. |
| Queue row | **A** (job card) | Title, scope + hours + nights, bar, note: four lines, one width, compact, nothing wraps at 1440. C's table rows wrap the name to three lines and the calibration text to three lines. But A's numbers are not tabular and its stripe is a separate rounded column. The demo takes A's card and gives it C's columns (right-aligned hours, calibration state, action). |
| Project card | **A** | Ring + name + one-line stat + per-scope timeline + badges is the right density for a grid. C's `details` with a five-column lanes grid is the better *deep dive* but is not a card: rows are 90–130 px tall with wrapped text. A's weaknesses: 72 px ring with 10 px text, the name wraps freely, the stat line breaks after a separator. Fixed in the demo. |
| Target row | A (only A has one) | Good shape; fix the left-aligned hours column, the 44 px ring, the free-wrapping name and the two-row pill stack for four-scope targets (allow pills to wrap but set the row's min height so single-scope rows don't look thinner than four-scope ones). |
| Needs attention | **C** | 24 px tabular number + unit + one bold line + one plain line + one button, in one grid: a proper three-level row. A's single-line amber strips put the count mid-sentence. |
| Charts | tie | A labels every thin bar (good) but uses mono axis text; C's hours chart clips long labels. Both set axis text below 11 px in places. |

## What the demo shows (demo-type.html)

Header (eyebrow, h1, one freshness line, tabs with a count pill); the totals block (48 px proportional hero on one baseline with its unit; five tiles with two-line subs; share bar with a six-column key in bar order, tabular values, `nowrap`); the queue (column heads in one eyebrow style; two rows, the second carrying the 48-character stress name on real data, hours right-aligned and tabular, 4 px inset accent bar, 32 px button); and two project cards (Andromeda's four-scope mixed stages, and the stress name on Triangulum's real data; 56 px ring without centre text, name clamped at two lines with muted codes, separators that travel with their item, 24 px chips). The scale specimen at the bottom lists the eight sizes and the spacing ladder.

Both PNGs were read back; the fixes made after reading were: codes dropping to their own line, a cramped "101.7" inside a 64 px ring, "Jun/Jul" month labels colliding at a timeline's left edge, a three-line hero sub-line, and a separator stranded at a line end.
