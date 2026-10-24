# Observatory round 3 — lens: colour, contrast and the meaning system

Reviewer: colour. Mocks read: A (light + dark), C (light only), B (dark, reference). Every number
below was computed, not eyeballed: the dataviz validator (OKLab ΔE ×100 under protan/deutan
simulation) and its WCAG `contrast()` export. Demo of the fixes: `demo-colour.html` /
`demo-colour.png` (both themes side by side, real data). Token set: `tokens-colour.css`.

## The five things that matter most

1. **Neither mock's status palette is safe beside the scope palette.** A's "Done" green is the S50 Pro
   green (ΔE 5.9: the same colour), A's "In progress" orange is the S30 Pro amber (5.9), A's "To process"
   pink is the FRA400 red (7.2). C's "Process it" amber is the S30 Pro (10.9), and C also uses that amber
   for warnings, for "Integration unknown" and for the attention numbers: one hue, four meanings.
   It cannot be fixed by picking better hues: I tested every free region (teal, rose) and each lands
   within ΔE 9–13 of a scope. **Fix: status stops being a hue system.** Glyph + word, in ink, fill
   weight for the stage; one accent (teal) for "alive"; ink-solid for the one action. Finding 1.
2. **The contract's six scope colours fail the colour-blind check on their own** (Starfront purple vs
   107PHQ blue ΔE 1.7 deutan; 14.1 normal, below the 15 floor). The page cannot change them, so it must
   never show a scope colour without the scope's name in the same row or card, and the legend strip is
   where the pairing is learnt. A's lanes and C's stripes do this; A's share bar and ring segments do
   not (hover only). Finding 2.
3. **Pill text fails AA in both mocks.** White on A's five badges: 2.5–3.8:1. White on C's teal and amber
   pills: 3.7 and 3.2. C's soft pills 2.8–4.3. These are 12px bold labels that carry the page's meaning.
   The token pills are 4.6–17:1. See the table.
4. **Muted text fails AA in both light mocks.** A `--muted #8b8899` on the card is 3.4:1 (3.2 on job
   cards); C `--ink3 #857f8f` is 3.8:1, and C sets 11px captions, column heads, "quiet for 96 nights"
   and "nights · frames" in it. The darkest tier is fine; the tier Brett squints at is the broken one.
   Tokens: light muted `#6b6a7e` (5.2:1), dark muted `#959bba` (6.1:1).
