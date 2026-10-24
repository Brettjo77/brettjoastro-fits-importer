# Observatory, round 3: "history first" — specification addendum (19 Oct 2026)

This adds to `docs/ux-observatory-16oct/SPEC.md`; everything there still holds unless this
file says otherwise. Brett's words that drove it are in `BRIEF-3.md` beside this file. The five
reviews it is built from are `hierarchy/`, `history/`, `charts/`, `craft/` and `truth/`
(each a `findings.md` and mockups). Brett also sent his own mockup of the scope chart
(`/tmp/claude-0/-home-user/c23ee14e-85ed-5f5b-94f9-0fb713d6fb24/images/13.webp`) and
approved this plan on 19 Oct with the changes written under §3.

Rules that never bend: every mark means something; scope colour comes only from the dataset
(`D.scopes[].colour`) and never appears without the scope's name nearby; unknown hours are
hatched, never guessed; nothing on the page is a judgement, only a fact or a rule; the page
reads, never writes; nothing is loaded from the web; both themes; phone to desktop.

## 1. The Overview, in this order

1. **Recent nights** (new, §2) — replaces the "Last night" block.
2. **What each scope captured** (rebuilt, §3) with **What each scope shot** under it (§4).
3. **Projects that moved lately** (cards reworked, §5).
4. **Needs your attention** (as now; "nothing to do" rows folded into one line).
5. **What to do next** (as now).
6. **Where the hours went** (as now; names must not clip: wrap to two lines).

## 2. Recent nights (history/findings.md §1, mock `history/history-week-1440.png`)

- Rows = nights, newest first, each labelled "Fri 16 → Sat 17 Oct" with "11.5 h · 7 objects on
  5 scopes" under it. Columns = the six scopes in `D.scopeOrder` (the importer's fixed order), each
  head: dot, name, "5 nights · 9.5 h · 3,455 frames" for the range.
- A cell lists that scope's objects that night: name + codes (`nameEl`), "503 frames · 1.4 h",
  "10 s LP" or "300 s L-eXtreme · ✓ 30 darks · 25 flats" or "⚠ no darks or flats filed", and a
  3 px hours bar in the scope's colour (dashed when hours unknown). Empty cell in the newest frames
  row says "not out"; elsewhere a faint dash.
- The top row carries the eyebrow LAST NIGHT, or LATEST FRAMES · N NIGHTS AGO when the newest
  frames are older than last night. Nights with no frames on any scope between then and last night
  collapse into one thin row: "The last 2 nights · Sat 17 → Mon 19 Oct · no frames on any scope".
  Only nights ≤ `D.asOfNight` are called empty; when the record is older than last night say
  "record built … · nights after it are not in this list".
- A scope idle in the range shrinks to a narrow column: "S50 · nothing in 7 nights · last out 30 Aug".
- Ranges: a week (default) / 14 nights / 30 nights, the page's `segRange` control.
- Above the rows, when `D.pendingImport` has files: one warm-wash line "87 files still on the
  ASIAir, not yet imported · 1 target · Tadpoles Nebula · 85 already backed up by the PC · seen 3 h
  ago · not in the rows below" with an "Open the Panel to import" button (posts `{kind:"open-panel"}`
  through `ask()`; the panel switches to its Panel tab). Fields: `pendingImport.files/targets/
  elsewhere/seenAt/ageHours/machine` plus the new `targetNames[]` and `elsewhereMachine`.
- A cell's object opens the night panel (`openNight`); a column head opens the scope's timeline
  (`openScope`).
- Phone (< 700 px): one column, one line per object with the scope dot first; 44 px taps.
  Tablet: idle scopes become a footer line.

## 3. What each scope captured (Brett's mockup, with his agreed changes)

Replaces the dot strip. Same section title, same range control (30 nights / 90 nights / a year /
everything), same card.

- **Summary tiles** (four, 24 px numbers): "Nights out 15 of 30" with a strip of squares, one per
  night, filled when any scope was out; "Integration captured 137.1 h" with a thin share bar by
  scope; "Nights with the moon under half lit 9 of 15" (illumination < 0.5 at local midnight) with
  a bar; "Biggest night 16.5 h · Fri 9 Oct · 3 scopes out". Under the title one line of facts:
  "Out 15 of the last 30 nights, and 9 of the 15 moon-dark ones · the S50 Pro took 44% of the
  hours" (a rule, never an opinion).
