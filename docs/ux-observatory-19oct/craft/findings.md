# Observatory round 3 · lens: craft (does it look top class, with nothing that means nothing)

Reviewer: craft. Looked at Brett's five Safari shots (light), the `built/` shots (dark), directions A and C, SPEC.md, the five R reviews, and the built page's CSS (`astro-observatory.html` lines 12–649) and renderers (`renderStrips` ~1452, `buildStrip` 1120, `projCard` 1532, `ring` 1517, `pill` 853). Every colour number below was computed (WCAG contrast; the dataviz validator on the six scope colours), not eyeballed.

Mockups (all in `/tmp/claude-0/-home-user/c23ee14e-85ed-5f5b-94f9-0fb713d6fb24/scratchpad/ux3/craft/shots/`, 1440 px wide unless named `-2x`), each built from a copy of the page with **CSS only** (`polish.css` in this folder, appended after the page's own style; the shoot script is `shoot_file.sh`, the page is `observatory-current.html` rendered from the sample dataset):

| Pair | Before | After |
|---|---|---|
| Scope strip, 30 nights, light | `before-light-strip30.png` | `after-light-strip30.png` |
| Scope strip, 90 nights, light | `before-light-strip90.png` | `after-light-strip90.png` |
| Scope strip, 30 nights, dark | `before-dark-strip30.png` | `after-dark-strip30.png` |
| Scope strip, 90 nights, dark | `before-dark-strip90.png` | `after-dark-strip90.png` |
| Project cards, light | `before-light-proj.png` | `after-light-proj.png` |
| Project cards, dark | `before-dark-proj.png` | `after-dark-proj.png` |
| One card (Andromeda), 2×, light | `before-light-card-2x.png` | `after-light-card-2x.png` |
| One card (Andromeda), 2×, dark | `before-dark-card-2x.png` | `after-dark-card-2x.png` |

Three things in `polish.css` are mockup tricks, not the real build: the shorter sub-lines are injected with `::before` (the real text lives in JS), the dot sizes are nudged with `[r^="…"]` selectors (the real change is one line in `rMax`), and the scope names inside the card rows come from the dot's `title` (the real build prints the scope's short name). Everything else in the file is the spec as written.

---

## The verdict in one paragraph

The build is faithful to SPEC.md and the tokens are in place, so the bones are right. It looks "mushy" rather than "top class" for four reasons that are all finish, not structure: (1) the light theme has no contrast between its layers (page / card / inner card are three warm greys within 1.2:1 of each other, and the hairlines are 1.3:1) so nothing lifts off anything; (2) too many marks mean nothing: 180 "no frames that night" dust dots, a solid grey quiet band, a legend and a keyboard-hint row under every strip, five sample pills in the header, a border + a tint + a shadow on every card; (3) the numbers Brett reads first are the same size as the words around them (12–13 px, just bolder), so the hierarchy inside a card is weight-only, which reads as noise; (4) the scope, which he says is the point, is shown on the cards by colour alone: a ring, a dot in a pill, dots on a lane, and no scope name anywhere on a card. Fix those four and the page looks like the mockups he liked.

---

## Ranked findings

### 1. Project cards show the scope by colour only · page-only · S
**Now** (9.webp, 10.webp; `projCard` lines 1535–1537): a 56 px ring, a 10 px dot inside each pill, dots on the mini lane. Not one scope name on a card. Brett has two amber-ish and two near-grey scopes (S30 Pro amber, S50 near-black, S50 Pro slate/green); the colour review already said a scope colour never appears without its name in the same card (R/colour finding 2). Andromeda's card has four unlabelled colours.
**Change:** replace the stack of five pills by one row per scope, in the fixed order: `● Askar FRA400 ………… ◑ Finish it`. Scope dot + short name at the left in 12/600 ink; the next step at the right as glyph + word in the step's ink (Ready to process in bold ink; Finish it and Still capturing in teal; Done and Quick look muted); 26 px rows with a hairline between. No filled pills on the card. (After-mockup: `after-light-card-2x.png`.) The rows take the same height as the pill stack (Andromeda: 4 × 26 = 104 px vs 4 × 30 = 120) and now name everything.
**Why:** his point 1 (what was captured onto which scope) and point 2 (five filled pills on one card is the loudest thing on the page and says the least).