5. **Glow is kitsch and it fights the data.** A: `box-shadow 0 0 6px currentColor` on every dot, 8px on
   the share bar, `drop-shadow` on every timeline dot, `text-shadow` on the hero. On the cream page the
   halo is a muddy smear (zoom A's queue: the red dot has a pink stain). B: Gaussian halos on ~300 dots.
   Replace every glow with a 2px surface ring (the dataviz rule for overlapping marks); keep at most one
   soft glow, on the hero number in the night-sky header, if any.

## Decision: dark, light, or both?

**Both, selected per theme, dark as the fallback.** At night by the scope (phone, laptop) a cream page
is a torch. By day at the Mac or PC a light page reads better for long lists. A already ships both
(`prefers-color-scheme` + `data-theme`); C is light only and would need the whole dark set added.
- Resolve: `<html data-theme>` (the user's toggle, kept in localStorage) wins; else the OS; else
  **dark**. A small sun/moon toggle in the header row, not a settings page.
- The night-sky header stays dark in both themes: it is the page's identity and carries the hero
  number, the share bar and the tabs. Its ink is its own (`--sky-ink*`), independent of the theme.
- Dark is **selected**, not flipped: the same roles with re-chosen values. Dark card `#171c33` on
  page `#0e1222`; A's `#161b33` on `#0d1125` is too close (cards vanish). Light stays warm paper
  (`#f3f0e8` / `#fffdf9`); dark is cool navy. A warm day, a cool night.

## Ranked findings

### 1. Status colours collide with scope colours (A and C) — severity: critical
**Where.** A: badges, bdots, and especially the *stage dot after the quiet band* on every timeline
(project cards, Targets rows): a plain filled circle in the status colour with no glyph. C: the NEXT
pills, the section-heading squares, the `col` map that paints the timeline's end circle.
**What is wrong.** Against the scope set (normal vision, floor 15): A `#2fb06a` Done ↔ S50 Pro
`#4cbf8a` **5.9**; A `#f0891f` In progress ↔ S30 Pro `#eda100` **5.9**; A `#e8457f` To process ↔
FRA400 `#e05a5a` **7.2**; A `#17a9cc` Still capturing ↔ 107PHQ `#5a8fe0` 9.0; C `#d97706` Process it ↔
S30 Pro **10.9**; C `#0891b2` ↔ 107PHQ 9.1; C `#15803d` Done ↔ S50 Pro 19.9 (passes, by darkness).
In A's Andromeda card the orange "in progress" end-dot sits on the FRA400 lane right beside amber
S30 Pro session dots; in A's Targets row for Orion a green Done bdot sits beside a green S50 Pro dot.
A's review promises "a strong colour AND a shape, so it never collides"; the timeline end-dots have
no shape.
**Why it matters.** Colour is the page's one promise: *this colour is this scope*. The moment a status
wears a scope's colour, every dot has to be re-read. Brett owns an S30 Pro and an S50 Pro; those are
exactly the two hues A spent on "in progress" and "done".
**The fix.** Status = glyph + word, always; never a bare dot. Five shapes (A's set is good: open
aperture, play, half-moon, tick, dashed ring). Colour is tone, not signal:
- Still capturing: teal tint pill, teal text (alive, nothing to do yet)
- In progress: teal solid pill (alive, you are mid-way)
- To process: **ink solid** (the darkest/lightest thing on the page = the one action)
- Done: outline, muted (recedes)
- Sample: dashed outline, muted
On a timeline the stage after the band is the glyph drawn in ink inside a surface ring (demo,
Andromeda card). Teal is the only accent hue; it sits 60° from the 107PHQ blue, is never a dot,
and always carries a word.

### 2. The contract palette is not colour-blind safe and the page leans on it — severity: high
**Where.** A: the header share bar (six unlabelled segments, key on a separate row), ring segments,
"Where the hours went" stacks, the seasons strip. C: "Integration by scope" (thin slices numbered,
good), the season-strip stacks (unlabelled), the chart stacks.
**What is wrong.** Validator on the six contract colours, all pairs: Starfront `#b06ad8` ↔ 107PHQ
`#5a8fe0` ΔE **1.7** deutan / 14.1 normal (FAIL); S50 `#8a8a8a` has zero chroma (reads as "empty");
S30 Pro and S50 Pro are 2.1–2.3:1 on the cream card (below the 3:1 mark floor).
**Why.** A deuteranope cannot tell the Starfront from the 107PHQ anywhere colour is alone; everyone
loses the S50 against the empty-bar track; on the light page amber and mint sink into the paper.
**The fix.** (a) A scope colour never appears without its name in the same row/card: stacked bars
get in-segment labels when wide and a numbered tick + list when thin (C's pattern); rings get a key.
(b) Every mark gets a 2px surface ring (`box-shadow:0 0 0 2px var(--card)`), which lifts amber and
mint off the cream card. (c) The S50 grey must not match the empty track: `--track` is a tinted grey.
(d) Tell Brett the contract pair purple/blue is the risk; the page can only name it.

### 3. Pill and badge text below AA (A, C) — severity: high
A's five solid badges (`#fff` on cyan/pink/orange/green/grey): 2.5–3.8:1. C's solid teal and amber
pills: 3.7 / 3.2; soft pills: teal 3.2, amber 2.8, green 4.3. These are 12px bold; "large text"
starts at 18.7px bold, so 4.5:1 applies. Fixed by finding 1 (teal steps chosen for 4.6:1 light /
6.4:1 dark; ink pills 16–17:1; outline pills use `--muted` at 5.2+).

### 4. Muted text tier fails AA in both light mocks — severity: high
A light `--muted #8b8899`: 3.4:1 on card, 3.2 on `--card2`; A dark muted on card2 4.45 (just under).
C `--ink3 #857f8f`: 3.8 on card, 3.3 on the page, used at 10.5–11px for column heads, "quiet for N
nights", "nights · frames", the season labels, the Why lines. Tokens: light `--muted #6b6a7e`
(5.2 card / 4.8 card2 / 4.6 page), dark `#959bba` (6.1 / 5.6). A fourth tier `--faint` exists for
ticks and dividers only, never text.

### 5. Glow (A, B) — severity: medium-high
A: `.dot{box-shadow:0 0 6px currentColor}`, `.sharebar i{box-shadow:0 0 8px}`, `.scoperows .bar i`
glow, `.glow{filter:drop-shadow}` on every timeline dot, `.bigdot` 12px glow, `.hero .big`
text-shadow. B: `feGaussianBlur` halo under every session dot plus box-shadow on dots and "last"
marks. On the light theme the halo is darker than the surface, so it reads as a dirty shadow; on
dark it reads as "neon dashboard". It also hides the mark edge, so touching dots merge. Fix: no
glow on data; 2px surface ring; hover = ring widens to 3px + tooltip. The header may keep one soft
glow on the hero figure as the single lit element.

### 6. Amber is overloaded (C mainly; A's warnings) — severity: high for C, medium for A
C uses `--st-todo #d97706` for: the Process it pill, the attention numbers (184 / 2 / 2,150), the
attention buttons, "Integration unknown", the calibration ⚠ "Missing flats", section-heading
squares; the S30 Pro is `#eda100` (ΔE 10.9 from it). A uses `--warn-ink #9a4a12` / `#f4b36a` for
warning text and ⚠ icons; the dark warn ink `#f4b36a` is one step from the S30 Pro, and A's dark
warning rows (`#3a2a16` brown) look muddy against navy cards. **Fix:** warnings are ink text + ⚠
glyph on a warm wash (`--attn-wash`), never amber text, never an amber icon. The wash is a
5%-chroma background, never a mark, so it cannot impersonate the S30 Pro. "Fine, nothing to do" rows
are muted + ✓, no green (green is the S50 Pro). C's red Askar callout (`#b91c1c`) sits 13.8 from the
FRA400 red and the note is literally about the FRA400: same treatment, ink on wash with the `?` glyph.

### 7. The "unknown" marks (A's hatch; C's hollow) — severity: medium
A's hatch: 6px pitch, 2.2px lines, 20% tint, used on 5px-radius dots. Zoom the Milky Way row: the
dots look broken or smudged, the ring looks braided. C's hollow dots (white fill, scope stroke) read
cleanly at small size, but C has no hatched area mark for bars. **Fix:** two marks, chosen by size:
hollow (surface fill, 2px scope stroke) under ~14px; hatch at 4px pitch, 1.5px lines, 22% tint for
areas (bars, ring segments). Both in the legend strip. A's `?` dashed-ring glyph stays for
"uncertain, see the note".

### 8. Decorative colour spends the budget (A header, C hero, C headings) — severity: medium
A: yellow tab underline `#ffd166` (ΔE 12 from S30 Pro), green `--ok` text, blue text-shadow, four
season tints behind the month stacks, a warm gradient on "Last night". C: gradient text on the hero
number (navy to violet, the Starfront's hue), coloured squares before every section heading in
status colours that mean nothing there ("Projects" is violet = "Finish it"). Count on A's Overview:
6 scope + 5 status + warning + ok + tab yellow + 4 season tints = 17 meaningful colours. **Fix:**
colour means scope; the selected tab is ink; headings are ink; the hero is the sky's own light ink;
season tints go (the month label says the season). Budget after: 6 scope + 1 teal + ink. Still a
colourful page (the six scopes are everywhere) but every colour on it can be named.

### 9. Dark surfaces too close (A) — severity: medium
A dark: card `#161b33` on page `#0d1125`, card2 `#1c2240`. Cards barely separate; borders do all
the work. Tokens: page `#0e1222`, card `#171c33`, card2 `#1d2340`, line `#2c3356`; `--wash` is ink
at 6%, so hover and the quiet band read the same in both themes.

### 10. Quiet band and "today" line carry a hue (B, C) — severity: low
B's band is violet (`rgba(120,110,255,.13)`), its today line yellow `#fff3c4`; C's band is navy at
8%. On the Starfront's lane a violet band looks like Starfront activity. **Fix:** band = ink at 6–7%;
today = 1.5px ink line. Neither carries a hue.

### 11. B's scope lane wash is right; keep it — note
B's `color-mix(sc 8%)` lane wash puts a scope's colour behind its lane without a glow; adopted in
the tokens as `.sc-lane` at 7%.

## Block by block, A vs C

| Block | A | C | For the blend |
|---|---|---|---|
| Header | night sky; hero + share bar (glow) + key; yellow tab underline | night sky; "last night" chips; no share bar | A's structure; drop glow and yellow; label the share bar in-segment when wide |
| Legend | none (a sentence per card) | one strip: scope / next step / marks | C's strip, fixed scope order, the new glyph set |
| Attention rows | amber text, brown bg in dark | amber numbers, white bg, amber buttons | ink + ⚠ on a warm wash, ink-outline buttons |
| Queue | three columns, scope stripe, hours bar, amber warnings | table with CALIBRATION column, amber "Process it" | A's cards; C's calibration mark in ink + glyph; the action pill in ink |
| Project card | ring + lanes + coloured end-dots + badges | lanes + three indicators + violet "Finish it" | A's ring/lanes; end-dots become ink glyphs; C's three indicators, in ink |
| Unknown | hatch (too fine) | hollow dots, amber note | hollow < 14px, hatch ≥ 14px; note in ink |
| Theme | both | light only | both; dark is the fallback |

## Contrast table (WCAG, computed)

AA needs 4.5:1 for text under 18.7px bold / 24px regular; every pill here is 12px bold.

| Mock | Element | Fg | Bg | Ratio | AA |
|---|---|---|---|---|---|
| A light | body text (ink) | #1c1a2e | #fffdf8 | 16.71:1 | pass |
| A light | secondary (ink2) 12.5px | #55536a | #fffdf8 | 7.30:1 | pass |
| A light | muted 12px (subtitles, axis, 'nights') | #8b8899 | #fffdf8 | 3.40:1 | **FAIL** |
| A light | muted on card2 (job cards) | #8b8899 | #f8f5ee | 3.17:1 | **FAIL** |
| A light | warning text on warn-bg | #9a4a12 | #fff0dc | 5.58:1 | pass |
| A light | 'ok' green text | #1d8a5a | #fffdf8 | 4.27:1 | **FAIL** |
| A light | badge: white on Still capturing cyan | #ffffff | #17a9cc | 2.77:1 | **FAIL** |
| A light | badge: white on To process pink | #ffffff | #e8457f | 3.76:1 | **FAIL** |
| A light | badge: white on In progress orange | #ffffff | #f0891f | 2.53:1 | **FAIL** |
| A light | badge: white on Done green | #ffffff | #2fb06a | 2.79:1 | **FAIL** |
| A light | badge: white on Sample grey | #ffffff | #8188a8 | 3.49:1 | **FAIL** |
| A light | header secondary (hdr-ink2) on sky | #c3c8e6 | #141b45 | 10.00:1 | pass |
| A light | header 'worked out' at 80% opacity 11px | #a0a5c6 | #141b45 | 6.83:1 | pass |
| A dark | body text (ink) | #f2f0ea | #161b33 | 14.88:1 | pass |
| A dark | secondary (ink2) | #b7bbd0 | #161b33 | 8.91:1 | pass |
| A dark | muted 12px | #8188a8 | #161b33 | 4.86:1 | pass |
| A dark | muted on card2 | #8188a8 | #1c2240 | 4.45:1 | **FAIL** |
| A dark | warning text on warn-bg | #f4b36a | #3a2a16 | 7.55:1 | pass |
| A dark | 'ok' green text | #5fd3a0 | #161b33 | 9.13:1 | pass |
| A dark | badges (same hexes as light) | #ffffff | #17a9cc … | 2.5–3.8:1 | **FAIL** |
| C | body text (ink) | #1b1a24 | #fffdf8 | 16.93:1 | pass |
| C | secondary (ink2) 12.5px | #524d5c | #fffdf8 | 8.02:1 | pass |
| C | ink3 11px (nights, frames, 'quiet for', column heads) | #857f8f | #fffdf8 | 3.80:1 | **FAIL** |
| C | ink3 on page bg | #857f8f | #f3eee4 | 3.34:1 | **FAIL** |
| C | pill: white on Keep capturing teal | #ffffff | #0891b2 | 3.68:1 | **FAIL** |
| C | pill: white on Process it amber | #ffffff | #d97706 | 3.19:1 | **FAIL** |
| C | pill: white on Finish it violet | #ffffff | #6d28d9 | 7.10:1 | pass |
| C | pill: white on Done green | #ffffff | #15803d | 5.02:1 | pass |
| C | soft pill: teal on teal tint | #0891b2 | #dff3f8 | 3.21:1 | **FAIL** |
| C | soft pill: amber on amber tint | #d97706 | #fdeed2 | 2.78:1 | **FAIL** |
| C | soft pill: violet on violet tint | #6d28d9 | #ece3fb | 5.73:1 | pass |
| C | soft pill: green on green tint | #15803d | #dcf2e3 | 4.26:1 | **FAIL** |
| C | Sample pill: ink2 on grey tint | #524d5c | #ece9e3 | 6.73:1 | pass |
| C | warn pill: red on red tint | #b91c1c | #fde5e5 | 5.40:1 | pass |
| C | attention button: amber on white 12.5px bold | #d97706 | #ffffff | 3.19:1 | **FAIL** |
| C | attention number 24px bold amber (large) | #d97706 | #fff7ea | 3.00:1 | **FAIL** (just) |
| C | 'Integration unknown' amber bold 14px | #d97706 | #fffdf8 | 3.13:1 | **FAIL** |
| C | header secondary on sky | #c9d0f5 | #1d2a6b | 8.66:1 | pass |
| C | tab count badge | #3a2600 | #ffd48a | 10.32:1 | pass |
| B | secondary ink2 | #b9c3dc | #141c31 | 9.60:1 | pass |
| B | muted | #8692b3 | #141c31 | 5.46:1 | pass |
| B | pill: cyan text on 16% cyan tint | #36d6ea | #193a4f | 6.80:1 | pass |
| **Tokens light** | ink on card | #1a1926 | #fffdf9 | 17.07:1 | pass |
| Tokens light | ink2 on card | #4e4c60 | #fffdf9 | 8.18:1 | pass |
| Tokens light | muted on card / card2 / page (11px+) | #6b6a7e | #fffdf9 / #f7f4ec / #f3f0e8 | 5.18 / 4.79 / 4.62 | pass |
| Tokens light | Still capturing: teal on teal tint | #086b80 | #dcf2f6 | 5.28:1 | pass |
| Tokens light | In progress: paper on solid teal | #fffdf9 | #0f7f95 | 4.60:1 | pass |
| Tokens light | To process: paper on ink | #fffdf9 | #1a1926 | 17.07:1 | pass |
| Tokens light | Done / Sample: muted on card | #6b6a7e | #fffdf9 | 5.18:1 | pass |
| Tokens light | attention text on wash | #1a1926 | #fbf1dc | 15.46:1 | pass |
| Tokens light | attention ⚠ on wash | #7a4a12 | #fbf1dc | 6.65:1 | pass |
| Tokens light | header secondary / muted on sky | #c9cde6 / #a4aacb | #131a40 | 10.69 / 7.36 | pass |
| **Tokens dark** | ink on card | #f1efe8 | #171c33 | 14.60:1 | pass |
| Tokens dark | ink2 on card | #c1c5d9 | #171c33 | 9.80:1 | pass |
| Tokens dark | muted on card / card2 / page | #959bba | #171c33 / #1d2340 / #0e1222 | 6.14 / 5.62 / 6.80 | pass |
| Tokens dark | Still capturing: teal on teal tint | #5cc9de | #21344b | 6.55:1 | pass |
| Tokens dark | In progress: page-ink on solid teal | #0e1222 | #2aa5bd | 6.39:1 | pass |
| Tokens dark | To process: page on paper-ink | #0e1222 | #f1efe8 | 16.18:1 | pass |
| Tokens dark | attention text on wash | #f1efe8 | #36301d | 11.43:1 | pass |

Validator runs (categorical six checks), for the record:
- Contract scopes, light on `#fffdf8`: chroma FAIL (S50 grey); contrast WARN (S30 Pro 2.13, S50 Pro
  2.26; relief = labels + the surface ring); adjacent CVD pass (9.8); all-pairs CVD **FAIL**
  (purple ↔ blue 1.7).
- Contract scopes, dark on `#161b33`: lightness band FAIL (S30 Pro .76, S50 Pro .73, too light for
  dark; unchangeable, so marks get the surface ring); all ≥ 3:1.
- A status ×5, both modes: CVD WARN (green ↔ orange 7.2 protan); chroma FAIL (sample grey); light
  contrast WARN on cyan/orange/green. With the scopes, all pairs: normal-vision **FAIL** at 5.9.
- C status ×5, light: passes its own set; with the scopes, all pairs: **FAIL** (teal ↔ blue 9.1,
  amber ↔ S30 Pro 10.9).
- The token set has one accent hue plus ink, so there is no status palette to collide; it is not a
  categorical palette and is not run through those checks.

## Colour-blind summary
- Scope: the contract pair purple/blue collapses under deuteranopia. Mitigation is structural (name
  beside colour, fixed order, legend strip), and Brett should know the contract is the cause.
- Status: shape first, so safe by construction; the teal accent is never the only signal.
- Warnings: ⚠ glyph + ink, so safe; the wash is a background.
- Unknown: hollow / hatched are shape marks, so safe.
- Print / forced-colors: ink pills and glyph marks survive; add `@media (forced-colors:active)`
  outlines on pills and dots in the build (not drawn here).

## What the demo shows (`demo-colour.png`)
Left dark, right light, same data: a swatch sheet with the tiers' measured contrast printed; the
five status pills and their verb forms; the six scope chips; hollow and hatched unknown marks; an
attention row and a "fine" row; the legend strip; the Andromeda project card (ring with surface
gaps, four lanes, ink stage glyphs after the band, one badge per scope carrying its scope dot, the
Askar note in ink); two queue rows (107PHQ to process with missing calibration; Milky Way Core with a
hatched bar and "hours unknown"); and the six-lane last-120-nights timeline with hollow S30 Pro
dots, the quiet band in ink at 7%, and no glow anywhere.