- **Moon row** (30-night range only): one small disc per night drawn from the illumination
  fraction, "New" and "Full" labelled; each night's column has a faint glow in proportion to the
  illumination. Illumination is computed in the page from the date alone (synodic month
  29.530588853 d from the 2000-01-06 18:14 UTC new moon; fraction = (1 − cos(2π·age/29.5306))/2),
  for local midnight of the night. Say "moon under half lit", never "dark sky" (the moon may be below
  the horizon; we don't compute that).
- **All scopes row**: one stacked column per night, segments in the scope colours in the fixed
  order bottom-up, height = hours, an "8 h" guide line (nice tick from `niceTicks`). The selected
  night's column shows its total above it.
- **One row per scope, in the fixed order** (`D.scopeOrder`, never sorted by hours — Brett's
  rule). Label: dot, name, then "59.7 h · 15 nights · 44%" (its share of the range's hours).
  Bars: height = hours; the hatched fill (`hatchFor`) for frames with no exposure; a faint speck for
  a night not out; the selected night's bars get a ring. Scopes with no frames in the range leave
  the rows and go into one line under the chart: "Resting this period · ● Seestar S30 57 nights ·
  last out 22 Aug · ● Seestar S50 147 nights · last out 24 May".
- **Longer ranges**: 90 nights = weeks, a year = months, everything = months (or quarters past
  36 months): one column per bin, the bin's nights count written on the column, the moon row
  hidden, tiles still count nights. Use the page's `binFor` logic; the subtitle must say what a
  column is.
- **Selected night panel** on the right of the chart (inside the section, not the drawer): "Fri 16
  Oct · 13.9 h · across 2 scopes", the moon (disc and "First quarter · 43%"), then per scope a row
  with an hours bar and the objects named ("Tadpoles Nebula 503 frames · 1.4 h"). "‹ Previous night
  out" and "Next night out ›" buttons; ← → keys walk nights out; clicking a column selects it; the
  newest night out is selected on load. An object in the panel opens the existing night panel
  (`openNight`). This replaces the hover tooltip and the keyboard-hint row. Phone: the panel sits
  under the chart.
- Legend, three items: "length is hours imaged", "column glow is moonlight", "a speck is no frames
  that night".
- Axis: day numbers, nights out in bold, month names at the first of each month, "last night"
  marked, the last-14-nights band labelled under the axis.
- Both themes (Brett's mockup is dark; the light theme uses the craft tokens).

## 4. What each scope shot (charts/findings.md proposal 1, mock `charts/mock-1-*.png`)

Under the chart, sharing its range: one 20 px bar per scope (fixed order), length = hours in the
range, split into object pieces in the scope's colour with 2 px gaps (≤ 6 named + "N more
objects"), the name and hours inside a piece when they fit, else a number; under each bar a
numbered line naming every piece with its hours; the tip "162.9 h · 42 nights · 29 objects"; a
hatched stub "+ 860 frames, hours unknown"; a resting scope = one muted line. Hover/tap/focus a
piece: value-first tooltip (object, hours, nights, frames, last night); click opens the project
(`openProject`). "View as table" twin.

## 5. Project cards (charts/findings.md proposal 2 + craft/findings.md §4)

- The ring (donut) stays, 56 px, 7 px stroke, and gets its key: under the meta line, **one row per
  scope**: scope dot + name, its hours, then its next step as glyph + word in the state's ink
  ("● Askar FRA400 · 60.0 h ·········· ◑ Finish it"); only "Ready to process" bold. This replaces
  the stack of pills (the pills remain in the opened panel's table where they have room).
- Meta line: "101.7 h · 4,956 frames · 35 nights · latest 16 Oct: 503 frames on the S30 Pro";
  "mosaic" becomes "mosaic on the S30 Pro" (from `programmes[].mosaic`).
- The mini timeline becomes **one lane per scope** (the card's scopes, fixed order), 18 px each,
  52 px labels, dots in the scope's own colour, the last-14-nights band and the "last night" line
  across all lanes, "‹N" earlier count per lane; no grey shared dots. 120 nights.
- The opened card keeps its lanes table and three marks; its nights table opens by default when
  ≤ 8 nights.

## 6. The header (hierarchy/findings.md §2, mock `hierarchy/after-header-closeup.png`)

- Row 1 (44 px): left "Astro Archive Observatory" 16/700 with the eyebrow "PC · E:\Astro Image
  Data" 11 px mono; under it one 12 px freshness line (truth §2): "Built on the PC at 03:38 this
  morning · 19 h old · from the Mac's record of 18 Oct 21:04", the live pill reduced to the
  connection ("live", "rebuilding…", "importer not answering"), and, only when a camera holds
  files, a 22 px amber chip "⚠ 87 files still on the ASIAir" (the sentence on hover; click scrolls
  to the Recent nights line). Right: the hours number 28/700 + "hours of integration" 13 px, and
  "120,571 frames · 87 targets · 240 nights · 6 scopes" 12 px under it.
- Row 2: a 10 px share strip with no in-bar labels, then ONE 12 px key line "● S30 Pro 386.0 h ·
  29% · 115 nights · ● S30 …" (this is the scope legend; the numbered tick fallback and the "1"
  prefix go). Clicking a scope's name opens its timeline (`openScope`), as now.
- The sticky bar (44 px): the view tabs, a **Key** button that opens the folded legend (what the
  glyphs, bands and hatching mean), **Refresh now** (posts `{kind:"observatory-refresh"}` through
  `ask()`; the panel rebuilds; the page's 30 s poll shows "rebuilding…" then "updated just now"),
  the theme toggle. The mono "record built" stamp leaves the bar and the footer keeps the one full
  provenance line.
- Target: ≤ 110 px of dark band + 44 px sticky bar before content, in both themes (the band stays
  dark in both; it is the page's identity, kept short).
- Hero numbers: one rounding rule (truth §5): totals are sums of the displayed parts.

## 7. Polish (craft/findings.md, `craft/polish.css` is the reference)

Tokens: light page `#eeeae0`, card `#fffefb`, line `#d9d3c5`, ink2 `#403e52`, muted `#625f74`;
dark card `#181d36`, line `#303860`, muted `#9aa0bd`. Lead numbers 15/600 ink; sentences 13/400
ink2; one bold per line; rail names 14/600. Cards white on the page, radius 12, one border per
level (no border + tint + shadow stacks). Legends ≤ 3 items; keyboard hints only on
`:focus-within`; section sub-lines ≤ 72 characters of facts. Text drawn on a scope colour is always
`#15141f`. No dust dots (the chart's speck is one 2 px mark, not a row of grey dots).

## 8. Truth fixes (truth/findings.md, all except #4 which stays as it is)

1 week bins always numbered and the subtitle says "a column is a week" (now bars, §3);
2 one freshness line (§6); 3 the pending-import line (§2, with the new fields);
5 one rounding; 6 share-bar labels (§6); 7 per-scope rows instead of three "Finish it" pills (§5);
8 no truncation: "quiet for 90 nights / last out 24 May · 147 nights ago" on two lines, marks wrap;
9 "‹N" explained where it appears ("+80 nights before this range" in a tooltip and in the Key);
10–17: legend entries true for the range; "hours unknown" swatch not in a scope colour; "mosaic on
the S30 Pro"; "everything" is not "90 nights" for a young project; "see Data checks" everywhere
(never "Data health"); "ready to process from 31 Oct"; label the Mac's Refresh as rebuilding the
Mac's record while the PC's newer copy is shown; the storage pill is the panel's, out of scope.

## 9. The engine and the panel (done by the lead, not the page builder)

- Engine `save_scan_summary(..., target_names=[...], elsewhere_machine=...)` and
  `read_scan_summary()` → `pendingImport.targetNames` (list of display names, ≤ 12) and
  `pendingImport.elsewhereMachine` (the other computer's label or null). Missing → `[]` / null;
  the page must cope with both absent.
- Panel: on `observatory-ready` it hides its own "Worked out … Refresh now" row (keeps it while the
  frame is a note); handles `{kind:"observatory-refresh"}` exactly as its Refresh button; handles
  `{kind:"open-panel"}` by switching to the Panel tab; hides its footer engine line while the
  Observatory tab is showing. Message checks stay same-origin, same-frame.

## 10. What must not break (the suites read the page)

Keep these exact strings in the page: `function openScope(cam)`, `function scopePanelFor(cam`,
at least four `openScope(` call sites, `function openNight(cam,night,target,host`,
`function nightPanelFor(cam,night,target)`, the range literal
`["90","90 nights",90],["365","a year",365],["all","everything",`, `what it has been doing`,
`Timeline of its projects`, `function normalise(d)`, `reconciliation:[],warnings:[]`,
`What each scope captured`, `Needs your attention`, `Astro Archive Observatory`, the dataset slot
`<script id="dataset" type="application/json">__DATASET__</script>` exactly once and nothing else
named `__DATASET__`, `kind:"observatory-ready"` posted on load. Every `<script>` block must parse
in node. No external URL anywhere. `test_app.py` lines 1700–1815 and `test_v2.py` chain OB (search
"OB the dataset block") are the checks; read them. Run `python3 test_app.py` from the repo root
when the page is in place (it takes a few minutes; never run it at the same time as `test_v2.py`).

## 11. Delivery

The page builder works on a copy, then puts the finished `astro-observatory.html` in the repo,
renders it with `scratchpad/ux2/render.py` and the real-size `R/truth/stress-dataset.json`
(colours renamed to Brett's six as `history/dataset-history.json` does) and screenshots the
Overview at 1440×900 and 2000×1100 in both themes, a project card, the selected-night panel, the
Recent nights ledger, and a 390 px phone view (`A/shoot_phone.sh`), into
`scratchpad/ux3/built/`. Then a short BUILD-NOTES.md: what was built, what was left out and why,
and which strings the lead should assert in the suites.