### 2. The light theme is washed out: the layers do not separate · page-only · S
**Now** (7.webp, 9.webp): page `#f3f0e8`, card `#fffdf9`, inner card `#f7f4ec`: 1.12:1 page-to-card. Hairline `#e1dbce` on the card is 1.3:1. Ring track, quiet band, empty dots, dividers are all this same warm grey. Most of the words on the page are muted (`#6b6a7e`, 5.2:1) or ink2 at 12–13 px. The data colours are the only saturated thing and they are 6–24 px marks.
**Change:** the light tokens in the table below: page a touch darker (`#eeeae0`), card whiter (`#fffefb`, page-to-card 1.19:1, visibly a card), hairline `#d9d3c5` (1.48:1, visible), secondary ink `#403e52` (10.3:1) and muted `#625f74` (6.1:1 on the card, 5.1 on the page). Fewer grey marks (findings 4, 5, 7). Project cards sit on the page as white cards (finding 6), not beige boxes inside a white box.
**Why:** point 2. Compare `before-light-proj.png` with `after-light-proj.png`: the same content, and the cards now read as cards.

### 3. The numbers Brett reads first are not bigger, only bolder · page-only · S
**Now** (7.webp right column, 9.webp stat line; `stripText` 1443, `.proj .hl` CSS line 430): "**14.0 h** over **7 nights**" and "**63.9 h** · 5,603 frames · 29 nights" are 12–13 px with two bolds in one phrase. The section headings are 20 px; everything under them is 12–13. One jump, then flat.
**Change:** the lead number 15/600 in ink (`14.0 h`, `101.7 h`), the sentence around it 13/400 in ink2, one bold per line (so "over 7 nights" loses its bold). Scope names in the rail 14/600. Card title stays 16/700 with codes 13/400 muted. That gives three levels inside every block: title → number → words.
**Why:** point 2. Hierarchy comes from size steps (13 → 15 → 16 → 20), not from weight alone, which Windows renders unevenly (R/type finding 1).

### 4. The 180 "no frames that night" dots · page-only · S
**Now** (8.webp; `updateStrip` ~line 1150: `r:2.2, fill:var(--track)`): at 30 nights every empty night on every lane gets a 4 px grey dot: 6 × 30 = 180 marks at 1.1:1 contrast, and a legend entry that has to explain "(30 nights only)" because they vanish at 90. A rule that needs a footnote is the wrong rule.
**Change:** remove them. The lane's hairline already says time passes, the axis says when. If Brett wants to see the calendar grain, draw one 1 px vertical hairline per week (Monday) across the plot in `--grid`: four lines, not 180 dots, and they mean "a week". The legend loses an entry.
**Why:** point 2 ("every mark must mean something"). In `after-light-strip30.png` the lanes read instantly.

### 5. The quiet band is a grey slab, and it is explained twice · page-only · S
**Now** (7.webp, 10.webp; `svg .band` CSS line 381, `--quiet-band` .06): a solid grey rectangle the full height of the strip, repeated as a smaller box on every mini lane (where it looks like a disabled button, 9.webp), plus a legend swatch "the last 14 nights", plus in the project panel a 170-character line "shaded: the last 14 nights · a dataset is usually still capturing while its last dot is in there; you can override that".
**Change:** tint `.045` light / `.055` dark, a 1 px left edge in `--line`, and a label inside the band's top-right corner in 11/400 muted: "last 14 nights". Then the legend swatch and the explanatory line go. On mini lanes the band is 18 px tall (not the full 26) with the same edge and no label.
**Why:** point 2. The band is important (it is the rule that decides "still capturing"), so it should be quiet and self-labelled, not loud and footnoted.

### 6. Card chrome: a border, a tint and a shadow on every level · page-only · S
**Now** (9.webp; `.card` CSS 220, `.proj` 421): section card (white, border, shadow) → project card (beige `--card2`, border, hover shadow). R/type finding 5 warned against exactly this. The beige-in-white is what makes 9.webp look like a form.
**Change:** the "Projects that moved lately" section is a region, not a card: its heading sits on the page, and the project cards are the cards: `--card` background, 1 px `--line`, radius 12, shadow `0 1px 2px`, hover `0 6px 18px` at 10 % (45 % dark). Grid gap 20. Cards stretch to the row's height with the mini lane pinned to the bottom (`margin-top:auto`), so every lane in a row sits on one line (see `after-light-proj.png`: the three lanes align at y = 349).
**Why:** point 2. One border per level; the eye gets one rhythm (strip card, then a grid of cards).

### 7. Legend and keyboard hints under every strip · page-only · S
**Now** (7.webp bottom, 10.webp; `renderStrips` ~1470–1472): two rows on every strip: five legend items and four `Tab / ← → / Enter / Esc` hints, 60 px of the card, repeated in the project panel. Brett drives this with a mouse.
**Change:** the keyboard row shows only when the keyboard is in the strip (`.card:focus-within .keys{display:flex}`, otherwise hidden; the lane's aria-label already tells a screen reader). The legend keeps two items at most (a night out · bigger is more hours; hollow = hours unknown) plus the week note at 90+; the band is labelled in place (finding 5) and the dust dots are gone (finding 4). Section sub-lines become one short fact ≤ 72 characters ("a dot per night out · bigger is more hours · shaded: the last 14 nights"); the "hover, tap or focus a dot" and "click a scope's name" instructions move into the dot's tooltip and the name's `title`, which already exist.
**Why:** point 2 and point 3 (every repeated row is height before the next useful thing). The strip card drops from 460 px to 400 px at 1440.

### 8. Dots: the scale is wrong at both ends · page-only · S
**Now** (`rMax` 1085, `rOf` 1086): at 30 nights r runs 3 → 12 (6 → 24 px). The 24 px dots in 8.webp (S50 Pro lane) nearly touch their neighbours and dominate the strip; the 6 px dots are under the 8 px marker minimum, and a 6 px blue dot and a 4 px grey "empty" dot (finding 4) are hard to tell apart. White 10 px counts inside week dots fail on amber and mint (2.2:1).
**Change:** r 4 → 9 at 30 nights (8 → 18 px), 4 → 7 at 90, 3.5 → 6 at a year; the surface ring on every dot 2 px (now 1.5); hollow dots 2.5 px stroke. Count text inside dots and the labels inside the share bar are always near-black `#15141f` (5.0:1 on the red, 5.6 on the blue, 8.4 on the amber, 7.9 on the mint, 5.1 on the purple, 5.3 on the grey; white fails on four of the six). Same rule in dark: the scope colours do not change with the theme, so neither does the ink on them.
**Why:** point 2. The validator result for the six contract colours: amber and mint sit at 2.1–2.2:1 on the light card ("relief required"), which the 2 px ring plus the named rail provides; the grey S50 fails the chroma floor (reads as "empty"), which is one more reason no other grey mark may share a lane with it (finding 4).

### 9. The ring: 8 px stroke, and nothing says what it is · page-only · S (keep it, label it)
**Now** (9.webp; `ring` 1517): 56 px, 8 px stroke, the track in the same grey as the quiet band; a one-scope project is a full circle, which the dataviz rules call a one-slice donut. The sub-line says "the ring is hours by scope" once, 600 px away.
**Change:** keep the ring: on a one-scope project it is the scope badge (the thing Brett looks for first), on a multi-scope project the split of hours. Stroke 7 px, 2 px gaps, track one step off the card (`--track`), and the rows of finding 1 directly under it name every colour the ring uses. Hover already gives hours per scope. Do not put a number in the centre (R/type 13). If Brett wants the ring to say more, the honest extra is a thin outer arc for "hours against the biggest moved project", but only if he asks; it is not needed for the ring to mean something once the scopes are named.
**Why:** point 4 ("donut graphs" were promised in A and are built; what was missing is the label, not the chart).

### 10. The mini lane loses the scope on a shared night · page-only · S
**Now** (9.webp Andromeda "‹28 ❸", Triangulum "❷"; `projCard.fitMini` ~1541): a night with two scopes is a grey ink dot with a count, and only the card's tooltip says why. On a card whose purpose is "which scope", a grey dot is a hole.
**Change:** draw a shared night as a split dot: two half-discs in the two scope colours (three sectors for three), the count inside in `#15141f` if r ≥ 6.5. Add three month ticks under the mini lane in 11/400 muted (A had them; the built card has only "‹28" and the band), e.g. "Aug · Sep · Oct", so the lane says when as well as what.
**Why:** point 1 and point 4 (A's card had dated, scope-labelled lanes; the build has one undated mixed lane).

### 11. Per-scope lanes inside the card, as A drew them · page-only · M
**Now:** A's project card (`A-desk-lower.png`) had one labelled lane per scope ("107PHQ / S30 Pro") inside the card; the build collapsed that to one mixed lane and moved the per-scope lanes into the opened panel.
**Change:** for projects with 2–3 scopes, draw one 18 px lane per scope inside the card, each lane keyed by the row of finding 1 (same order); 4+ scopes keep the mixed lane with the split dots. This is the "history, on which scope" picture Brett screenshotted, visible without opening anything.
**Why:** point 1. Ranked after the S items because the split dot (finding 10) gets most of the way there at a tenth of the work.

### 12. The hero: a 440 px slab on a light page, carrying a key for things that are not there · page-only · S–M
**Now** (11.webp, 2000 px wide): panel header 0–115, tabs 115–180, "Worked out … Refresh now" 180–250, the night-sky hero 250–690: 690 px before "Last night". Inside the hero: eyebrow, title, freshness line, a two-line warning, a 36 px share bar with white labels inside amber and green (2.2:1), a six-column key that repeats the bar's numbers, then a legend strip with the six scope dots, five sample status pills and three marks, then the nav. The legend strip is 70 px of pills that point at nothing: a pill means something next to a project, not in a row by itself.
**Change (the look; the other reviewers own the height budget):** the hero is a band, not a slab: ≤ 200 px at desktop. Eyebrow + title on the left, the hero number 48/700 with "hours of integration" 16/600 on one baseline on the right, the four companions at 14/600 (not 13/400) under it; the freshness line 13; the share bar 24 px tall with the key under it in one six-column row (name 12/600, hours 14/600 tabular, "29% · 115 nights" 12/400), labels inside the bar only where they fit, in ink `#15141f`; the legend strip removed entirely (status pills are glyph + word, self-explaining where they occur; the two "unknown" marks are explained once, where they appear). Keep it dark in both themes: it is the identity, and a dark 200 px band on paper looks like a masthead; a dark 440 px block looks like a different app bolted on.
**Why:** points 2 and 3.

### 13. Share-bar and dot text in white · page-only · S
Covered inside findings 8 and 12; listed so it is not lost: every label set on a scope colour is `#15141f`, never white, never the theme ink.

### 14. The right column truncates the one fact a quiet scope has · page-only · S
**Now** (7.webp, 8.webp): "nothing in 90 nights · last out 24 May 2026, 147 nights …" ellipsised at 330 px.
**Change:** "nothing in 90 nights" on line one in muted; "last out 24 May · 147 nights ago" on line two in ink2, the year only when it is not this year. Column 320 px, gap 20, rail 184 px (`after-light-strip30.png`).

### 15. The "›" and the hairlines in the scope rail · page-only · S
**Now** (7.webp): each rail name and each right-column row has its own hairline underneath, but the plot between them has none, so the strip reads as two little tables flanking a chart. The "›" after every name is a seventh mark per row.
**Change:** no hairlines in the rail or the column; the lane's own centre hairline is the only rule. Keep the "›" at 70 % (it is the only hint the name is a button).

---

## Where the build fell short of A and C (the mockups Brett liked)

| In A / C | In the build | Finding |
|---|---|---|
| A: one labelled lane per scope on every project card, with month ticks | one mixed lane, no scope names, no ticks, a grey dot for shared nights | 1, 10, 11 |
| A and C: cards on the page in a light grid, one border per level | beige cards inside a white section card inside a cream page | 6, 2 |
| C: the archive's numbers as tiles with 28 px figures | companions at 13 px in the hero | 12 |
| A: the ring as the first thing on the card, big and legible | 56 px, 8 px stroke, same grey track as the band, unlabelled | 9 |
| R/type: numbers bigger than their words, one bold per line | 12–13 px with two bolds per phrase | 3 |
| R/colour: a scope colour never without its name in the card | ring, pill dots, lane dots, no names | 1 |
| R/colour: text on a colour chosen by luminance | white on amber and mint in the share bar and week dots | 8, 13 |
| SPEC §4: 24 chip / 32 button, one spacing ladder | kept, and it shows; the ladder is fine | keep |
| SPEC §1.1: legend strip in the header | built as specified; I am arguing against it | 12 |

What the build does better than A or C and must stay: the status glyphs (A's shapes), the ink-solid "Ready to process", the hollow dots, no glow anywhere, the hover ring on dots, the segmented range control, the week-cluster counts at 90+, the sticky nav, the shorter names with muted codes.

---

## The polish spec

### Colour tokens

Light (every value checked against `--card` unless stated):

| Token | Built | Craft | Note |
|---|---|---|---|
| `--page` | `#f3f0e8` | `#eeeae0` | paper, one step darker so cards lift |
| `--card` | `#fffdf9` | `#fffefb` | 1.19:1 against the page (was 1.12) |
| `--card2` | `#f7f4ec` | `#f6f3eb` | inner tints only (queue cards); project cards use `--card` |
| `--line` | `#e1dbce` | `#d9d3c5` | 1.48:1: a hairline you can see |
| `--grid` | `#ebe6da` | `#e8e3d7` | lane hairlines |
| `--ink` | `#1a1926` | `#15141f` | |
| `--ink2` | `#4e4c60` | `#403e52` | 10.3:1 |
| `--muted` | `#6b6a7e` | `#625f74` | 6.1:1 on the card, 5.1 on the page |
| `--faint` | `#a09ead` | `#a39fae` | ticks and dividers only, never text |
| `--track` | `#e6e1d6` | `#e2ddd1` | ring track, bar track |
| `--quiet-band` | rgba(26,25,38,.06) | rgba(26,25,38,.045) | plus a 1 px left edge in `--line` |
| `--shadow` | 0 1px 2px .05 | 0 1px 2px rgba(26,25,38,.06) | rest |
| hover shadow | 0 4px 14px .08 | 0 6px 18px rgba(26,25,38,.10) | cards only |
| `--st-quiet-line` | `#c9c4b8` | `#c4bfb2` | |

Dark:

| Token | Built | Craft | Note |
|---|---|---|---|
| `--page` | `#0e1222` | `#0d1120` | |
| `--card` | `#171c33` | `#181d36` | 1.13:1 against the page; the border does the rest |
| `--card2` | `#1d2340` | `#1f2544` | |
| `--line` | `#2c3356` | `#303860` | visible on the card |
| `--grid` | `#252c4a` | `#262d4c` | |
| `--ink` | `#f1efe8` | `#f3f1ea` | |
| `--ink2` | `#c1c5d9` | `#c6cadc` | 10.2:1 |
| `--muted` | `#959bba` | `#9aa0bd` | 6.4:1 |
| `--track` | `#2a3152` | `#2c3456` | |
| `--quiet-band` | rgba(241,239,232,.07) | rgba(241,239,232,.055) | |
| `--shadow` | 0 1px 2px rgba(0,0,0,.35) | 0 1px 2px rgba(0,0,0,.40) | hover 0 6px 18px rgba(0,0,0,.45) |

Both themes, fixed: `--on-scope: #15141f` for any text drawn on a scope colour (share-bar labels, counts inside dots). The six scope colours stay exactly as the dataset gives them. Teal stays the one accent (`#086b80` light / `#5cc9de` dark on text; 6.1:1 and 8.6:1). The night-sky header keeps its own `--sky-*` inks in both themes.

### Type (the scale is right; the roles are what change)

Sizes 11 / 12 / 13 / 14 / 16 / 20 / 28 / 48, weights 400 / 600 / 700, system sans, mono only for paths and timestamps.

| Role | Size / weight / colour |
|---|---|
| Section heading | 20 / 700 / ink, letter-spacing −.01em |
| Section sub-line | 13 / 400 / muted, one line, ≤ 72 ch, a fact not an instruction |
| Scope name in the rail | 14 / 600 / ink (muted when quiet) |
| Lead number (strip column, card hours) | 15 / 600 / ink, tabular, number and unit never split |
| The sentence around a number | 13 / 400 / ink2, at most one bold |
| Meta (type · constellation, "last 15 Oct") | 12 / 400 / muted |
| Card title | 16 / 700 / ink + codes 13 / 400 / muted, clamped to two lines |
| Scope row on a card | 12 / 600: scope name in ink, the step in its state ink (Ready to process 700) |
| Axis and ticks | 11 / 400 / muted, tabular |
| Count inside a dot / label inside the share bar | 10 / 700 and 11 / 600, `#15141f` |
| Hero number | 48 / 700 proportional figures; unit 16 / 600; companions 14 / 600 |
| Keyboard hint | 11 mono in a `kbd` box, shown only on focus-within |

### Spacing (4 px ladder, as SPEC §4; these are the exact values the mockup uses)

Section gap 24 · card padding 20 (16 under 1200) · heading to content 20 · strip: rail 184, plot `1fr`, column 320, column gap 20, lane height 40, axis 6 under the plot, legend 16 under the axis · project grid gap 20 · card head padding 16 16 6, ring 56, head gap 14 · scope rows 26 high, hairline between, 10 above the first · mini lane padding 8 16 14, pinned to the card bottom · pills (where they remain: the queue, the panel's NEXT column) 24 high · buttons 32 high.

### Radii and shadows

Section card 10 · project card 12 · pill 999 · button 6 · quiet band 4 · kbd 4. Shadows as in the token tables; no glow, no text-shadow, no `drop-shadow` on marks (already true: keep it that way).

### Marks

Dot r 4–9 at 30 nights, 4–7 at 90, 3.5–6 at a year and beyond; 2 px surface ring (`--card`) on every dot; hollow dot = 2.5 px stroke in the scope colour, card fill; a week dot with ≥ 2 nights carries its count in 10 / 700 `#15141f` when r ≥ 6.5; shared night on a mini lane = split dot; lane hairline 1 px `--grid`; quiet band = tint + 1 px left edge + "last 14 nights" label; ring 56 px, 7 px stroke, 2 px gaps, track `--track`, no centre text; share bar 24 px, 2 px gaps in the sky colour, labels only where they fit, in `#15141f`; hover = ring widens to 3 px + ink stroke (as built).

---

## Keep as it is

- The strip itself: six fixed lanes, dot per night sized by hours, the range control, the sliding dots, the right-hand summary per lane, the "‹N earlier" marker, the week clusters with counts past 90 nights.
- The status vocabulary: five glyphs + words, ink-solid for the one action, teal as the only accent, Done and Quick look outlined. Never a bare coloured dot for a stage.
- Hollow dots and hatched segments for "hours unknown"; "unknown is never 0".
- The 2 px surface ring and no glow anywhere.
- The eight-size / three-weight scale and the 4 px ladder (the tokens are right; only their use changes).
- Common name + muted codes, clamped to two lines.
- Dark theme as a selected palette (it already looks good: `before-dark-proj.png` is close; the dark changes above are small).
- The night-sky header as the identity in both themes (shorter, not gone).
- The opened project panel's SCOPE / HOURS / NIGHTS / CAPTURE · PROCESSING · CALIBRATION / NEXT table (10.webp): the right structure; only its explanatory line shrinks (finding 5).

## Effort summary

Everything above is page-only (no engine field needed; short scope names and `scopes[].order` already reach the page). S items: 1–10, 12–15, together about one working day. M item: 11 (per-scope lanes in the card). Do 2, 4, 6, 7 first: they are tokens and deletions, and they are most of the "washed out" complaint.
